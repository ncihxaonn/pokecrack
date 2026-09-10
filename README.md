# Pokecrack — Pokémon TCG Pull Rates & Pack-Opening Data

Pokecrack is a public research dashboard for exploring Pokémon TCG pack-opening data, set coverage, and evidence-backed pull-rate summaries. It brings observed Pokémon card pull rates, product context, regional activity, and source evidence into one readable place so collectors can see what has actually been documented and how much evidence supports each view.

**Explore the live dashboard:** [pokecrack.vercel.app](https://pokecrack.vercel.app)

## What you can explore

- Observed openings across Pokémon TCG sets and sealed products.
- Pokémon card pull-rate and hit-rate summaries when an exact qualifying-hit count and eligible pack denominator are available.
- Global coverage by country or product-market bucket.
- Set and product context from the tracked Pokémon TCG catalog.
- Recent source activity, observation periods, and data freshness.
- Visible batch, lot, and retailer context without turning activity into a ranking or prediction.

## How it works

```text
Opening evidence → review and normalization → coverage checks → public summaries
```

1. Opening evidence is collected from documented public or authorized sources.
2. Set, product, pack, hit, region, and date fields are normalized for comparison.
3. Duplicates, incomplete openings, and ambiguous records are kept out of rate calculations.
4. Public views show the strongest supported result: activity, coverage, a descriptive sample rate, or a reviewed statistical summary.

## Reading the numbers

- **Observed packs** means packs with a verified denominator in the reviewed sample. A post, video, box, or hit by itself is not a pack denominator.
- **Observed hit rate** is the literal qualifying-hit pack count divided by eligible packs when both counts are known and aligned.
- Small or incomplete samples may still be useful for coverage and discovery, but they are not presented as representative Pokémon booster pack odds.
- Set, product, region, sample size, source diversity, and observation period provide the context needed to interpret every summary.

The detailed methodology is documented in [`docs/METHODOLOGY.md`](docs/METHODOLOGY.md).

## Why Pokecrack exists

Pull-rate discussions are often built from isolated openings, incomplete counts, or memorable hits. Pokecrack is designed to make the underlying evidence easier to inspect: what was observed, what can be counted, where coverage is strong, and where the available sample is still too thin for a meaningful comparison.

## What Pokecrack is — and is not

Pokecrack is an unofficial Pokémon TCG data explorer for collectors, hobby researchers, and anyone interested in pack-opening patterns.

It is not a guarantee of future pulls, a “hot pack” predictor, a buying bot, a gambling product, or a ranking of lucky stores and retailers. Observed results do not guarantee the contents of any individual pack, box, product, batch, or purchase.

## Run locally

Requirements: Node.js 22.13 or newer and pnpm 11.23.0 or newer.

```bash
pnpm install --frozen-lockfile
pnpm dev
```

Open <http://localhost:3000>.

For contribution guidelines, see [`CONTRIBUTING.md`](CONTRIBUTING.md).

## Scope and attribution

Pokecrack is free for research and community education. Pokémon, Pokémon TCG, and related names and marks belong to their respective owners. Pokecrack is not affiliated with, endorsed by, or sponsored by The Pokémon Company, Nintendo, Game Freak, or Creatures.

Please preserve source attribution, evidence context, denominator information, and the distinction between observed activity and statistical inference when extending the project.
