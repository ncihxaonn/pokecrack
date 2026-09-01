# VPS deployment artifacts

These files are **implemented deployment artifacts, not evidence that the
current branch was deployed**. The exact previously verified hosted baseline is
recorded in `docs/IMPLEMENTATION_NOTES.md`; do not infer a later migration,
worker, browser account, DNS change, or release from repository files alone.
Local Docker builds were not run on this Mac because the Docker CLI/socket is
absent.

## Runtime layout

`compose.prod.yml` defines `collector`, `nostr-collector`, `auth-browser`, `ai-worker`, `aggregator`, `scheduler`, and `watchdog`. The default profile contains only the supported TCGdex core: `collector`, `scheduler`, and `watchdog`. The gated `nostr` profile adds only the isolated Nostr collector; `auth-browser`, `ai-worker`, and `aggregator` remain behind `unready-full`, and the release script refuses that full set. Worker roles share `Dockerfile.worker`; the headed browser uses `Dockerfile.auth-browser`. Every service has `restart: unless-stopped`, bounded local Docker logs, a health check, a read-only root filesystem, a private `/tmp` tmpfs, dropped capabilities, `no-new-privileges`, configurable CPU/RAM limits, and no Docker socket.

Services join a non-published bridge for outbound Internet/Supabase access and an `internal: true` network for private service traffic. The only published port is host loopback `127.0.0.1:6080`. CDP `9222`, VNC `5900`, and the OpenCLI daemon `19825` are never published.

The core release uses only the backup-marker volume. Optional, currently
unreleased browser artifacts additionally use:

- `/opt/pokecrack/browser-profiles` -> `/profiles` (sensitive, mode `0700`, uid/gid `10001`);
- `/opt/pokecrack/backups` -> watchdog read-only marker access;
- `/opt/pokecrack/opencli-extension` -> browser read-only pinned extension releases.

## One-time host preparation

Run as a dedicated non-root deploy operator with Docker access. The TCGdex core
requires only the backup and configuration directories:

```bash
sudo install -d -o "$USER" -g "$USER" -m 0700 /opt/pokecrack/backups
sudo install -d -o root -g root -m 0700 /etc/pokecrack
sudo cp deploy/env/production.env.example /etc/pokecrack/production.env
sudo chmod 0600 /etc/pokecrack/production.env
sudoedit /etc/pokecrack/production.env
```

Put real secrets only in the root-readable environment file, never in Git, Compose YAML, command history, issues, prompts, or logs. Set `DATA_MODE=live` only after a real Supabase database is migrated and tested. Use a dedicated TLS database URL with bounded connection timeout, keep `WORKER_MAX_CONCURRENCY=1`, `YOUTUBE_COLLECTION_ENABLED=false`, `AI_PROVIDER=fixture`, and `OPENCLI_ENABLED=false`. The TCGdex catalog does not require an API key.

The browser profile, extension directory, and long unique noVNC secret described
below are not prerequisites for the TCGdex core. Prepare them only under a
separately reviewed browser release.

Nostr additionally requires the exact four-key file. Create it only after
migrations `060`, `090`, and `100`, both dedicated logins, backup/PITR evidence,
and an isolated restore drill are complete:

```bash
sudo cp deploy/env/nostr.env.example /etc/pokecrack/nostr.env
sudo chmod 0600 /etc/pokecrack/nostr.env
sudoedit /etc/pokecrack/nostr.env
```

The attestor and worker DSNs must be different credentials for the same
host/port/database and use their exact role options. Never place either one in
`production.env`; the attestor DSN is host-preflight-only and is not passed to
any container.

## Pin the Browser Bridge

Do not invent an OpenCLI release location. Obtain the audited extension version, HTTPS artifact URL (or documented URL template), and SHA-256 from the actual supplier, then run:

```bash
deploy/scripts/install-opencli-extension.sh install \
  --version "$OPENCLI_EXTENSION_VERSION" \
  --sha256 "$OPENCLI_EXTENSION_SHA256" \
  --url "$OPENCLI_EXTENSION_URL" \
  --install-root /opt/pokecrack/opencli-extension
```

The installer downloads to a temporary directory, verifies the checksum and manifest, rejects `latest`, and atomically switches `current` only after validation. It retains `previous` and all releases. Roll back explicitly with:

```bash
deploy/scripts/install-opencli-extension.sh rollback \
  --install-root /opt/pokecrack/opencli-extension
```

No compatible OpenCLI CLI/Browser Bridge artifact was available in this implementation environment. `OPENCLI_ENABLED=false` is therefore the honest default.

## Deploy and roll back an exact commit

The production checkout must be clean and the commit must be an exact lowercase 40-character SHA:

```bash
deploy/scripts/deploy.sh 0123456789abcdef0123456789abcdef01234567 \
  --env-file /etc/pokecrack/production.env \
  --service-set tcgdex
```

The script fetches the exact object only if absent, checks out detached at that SHA, validates Compose without printing expanded secrets, refuses any existing non-core service container rather than stopping it without approval, builds and starts only the three core services, and waits for all three health checks. It then atomically writes `/var/lib/pokecrack/deploy/last-successful-deployment` with the exact SHA, service-set name, and exact service list. A manual partial `docker compose up` cannot create this success record. The script never runs `git pull`.

After the Nostr release gate passes, deploy the four-service set explicitly:

```bash
deploy/scripts/deploy.sh 0123456789abcdef0123456789abcdef01234567 \
  --env-file /etc/pokecrack/production.env \
  --nostr-env-file /etc/pokecrack/nostr.env \
  --service-set tcgdex-nostr
```

The shared collector never receives the Nostr flag or worker DSN. The Nostr
container receives only its dedicated DSN; the separate attestor URL is read by
the host preflight before build/up and removed from the child environment.

The full service set is unavailable. Existing browser/AI/aggregator containers
must be retired through a separately approved operation before the core release;
the deploy script will not stop or remove them implicitly.

Rollback always requires the chosen commit; it does not guess “previous”:

```bash
deploy/scripts/rollback.sh FED_SHA_IN_LOWERCASE_40_HEX \
  --env-file /etc/pokecrack/production.env \
  --service-set tcgdex
```

The rollback SHA must be compatible with every already-applied forward database
migration. To intentionally disable an existing Nostr container, select a
Nostr-compatible exact SHA and add `--retire-nostr`; that explicit flag stops
and removes only the managed `nostr-collector` before validating the three core
services. No path uses `--remove-orphans`.

## Browser login and tunnel

Open the tunnel from the operator computer exactly as follows:

```bash
ssh -L 6080:127.0.0.1:6080 VPS_USER@VPS_HOST
```

Then open `http://127.0.0.1:6080/vnc.html`, unlock noVNC, log in manually, complete CAPTCHA/2FA yourself, close the browser view, and run the browser `doctor`, `check-auth`, and one read-only adapter smoke command inside the container. Never automate CAPTCHA or 2FA. Close the SSH session when done. See `docs/OPENCLI_VPS.md`.

The container automatically starts the allowlisted profile selected by `CHROMIUM_PROFILE` through `BrowserManager`; it owns the profile state and lock until shutdown. Change the production environment and use the exact-SHA deploy/recreate flow to switch profiles. Do not invoke `start-profile` or `stop-profile` inside the supervised Compose service.

## Operations scripts

- `deploy/scripts/backup.sh`: a stdin-only URL runner requires `sslmode=require` or stronger, clears inherited `PG*`, and maps only allowlisted fields to libpq -> independently role-switched `psql` policy/table/privilege preflights -> one-snapshot plain `pg_dump` on the owner-capable login, strictly limited to `catalog`, `ingest`, `analytics`, `public`, and `supabase_migrations` (never provider `auth`/`storage`/`realtime` data), with exact request-gate and private social-activity data exclusions -> fail-closed sanitizer that verifies the policy-free regular gate schema, rejects live gate rows, inserts canonical idle gates before RLS enablement, strips disposable social discovery rows, retains exact checkpoints, and retains the public-study ledger only after exact schema/COPY/row validation -> gzip, non-empty validation, UTC filename, atomic last-success marker, newest 7 daily plus 4 weekly representatives.
- `deploy/scripts/cleanup.sh`: removes only stopped project containers and unused labeled images; never stops services or prunes volumes/profiles/backups/extensions.
- `deploy/scripts/deploy.sh`: exact-SHA, exact-service-set build/start/health gate plus host-only Nostr attestation.
- `deploy/scripts/rollback.sh`: explicit-SHA deployment of the same deterministic service set.
- `deploy/scripts/install-opencli-extension.sh`: pinned extension install/rollback.

Run `python3 -m unittest -v deploy.tests.test_deploy_artifacts` and `docker compose --env-file /etc/pokecrack/production.env -f deploy/compose.prod.yml config --quiet` before a release. A successful render is not a successful image build or deployment.
