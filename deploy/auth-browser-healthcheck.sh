#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

runtime_dir=/run/pokecrack-browser
for process_name in xvfb x11vnc novnc browser-supervisor; do
  pid_file="$runtime_dir/$process_name.pid"
  [[ -s $pid_file ]] || exit 1
  IFS= read -r pid < "$pid_file"
  [[ $pid =~ ^[0-9]+$ ]] || exit 1
  kill -0 "$pid" 2>/dev/null || exit 1
done
python3 -c 'import sys
from pokecrack_browser.config import ServiceSettings
from pokecrack_browser.runtime import process_matches_identity, read_runtime_state
settings = ServiceSettings.from_env()
state = read_runtime_state(settings.runtime_root)
if state is None or state.get("profile") != sys.argv[1]:
    raise SystemExit(1)
pid = state.get("pid")
identity = state.get("process_identity")
if not isinstance(pid, int) or isinstance(pid, bool) or not isinstance(identity, str):
    raise SystemExit(1)
if not process_matches_identity(pid, identity):
    raise SystemExit(1)
' "${CHROMIUM_PROFILE:-research-general}"
curl --fail --silent --show-error --max-time 3 http://127.0.0.1:6080/vnc.html >/dev/null
curl --fail --silent --show-error --max-time 3 "http://127.0.0.1:${CHROMIUM_CDP_PORT:-9222}/json/version" >/dev/null
if [[ ${OPENCLI_ENABLED:-false} == true ]]; then
  python3 -c 'import sys
from pokecrack_browser.runner import run_bounded_process
result = run_bounded_process(
    sys.argv[1:],
    timeout_seconds=10,
    max_stdout_bytes=65536,
    max_stderr_bytes=65536,
)
raise SystemExit(0 if result.returncode == 0 else 1)
' opencli doctor
  python3 -m pokecrack_browser doctor >/dev/null
  python3 -c 'import socket, sys
with socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=2):
    pass
' "${OPENCLI_DAEMON_PORT:-19825}"
fi
