# coding-search

Python SDK for the Coding Search API. One endpoint, typed responses, typed errors, sync + async.

## Install

From this repo:

```bash
pip install -e ./sdk
# or:  uv pip install -e ./sdk
```

## Quickstart

```python
from coding_search import Client

with Client() as c:
    r = c.search("how to handle connection pooling in asyncpg")
    for hit in r.results:
        print(hit.position, hit.domain, hit.url)
```

The default base URL points at `http://54.70.137.0:8080`. Override per-client or via the `CODING_SEARCH_BASE_URL` environment variable.

## Async

```python
import asyncio
from coding_search import AsyncClient

async def main():
    async with AsyncClient() as c:
        r = await c.search("react useEffect cleanup function")
        return r.results

asyncio.run(main())
```

## One-shot

```python
from coding_search import search

r = search("how to use python asyncio gather")
print(r.metadata.search_id, len(r.results))
```

Creates and tears down a `Client` per call — fine for scripts, but reuse a `Client` for high-frequency use so the HTTP connection pool persists.

## Request options

```python
c.search(
    "how to ...",
    max_results=5,            # 1-20, default 10
    max_chars_per_result=800, # 200-4000, default 1500
)
```

## Errors

All failures raise a `CodingSearchError` subclass. Catch the specific class or the base.

| Exception                  | HTTP | When                                | Retry?       |
| -------------------------- | ---- | ----------------------------------- | ------------ |
| `InvalidRequestError`      | 400  | request validation failed           | fix + retry  |
| `SearchUnavailableError`   | 502  | search backend failed               | yes, backoff |
| `SearchTimeoutError`       | 502  | backend exceeded 10s                | yes, backoff |
| `CodingSearchError` (base) | —    | network errors + anything unmapped  | depends      |

Each carries `.detail` (string) and `.search_id` (UUID, present on 5xx — quote it when reporting issues).

```python
from coding_search import Client, SearchUnavailableError

with Client() as c:
    try:
        r = c.search("...")
    except SearchUnavailableError as exc:
        print("retry after backoff:", exc.detail, exc.search_id)
```

## Configuration

| Argument               | Default                       | Notes                                                  |
| ---------------------- | ----------------------------- | ------------------------------------------------------ |
| `base_url`             | `http://54.70.137.0:8080`     | Or `CODING_SEARCH_BASE_URL` env var                    |
| `timeout`              | `15.0`                        | Seconds; do not drop below 15s per integration guide   |
| `client`               | a fresh `httpx.(Async)Client` | Pass your own for connection-pool / proxy customization |

## Response shape

```python
SearchResponse(
    query: str,
    results: list[SearchResult],
    metadata: SearchMetadata,
)
SearchResult(url, title | None, excerpt, position, domain)
SearchMetadata(search_latency_ms, total_latency_ms, result_count, search_id)
```

All response types are frozen dataclasses — safe to log, hash, pass around.
