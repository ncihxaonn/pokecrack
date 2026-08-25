# Authenticated Browser / OpenCLI Service

This private VPS service owns one headed Playwright Chromium persistent context at a time and runs only allowlisted OpenCLI adapter argv arrays. It has no HTTP API. CDP (`127.0.0.1:9222`) is health/debug only; adapters invoke their pinned CLI/Browser Bridge daemon directly.

## Local fixture verification

```bash
uv sync --frozen --extra dev
uv run pokecrack-browser --help
uv run pokecrack-browser run-opencli fixture --query fixture --max-results 1
uv run pokecrack-browser check-auth fixture
uv run pytest
```

The `fixture` adapter never launches Chromium, downloads OpenCLI, logs in, or contacts a platform. Live adapters and a real Chromium smoke test require operator-supplied pinned artifacts and authenticated profiles.

## Live artifact contracts

* The extension installer manages `/opt/pokecrack/opencli-extension/current -> releases/VERSION`. The validator permits only that exact in-root managed symlink and verifies `manifest.json` version.
* Mount the OpenCLI artifact read-only at `/opt/pokecrack/opencli`. Its `daemon-contract.json` must contain pinned `version`, `sha256`, `executable`, and an argv array using only complete `{executable}`, `{host}`, and `{port}` tokens. The executable checksum must equal `POKECRACK_OPENCLI_SHA256`.
* Supply an x11vnc-format password file at `/run/secrets/vnc_password`, owned by uid 10001 and mode 0600.
* Use host networking only so x11vnc, noVNC, CDP, and the daemon can bind `127.0.0.1`. Reach noVNC through an SSH tunnel; never publish these ports publicly.

## Profile safety

Allowed profiles are `social-western`, `social-chinese`, and `research-general`. Profile/runtime directories are mode 0700; state files are 0600. A lifetime flock permits only one active browser profile and a second flock serializes adapter runs. Profile contents (including cookies) are never emitted, included in image builds, backed up, or uploaded. Captured command output is bounded, ANSI-stripped, schema-validated, and credential-redacted before structured results are returned.

`start-profile` and `run-opencli` provide `--dry-run`. Shutdown sends SIGTERM and waits a finite interval before SIGKILL. There are no unbounded retries.
