#!/bin/sh
set -eu
umask 077
python -m pokecrack_browser.container_init
exec /usr/bin/supervisord -n -c /etc/supervisor/conf.d/auth-browser.conf
