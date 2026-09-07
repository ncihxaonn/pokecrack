#!/usr/bin/env bash
# Run the local Supabase stack without emitting unbounded CLI diagnostics into
# the GitHub Actions log. On failure, expose only a fixed, non-sensitive
# category and regexp-bounded migration metadata through GITHUB_OUTPUT so CI
# can distinguish infrastructure failures from migration failures without
# printing a database URL, statement, or service output.
set -Eeuo pipefail

: "${GITHUB_OUTPUT:?GITHUB_OUTPUT is required}"

log_file="$(mktemp)"
# shellcheck disable=SC2317 # invoked indirectly by the EXIT trap below
cleanup() {
  rm -f "$log_file"
}
trap cleanup EXIT

# This job runs only migration and pgTAP checks. Keep PostgreSQL in the local
# stack, but exclude unrelated API/UI services so their health cannot mask a
# database migration failure. `supabase db reset` and `supabase test db` both
# use the local PostgreSQL port directly.
database_only_excludes='gotrue,realtime,storage-api,imgproxy,kong,mailpit,postgrest,postgres-meta,studio,edge-runtime,logflare,vector,supavisor'
if npx --yes supabase@2.116.0 start --exclude "$database_only_excludes" >"$log_file" 2>&1; then
  printf 'category=started\n' >>"$GITHUB_OUTPUT"
  exit 0
fi

category="unknown"
if grep -Eiq 'applying migration|sqlstate|at statement:' "$log_file"; then
  # Supabase applies local migrations during `start`; this must win over an
  # earlier, transient image-pull warning in the same sealed CLI log.
  category="bootstrap_migration"
elif grep -Eiq 'cannot connect to the docker daemon|docker daemon is not running|is the docker daemon running' "$log_file"; then
  category="docker_unavailable"
elif grep -Eiq 'failed to pull|pull access denied|manifest unknown|unable to find image' "$log_file"; then
  category="image_pull"
elif grep -Eiq 'address already in use|port is already allocated' "$log_file"; then
  category="port_conflict"
elif grep -Eiq 'unhealthy|health check' "$log_file"; then
  category="health_check"
elif grep -Eiq 'context deadline exceeded|timed out|timeout' "$log_file"; then
  category="startup_timeout"
elif grep -Eiq 'npm ERR|failed to install|cannot find module' "$log_file"; then
  category="cli_install"
fi

printf 'category=%s\n' "$category" >>"$GITHUB_OUTPUT"
if [[ "$category" == "bootstrap_migration" ]]; then
  migration_file="$({ grep -Eo '[0-9]{14}_[a-z0-9_]+\.sql' "$log_file" || true; } | tail -n 1)"
  sqlstate="$({ grep -Eo 'SQLSTATE[[:space:]]+[0-9]{5}' "$log_file" || true; } | tail -n 1)"
  bootstrap_reason="unknown"
  sqlstate="${sqlstate##* }"

  # A 20260929 failure is intentionally fail-closed.  Its sealed database
  # output must remain private, but its four fixed guard messages can be
  # safely projected as a finite diagnostic enum for this one migration.
  # Do not add a fallback which relays a raw error, statement, or log line.
  if [[ "$migration_file" == "20260929000000_runtime_release_evidence_bluesky.sql" \
    && "$sqlstate" == "55000" ]]; then
    if grep -Eiq -- '(^|[[:space:]])ERROR:[[:space:]]*Bluesky runtime evidence prerequisites are unavailable([[:space:]]|\(|$)' "$log_file"; then
      bootstrap_reason="runtime_evidence_prerequisites"
    elif grep -Eiq -- '(^|[[:space:]])ERROR:[[:space:]]*runtime release evidence no longer has the reviewed security header([[:space:]]|\(|$)' "$log_file"; then
      bootstrap_reason="runtime_evidence_security_header"
    elif grep -Eiq -- '(^|[[:space:]])ERROR:[[:space:]]*runtime release evidence no longer matches the reviewed Bluesky integration points([[:space:]]|\(|$)' "$log_file"; then
      bootstrap_reason="runtime_evidence_integration_points"
    elif grep -Eiq -- '(^|[[:space:]])ERROR:[[:space:]]*runtime release evidence Bluesky integration did not match exactly([[:space:]]|\(|$)' "$log_file"; then
      bootstrap_reason="runtime_evidence_replacement"
    fi
  fi

  if [[ "$migration_file" =~ ^[0-9]{14}_[a-z0-9_]+\.sql$ ]]; then
    printf 'migration_file=%s\n' "$migration_file" >>"$GITHUB_OUTPUT"
  fi
  if [[ "$sqlstate" =~ ^[0-9]{5}$ ]]; then
    printf 'sqlstate=%s\n' "$sqlstate" >>"$GITHUB_OUTPUT"
  fi
  printf 'bootstrap_reason=%s\n' "$bootstrap_reason" >>"$GITHUB_OUTPUT"
fi
printf 'Safe Supabase local startup category: %s\n' "$category"
exit 1
