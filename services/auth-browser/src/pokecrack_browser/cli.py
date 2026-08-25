"""JSON-only command-line contract for the authenticated browser service."""

from __future__ import annotations

import argparse
import json
import sys
from collections.abc import Sequence
from typing import Any, NoReturn

from .adapters import AdapterConfigError, load_adapter
from .config import ServiceSettings
from .errors import ServiceError
from .health import HealthChecker, check_auth, run_doctor
from .manager import BrowserManager
from .paths import PathValidationError, validate_profile_name
from .redaction import redact
from .runner import OpenCliRunner

COMMANDS = (
    "start-profile",
    "stop-profile",
    "status",
    "doctor",
    "run-opencli",
    "check-auth",
)


class JsonArgumentParser(argparse.ArgumentParser):
    def error(self, message: str) -> NoReturn:
        payload = ServiceError("invalid_request", message).as_payload()
        print(json.dumps(payload, sort_keys=True), file=sys.stderr)
        raise SystemExit(2)


def _add_dry_run(parser: argparse.ArgumentParser) -> None:
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Validate and show the action without changing state or running a command.",
    )


def build_parser() -> argparse.ArgumentParser:
    parser = JsonArgumentParser(
        prog="pokecrack-browser",
        description="Manage the authenticated Chromium/OpenCLI runtime.",
    )
    parser.add_argument("--version", action="version", version="%(prog)s 0.1.0")
    subparsers = parser.add_subparsers(dest="command", required=True)

    start = subparsers.add_parser(
        "start-profile",
        help="Start a persistent headed Chromium profile.",
        description="Start a persistent headed Chromium profile.",
    )
    start.add_argument("profile", metavar="PROFILE")
    _add_dry_run(start)

    stop = subparsers.add_parser(
        "stop-profile",
        help="Stop the active Chromium profile.",
        description="Stop the active Chromium profile gracefully.",
    )
    stop.add_argument("profile", metavar="PROFILE")
    _add_dry_run(stop)

    subparsers.add_parser(
        "status",
        help="Report browser and bridge status.",
        description="Report browser, daemon, extension, CDP, and auth status.",
    )
    subparsers.add_parser(
        "doctor",
        help="Run local runtime diagnostics.",
        description="Run finite local runtime diagnostics.",
    )

    run = subparsers.add_parser(
        "run-opencli",
        help="Run one allowlisted OpenCLI adapter command.",
        description="Run one allowlisted OpenCLI adapter command.",
    )
    run.add_argument("adapter", metavar="ADAPTER")
    run.add_argument("--query", default="", help="Adapter query passed as one argv token.")
    run.add_argument("--max-results", type=int, default=None)
    _add_dry_run(run)

    auth = subparsers.add_parser(
        "check-auth",
        help="Check authenticated state for an adapter.",
        description="Check authenticated state without printing credentials.",
    )
    auth.add_argument("source", metavar="SOURCE")
    return parser


def _json(payload: dict[str, Any], *, stream: Any = sys.stdout) -> None:
    print(json.dumps(payload, sort_keys=True, separators=(",", ":")), file=stream)


def _profile_dry_run(command: str, profile: str) -> dict[str, Any]:
    validate_profile_name(profile)
    return {
        "ok": True,
        "action": command,
        "profile": profile,
        "dry_run": True,
    }


def main(argv: Sequence[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        if args.command in {"start-profile", "stop-profile"}:
            validate_profile_name(args.profile)
            if args.dry_run:
                _json(_profile_dry_run(args.command, args.profile))
                return 0
            manager = BrowserManager(ServiceSettings.from_env())
            if args.command == "start-profile":
                result = manager.start(args.profile)
            else:
                result = manager.stop(args.profile)
            _json(result)
            return 0
        if args.command == "run-opencli":
            settings = ServiceSettings.from_env()
            if args.dry_run:
                try:
                    adapter = load_adapter(args.adapter, settings.adapter_root)
                    requested_max = (
                        adapter.max_results if args.max_results is None else args.max_results
                    )
                    rendered = adapter.render_argv(
                        query=args.query,
                        max_results=requested_max,
                    )
                except AdapterConfigError as exc:
                    raise ServiceError("source_unavailable", str(exc)) from exc
                _json(
                    {
                        "ok": True,
                        "action": "run-opencli",
                        "adapter": adapter.name,
                        "adapter_version": adapter.version,
                        "profile": adapter.profile,
                        "argv": redact(rendered),
                        "dry_run": True,
                    }
                )
                return 0
            result = OpenCliRunner(settings).run(
                args.adapter,
                query=args.query,
                max_results=args.max_results,
            )
            _json(result)
            return 0
        settings = ServiceSettings.from_env()
        if args.command == "status":
            result = HealthChecker(settings).status()
            _json(result)
            return 0
        if args.command == "doctor":
            result = run_doctor(settings)
            _json(result)
            return 0 if result["ok"] else 1
        if args.command == "check-auth":
            result = check_auth(settings, args.source)
            _json(result)
            return 0
        raise ServiceError("invalid_request", f"unsupported command: {args.command}")
    except (PathValidationError, ValueError) as exc:
        error = ServiceError("invalid_request", str(exc))
    except ServiceError as exc:
        error = exc
    _json(error.as_payload(), stream=sys.stderr)
    return error.exit_code
