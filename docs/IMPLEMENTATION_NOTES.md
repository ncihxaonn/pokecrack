# Implementation notes

Last audited: **2026-08-27 UTC**

This file is the canonical record of what was actually exercised in the implementation environment. A repository artifact, rendered configuration, fixture run, or generated workflow is not evidence of a live deployment.

## Status vocabulary

- **Verified:** the stated command or runtime path was executed successfully in this environment.
- **Fixture/demo verified:** deterministic synthetic inputs exercised the contract without representing real observations or external service success.
- **Static verified:** syntax, schema, policy, or configuration rendering passed, but the corresponding service was not started.
- **Blocked/unverified:** the environment lacked the daemon, browser, credentials, account access, remote, or artifact needed for the real path.
- **Release blocker:** implemented components exist, but a required end-to-end production path is not wired or proven.

## Repository and environment state

- The existing working tree was preserved. Git is on `feat/free-mvp`; `origin` is the owner-approved private Personal repository `ncihxaonn/pokecrack`. Commit `86ddb66` is pushed to `origin/feat/free-mvp`, and GitHub CI run `33023105390` passed all seven jobs on that exact commit.
- The owner approved the exact Personal targets now linked to this project: GitHub `ncihxaonn/pokecrack`, Supabase `Pokecrack` (`wohnphsxlquhhknuthrj`), and the Vercel `pokecrack` project. No VPS target has been approved or contacted.
- The project-scoped credential helper verified the Personal Maton and Supabase credentials as available with system-level execution. Maton reports one Active Supabase connection for the same project ref. Credential values remain outside the repository.
- Observed toolchain: Node.js 22.18.0, pnpm 11.23.0, system Python 3.14.6, uv 0.8.15, and worker uv Python 3.13.7.
- No Docker CLI or Docker Compose CLI is installed locally. The fixed Supabase CLI can run through `npx`, but the current Personal access token receives HTTP 403 for management endpoints that require additional organization privileges.
- The local `next start` process used for browser QA was stopped after verification. An owner-approved Vercel **Demo-mode** deployment is online at `https://pokecrack.vercel.app`; it is not evidence of a live collection pipeline.

## Verified quality gates

### JavaScript, shared packages, and Web

The following completed successfully after the final Web hardening changes:

```bash
pnpm run lint
pnpm run typecheck
pnpm test
pnpm run build
```

Observed results:

- shared config: 9 tests passed;
- shared types: 114 tests passed across 10 files;
- Web: 105 tests passed across 28 files;
- Next.js 16.3.2 production build completed on the final Web tree, generated 13 static pages, and emitted the expected public and protected App Router routes.

A production `next start` smoke run then verified:

- HTTP 200 for `/`, `/sets`, `/regions`, `/retailers`, `/batches`, `/methodology`, `/sources`, and `/status`, plus desktop and mobile layout checks for the key public and Admin-login views;
- `/admin` failed closed with a 307 redirect to `/admin/login` when Supabase was unconfigured;
- CSP, `X-Frame-Options: DENY`, and `X-Content-Type-Options: nosniff` were present;
- the fixed Pokecrack tagline/footer disclaimer rendered;
- the batch listing and detail rendered the general observation disclaimer and the exact batch-level disclaimer, with the detail disclaimer appearing before the main heading;
- no body-level horizontal overflow or browser-console problem was observed in the tested views.

Production Web environment parsing now rejects URL credentials, query strings, and fragments in the site/Supabase base URLs, and requires HTTPS for non-loopback production endpoints.

### Worker

The final worker gate completed successfully:

```bash
uv run ruff check pokecrack_worker tests
uv run ruff format --check pokecrack_worker tests
uv run mypy pokecrack_worker
uv run pytest -q
```

Observed result on the current fencing tree: **271 tests and 2 subtests passed; 1 optional Scrapling runtime test was skipped**. In addition to the prior coverage, this includes same-worker-ID ABA reclamation, monotonic lease generations, rejection of stale generation heartbeat/fail/pause/complete operations, typed completion effects, and fail-closed lease-loss handling that never records a failure through a stale lease.

The optional Scrapling dependency is locked as `scrapling[fetchers]`; the installed fetcher surface was imported successfully. Static transport uses the pinned curl wrappers, while dynamic collection uses the extra's Playwright dependency through a project-owned one-attempt wrapper because Scrapling 0.4.15 swallows `page_setup` exceptions before navigation.

### Auth browser

The final auth-browser gate completed successfully:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src/pokecrack_browser
uv run pytest -q
```

Current local macOS result: **71 tests and 40 subtests passed; 1 Linux `/proc` lifecycle test was skipped**. Fixture/dry-run paths verified bounded OpenCLI output handling, process-group cleanup when a timed-out adapter leader exits before a pipe-owning descendant, credential-safe dry-run argv rendering, structured and free-text redaction of common session identifiers (including quoted JSON `session_id`, `sid`, and `auth`, plus nested and captured-text camelCase keys such as `sessionData`/`sessionID`), exact per-adapter HTTPS output-host allowlists, stable canonical fingerprints, URL redaction, boot-scoped process identity checks that prevent PID-reuse signaling, profile/runtime path checks, container-supervisor/manager ownership, and extension/path contracts. Linux CI remains responsible for exercising the skipped boot-scoped lifecycle path. No real Chromium session, noVNC login, or authenticated platform command was run.

### Database contracts

Current evidence:

- 33 static migration/type contract tests passed on the current tree;
- 17 repository/migration-safety tests passed, and the actual safety gate found 0 errors with the new forward migration while preserving the 16 reviewed historical `DELETE` fingerprints;
- the current pgTAP files plan **353 assertions**: 128 schema/queue, 54 analytics, 79 public/security/Admin, 42 seed, and 50 lease-fencing assertions;
- GitHub CI run `33023105390` at `86ddb66` successfully started a clean local Supabase stack, applied the complete migration chain, and passed all **353 pgTAP assertions**, including the 50 new lease-fencing/finalizer assertions;
- local standalone PostgreSQL remains unavailable because the host has exhausted its global System V shared-memory slots (`could not create shared memory segment: No space left on device`).

The first seven migrations (`20260825000000` through `20260825000600`) are applied to the approved hosted Supabase project. Hosted PostgREST smoke checks verified empty public reads, private-schema rejection, anonymous write rejection, and Admin-RPC denial. The new `20260827000000_job_lease_fencing.sql` migration is not yet applied. Hosted Auth still reports public signup enabled and the Admin allowlist/app-metadata setup remains incomplete.

### Deployment artifacts

Verified:

- 17 non-Docker deployment/backup/rollback/OpenCLI-installer tests and 3 non-rendering Compose policy test methods passed (**20 total**; the worker-role method also exercised 5 role subtests);
- 17 repository/migration-safety script tests passed;
- `bash -n` passed for `deploy/*.sh` and `deploy/scripts/*.sh`;
- the deployment shell now uses portable BSD/GNU stat/hash handling, Bash 3.2-compatible lowercase conversion, and atomic `os.replace` replacement rather than GNU-only move flags;
- static contracts still require OpenCLI at `/opt/pokecrack/opencli-extension/current`, a read-only host bind, no automatic host-path creation, noVNC secret uid/gid 10001 with mode 0400, loopback-only noVNC publication, and full commit SHA GitHub Action pins.

Exactly 6 Docker Compose render tests could not run because no Docker CLI is installed. ShellCheck is also unavailable in the current environment. Therefore no current `docker compose config`, image build, Compose startup, or ShellCheck pass is claimed.

### Repository and security checks

Verified after the dependency and transport changes:

- repository guard: `{"ok": true, "findings": []}`;
- repository/migration-safety guard tests: 17 passed;
- `pnpm audit --prod --audit-level high`: no known vulnerabilities found;
- worker frozen production dependency export audited with pinned `pip-audit` 2.10.1: no known vulnerabilities found;
- auth-browser frozen production dependency export audited with pinned `pip-audit` 2.10.1: no known vulnerabilities found;
- the direct development dependency was raised to pytest 9.1.1 after `PYSEC-2026-1845` was detected in 8.4.2; both Python suites passed after the lock refresh;
- Bandit medium/high scans for worker and auth-browser passed;
- no credential value was intentionally written to the repository or this record.

Dependency audit results are a dated snapshot, not a permanent security guarantee.

## Fixture/demo-only verification

The following successful paths used clearly synthetic or deterministic data and must not be described as live collection:

- public Dashboard demo snapshot and demo empty states;
- CSV, JSONL, and OpenCLI imports using `openings.example.csv`, `sources.example.jsonl`, and `opencli.example.json`;
- fixture extractor, independent validator, escalation, rejection, activity-only, and budget paths;
- example.com static and reserved-domain dynamic collector contracts;
- TCGdex and YouTube metadata mappings with fixture responses;
- auth-browser/OpenCLI adapter output, profile, and auth-state fixtures;
- scheduler, queue, aggregation, and signal calculations exercised through unit/in-memory fixtures.

No fixture output is evidence about a real Pokémon product, set, batch, region, retailer, platform post, or pull rate.

## Release blocker: persistent live pipeline and fencing

The worker contains tested queue, PostgreSQL claim, heartbeat, collector, validation, aggregation, and scheduler components, but they are deliberately **fail closed** rather than connected into an unsafe live pipeline:

- in `DATA_MODE=demo`, `pokecrack-worker worker --forever` and the other service commands expose bounded fixture/reporting behavior rather than constructing a live persistence pipeline;
- in `DATA_MODE=live`, the composition registers only the scheduler cleanup schedule, watchdog cleanup handler, and live database heartbeat, with `WORKER_MAX_CONCURRENCY=1` enforced;
- collector, AI-worker, and aggregator roles still exit 78 and cannot report healthy. Imports, catalog sync, aggregation, and other schedules remain unwired.

The following are P0 release blockers, not optional polish:

1. **Lease fencing and atomic effects:** the current tree now assigns a monotonic `lease_generation` on every claim, requires it on every lease mutation, disables the legacy claim and naked-cleanup protocols, and routes the only live handler (`maintenance.cleanup`) through a typed `finalize_cleanup_job` transaction that performs cleanup and completion together. The migration and all 50 new pgTAP assertions passed in clean CI; this sub-blocker remains open until the approved hosted project is migrated. Every future persistent handler still requires its own typed transactional finalizer; external AI/API effects additionally require durable idempotency or an outbox.
2. **End-to-end mode isolation:** live claiming and Admin controls now exclude demo jobs, and active-job deduplication includes `is_demo`; however, the full source → extraction → opening → hit/batch relationship is not protected by mode-scoped composite foreign keys and indexes. Some URL/platform uniqueness constraints still cross modes.
3. **Collector persistence contract:** source-policy route values and Python DTO values are not fully aligned, candidate `content_hash` may be absent while the database requires it, and rate limits are process-local rather than shared and durable.
4. **AI idempotency and accounting:** reservations, run state, and budget coordination are still in memory. There is no persistent request-idempotency key and no single transaction that finalizes model usage, result persistence, and job state.
5. **Atomic aggregation publication:** aggregation is in memory and lacks mode-scoped staging/revision tables, an advisory lock, and atomic publish. That leaves a race with record exclusion and aggregate invalidation.
6. **Scheduler durability:** active-only deduplication lets a completed slot be enqueued again, and there is no durable watermark or bounded downtime catch-up policy.
7. **Operational state:** watchdogs do not maintain `current_job_id`; browser, host, and storage checkpoints lack a safe persistence channel; browser-refresh and service-restart control jobs have no live handler; and the current Admin retry branch accepts `failed` rows while the canonical runtime ends exhausted work as `dead`, so dead-letter recovery is not yet a closed operational path.

Accordingly, the repository is **not production-ready for unattended VPS collection**. These blockers require transactional design changes and end-to-end tests against an isolated PostgreSQL/Supabase-compatible database before any live collector, AI, aggregator, or control role may be enabled.

## Restricted Admin mutation status

The missing-RPC blocker was closed locally by migration `20260825000600_admin_control.sql`:

- Web authentication requires a real Supabase user, a stable user UUID, `app_metadata.pokecrack_admin=true`, and the server-side `ADMIN_EMAILS` allowlist; there is no demo bypass;
- the Web kill switch defaults off and creates a non-persistent service client only from the Vercel-only `SUPABASE_SERVICE_ROLE_KEY`; that name is never browser-public;
- the RPC fixes its `search_path`, denies `public`, `anon`, and `authenticated`, grants only `service_role`, validates the explicit audited actor and action/target/URL inputs, checks source policy for URL enqueue, and writes `ingest.admin_audit_log`;
- source enqueue, job retry/cancel, source disable, record exclusion, browser refresh, and service restart refuse demo targets; queue-producing actions explicitly create live jobs, and audit rows retain the affected mode;
- `record.exclude` now marks linked openings excluded and non-statistical, removes source-linked batch sightings, invalidates same-mode private/public aggregates, and publishes an `unavailable` sentinel until a complete rebuild, rather than leaving stale public statistics;
- import actions remain deliberately unavailable;
- the current Admin views remain read-only and keep mutation buttons disabled; the authenticated server-action/RPC boundary is implemented for later activation, but is not presented as an operational control surface on this tree;
- queue-producing controls such as browser refresh and service restart are not end-to-end operational until the live-handler and fencing blockers above are closed;
- the complete 353-assertion database tree, including the 50 fencing/finalizer assertions, passed in GitHub CI run `33023105390`; hosted read/denial RPC behavior was smoke-tested, while the new fencing migration remains pending on the hosted project.

This is static/local implementation evidence, not hosted Supabase/Auth/PostgREST evidence. The account owner must configure the Supabase app-metadata claim, `ADMIN_EMAILS`, and the Vercel server-only service-role key before enabling `ADMIN_CONTROL_RPC_ENABLED`; the service-role key must never be placed in a `NEXT_PUBLIC_` variable or the VPS worker environment.

## Blocked or unverified real paths

1. **Docker runtime:** no Docker/Compose CLI is installed, so Compose rendering through the CLI, worker/auth-browser images, startup, container healthchecks, resource limits, and network behavior were not exercised.
2. **Authenticated browser:** the in-app browser exercised the local public/Admin-login Web UI, but no containerized Chromium, noVNC, Browser Bridge, OpenCLI daemon, external-platform login, CAPTCHA/2FA, or persistent-profile smoke was performed.
3. **Hosted Supabase:** the approved project has the first seven migrations and bounded API smoke evidence, but the fencing migration is pending; Auth signup/redirect policy, Admin identity claims, Realtime, and the full authenticated Admin flow remain unverified or incomplete.
4. **Vercel Hobby:** the approved project serves the public Demo-mode Web app at `https://pokecrack.vercel.app`; no live data path or Admin mutation surface is enabled.
5. **GitHub private repository:** `ncihxaonn/pokecrack` is private; commit `86ddb66` is pushed on `feat/free-mvp`, and all seven jobs in GitHub CI run `33023105390` are green.
6. **VPS:** no host access; production deploy, firewall inspection, backup, restore, rollback, and monitoring were not exercised.
7. **External collectors and AI:** no real source/API credentials or paid model calls; terms/robots compatibility and model accuracy remain account/source-specific validation work.
8. **OpenCLI artifact:** no owner-approved, checksum-pinned compatible release artifact was available; the installer contract was tested only with synthetic archives.
9. **Independent review:** bounded local current-tree reviews failed closed until reproduced HIGH/MEDIUM findings were addressed. Fixes now cover static Scrapling DNS rebinding through transport-level pinning, one-dispatch AI reservations, conservative accounting for failed/missing-usage responses, common session credential redaction, RPC demo/live isolation with unavailable-mode fail-closed behavior, service-role-only Admin controls with same-mode record-exclusion invalidation, canonical exhausted-job handling and active-lease mutation guards, unready-role heartbeat suppression, rarity-aware extractor/validator disagreement, and fail-closed public statistics eligibility/withholding, including complete withholding below 30 packs or three independent sources, practical-uplift probability gates, and source/opening/pack count coherence across private/public SQL, shared types, and Web. The structured external `autoreview --mode local` closeout was attempted but did not start because the system approval boundary rejected transmission of the private uncommitted patch to an external review process. No clean external-review result is claimed; a future run requires the owner to explicitly authorize that code transmission.

## Scope safeguards

No Stripe, subscription, advertising, affiliate, sponsorship, paid public API, paid alert, user signup, public upload, automated purchasing, CAPTCHA bypass, proxy pool, or deceptive pack/store prediction feature is implemented. Full third-party video retention is prohibited. Conflicting, low-confidence, or suspected-duplicate evidence is excluded from statistics.

## Deployment claim

An owner-approved **Demo Web deployment** was performed, and the first seven database migrations were applied to an otherwise empty approved Supabase project. No VPS or unattended live collection deployment was performed. The correct current description is:

> The private monorepo and online Vercel site contain a tested Demo-mode Web application. The approved Supabase project has the first seven migrations and no seed/live observations. The generation-fenced queue mutations and atomic cleanup finalizer passed clean CI and are pending only the controlled hosted migration. Collector, AI-worker, aggregator, Admin mutation, authenticated browser, and VPS live paths remain fail closed or unverified, so this is not an unattended production collection deployment.
