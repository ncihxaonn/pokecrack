FROM mcr.microsoft.com/playwright/python:v1.55.0-noble

ENV DEBIAN_FRONTEND=noninteractive \
    DISPLAY=:99 \
    PYTHONUNBUFFERED=1 \
    POKECRACK_BROWSER_PROFILE_ROOT=/var/lib/pokecrack-browser/profiles \
    POKECRACK_BROWSER_RUNTIME_ROOT=/run/pokecrack-browser \
    POKECRACK_BRIDGE_EXTENSION_PATH=/opt/pokecrack/opencli-extension/current \
    POKECRACK_ADAPTER_ROOT=/opt/pokecrack/auth-browser/adapters \
    POKECRACK_CDP_HOST=127.0.0.1 \
    POKECRACK_CDP_PORT=9222 \
    POKECRACK_DAEMON_HOST=127.0.0.1 \
    POKECRACK_DAEMON_PORT=19825 \
    VNC_PASSWORD_FILE=/run/secrets/vnc_password

RUN apt-get update \
 && apt-get install -y --no-install-recommends \
      fluxbox novnc supervisor websockify x11vnc xvfb \
 && rm -rf /var/lib/apt/lists/* \
 && useradd --create-home --uid 10001 --shell /usr/sbin/nologin pokecrack \
 && install -d -m 0700 -o pokecrack -g pokecrack \
      /var/lib/pokecrack-browser/profiles /run/pokecrack-browser \
      /opt/pokecrack/opencli-extension /opt/pokecrack/opencli

WORKDIR /opt/pokecrack/auth-browser
COPY pyproject.toml uv.lock README.md ./
COPY src ./src
COPY adapters ./adapters
RUN python -m pip install --no-cache-dir .
COPY --chmod=0755 container/entrypoint.sh /usr/local/bin/auth-browser-entrypoint
COPY --chmod=0755 container/run_bridge_daemon.py /opt/pokecrack/auth-browser/container/run_bridge_daemon.py
COPY container/supervisord.conf /etc/supervisor/conf.d/auth-browser.conf
RUN chown -R pokecrack:pokecrack /opt/pokecrack/auth-browser

USER pokecrack
ENTRYPOINT ["/usr/local/bin/auth-browser-entrypoint"]
