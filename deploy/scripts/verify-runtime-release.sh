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
GRACE_SECONDS=21600
HEARTBEAT_STALE_SECONDS=180
BACKUP_MAX_AGE_SECONDS=172800
RELEASE_STARTED_AT=''

die() {
  printf 'verify-runtime-release: %s\n' "$*" >&2
  exit 2
}

usage() {
  cat >&2 <<'USAGE'
Usage: verify-runtime-release.sh EXACT_40_CHARACTER_GIT_SHA --release-started-at UTC_TIMESTAMP [options]

Options:
  --env-file ABSOLUTE_PATH       Compose interpolation file (default: /etc/pokecrack/production.env)
  --release-started-at TIMESTAMP UTC ISO-8601 release start (required for bounded grace)
  --grace-seconds SECONDS        First-run warming-up window (default: 21600)
  --heartbeat-stale-seconds SEC  Worker heartbeat stale threshold (default: 180)
  --backup-max-age-seconds SEC   Backup marker stale threshold (default: 172800)

The command only runs the read-only verifier in the already running watchdog
container. It does not apply migrations, deploy services, or print credentials.
USAGE
}

(($# >= 1)) || { usage; exit 2; }
target_sha=$1
shift
while (($#)); do
  case $1 in
    --env-file) (($# >= 2)) || die "--env-file requires a value"; ENV_FILE=$2; shift 2 ;;
    --release-started-at) (($# >= 2)) || die "--release-started-at requires a value"; RELEASE_STARTED_AT=$2; shift 2 ;;
    --grace-seconds) (($# >= 2)) || die "--grace-seconds requires a value"; GRACE_SECONDS=$2; shift 2 ;;
    --heartbeat-stale-seconds) (($# >= 2)) || die "--heartbeat-stale-seconds requires a value"; HEARTBEAT_STALE_SECONDS=$2; shift 2 ;;
    --backup-max-age-seconds) (($# >= 2)) || die "--backup-max-age-seconds requires a value"; BACKUP_MAX_AGE_SECONDS=$2; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[[ $target_sha =~ ^[0-9a-f]{40}$ ]] || die "deployment target must be an exact lowercase 40-character Git SHA"
[[ $ENV_FILE == /* && -f $ENV_FILE && ! -L $ENV_FILE ]] || die "environment file must be an absolute regular, non-symlink file"
[[ -n $RELEASE_STARTED_AT && $RELEASE_STARTED_AT =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(Z|[+-][0-9]{2}:[0-9]{2})$ ]] || \
  die "--release-started-at must be a UTC ISO-8601 timestamp"
[[ $GRACE_SECONDS =~ ^[0-9]+$ && $GRACE_SECONDS -le 172800 ]] || die "grace seconds must be between 0 and 172800"
[[ $HEARTBEAT_STALE_SECONDS =~ ^[0-9]+$ && $HEARTBEAT_STALE_SECONDS -ge 30 && $HEARTBEAT_STALE_SECONDS -le 3600 ]] || \
  die "heartbeat stale seconds must be between 30 and 3600"
[[ $BACKUP_MAX_AGE_SECONDS =~ ^[0-9]+$ && $BACKUP_MAX_AGE_SECONDS -le 2592000 ]] || \
  die "backup max age seconds must be between 0 and 2592000"
[[ -f $COMPOSE_FILE && ! -L $COMPOSE_FILE ]] || die "Compose file is missing"

env_mode=$(pokecrack_stat_mode "$ENV_FILE") || die "could not validate environment file permissions"
[[ $env_mode =~ ^[0-7]{3,4}$ ]] || die "could not validate environment file permissions"
env_permissions=$((8#$env_mode))
(( (env_permissions & 0077) == 0 )) || die "environment file must be owner-only"

command -v docker >/dev/null 2>&1 || die "required command not found: docker"
compose=(docker compose --project-name pokecrack --env-file "$ENV_FILE" -f "$COMPOSE_FILE")
export DEPLOY_SHA=$target_sha
"${compose[@]}" exec -T watchdog pokecrack-worker verify-release \
  --release-started-at "$RELEASE_STARTED_AT" \
  --grace-seconds "$GRACE_SECONDS" \
  --heartbeat-stale-seconds "$HEARTBEAT_STALE_SECONDS" \
  --backup-max-age-seconds "$BACKUP_MAX_AGE_SECONDS"
