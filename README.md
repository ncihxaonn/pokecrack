# Pokecrack

> **Working name.** Trademark, domain, and commercial-use clearance have not been performed.

**Crack open the data behind every pack.**

Pokecrack is a free, personal, experimental, non-commercial and unofficial dashboard for **observed** Pokémon TCG physical pack-opening activity across sets, products, regions, retailers, and visible batch/lot codes.

> Observed results do not guarantee the contents of any individual pack, box, product, batch or store purchase.

Pokecrack is not affiliated with, endorsed by, or sponsored by The Pokémon Company, Nintendo, Game Freak or Creatures. It is not a gambling product, buying bot, “hot pack” predictor, store luck leaderboard, or guarantee of future pull rates.

## Current release and handoff

Start operational work with [the release status and convergence checklist](docs/RELEASE_STATUS.md).
It distinguishes the verified production baseline from unreleased candidates and
records the Web/database/Worker checks required before calling a release complete.
Older implementation reports are historical evidence, not the current runtime inventory.

## Architecture

```text
Public GitHub monorepo
├── Vercel Hobby: Next.js public dashboard + protected admin status UI
├── Supabase Free: PostgreSQL/Auth/RLS/public aggregate layer
└── Existing VPS (Docker Compose)
    ├── collector       allowlisted official APIs and bounded source adapters
    ├── auth-browser    headed persistent Chromium + Browser Bridge + OpenCLI
    ├── ai-worker       deterministic checks + extract + validate + escalation
    ├── aggregator      eligibility, baselines, empirical Bayes, public summaries
    ├── scheduler       PostgreSQL job creation
    └── watchdog        health, budgets, free-tier thresholds and optional email
```

The diagram describes the implementation, not the currently enabled service set.
The verified production core runs `collector`, `scheduler`, and `watchdog` on the
VPS. Browser, AI, aggregation, and isolated social lanes must pass their own
release gates before activation; their presence in the repository does not mean
they are running. A personal computer is not the production collection host.

The [global data pipeline contract](docs/GLOBAL_DATA_PIPELINE.md) separates catalog coverage, activity-only discovery, and denominator-backed statistical evidence. Global search metadata is never presented as a regional pull-rate claim.

## Safe defaults

- `DATA_MODE=demo`: clearly labelled synthetic data, no live observations.
- `AI_PROVIDER=fixture`: no paid AI requests.
- Unknown source domains are disabled.
- Social data starts as `statistics_eligible=false`.
- Third-party media is metadata-only by default; full videos are never retained.
- noVNC, CDP, and the OpenCLI daemon bind to loopback only.
- No Realtime, paid features, ads, affiliate links, public signup, CAPTCHA bypass, proxies, or automatic purchasing.

## Repository layout

```text
apps/web/                 Next.js dashboard and admin UI
services/worker/          collectors, queue, AI pipeline, aggregation and CLI
services/auth-browser/    VPS Chromium/OpenCLI/noVNC runner and health checks
packages/                 shared safe DTO/config schemas
config/                   explicit source/query/rarity registries
supabase/                 migrations, seed and pgTAP tests
deploy/                   Compose, extension installer, backup/deploy scripts
docs/                     architecture, methodology, security and operations
data/examples/            synthetic import fixtures only
```

## Local demo

Prerequisites: Node.js 22.13+, pnpm (version pinned in `package.json`), Python 3.12+, and `uv`.

```bash
cp .env.example .env
pnpm install --frozen-lockfile
pnpm --filter @pokecrack/web dev
```

Open <http://localhost:3000>. Demo mode requires no Supabase or AI key.

Worker fixture commands:

```bash
cd services/worker
uv sync --frozen
uv run pokecrack-worker health
uv run pokecrack-worker --help
uv run pokecrack-worker show-queue
```

Authenticated-browser fixture commands:

```bash
cd services/auth-browser
uv sync --frozen
uv run pokecrack-browser --help
uv run pokecrack-browser doctor
```

## Verification

```bash
candidate_sha=$(git rev-parse --verify HEAD)
scripts/run_ci_checks.sh all \
  --expected-sha "$candidate_sha" \
  --evidence-dir "/tmp/pokecrack-ci-${candidate_sha}"
```

This is the canonical verification path for Web, Worker, auth-browser,
Supabase/pgTAP, type drift, Docker images, repository policy and deployment
contracts. It requires a clean checkout and a Docker-capable runner. Preserve
the generated evidence manifest and logs; never report the Docker, Supabase or
image checks as passed when only static configuration validation ran. See
[`docs/CI_EXTERNAL_RUNNER.md`](docs/CI_EXTERNAL_RUNNER.md) for an isolated
non-GitHub execution path.

## Live setup

1. Create a dedicated **Supabase Free organization and project**; apply migrations and create the first admin account with signup disabled.
2. Create a **Vercel Hobby** project rooted at `apps/web`; configure only public Supabase values in browser-visible variables and server secrets in Vercel settings.
3. Prepare the VPS as a non-root deploy user, clone the public repository at the exact reviewed SHA, create `/opt/pokecrack/{browser-profiles,backups,opencli-extension}`, and set profile permissions to `0700`. Keep all configuration and secrets outside the checkout.
4. Pin and install an audited OpenCLI CLI/Browser Bridge release with its SHA-256; do not use a floating `latest` artifact.
5. Start Compose, tunnel `6080` over SSH, log into each permitted platform profile, run the browser doctor, and close the tunnel.
6. Configure daily `pg_dump` backups and test restore into a fresh project.

Exact account-owner steps are in:

- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
- [`docs/OPENCLI_VPS.md`](docs/OPENCLI_VPS.md)
- [`docs/BACKUP_AND_RESTORE.md`](docs/BACKUP_AND_RESTORE.md)
- [`docs/SECURITY.md`](docs/SECURITY.md)
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md)
- [`docs/CI_EXTERNAL_RUNNER.md`](docs/CI_EXTERNAL_RUNNER.md)

## Methodology summary

Only reviewed complete openings with an exact pack denominator can enter opening-sample coverage. When the same reviewed contract also contains an exact normalized qualifying-hit numerator, the public dashboard shows the literal descriptive fraction and observed sample rate at any sample size. Baselines, empirical-Bayes estimates, 90% credible intervals, comparisons, and signals still require the stricter statistical ledger, source-diversity gates, and sample thresholds. Activity-only records may support freshness, region activity, sightings, or batch mentions but never provide a denominator.

See [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) and [`docs/AI_VALIDATION.md`](docs/AI_VALIDATION.md).

## Credentials

Copy `.env.example`; never commit `.env`. Missing credentials are expected in demo/CI. Do not paste secrets into issues, logs, prompts, or chat. Secret/service-role database credentials belong only on the VPS and server-side runtime.

## Commercialization

There is no monetization code in this MVP. Before any commercial use, work through [`docs/COMMERCIALISATION_CHECKLIST.md`](docs/COMMERCIALISATION_CHECKLIST.md); this is a checklist, not a legal clearance.
