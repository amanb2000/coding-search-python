"""``coding-search`` — terminal client for the Coding Search API.

Three output modes:

* default (TTY-friendly): one line per result, ``rank. domain - title``
  on top and the URL underneath.
* ``--urls``: one URL per line — pipe-friendly for ``xargs`` / shell loops.
* ``--json``: full ``SearchResponse`` as JSON.

Query is taken from the positional argument, or read from stdin if stdin
is not a TTY (e.g. ``echo "..." | coding-search``). If neither is
present, ``--help`` is printed and the process exits 2.
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Sequence

from coding_search import __version__
from coding_search._client import (
    DEFAULT_TIMEOUT,
    Client,
    CodingSearchError,
    SearchResponse,
)


def _build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="coding-search",
        description="Query the Coding Search API from the terminal.",
    )
    p.add_argument(
        "query",
        nargs="?",
        help="search query; if omitted, reads from stdin (when piped)",
    )
    p.add_argument(
        "--api-key",
        default=None,
        help="API key. Falls back to CODING_SEARCH_API_KEY env var.",
    )
    p.add_argument(
        "--base-url",
        default=None,
        help="Override the proxy base URL. Falls back to CODING_SEARCH_BASE_URL.",
    )
    p.add_argument(
        "--max-results",
        type=int,
        default=None,
        metavar="N",
        help="1-20, default 10",
    )
    p.add_argument(
        "--max-chars-per-result",
        type=int,
        default=None,
        metavar="N",
        help="200-4000, default 1500 (only affects --json output)",
    )
    p.add_argument(
        "--timeout",
        type=float,
        default=DEFAULT_TIMEOUT,
        metavar="SEC",
        help=f"client timeout in seconds (default: {DEFAULT_TIMEOUT})",
    )
    out = p.add_mutually_exclusive_group()
    out.add_argument("--json", dest="json_out", action="store_true", help="emit full JSON")
    out.add_argument("--urls", action="store_true", help="emit only URLs, one per line")
    p.add_argument(
        "-V",
        "--version",
        action="version",
        version=f"%(prog)s {__version__}",
    )
    return p


def _resolve_query(args: argparse.Namespace) -> str | None:
    if args.query is not None:
        return args.query.strip() or None
    if not sys.stdin.isatty():
        piped = sys.stdin.read().strip()
        return piped or None
    return None


def _print_human(response: SearchResponse) -> None:
    m = response.metadata
    print(f"search_id: {m.search_id}  ({m.result_count} results in {m.total_latency_ms}ms)")
    print()
    for r in response.results:
        title = r.title or "(no title)"
        print(f"  {r.position}. {r.domain} — {title}")
        print(f"     {r.url}")


def _print_urls(response: SearchResponse) -> None:
    for r in response.results:
        print(r.url)


def _print_json(response: SearchResponse) -> None:
    payload = {
        "query": response.query,
        "results": [asdict(r) for r in response.results],
        "metadata": asdict(response.metadata),
    }
    print(json.dumps(payload, indent=2, ensure_ascii=False))


def main(argv: Sequence[str] | None = None) -> int:
    parser = _build_parser()
    args = parser.parse_args(argv)

    query = _resolve_query(args)
    if query is None:
        parser.print_help(sys.stderr)
        return 2

    try:
        with Client(
            api_key=args.api_key,
            base_url=args.base_url,
            timeout=args.timeout,
        ) as c:
            response = c.search(
                query,
                max_results=args.max_results,
                max_chars_per_result=args.max_chars_per_result,
            )
    except CodingSearchError as exc:
        print(f"error: {exc.detail}", file=sys.stderr)
        if exc.search_id:
            print(f"search_id: {exc.search_id}", file=sys.stderr)
        return 1

    if args.json_out:
        _print_json(response)
    elif args.urls:
        _print_urls(response)
    else:
        _print_human(response)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
