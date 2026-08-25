# PokeCrack Codex migration handoff

Generated: 2026-08-26 (Australia/Melbourne)

## Source snapshot

- Former runtime: Hermes Personal gateway on `root@187.77.114.88`
- Former repository path: `/srv/hermes/companies/personal/work/projects/personal-core`
- Hermes project label: `POKECRACK MVP`
- Hermes project/workspace: `personal-core`
- Hermes session: `20260825_054905_f1e073`
- Git branch: `feat/free-mvp`
- State before migration: zero commits; all source files were untracked
- Migration rule: preserve source and Git history, but do not migrate Hermes chats or Hermes runtime state

## Product and repository

PokeCrack is a private monorepo for a free, experimental dashboard that reports observed Pokemon TCG pack-opening activity. The repository contains:

- Next.js public dashboard and protected admin UI in `apps/web`
- Python collection, validation, aggregation, and scheduling services in `services/worker`
- Authenticated browser/OpenCLI support in `services/auth-browser`
- Shared TypeScript packages in `packages`
- Supabase migrations, seed data, and pgTAP tests in `supabase`
- VPS deployment and operations assets in `deploy`

The canonical implementation record is `docs/IMPLEMENTATION_NOTES.md`. Read it before making deployment claims.

## Verified at handoff

The existing implementation record reports successful final local gates for:

- JavaScript/TypeScript lint, typecheck, tests, and Next.js production build
- 9 shared-config tests
- 114 shared-types tests
- 91 Web tests
- 229 Worker tests plus 2 subtests
- authenticated-browser fixture and policy tests
- 281 pgTAP assertions on a fresh PostgreSQL 17 audit harness
- repository policy checks and static deployment configuration validation

These results describe the prior implementation environment. Re-run the relevant gates in the new Codex environment before relying on them.

## Known blockers and unfinished work

- No real production deployment has been completed.
- Persistent production worker-role handlers are not fully wired or proven end to end.
- Hosted Supabase/Auth/PostgREST, Vercel, GitHub CI, browser login, OpenCLI artifact, Docker runtime, external collectors, and paid AI paths remain unverified or account-dependent.
- The final independent current-tree review noted in `docs/IMPLEMENTATION_NOTES.md` had not produced a recorded release sign-off at migration time.
- Do not describe the repository as production-ready until the blockers in `docs/IMPLEMENTATION_NOTES.md` are closed and independently verified.

## Security and isolation requirements

- Keep this project in its own container and its own persistent `CODEX_HOME`.
- Do not copy Hermes session databases, chats, runtime state, or Hermes credentials.
- Do not commit `.env`, OAuth caches, browser profiles, database dumps, backups, media evidence, or service-role keys.
- Keep project credentials scoped to PokeCrack only; do not mount MAM or N8N credentials into this container.
- Bind noVNC, CDP, OpenCLI bridge, and administrative services to loopback unless a separately reviewed ingress is required.
- Preserve deny-by-default source policy and demo/fixture defaults until live integrations are explicitly approved.

## Recommended Codex restart point

1. Read `README.md`, `docs/IMPLEMENTATION_NOTES.md`, `docs/FINAL_AUDIT_REPORT.md`, `docs/SECURITY.md`, and `docs/DEPLOYMENT.md`.
2. Run `python3 scripts/verify_repository.py .` before installing or starting services.
3. Re-run the repository's documented JavaScript, Python, database, and Compose verification gates in the new container.
4. Reproduce or complete the independent audit before changing release status.
5. Wire and test persistent production handlers against an isolated PostgreSQL/Supabase-compatible database before any unattended deployment.

## Migration artifacts

The migration should produce and verify all of the following outside `/srv/hermes`:

- a commit on `feat/free-mvp`
- a Git bundle containing the branch
- a working copy under `/srv/codex`
- an isolated persistent `CODEX_HOME`
- a Codex container that survives restart with its project and authentication state intact

