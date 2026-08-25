#!/usr/bin/env bash
set -euo pipefail

if command -v pnpm >/dev/null 2>&1; then
  exec pnpm "$@"
fi

if [[ -x /opt/data/.local/bin/pnpm ]]; then
  exec /opt/data/.local/bin/pnpm "$@"
fi

printf "pnpm 11.23.0 is required but was not found.\n" >&2
exit 127
