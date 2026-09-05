# Implementation notes

Last audited: **2026-08-30 UTC**

This file records what was actually exercised. Repository code, a rendered
configuration, a fixture response, or a successful migration compile is not by
itself evidence of a live collection run.

## 2026-09-04 Pokesup M5 rollout preparation

- The reviewed change prepares an exact live static-HTML source for
  `https://pokesup.com/blog/unboxing-m5/`, with
  `policy_review_date=2026-09-04`. Robots allowed the reviewed route. No
  independent terms page was found, and the page footer states
  `© ポケサプ All Rights Reserved`.
- The copyright boundary permits only non-copyrightable minimum facts and short
  pack labels needed to verify completeness. The collector must not copy article
  body prose or images, fetch media, or retain raw HTML. The product version is
  `ja/M5/アビスアイ/booster_box`; the official
  [Japanese M5 product page](https://www.pokemon-card.com/ex/m5/) proves only
  that product identity, not Pokesup's publisher location, an author address,
  or the opening location.
- This is a coverage-only denominator observation, not `activity_only` or pure
  discovery metadata. Its real field is `pack_count=30`; `observed_at` is the
  article publication timestamp. JP is a Tier-B product-market bucket
  (`country_code=JP`, `geography_basis=product_market`,
  `geography_confidence=tier_b`).
- The policy intentionally uses `statistics_eligible_default=true` because the
  existing fenced coverage pipeline requires that value. It does not make this
  source rate-eligible. Reviewed contract ordinal 6 writes only to
  `ingest.public_study_coverage_observations`, whose schema has no numerator; it
  never enters `ingest.public_study_observations` and cannot be statistically
  promoted. No qualifying-hit count, rate metric, posterior input, or `SAR` to
  `SIR` mapping is permitted.
- After the first verified live collection, the public coverage contract may
  show exactly 30 packs, 1 opening, and 1 source, with no numerator, rate,
  baseline, posterior, interval, delta, or signal. Migration files, worker code,
  fixtures, tests, or deployment alone do not prove that observation exists:
  the migration and worker must be released and the first persisted row and
  public response independently verified before it is described as live.
- Australia (`AU`), China (`CN`), Russia (`RU`), Canada (`CA`), Mexico (`MX`),
  and Brazil (`BR`) have no qualified source in this M5 review. An outline does
  not count as an observation. This rollout does not make PokeCrack
  production-ready.

## Historical 2026-08-30 branch audit

This section records the state observed on 2026-08-30. It is not a description
of the current production contract; later migrations add reviewed country
coverage and the v3 direct observed-sample projection.

- Production v2 was observed serving the live 218-set TCGdex catalog plus two
  current country observations: 72 reviewed packs across the United States and
  United Kingdom. Both countries remain below three independent sources, so no
  country rate is published.
- This branch adds `get_public_dashboard_snapshot_v3()`. It connects the two
  reviewed studies to bounded set and current-period country summaries, merges
  those denominators with any reviewed published v2 map result, publishes safe
  status for all four registered source classes, and publishes role-level health
  for the three currently ready worker services. Denominator rows remain visible
  as `pending` after the evidence threshold is met if the reviewed baseline and
  interval publisher has not completed. It does not publish a hit numerator,
  private YouTube identity, or convert discovery metadata into statistical
  evidence.
- v3 is **not deployed/live** merely because the migration and Web adapter exist
  in this branch. It must pass clean PostgreSQL 17 migration/pgTAP replay, merge,
  apply to Personal Supabase project `wohnphsxlquhhknuthrj`, and receive live
  browser verification before that claim changes.
- The authorized-opening operator hardening remains a forward-only,
  not-deployed change in migration `20260925000000`. It pins the four existing
  SECURITY DEFINER RPCs to `pg_catalog, pg_temp`, gives the submitter only a
  direct-owner wrapper, rejects URL/URI-bearing envelope strings locally, and
  carries accepted observation UUIDs through the reviewer CLI. PostgreSQL
  replay, dedicated-login attestation, and owner review are still required
  before any real operator envelope is used.
- The MAM VPS runtime was not re-audited in this branch because the current
  session had not yet received exact authorization for that boundary. YouTube
  collection and the hosted worker revision therefore remain unverified here.

The sections below retain the 2026-08-28 implementation record as historical
evidence; where it conflicts with the current audit above, the dated current
audit takes precedence.

## Status vocabulary

- **Verified:** the stated command or runtime path completed successfully.
- **Fixture verified:** deterministic synthetic inputs exercised the contract;
  no real-world observation is implied.
- **Static verified:** code, schema, policy, or configuration checks passed, but
  the corresponding production revision was not started.
- **Deployed/live:** the exact revision ran against the exact approved target and
  produced recorded operational evidence.
- **Blocked/unverified:** a required credential, approval, runtime, or complete
  end-to-end observation was absent.

## Historical 2026-08-28 repository and external baseline

- The backend integration worktree is
  `/private/tmp/pokecrack-global-backend.VfSoCM` on
  `codex/global-data-pipeline`, based on merged Personal-repository commit
  `9428e1d`. The protected UI worktree and its `codex/light-map-dashboard`
  branch were not modified. This backend diff contains no `apps/web` path.
- The approved Git origin is the private repository `ncihxaonn/pokecrack`.
  Repository-local Git identity is `ncihxaonn` with the approved GitHub
  noreply address.
- A prior owner-approved rollout deployed main commit `9428e1d` and its
  catalog-only TCGdex path to Personal Supabase project `wohnphsxlquhhknuthrj`
  and the MAM VPS. This backend-only audit did not independently revalidate the
  exact hosted migration list, so future-dated repository filenames are not used
  as deployment chronology. The catalog contains 218 live TCGdex set rows.
  Collector, scheduler, and watchdog were observed healthy after the isolated
  database tests in this audit. TCGdex is catalog-only and is not pull-rate
  evidence.
- The hosted public live observation/rate data remains empty. The Vercel site is
  a Demo-mode Web deployment and is not evidence of a live statistical path.
- The project credential helper found the Personal Maton credential with
  system-level execution, and Maton reports an Active YouTube connection. The
  broad Maton credential was not copied to the VPS or repository. No dedicated
  `YOUTUBE_API_KEY` is currently available to the worker, and
  `YOUTUBE_COLLECTION_ENABLED` remains false.
- The current `20260828500000` backup-lock migration,
  `20260828750000` Admin session-fence migration, `20260829000000` YouTube
  migration, and worker revision are not deployed. The latest project rules
  require a new explicit approval before any hosted migration or VPS production
  change, so this branch stops at PR/CI.
- The `codex/live-data-dashboard` integration branch adds a separate global
  public v2 schema/UI contract. It projects the existing TCGdex catalog into
  browser-safe tables, adds a strict country-period map dimension, and renders a
  local Natural Earth Equal Earth map. The country observation table has no
  writer and therefore starts honestly empty. This revision is not deployed.

## Implemented global backend contract

### Global discovery, not global pull rates

The private pipeline now supports bounded global discovery while keeping the
public v1 statistics contract Australia/English-only:

- private validation preserves an explicit uppercase two-letter country fact
  from any country instead of defaulting missing geography to Australia;
- missing geography becomes `activity_only`, while malformed geography fails;
- public aggregation still requires `country_code=AU` and the existing
  denominator, evidence-tier, completeness, and source-count gates;
- activity metadata cannot create an opening, hit, denominator, aggregate, or
  public signal.

The evidence classes and the path to denominator-backed global statistics are
documented in `docs/GLOBAL_DATA_PIPELINE.md`.

### YouTube Data API discovery

The worker implements one job per exact query for five fixed, versioned global
English searches: booster box, ETB, booster bundle, pack opening, and opening
batch-code discovery. Each job makes exactly one official `search.list` request;
there is no channel enrichment request.

The adapter:

- uses a fixed `youtube.googleapis.com` search endpoint, disables environment
  proxies and redirects, requests identity encoding, rejects compressed
  responses, applies a fixed 30-second deadline, and streams stdout/stderr
  through independent hard caps before buffering more than one sentinel byte;
- independently rejects any drift from the five exact query texts,
  `order=date`, 25-result cap, 30-day publication window, metadata-only flag, or
  absent `regionCode` before network I/O;
- validates duplicate JSON keys, exact 11-character video IDs, response shape,
  timestamps, and bounded normalized title text, while excluding legitimate
  upcoming premieres locally after an upstream `publishedBefore` bound;
- never downloads or retains video, audio, captions, thumbnails, descriptions,
  channel identity/country, or raw channel IDs;
- stores no query/rank association, content hash, inferred language,
  product/batch hint, category, engagement metric, or geography;
- persists only video ID, canonical URL, title, publication time, a source-policy
  reference and lifecycle timestamps in a private 28-day cache. The finalizer
  validates both exact version strings but does not retain them as cache columns.

The scheduler receives only `YOUTUBE_COLLECTION_ENABLED`; it never receives the
API key. The collector requires both the flag and a dedicated key. Enabling the
feature freezes `SCHEDULE_OFFICIAL_API` to exactly every six hours and
`SCHEDULE_CLEANUP` to exactly daily, so an operator cannot accidentally enqueue
expensive searches every minute or weaken retention by moving cleanup weekly.
The daily cleanup has a bounded 12-hour restart catch-up, leaving operational
margin below 30 days for the supported recovery window. The checked-in flag
default is false, and the database source policy remains an independent kill
switch.

### Fenced persistence

Migration `20260829000000_youtube_global_discovery.sql` adds:

- a dedicated `UNLOGGED`, forced-RLS `ingest.youtube_discoveries` table that is
  isolated from generic sources, extraction, openings, analytics, Admin, and
  public relations;
- an exact live `youtube_discovery` source policy and persistent request gate;
- `begin_youtube_discovery_job`, which validates the job payload, current lease
  generation, policy, request spacing, and gate ownership before network I/O;
- `finalize_youtube_discovery_job`, which rechecks the lease, policy, gate,
  versioned result shape, exact identities and bounds before atomically
  upserting only the dedicated cache and completing the job;
- per-row database-clock `expires_at = now + 28 days` refresh semantics and
  bounded daily deletion ordered by each independent expiry;
- service-role read-only table access, with upserts available only through the
  fenced YouTube security-definer finalizer and expiry deletion only through the
  existing fenced cleanup finalizer;
- post-network success/failure timestamps that preserve cross-job request
  spacing before releasing the persistent gate.

The RPCs are service-role-only. `anon`, `authenticated`, and `public` receive
no execute or direct DML access. A stale lease, disabled policy, malformed result,
identity rebind, or second-item conflict produces no partial persistence. The
table is disposable across crashes and has no WAL/standby-replication guarantee.

Migration `20260828750000_admin_session_fence.sql` keeps the public Admin RPC
signatures stable while moving both implementations into `ingest`, removing all
non-owner execution there, and making the public wrappers require both the
immutable `authenticator` login session and a `service_role` JWT claim. A direct
database worker that inherits `service_role` cannot manufacture that session by
changing role or request GUCs.

## Verified quality gates

### Worker

Run from `services/worker` after integration and final formatting:

```bash
uv run ruff check pokecrack_worker tests
uv run ruff format --check pokecrack_worker tests
uv run mypy pokecrack_worker
uv run pytest -q
```

Result: **421 passed, 1 optional Scrapling runtime skipped, and 2 subtests
passed**. Ruff and format checks passed; mypy reported no issues in 64 source
files. Coverage includes flag-off behavior, five scheduler jobs, scheduler
operation without the key, exact six-hour cadence, query-drift rejection before
network I/O, preflight deferral, one fixed API call, 429 retry classification,
malformed-response rejection, streaming raw-byte/content-encoding bounds,
upcoming-result filtering without whole-job failure, process-group
termination/reaping on every exceptional transport exit, stale leases, typed
finalization, fatal non-finalization while a curl process remains unreaped,
worker enqueue/pause/complete/heartbeat through bounded RPCs rather
than direct DML, and global-country/AU-publication boundaries.

### Database

- Static migration/type contracts: **46/46 passed**; the combined static and
  migration-safety unit suite passed **54/54**.
- An isolated PostgreSQL 17 container on the previously approved VPS compiled
  all 12 migrations, loaded the synthetic seed, and passed all nine pgTAP files
  without production data or credentials.
- pgTAP plans passed **575/575**: 132 schema/queue, 54 analytics, 79
  public/security/Admin, 42 seed, 50 lease fencing, 122 TCGdex, 63 YouTube
  discovery, 21 service-role least-privilege, and 12 Admin session-fence
  assertions.
- The dedicated YouTube file passed **63/63**, including exact six-field item
  shape, 25-item/one-page/four-key-policy bounds, direct-DML denial, fenced
  finalization, scheduled-job allowlisting, per-row database-clock expiry,
  independent bounded deletion, and
  absence of generic source/evidence/public relationships.
- The least-privilege file passed **21/21**: all 36 application tables have no
  direct service-role row-mutation privilege, 35 remain readable, the request
  gate remains unreadable, and its sole direct exception is PostgreSQL 17
  `MAINTAIN` for the backup schema lock. Replacement worker/finalizer RPC paths
  still succeed.
- The Admin session-fence file passed **12/12**: private implementations have no
  non-owner execution, public wrappers retain exact ACL/owner/definer contracts,
  a direct database worker is rejected even after `SET ROLE service_role` and a
  forged JWT GUC, and the real `authenticator` plus service-role JWT path works.
- Local Supabase is pinned to PostgreSQL 17. The protected remote migration
  workflow now rejects a hosted server below PostgreSQL 17 before reading or
  applying schema state.
- The temporary database container had no published port or persistent volume
  and was deleted after testing. No hosted schema was changed.

Local standalone PostgreSQL on the Mac remains unavailable because the host has
exhausted its global System V shared-memory slots. The isolated PostgreSQL run
provides the clean replay/pgTAP evidence for this revision.

### Monorepo, deployment contracts, and safety

- `pnpm lint`, `pnpm typecheck`, `pnpm test`, and `pnpm build` passed. Test
  counts were shared config 9, shared types 114, and unchanged base Web 105
  (**228/228 total**); Next.js generated 13 static pages.
- All **45/45** deployment tests that do not invoke Docker passed. Full discovery
  reported 45 passing tests and six errors solely where Compose rendering tried
  to execute a missing local Docker CLI; no new Compose runtime claim is made
  until CI.
- The backup sanitizer and backup-script boundary passed **25/25** targeted
  tests. It uses an unlinked mode-`0600` spool and two passes over one dump to
  accept either a coherent post-backup-lock/pre-YouTube state with policy/table
  both absent, or the exact policy plus exactly one supported `CREATE UNLOGGED
  TABLE` header in the same dump. In the latter state it removes every
  dedicated-cache data row while preserving unrelated generic source rows.
  Request-gate data is excluded at `pg_dump`, rejected again by the sanitizer,
  and replaced only with canonical idle source keys immediately before RLS is
  enabled. The sanitizer verifies the exact PostgreSQL 17 gate columns, checks,
  primary key, forced/enabled RLS and zero gate policies. Partial states,
  logged/TEMP/duplicate definitions, permissive gate policies, preflight/dump
  mismatch, malformed COPY/INSERT data, and sanitizer/`psql` failures all abort
  before output without exposing the database URL or advancing the success
  marker. A fixed command runner requires `sslmode=require` or stronger, receives
  the URL on standard input, clears every inherited `PG*` variable, and maps only
  allowlisted fields into the child environment.
- A real PostgreSQL 17 fixture proved that schema `USAGE` plus only `MAINTAIN`
  on `ingest.source_request_gates` lets `pg_dump --role=service_role` retain the
  table schema when its data is explicitly excluded. The same role could not
  `SELECT` the table, and a dump that requested its rows failed. Two real plain
  pre- and post-YouTube dumps were then sanitized and restored into fresh
  databases owned by roles without `BYPASSRLS`: the YouTube cache restored with
  zero rows when present, the regular forced-RLS gate table retained its schema,
  and only the expected idle gate rows with null ownership were present. Both
  no-volume/no-port containers and all task-specific archives were deleted
  afterward. This is isolated fixture evidence, not a hosted-project backup or
  production restore drill.
- Repository/migration-safety guard tests passed **18/18**. The repository guard
  returned `{"ok": true, "findings": []}`.
- Pending-migration safety passed with exactly three reviewed DELETE
  fingerprints, each limited to the fenced bounded retention function.
- `git diff --check` passed and no credential value, environment file, database
  dump, backup, browser profile, media evidence, or private API payload was
  added.

## Fixture versus live evidence

All YouTube payload tests used fixtures. No credentialed YouTube request was
made, so this audit proves the adapter, queue, policy, and persistence contract,
not real global coverage. The cache contains no geography and cannot identify
the physical location of an opening or purchase.

Global observed-rate data still needs a verified pack denominator. The preferred
next data path is a first-party structured opening submission or an authorized
creator submission that accounts for every opened pack, followed by catalog
mapping, duplicate controls, independent validation, and the existing minimum
pack/source thresholds. Search popularity, catalog rows, and posts must never be
used as rate denominators.

## Remaining release blockers

1. The dedicated, API-restricted YouTube key is absent; automated discovery is
   correctly disabled.
2. The current `pokecrack_worker` login inherits broad `service_role`
   membership. The pending backup migration also grants that role PostgreSQL 17
   `MAINTAIN` on the request-gate table solely so the current logical backup can
   lock its schema. Collection must remain disabled until explicitly approved
   dedicated `NOINHERIT` worker and backup credentials are separated and
   verified with only their required RPC/read/schema-lock permissions, and the
   exact hosted backup/PITR retention is revalidated. Scheduler/watchdog health
   plus stale-cleanup and queue-delay alerts must also be verified because the
   retention catch-up window is finite.
3. The three new migrations and worker revision are not deployed or exercised
   against the approved hosted project/VPS. CI must pass before a separate
   deployment approval is requested.
4. The reviewed global public metric dimension and v2 DTO now exist locally, but
   global denominator-backed ingestion, its fenced aggregate publisher, and
   multilingual discovery do not. Public v1 stays frozen as the AU legacy slice;
   v2 country observations remain empty until a real verified denominator is
   published.
5. AI reservation/accounting and aggregate publication still need durable
   idempotency, staging, revision locking, and atomic publication before they can
   be enabled as unattended production roles.
6. Auth/Admin identity configuration, browser automation, dead-letter recovery,
   backup restore, and complete production monitoring remain incomplete or
   unverified.

Accordingly, PokeCrack is **not production-ready for unattended global pull-rate
research**.

## Deployment claim

The correct current description is:

> The existing VPS runs the merged catalog-only TCGdex revision and the hosted
> database contains 218 live catalog set rows but no live opening/rate data. The
> current branches add a tested, fenced, metadata-only global YouTube discovery
> path plus an independent global public v2 catalog/map contract and white global
> dashboard. Public v1 remains Australia-only, the v2 country table has no
> aggregate writer or live rows, neither revision is deployed, and the dedicated
> YouTube key is absent. The system therefore cannot yet produce global observed
> pull rates.
