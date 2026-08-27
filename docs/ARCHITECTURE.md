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

The deployment artifacts define `collector`, `ai-worker`, `aggregator`, `scheduler`, and `watchdog` as roles of one worker image with role-specific commands and least-privilege environment variables. The live composition is deliberately single-process (`WORKER_MAX_CONCURRENCY=1`): `scheduler` can enqueue fenced cleanup and a daily TCGdex English sets-catalog job; `watchdog` can claim only cleanup; and `collector` can claim only that fixed TCGdex job. General URL/YouTube/browser collection, `ai-worker`, and `aggregator` still fail closed. The TCGdex path stores catalog metadata only—never cards, openings, hits, or pull-rate evidence—and is not an operational research pipeline until its migrations and worker are deployed and verified. `auth-browser` has its own Chromium/noVNC image and sensitive persistent profile volume.

## PostgreSQL queue; no Redis in the free MVP

`ingest.jobs` is the durable queue contract: bounded attempts, finite leases, lease-expiry recovery, and terminal states. Durable `schedule_slots` reserve a UTC slot even after its job becomes terminal; the TCGdex scheduler uses interval buckets to enqueue only the latest missed daily slot within 36 hours, independent of exact loop phase. The forward fencing protocol increments `lease_generation` on every claim; heartbeat, pause, fail, and completion must match the exact owner and generation while the database-clock lease is live. Claiming uses `FOR UPDATE SKIP LOCKED`. Cleanup uses `finalize_cleanup_job`; each TCGdex attempt uses a fenced, database-policy preflight before at most one GET, then `finalize_tcgdex_sets_job` atomically validates the current lease and kill switch, upserts bounded live catalog rows/checkpoint state, and completes the job. Future persistent handlers still require their own typed transactional finalizer and external idempotency. PostgreSQL is already required and is adequate for expected low concurrency. Omitting Redis removes another credentialed, patched, monitored, backed-up stateful service. Add a broker only after measured latency/throughput or lock pressure proves this design insufficient. These migration/code contracts do not prove that either new migration or a live worker has run in a hosted environment.

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
