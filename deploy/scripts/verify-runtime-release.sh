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
SERVICE_SET=tcgdex
NOSTR_ENV_FILE=''
COMPOSE_EXEC_TIMEOUT_SECONDS=60

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
  --service-set NAME             Exact release service set (tcgdex or tcgdex-nostr)
  --nostr-env-file ABSOLUTE_PATH Nostr interpolation file (tcgdex-nostr only)
  --exec-timeout-seconds SEC     Bound each Compose/Docker probe (default: 60)

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
    --service-set) (($# >= 2)) || die "--service-set requires a value"; SERVICE_SET=$2; shift 2 ;;
    --nostr-env-file) (($# >= 2)) || die "--nostr-env-file requires a value"; NOSTR_ENV_FILE=$2; shift 2 ;;
    --exec-timeout-seconds) (($# >= 2)) || die "--exec-timeout-seconds requires a value"; COMPOSE_EXEC_TIMEOUT_SECONDS=$2; shift 2 ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[[ $target_sha =~ ^[0-9a-f]{40}$ ]] || die "deployment target must be an exact lowercase 40-character Git SHA"
[[ $ENV_FILE == /* && -f $ENV_FILE && ! -L $ENV_FILE ]] || die "environment file must be an absolute regular, non-symlink file"
case $SERVICE_SET in
  tcgdex)
    [[ -z $NOSTR_ENV_FILE ]] || die "the tcgdex service set does not accept a Nostr environment file"
    SERVICES=(collector scheduler watchdog)
    ;;
  tcgdex-nostr)
    [[ $NOSTR_ENV_FILE == /* && -f $NOSTR_ENV_FILE && ! -L $NOSTR_ENV_FILE ]] || \
      die "tcgdex-nostr requires an absolute regular, non-symlink Nostr environment file"
    [[ ! $ENV_FILE -ef $NOSTR_ENV_FILE ]] || die "Nostr environment file must be distinct from the production environment file"
    SERVICES=(collector scheduler watchdog nostr-collector)
    ;;
  *) die "unsupported service set: $SERVICE_SET (allowed: tcgdex, tcgdex-nostr)" ;;
esac
[[ -n $RELEASE_STARTED_AT && $RELEASE_STARTED_AT =~ ^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(Z|[+-][0-9]{2}:[0-9]{2})$ ]] || \
  die "--release-started-at must be a UTC ISO-8601 timestamp"
[[ $GRACE_SECONDS =~ ^[0-9]+$ && $GRACE_SECONDS -le 172800 ]] || die "grace seconds must be between 0 and 172800"
[[ $HEARTBEAT_STALE_SECONDS =~ ^[0-9]+$ && $HEARTBEAT_STALE_SECONDS -ge 30 && $HEARTBEAT_STALE_SECONDS -le 3600 ]] || \
  die "heartbeat stale seconds must be between 30 and 3600"
[[ $BACKUP_MAX_AGE_SECONDS =~ ^[0-9]+$ && $BACKUP_MAX_AGE_SECONDS -le 2592000 ]] || \
  die "backup max age seconds must be between 0 and 2592000"
[[ $COMPOSE_EXEC_TIMEOUT_SECONDS =~ ^[1-9][0-9]*$ && $COMPOSE_EXEC_TIMEOUT_SECONDS -le 120 ]] || \
  die "exec timeout seconds must be between 1 and 120"
[[ -f $COMPOSE_FILE && ! -L $COMPOSE_FILE ]] || die "Compose file is missing"

env_mode=$(pokecrack_stat_mode "$ENV_FILE") || die "could not validate environment file permissions"
[[ $env_mode =~ ^[0-7]{3,4}$ ]] || die "could not validate environment file permissions"
env_permissions=$((8#$env_mode))
(( (env_permissions & 0077) == 0 )) || die "environment file must be owner-only"
if [[ $SERVICE_SET == tcgdex-nostr ]]; then
  nostr_env_mode=$(pokecrack_stat_mode "$NOSTR_ENV_FILE") || die "could not validate Nostr environment file permissions"
  [[ $nostr_env_mode =~ ^[0-7]{3,4}$ ]] || die "could not validate Nostr environment file permissions"
  nostr_env_permissions=$((8#$nostr_env_mode))
  (( (nostr_env_permissions & 0077) == 0 )) || die "Nostr environment file must be owner-only"
fi

command -v docker >/dev/null 2>&1 || die "required command not found: docker"
command -v timeout >/dev/null 2>&1 || die "required command not found: timeout"
compose=(docker compose --project-name pokecrack --env-file "$ENV_FILE" -f "$COMPOSE_FILE")
if [[ $SERVICE_SET == tcgdex-nostr ]]; then
  compose=(docker compose --project-name pokecrack --env-file "$ENV_FILE" --env-file "$NOSTR_ENV_FILE" --profile nostr -f "$COMPOSE_FILE")
fi
export DEPLOY_SHA=$target_sha

bounded() {
  timeout --foreground --kill-after=5 "$COMPOSE_EXEC_TIMEOUT_SECONDS" "$@"
}

for service in "${SERVICES[@]}"; do
  container_id=$(bounded "${compose[@]}" ps -q "$service") || die "could not inspect the running service set"
  [[ $container_id =~ ^[0-9a-f]+$ ]] || die "running service set is incomplete"
  image_id=$(bounded docker inspect --format '{{.Image}}' "$container_id") || die "could not inspect the running service image"
  [[ $image_id =~ ^sha256:[0-9a-f]{64}$ ]] || die "running service image identity is unavailable"
  image_revision=$(bounded docker image inspect --format '{{index .Config.Labels "org.opencontainers.image.revision"}}' "$image_id") || \
    die "running service image revision is unavailable"
  [[ $image_revision == "$target_sha" ]] || die "running service image does not match the requested release"
done

set +e
bounded "${compose[@]}" exec -T watchdog pokecrack-worker verify-release \
  --release-started-at "$RELEASE_STARTED_AT" \
  --grace-seconds "$GRACE_SECONDS" \
  --heartbeat-stale-seconds "$HEARTBEAT_STALE_SECONDS" \
  --backup-max-age-seconds "$BACKUP_MAX_AGE_SECONDS" \
  --service-set "$SERVICE_SET"
verify_status=$?
set -e
case $verify_status in
  0|1|2) exit "$verify_status" ;;
  *) die "runtime release evidence probe timed out or could not run" ;;
esac
