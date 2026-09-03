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

if npx --yes supabase@2.116.0 start >"$log_file" 2>&1; then
  printf 'category=started\n' >>"$GITHUB_OUTPUT"
  exit 0
fi

category="unknown"
if grep -Eiq 'cannot connect to the docker daemon|docker daemon is not running|is the docker daemon running' "$log_file"; then
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
