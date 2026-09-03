# VPS deployment artifacts

These files are **implemented deployment artifacts, not evidence that the
current branch was deployed**. The exact previously verified hosted baseline is
recorded in `docs/IMPLEMENTATION_NOTES.md`; do not infer a later migration,
worker, browser account, DNS change, or release from repository files alone.
Local Docker builds were not run on this Mac because the Docker CLI/socket is
absent.

## Runtime layout

`compose.prod.yml` defines `collector`, `nostr-collector`, `bluesky-collector`, `auth-browser`, `ai-worker`, `aggregator`, `scheduler`, and `watchdog`. The default profile contains only the supported TCGdex core: `collector`, `scheduler`, and `watchdog`. The gated `nostr` and `bluesky` profiles add only their independently schedulable, least-privilege source lane; `auth-browser`, `ai-worker`, and `aggregator` remain behind `unready-full`, and the release script refuses that full set. Worker roles share `Dockerfile.worker`; the headed browser uses `Dockerfile.auth-browser`. Every service has `restart: unless-stopped`, bounded local Docker logs, a health check, a read-only root filesystem, a private `/tmp` tmpfs, dropped capabilities, `no-new-privileges`, configurable CPU/RAM limits, and no Docker socket.

Services join a non-published bridge for outbound Internet/Supabase access and an `internal: true` network for private service traffic. The only published port is host loopback `127.0.0.1:6080`. CDP `9222`, VNC `5900`, and the OpenCLI daemon `19825` are never published.

The core release uses only the backup-marker volume. Optional, currently
unreleased browser artifacts additionally use:

- `/opt/pokecrack/browser-profiles` -> `/profiles` (sensitive, mode `0700`, uid/gid `10001`);
- `/opt/pokecrack/backups` -> watchdog read-only volume (the default `0700`/`0600`
  backup contract intentionally keeps the marker unavailable to container UID
  `10001`);
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

The default backup directory remains owner-only (`0700`) and backup artifacts and
the success marker remain owner-only (`0600`). Do not broaden that directory or
marker permissions to make the watchdog readable. Until a separately reviewed,
narrow marker-only mount is provisioned for UID `10001`, runtime verification
reports a missing, unsupported, or unreadable backup marker as `inconclusive`
(exit `2`), including during first-run grace. This preserves backup
confidentiality and never treats an unavailable marker as a successful backup.

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

Bluesky uses a separate mode-`0600` file and login. Create it only after the
Bluesky isolation migration and an isolated restore/retention review are
complete:

```bash
sudo cp deploy/env/bluesky.env.example /etc/pokecrack/bluesky.env
sudo chmod 0600 /etc/pokecrack/bluesky.env
sudoedit /etc/pokecrack/bluesky.env
```

Set `BLUESKY_SUPABASE_DB_URL` to a fresh `NOINHERIT` login whose startup option
selects only `pokecrack_bluesky_worker`; it must use secure TLS and a positive
`connect_timeout` no greater than 60 seconds. The host preflight accepts only
the exact three assignments in this file, requires a regular non-symlink file
with mode `0600`, and rejects `service_role`, `SUPABASE_DB_URL`, or unknown
keys without printing secret values. Never put the DSN in `production.env` or
reuse a `service_role` URL. The default source and Compose profile remain
disabled. This repository contains deployment artifacts and verification
instructions, not evidence of a production-ready Bluesky release.

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

After the Bluesky migration and owner-provisioned login pass their contract,
deploy the four-service set explicitly. The script validates the exact env
file, runs the boolean-only hosted attestation before any replacement, and
records the exact service list in the success marker once the runtime-release
evidence verifier has an explicit `tcgdex-bluesky` implementation and declares
the exact `RUNTIME_EVIDENCE_SERVICE_SET=tcgdex-bluesky` capability sentinel:

```bash
deploy/scripts/deploy.sh 0123456789abcdef0123456789abcdef01234567 \
  --env-file /etc/pokecrack/production.env \
  --bluesky-env-file /etc/pokecrack/bluesky.env \
  --service-set tcgdex-bluesky
```

The default `tcgdex` set remains unchanged. Existing `bluesky-collector`
containers are rejected unless the explicit `--retire-bluesky` operation is
selected on a `tcgdex` deployment; the script never uses `--remove-orphans`.
Until that runtime verifier integration lands, the `tcgdex-bluesky` command is
deliberately rejected before Compose or service replacement; a comment or
unrelated service-set string cannot unlock it.

Bluesky is an independent opt-in profile. Before enabling it, apply and verify
the forward migration, provision the dedicated `NOLOGIN` capability plus a
separate login, and check the login DSN has `options=-c
role=pokecrack_bluesky_worker`, `sslmode=require` (or stronger), and a bounded
`connect_timeout`. Then run the Compose render with the separate file:

```bash
docker compose --env-file /etc/pokecrack/production.env \
  --env-file /etc/pokecrack/bluesky.env \
  -f deploy/compose.prod.yml --profile bluesky config --quiet
```

Only after that review should an operator build/start the `bluesky-collector`
service explicitly. Verify that `collector` and `scheduler` show
`BLUESKY_COLLECTION_ENABLED=false`, the dedicated container has no
`SUPABASE_DB_URL`, the env file is mode `0600`, and the Bluesky heartbeat,
durable cursor, and typed job lease advance. A render or heartbeat alone is not
deployment evidence and does not establish production readiness.

The full service set is unavailable. Existing browser/AI/aggregator containers
must be retired through a separately approved operation before the core release;
the deploy script will not stop or remove them implicitly.

### Verify runtime release evidence

Container health proves only that processes started. A release operator can
add the bounded runtime gate after the health wait:

```bash
deploy/scripts/deploy.sh EXACT_LOWERCASE_40_CHARACTER_SHA \
  --env-file /etc/pokecrack/production.env \
  --service-set tcgdex \
  --verify-runtime
```

The gate invokes the read-only `verify-release` command in the watchdog. It
uses the private `ingest.get_runtime_release_evidence_v1` RPC from migrations
`20260923000000_runtime_release_evidence.sql` and
`20260924000000_runtime_release_evidence_hardening.sql` through the dedicated
`pokecrack_runtime_monitor` capability role. Provision the exact
`pokecrack_runtime_monitor_login` NOINHERIT login outside migrations with
`NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOREPLICATION`, `NOBYPASSRLS`,
`CONNECTION LIMIT 2`, and only the membership
`pokecrack_runtime_monitor_login -> pokecrack_runtime_monitor` with
`INHERIT FALSE, SET TRUE`. The login must not inherit any other capability or
be a member of `service_role`. Set its TLS URL as
`RUNTIME_RELEASE_EVIDENCE_DB_URL` in the mode-0600 environment file, and do
not use `anon`, `authenticated`, `service_role`, or a worker DSN. The URL is
forced to `options=-c role=pokecrack_runtime_monitor` by the worker and is
never printed. Existing role attributes, ownership, or memberships that drift
from this contract fail closed; the migration does not normalize unknown role
state.

The verifier prints only status, counts, age bands, and backup-marker age. It
returns success for `healthy` and first-run `warming_up`, exit 1 for observed
stale/failed evidence, and exit 2 for unavailable or incompatible schema,
configuration, role, image, or marker evidence. A new release remains
`warming_up` for the configured grace window until its expected service-set
heartbeat, schedule, source/checkpoint, and cleanup evidence exists. Enabled
sources and checkpoints must advance at or after the release start before the
result can become `healthy`; disabled source policies remain observed as
disabled and do not become implicit expectations. The verifier checks the
running container image revision against the requested exact SHA and requires
the explicit `tcgdex` or `tcgdex-nostr` service set (the latter includes the
Nostr worker heartbeat/checkpoint/schedule evidence). The deploy script advances
its success manifest only when this optional gate succeeds. It never applies
migrations or deploys anything on its own.

If health or runtime evidence fails after replacement, the new containers are
left in place for diagnosis, the success manifest is not advanced, and no
rollback is attempted. Choose a known-good compatible SHA and run the explicit
rollback command below after preserving the aggregate evidence.

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

- `deploy/scripts/backup.sh`: a stdin-only URL runner requires `sslmode=require` or stronger, clears inherited `PG*`, and maps only allowlisted fields to libpq -> independently role-switched `psql` policy/table/privilege preflights -> one-snapshot plain `pg_dump` on the owner-capable login, strictly limited to `catalog`, `ingest`, `analytics`, `public`, and `supabase_migrations` (never provider `auth`/`storage`/`realtime` data), with exact request-gate and private social-activity data exclusions -> fail-closed sanitizer that verifies the policy-free regular gate schema, rejects live gate rows, inserts canonical idle gates before RLS enablement, strips disposable social discovery rows, retains exact checkpoints, retains the public-study ledger only after exact schema/COPY/row validation, and retains the optional aggregate-admission bridge only as a complete immutable source/binding/admission bundle -> gzip, non-empty validation, UTC filename, atomic last-success marker, newest 7 daily plus 4 weekly representatives.
- `deploy/scripts/cleanup.sh`: removes only stopped project containers and unused labeled images; never stops services or prunes volumes/profiles/backups/extensions.
- `deploy/scripts/deploy.sh`: exact-SHA, exact-service-set build/start/health gate plus host-only Nostr attestation; rejects the retired once-daily TCGdex schedule before checkout while preserving other explicit operator overrides.
- `deploy/scripts/verify-runtime-release.sh`: optional exact-SHA post-deploy aggregate verifier; it executes only inside the already-running watchdog and preserves `healthy`/`warming_up`/failure exit semantics.
- `deploy/scripts/rollback.sh`: explicit-SHA deployment of the same deterministic service set.
- `deploy/scripts/install-opencli-extension.sh`: pinned extension install/rollback.

Run `python3 -m unittest -v deploy.tests.test_deploy_artifacts` and `docker compose --env-file /etc/pokecrack/production.env -f deploy/compose.prod.yml config --quiet` before a release. A successful render is not a successful image build or deployment.
