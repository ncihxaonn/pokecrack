#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
umask 077

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)

if (($# < 1)); then
  printf 'Usage: rollback.sh EXACT_40_CHARACTER_GIT_SHA [deploy.sh options]\n' >&2
  exit 2
fi
rollback_sha=$1
shift
[[ $rollback_sha =~ ^[0-9a-f]{40}$ ]] || {
  printf 'rollback: an explicit lowercase 40-character Git SHA is required\n' >&2
  exit 2
}

"$SCRIPT_DIR/deploy.sh" "$rollback_sha" "$@"
printf 'Rollback target %s is healthy for the selected deterministic service set.\n' \
  "$rollback_sha"
