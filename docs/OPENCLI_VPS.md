# OpenCLI and Browser Bridge on the VPS

## Honest boundary

The repository provides a headed Chromium/noVNC container, profile/path controls and a checksum-pinned extension installer. No compatible OpenCLI CLI/Browser Bridge release URL/checksum or logged-in account was available, so authenticated commands remain fixture/account-bound. Never guess an artifact or use `latest`.

## Install and profile security

Create the profile root for container uid/gid `10001`:

```bash
sudo install -d -o 10001 -g 10001 -m 0700 /opt/pokecrack/browser-profiles
sudo install -d -o "$USER" -g "$USER" -m 0755 /opt/pokecrack/opencli-extension
```

Install an audited unpacked Browser Bridge with explicit version, checksum and HTTPS URL/template:

```bash
deploy/scripts/install-opencli-extension.sh install \
  --version "$OPENCLI_EXTENSION_VERSION" \
  --sha256 "$OPENCLI_EXTENSION_SHA256" \
  --url "$OPENCLI_EXTENSION_URL" \
  --install-root /opt/pokecrack/opencli-extension
```

Only set `OPENCLI_ENABLED=true` after the extension, a compatible pinned CLI/daemon in the image, and adapter allowlists are all verified. Keep separate allowlisted profiles (`social-western`, `social-chinese`, `research-general`) where policy/account isolation requires it. Profile directories and cookies are credentials: mode `0700`, owner uid `10001`, no Git/cloud sync or unencrypted backup.

## Login, 2FA, doctor and adapter flow

1. Select the single container-owned profile in the root-readable production environment before running the exact-SHA deployment:

   ```bash
   CHROMIUM_PROFILE=research-general
   ```

   The `auth-browser` container supervisor starts this profile through `BrowserManager` and holds the one-profile lock for the container lifetime. Do not run `start-profile` inside the running Compose service.

2. From the operator computer open exactly:

   ```bash
   ssh -L 6080:127.0.0.1:6080 VPS_USER@VPS_HOST
   ```

3. Visit `http://127.0.0.1:6080` (or `/vnc.html`), authenticate to noVNC, and confirm the Browser Bridge extension is loaded.
4. In headed Chromium, navigate manually to the permitted platform, sign in, and complete CAPTCHA/2FA manually. Do not send credentials/codes through logs, CLI arguments, prompts or chat.
5. Run inside the container after a compatible pinned OpenCLI release is installed:

   ```bash
   opencli doctor
   pokecrack-browser doctor
   pokecrack-browser check-auth SOURCE_NAME
   pokecrack-browser run-opencli ADAPTER_NAME --dry-run
   pokecrack-browser run-opencli ADAPTER_NAME
   ```

   The adapter smoke test must be read-only, allowlisted and bounded. Fixture adapters validate the runner contract without logging in; real behavior remains account/platform/version dependent.
6. Validate the output and close the SSH tunnel. To switch profiles, change `CHROMIUM_PROFILE` in the root-readable production environment and rerun the exact-SHA deploy/recreate flow; do not run `stop-profile` behind the container supervisor.

The VPS scheduler remains the runtime owner; the operator computer is not a continuous dependency. Profiles are serialized and never share cookies.

Host port `6080` is loopback-only. Container CDP `9222`, VNC `5900` and daemon `19825` stay un-published. Do not add firewall exceptions or public reverse proxying. On auth failure, stop that adapter, reopen the tunnel, inspect manually, and reauthenticate; never bypass controls.

Rollback the extension with `deploy/scripts/install-opencli-extension.sh rollback --install-root /opt/pokecrack/opencli-extension`; this atomically swaps `current`/`previous` without deleting releases.
