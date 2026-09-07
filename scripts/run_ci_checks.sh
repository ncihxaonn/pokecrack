#!/usr/bin/env bash
# PokeCrack CI runner v1.
#
# This is the canonical implementation of the repository's non-production
# verification stages. GitHub Actions and an independently managed, disposable
# Docker-capable Linux runner call the same stage functions below. The runner
# never reads production credentials, never mutates a hosted database, and
# fails closed on a missing tool, dirty checkout, SHA mismatch, or failed stage.
set -Eeuo pipefail
IFS=$'\n\t'
umask 077

RUNNER_VERSION=1
SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
REPO_ROOT=$(CDPATH='' cd -- "$SCRIPT_DIR/.." && pwd -P)
EXPECTED_SHA=''
EVIDENCE_DIR=''
EVIDENCE_REAL=''
STAGE_RECORDS=''
TOOL_RECORDS=''

POSTGRES_META_SOURCE='ghcr.io/supabase/postgres-meta@sha256:cef71ba901751dcc242cc685cf13786935ea8926820fb342f23bb0fbef77de5a'
POSTGRES_META_TARGET='public.ecr.aws/supabase/postgres-meta:v0.98.0'
POSTGRES_META_DIGEST='sha256:cef71ba901751dcc242cc685cf13786935ea8926820fb342f23bb0fbef77de5a'
GITLEAKS_IMAGE='ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f'
GITLEAKS_DIGEST='sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f'

usage() {
  cat <<'USAGE'
Usage:
  scripts/run_ci_checks.sh [all|stage] --expected-sha SHA [--evidence-dir DIR]

Stages:
  all                 Run every verification stage in order (default).
  web                 pnpm install, lint, typecheck, test, and production build.
  worker              Locked uv environment, dependency audit, lint, types, tests.
  auth-browser        Locked auth-browser checks and production image build.
  database            Local Supabase migration reset, pgTAP, and type-drift checks.
  container-worker    Build the production worker image.
  repository-policy   Shellcheck, repository tests, policy verification, Gitleaks.
  deployment-contracts Compose render and deployment/backup contract tests.

The checkout must be clean, use the PokeCrack origin, and be exactly SHA.
Evidence is written to a new owner-only directory outside the checkout.
USAGE
}

die() {
  printf 'PokeCrack CI runner: %s\n' "$*" >&2
  exit 1
}

require_command() {
  local command_name=$1
  command -v "$command_name" >/dev/null 2>&1 || die "required command not found: $command_name"
}

utc_now() {
  date -u '+%Y-%m-%dT%H:%M:%SZ'
}

record_tool() {
  local name=$1
  local value='unavailable'
  case "$name" in
    bash)
      value=$(bash --version 2>&1 | sed -n '1p') || value=unavailable
      ;;
    git)
      value=$(git --version 2>&1 | sed -n '1p') || value=unavailable
      ;;
    python3)
      value=$(python3 --version 2>&1 | sed -n '1p') || value=unavailable
      ;;
    node)
      value=$(node --version 2>&1 | sed -n '1p') || value=unavailable
      ;;
    pnpm)
      value=$("$SCRIPT_DIR/run-pnpm.sh" --version 2>&1 | sed -n '1p') || value=unavailable
      ;;
    npx)
      value=$(npx --version 2>&1 | sed -n '1p') || value=unavailable
      ;;
    uv)
      value=$(uv --version 2>&1 | sed -n '1p') || value=unavailable
      ;;
    docker)
      value=$(docker --version 2>&1 | sed -n '1p') || value=unavailable
      ;;
    shellcheck)
      value=$(shellcheck --version 2>&1 | sed -n '2p') || value=unavailable
      ;;
    gitleaks)
      value="docker-image:${GITLEAKS_IMAGE}"
      ;;
    *)
      value=unavailable
      ;;
  esac
  value=${value//$'\t'/ }
  value=${value//$'\n'/ }
  printf '%s\t%s\n' "$name" "$value" >>"$TOOL_RECORDS"
}

validate_root() {
  require_command git
  require_command date
  require_command python3
  [[ -e "$REPO_ROOT/.git" && ! -L "$REPO_ROOT/.git" ]] \
    || die "repository root does not contain a real .git entry: $REPO_ROOT"
  local origin_url actual_sha status_output
  origin_url=$(git -C "$REPO_ROOT" remote get-url origin) || die "could not read repository origin"
  [[ "$origin_url" =~ ^https://github\.com/ncihxaonn/pokecrack(\.git)?$ ]] || die "unexpected repository origin"
  [[ "$EXPECTED_SHA" =~ ^[0-9a-f]{40}$ ]] || die "--expected-sha must be a 40-character lowercase commit SHA"
  actual_sha=$(git -C "$REPO_ROOT" rev-parse --verify HEAD^{commit}) || die "could not resolve HEAD"
  [[ "$actual_sha" == "$EXPECTED_SHA" ]] || die "checkout SHA does not match --expected-sha"
  git -C "$REPO_ROOT" diff --quiet --ignore-submodules -- || die "checkout has unstaged changes"
  git -C "$REPO_ROOT" diff --cached --quiet --ignore-submodules -- || die "checkout has staged changes"
  status_output=$(git -C "$REPO_ROOT" status --porcelain --untracked-files=all)
  [[ -z "$status_output" ]] || die "checkout is not clean"
  [[ "$EVIDENCE_REAL" != "$REPO_ROOT" && "$EVIDENCE_REAL" != "$REPO_ROOT"/* ]] \
    || die "evidence directory must be outside the checkout"
}

validate_evidence_location() {
  python3 - "$EVIDENCE_DIR" "$REPO_ROOT" <<'PY'
from pathlib import Path
import sys

requested = Path(sys.argv[1])
repository = Path(sys.argv[2]).resolve()
if not requested.is_absolute():
    raise SystemExit("--evidence-dir must be an absolute path")
if ".." in requested.parts:
    raise SystemExit("--evidence-dir must not contain ..")

missing = []
ancestor = requested
while not ancestor.exists():
    if ancestor == ancestor.parent:
        raise SystemExit("--evidence-dir has no existing parent")
    missing.append(ancestor.name)
    ancestor = ancestor.parent

candidate = ancestor.resolve()
for name in reversed(missing):
    candidate /= name

if candidate == repository or repository in candidate.parents:
    raise SystemExit("evidence directory must be outside the checkout")
PY
}

prepare_evidence() {
  if [[ -z "$EVIDENCE_DIR" ]]; then
    EVIDENCE_DIR=$(mktemp -d "${TMPDIR:-/tmp}/pokecrack-ci-evidence.XXXXXXXX")
  else
    validate_evidence_location || die "invalid evidence directory location"
    [[ ! -e "$EVIDENCE_DIR" && ! -L "$EVIDENCE_DIR" ]] || die "--evidence-dir must name a new path"
    mkdir -m 0700 -- "$EVIDENCE_DIR"
  fi
  [[ -d "$EVIDENCE_DIR" && ! -L "$EVIDENCE_DIR" ]] || die "evidence directory is not a real directory"
  EVIDENCE_REAL=$(CDPATH='' cd -- "$EVIDENCE_DIR" && pwd -P) || die "could not resolve evidence directory"
  [[ "$EVIDENCE_REAL" != "$REPO_ROOT" && "$EVIDENCE_REAL" != "$REPO_ROOT"/* ]] \
    || die "evidence directory must be outside the checkout"
  EVIDENCE_DIR=$EVIDENCE_REAL
  chmod 0700 "$EVIDENCE_DIR"
  STAGE_RECORDS="$EVIDENCE_DIR/stages.tsv"
  TOOL_RECORDS="$EVIDENCE_DIR/tools.tsv"
  : >"$STAGE_RECORDS"
  : >"$TOOL_RECORDS"
  chmod 0600 "$STAGE_RECORDS" "$TOOL_RECORDS"
}

write_manifest() {
  local exit_code=$1
  python3 - "$EVIDENCE_DIR/manifest.json" "$REPO_ROOT" "$EXPECTED_SHA" "$RUNNER_VERSION" "$exit_code" "$STAGE_RECORDS" "$TOOL_RECORDS" <<'PY'
import json
import platform
import subprocess
import sys
from pathlib import Path

manifest_path = Path(sys.argv[1])
repo_root = Path(sys.argv[2])
expected_sha = sys.argv[3]
runner_version = int(sys.argv[4])
exit_code = int(sys.argv[5])
stage_path = Path(sys.argv[6])
tool_path = Path(sys.argv[7])

def read_tsv(path: Path, expected_fields: int):
    records = []
    for line in path.read_text(encoding="utf-8").splitlines():
        fields = line.split("\t")
        if len(fields) == expected_fields:
            records.append(fields)
    return records

try:
    actual_sha = subprocess.check_output(
        ["git", "-C", str(repo_root), "rev-parse", "--verify", "HEAD^{commit}"],
        text=True,
        stderr=subprocess.DEVNULL,
    ).strip()
except (OSError, subprocess.CalledProcessError):
    actual_sha = None

manifest = {
    "schema_version": 1,
    "runner_version": runner_version,
    "status": "passed" if exit_code == 0 else "failed",
    "exit_code": exit_code,
    "expected_sha": expected_sha,
    "actual_sha": actual_sha,
    "repository": "ncihxaonn/pokecrack",
    "platform": {
        "system": platform.system(),
        "release": platform.release(),
        "machine": platform.machine(),
        "python": platform.python_version(),
    },
    "stages": [
        {
            "name": name,
            "exit_code": int(stage_exit),
            "started_at": started,
            "completed_at": completed,
            "log": log,
        }
        for name, stage_exit, started, completed, log in read_tsv(stage_path, 5)
    ],
    "tools": {
        name: version
        for name, version in read_tsv(tool_path, 2)
    },
}
manifest_path.write_text(
    json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
    encoding="utf-8",
)
PY
  chmod 0600 "$EVIDENCE_DIR/manifest.json"
}

finish() {
  local exit_code=$?
  trap - EXIT HUP INT TERM
  if ! write_manifest "$exit_code"; then
    printf 'PokeCrack CI runner: could not write evidence manifest\n' >&2
    [[ "$exit_code" -eq 0 ]] && exit_code=1
  fi
  if [[ "$exit_code" -eq 0 ]]; then
    printf 'PokeCrack CI runner v%s passed for %s\n' "$RUNNER_VERSION" "$EXPECTED_SHA"
  else
    printf 'PokeCrack CI runner v%s failed for %s (exit %s)\n' "$RUNNER_VERSION" "$EXPECTED_SHA" "$exit_code" >&2
  fi
  printf 'Evidence directory: %s\n' "$EVIDENCE_DIR"
  exit "$exit_code"
}

run_stage() {
  local stage_name=$1
  shift
  local log_file="$EVIDENCE_DIR/${stage_name}.log"
  local started completed stage_exit tee_exit
  started=$(utc_now)
  printf '\n== %s ==\n' "$stage_name"
  set +e
  (
    set -Eeuo pipefail
    "$@"
  ) 2>&1 | tee "$log_file"
  local -a pipeline_status=("${PIPESTATUS[@]}")
  set -e
  stage_exit=${pipeline_status[0]}
  tee_exit=${pipeline_status[1]}
  completed=$(utc_now)
  chmod 0600 "$log_file"
  if [[ "$tee_exit" -ne 0 && "$stage_exit" -eq 0 ]]; then
    stage_exit=$tee_exit
  fi
  printf '%s\t%s\t%s\t%s\t%s\n' \
    "$stage_name" "$stage_exit" "$started" "$completed" "$(basename "$log_file")" \
    >>"$STAGE_RECORDS"
  if [[ "$stage_exit" -ne 0 ]]; then
    printf 'Stage %s failed with exit %s\n' "$stage_name" "$stage_exit" >&2
    return "$stage_exit"
  fi
}

stage_web() {
  require_command node
  require_command python3
  "$SCRIPT_DIR/run-pnpm.sh" --version >/dev/null
  cd "$REPO_ROOT"
  "$SCRIPT_DIR/run-pnpm.sh" install --frozen-lockfile
  "$SCRIPT_DIR/run-pnpm.sh" lint
  "$SCRIPT_DIR/run-pnpm.sh" typecheck
  "$SCRIPT_DIR/run-pnpm.sh" test
  "$SCRIPT_DIR/run-pnpm.sh" build
}

stage_worker() {
  require_command uv
  require_command python3
  cd "$REPO_ROOT/services/worker"
  uv sync --frozen --extra dev --extra scrapling
  uv export --quiet --frozen --all-extras --format requirements-txt --no-emit-project -o "$EVIDENCE_DIR/worker-audit.txt"
  uvx --from pip-audit==2.10.1 pip-audit -r "$EVIDENCE_DIR/worker-audit.txt" --disable-pip
  uv run ruff check pokecrack_worker tests
  uv run ruff format --check pokecrack_worker tests
  uv run mypy pokecrack_worker
  uv run pytest -q
}

stage_auth_browser() {
  require_command uv
  require_command python3
  require_command docker
  cd "$REPO_ROOT/services/auth-browser"
  uv sync --frozen --extra dev
  uv export --quiet --frozen --all-extras --format requirements-txt --no-emit-project -o "$EVIDENCE_DIR/auth-browser-audit.txt"
  uvx --from pip-audit==2.10.1 pip-audit -r "$EVIDENCE_DIR/auth-browser-audit.txt" --disable-pip
  uv run ruff check src tests
  uv run ruff format --check src tests
  uv run mypy src/pokecrack_browser
  uv run pytest -q
  cd "$REPO_ROOT"
  DEPLOY_SHA="$EXPECTED_SHA" docker build --file deploy/Dockerfile.auth-browser --tag "pokecrack-auth-browser:$EXPECTED_SHA" .
}

read_start_output() {
  local key=$1
  local path=$2
  awk -F= -v wanted="$key" '$1 == wanted { value = substr($0, index($0, "=") + 1) } END { print value }' "$path"
}

diagnose_supabase_start() {
  local output_file=$1
  local category migration_file sqlstate bootstrap_reason
  category=$(read_start_output category "$output_file")
  case "$category" in
    bootstrap_migration)
      migration_file=$(read_start_output migration_file "$output_file")
      sqlstate=$(read_start_output sqlstate "$output_file")
      bootstrap_reason=$(read_start_output bootstrap_reason "$output_file")
      [[ "$migration_file" =~ ^[0-9]{14}_[a-z0-9_]+\.sql$ ]] || migration_file=unknown
      [[ "$sqlstate" =~ ^[0-9]{5}$ ]] || sqlstate=unknown
      case "$bootstrap_reason" in
        runtime_evidence_prerequisites|runtime_evidence_security_header|runtime_evidence_integration_points|runtime_evidence_replacement|unknown) ;;
        *) bootstrap_reason=unknown ;;
      esac
      printf 'Safe Supabase bootstrap migration metadata: migration=%s SQLSTATE=%s reason=%s\n' \
        "$migration_file" "$sqlstate" "$bootstrap_reason"
      ;;
    docker_unavailable|image_pull|port_conflict|health_check|startup_timeout|cli_install|unknown)
      printf 'Safe Supabase local startup category: %s\n' "$category"
      ;;
    *)
      printf 'Safe Supabase local startup category: unknown\n'
      ;;
  esac
  return 1
}

stage_database() {
  require_command docker
  require_command npx
  require_command python3
  require_command diff
  cd "$REPO_ROOT"

  local postgres_meta_pull_log="$EVIDENCE_DIR/postgres-meta-pull.log"
  docker pull "$POSTGRES_META_SOURCE" | tee "$postgres_meta_pull_log"
  chmod 0600 "$postgres_meta_pull_log"
  grep -Fqx "Digest: $POSTGRES_META_DIGEST" "$postgres_meta_pull_log" \
    || die "PostgreSQL-meta image digest was not confirmed"
  docker tag "$POSTGRES_META_SOURCE" "$POSTGRES_META_TARGET"
  printf '%s\n' "$POSTGRES_META_SOURCE" >"$EVIDENCE_DIR/postgres-meta-image.txt"
  chmod 0600 "$EVIDENCE_DIR/postgres-meta-image.txt"

  local start_output=/tmp/pokecrack-supabase-start-output.XXXXXXXX
  start_output=$(mktemp "$start_output")
  chmod 0600 "$start_output"
  local database_stack_started=false
  cleanup_database() {
    local status=$?
    trap - EXIT HUP INT TERM
    if [[ "$database_stack_started" == true ]]; then
      if ! npx --yes supabase@2.116.0 stop --no-backup; then
        status=1
      fi
    fi
    rm -f -- "$start_output"
    exit "$status"
  }
  trap cleanup_database EXIT HUP INT TERM

  database_stack_started=true
  if ! GITHUB_OUTPUT="$start_output" bash "$SCRIPT_DIR/start-local-supabase-ci.sh"; then
    diagnose_supabase_start "$start_output"
    return 1
  fi
  npx --yes supabase@2.116.0 db reset

  local -a regular_tests=()
  local test_file
  for test_file in "$REPO_ROOT"/supabase/tests/*.sql; do
    case "$test_file" in
      "$REPO_ROOT/supabase/tests/003_public_security.sql"|"$REPO_ROOT/supabase/tests/009_admin_session_fence.sql") ;;
      *) regular_tests+=("$test_file") ;;
    esac
  done
  npx --yes supabase@2.116.0 test db "${regular_tests[@]}"
  npx --yes supabase@2.116.0 test db \
    --db-url postgresql://supabase_admin:postgres@127.0.0.1:54322/postgres \
    "$REPO_ROOT/supabase/tests/003_public_security.sql" \
    "$REPO_ROOT/supabase/tests/009_admin_session_fence.sql"

  mkdir -m 0700 -- "$EVIDENCE_DIR/generated-types"
  npx --yes supabase@2.116.0 gen types typescript --local \
    --schema public,catalog,ingest,analytics \
    >"$EVIDENCE_DIR/generated-types/database.generated.ts"
  test -s "$EVIDENCE_DIR/generated-types/database.generated.ts"
  python3 -c 'from pathlib import Path; path = Path(__import__("sys").argv[1]); data = path.read_bytes(); path.write_bytes(data.rstrip(b"\n") + b"\n")' \
    "$EVIDENCE_DIR/generated-types/database.generated.ts"
  diff --unified "$REPO_ROOT/supabase/types/database.ts" \
    "$EVIDENCE_DIR/generated-types/database.generated.ts"
}

run_gitleaks() {
  require_command docker
  [[ "$GITLEAKS_IMAGE" =~ ^[A-Za-z0-9./:@_-]+$ ]] || die "GITLEAKS_IMAGE contains unsupported characters"
  local gitleaks_pull_log="$EVIDENCE_DIR/gitleaks-pull.log"
  docker pull "$GITLEAKS_IMAGE" | tee "$gitleaks_pull_log"
  chmod 0600 "$gitleaks_pull_log"
  grep -Fqx "Digest: $GITLEAKS_DIGEST" "$gitleaks_pull_log" \
    || die "Gitleaks image digest was not confirmed"
  printf '%s\n' "$GITLEAKS_IMAGE" >"$EVIDENCE_DIR/gitleaks-image.txt"
  chmod 0600 "$EVIDENCE_DIR/gitleaks-image.txt"
  docker run --rm \
    --network none \
    --read-only \
    --tmpfs /tmp:rw,noexec,nosuid,size=64m \
    --cap-drop=ALL \
    --security-opt=no-new-privileges \
    --user "$(id -u):$(id -g)" \
    --volume "$REPO_ROOT:/repo:ro" \
    "$GITLEAKS_IMAGE" \
    detect --source=/repo --redact --no-banner
}

stage_container_worker() {
  require_command docker
  cd "$REPO_ROOT"
  DEPLOY_SHA="$EXPECTED_SHA" docker build --file deploy/Dockerfile.worker --tag "pokecrack-worker:$EXPECTED_SHA" .
}

stage_repository_policy() {
  require_command shellcheck
  require_command python3
  cd "$REPO_ROOT"
  [[ "$(git rev-parse --is-shallow-repository)" == false ]] \
    || die "repository-policy requires a full Git history for the secret scan"
  shellcheck scripts/*.sh deploy/scripts/*.sh deploy/*.sh deploy/lib/run_postgres_client_container.sh services/auth-browser/container/*.sh
  python3 scripts/verify_repository.py .
  python3 -m unittest discover -s scripts/tests -v
  run_gitleaks
}

stage_deployment_contracts() {
  require_command docker
  require_command python3
  cd "$REPO_ROOT"
  python3 -m unittest discover -s deploy/tests -v
  DEPLOY_SHA="$EXPECTED_SHA" \
    CHROMIUM_PROFILE_ROOT_HOST="$EVIDENCE_DIR/chromium-profiles" \
    BACKUP_DIR="$EVIDENCE_DIR/backups" \
    OPENCLI_EXTENSION_DIR="$EVIDENCE_DIR/opencli-extension" \
    NOVNC_PASSWORD_FILE="$EVIDENCE_DIR/novnc-password" \
    docker compose -f deploy/compose.prod.yml config --quiet
}

parse_args() {
  local stage=all
  if (($# > 0)) && [[ "$1" != -* ]]; then
    stage=$1
    shift
  fi
  while (($# > 0)); do
    case "$1" in
      --expected-sha)
        (($# >= 2)) || die "--expected-sha requires a value"
        EXPECTED_SHA=$2
        shift 2
        ;;
      --evidence-dir)
        (($# >= 2)) || die "--evidence-dir requires a value"
        EVIDENCE_DIR=$2
        shift 2
        ;;
      --help|-h)
        usage
        exit 0
        ;;
      --list)
        printf '%s\n' web worker auth-browser database container-worker repository-policy deployment-contracts
        exit 0
        ;;
      *)
        die "unknown argument: $1"
        ;;
    esac
  done
  [[ "$stage" =~ ^(all|web|worker|auth-browser|database|container-worker|repository-policy|deployment-contracts)$ ]] \
    || die "unknown stage: $stage"
  if [[ -z "$EXPECTED_SHA" ]]; then
    die "--expected-sha is required"
  fi
  RUN_STAGE=$stage
}

RUN_STAGE=all
parse_args "$@"
prepare_evidence
trap finish EXIT
trap 'exit 129' HUP
trap 'exit 130' INT
trap 'exit 143' TERM
record_tool bash
record_tool git
record_tool python3
validate_root
record_tool node
record_tool pnpm
record_tool npx
record_tool uv
record_tool docker
record_tool shellcheck
record_tool gitleaks

case "$RUN_STAGE" in
  all)
    STAGES=(web worker auth-browser database container-worker repository-policy deployment-contracts)
    ;;
  *)
    STAGES=("$RUN_STAGE")
    ;;
esac

for stage in "${STAGES[@]}"; do
  case "$stage" in
    web) stage_function=stage_web ;;
    worker) stage_function=stage_worker ;;
    auth-browser) stage_function=stage_auth_browser ;;
    database) stage_function=stage_database ;;
    container-worker) stage_function=stage_container_worker ;;
    repository-policy) stage_function=stage_repository_policy ;;
    deployment-contracts) stage_function=stage_deployment_contracts ;;
    *) die "internal stage mapping error" ;;
  esac
  # Keep the function call out of an `if`/`||` conditional context. Bash
  # disables errexit inside functions called that way, which could otherwise
  # let a failed command be masked by a later successful command. The stage
  # itself is run in a strict subshell above; capture its status explicitly.
  set +e
  run_stage "$stage" "$stage_function"
  stage_status=$?
  set -e
  if ((stage_status != 0)); then
    exit "$stage_status"
  fi
done

validate_root
