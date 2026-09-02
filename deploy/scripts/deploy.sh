#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
umask 077

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
PORTABILITY_HELPER="$SCRIPT_DIR/../lib/shell_portability.sh"
NOSTR_PREFLIGHT="$SCRIPT_DIR/../lib/verify_nostr_release.py"
RUNTIME_EVIDENCE_VERIFY="$SCRIPT_DIR/verify-runtime-release.sh"
# shellcheck disable=SC1090
source "$PORTABILITY_HELPER"
REPOSITORY_ROOT=$(CDPATH='' cd -- "$SCRIPT_DIR/../.." && pwd -P)
COMPOSE_FILE="$REPOSITORY_ROOT/deploy/compose.prod.yml"
ENV_FILE=${POKECRACK_ENV_FILE:-/etc/pokecrack/production.env}
NOSTR_ENV_FILE=${POKECRACK_NOSTR_ENV_FILE:-}
STATE_DIR=${POKECRACK_DEPLOY_STATE_DIR:-/var/lib/pokecrack/deploy}
HEALTH_TIMEOUT=${DEPLOY_HEALTH_TIMEOUT_SECONDS:-180}
RUNTIME_GRACE_SECONDS=${DEPLOY_RUNTIME_GRACE_SECONDS:-21600}
SERVICE_SET=tcgdex
RETIRE_NOSTR=false
VERIFY_RUNTIME=false
SERVICES=(collector scheduler watchdog)
SERVICES_CSV=collector,scheduler,watchdog
EXPECTED_CATALOG_SCHEDULE='0 2,14 * * *'
LEGACY_CATALOG_SCHEDULE='0 2 * * *'

rollback_marker() {
  local marker marker_mode version_line sha_line service_set_line services_line extra_line
  local rollback valid_marker
  marker="$STATE_DIR/last-successful-deployment"
  if [[ -d $STATE_DIR && ! -L $STATE_DIR && -f $marker && ! -L $marker ]]; then
    marker_mode=$(pokecrack_stat_mode "$marker") || return 0
    [[ $marker_mode == 600 ]] || return 0
    version_line=''
    sha_line=''
    service_set_line=''
    services_line=''
    extra_line=''
    valid_marker=true
    {
      IFS= read -r version_line || valid_marker=false
      IFS= read -r sha_line || valid_marker=false
      IFS= read -r service_set_line || valid_marker=false
      IFS= read -r services_line || valid_marker=false
      if IFS= read -r extra_line || [[ -n $extra_line ]]; then
        valid_marker=false
      fi
    } < "$marker"
    rollback=${sha_line#sha=}
    if [[ $valid_marker == true \
      && $version_line == 'version=1' \
      && $sha_line == "sha=$rollback" \
      && $rollback =~ ^[0-9a-f]{40}$ \
      && ( \
        ( $service_set_line == 'service_set=tcgdex' \
          && $services_line == 'services=collector,scheduler,watchdog' ) \
        || ( $service_set_line == 'service_set=tcgdex-nostr' \
          && $services_line == 'services=collector,scheduler,watchdog,nostr-collector' ) \
      ) ]]
    then
      printf "Rollback commit: %s (%s; %s)\n" \
        "$rollback" "$service_set_line" "$services_line" >&2
    fi
  fi
}

die() {
  printf "deploy: %s\n" "$*" >&2
  rollback_marker
  exit 1
}

usage() {
  cat >&2 <<'USAGE'
Usage: deploy.sh EXACT_40_CHARACTER_GIT_SHA [options]

Options:
  --env-file ABSOLUTE_PATH    Compose interpolation file (default: /etc/pokecrack/production.env)
  --nostr-env-file PATH       Dedicated Nostr interpolation/preflight file (tcgdex-nostr only)
  --state-dir ABSOLUTE_PATH   Success-marker directory (default: /var/lib/pokecrack/deploy)
  --health-timeout SECONDS    Health deadline (default: 180)
  --verify-runtime             Run aggregate runtime evidence after health checks
  --runtime-grace-seconds SEC First-run warming-up window (default: 21600)
  --service-set NAME          Exact release service set (tcgdex or tcgdex-nostr)
  --retire-nostr              Explicitly stop/remove only the managed Nostr container

The full service set is intentionally unavailable: ai-worker and aggregator do
not have safe live handlers in this release.
USAGE
}

(($# >= 1)) || { usage; exit 2; }
target_sha=$1
shift
while (($#)); do
  case $1 in
    --env-file) (($# >= 2)) || die "--env-file requires a value"; ENV_FILE=$2; shift 2 ;;
    --nostr-env-file) (($# >= 2)) || die "--nostr-env-file requires a value"; NOSTR_ENV_FILE=$2; shift 2 ;;
    --state-dir) (($# >= 2)) || die "--state-dir requires a value"; STATE_DIR=$2; shift 2 ;;
    --health-timeout) (($# >= 2)) || die "--health-timeout requires a value"; HEALTH_TIMEOUT=$2; shift 2 ;;
    --verify-runtime) VERIFY_RUNTIME=true; shift ;;
    --runtime-grace-seconds) (($# >= 2)) || die "--runtime-grace-seconds requires a value"; RUNTIME_GRACE_SECONDS=$2; shift 2 ;;
    --service-set) (($# >= 2)) || die "--service-set requires a value"; SERVICE_SET=$2; shift 2 ;;
    --retire-nostr) RETIRE_NOSTR=true; shift ;;
    -h|--help) usage; exit 0 ;;
    *) die "unknown argument: $1" ;;
  esac
done

[[ $target_sha =~ ^[0-9a-f]{40}$ ]] || die "deployment target must be an exact lowercase 40-character Git SHA"
[[ $ENV_FILE == /* ]] || die "environment file path must be absolute"
[[ -f $ENV_FILE && ! -L $ENV_FILE ]] || die "environment file must be a regular, non-symlink file"
[[ $STATE_DIR == /* ]] || die "state directory path must be absolute"
[[ $HEALTH_TIMEOUT =~ ^[1-9][0-9]*$ ]] || die "health timeout must be a positive integer"
[[ $RUNTIME_GRACE_SECONDS =~ ^[0-9]+$ && $RUNTIME_GRACE_SECONDS -le 172800 ]] || \
  die "runtime grace seconds must be between 0 and 172800"
[[ -f $COMPOSE_FILE ]] || die "Compose file is missing: $COMPOSE_FILE"
case $SERVICE_SET in
  tcgdex)
    [[ -z $NOSTR_ENV_FILE ]] || \
      die "the tcgdex service set does not accept a Nostr environment file"
    ;;
  tcgdex-nostr)
    [[ $RETIRE_NOSTR == false ]] || \
      die "tcgdex-nostr cannot be combined with --retire-nostr"
    SERVICES=(collector scheduler watchdog nostr-collector)
    SERVICES_CSV=collector,scheduler,watchdog,nostr-collector
    [[ -n $NOSTR_ENV_FILE && $NOSTR_ENV_FILE == /* ]] || \
      die "tcgdex-nostr requires an absolute Nostr environment file path"
    [[ -f $NOSTR_ENV_FILE && ! -L $NOSTR_ENV_FILE ]] || \
      die "Nostr environment file must be a regular, non-symlink file"
    [[ ! $ENV_FILE -ef $NOSTR_ENV_FILE ]] || \
      die "Nostr environment file must be distinct from the production environment file"
    [[ -f $NOSTR_PREFLIGHT && ! -L $NOSTR_PREFLIGHT ]] || \
      die "Nostr release preflight is missing"
    ;;
  full) die "full service set is unavailable because ai-worker and aggregator fail closed in live mode" ;;
  *) die "unsupported service set: $SERVICE_SET (allowed: tcgdex, tcgdex-nostr)" ;;
esac

for command in date docker git install mktemp python3 stat; do
  command -v "$command" >/dev/null 2>&1 || die "required command not found: $command"
done

env_mode=$(pokecrack_stat_mode "$ENV_FILE") || die "could not validate environment file permissions"
[[ $env_mode =~ ^[0-7]{3,4}$ ]] || die "could not validate environment file permissions"
env_permissions=$((8#$env_mode))
(( (env_permissions & 0077) == 0 )) || die "environment file must not be accessible by group or other users (use mode 0600)"
if [[ $SERVICE_SET == tcgdex-nostr ]]; then
  nostr_env_mode=$(pokecrack_stat_mode "$NOSTR_ENV_FILE") || \
    die "could not validate Nostr environment file permissions"
  [[ $nostr_env_mode =~ ^[0-7]{3,4}$ ]] || \
    die "could not validate Nostr environment file permissions"
  nostr_env_permissions=$((8#$nostr_env_mode))
  (( (nostr_env_permissions & 0077) == 0 )) || \
    die "Nostr environment file must not be accessible by group or other users (use mode 0600)"
fi

validate_catalog_schedule_override() {
  local line value
  local seen=false
  value=''
  while IFS= read -r line || [[ -n $line ]]; do
    case $line in
      SCHEDULE_CATALOG_SYNC=*)
        [[ $seen == false ]] || \
          die "environment file contains duplicate SCHEDULE_CATALOG_SYNC entries"
        seen=true
        value=${line#SCHEDULE_CATALOG_SYNC=}
        ;;
    esac
  done < "$ENV_FILE"
  if [[ $seen == true \
    && ( $value == "$LEGACY_CATALOG_SCHEDULE" \
      || $value == "'$LEGACY_CATALOG_SCHEDULE'" \
      || $value == "\"$LEGACY_CATALOG_SCHEDULE\"" ) ]]; then
    die "environment file pins the retired once-daily TCGdex schedule; update it to ${EXPECTED_CATALOG_SCHEDULE} or choose a deliberate override"
  fi
  if [[ ${SCHEDULE_CATALOG_SYNC+x} == x \
    && ( $SCHEDULE_CATALOG_SYNC == "$LEGACY_CATALOG_SCHEDULE" \
      || $SCHEDULE_CATALOG_SYNC == "'$LEGACY_CATALOG_SCHEDULE'" \
      || $SCHEDULE_CATALOG_SYNC == "\"$LEGACY_CATALOG_SCHEDULE\"" ) ]]; then
    die "inherited environment pins the retired once-daily TCGdex schedule; update it to ${EXPECTED_CATALOG_SCHEDULE} or choose a deliberate override"
  fi
}

validate_catalog_schedule_override

[[ ! -L $STATE_DIR ]] || die "state directory must not be a symbolic link"
install -d -m 0700 "$STATE_DIR"
[[ -d $STATE_DIR && ! -L $STATE_DIR ]] || die "state directory is invalid"
manifest="$STATE_DIR/last-successful-deployment"
if [[ -e $manifest || -L $manifest ]]; then
  [[ -f $manifest && ! -L $manifest ]] || \
    die "success manifest path must be a regular, non-symlink file"
fi

actual_root=$(git -C "$REPOSITORY_ROOT" rev-parse --show-toplevel 2>/dev/null) || die "repository root is not a Git working tree"
actual_root=$(CDPATH='' cd -- "$actual_root" && pwd -P)
[[ $actual_root == "$REPOSITORY_ROOT" ]] || die "script path does not match the Git repository root"

git -C "$REPOSITORY_ROOT" diff --quiet --ignore-submodules -- || die "tracked working tree changes must be resolved before deployment"
git -C "$REPOSITORY_ROOT" diff --cached --quiet --ignore-submodules -- || die "staged changes must be resolved before deployment"
[[ -z $(git -C "$REPOSITORY_ROOT" status --porcelain --untracked-files=all) ]] || die "untracked files must be removed before deployment"

if ! git -C "$REPOSITORY_ROOT" cat-file -e "${target_sha}^{commit}" 2>/dev/null; then
  git -C "$REPOSITORY_ROOT" fetch --no-tags --no-write-fetch-head origin "$target_sha"
fi
resolved_sha=$(git -C "$REPOSITORY_ROOT" rev-parse --verify "${target_sha}^{commit}")
[[ $resolved_sha == "$target_sha" ]] || die "resolved commit does not equal the requested SHA"
git -C "$REPOSITORY_ROOT" checkout --detach "$target_sha"
checked_out_sha=$(git -C "$REPOSITORY_ROOT" rev-parse --verify HEAD)
[[ $checked_out_sha == "$target_sha" ]] || die "checkout did not land on the requested SHA"

export DEPLOY_SHA=$target_sha
export POKECRACK_ENV_FILE=$ENV_FILE
release_started_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
compose=(docker compose --project-name pokecrack --env-file "$ENV_FILE" -f "$COMPOSE_FILE")
if [[ $SERVICE_SET == tcgdex-nostr ]]; then
  compose=(docker compose --project-name pokecrack \
    --env-file "$ENV_FILE" --env-file "$NOSTR_ENV_FILE" \
    --profile nostr -f "$COMPOSE_FILE")
  python3 "$NOSTR_PREFLIGHT" \
    --env-file "$NOSTR_ENV_FILE" --require-enabled || \
    die "Nostr hosted contract preflight failed; existing services were left unchanged"
fi

docker compose version >/dev/null
"${compose[@]}" config --quiet
existing_services=$(docker ps --all \
  --filter label=com.docker.compose.project=pokecrack \
  --format '{{.ID}}|{{.Label "com.docker.compose.service"}}') || \
  die "could not enumerate existing Pokecrack project containers"
nostr_container_present=false
while IFS='|' read -r existing_id existing_service extra_field; do
  [[ -n $existing_id ]] || continue
  [[ -n $existing_service && -z $extra_field ]] || \
    die "Pokecrack project container is missing a valid Compose service label: $existing_id"
  case $existing_service in
    collector|scheduler|watchdog) ;;
    nostr-collector)
      if [[ $SERVICE_SET == tcgdex-nostr ]]; then
        :
      elif [[ $RETIRE_NOSTR == true ]]; then
        nostr_container_present=true
      else
        die "Nostr collector exists but is excluded; repeat with explicit --retire-nostr"
      fi
      ;;
    *) die \
      "unapproved service container exists: $existing_service; retire it through a separately approved operation" ;;
  esac
done <<< "$existing_services"
if [[ $nostr_container_present == true ]]; then
  "${compose[@]}" stop nostr-collector || \
    die "could not stop the explicitly retired Nostr collector"
  "${compose[@]}" rm --force --stop nostr-collector || \
    die "could not remove the explicitly retired Nostr collector"
fi
"${compose[@]}" build --pull "${SERVICES[@]}"
"${compose[@]}" config --quiet
"${compose[@]}" up --detach "${SERVICES[@]}"

deadline=$((SECONDS + HEALTH_TIMEOUT))
while true; do
  all_healthy=true
  for service in "${SERVICES[@]}"; do
    container_id=$("${compose[@]}" ps -q "$service")
    if [[ -z $container_id ]]; then
      all_healthy=false
      break
    fi
    state=$(docker inspect --format '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' "$container_id")
    if [[ $state != 'running healthy' ]]; then
      all_healthy=false
      break
    fi
  done
  if [[ $all_healthy == true ]]; then
    break
  fi
  if (( SECONDS >= deadline )); then
    "${compose[@]}" ps >&2 || true
    die "services did not become healthy within ${HEALTH_TIMEOUT} seconds; success marker was not advanced"
  fi
  sleep 1
done

if [[ $VERIFY_RUNTIME == true ]]; then
  [[ -f $RUNTIME_EVIDENCE_VERIFY && ! -L $RUNTIME_EVIDENCE_VERIFY ]] || \
    die "runtime release verifier is missing"
  "$RUNTIME_EVIDENCE_VERIFY" "$target_sha" \
    --env-file "$ENV_FILE" \
    --release-started-at "$release_started_at" \
    --grace-seconds "$RUNTIME_GRACE_SECONDS" || \
    die "runtime release evidence did not pass; success marker was not advanced"
fi

marker=$(mktemp "$STATE_DIR/.last-successful-deployment.XXXXXXXX")
printf 'version=1\nsha=%s\nservice_set=%s\nservices=%s\n' \
  "$target_sha" "$SERVICE_SET" "$SERVICES_CSV" > "$marker"
chmod 0600 "$marker"
if ! pokecrack_atomic_replace "$marker" "$manifest"; then
  rm -f -- "$marker" || true
  die "could not atomically replace the success manifest"
fi

printf 'Deployment healthy at exact SHA %s for service set %s (%s).\n' \
  "$target_sha" "$SERVICE_SET" "$SERVICES_CSV"
