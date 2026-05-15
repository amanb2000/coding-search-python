# coding-search

Python SDK for the Coding Search API. One endpoint, typed responses, typed errors, sync + async.

## Install

One-liner (macOS / Linux). Installs everything — including a Python toolchain if you don't have one — and wires the `coding-search` CLI into your `$PATH`:

```bash
curl -fsSL https://raw.githubusercontent.com/andre-fu/coding-search-python/main/install.sh | bash
```

The script:

1. Installs [`uv`](https://docs.astral.sh/uv/) if it isn't already on `$PATH`.
2. Runs `uv tool install` to drop `coding-search` into an isolated venv under `~/.local`.
3. Calls `uv tool update-shell` so `~/.local/bin` is on `$PATH` in new shells.

No `sudo`, no system-Python pollution, idempotent — re-running upgrades to the latest `main`. After install, open a new shell (or `source` your rc file) and run `coding-search --help`.

If you'd rather skip the script, the same thing in two commands:

```bash
uv tool install git+https://github.com/andre-fu/coding-search-python.git
# or, without uv:
pipx install git+https://github.com/andre-fu/coding-search-python.git
```

Or install the published package directly from PyPI:

```bash
pip install coding-search
# or:  uv add coding-search
```

From a local clone (for development):

```bash
pip install -e .
# or:  uv pip install -e .
```

Any of these install both the Python library and the `coding-search` CLI.

## CLI

```bash
coding-search "how to handle connection pooling in asyncpg"

# Just URLs, one per line — pipe-friendly
coding-search --urls "python pathlib glob"

# Full response as JSON
coding-search --json "react useEffect cleanup"

# Pipe a query in
echo "asyncio gather return exceptions" | coding-search --urls

# Send your API key (or set CODING_SEARCH_API_KEY)
coding-search --api-key acme-prod "..."

# Show all options
coding-search --help
```

Exits non-zero on error; error message goes to stderr. The CLI uses the same env vars as the library (`CODING_SEARCH_API_KEY`, `CODING_SEARCH_BASE_URL`).

## Quickstart

```python
from coding_search import Client

with Client(api_key="your-key") as c:
    r = c.search("how to handle connection pooling in asyncpg")
    for hit in r.results:
        print(hit.position, hit.domain, hit.url)
```

The default base URL points at `http://54.70.137.0:8080`. Override per-client or via the `CODING_SEARCH_BASE_URL` environment variable.

The `api_key` is **optional and not validated today** — it is forwarded as `Authorization: Bearer <key>` so the server can attribute traffic per consumer in the request logs. Set it via the `api_key=` argument or the `CODING_SEARCH_API_KEY` environment variable; omit it for ad-hoc testing.

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

| Argument               | Default                       | Notes                                                                       |
| ---------------------- | ----------------------------- | --------------------------------------------------------------------------- |
| `api_key`              | `None`                        | Or `CODING_SEARCH_API_KEY`; sent as `Authorization: Bearer ...` for tracking (not validated today) |
| `base_url`             | `http://54.70.137.0:8080`     | Or `CODING_SEARCH_BASE_URL` env var                                         |
| `timeout`              | `15.0`                        | Seconds; do not drop below 15s per integration guide                        |
| `client`               | a fresh `httpx.(Async)Client` | Pass your own for connection-pool / proxy customization                     |

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
