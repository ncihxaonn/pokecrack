#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

fail() {
  printf 'worker-service: %s\n' "$*" >&2
  exit 1
}

(($# == 1)) || fail "exactly one role is required"
role=$1

if [[ "${DATA_MODE:-demo}" != "demo" ]]; then
  printf '%s\n' \
    "worker-service: production database-backed worker role wiring is not implemented" >&2
  exit 78
fi
case $role in
  collector|ai-worker|watchdog)
    command=(pokecrack-worker worker --forever)
    interval=${WORKER_POLL_SECONDS:-10}
    ;;
  aggregator)
    command=(pokecrack-worker aggregate all)
    interval=${AGGREGATOR_LOOP_SECONDS:-3600}
    ;;
  scheduler)
    command=(pokecrack-worker scheduler)
    interval=${SCHEDULER_LOOP_SECONDS:-60}
    ;;
  *) fail "unsupported role: $role" ;;
esac
[[ $interval =~ ^[0-9]+([.][0-9]+)?$ ]] || fail "loop interval must be numeric"

child_pid=''
terminate() {
  local status=$?
  trap - EXIT HUP INT TERM
  if [[ -n $child_pid ]]; then
    kill -TERM "$child_pid" 2>/dev/null || true
    wait "$child_pid" 2>/dev/null || true
  fi
  exit "$status"
}
trap terminate EXIT HUP INT TERM

while true; do
  "${command[@]}" &
  child_pid=$!
  if wait "$child_pid"; then
    status=0
  else
    status=$?
  fi
  child_pid=''
  if ((status != 0)); then
    fail "$role command exited unsuccessfully with status $status"
  fi
  sleep "$interval" &
  child_pid=$!
  wait "$child_pid"
  child_pid=''
done
