"""Offline OpenCLI fixture executable used only by tests and smoke checks."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

VERSION = "fixture-opencli 1.0.0"


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--version", action="version", version=VERSION)
    subparsers = parser.add_subparsers(dest="command", required=True)
    query = subparsers.add_parser("query")
    query.add_argument("--fixture", type=Path, required=True)
    query.add_argument("--query", required=True)
    query.add_argument("--max-results", type=int, required=True)
    subparsers.add_parser("auth-health")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "auth-health":
        print(
            json.dumps(
                {
                    "authenticated": True,
                    "daemon_available": True,
                    "extension_connected": True,
                    "fixture": True,
                },
                separators=(",", ":"),
            )
        )
        return 0
    value = json.loads(args.fixture.read_text(encoding="utf-8"))
    value["items"] = value["items"][: args.max_results]
    value["fixture_query"] = args.query
    # The descriptor schema intentionally rejects undeclared fields; remove test trace.
    value.pop("fixture_query")
    print(json.dumps(value, separators=(",", ":")))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
