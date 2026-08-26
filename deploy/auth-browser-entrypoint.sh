#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
umask 077

fail() {
  printf 'auth-browser: %s\n' "$*" >&2
  exit 1
}

PORTABILITY_HELPER=/usr/local/lib/pokecrack/shell-portability.sh
[[ -f $PORTABILITY_HELPER && ! -L $PORTABILITY_HELPER ]] || fail "shell portability helper is unavailable"
# shellcheck disable=SC1090
source "$PORTABILITY_HELPER"

for command in chromium curl opencli python3 stat websockify x11vnc Xvfb; do
  command -v "$command" >/dev/null 2>&1 || fail "required command not found: $command"
done

profile_root=${CHROMIUM_PROFILE_ROOT:-/profiles}
profile=${CHROMIUM_PROFILE:-research-general}
password_file=${NOVNC_PASSWORD_FILE:-/run/secrets/novnc_password}
display=${DISPLAY:-:99}
novnc_bind=${NOVNC_BIND_HOST:-0.0.0.0}
novnc_port=${NOVNC_PORT:-6080}
cdp_port=${CHROMIUM_CDP_PORT:-9222}
runtime_dir=/run/pokecrack-browser

[[ $profile_root == /* && -d $profile_root && ! -L $profile_root ]] || fail "profile root must be an existing absolute real directory"
[[ $(pokecrack_stat_mode "$profile_root") == 700 ]] || fail "profile root must have mode 0700"
[[ $(pokecrack_stat_uid "$profile_root") == $(id -u) ]] || fail "profile root must be owned by the container browser uid"
[[ -f $password_file && ! -L $password_file ]] || fail "noVNC password secret is unavailable"
IFS= read -r vnc_credential < "$password_file" || fail "could not read noVNC password secret"
[[ ${#vnc_credential} -ge 12 ]] || fail "noVNC password must contain at least 12 characters"
unset vnc_credential
[[ $display =~ ^:[0-9]+$ ]] || fail "DISPLAY must be a local numeric X display"
[[ $novnc_bind == 0.0.0.0 || $novnc_bind == 127.0.0.1 ]] || fail "noVNC bind host must be local/container-only"
[[ $novnc_port =~ ^[0-9]+$ && $cdp_port =~ ^[0-9]+$ ]] || fail "browser ports must be numeric"
((novnc_port >= 1 && novnc_port <= 65535 && cdp_port >= 1 && cdp_port <= 65535)) || fail "browser ports are out of range"

install -d -m 0700 "$runtime_dir"

pids=()
# Invoked indirectly by the EXIT/TERM/INT traps below.
# shellcheck disable=SC2329
shutdown() {
  local status=$?
  trap - EXIT HUP INT TERM
  if [[ ${OPENCLI_ENABLED:-false} == true ]]; then
    opencli daemon stop >/dev/null 2>&1 || true
  fi
  if ((${#pids[@]} >= 4)); then
    kill "${pids[3]}" 2>/dev/null || true
    wait "${pids[3]}" 2>/dev/null || true
  fi
  if ((${#pids[@]})); then
    kill "${pids[@]:0:3}" 2>/dev/null || true
    wait "${pids[@]:0:3}" 2>/dev/null || true
  fi
  exit "$status"
}
trap shutdown EXIT HUP INT TERM

Xvfb "$display" -screen 0 "${XVFB_SCREEN:-1440x900x24}" -nolisten tcp >"$runtime_dir/xvfb.log" 2>&1 &
pids+=("$!")
printf '%s\n' "$!" > "$runtime_dir/xvfb.pid"

display_socket="/tmp/.X11-unix/X${display#:}"
for _attempt in {1..100}; do
  [[ -S $display_socket ]] && break
  kill -0 "${pids[0]}" 2>/dev/null || fail "Xvfb exited before becoming ready"
  sleep 0.1
done
[[ -S $display_socket ]] || fail "Xvfb did not become ready"

# `-passwdfile` keeps the credential itself out of process arguments and logs.
x11vnc -display "$display" -forever -shared -localhost -rfbport 5900 -passwdfile "$password_file" >"$runtime_dir/x11vnc.log" 2>&1 &
pids+=("$!")
printf '%s\n' "$!" > "$runtime_dir/x11vnc.pid"

websockify --web /usr/share/novnc/ "${novnc_bind}:${novnc_port}" 127.0.0.1:5900 >"$runtime_dir/novnc.log" 2>&1 &
pids+=("$!")
printf '%s\n' "$!" > "$runtime_dir/novnc.pid"

python3 -m pokecrack_browser.container_browser --profile "$profile" >"$runtime_dir/browser-supervisor.log" 2>&1 &
pids+=("$!")
printf '%s\n' "$!" > "$runtime_dir/browser-supervisor.pid"

cdp_url="http://127.0.0.1:${cdp_port}/json/version"
for _attempt in {1..200}; do
  curl --fail --silent --show-error --max-time 1 "$cdp_url" >/dev/null 2>&1 && break
  kill -0 "${pids[3]}" 2>/dev/null || fail "BrowserManager supervisor exited before CDP became ready"
  sleep 0.1
done
curl --fail --silent --show-error --max-time 2 "$cdp_url" >/dev/null || fail "Chromium CDP did not become ready"

if [[ ${OPENCLI_ENABLED:-false} == true ]]; then
  opencli daemon restart >/dev/null
fi

# Bash 3.2 has no `wait -n`. Polling the fixed child set preserves the same
# fail-closed contract without waiting indefinitely on whichever PID came first.
while true; do
  for child_pid in "${pids[@]}"; do
    if ! kill -0 "$child_pid" 2>/dev/null; then
      wait "$child_pid" 2>/dev/null || true
      fail "a supervised browser process exited"
    fi
  done
  sleep 0.2
done
