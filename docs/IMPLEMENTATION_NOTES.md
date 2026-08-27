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

- The existing working tree was preserved. Git is on `codex/tcgdex-live-sync`, based on merged Personal-repository commit `138cb77`; `origin` is the owner-approved private repository `ncihxaonn/pokecrack`. GitHub Actions run `33032513290` on PR #2 passed all seven jobs for commit `004d523` on the current TCGdex tree.
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

Observed result on the current TCGdex tree: **325 tests and 2 subtests passed; 1 optional Scrapling runtime test was skipped**. In addition to the prior coverage, this includes same-worker-ID ABA reclamation, monotonic lease generations, rejection of stale generation heartbeat/fail/pause/complete operations, typed completion effects, fail-closed lease-loss handling, absolute-deadline/raw-byte HTTP transport tests, permanent/transient failure classification (including HTTP 408, 429 and 5xx retry handling), strict entity-tag validation, stale-checkpoint revision propagation, persistent request-gate deferral without consuming an attempt, and ambiguous-finalizer handling.

The optional Scrapling dependency is locked as `scrapling[fetchers]`; the installed fetcher surface was imported successfully. Static transport uses the pinned curl wrappers, while dynamic collection uses the extra's Playwright dependency through a project-owned one-attempt wrapper because Scrapling 0.4.15 swallows `page_setup` exceptions before navigation.

### Auth browser

The final auth-browser gate completed successfully:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src/pokecrack_browser
uv run pytest -q
```

Current local macOS result: **71 tests and 40 subtests passed; 1 Linux `/proc` lifecycle test was skipped**. Fixture/dry-run paths verified bounded OpenCLI output handling, process-group cleanup when a timed-out adapter leader exits before a pipe-owning descendant, credential-safe dry-run argv rendering, structured and free-text redaction of common session identifiers (including quoted JSON `session_id`, `sid`, and `auth`, plus nested and captured-text camelCase keys such as `sessionData`/`sessionID`), exact per-adapter HTTPS output-host allowlists, stable canonical fingerprints, URL redaction, boot-scoped process identity checks that prevent PID-reuse signaling, profile/runtime path checks, container-supervisor/manager ownership, and extension/path contracts. GitHub Actions run `33032513290` exercised the Linux suite, including the boot-scoped `/proc` lifecycle path. No real Chromium session, noVNC login, or authenticated platform command was run.

### Database contracts

Current evidence:

- 38 static migration/type contract tests passed on the current tree;
- 18 repository/migration-safety script tests passed, and the actual safety gate found 0 errors with the new forward migration while preserving the reviewed historical `DELETE` fingerprints;
- the current pgTAP files plan **478 assertions**: 132 schema/queue, 54 analytics, 79 public/security/Admin, 42 seed, 50 lease-fencing, and 121 TCGdex-pipeline assertions;
- GitHub Actions run `33032513290` on PR #2 started a clean local Supabase stack, replayed the full current migration tree, and passed all **478 pgTAP assertions** on commit `004d523`;
- local standalone PostgreSQL remains unavailable because the host has exhausted its global System V shared-memory slots (`could not create shared memory segment: No space left on device`).

The first seven migrations (`20260825000000` through `20260825000600`) are applied to the approved hosted Supabase project. Hosted PostgREST smoke checks verified empty public reads, private-schema rejection, anonymous write rejection, and Admin-RPC denial. Both `20260827000000_job_lease_fencing.sql` and `20260828000000_tcgdex_sets_pipeline.sql` remain unapplied. Hosted Auth still reports public signup enabled and the Admin allowlist/app-metadata setup remains incomplete.

### Deployment artifacts

Verified:

- 22 non-Docker deployment/backup/rollback/OpenCLI-installer and static Compose-policy tests passed;
- 18 repository/migration-safety script tests passed;
- `bash -n` passed for `deploy/*.sh` and `deploy/scripts/*.sh`;
- the deployment shell now uses portable BSD/GNU stat/hash handling, Bash 3.2-compatible lowercase conversion, and atomic `os.replace` replacement rather than GNU-only move flags;
- static contracts still require OpenCLI at `/opt/pokecrack/opencli-extension/current`, a read-only host bind, no automatic host-path creation, noVNC secret uid/gid 10001 with mode 0400, loopback-only noVNC publication, and full commit SHA GitHub Action pins.

Local execution still skipped exactly 6 Docker Compose render tests because Docker is unavailable on this Mac, and ShellCheck is unavailable locally. In GitHub Actions run `33032513290`, the deployment-contracts job passed the full deployment test suite and `docker compose config`, the worker and auth-browser images built successfully, and ShellCheck passed. No Compose startup or container-runtime smoke is claimed.

### Repository and security checks

Verified after the dependency and transport changes:

- repository guard: `{"ok": true, "findings": []}`;
- repository/migration-safety guard tests: 18 passed;
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
- in `DATA_MODE=live`, the composition enforces `WORKER_MAX_CONCURRENCY=1`; the scheduler registers fenced cleanup plus one daily TCGdex sets job, the watchdog claims only cleanup, and the collector claims only `catalog.tcgdex.sets.sync`;
- the TCGdex handler first validates an empty job payload and current database lease/policy, then acquires a persistent generation-fenced database request gate that serializes requests across workers and enforces the source delay. A busy gate defers the job to its database-provided retry time and refunds the claimed attempt. An acquired gate extends the lease for at least 45 seconds before one fixed conditional GET with redirects and environment proxies disabled, an absolute 30-second deadline, identity/raw response streaming, a 2 MiB cap and a 1,000-set cap; its typed finalizer uses checkpoint-revision compare-and-swap to atomically upsert live English set metadata/checkpoint state, complete the exact lease, and release only that lease's gate ownership;
- general URL/YouTube/browser collection, imports, AI-worker, aggregation, and every other schedule remain unwired or fail closed. The TCGdex path cannot create cards, openings, hits, public statistics, or pull-rate evidence.

The following are P0 release blockers, not optional polish:

1. **Lease fencing and atomic effects:** the current tree assigns a monotonic `lease_generation` on every claim, requires it on every lease mutation, disables the legacy claim and naked-cleanup protocols, and routes cleanup through `finalize_cleanup_job`. The TCGdex path adds a persistent generation-fenced pre-network policy/request gate, gate-aware heartbeat and failure RPCs, and its own typed `finalize_tcgdex_sets_job`; stale leases, stale gate owners, and a policy disabled during the GET perform no catalog effect. These migrations remain unhosted, and every future persistent handler still requires its own typed transactional finalizer; external AI effects additionally require durable idempotency or an outbox.
2. **End-to-end mode isolation:** live claiming and Admin controls exclude demo jobs, active-job deduplication includes `is_demo`, and the new TCGdex set identity/slug constraints are mode-scoped. The full source → extraction → opening → hit/batch relationship is still not protected by mode-scoped composite foreign keys and indexes; some URL/platform uniqueness constraints remain cross-mode.
3. **Collector persistence contract:** the bounded TCGdex sets exception has an exact source policy, DTO, checkpoint and atomic persistence contract. General source collection remains blocked: route vocabularies are not fully aligned, candidate `content_hash` may be absent while the database requires it, and general rate limits are process-local rather than shared and durable.
4. **AI idempotency and accounting:** reservations, run state, and budget coordination are still in memory. There is no persistent request-idempotency key and no single transaction that finalizes model usage, result persistence, and job state.
5. **Atomic aggregation publication:** aggregation is in memory and lacks mode-scoped staging/revision tables, an advisory lock, and atomic publish. That leaves a race with record exclusion and aggregate invalidation.
6. **Scheduler durability:** the new service-only `schedule_slots` reservation prevents a completed wired slot from being recreated, reconciles canonical schedule dedupe keys written by the previous scheduler, and TCGdex performs only the latest missed slot within a 36-hour window using interval buckets that do not depend on the worker loop landing on an exact wall-clock minute. This is locally implemented, not hosted operational evidence; additional schedules need the same bounded policy before they are wired.
7. **Operational state:** watchdogs do not maintain `current_job_id`; browser, host, and storage checkpoints lack a safe persistence channel; browser-refresh and service-restart control jobs have no live handler; and the current Admin retry branch accepts `failed` rows while the canonical runtime ends exhausted work as `dead`, so dead-letter recovery is not yet a closed operational path.

Accordingly, the repository is **not production-ready for unattended research collection**. The TCGdex sets path is a catalog-only exception and still requires the hosted migrations and an approved always-on worker before it is operational. General collector, AI, aggregator and control paths remain blocked.

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
- GitHub Actions run `33032513290` on PR #2 replayed the current migration tree on a clean local Supabase stack and passed all 478 pgTAP assertions, including the 50 fencing/finalizer and 121 TCGdex-pipeline assertions. Hosted read/denial RPC behavior was smoke-tested, while the fencing and TCGdex migrations remain pending on the hosted project.

This is local and GitHub CI implementation evidence, not hosted Supabase/Auth/PostgREST evidence. The account owner must configure the Supabase app-metadata claim, `ADMIN_EMAILS`, and the Vercel server-only service-role key before enabling `ADMIN_CONTROL_RPC_ENABLED`; the service-role key must never be placed in a `NEXT_PUBLIC_` variable or the VPS worker environment.

## Blocked or unverified real paths

1. **Docker runtime:** Docker/Compose is unavailable locally. GitHub CI rendered the production Compose contract and built both production images, but no Compose startup, container healthcheck, resource-limit, or network-behavior runtime was exercised.
2. **Authenticated browser:** the in-app browser exercised the local public/Admin-login Web UI, but no containerized Chromium, noVNC, Browser Bridge, OpenCLI daemon, external-platform login, CAPTCHA/2FA, or persistent-profile smoke was performed.
3. **Hosted Supabase:** the approved project has the first seven migrations and bounded API smoke evidence, but both the fencing migration and the new TCGdex sets-pipeline migration are pending; Auth signup/redirect policy, Admin identity claims, Realtime, and the full authenticated Admin flow remain unverified or incomplete.
4. **Vercel Hobby:** the approved project serves the public Demo-mode Web app at `https://pokecrack.vercel.app`; no live data path or Admin mutation surface is enabled.
5. **GitHub private repository:** `ncihxaonn/pokecrack` is private. Commit `138cb77` is the merged base of the current branch; GitHub Actions run `33032513290` passed all seven PR #2 jobs for commit `004d523` on the current TCGdex tree.
6. **VPS:** no host access; production deploy, firewall inspection, backup, restore, rollback, and monitoring were not exercised.
7. **External collectors and AI:** one bounded, read-only direct transport smoke against the free, no-key English TCGdex sets endpoint returned HTTP 200 with 218 sets, an ETag and a 64-character SHA-256 digest. It made no database write and is not an always-on worker run. No credentialed source or paid model call was made; terms/robots compatibility and model accuracy remain source-specific work.
8. **OpenCLI artifact:** no owner-approved, checksum-pinned compatible release artifact was available; the installer contract was tested only with synthetic archives.
9. **Independent review:** multiple read-only current-tree specialist reviews covered the worker/runtime path, Python-to-SQL contract, SQL pipeline, and complete change scope. Accepted findings were fixed for raw/identity response bounds, an absolute request deadline, finalizer ambiguity, HTTP 408/429/5xx retry classification, scheduler drift, exact readiness policy, configuration bounds, conditional-304 handling, control-character rejection, database-clock lease rechecks, exact SQL policy gating, stale-checkpoint revision compare-and-swap, safe numeric validation, persistent global request serialization/rate gating, and missing pgTAP cases. The final runtime and SQL audits found no remaining contract or gate defect after the HTTP 408 fix; their focused checks, the 325-test worker suite, and 38 static migration contracts passed. The structured external `/Users/nixon/.codex/skills/autoreview/scripts/autoreview --mode local` closeout was attempted after the patch froze, but did not start because the system approval boundary rejected transmission of the private uncommitted patch to an external Codex review service without specific owner authorization for that payload and destination. No clean external-review result is claimed, and no workaround was attempted.

## Scope safeguards

No Stripe, subscription, advertising, affiliate, sponsorship, paid public API, paid alert, user signup, public upload, automated purchasing, CAPTCHA bypass, proxy pool, or deceptive pack/store prediction feature is implemented. Full third-party video retention is prohibited. Conflicting, low-confidence, or suspected-duplicate evidence is excluded from statistics.

## Deployment claim

An owner-approved **Demo Web deployment** was performed, and the first seven database migrations were applied to an otherwise empty approved Supabase project. No VPS or unattended live collection deployment was performed. The correct current description is:

> The private monorepo and online Vercel site contain a tested Demo-mode Web application. The approved Supabase project has the first seven migrations and no seed/live observations. The current branch implements, but has not deployed, generation-fenced cleanup plus a catalog-only TCGdex English sets sync with durable scheduling and atomic persistence. The required hosted migrations and always-on worker are absent; general collector, AI-worker, aggregator, Admin mutation, authenticated browser, and VPS paths remain fail closed or unverified. This is not an unattended research collection deployment.
