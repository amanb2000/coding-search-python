"""Sync + async client, typed responses, typed errors.

Single file by design — the SDK has one endpoint and minimal surface.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any

import httpx

DEFAULT_BASE_URL = "http://54.70.137.0:8080"
"""Public proxy default. Override with the ``base_url`` arg or the
``CODING_SEARCH_BASE_URL`` environment variable."""

DEFAULT_TIMEOUT = 15.0
"""15s per the integration guide. Backend has a hard 10s upstream timeout
plus per-request overhead, so anything under 15s on the client side will
truncate retryable timeouts."""

_ENV_BASE_URL = "CODING_SEARCH_BASE_URL"
_PATH = "/api/search"


# ─── Types ───────────────────────────────────────────────────────────────


@dataclass(frozen=True, slots=True)
class SearchResult:
    url: str
    title: str | None
    excerpt: str
    position: int
    """1-indexed."""
    domain: str
    """Leading ``www.`` stripped."""


@dataclass(frozen=True, slots=True)
class SearchMetadata:
    search_latency_ms: int
    total_latency_ms: int
    result_count: int
    search_id: str
    """Opaque UUID. Quote this when reporting issues."""


@dataclass(frozen=True, slots=True)
class SearchResponse:
    query: str
    results: list[SearchResult]
    metadata: SearchMetadata


# ─── Errors ──────────────────────────────────────────────────────────────


class CodingSearchError(Exception):
    """Base class. Catch this if you want all SDK errors uniformly."""

    def __init__(self, detail: str, *, search_id: str | None = None) -> None:
        super().__init__(detail)
        self.detail = detail
        self.search_id = search_id


class InvalidRequestError(CodingSearchError):
    """400 — request body failed validation. Fix and retry."""


class SearchUnavailableError(CodingSearchError):
    """502 — search backend failed. Retry with exponential backoff."""


class SearchTimeoutError(CodingSearchError):
    """502 — search backend exceeded 10s. Retry with exponential backoff."""


_ERROR_TYPES: dict[str, type[CodingSearchError]] = {
    "invalid_request": InvalidRequestError,
    "search_unavailable": SearchUnavailableError,
    "search_timeout": SearchTimeoutError,
}


# ─── Parsing helpers ─────────────────────────────────────────────────────


def _resolve_base_url(base_url: str | None) -> str:
    return (base_url or os.getenv(_ENV_BASE_URL) or DEFAULT_BASE_URL).rstrip("/")


def _build_body(
    query: str, max_results: int | None, max_chars_per_result: int | None
) -> dict[str, Any]:
    body: dict[str, Any] = {"query": query}
    if max_results is not None:
        body["max_results"] = max_results
    if max_chars_per_result is not None:
        body["max_chars_per_result"] = max_chars_per_result
    return body


def _parse_response(raw: dict[str, Any]) -> SearchResponse:
    return SearchResponse(
        query=raw["query"],
        results=[
            SearchResult(
                url=r["url"],
                title=r.get("title"),
                excerpt=r["excerpt"],
                position=r["position"],
                domain=r["domain"],
            )
            for r in raw["results"]
        ],
        metadata=SearchMetadata(**raw["metadata"]),
    )


def _raise_for_error(response: httpx.Response) -> None:
    """Map a non-2xx response to a typed exception. Fail loud on malformed bodies."""
    status = response.status_code
    try:
        body = response.json()
    except ValueError as exc:
        raise CodingSearchError(
            f"HTTP {status}: non-JSON response ({response.text[:200]!r})"
        ) from exc

    err = body.get("error") or {}
    err_type = err.get("type", "")
    detail = err.get("detail") or f"HTTP {status}"
    search_id = err.get("search_id")
    cls = _ERROR_TYPES.get(err_type, CodingSearchError)
    raise cls(detail, search_id=search_id)


# ─── Sync client ─────────────────────────────────────────────────────────


class Client:
    """Synchronous client.

    Use as a context manager for automatic connection cleanup::

        with Client() as c:
            r = c.search("how to ...")

    Pass ``base_url`` or set ``CODING_SEARCH_BASE_URL`` to point at a
    non-default host.
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.Client | None = None,
    ) -> None:
        self._base_url = _resolve_base_url(base_url)
        self._owned = client is None
        self._client = client or httpx.Client(timeout=timeout)

    def search(
        self,
        query: str,
        *,
        max_results: int | None = None,
        max_chars_per_result: int | None = None,
    ) -> SearchResponse:
        """Issue a search. Raises a typed ``CodingSearchError`` subclass on failure."""
        url = f"{self._base_url}{_PATH}"
        body = _build_body(query, max_results, max_chars_per_result)
        try:
            response = self._client.post(url, json=body)
        except httpx.TimeoutException as exc:
            raise SearchTimeoutError(f"client-side timeout: {exc}") from exc
        except httpx.HTTPError as exc:
            raise CodingSearchError(f"transport error: {exc}") from exc

        if response.status_code >= 400:
            _raise_for_error(response)

        return _parse_response(response.json())

    def close(self) -> None:
        if self._owned:
            self._client.close()

    def __enter__(self) -> Client:
        return self

    def __exit__(self, *_exc: object) -> None:
        self.close()


# ─── Async client ────────────────────────────────────────────────────────


class AsyncClient:
    """Asynchronous client.

    Use as an async context manager for automatic cleanup::

        async with AsyncClient() as c:
            r = await c.search("how to ...")
    """

    def __init__(
        self,
        *,
        base_url: str | None = None,
        timeout: float = DEFAULT_TIMEOUT,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = _resolve_base_url(base_url)
        self._owned = client is None
        self._client = client or httpx.AsyncClient(timeout=timeout)

    async def search(
        self,
        query: str,
        *,
        max_results: int | None = None,
        max_chars_per_result: int | None = None,
    ) -> SearchResponse:
        """Issue a search. Raises a typed ``CodingSearchError`` subclass on failure."""
        url = f"{self._base_url}{_PATH}"
        body = _build_body(query, max_results, max_chars_per_result)
        try:
            response = await self._client.post(url, json=body)
        except httpx.TimeoutException as exc:
            raise SearchTimeoutError(f"client-side timeout: {exc}") from exc
        except httpx.HTTPError as exc:
            raise CodingSearchError(f"transport error: {exc}") from exc

        if response.status_code >= 400:
            _raise_for_error(response)

        return _parse_response(response.json())

    async def aclose(self) -> None:
        if self._owned:
            await self._client.aclose()

    async def __aenter__(self) -> AsyncClient:
        return self

    async def __aexit__(self, *_exc: object) -> None:
        await self.aclose()


# ─── Module-level convenience ────────────────────────────────────────────


def search(
    query: str,
    *,
    max_results: int | None = None,
    max_chars_per_result: int | None = None,
    base_url: str | None = None,
    timeout: float = DEFAULT_TIMEOUT,
) -> SearchResponse:
    """One-shot search. Creates and tears down a ``Client`` per call.

    For scripts and notebooks. For high-frequency use, instantiate a
    ``Client`` once and reuse it so the connection pool persists.
    """
    with Client(base_url=base_url, timeout=timeout) as c:
        return c.search(query, max_results=max_results, max_chars_per_result=max_chars_per_result)
