#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'

runtime_dir=/run/pokecrack-browser
for process_name in xvfb x11vnc novnc chromium; do
  pid_file="$runtime_dir/$process_name.pid"
  [[ -s $pid_file ]] || exit 1
  IFS= read -r pid < "$pid_file"
  [[ $pid =~ ^[0-9]+$ ]] || exit 1
  kill -0 "$pid" 2>/dev/null || exit 1
done
curl --fail --silent --show-error --max-time 3 http://127.0.0.1:6080/vnc.html >/dev/null
curl --fail --silent --show-error --max-time 3 "http://127.0.0.1:${CHROMIUM_CDP_PORT:-9222}/json/version" >/dev/null
if [[ ${OPENCLI_ENABLED:-false} == true ]]; then
  python3 -m pokecrack_browser doctor >/dev/null
  python3 -c 'import socket, sys
with socket.create_connection(("127.0.0.1", int(sys.argv[1])), timeout=2):
    pass
' "${OPENCLI_DAEMON_PORT:-19825}"
fi
