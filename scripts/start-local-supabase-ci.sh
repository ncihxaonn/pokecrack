#!/usr/bin/env bash
# Run the local Supabase stack without emitting unbounded CLI diagnostics into
# the GitHub Actions log. On failure, expose only a fixed, non-sensitive
# category through GITHUB_OUTPUT so CI can distinguish infrastructure failures
# from migration failures without printing a database URL or service output.
set -Eeuo pipefail

: "${GITHUB_OUTPUT:?GITHUB_OUTPUT is required}"

log_file="$(mktemp)"
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
printf 'Safe Supabase local startup category: %s\n' "$category"
exit 1
