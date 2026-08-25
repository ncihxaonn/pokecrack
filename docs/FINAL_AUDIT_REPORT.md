# Pokecrack MVP — Final Local Audit Report

**Audit timestamp:** 2026-08-25T20:00:38Z  
**Repository:** `/work/projects/personal-core`  
**Branch:** `feat/free-mvp` (unborn; no commits and no remote configured)

## Verdict

| Layer | Verdict | Meaning |
| --- | --- | --- |
| Free experimental fixture/demo MVP | **PASS locally** | Available policy, format, type, test, build, fixture smoke, and static security gates passed. |
| Final independent current-tree review | **[PENDING_FINAL_REVIEW]** | Release sign-off remains withheld until the running logic and security reviews return complete. |
| Production release/deployment | **BLOCKED / NOT DEPLOYED** | The production Worker has no persistent database-backed composition root; Docker, hosted Supabase, and account-bound deployment integrations were unavailable. |

This verdict applies only to Australia, English, physical Pokémon TCG, and the `booster_box`, `etb`, and `booster_bundle` product types.

## Closed HIGH/MEDIUM findings

1. Static Scrapling requests now pin the validated public IP at the transport layer instead of trusting a preflight lookup.
2. Paid-capable AI dispatches are limited to one attempt per reservation; failed, missing-usage, and zero-usage responses retain the conservative reservation rather than recording AUD 0. Committed reservations remain charged to their trusted start day/month across UTC rollover.
3. Auth-browser output redacts common session identifiers in text and nested mappings, including quoted JSON `session_id`, `sid`, and `auth` plus camelCase `sessionData` keys.
4. Public snapshot collections are filtered to the selected demo/live mode and an `unavailable` dashboard cannot expose stale collection rows.
5. `record.exclude` marks linked openings non-statistical/excluded, removes derived sightings, invalidates same-mode private/public projections, publishes an unavailable sentinel pending rebuild, and immediately invalidates the tagged public Web cache.
6. Extractor/validator rarity disagreement and extractor/catalog rarity disagreement both prevent evidence acceptance for rates.
7. PostgreSQL heartbeat/complete/fail/budget-pause mutations require an active unexpired lease and use one database clock rather than a worker-supplied clock for ownership and transition timestamps.
8. Public inference is withheld in Worker, shared-types, Web, signal DTOs, dashboard baseline, private signal storage, RPC output, and public-table contracts whenever there are fewer than 30 packs **or** fewer than three independent sources.
9. `Watch` and `Possible anomaly` now gate on posterior probability above the configured practical uplift (0.90/0.95), not merely probability above baseline; matching private/public SQL checks use the same quantity.
10. Dashboard, private metric, public summary, and public signal contracts now reject independent-source counts above complete openings; dashboard/shared/Web contracts also reject openings above observed packs.
11. The dynamic browser adapter now runs one attempt through a project-owned Playwright boundary, ignores proxy configuration, blocks service workers and WebSockets, pins the approved hostname, and invokes request/WebSocket guard setup directly so setup failure aborts before navigation rather than being swallowed by Scrapling.
12. Captured auth-browser text now redacts camelCase `sessionData`/`sessionID` assignments and quoted JSON as well as nested mapping keys.
13. Synthetic SQL aggregate/signal seed rows now satisfy source/opening coherence and practical-uplift probability gates.
14. Validator and escalation card identity and rarity are rechecked against the deterministic catalog; unknown, ambiguous, missing-rarity, or conflicting-rarity consensus cannot become rate-eligible.
15. Private dashboard aggregates now reject accepted-source totals above complete openings.
16. Shared and Web trend points now carry complete-opening and independent-source counts and withhold both rates below 30 packs or three sources.
17. Seeded public metric deltas now exactly equal observed minus baseline, and the pgTAP index assertions use the correct schema/table/index overloads.

## Executed verification

| Area | Executed result |
| --- | --- |
| Repository policy guard | `ok: true`, zero findings; 7 guard tests passed. |
| JS/TS install | Frozen pnpm install succeeded. |
| JS/TS lint and types | Workspace lint and typecheck passed. |
| Shared config | 9 tests passed. |
| Shared types | 114 tests passed across 10 files. |
| Web | 91 tests passed across 24 files. |
| Web build | Next.js 16.3.2 production build completed; expected public/protected routes emitted. |
| Web smoke | Eight public routes returned HTTP 200; `/admin` returned 307 to `/admin/login`; CSP was present. |
| Worker | Ruff, format check, mypy, and 229 tests plus 2 subtests passed. |
| Auth-browser | Ruff, format check, mypy, and 66 tests passed. |
| Supabase static contracts | 26 tests passed; all 12 migration/seed/SQL-test files and 4 PostgreSQL lease statements parsed with pglast 8.4. |
| Local PostgreSQL runtime | On a fresh PostgreSQL 17 cluster with explicit Supabase-like roles and a minimal `auth.jwt()` test shim, all 7 migrations and the current seed committed; 281 pgTAP assertions passed (125 schema, 54 analytics, 64 public/security, 38 seed). |
| Deployment artifacts | 25 tests passed; shell syntax and Compose render passed. |
| Fixture Worker | Health reported fixture/demo/in-memory/no-network; dry-run performed no mutation. |
| Live Worker fail-closed | Invalid live configuration emitted redacted JSON and exited 78. |
| Python static/dependency security | Worker and auth-browser Bandit medium/high scans passed; pinned pip-audit 2.10.1 found no known vulnerabilities in frozen production exports. |
| Node dependency security | `pnpm audit --prod` found no known vulnerabilities. |
| Client bundle secret scan | No service-role/Admin/AI/YouTube secret identifiers found in `.next/static` JavaScript. |

## Verification boundaries and blockers

- **No real deployment was performed.** There is no repository remote or deployment credential/context.
- **Production Worker persistence remains unimplemented.** Live mode fails closed rather than pretending to process durable jobs.
- **Current SQL has local runtime evidence, but not a full Supabase stack.** All current migrations, seed data, and 281 pgTAP assertions passed on a fresh standalone PostgreSQL 17 cluster with Supabase-like roles and a minimal `auth.jwt()` shim. Hosted Supabase Auth, PostgREST, Realtime, and provider behavior remain unverified.
- **Docker runtime was unavailable.** Compose rendered successfully, but `docker info` could not connect to `/var/run/docker.sock`; no image build, container health check, or rollback drill was executed.
- **No account-bound integration was exercised.** No real Supabase Auth/PostgREST, collector API, AI API, Chromium/noVNC login, OpenCLI artifact, or authenticated social/video command was run.
- **No post-fix headed-browser runtime probe was possible on this host.** The pinned Playwright Chromium executable was absent; the dynamic service-worker/WebSocket controls were verified through focused code-level regressions and configuration inspection, not a real browser launch.
- Fixture and dry-run outputs are not live collection evidence and are not production data.

## Residual local resources

- A local Next.js test process remains bound only to `127.0.0.1:3000`; cleanup authorization timed out, so it was not terminated.
- `/tmp/pokecrack-pg-final.CWqpTPIf` remains on disk because deletion/rebuild authorization timed out. Its PostgreSQL server was stopped and port `55440` was verified closed.
- `/tmp/pokecrack-pg-audit.6k6Zx6hY` contains the successful standalone PostgreSQL 17 audit cluster; its tracked server process was stopped after the migration/seed/pgTAP run.
- Ports `6080`, `5900`, `19825`, and `9222` were verified closed.

## Production acceptance still required

1. Implement and test a persistent PostgreSQL/Supabase Worker composition root for every production role.
2. Repeat the current passing PostgreSQL migration/seed/RLS/RPC/Admin tests on an owner-controlled full Supabase stack, including Auth and PostgREST behavior.
3. Build and run containers with a real Docker daemon; verify every healthcheck, resource limit, backup, deploy, and rollback path.
4. Configure owner-controlled secrets only through environment/secret files and validate real provider policies without bypassing CAPTCHA or using proxy pools.
5. Complete a real hosted smoke test and read back deployed state before changing this report to production-ready.
