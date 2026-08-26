#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
umask 077

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
PORTABILITY_HELPER="$SCRIPT_DIR/../lib/shell_portability.sh"
# shellcheck disable=SC1090
source "$PORTABILITY_HELPER"
REPOSITORY_ROOT=$(CDPATH='' cd -- "$SCRIPT_DIR/../.." && pwd -P)
COMPOSE_FILE="$REPOSITORY_ROOT/deploy/compose.prod.yml"
ENV_FILE=${POKECRACK_ENV_FILE:-/etc/pokecrack/production.env}
IMAGE_RETENTION_HOURS=${IMAGE_RETENTION_HOURS:-168}
DRY_RUN=false

die() {
  printf 'cleanup: %s\n' "$*" >&2
  exit 1
}

usage() {
  cat >&2 <<'USAGE'
Usage: cleanup.sh [--env-file ABSOLUTE_PATH] [--image-retention-hours HOURS] [--dry-run]

Removes stopped containers in the Pokecrack Compose project and unused, labeled
Pokecrack images older than the retention period. It never stops running services,
prunes global build cache/volumes, or removes browser profiles/extensions/backups.
USAGE
}

while (($#)); do
  case $1 in
    --env-file) (($# >= 2)) || die "--env-file requires a value"; ENV_FILE=$2; shift 2 ;;
    --image-retention-hours) (($# >= 2)) || die "--image-retention-hours requires a value"; IMAGE_RETENTION_HOURS=$2; shift 2 ;;
    --dry-run) DRY_RUN=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[[ $ENV_FILE == /* && -f $ENV_FILE && ! -L $ENV_FILE ]] || die "environment file must be an absolute regular, non-symlink file"
[[ $IMAGE_RETENTION_HOURS =~ ^[1-9][0-9]*$ ]] || die "image retention must be a positive integer"
[[ -f $COMPOSE_FILE ]] || die "Compose file is missing"
for command in docker stat; do
  command -v "$command" >/dev/null 2>&1 || die "required command not found: $command"
done
mode=$(pokecrack_stat_mode "$ENV_FILE") || die "could not validate environment file permissions"
[[ $mode =~ ^[0-7]{3,4}$ ]] || die "could not validate environment file permissions"
permissions=$((8#$mode))
(( (permissions & 0077) == 0 )) || die "environment file must have mode 0600"

export DEPLOY_SHA=${DEPLOY_SHA:-0000000000000000000000000000000000000000}
[[ $DEPLOY_SHA =~ ^[0-9a-f]{40}$ ]] || die "DEPLOY_SHA must be a lowercase 40-character SHA when set"
compose=(docker compose --project-name pokecrack --env-file "$ENV_FILE" -f "$COMPOSE_FILE")

docker compose version >/dev/null
"${compose[@]}" config --quiet
if [[ $DRY_RUN == true ]]; then
  "${compose[@]}" ps --all
  docker image ls --filter label=com.pokecrack.runtime=worker
  docker image ls --filter label=com.pokecrack.runtime=auth-browser
  printf 'Dry run only; no containers or images were removed.\n'
  exit 0
fi

# `compose rm` only removes stopped service containers because --stop is omitted.
"${compose[@]}" rm --force
docker image prune --all --force \
  --filter label=com.pokecrack.runtime=worker \
  --filter "until=${IMAGE_RETENTION_HOURS}h"
docker image prune --all --force \
  --filter label=com.pokecrack.runtime=auth-browser \
  --filter "until=${IMAGE_RETENTION_HOURS}h"
printf 'Cleanup completed without stopping services or pruning volumes.\n'
