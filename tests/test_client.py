"""Minimal tests — respx-mocked transport, sync + async, happy path + errors."""

from __future__ import annotations

import httpx
import pytest
import respx

from coding_search import (
    AsyncClient,
    Client,
    CodingSearchError,
    InvalidRequestError,
    SearchTimeoutError,
    SearchUnavailableError,
    search,
)

_BASE = "http://test"
_URL = f"{_BASE}/api/search"

_SAMPLE_OK: dict = {
    "query": "test",
    "results": [
        {
            "url": "https://example.com/a",
            "title": "Example A",
            "excerpt": "hello",
            "position": 1,
            "domain": "example.com",
        },
        {
            "url": "https://docs.example.com/b",
            "title": None,
            "excerpt": "world",
            "position": 2,
            "domain": "docs.example.com",
        },
    ],
    "metadata": {
        "search_latency_ms": 123,
        "total_latency_ms": 145,
        "result_count": 2,
        "search_id": "abc-1234",
    },
}


@respx.mock
def test_sync_happy_path() -> None:
    respx.post(_URL).mock(return_value=httpx.Response(200, json=_SAMPLE_OK))
    with Client(base_url=_BASE) as c:
        r = c.search("test")
    assert r.query == "test"
    assert len(r.results) == 2
    assert r.results[0].position == 1
    assert r.results[1].title is None
    assert r.metadata.search_id == "abc-1234"


@respx.mock
def test_sync_invalid_request_raises() -> None:
    respx.post(_URL).mock(
        return_value=httpx.Response(
            400, json={"error": {"type": "invalid_request", "detail": "query too short"}}
        )
    )
    with Client(base_url=_BASE) as c, pytest.raises(InvalidRequestError) as exc:
        c.search("")
    assert "too short" in exc.value.detail
    assert exc.value.search_id is None  # 400s don't carry search_id


@respx.mock
def test_sync_unavailable_carries_search_id() -> None:
    respx.post(_URL).mock(
        return_value=httpx.Response(
            502,
            json={
                "error": {
                    "type": "search_unavailable",
                    "detail": "backend down",
                    "search_id": "sid-1",
                }
            },
        )
    )
    with Client(base_url=_BASE) as c, pytest.raises(SearchUnavailableError) as exc:
        c.search("anything")
    assert exc.value.search_id == "sid-1"


@respx.mock
def test_sync_timeout_raises_typed_error() -> None:
    respx.post(_URL).mock(
        return_value=httpx.Response(
            502,
            json={
                "error": {"type": "search_timeout", "detail": "timed out", "search_id": "sid-2"}
            },
        )
    )
    with Client(base_url=_BASE) as c, pytest.raises(SearchTimeoutError):
        c.search("anything")


@respx.mock
def test_sync_passes_optional_params() -> None:
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_SAMPLE_OK))
    with Client(base_url=_BASE) as c:
        c.search("q", max_results=5, max_chars_per_result=800)
    sent = route.calls.last.request
    body = sent.read()
    assert b'"max_results":5' in body
    assert b'"max_chars_per_result":800' in body


@respx.mock
def test_module_level_search() -> None:
    respx.post(_URL).mock(return_value=httpx.Response(200, json=_SAMPLE_OK))
    r = search("test", base_url=_BASE)
    assert r.metadata.result_count == 2


@respx.mock
def test_unknown_error_type_falls_back_to_base() -> None:
    respx.post(_URL).mock(
        return_value=httpx.Response(
            502, json={"error": {"type": "something_new", "detail": "?", "search_id": "x"}}
        )
    )
    with Client(base_url=_BASE) as c, pytest.raises(CodingSearchError) as exc:
        c.search("q")
    # Falls back to the base class, not one of the typed subclasses.
    assert type(exc.value) is CodingSearchError
    assert exc.value.search_id == "x"


@respx.mock
async def test_async_happy_path() -> None:
    respx.post(_URL).mock(return_value=httpx.Response(200, json=_SAMPLE_OK))
    async with AsyncClient(base_url=_BASE) as c:
        r = await c.search("test")
    assert r.metadata.search_id == "abc-1234"
    assert r.results[0].domain == "example.com"


@respx.mock
async def test_async_error_path() -> None:
    respx.post(_URL).mock(
        return_value=httpx.Response(
            502, json={"error": {"type": "search_unavailable", "detail": "x", "search_id": "y"}}
        )
    )
    async with AsyncClient(base_url=_BASE) as c:
        with pytest.raises(SearchUnavailableError):
            await c.search("q")


def test_env_var_base_url(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODING_SEARCH_BASE_URL", "https://override.example.com/")
    c = Client()
    # Trailing slash should be stripped.
    assert c._base_url == "https://override.example.com"


def test_explicit_base_url_wins_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODING_SEARCH_BASE_URL", "https://env.example.com")
    c = Client(base_url="https://arg.example.com")
    assert c._base_url == "https://arg.example.com"


@respx.mock
def test_api_key_sent_as_bearer() -> None:
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_SAMPLE_OK))
    with Client(base_url=_BASE, api_key="key-abc-123") as c:
        c.search("q")
    sent = route.calls.last.request
    assert sent.headers.get("authorization") == "Bearer key-abc-123"


@respx.mock
def test_no_api_key_omits_header() -> None:
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_SAMPLE_OK))
    with Client(base_url=_BASE) as c:
        c.search("q")
    sent = route.calls.last.request
    assert "authorization" not in sent.headers


@respx.mock
def test_api_key_from_env_var(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODING_SEARCH_API_KEY", "env-key-xyz")
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_SAMPLE_OK))
    with Client(base_url=_BASE) as c:
        c.search("q")
    sent = route.calls.last.request
    assert sent.headers.get("authorization") == "Bearer env-key-xyz"


@respx.mock
def test_arg_api_key_wins_over_env(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("CODING_SEARCH_API_KEY", "env-key")
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_SAMPLE_OK))
    with Client(base_url=_BASE, api_key="arg-key") as c:
        c.search("q")
    sent = route.calls.last.request
    assert sent.headers.get("authorization") == "Bearer arg-key"


@respx.mock
def test_empty_api_key_omits_header() -> None:
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_SAMPLE_OK))
    with Client(base_url=_BASE, api_key="   ") as c:
        c.search("q")
    sent = route.calls.last.request
    assert "authorization" not in sent.headers


@respx.mock
async def test_async_api_key_sent_as_bearer() -> None:
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_SAMPLE_OK))
    async with AsyncClient(base_url=_BASE, api_key="async-key") as c:
        await c.search("q")
    sent = route.calls.last.request
    assert sent.headers.get("authorization") == "Bearer async-key"
