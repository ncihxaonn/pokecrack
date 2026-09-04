#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
umask 077

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
PORTABILITY_HELPER="$SCRIPT_DIR/../lib/shell_portability.sh"
NOSTR_PREFLIGHT="$SCRIPT_DIR/../lib/verify_nostr_release.py"
BLUESKY_PREFLIGHT="$SCRIPT_DIR/../lib/verify_bluesky_release.py"
RUNTIME_EVIDENCE_VERIFY="$SCRIPT_DIR/verify-runtime-release.sh"
# shellcheck disable=SC1090
source "$PORTABILITY_HELPER"
REPOSITORY_ROOT=$(CDPATH='' cd -- "$SCRIPT_DIR/../.." && pwd -P)
COMPOSE_FILE="$REPOSITORY_ROOT/deploy/compose.prod.yml"
ENV_FILE=${POKECRACK_ENV_FILE:-/etc/pokecrack/production.env}
NOSTR_ENV_FILE=${POKECRACK_NOSTR_ENV_FILE:-}
BLUESKY_ENV_FILE=${POKECRACK_BLUESKY_ENV_FILE:-}
STATE_DIR=${POKECRACK_DEPLOY_STATE_DIR:-/var/lib/pokecrack/deploy}
# Worker health performs a live dependency probe plus heartbeat write.  Its
# bounded Nostr path can use three 90-second Docker checks after startup, so
# the deployment deadline must allow those probes to finish before declaring
# the release failed and withholding the success marker.
HEALTH_TIMEOUT=${DEPLOY_HEALTH_TIMEOUT_SECONDS:-420}
RUNTIME_GRACE_SECONDS=${DEPLOY_RUNTIME_GRACE_SECONDS:-21600}
RUNTIME_EXEC_TIMEOUT_SECONDS=${DEPLOY_RUNTIME_EXEC_TIMEOUT_SECONDS:-60}
DOCKER_METADATA_TIMEOUT_SECONDS=30
DOCKER_SERVICE_TIMEOUT_SECONDS=180
DOCKER_BUILD_TIMEOUT_SECONDS=1200
SERVICE_SET=tcgdex
RETIRE_NOSTR=false
VERIFY_RUNTIME=false
RETIRE_BLUESKY=false
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
        || ( $service_set_line == 'service_set=tcgdex-bluesky' \
          && $services_line == 'services=collector,scheduler,watchdog,bluesky-collector' ) \
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
  --bluesky-env-file PATH     Dedicated Bluesky interpolation/preflight file (tcgdex-bluesky only)
  --state-dir ABSOLUTE_PATH   Success-marker directory (default: /var/lib/pokecrack/deploy)
  --health-timeout SECONDS    Health deadline (default: 420)
  --verify-runtime             Run aggregate runtime evidence after health checks (always required for tcgdex-bluesky)
  --runtime-grace-seconds SEC First-run warming-up window (default: 21600)
  --runtime-exec-timeout-seconds SEC Bound each runtime verifier probe (default: 60)
  --service-set NAME          Exact release service set (tcgdex, tcgdex-nostr, or tcgdex-bluesky)
  --retire-nostr              Explicitly stop/remove only the managed Nostr container
  --retire-bluesky            Explicitly stop/remove only the managed Bluesky container

The full service set is intentionally unavailable: ai-worker and aggregator do
not have safe live handlers in this release.
USAGE
}

require_bluesky_runtime_verifier() {
  local runtime_verifier_line runtime_verifier_help
  local runtime_verifier_supports_bluesky=false

  # This path is checked only after the exact deployment SHA is detached.
  # Reading the caller checkout would let a stale or untracked helper unlock a
  # target that cannot actually prove the isolated lane's runtime evidence.
  [[ -x $RUNTIME_EVIDENCE_VERIFY && ! -L $RUNTIME_EVIDENCE_VERIFY ]] || \
    die "tcgdex-bluesky remains gated until the target SHA provides runtime release evidence"
  while IFS= read -r runtime_verifier_line || [[ -n $runtime_verifier_line ]]; do
    case $runtime_verifier_line in
      RUNTIME_EVIDENCE_SERVICE_SET=tcgdex-bluesky)
        runtime_verifier_supports_bluesky=true
        break
        ;;
    esac
  done < "$RUNTIME_EVIDENCE_VERIFY"
  [[ $runtime_verifier_supports_bluesky == true ]] || \
    die "tcgdex-bluesky remains gated until the target SHA provides runtime verifier service-set support"

  if ! runtime_verifier_help=$("$RUNTIME_EVIDENCE_VERIFY" --help 2>&1); then
    die "tcgdex-bluesky target runtime verifier could not validate its read-only interface"
  fi
  [[ $runtime_verifier_help == *"--service-set NAME"* \
    && $runtime_verifier_help == *"--bluesky-env-file"* \
    && $runtime_verifier_help == *"--require-healthy"* \
    && $runtime_verifier_help == *"tcgdex-bluesky"* ]] || \
    die "tcgdex-bluesky target runtime verifier does not expose the reviewed interface"
}

(($# >= 1)) || { usage; exit 2; }
original_args=("$@")
target_sha=$1
shift
while (($#)); do
  case $1 in
    --env-file) (($# >= 2)) || die "--env-file requires a value"; ENV_FILE=$2; shift 2 ;;
    --nostr-env-file) (($# >= 2)) || die "--nostr-env-file requires a value"; NOSTR_ENV_FILE=$2; shift 2 ;;
    --bluesky-env-file) (($# >= 2)) || die "--bluesky-env-file requires a value"; BLUESKY_ENV_FILE=$2; shift 2 ;;
    --state-dir) (($# >= 2)) || die "--state-dir requires a value"; STATE_DIR=$2; shift 2 ;;
    --health-timeout) (($# >= 2)) || die "--health-timeout requires a value"; HEALTH_TIMEOUT=$2; shift 2 ;;
    --verify-runtime) VERIFY_RUNTIME=true; shift ;;
    --runtime-grace-seconds) (($# >= 2)) || die "--runtime-grace-seconds requires a value"; RUNTIME_GRACE_SECONDS=$2; shift 2 ;;
    --runtime-exec-timeout-seconds) (($# >= 2)) || die "--runtime-exec-timeout-seconds requires a value"; RUNTIME_EXEC_TIMEOUT_SECONDS=$2; shift 2 ;;
    --service-set) (($# >= 2)) || die "--service-set requires a value"; SERVICE_SET=$2; shift 2 ;;
    --retire-nostr) RETIRE_NOSTR=true; shift ;;
    --retire-bluesky) RETIRE_BLUESKY=true; shift ;;
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
[[ $RUNTIME_EXEC_TIMEOUT_SECONDS =~ ^[1-9][0-9]*$ && $RUNTIME_EXEC_TIMEOUT_SECONDS -le 120 ]] || \
  die "runtime exec timeout seconds must be between 1 and 120"
[[ -f $COMPOSE_FILE ]] || die "Compose file is missing: $COMPOSE_FILE"
case $SERVICE_SET in
  tcgdex)
    [[ -z $NOSTR_ENV_FILE ]] || \
      die "the tcgdex service set does not accept a Nostr environment file"
    [[ -z $BLUESKY_ENV_FILE ]] || \
      die "the tcgdex service set does not accept a Bluesky environment file"
    ;;
  tcgdex-nostr)
    [[ $RETIRE_NOSTR == false ]] || \
      die "tcgdex-nostr cannot be combined with --retire-nostr"
    [[ $RETIRE_BLUESKY == false ]] || \
      die "tcgdex-nostr cannot be combined with --retire-bluesky"
    [[ -z $BLUESKY_ENV_FILE ]] || \
      die "the tcgdex-nostr service set does not accept a Bluesky environment file"
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
  tcgdex-bluesky)
    # The isolated social lane may only advance the success marker after its
    # own post-release evidence has advanced. Health and the host attestation
    # prove configuration, not a durable cursor, queue, or worker heartbeat.
    # Do not make this opt-in: callers cannot bypass the verifier by omitting
    # --verify-runtime.
    VERIFY_RUNTIME=true
    [[ $RETIRE_NOSTR == false ]] || \
      die "tcgdex-bluesky cannot be combined with --retire-nostr"
    [[ $RETIRE_BLUESKY == false ]] || \
      die "tcgdex-bluesky cannot be combined with --retire-bluesky"
    [[ -z $NOSTR_ENV_FILE ]] || \
      die "the tcgdex-bluesky service set does not accept a Nostr environment file"
    SERVICES=(collector scheduler watchdog bluesky-collector)
    SERVICES_CSV=collector,scheduler,watchdog,bluesky-collector
    [[ -n $BLUESKY_ENV_FILE && $BLUESKY_ENV_FILE == /* ]] || \
      die "tcgdex-bluesky requires an absolute Bluesky environment file path"
    [[ -f $BLUESKY_ENV_FILE && ! -L $BLUESKY_ENV_FILE ]] || \
      die "Bluesky environment file must be a regular, non-symlink file"
    [[ ! $ENV_FILE -ef $BLUESKY_ENV_FILE ]] || \
      die "Bluesky environment file must be distinct from the production environment file"
    [[ -f $BLUESKY_PREFLIGHT && ! -L $BLUESKY_PREFLIGHT ]] || \
      die "Bluesky release preflight is missing"
    ;;
  full) die "full service set is unavailable because ai-worker and aggregator fail closed in live mode" ;;
  *) die "unsupported service set: $SERVICE_SET (allowed: tcgdex, tcgdex-nostr, tcgdex-bluesky)" ;;
esac

for command in date docker env git install mktemp python3 stat timeout; do
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
if [[ $SERVICE_SET == tcgdex-bluesky ]]; then
  bluesky_env_mode=$(pokecrack_stat_mode "$BLUESKY_ENV_FILE") || \
    die "could not validate Bluesky environment file permissions"
  [[ $bluesky_env_mode == 600 ]] || \
    die "Bluesky environment file must have exact mode 0600"
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

actual_root=$(git -C "$REPOSITORY_ROOT" rev-parse --show-toplevel 2>/dev/null) || die "repository root is not a Git working tree"
actual_root=$(CDPATH='' cd -- "$actual_root" && pwd -P)
[[ $actual_root == "$REPOSITORY_ROOT" ]] || die "script path does not match the Git repository root"

git -C "$REPOSITORY_ROOT" diff --quiet --ignore-submodules -- || die "tracked working tree changes must be resolved before deployment"
git -C "$REPOSITORY_ROOT" diff --cached --quiet --ignore-submodules -- || die "staged changes must be resolved before deployment"
[[ -z $(git -C "$REPOSITORY_ROOT" status --porcelain --untracked-files=all) ]] || die "untracked files must be removed before deployment"

# This shell has already sourced deploy.sh and shell_portability.sh from the
# caller checkout. Capture their tracked content before the target checkout so
# a different target entrypoint is always re-executed from the exact target
# SHA, rather than continuing to run stale code in this process.
caller_entrypoint_blobs=$(git -C "$REPOSITORY_ROOT" hash-object -- \
  "$SCRIPT_DIR/deploy.sh" "$PORTABILITY_HELPER") || \
  die "could not fingerprint the deployment entrypoint"

if ! git -C "$REPOSITORY_ROOT" cat-file -e "${target_sha}^{commit}" 2>/dev/null; then
  git -C "$REPOSITORY_ROOT" fetch --no-tags --no-write-fetch-head origin "$target_sha"
fi
resolved_sha=$(git -C "$REPOSITORY_ROOT" rev-parse --verify "${target_sha}^{commit}")
[[ $resolved_sha == "$target_sha" ]] || die "resolved commit does not equal the requested SHA"
git -C "$REPOSITORY_ROOT" checkout --detach "$target_sha"
checked_out_sha=$(git -C "$REPOSITORY_ROOT" rev-parse --verify HEAD)
[[ $checked_out_sha == "$target_sha" ]] || die "checkout did not land on the requested SHA"
[[ -f $SCRIPT_DIR/deploy.sh && -x $SCRIPT_DIR/deploy.sh && ! -L $SCRIPT_DIR/deploy.sh ]] || \
  die "target deployment script is not a regular executable"
target_entrypoint_blobs=$(git -C "$REPOSITORY_ROOT" hash-object -- \
  "$SCRIPT_DIR/deploy.sh" "$PORTABILITY_HELPER") || \
  die "could not fingerprint the target deployment entrypoint"
if [[ $caller_entrypoint_blobs != "$target_entrypoint_blobs" ]]; then
  # Preserve the original options, including the exact SHA, and restart in the
  # target checkout. On the second pass the entrypoint fingerprints match, so
  # this cannot loop and the code controlling replacement is target-bound.
  exec "$SCRIPT_DIR/deploy.sh" "${original_args[@]}"
fi
if [[ $SERVICE_SET == tcgdex-bluesky ]]; then
  require_bluesky_runtime_verifier
fi

[[ ! -L $STATE_DIR ]] || die "state directory must not be a symbolic link"
install -d -m 0700 "$STATE_DIR"
[[ -d $STATE_DIR && ! -L $STATE_DIR ]] || die "state directory is invalid"
manifest="$STATE_DIR/last-successful-deployment"
if [[ -e $manifest || -L $manifest ]]; then
  [[ -f $manifest && ! -L $manifest ]] || \
    die "success manifest path must be a regular, non-symlink file"
fi

export DEPLOY_SHA=$target_sha
export POKECRACK_ENV_FILE=$ENV_FILE
# Compose gives inherited shell variables precedence over --env-file. The
# reviewed owner-only files are authoritative for every database credential;
# never let an SSH profile or operator shell silently substitute another DSN.
unset SUPABASE_DB_URL NOSTR_SUPABASE_DB_URL BLUESKY_SUPABASE_DB_URL \
  RUNTIME_RELEASE_EVIDENCE_DB_URL
release_started_at=$(date -u '+%Y-%m-%dT%H:%M:%SZ')
compose=(docker compose --project-name pokecrack --env-file "$ENV_FILE" -f "$COMPOSE_FILE")
if [[ $SERVICE_SET == tcgdex-nostr ]]; then
  compose=(docker compose --project-name pokecrack \
    --env-file "$ENV_FILE" --env-file "$NOSTR_ENV_FILE" \
    --profile nostr -f "$COMPOSE_FILE")
  python3 "$NOSTR_PREFLIGHT" \
    --env-file "$NOSTR_ENV_FILE" --require-enabled || \
    die "Nostr hosted contract preflight failed; existing services were left unchanged"
elif [[ $SERVICE_SET == tcgdex-bluesky ]]; then
  compose=(env "POKECRACK_BLUESKY_ENV_FILE=$BLUESKY_ENV_FILE" docker compose --project-name pokecrack \
    --env-file "$ENV_FILE" --env-file "$BLUESKY_ENV_FILE" \
    --profile bluesky -f "$COMPOSE_FILE")
  python3 "$BLUESKY_PREFLIGHT" \
    --env-file "$BLUESKY_ENV_FILE" --require-enabled || \
    die "Bluesky hosted contract preflight failed; existing services were left unchanged"
fi

timeout --foreground --kill-after=5 "$DOCKER_METADATA_TIMEOUT_SECONDS" \
  docker compose version >/dev/null || die "Docker Compose is unavailable"
timeout --foreground --kill-after=5 "$DOCKER_METADATA_TIMEOUT_SECONDS" \
  "${compose[@]}" config --quiet || die "Compose configuration is invalid"
existing_services=$(timeout --foreground --kill-after=5 \
  "$DOCKER_METADATA_TIMEOUT_SECONDS" docker ps --all \
  --filter label=com.docker.compose.project=pokecrack \
  --format '{{.ID}}|{{.Label "com.docker.compose.service"}}|{{.State}}') || \
  die "could not enumerate existing Pokecrack project containers"
nostr_container_present=false
bluesky_container_present=false
while IFS='|' read -r existing_id existing_service existing_state extra_field; do
  [[ -n $existing_id ]] || continue
  [[ -n $existing_service && $existing_state =~ ^[a-z]+$ && -z $extra_field ]] || \
    die "Pokecrack project container is missing a valid Compose service label or state: $existing_id"
  case $existing_service in
    collector|scheduler|watchdog) ;;
    nostr-collector)
      if [[ $SERVICE_SET == tcgdex-nostr ]]; then
        :
      elif [[ $RETIRE_NOSTR == true ]]; then
        nostr_container_present=true
      elif [[ $existing_state == exited ]]; then
        printf '%s\n' 'deploy: preserving stopped excluded Nostr collector' >&2
      else
        die "Nostr collector exists in state $existing_state but is excluded; repeat with explicit --retire-nostr"
      fi
      ;;
    bluesky-collector)
      if [[ $SERVICE_SET == tcgdex-bluesky ]]; then
        :
      elif [[ $RETIRE_BLUESKY == true ]]; then
        bluesky_container_present=true
      elif [[ $existing_state == exited ]]; then
        printf '%s\n' 'deploy: preserving stopped excluded Bluesky collector' >&2
      else
        die "Bluesky collector exists in state $existing_state but is excluded; repeat with explicit --retire-bluesky"
      fi
      ;;
    *) die \
      "unapproved service container exists: $existing_service; retire it through a separately approved operation" ;;
  esac
done <<< "$existing_services"
if [[ $nostr_container_present == true ]]; then
  timeout --foreground --kill-after=5 "$DOCKER_SERVICE_TIMEOUT_SECONDS" \
    "${compose[@]}" stop nostr-collector || \
    die "could not stop the explicitly retired Nostr collector"
  timeout --foreground --kill-after=5 "$DOCKER_SERVICE_TIMEOUT_SECONDS" \
    "${compose[@]}" rm --force --stop nostr-collector || \
    die "could not remove the explicitly retired Nostr collector"
fi
if [[ $bluesky_container_present == true ]]; then
  timeout --foreground --kill-after=5 "$DOCKER_SERVICE_TIMEOUT_SECONDS" \
    "${compose[@]}" stop bluesky-collector || \
    die "could not stop the explicitly retired Bluesky collector"
  timeout --foreground --kill-after=5 "$DOCKER_SERVICE_TIMEOUT_SECONDS" \
    "${compose[@]}" rm --force --stop bluesky-collector || \
    die "could not remove the explicitly retired Bluesky collector"
fi
timeout --foreground --kill-after=5 "$DOCKER_BUILD_TIMEOUT_SECONDS" \
  "${compose[@]}" build --pull "${SERVICES[@]}" || die "worker image build failed or timed out"
timeout --foreground --kill-after=5 "$DOCKER_METADATA_TIMEOUT_SECONDS" \
  "${compose[@]}" config --quiet || die "post-build Compose configuration is invalid"
timeout --foreground --kill-after=5 "$DOCKER_SERVICE_TIMEOUT_SECONDS" \
  "${compose[@]}" up --detach "${SERVICES[@]}" || die "worker service startup failed or timed out"

print_bounded_health_diagnostics() {
  local service container_id state diagnostic
  printf '%s\n' 'deploy: bounded worker health diagnostics begin' >&2
  for service in "${SERVICES[@]}"; do
    container_id=$(timeout --foreground --kill-after=2 10 \
      "${compose[@]}" ps -q "$service" 2>/dev/null || true)
    if [[ -z $container_id ]]; then
      printf 'service=%s container=missing\n' "$service" >&2
      continue
    fi
    state=$(timeout --foreground --kill-after=2 10 docker inspect --format \
      'status={{.State.Status}} health={{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}} restart_count={{.RestartCount}} exit_code={{.State.ExitCode}} oom_killed={{.State.OOMKilled}}' \
      "$container_id" 2>/dev/null || true)
    if [[ $state =~ ^status=(created|running|paused|restarting|removing|exited|dead)\ health=(starting|healthy|unhealthy|none)\ restart_count=[0-9]+\ exit_code=[0-9]+\ oom_killed=(true|false)$ ]]; then
      printf 'service=%s %s\n' "$service" "$state" >&2
    else
      printf 'service=%s state=inspect_unavailable\n' "$service" >&2
    fi
    diagnostic=$(timeout --foreground --kill-after=2 35 \
      "${compose[@]}" exec -T "$service" \
      python -m pokecrack_worker.safe_health_diagnostics 2>/dev/null || true)
    if (( ${#diagnostic} <= 256 )) \
      && [[ $diagnostic =~ ^status=(failed|ok)\ stage=(configuration|dns|tcp|database|dependencies|heartbeat|runtime)\ reason=(invalid_dsn|invalid_runtime|validation_failed|unavailable|unreachable|authentication_failed|capacity_unavailable|authorization_failed|tls_failed|connection_unavailable|query_failed|contract_unavailable|ready|probe_failed|probe_timed_out)(\ worker_role=(collector|scheduler|watchdog))?$ ]]
    then
      printf 'service=%s diagnostic=%s\n' "$service" "$diagnostic" >&2
    else
      printf 'service=%s diagnostic=unavailable\n' "$service" >&2
    fi
  done
  printf '%s\n' 'deploy: bounded worker health diagnostics end' >&2
}

deadline=$((SECONDS + HEALTH_TIMEOUT))
while true; do
  all_healthy=true
  for service in "${SERVICES[@]}"; do
    container_id=$(timeout --foreground --kill-after=2 10 \
      "${compose[@]}" ps -q "$service" 2>/dev/null || true)
    if [[ -z $container_id ]]; then
      all_healthy=false
      break
    fi
    state=$(timeout --foreground --kill-after=2 10 docker inspect --format \
      '{{.State.Status}} {{if .State.Health}}{{.State.Health.Status}}{{else}}none{{end}}' \
      "$container_id" 2>/dev/null || true)
    if [[ $state != 'running healthy' ]]; then
      all_healthy=false
      break
    fi
  done
  if [[ $all_healthy == true ]]; then
    break
  fi
  if (( SECONDS >= deadline )); then
    print_bounded_health_diagnostics
    die "services did not become healthy within ${HEALTH_TIMEOUT} seconds; success marker was not advanced"
  fi
  sleep 1
done

if [[ $VERIFY_RUNTIME == true ]]; then
  [[ -f $RUNTIME_EVIDENCE_VERIFY && ! -L $RUNTIME_EVIDENCE_VERIFY ]] || \
    die "runtime release verifier is missing"
  runtime_verify_args=(
    "$target_sha"
    --env-file "$ENV_FILE"
    --release-started-at "$release_started_at"
    --grace-seconds "$RUNTIME_GRACE_SECONDS"
    --service-set "$SERVICE_SET"
    --exec-timeout-seconds "$RUNTIME_EXEC_TIMEOUT_SECONDS"
  )
  if [[ -n $NOSTR_ENV_FILE ]]; then
    runtime_verify_args+=(--nostr-env-file "$NOSTR_ENV_FILE")
  fi
  if [[ -n $BLUESKY_ENV_FILE ]]; then
    runtime_verify_args+=(--bluesky-env-file "$BLUESKY_ENV_FILE" --require-healthy)
  fi
  set +e
  "$RUNTIME_EVIDENCE_VERIFY" "${runtime_verify_args[@]}"
  runtime_verify_status=$?
  set -e
  case $runtime_verify_status in
    0) ;;
    1) die "runtime release evidence failed; success marker was not advanced" ;;
    2)
      printf '%s\n' \
        "deploy: runtime release evidence was inconclusive; success marker was not advanced" >&2
      rollback_marker
      exit 2
      ;;
    *) die "runtime release evidence could not run; success marker was not advanced" ;;
  esac
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
