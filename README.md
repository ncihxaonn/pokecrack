# Pokecrack

> **Working name.** Trademark, domain, and commercial-use clearance have not been performed.

**Crack open the data behind every pack.**

Pokecrack is a free, personal, experimental, non-commercial and unofficial dashboard for **observed** Pokémon TCG physical pack-opening activity across sets, products, regions, retailers, and visible batch/lot codes.

> Observed results do not guarantee the contents of any individual pack, box, product, batch or store purchase.

Pokecrack is not affiliated with, endorsed by, or sponsored by The Pokémon Company, Nintendo, Game Freak or Creatures. It is not a gambling product, buying bot, “hot pack” predictor, store luck leaderboard, or guarantee of future pull rates.

## Architecture

```text
Private GitHub monorepo
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

The everyday pipeline runs on the VPS. A personal computer is used only to open an SSH tunnel to the VPS-local noVNC listener for first login, CAPTCHA, or two-factor authentication; it does not run scheduled collection or AI processing.

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
pnpm install --frozen-lockfile
pnpm lint
pnpm typecheck
pnpm test
pnpm build

cd services/worker
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy pokecrack_worker
uv run pytest

cd ../auth-browser
uv sync --frozen
uv run ruff check .
uv run ruff format --check .
uv run mypy src/pokecrack_browser
uv run pytest

cd ../..
npx supabase@2.115.0 start
npx supabase@2.115.0 db reset
npx supabase@2.115.0 test db

DEPLOY_SHA=0000000000000000000000000000000000000000 docker compose -f deploy/compose.prod.yml config --quiet
docker compose -f deploy/compose.prod.yml build
```

The Supabase and Docker build commands require a running Docker daemon. Never report them as passed when only static configuration validation ran.

## Live setup

1. Create a dedicated **Supabase Free organization and project**; apply migrations and create the first admin account with signup disabled.
2. Create a **Vercel Hobby** project rooted at `apps/web`; configure only public Supabase values in browser-visible variables and server secrets in Vercel settings.
3. Prepare the VPS as a non-root deploy user, clone the private repository using a dedicated deploy key, create `/opt/pokecrack/{browser-profiles,backups,opencli-extension}`, and set profile permissions to `0700`.
4. Pin and install an audited OpenCLI CLI/Browser Bridge release with its SHA-256; do not use a floating `latest` artifact.
5. Start Compose, tunnel `6080` over SSH, log into each permitted platform profile, run the browser doctor, and close the tunnel.
6. Configure daily `pg_dump` backups and test restore into a fresh project.

Exact account-owner steps are in:

- [`docs/DEPLOYMENT.md`](docs/DEPLOYMENT.md)
- [`docs/OPENCLI_VPS.md`](docs/OPENCLI_VPS.md)
- [`docs/BACKUP_AND_RESTORE.md`](docs/BACKUP_AND_RESTORE.md)
- [`docs/SECURITY.md`](docs/SECURITY.md)
- [`docs/OPERATIONS.md`](docs/OPERATIONS.md)

## Methodology summary

Only records that are accepted, complete openings, statistics-eligible, non-duplicate, and evidence tier A/B enter primary pull-rate statistics. Activity-only records may support freshness, region activity, sightings, or batch mentions but never provide a denominator. Signals use configurable minimum samples, independent-source counts, empirical-Bayes shrinkage, 90% credible intervals, and probability thresholds. Labels are deliberately limited to **Insufficient sample**, **No significant signal**, **Watch**, and **Possible anomaly**.

See [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md) and [`docs/AI_VALIDATION.md`](docs/AI_VALIDATION.md).

## Credentials

Copy `.env.example`; never commit `.env`. Missing credentials are expected in demo/CI. Do not paste secrets into issues, logs, prompts, or chat. Secret/service-role database credentials belong only on the VPS and server-side runtime.

## Commercialization

There is no monetization code in this MVP. Before any commercial use, work through [`docs/COMMERCIALISATION_CHECKLIST.md`](docs/COMMERCIALISATION_CHECKLIST.md); this is a checklist, not a legal clearance.
