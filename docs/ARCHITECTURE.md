# Architecture

## Status vocabulary

- **Implemented/static:** repository code, migrations, Compose, scripts, tests, and fixture adapters that can be inspected locally.
- **Fixture/demo:** synthetic labelled data (`DATA_MODE=demo`) and deterministic AI (`AI_PROVIDER=fixture`); no external observation is implied.
- **Account-bound:** Supabase, Vercel, VPS, OpenCLI artifact, social login, API keys, DNS, email, and provider billing that require the owner.
- **Deployed/live:** only true after an operator completes and records the account-bound verification. This repository alone is not deployed.

## Fixed research scope

The MVP is limited to Australia, English-language evidence, physical Pokémon TCG openings, and exactly these sealed product types: `booster_box`, `etb`, and `booster_bundle`. Other countries, languages, games, digital products, singles, loose-pack predictions, and commercial features are out of scope.

## Fixed responsibilities

| Platform | Responsibility | Explicitly not its responsibility |
| --- | --- | --- |
| Vercel Hobby | Build/serve `apps/web`; render the public dashboard and protected admin UI; call only the public Supabase contract | Durable jobs, collectors, Chromium/OpenCLI, aggregation, backups, DB/service-role secrets |
| Supabase Free | PostgreSQL/Auth, private ingest/catalog/analytics data, durable jobs, RLS, and explicitly granted public-safe views/RPCs | Scraping, browser profiles/cookies, or long-running workers |
| Existing VPS | All six Compose services, collection, AI validation, aggregation, scheduling/watchdog, headed browser/noVNC, cleanup, and backups | Public web hosting or public browser-control ports |
| Operator computer | Temporary SSH tunnel for manual login/CAPTCHA/2FA only | Everyday scheduled processing |

```text
Public browser
  -> Vercel Next.js (public-safe DTOs only)
     -> Supabase public API surface / RLS

VPS Docker Compose
  scheduler -> PostgreSQL jobs
  collector -> allowlisted official/public sources -> private ingest records
  auth-browser -> pinned CLI -> loopback daemon -> Browser Bridge -> headed Chromium
  ai-worker -> deterministic checks -> extract -> validate -> optional tie-break
  aggregator -> eligible openings -> baselines/intervals/signals -> public summaries
  watchdog -> heartbeats, budget/free-tier/backup freshness alerts
```

The deployment artifacts define `collector`, `ai-worker`, `aggregator`, `scheduler`, and `watchdog` as roles of one worker image with role-specific commands and least-privilege environment variables. The first live composition is deliberately single-process (`WORKER_MAX_CONCURRENCY=1`): `scheduler` can enqueue only the implemented cleanup job and `watchdog` can claim only that cleanup job. `collector`, `ai-worker`, and `aggregator` still fail closed with exit code 78 because they have no registered live handlers. This partial composition must not be described as an operational live collection pipeline. `auth-browser` has its own Chromium/noVNC image and sensitive persistent profile volume.

## PostgreSQL queue; no Redis in the free MVP

`ingest.jobs` is the durable queue contract: idempotent `(job_type, dedupe_key)`, bounded attempts, finite leases, lease-expiry recovery, and terminal states. The forward fencing protocol increments `lease_generation` on every claim; heartbeat, pause, fail, and completion must match the exact owner and generation while the database-clock lease is live. Claiming uses `FOR UPDATE SKIP LOCKED`, and the only wired live effect uses `finalize_cleanup_job` to lock and validate the lease, prune bounded ephemera, and complete the job in one transaction. Future persistent handlers require their own typed transactional finalizer, while external calls additionally need durable idempotency. PostgreSQL is already required and is adequate for expected low concurrency. Omitting Redis removes another credentialed, patched, monitored, backed-up stateful service. Add a broker only after measured latency/throughput or lock pressure proves this design insufficient. These migration/code contracts do not prove that the fencing migration or a live worker has run in a hosted environment.

## Data flow

1. The scheduler creates idempotent jobs; workers lease with bounded attempts.
2. A collector resolves an exact source policy. Unknown or disabled domains fail closed.
3. Metadata/excerpts are normalized and deduplicated; third-party video is not retained.
4. Deterministic bounds and catalog checks precede any AI call.
5. Independent extraction and validation must agree; one escalation can break a tie. Remaining conflict or low confidence is rejected.
6. Only accepted, complete, nonduplicate tier A/B openings explicitly marked statistics-eligible contribute denominators.
7. Aggregation produces public-safe summaries; private URLs, payloads, prompts, author hashes, sessions, and worker state stay outside the browser surface.

## Trust and network boundaries

- Browser code receives only publishable Supabase values; service-role and DB credentials are server/VPS only.
- Private `catalog`, `ingest`, and `analytics` schemas are not browser APIs. Public grants/views are explicit and read-only.
- Compose has an internal-only network plus a non-published bridge needed for outbound Internet/Supabase. No service binds a public host interface.
- Host loopback `6080` is the sole published browser-support port. CDP, raw VNC, OpenCLI daemon, PostgreSQL, and Docker socket are not published/mounted.
- Browser profiles/cookies live only in a mode-`0700` VPS volume and are account credentials, not project data.

## Failure behavior

Missing live configuration yields unavailable/failure, never silent demo substitution. A collector error leaves the job retryable/dead-lettered; it does not fabricate an opening. AI budget exhaustion pauses AI work. Health failure prevents the deploy success marker. Database migrations and external deployments remain explicit operator actions.
