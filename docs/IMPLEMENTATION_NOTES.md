# Implementation notes

Last audited: **2026-08-25 UTC**

This file is the canonical record of what was actually exercised in the implementation environment. A repository artifact, rendered configuration, fixture run, or generated workflow is not evidence of a live deployment.

## Status vocabulary

- **Verified:** the stated command or runtime path was executed successfully in this environment.
- **Fixture/demo verified:** deterministic synthetic inputs exercised the contract without representing real observations or external service success.
- **Static verified:** syntax, schema, policy, or configuration rendering passed, but the corresponding service was not started.
- **Blocked/unverified:** the environment lacked the daemon, browser, credentials, account access, remote, or artifact needed for the real path.
- **Release blocker:** implemented components exist, but a required end-to-end production path is not wired or proven.

## Repository and environment state

- The existing working tree was preserved. Git is on `feat/free-mvp`, has **zero commits**, and has **no remotes**.
- No GitHub, Vercel, hosted Supabase, VPS, DNS, browser-login, or OpenCLI release access was available.
- Observed toolchain: Node.js 26.5.1, pnpm 11.23.0, Python 3.13.5, uv 0.11.6, Docker client 26.1.5, and Docker Compose v5.5.0.
- The Docker client cannot connect to `/var/run/docker.sock`; no local Chromium/Chrome executable is installed.
- `gh`, standalone Vercel CLI, and standalone Supabase CLI are unavailable in the current shell. The pinned Supabase CLI can be invoked through `npx` when Docker/account access is available.
- A local `next start` test process remains reachable only at `127.0.0.1:3000`; it was not terminated because explicit cleanup authorization was not received. Local probes found 6080, 5900, 19825, and 9222 closed.

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
- Web: 91 tests passed across 24 files;
- Next.js 16.3.2 production build completed and emitted the expected public and protected App Router routes.

A production `next start` smoke run then verified:

- HTTP 200 for `/`, `/sets`, `/regions`, `/retailers`, `/batches`, `/methodology`, `/sources`, and `/status`;
- `/admin` failed closed with a 307 redirect to `/admin/login` when Supabase was unconfigured;
- CSP, `X-Frame-Options: DENY`, and `X-Content-Type-Options: nosniff` were present;
- the fixed Pokecrack tagline/footer disclaimer rendered;
- the batch listing rendered both the general observation disclaimer and the exact batch-level disclaimer.

Production Web environment parsing now rejects URL credentials, query strings, and fragments in the site/Supabase base URLs, and requires HTTPS for non-loopback production endpoints.

### Worker

The final worker gate completed successfully:

```bash
uv run ruff check pokecrack_worker tests
uv run ruff format --check pokecrack_worker tests
uv run mypy pokecrack_worker
uv run pytest -q
```

Observed result: **229 tests plus 2 subtests passed**. This includes deny-by-default and HTTPS-only source-policy authorization, URL redaction, collector/import fixtures, exact AI schemas, async provider surface, bounded AI and YouTube responses, atomic concurrent budget reservations with trusted start-period accounting across UTC day/month rollover, a mandatory shared settings-matched ledger and finite output-token cap for live AI providers, one paid-capable dispatch per reservation, conservative reservation commitment when a transport or response fails, strict rejection of missing/zero network usage, independently observed validator facts including rarity plus deterministic extractor/catalog rarity agreement, strict rejection of legacy/coercible payloads and non-finite schema numbers, complete statistics-field checks, disagreement rejection, deduplication, signal boundaries and complete public inference withholding below 30 packs or three independent sources, automatic queue retry backoff, canonical PostgreSQL claim semantics, expired-lease mutation rejection using one database clock for ownership and transition timestamps, aggregation eligibility/withholding logic, static Scrapling transport-level DNS pinning and bounded responses, disabled static redirects, dynamic-browser same-origin/private-address route blocking, service-worker blocking, pre-navigation WebSocket closure, fail-closed direct guard installation, one-attempt dynamic fetching, a default AI transport regression proving HTTP redirects are not followed with the authorization-bearing request, and regressions preventing fixture-only CLI commands from claiming real mutations.

The optional Scrapling dependency is locked as `scrapling[fetchers]`; the installed fetcher surface was imported successfully. Static transport uses the pinned curl wrappers, while dynamic collection uses the extra's Playwright dependency through a project-owned one-attempt wrapper because Scrapling 0.4.15 swallows `page_setup` exceptions before navigation.

### Auth browser

The final auth-browser gate completed successfully:

```bash
uv run ruff check src tests
uv run ruff format --check src tests
uv run mypy src/pokecrack_browser
uv run pytest -q
```

Observed result: **66 tests passed**. Fixture/dry-run paths verified bounded OpenCLI output handling, process-group cleanup when a timed-out adapter leader exits before a pipe-owning descendant, credential-safe dry-run argv rendering, structured and free-text redaction of common session identifiers (including quoted JSON `session_id`, `sid`, and `auth`, plus nested and captured-text camelCase keys such as `sessionData`/`sessionID`), exact per-adapter HTTPS output-host allowlists, stable canonical fingerprints, URL redaction, boot-scoped process identity checks that prevent PID-reuse signaling, profile/runtime path checks, and extension/path contracts. No real Chromium session, noVNC login, or authenticated platform command was run.

### Database contracts

Verified:

- 26 static migration/type contract tests passed;
- all 12 migration, seed, and SQL-test files plus the four PostgreSQL lease-mutation statements parsed successfully with `pglast` 8.4;
- a fresh standalone PostgreSQL 17 cluster was initialized with explicit `anon`, `authenticated`, and `service_role` roles plus a minimal `auth.jwt()` test shim; all 7 current migrations and the current seed committed successfully;
- all 281 pgTAP assertions passed: 125 schema/queue, 54 analytics, 64 public/security/Admin, and 38 seed assertions;
- this runtime pass caught and closed invalid seeded public metric deltas and four pgTAP index assertions that had selected the wrong overload.

The audit cluster was **not** a hosted Supabase stack. Supabase Auth, PostgREST, Realtime, hosted role behavior, and provider configuration remain unverified.

### Deployment artifacts

Verified:

- 25 deployment/backup/rollback/OpenCLI installer, runtime-contract, and CI security-policy unit tests passed;
- `bash -n` passed for deployment and auth-browser shell entrypoints;
- ShellCheck passed via `shellcheck-py`;
- `docker compose -f deploy/compose.prod.yml config --quiet` passed with a synthetic exact SHA and test extension path;
- only loopback noVNC port 6080 is published by the rendered Compose contract;
- OpenCLI uses the canonical `/opt/pokecrack/opencli-extension/current` path, a read-only host bind, and no automatic host-path creation;
- the noVNC secret target is explicitly uid/gid 10001 with mode 0400;
- GitHub Actions use full commit SHA pins.

These are static/unit results, not image-build or Compose-runtime evidence.

### Repository and security checks

Verified after the dependency and transport changes:

- repository guard: `{"ok": true, "findings": []}`;
- repository guard tests: 7 passed;
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

## Release blocker: production worker role wiring

The worker contains tested queue, PostgreSQL claim, heartbeat, collector, validation, aggregation, and scheduler components, but the current production CLI entrypoints do not yet connect them into a complete persistent service:

- in `DATA_MODE=demo`, `pokecrack-worker worker --forever` and the other service commands expose bounded fixture/reporting behavior rather than constructing the PostgreSQL repository, handlers, heartbeat loop, and real job processing pipeline;
- in `DATA_MODE=live`, every fixture-only CLI surface now fails closed with exit code 78 and `deploy/worker-service-entrypoint.sh` also exits 78 before looping, so an unwired live role can no longer report false health;
- `scheduler`, `aggregate all`, collectors/imports, catalog sync, retry/cleanup, and fixture telemetry still require real persistence handlers before unattended live operation is possible.

Accordingly, the repository is **not production-ready for unattended VPS collection**. This gap must be closed with end-to-end tests against an isolated PostgreSQL/Supabase-compatible database before a deployment can be accepted.

## Restricted Admin mutation status

The missing-RPC blocker was closed locally by migration `20260825000600_admin_control.sql`:

- Web authentication requires a real Supabase user, a stable user UUID, `app_metadata.pokecrack_admin=true`, and the server-side `ADMIN_EMAILS` allowlist; there is no demo bypass;
- the Web kill switch defaults off and creates a non-persistent service client only from the Vercel-only `SUPABASE_SERVICE_ROLE_KEY`; that name is never browser-public;
- the RPC fixes its `search_path`, denies `public`, `anon`, and `authenticated`, grants only `service_role`, validates the explicit audited actor and action/target/URL inputs, checks source policy for URL enqueue, and writes `ingest.admin_audit_log`;
- the fresh PostgreSQL 17 audit run executed the current migration, seed, public/RLS/RPC/Admin pgTAP suite, including direct authenticated denial, authorized service-role mutations, audit persistence, and record-exclusion invalidation contracts;
- `record.exclude` now marks linked openings excluded and non-statistical, removes source-linked batch sightings, invalidates same-mode private/public aggregates, and publishes an `unavailable` sentinel until a complete rebuild, rather than leaving stale public statistics;
- import actions remain deliberately unavailable;
- queue-producing controls such as browser refresh and service restart are not end-to-end operational until the production worker role wiring blocker below is closed.

This is local PostgreSQL evidence, not hosted Supabase/Auth/PostgREST evidence. The account owner must configure the Supabase app-metadata claim, `ADMIN_EMAILS`, and the Vercel server-only service-role key before enabling `ADMIN_CONTROL_RPC_ENABLED`; the service-role key must never be placed in a `NEXT_PUBLIC_` variable or the VPS worker environment.

## Blocked or unverified real paths

1. **Docker runtime:** daemon unavailable, so worker/auth-browser images, Compose startup, container healthchecks, resource limits, and network behavior were not exercised.
2. **Authenticated browser:** Chromium/Chrome unavailable; no noVNC, Browser Bridge, OpenCLI daemon, login, CAPTCHA/2FA, or persistent profile smoke was performed.
3. **Hosted Supabase:** no authenticated project; migrations, Auth, PostgREST, hosted RLS, and Admin login were not deployed or integrated against a real project.
4. **Vercel Hobby:** no account/project authorization; no deployment URL exists.
5. **GitHub private repository:** no commit, remote, `gh`, or authenticated push; CI workflows have not run on GitHub.
6. **VPS:** no host access; production deploy, firewall inspection, backup, restore, rollback, and monitoring were not exercised.
7. **External collectors and AI:** no real source/API credentials or paid model calls; terms/robots compatibility and model accuracy remain account/source-specific validation work.
8. **OpenCLI artifact:** no owner-approved, checksum-pinned compatible release artifact was available; the installer contract was tested only with synthetic archives.
9. **Independent review:** bounded current-tree reviews failed closed until reproduced HIGH/MEDIUM findings were addressed. Fixes now cover static Scrapling DNS rebinding through transport-level pinning, one-dispatch AI reservations, conservative accounting for failed/missing-usage responses, common session credential redaction, RPC demo/live isolation with unavailable-mode fail-closed behavior, service-role-only Admin controls with record-exclusion invalidation, canonical exhausted-job handling and active-lease mutation guards, rarity-aware extractor/validator disagreement, and fail-closed public statistics eligibility/withholding, including complete withholding below 30 packs or three independent sources, practical-uplift probability gates, and source/opening/pack count coherence across private/public SQL, shared types, and Web. A final independent current-tree review is running; release sign-off remains withheld until it returns complete with no reproducible HIGH/MEDIUM finding.

## Scope safeguards

No Stripe, subscription, advertising, affiliate, sponsorship, paid public API, paid alert, user signup, public upload, automated purchasing, CAPTCHA bypass, proxy pool, or deceptive pack/store prediction feature is implemented. Full third-party video retention is prohibited. Conflicting, low-confidence, or suspected-duplicate evidence is excluded from statistics.

## Deployment claim

**No real deployment was performed.** The correct current description is:

> The monorepo contains a locally tested Web/demo, current database migrations and seed that passed on a fresh standalone PostgreSQL 17 role harness with 281 pgTAP assertions, fixture-validated collectors/AI/browser boundaries, and statically validated deployment artifacts. The persistent production worker pipeline, full hosted Supabase behavior, account-bound integrations, container runtime, and real platform deployments remain unverified or incomplete.
