# Deployment

The approved Personal targets currently host the private GitHub repository and
the public Vercel site. The last verified Vercel production revision was
`36d8701e85c098160635580aa46f614dcfdf066b`; the MAM VPS was separately
observed at `fdfb49ebb03d116abafcfeccaa09618d171ee0fb` with the existing
TCGdex/Bluesky service set. Those are historical observations, not evidence for
this branch. General browser collection, AI-worker, aggregator, Nostr, and
Mastodon remain fail closed until their separate release contracts pass. Do not
describe the whole research pipeline as production-ready from a Compose render,
heartbeat, or web deployment alone.

> **Nostr remains disabled:** the authoritative hosted ledger currently stops
> at `050`; `060`, `090`, and the worker-isolation migration `100` are not hosted, and
> the owner-scoped Personal Supabase credential is unavailable. Keep
> `NOSTR_COLLECTION_ENABLED=false`. A future Nostr release must use the
> Management API migration runner, then pass the env-file preflight in
> `deploy/lib/verify_nostr_release.py` before replacing any service.
> Provider-managed backup/PITR retention has not been evidenced, and the
> dedicated login creation and exact membership remain blockers; neither may be
> inferred from a successful local migration or Compose render.

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

## 3. Web (Vercel)

Import the private repository and use `apps/web` as the project root. Pin the production branch and Node version. Set only `NEXT_PUBLIC_SITE_URL`, `NEXT_PUBLIC_SUPABASE_URL` and the publishable key in browser-visible variables. Keep `ADMIN_EMAILS`, `ADMIN_CONTROL_RPC_ENABLED`, and `SUPABASE_SERVICE_ROLE_KEY` as Vercel server-only variables; never prefix the service-role key with `NEXT_PUBLIC_`, place it in the VPS environment, or enable controls before the Auth claim and email allowlist are verified. Start with `ADMIN_CONTROL_RPC_ENABLED=false` and demo mode, run the production build, verify the demo label/disclaimers and no secret in built assets, then switch to live only after the database public surface and service-role-only Admin RPC grants are verified. DNS/OAuth/email-provider setup is account-bound and was not done here.

## 4. VPS

Use a patched Linux host, dedicated non-root deploy user, SSH keys only, host firewall and Docker Engine/Compose. Clone the private repo to an absolute path; keep config/secrets outside it. Follow `deploy/README.md` to configure the mode-`0600` `/etc/pokecrack/production.env` and backup-marker directory. For Nostr, create a separate mode-`0600` `/etc/pokecrack/nostr.env` from the exact four-key template; do not add either Nostr DSN to the shared production file. Browser profile/noVNC/Bridge preparation is not part of these service sets.

Deploy an exact commit:

```bash
deploy/scripts/deploy.sh EXACT_LOWERCASE_40_CHARACTER_SHA \
  --env-file /etc/pokecrack/production.env \
  --service-set tcgdex
```

The default service set remains `tcgdex`: collector, scheduler, and watchdog.
The gated `tcgdex-nostr` set adds only `nostr-collector` and requires both
`--nostr-env-file /etc/pokecrack/nostr.env` and the successful hosted
attestation before any service replacement. The shared collector always has
Nostr disabled; only the dedicated container receives the worker DSN. The
script refuses full mode and every unknown container. Removing an existing
Nostr container requires the explicit `--retire-nostr` rollback flag; it never
uses `--remove-orphans`. The atomic success manifest records SHA, service-set
name, and exact services. The GitHub deploy workflow requires the same explicit
choice and verifies remote `HEAD == GITHUB_SHA`; it never uses `git pull`.
Protect `worker-production` and configure `VPS_HOST`, `VPS_USER`, `VPS_PORT`,
`VPS_DEPLOY_PATH`, `VPS_ENV_FILE`, `VPS_NOSTR_ENV_FILE`,
`VPS_SSH_PRIVATE_KEY`, and pinned `VPS_KNOWN_HOSTS`.

For a stronger post-deploy gate than container health, provision the dedicated
`pokecrack_runtime_monitor` capability role from migration
`20260923000000_runtime_release_evidence.sql` and an outside-migration
NOINHERIT login. Put only that login's TLS URL in the mode-0600 production env
file as `RUNTIME_RELEASE_EVIDENCE_DB_URL`; the watchdog is the only container
that receives it. Then opt into the verifier during deployment:

```bash
deploy/scripts/deploy.sh EXACT_LOWERCASE_40_CHARACTER_SHA \
  --env-file /etc/pokecrack/production.env \
  --service-set tcgdex \
  --verify-runtime
```

The verifier reports aggregate worker heartbeat age/status, observed source
state, schedule/job outcome, checkpoint freshness, queue age bands, cleanup
freshness, and local backup-marker age where the marker is mounted. It never
prints source text, URLs, payloads, policy/gate identifiers, cursors,
credentials, or identity. `healthy` and first-run `warming_up` exit 0;
observed stale/failed evidence exits 1; missing/incompatible schema or
unavailable monitor access is explicitly `inconclusive` and exits 2. The
first-run grace window avoids failing before the first schedule; it does not
assert that a source is enabled. No migration or deployment is automatic.
For an already-running release, the same check is available directly as
`deploy/scripts/verify-runtime-release.sh` with an exact SHA and release start.

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
