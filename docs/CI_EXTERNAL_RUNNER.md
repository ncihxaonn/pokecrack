# Independent CI runner

`scripts/run_ci_checks.sh` is the versioned verification entry point for
PokeCrack. It is deliberately independent of GitHub Actions scheduling. The
GitHub workflow calls the same stage functions, so the repository does not have
one set of tests for GitHub and another set for local release work.

## What it does

The runner requires an explicit 40-character commit SHA, the exact PokeCrack
origin, and a clean checkout. It creates a new owner-only evidence directory
outside the checkout and records:

- the expected and resolved SHA;
- runner/platform and tool versions;
- each stage's start time, end time and exit code;
- one complete log per stage;
- dependency-audit exports and generated database types;
- the resolved digests for the pinned PostgreSQL-meta and Gitleaks images.

It stops at the first failed stage and writes a failed manifest. A successful
manifest is evidence for that exact checkout only; it does not set a GitHub
check, approve a pull request, or authorize a production mutation.

## Complete check set

| Stage | Checks |
| --- | --- |
| `web` | Frozen pnpm install, lint, typecheck, tests and production build |
| `worker` | Frozen uv environment, full locked dependency audit, Ruff, mypy and pytest |
| `auth-browser` | Frozen environment, dependency audit, Ruff, mypy, pytest and fixture-only production image build |
| `database` | Local Supabase startup, migration reset, both pgTAP boundaries, generated database type drift and guaranteed local-stack cleanup |
| `container-worker` | Production worker image build |
| `repository-policy` | Shellcheck, repository verifier, script tests and redacted Git-history secret scan |
| `deployment-contracts` | Deployment/backup/rollback contract tests and secret-free Compose render |

The database stage uses the same pinned PostgreSQL-meta image and Supabase CLI
version as the migration preflight. It never uses a production project or
production credential. The production migration, backup and Worker deployment
workflows remain separate because they are state-changing operations.

## Run on an isolated Linux runner

Use a disposable Docker-capable Linux VM, container host or CI worker that is
not the production VPS and has no production credentials mounted. Clone/fetch
the full Git history so the repository-policy stage can scan it. The runner
needs Git, Bash, Python 3, Node 22.13, pnpm 11.23, uv 0.11.6, Docker Compose,
ShellCheck and access to pull the immutable official Gitleaks image
`ghcr.io/gitleaks/gitleaks@sha256:c00b6bd0aeb3071cbcb79009cb16a60dd9e0a7c60e2be9ab65d25e6bc8abbb7f`.
The script verifies the pull digest and records the immutable image reference
in the evidence directory; it does not accept a scanner override.

Run from a clean checkout of the candidate:

```bash
candidate_sha=$(git rev-parse --verify HEAD)
scripts/run_ci_checks.sh all \
  --expected-sha "$candidate_sha" \
  --evidence-dir "/tmp/pokecrack-ci-${candidate_sha}"
```

For a failed run, preserve the evidence directory and its `manifest.json` and
stage logs. Do not rerun with a different checkout while retaining the same
evidence path. A stage can also be run independently with the same SHA, for
example `scripts/run_ci_checks.sh database --expected-sha "$candidate_sha"`.

## Security boundary

Do not run this script against `/home/codex/pokecrack` on the production VPS or
against its host Docker socket. Do not use MAM or InsiderLeads hosts/accounts.
Do not pass `SUPABASE_ACCESS_TOKEN`, production database URLs, SSH private keys,
Vercel tokens, or runtime dotenv files to this test runner. Its database stack,
Compose paths, image tags and secret scan are test-only.

This path is not the same as changing `runs-on` to `self-hosted`. GitHub's
Actions control plane may still refuse to schedule a private-repository job, and
that behavior has not been assumed or tested here. The independent runner is
invoked directly and produces its own auditable evidence.

## Release use

Before a candidate can be released, an operator must compare the evidence
manifest's SHA to the exact reviewed GitHub commit and retain the full logs. The
normal release gates still include a fresh encrypted backup, an isolated restore,
forward-only production migrations, the existing authorized Worker service set,
and a GitHub-triggered Vercel deployment. This runner cannot waive those gates
or change the source-of-truth branch.

Use the read-only release preflight after the candidate has landed on `main` and
before any backup, migration, VPS deployment, or Vercel release operation:

```bash
python3 scripts/verify_release_preflight.py \
  --sha EXACT_MAIN_SHA \
  --checkout /secure/checkouts/pokecrack \
  --ci-manifest /secure/evidence/ci/manifest.json \
  --release-evidence /secure/evidence/release-evidence.json \
  --project-ref wohnphsxlquhhknuthrj \
  --service-set tcgdex \
  --vps-host-key-fingerprint SHA256:KNOWN_HOST_KEY_FINGERPRINT \
  --vps-deploy-path /home/codex/pokecrack
```

The command requires `origin/main` in the checkout to equal `--sha`; it rejects
partial CI evidence, stale or unencrypted backup evidence, a missing isolated
restore drill, a changed backup/restore checksum, an unexpected project or VPS
target, and missing permission/approval attestations. The two JSON inputs and
the referenced artifact/report files must be owner-only and outside the
checkout. A release-evidence file has this shape (values are placeholders, not
release evidence):

```json
{
  "schema_version": 1,
  "repository": "ncihxaonn/pokecrack",
  "release_sha": "aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa",
  "ci_manifest_sha256": "64-lowercase-hex-characters-from-manifest",
  "target": {
    "supabase_project_ref": "wohnphsxlquhhknuthrj",
    "service_set": "tcgdex",
    "vps_host_key_fingerprint": "SHA256:the-reviewed-host-key-fingerprint",
    "vps_deploy_path": "/home/codex/pokecrack"
  },
  "approval": {
    "recorded": true,
    "reference": "protected-environment-approval-reference"
  },
  "backup": {
    "reference": "encrypted-backup-reference",
    "encrypted": true,
    "isolated_restore_verified": true,
    "retention_verified": true,
    "created_at": "20260906T120000Z",
    "artifact_path": "/secure/evidence/backup.sql.gz.age",
    "artifact_sha256": "64-lowercase-hex-characters-from-artifact",
    "restore_evidence_path": "/secure/evidence/restore-report.json",
    "restore_evidence_sha256": "64-lowercase-hex-characters-from-report"
  },
  "permissions": {
    "runner_has_no_production_credentials": true,
    "backup_credential_is_separate": true,
    "worker_credential_is_separate": true,
    "backup_role_noinherit": true,
    "backup_role_cannot_read_gate_rows": true,
    "production_mutation_requires_owner_approval": true
  }
}
```

The preflight only verifies and prints a non-secret summary. It does not call
Supabase, SSH, Docker, Vercel, or any production mutation entry point. The
existing backup, migration, and Worker deployment workflows still use
`ubuntu-latest` because they carry state-changing credentials and operations;
they remain separately approved/manual release controls until an equivalent
owner-managed release host is provisioned. The independent check runner must
never receive those credentials or the production VPS Docker socket.

GitHub's current billing documentation distinguishes private-repository hosted
runner quotas from self-hosted usage; see [Billing and usage](https://docs.github.com/en/actions/concepts/billing-and-usage).
GitHub's pricing announcement also notes that its announced self-hosted billing
change was postponed; see [the official changelog](https://github.blog/changelog/2025-12-16-coming-soon-simpler-pricing-and-a-better-experience-for-github-actions/).
Neither page is used as permission to bypass the repository's release gates.
