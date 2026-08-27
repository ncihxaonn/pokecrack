# Architecture

## Status vocabulary

- **Implemented/static:** repository code, migrations, Compose, scripts, tests, and fixture adapters that can be inspected locally.
- **Fixture/demo:** synthetic labelled data (`DATA_MODE=demo`) and deterministic AI (`AI_PROVIDER=fixture`); no external observation is implied.
- **Account-bound:** Supabase, Vercel, VPS, OpenCLI artifact, social login, API keys, DNS, email, and provider billing that require the owner.
- **Deployed/live:** only true after an operator completes and records the account-bound verification. This repository alone is not deployed.

## Research and publication scope

The private discovery layer may collect bounded global catalog and activity metadata. That is coverage evidence, not pull-rate evidence. The public v1 statistical contract remains limited to Australia, English-language evidence, physical Pokémon TCG openings, and exactly these sealed product types: `booster_box`, `etb`, and `booster_bundle`. Other countries may be preserved as explicit private facts, but cannot enter public v1 aggregates. Other games, digital products, singles, loose-pack predictions, and commercial features remain out of scope.

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

The deployment artifacts define `collector`, `ai-worker`, `aggregator`, `scheduler`, and `watchdog` as roles of one worker image with role-specific commands and least-privilege environment variables. The live composition is deliberately single-process (`WORKER_MAX_CONCURRENCY=1`). Cleanup and the daily TCGdex English sets-catalog sync are fixed jobs. When the explicit YouTube collection flag is enabled, the scheduler enqueues one fenced job for each of five versioned global discovery queries on an exact six-hour schedule; any cadence drift fails startup, and the scheduler does not receive the API key. Only the collector receives the dedicated key and may claim those jobs. General URL and browser collection, `ai-worker`, and `aggregator` still fail closed. TCGdex rows are catalog-only. YouTube rows are tier-D/activity-only metadata. Neither path creates cards, openings, hits, denominators, aggregates, or pull-rate evidence. `auth-browser` has its own Chromium/noVNC image and sensitive persistent profile volume.

## PostgreSQL queue; no Redis in the free MVP

`ingest.jobs` is the durable queue contract: bounded attempts, finite leases, lease-expiry recovery, and terminal states. Durable `schedule_slots` reserve a UTC slot even after its job becomes terminal; schedulers use interval buckets rather than depending on an exact loop phase. The forward fencing protocol increments `lease_generation` on every claim; heartbeat, pause, fail, and completion must match the exact owner and generation while the database-clock lease is live. Claiming uses `FOR UPDATE SKIP LOCKED`.

Every persistent collector has its own transactional database boundary. Cleanup uses `finalize_cleanup_job`. TCGdex uses a fenced policy/request-gate preflight and `finalize_tcgdex_sets_job`. YouTube discovery uses `begin_youtube_discovery_job` before one bounded `search.list` call and `finalize_youtube_discovery_job` afterward. The finalizer rechecks the exact lease, generation, policy, request gate, result version, identities, and size bounds before atomically upserting the dedicated `UNLOGGED`, forced-RLS `ingest.youtube_discoveries` cache and completing the job. That cache has no path into generic source items, extraction, openings, analytics, Admin, or public relations. A stale lease, disabled kill switch, malformed response, or identity collision produces no partial persistence. Future persistent handlers still require their own typed finalizer and external idempotency. PostgreSQL is already required and is adequate for expected low concurrency. Omitting Redis removes another credentialed, patched, monitored, backed-up stateful service. Add a broker only after measured latency/throughput or lock pressure proves this design insufficient. Repository contracts are not evidence that a migration or worker revision has been deployed.

## Data flow

1. The scheduler creates idempotent jobs; workers lease with bounded attempts.
2. A collector resolves an exact source policy. Unknown or disabled domains fail closed.
3. Metadata/excerpts are normalized and deduplicated according to each source's exact contract. YouTube retains only the video identity, canonical URL, title, publication timestamp, and lifecycle fields; video, audio, captions, thumbnails, descriptions, query/rank associations, channel data, and derived classifications are not retained.
4. Deterministic bounds and catalog checks precede any AI call.
5. Independent extraction and validation must agree; one escalation can break a tie. Remaining conflict or low confidence is rejected.
6. Only accepted, complete, nonduplicate tier A/B openings with a verified positive pack denominator and an eligible geography contribute to statistics.
7. Public v1 aggregation publishes only the reviewed Australia/English statistical slice. Global activity metadata stays private.
8. Aggregation produces public-safe summaries; private URLs, payloads, prompts, author hashes, sessions, and worker state stay outside the browser surface.

## Trust and network boundaries

- Browser code receives only publishable Supabase values; service-role and DB credentials are server/VPS only.
- Private `catalog`, `ingest`, and `analytics` schemas are not browser APIs. Public grants/views are explicit and read-only.
- Compose has an internal-only network plus a non-published bridge needed for outbound Internet/Supabase. No service binds a public host interface.
- Host loopback `6080` is the sole published browser-support port. CDP, raw VNC, OpenCLI daemon, PostgreSQL, and Docker socket are not published/mounted.
- Browser profiles/cookies live only in a mode-`0700` VPS volume and are account credentials, not project data.
- The logical database backup stream strips all data rows from the dedicated
  retention-bounded YouTube cache before compression; a malformed or ambiguous
  dump fails without advancing the success marker. The sanitizer also uniquely
  verifies the cache's `CREATE UNLOGGED TABLE` header inside that same dump.
  Provider-managed snapshot retention must be revalidated separately before the
  feature is enabled.

## Failure behavior

Missing live configuration yields unavailable/failure, never silent demo substitution. A collector error leaves the job retryable/dead-lettered; it does not fabricate an opening. AI budget exhaustion pauses AI work. Health failure prevents the deploy success marker. Database migrations and external deployments remain explicit operator actions.
