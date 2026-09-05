# Deployment

Use [RELEASE_STATUS.md](RELEASE_STATUS.md) for the dated, verified production
inventory and pending release work. Do not infer the current revision, applied
migrations, credentials, or enabled collectors from an older implementation
report. Verify the exact Personal target through project configuration and
read-only provider evidence before a release; an old credential-unavailable
note is not a reason to request login again.

The documented release gates below remain required. General browser collection,
AI-worker, aggregator, Nostr, and the Bluesky isolated lane must not be enabled
merely to make every repository feature appear live. Each requires its own
verified service-set contract and authorization. Do not describe the whole
research pipeline as production-ready from a Compose render, heartbeat, or web
deployment alone.

## 1. Account-bound prerequisites

The owner must create/approve: a private GitHub repository and deploy key; protected GitHub environments; Supabase Free project and DB password; Vercel Hobby project; VPS/user/Docker access; DNS; noVNC secret; API/provider keys; a reviewed OpenCLI CLI/Bridge artifact; and platform logins/2FA. Review source/platform terms, trademark/name and privacy obligations before live collection.

Keep `DATA_MODE=demo`, `AI_PROVIDER=fixture`, `OPENCLI_ENABLED=false`, public signup off and retailer domains disabled until each corresponding live dependency is proven.

## 2. Database

1. Create a dedicated Supabase project; record region/project reference privately.
2. Test all migrations and pgTAP locally in Docker-capable CI. For YouTube,
   verify the dedicated cache is `UNLOGGED`, forced-RLS, service-role read-only,
   and absent from public/Admin/analytics relations.
3. Take/verify a backup before production changes.
4. Before the lease-fencing migration, stop every legacy worker and verify that no old worker process or in-flight job remains. This protocol upgrade is not compatible with a rolling old/new worker deployment. Run `.github/workflows/migrate-database.yml` manually against a protected environment. `confirm_sha` must equal `GITHUB_SHA`; supply the fresh backup reference. Before any hosted change, the workflow requires hosted PostgreSQL 17 or newer, reads the applied migration versions through the owner-scoped Personal Supabase Management API token, audits only pending migrations, requires an exact reasoned fingerprint for every reviewed `DELETE`, rejects `DROP`/`TRUNCATE`, builds the schema locally on PostgreSQL 17, and rejects generated TypeScript drift. It previews and applies forward migrations only—no automatic destructive rollback/reset and no database URL in the workflow environment, argv, child process or logs. Deploy only generation-aware workers after the migration; never roll code back to the legacy claim/naked-cleanup protocol.
5. Create the first admin account manually; disable public signup; configure redirect/email settings deliberately.
6. Verify private-schema grants/RLS and query the intended public-safe API as anon. Create a dedicated `NOINHERIT` collector login with only queue access and execute permission on the fenced collector RPCs; do not reuse broad `service_role` membership as the steady-state worker permission model. Create a separate `NOINHERIT` backup login/role with only the required read/grant path and PostgreSQL 17 gate-table schema lock, then prove it cannot read gate rows. Never expose DB/service-role credentials to browser variables.

For Nostr specifically, set `NOSTR_COLLECTION_ENABLED=true` only after the
hosted ledger contains `060`, `090`, and `100`, the exact Nostr policy/gate/RLS/ACL and
public v2 contract passes the env-file preflight in
`deploy/lib/verify_nostr_release.py`, and the operator has recorded the
account-specific backup/PITR retention assertion and isolated restore drill
described in `docs/BACKUP_AND_RESTORE.md`. The preflight is deliberately
fail-closed; it invokes the 100 version-two metadata attestation through a separate
`pokecrack_nostr_attestor_login` credential whose libpq startup option is
exactly `-c role=pokecrack_nostr_attestor`. That login is `NOINHERIT`, has
`CONNECTION LIMIT 2`, is not a member of `service_role` or any worker role, and
the selected group can execute only the attestation RPC—no table reads or
other ingest RPCs. A second login selects only
`pokecrack_nostr_worker`, which can execute the seven exact Nostr queue,
heartbeat, begin, and finalize RPCs plus an idempotent current-minute scheduler,
a boolean runtime-contract proof, and a reviewed non-secret policy projection,
but cannot use generic queue RPCs or read tables directly. The generic scheduler
is hard-disabled for Nostr. The distinct DSNs stay only in mode-`0600`
`/etc/pokecrack/nostr.env` as `SUPABASE_NOSTR_PREFLIGHT_DB_URL` and
`NOSTR_SUPABASE_DB_URL`; both target the same host, port, and database. The
attestor DSN is consumed only by the host preflight and is never passed into a
container. Neither DSN may be an owner, `service_role`, shared collector, or
browser credential. Create both logins and their single non-inherited
memberships outside migrations with account-owner authority and fresh random
passwords; never store an owner or service-role DSN on the VPS.

For Bluesky, keep `BLUESKY_COLLECTION_ENABLED=false` in the shared production
file. The opt-in `bluesky` Compose profile reads only the separate mode-`0600`
`/etc/pokecrack/bluesky.env` file, which must contain `DATA_MODE=live`,
`BLUESKY_COLLECTION_ENABLED=true`, and a dedicated
`BLUESKY_SUPABASE_DB_URL`. That URL must be a fresh `NOINHERIT` login whose
libpq startup option is exactly `-c role=pokecrack_bluesky_worker`, with
`sslmode=require` (or stronger) and a bounded `connect_timeout`; it must not be
an owner, `service_role`, or shared collector credential. The migration grants
the capability role only the fixed Bluesky enqueue/claim/heartbeat/fail/pause,
typed begin/finalize/cursor-recovery, health, and read-only policy-snapshot RPCs.
The generic queue RPCs and direct private activity tables are unavailable to
that role, and generic `collector`/`scheduler` processes cannot claim Bluesky.
The host preflight accepts exactly those three environment assignments, rejects
`service_role`, `SUPABASE_DB_URL`, and every unknown key, and requires the
dedicated file to be a regular non-symlink with exact mode `0600`. The
`tcgdex-bluesky` deployment service set runs that preflight before Compose
validation, build, or service replacement; `tcgdex` remains the default. A
Bluesky release additionally forces the exact `tcgdex-bluesky` runtime-evidence
set after health checks. It requires fresh evidence from all four workers, the
TCGdex and Bluesky policies, the three expected schedules, the bounded queue,
the Bluesky checkpoint, and cleanup. A role attestation and healthy containers
alone cannot create a verified success marker. The deploy script also requires
the executable verifier from the detached exact target SHA to declare the exact
`RUNTIME_EVIDENCE_SERVICE_SET=tcgdex-bluesky` capability sentinel before the
service set can be enabled.
Verify this with `docker compose --env-file /etc/pokecrack/production.env
--env-file /etc/pokecrack/bluesky.env -f deploy/compose.prod.yml --profile
bluesky config --quiet`, then inspect the rendered environments and migration
contract before any service replacement. This is an opt-in bounded lane, not a
production-ready claim.

## 3. Web (Vercel)

Import the private repository and use `apps/web` as the project root. Pin the production branch and Node version. Set only `NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_SUPABASE_URL` and the publishable key in browser-visible variables. Keep `ADMIN_EMAILS`, `ADMIN_CONTROL_RPC_ENABLED`, and `SUPABASE_SERVICE_ROLE_KEY` as Vercel server-only variables; never prefix the service-role key with `NEXT_PUBLIC_`, place it in the VPS environment, or enable controls before the Auth claim and email allowlist are verified. Start with `ADMIN_CONTROL_RPC_ENABLED=false` and demo mode, run the production build, verify the demo label/disclaimers and no secret in built assets, then switch to live only after the database public surface and service-role-only Admin RPC grants are verified. DNS/OAuth/email-provider setup is account-bound and was not done here.

## 4. VPS

Use a patched Linux host, dedicated non-root deploy user, SSH keys only, host firewall and Docker Engine/Compose. Clone the private repo to an absolute path; keep config/secrets outside it. Follow `deploy/README.md` to configure the mode-`0600` `/etc/pokecrack/production.env` and backup-marker directory. For Nostr, create a separate mode-`0600` `/etc/pokecrack/nostr.env` from the exact four-key template; for Bluesky, create a separate exact mode-`0600` `/etc/pokecrack/bluesky.env` from the exact three-key template. Do not add either source's DSN to the shared production file. Browser profile/noVNC/Bridge preparation is not part of these service sets.

Deploy an exact commit:

```bash
deploy/scripts/deploy.sh EXACT_LOWERCASE_40_CHARACTER_SHA \
  --env-file /etc/pokecrack/production.env \
  --service-set tcgdex
```

The default service set remains `tcgdex`: collector, scheduler, and watchdog.
The `tcgdex-nostr` set adds only `nostr-collector` and requires both
`--nostr-env-file /etc/pokecrack/nostr.env` and the successful hosted
attestation before any service replacement. The shared collector always has
Nostr disabled; only the dedicated container receives the worker DSN. The
`tcgdex-bluesky` set likewise adds only `bluesky-collector`, requires
`--bluesky-env-file /etc/pokecrack/bluesky.env`, and forces its strictly
healthy aggregate runtime-evidence gate before it can advance the success
marker. The shared
collector always has Bluesky disabled; only the dedicated container receives
the Bluesky worker DSN. The script refuses full mode and every unknown
container. Removing an existing
Nostr container requires the explicit `--retire-nostr` rollback flag; it never
uses `--remove-orphans`. The atomic success manifest records SHA, service-set
name, and exact services. The GitHub deploy workflow requires the same explicit
choice and verifies remote `HEAD == GITHUB_SHA`; it never uses `git pull`.
Protect `worker-production` with a custom deployment-branch policy matching
only `main`, then configure `VPS_HOST`, `VPS_USER`, `VPS_PORT`,
`VPS_DEPLOY_PATH`, `VPS_ENV_FILE`, `VPS_NOSTR_ENV_FILE`,
`VPS_BLUESKY_ENV_FILE`,
`VPS_SSH_PRIVATE_KEY`, pinned `VPS_KNOWN_HOSTS`, and the protected
`WORKER_SUPABASE_DB_URL` secret. The worker URL must use the persistent
`pokecrack_worker` login and the exact primary Tokyo transaction pooler returned
by the Management API on port `6543`, with
`application_name=pokecrack-worker`, `connect_timeout=10`,
`sslmode=verify-full`, and the container CA path
`/run/supabase-prod-ca-2021.crt`. Before deploying the exact commit, the
workflow validates that complete contract and atomically replaces only the
single `SUPABASE_DB_URL` assignment in the owner-readable `VPS_ENV_FILE`; it
does not print the URL or leave its transfer files behind. Never use a
short-lived backup login as the worker credential.

For a stronger post-deploy gate than container health, provision the dedicated
`pokecrack_runtime_monitor` capability role from migrations
`20260923000000_runtime_release_evidence.sql` and
`20260924000000_runtime_release_evidence_hardening.sql`, plus the exact
outside-migration `pokecrack_runtime_monitor_login` NOINHERIT login. That login
must be `NOSUPERUSER`, `NOCREATEDB`, `NOCREATEROLE`, `NOREPLICATION`,
`NOBYPASSRLS`, `CONNECTION LIMIT 2`, and have only the capability membership
`pokecrack_runtime_monitor_login -> pokecrack_runtime_monitor` with
`INHERIT FALSE, SET TRUE`. Role attributes, ownership, or memberships that
drift from this contract fail closed; they are not silently normalized. Put
only that login's TLS URL in the mode-0600 production env file as
`RUNTIME_RELEASE_EVIDENCE_DB_URL`; the watchdog is the only container that
receives it. Then opt into the verifier during deployment:

```bash
deploy/scripts/deploy.sh EXACT_LOWERCASE_40_CHARACTER_SHA \
  --env-file /etc/pokecrack/production.env \
  --service-set tcgdex \
  --verify-runtime
```

The verifier reports aggregate worker heartbeat age/status, observed source
state, expected schedule/job outcome, checkpoint freshness, queue age bands,
cleanup freshness, and local backup-marker age where a narrowly scoped marker
mount is available. It never prints source text, URLs, payloads, policy/gate
identifiers, cursors, credentials, image labels, or identity. For ordinary
observations, `healthy` and first-run `warming_up` exit 0; the forced Bluesky
deployment gate treats `warming_up` as inconclusive and cannot advance its
success marker. Observed stale/failed evidence exits 1;
missing/incompatible schema, service set, exact running-image revision, role,
or monitor access is explicitly `inconclusive` and exits 2. Missing,
unsupported, or unreadable backup markers are also `inconclusive` (exit 2),
including during first-run grace; the default owner-only backup directory is
not made group-readable for the watchdog. Enabled sources and checkpoints must
advance at or after the bounded release start before `healthy` is possible.
The `tcgdex-nostr` set additionally requires Nostr worker heartbeat, checkpoint,
and expected schedule evidence. The `tcgdex-bluesky` set applies equivalent
Bluesky requirements automatically and cannot run without the post-release
gate. No migration or deployment is automatic. For an already-running release, the same check is
available directly as `deploy/scripts/verify-runtime-release.sh` with an exact
SHA, explicit service set, and release start.

If health or runtime evidence fails after replacement, the new containers stay
in place for diagnosis, the success manifest is not advanced, and no automated
rollback is attempted. Preserve the aggregate evidence, then select an
explicit compatible SHA and run `rollback.sh` when an operator has approved the
recovery.

After every database or password rotation, provision the two login roles from
an owner-controlled, parameterized session (never a password literal in a
shell argument or repository): `NOINHERIT`, `NOSUPERUSER`, `NOCREATEDB`,
`NOCREATEROLE`, `NOREPLICATION`, `NOBYPASSRLS`, `CONNECTION LIMIT 2`, and one
membership using `WITH INHERIT FALSE, SET TRUE`. Run the preflight through a
real login connection; a test-only `SET ROLE` from postgres does not prove the
startup option or password path.

## 5. Authenticated browser

Install only an explicit reviewed artifact, start the service, then use exactly:

```bash
ssh -L 6080:127.0.0.1:6080 VPS_USER@VPS_HOST
```

Complete login/CAPTCHA/2FA manually, run doctor/auth/read-only adapter checks, then close the tunnel. Never publish 6080 or map CDP/VNC/daemon ports.

## 6. Acceptance record

For a real release record: exact Git SHA; exact service-set manifest; CI and
migration run; backup reference and plan-specific retention evidence; Supabase
project reference (not secret); VPS host identifier; every selected service
healthy; excluded services absent; runtime verifier status and exit code (with
worker/source/schedule/checkpoint/queue/cleanup aggregates and marker age);
source checkpoints/jobs advancing; anon public projection redaction;
restore-drill date; and known warnings. For Nostr,
also record that both dedicated sessions authenticated, the 15-key v2 contract
was all true, three relay jobs completed, and neither DSN appeared in logs or
container inspection. A Compose render, migration file, heartbeat-only result,
or successful script write alone is not deployment evidence.
