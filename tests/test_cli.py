"""Tests for the ``coding-search`` CLI entry point."""

from __future__ import annotations

import json

import httpx
import pytest
import respx

from coding_search._cli import main

_BASE = "http://test"
_URL = f"{_BASE}/api/search"

_SAMPLE: dict = {
    "query": "test",
    "results": [
        {
            "url": "https://realpython.com/primer-on-python-decorators/",
            "title": "Primer on Python Decorators",
            "excerpt": "Decorators allow you to wrap a function ...",
            "position": 1,
            "domain": "realpython.com",
        },
        {
            "url": "https://docs.python.org/3/glossary.html",
            "title": None,
            "excerpt": "Glossary of terms ...",
            "position": 2,
            "domain": "docs.python.org",
        },
    ],
    "metadata": {
        "search_latency_ms": 110,
        "total_latency_ms": 130,
        "result_count": 2,
        "search_id": "cli-search-id",
    },
}


@respx.mock
def test_human_default_output(capsys: pytest.CaptureFixture[str]) -> None:
    respx.post(_URL).mock(return_value=httpx.Response(200, json=_SAMPLE))
    rc = main(["--base-url", _BASE, "test"])
    out = capsys.readouterr().out
    assert rc == 0
    assert "search_id: cli-search-id" in out
    assert "(2 results in 130ms)" in out
    assert "1. realpython.com — Primer on Python Decorators" in out
    assert "https://realpython.com/primer-on-python-decorators/" in out
    assert "2. docs.python.org — (no title)" in out


@respx.mock
def test_urls_mode(capsys: pytest.CaptureFixture[str]) -> None:
    respx.post(_URL).mock(return_value=httpx.Response(200, json=_SAMPLE))
    rc = main(["--base-url", _BASE, "--urls", "test"])
    out = capsys.readouterr().out
    assert rc == 0
    lines = out.strip().splitlines()
    assert lines == [
        "https://realpython.com/primer-on-python-decorators/",
        "https://docs.python.org/3/glossary.html",
    ]


@respx.mock
def test_json_mode_emits_full_response(capsys: pytest.CaptureFixture[str]) -> None:
    respx.post(_URL).mock(return_value=httpx.Response(200, json=_SAMPLE))
    rc = main(["--base-url", _BASE, "--json", "test"])
    out = capsys.readouterr().out
    assert rc == 0
    parsed = json.loads(out)
    assert parsed["query"] == "test"
    assert len(parsed["results"]) == 2
    assert parsed["metadata"]["search_id"] == "cli-search-id"


@respx.mock
def test_api_key_forwarded(capsys: pytest.CaptureFixture[str]) -> None:
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_SAMPLE))
    rc = main(["--base-url", _BASE, "--api-key", "cli-key-42", "test"])
    assert rc == 0
    assert route.calls.last.request.headers.get("authorization") == "Bearer cli-key-42"


@respx.mock
def test_passes_max_results(capsys: pytest.CaptureFixture[str]) -> None:
    route = respx.post(_URL).mock(return_value=httpx.Response(200, json=_SAMPLE))
    rc = main(["--base-url", _BASE, "--max-results", "5", "test"])
    assert rc == 0
    body = route.calls.last.request.read()
    assert b'"max_results":5' in body


@respx.mock
def test_search_error_exits_one(capsys: pytest.CaptureFixture[str]) -> None:
    respx.post(_URL).mock(
        return_value=httpx.Response(
            502,
            json={
                "error": {
                    "type": "search_unavailable",
                    "detail": "backend down",
                    "search_id": "sid-x",
                }
            },
        )
    )
    rc = main(["--base-url", _BASE, "test"])
    err = capsys.readouterr().err
    assert rc == 1
    assert "error: backend down" in err
    assert "search_id: sid-x" in err


def test_no_query_no_stdin_prints_help(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    # Force isatty() to True so the no-stdin path is taken.
    import sys

    class _TTYStdin:
        def isatty(self) -> bool:
            return True

    monkeypatch.setattr(sys, "stdin", _TTYStdin())
    rc = main([])
    err = capsys.readouterr().err
    assert rc == 2
    assert "usage" in err.lower()


def test_mutually_exclusive_json_and_urls() -> None:
    with pytest.raises(SystemExit) as exc:
        main(["--json", "--urls", "test"])
    assert exc.value.code == 2  # argparse exits 2 on mutually-exclusive violation


@respx.mock
def test_query_from_stdin(
    capsys: pytest.CaptureFixture[str], monkeypatch: pytest.MonkeyPatch
) -> None:
    """If no positional arg and stdin is piped, read query from stdin."""
    import io
    import sys

    respx.post(_URL).mock(return_value=httpx.Response(200, json=_SAMPLE))

    class _PipedStdin(io.StringIO):
        def isatty(self) -> bool:
            return False

    monkeypatch.setattr(sys, "stdin", _PipedStdin("stdin-query\n"))
    rc = main(["--base-url", _BASE])
    out = capsys.readouterr().out
    assert rc == 0
    assert "search_id: cli-search-id" in out
