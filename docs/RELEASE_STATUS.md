# Release status and convergence

## Repository visibility update: 2026-09-07

The owner explicitly approved making the complete `ncihxaonn/pokecrack`
repository public, including its reachable branches, history, Worker,
auth-browser, Supabase migrations, deployment scripts, CI and documentation.
GitHub now reports the repository as public. No credentials, database dumps,
browser profiles or private API payloads were added. The dated baseline below
still records the private visibility that was verified on 2026-09-05.

The GitHub-managed API backup workflow remains private-only by design: its raw
rollback artifact would not be safe in publicly readable Actions storage. Public
repository operation therefore uses the VPS retention path or a separately
approved private artifact store; this visibility change does not waive the
backup, restore, CI or production release gates.

This is the operational entry point, not permission to deploy. Update the dated
evidence after each actual release. A candidate, clean checkout, successful
preview, or completed code review is not a production release.

## Verified baseline: 2026-09-05

Provider and runtime checks were performed with the Personal GitHub identity
`ncihxaonn`, the project-scoped Supabase credential route, and the PokeCrack-only
VPS checkout. No credentials or database payloads belong in this document.

| Component | Verified state |
| --- | --- |
| Authoritative repository | `https://github.com/ncihxaonn/pokecrack.git`, private, production branch `main` |
| GitHub main / Vercel code | `b3afeeb35f6fe91f76af44cbace0efe2d502bfbc` |
| Public site | `https://pokecrack.vercel.app/` |
| Production Supabase project | `wohnphsxlquhhknuthrj`; 46 applied migrations, latest `20261003000000` |
| VPS checkout | `/home/codex/pokecrack`, clean, `d6fa1d0cfa1769d6bc1cc4576f995bd74858db08` |
| VPS release marker | `/home/codex/.local/share/pokecrack/deploy/last-successful-deployment`, same Worker SHA |
| Enabled service set | `tcgdex`: collector, scheduler, watchdog; all three containers healthy |
| Latest VPS backup | `pokecrack-20260904T054715Z.sql.gz`; matching success marker, gzip integrity verified; no new restore drill |
| Managed database backups | API returned no backup records and PITR disabled at the audit time |

**The baseline is not synchronized.** Main still has three unapplied migrations:

- `20261004000000_public_observed_sample_rates.sql`
- `20261006000000_brazil_pontocom_observed_sample.sql`
- `20261007000000_puerto_rico_youtube_coverage.sql`

Migration prefixes are version identifiers, not deployment timestamps. Main's
latest successful CI was [33945140768](https://github.com/ncihxaonn/pokecrack/actions/runs/33945140768).
The last [backup attempt](https://github.com/ncihxaonn/pokecrack/actions/runs/33945164949)
failed before producing/uploading a backup. The older VPS backup predates the
most recent production migration and is not proof of current-state recoverability.

## One candidate, not multiple competing final versions

The convergence branch is `codex/release-convergence-20260905`. It combines:

- [PR #74](https://github.com/ncihxaonn/pokecrack/pull/74), reviewed target
  `7d997699aba288d49f1f318cead9e1edba5c9836`: exact-source Americas coverage,
  historical evidence-range handling, matching Worker and backup contracts.
- [PR #73](https://github.com/ncihxaonn/pokecrack/pull/73), reviewed target
  `5d9c043767fe4ecbf8bc20507b90a8a2a493c1e8`: session-pooler backup connection
  and bounded, sanitized connection-failure diagnostics.

PR #74 adds migrations `20261008000000`, `20261009000000`, and
`20261010000000`; these are also unreleased. Existing source branches remain
recoverable until a reviewed replacement is landed. Do not independently merge
both original PRs and a consolidated replacement without checking ancestry and
the final tree.

The intended feature scope is already-implemented reviewed-source coverage and
backup reliability, not activation of every experimental role. Coverage-only
observations must not gain invented hit numerators, language, geography,
baselines, or inferred probabilities merely to fill an empty UI.

## Completed candidate verification: 2026-09-05

The user explicitly approved submission of the private branch diffs to the
configured Codex reviewer. Independent, read-only structured reviews of PR #74
and PR #73 against `b3afeeb35f6fe91f76af44cbace0efe2d502bfbc` each completed
successfully with zero final actionable findings. These are review conclusions,
not a guarantee that the application is vulnerability-free. A tentative migration
finding was withdrawn after the earlier migration was checked; no source was
changed to satisfy that false positive.

The consolidated source tree was verified locally:

| Check | Result |
| --- | --- |
| Web / shared types / shared config | 332 tests passed |
| Worker | 788 passed, 1 skipped |
| Deployment, scripts and static migration contracts | 298 passed, 9 skipped |
| Auth-browser | 71 passed, 1 skipped |
| Lint, TypeScript checks, Next.js production build | Passed |
| Repository verification / whitespace checks | Passed; no repository findings |
| Native PostgreSQL 17.11 / UTF-8 migration replay | All 52 migrations applied through `20261010000000` |

Total: **1,489 passed, 11 skipped**, without double-counting pytest subtests.
Skips concern unavailable Docker, optional Scrapling runtime, and Linux-specific
process inspection. Local socket tests were run with the required local-system
permissions. The native database used an isolated, private Unix socket and a
minimal Supabase-auth fixture; it was stopped after testing. It was not production
and does not replace full Supabase/pgTAP CI or a production-data restore drill.

A native fixture dump was also checked in UTF-8/UTC. It was rejected by the
fail-closed sanitizer because a migration-only database has 15 of the 22 required
coverage records: seven older sources are populated by collection, not fresh
migration replay. No synthetic rows were added to manufacture a passing backup,
and no production data was copied. This is an incomplete backup rehearsal, not
restore evidence and not an accepted new regression in the candidate.

## Current release blockers

1. **CI capacity/account restriction.** PR #74 run
   [33959142684](https://github.com/ncihxaonn/pokecrack/actions/runs/33959142684)
   was retried at attempt 2 on 2026-09-05. All seven jobs were refused before
   execution because of failed recent payments or the spending limit. The
   account owner must resolve that condition. The candidate now contains the
   versioned `scripts/run_ci_checks.sh` runner; `.github/workflows/ci.yml`
   delegates all seven jobs to that same implementation, so an approved
   disposable Docker-capable Linux runner can execute the equivalent checks
   without consuming GitHub-hosted runner quota. The current Mac still has no
   Docker-capable runtime, so this alternative has not yet produced a passing
   full evidence manifest. Do not fabricate GitHub checks or treat a partial
   local pass as release evidence.
2. **Fresh, recoverable backup.** The candidate now encrypts the validated gzip
   before any GitHub artifact upload and verifies decrypt/gzip/byte equality;
   the protected `BACKUP_ENCRYPTION_PASSPHRASE` has been provisioned in the
   Production environment. A post-merge workflow run and isolated restore must
   still be recorded against the exact final main SHA before this gate is
   closed.
3. **Release control.** Main/Production lacked enforced protection at the audit
   time. Verify branch/environment restrictions and actual backup identity,
   project, age, integrity and restore evidence before running production
   migrations; a syntactically valid backup reference alone is insufficient.

Do not carry the completed review claim across subsequent source changes.
Any accepted code fix needs its focused tests and independent review before
being included in the release.

### CI alternative and release preflight

The repository now has an external execution path in
[`CI_EXTERNAL_RUNNER.md`](CI_EXTERNAL_RUNNER.md). `scripts/run_ci_checks.sh`
requires the exact checkout SHA, exact origin, clean status and a new private
evidence directory; it records tool versions, stage exit codes, full logs,
dependency-audit exports, generated types and resolved image digests. Every
`.github/workflows/ci.yml` check job calls the same stage implementation. A
passed external manifest is auditable evidence for that SHA, but it does not
create a GitHub check or merge a pull request.

The current Mac has no Docker-capable runtime, and no approved external CI
provider or Personal/PokeCrack Linux runner is configured, so the full external
run remains pending. The repository also includes the read-only
`scripts/verify_release_preflight.py` gate. After main contains the exact
release SHA, it verifies the external manifest plus operator-owned evidence for
the approved Supabase project/VPS target, encrypted fresh backup, isolated
restore, least-privilege credentials and separate owner approval. It performs no
provider, SSH, Vercel or production mutation. The existing backup, migration and
Worker deployment workflows still depend on `ubuntu-latest` for their protected
state-changing steps; do not replace that dependency with the production VPS or
the test runner until an owner-managed release host with the same isolation and
approval controls exists. Keep PR #75 as draft and do not merge or deploy until
the equivalent full checks and release gates pass.

Keep failures separate: the GitHub `Production` environment has been used by
both Vercel deployment and backup work. A later backup failure attached to that
environment does not by itself mean the Vercel site deployment failed.

## Required release sequence

1. Freeze the consolidated candidate and its review/test evidence. Require
   the repository's full CI, including Docker, PostgreSQL replay, pgTAP, type
   drift, dependency audits and repository policy checks.
2. Land only through the reviewed GitHub main flow. Record the resulting exact
   main SHA; re-check it before each external mutation. The user's approval of
   synchronization does not waive release checks or authorize billing changes.
3. Create and verify the fresh backup before the database changes. Do not
   weaken the backup sanitizer to accept a partial schema or mixed source set.
4. Apply forward migrations for that exact main checkout through
   `migrate-database.yml` against Production. Review only the actual pending
   migrations; require no pending migrations afterward. Do not reset production.
5. Deploy that same SHA through `deploy-worker.yml` to the existing authorized
   `tcgdex` service set. Do not silently enable/retire optional lanes. Check the
   image labels, checkout SHA, successful release marker and source-level
   runtime evidence, not just process health.
6. Verify the GitHub-triggered Vercel production deployment and canonical site.
   Never publish the application directly from a local checkout with
   `vercel --prod` or an equivalent command. Use backward-compatible database
   changes because GitHub-driven Web deployment may precede the Worker update.
7. Verify actual public coverage against reviewed source identities and sample
   counts; preserve coverage-only vs rate/inference distinctions. Confirm the
   first persisted collection and subsequent scheduling for enabled new sources.
8. Record the final Web SHA, Worker SHA/service set, applied ledger, backup and
   CI run identities here. Only then mark the release synchronized.

## Local workspace and task ownership

- Keep one long-lived **Local/main** task for release status and coordination;
  keep its checkout clean. Select Local explicitly: Worktree + main creates a
  separate checkout based on main, usually detached HEAD.
- Implement on one task-owned `codex/*` branch per worktree. Use Codex Handoff
  to move a task; never steal a branch checked out by another worktree.
- The saved Local checkout at `/Users/nixon/Documents/Codex/Personal/PokeCrack`
  is now on `main`, clean, and equal to `origin/main` at
  `b3afeeb35f6fe91f76af44cbace0efe2d502bfbc`. Its local `AGENTS.md` and
  `.codex/company-profile` remain on disk and are ignored only through the
  repository-local `.git/info/exclude`; they were not committed or deleted.
- Recovery's older 17-path state is preserved by local-only commit `6d0b22f`
  on `codex/supabase-type-contract-tests`. It was not pushed and is not the
  release source; the branch remains deliberately separate and must not
  overwrite later main or Americas implementations.
- Keep `AGENTS.md` and the local company-profile marker deliberately managed;
  do not delete safety rules, commit credentials/backups, or use blanket Git
  cleanup to manufacture a clean status.
- Archive superseded tasks/worktrees only after their exact unique changes are
  accounted for and deletion is authorized. Missing worktree registrations are
  different from existing directories; never treat the inventory as a bulk
  deletion list.

## Release completion record

Status: **pending; no consolidated production release performed**.

Do not replace this with "complete" until all of the following have evidence:

- Local main clean and identical to GitHub main.
- Vercel and VPS running the intended release SHA.
- Production migration set equal to that release, with no pending versions.
- New backup, encryption/retention and isolated restore verified.
- Required CI and independent review passed for the shipped tree.
- Enabled sources collected and persisted reviewed data; unsupported roles
  remain explicitly gated.
- Recovery and Local have a recoverable, documented disposition. Remaining
  stale worktree registrations and old task entries still require individual
  review before any prune, archive, branch deletion, or worktree deletion.
