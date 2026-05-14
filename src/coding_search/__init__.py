"""Python SDK for the Coding Search API.

Quickstart:

    from coding_search import Client

    with Client() as c:
        r = c.search("how to handle connection pooling in asyncpg")
        for hit in r.results:
            print(hit.position, hit.domain, hit.url)
"""

from coding_search._client import (
    DEFAULT_BASE_URL,
    DEFAULT_TIMEOUT,
    AsyncClient,
    Client,
    CodingSearchError,
    InvalidRequestError,
    SearchMetadata,
    SearchResponse,
    SearchResult,
    SearchTimeoutError,
    SearchUnavailableError,
    search,
)

__version__ = "0.3.0"

__all__ = [
    "DEFAULT_BASE_URL",
    "DEFAULT_TIMEOUT",
    "AsyncClient",
    "Client",
    "CodingSearchError",
    "InvalidRequestError",
    "SearchMetadata",
    "SearchResponse",
    "SearchResult",
    "SearchTimeoutError",
    "SearchUnavailableError",
    "__version__",
    "search",
]
