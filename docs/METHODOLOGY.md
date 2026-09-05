# Statistical methodology

## Claim being made

Pokecrack reports **observed openings in the collected sample**. It does not estimate factory guarantees, identify “hot” packs, promise future pulls, rank lucky stores, or advise purchases. Selection, publication, geography, product and platform biases remain.

## Eligibility and denominator

Primary rates include an opening only if all are true: accepted validation; complete opening; known positive pack count; nonduplicate; evidence tier A/B; `statistics_eligible=true`; and the set/product/rarity maps to the versioned catalog. Tier C may support auxiliary activity; tier D is activity-only. Neither provides a denominator. Social sources default to ineligible until a documented validation proves otherwise.

The denominator is packs observed, not posts, videos, boxes or hits. A directly observed sample rate is exactly `hit_count / rate_pack_count`; it must never be replaced by the empirical-Bayes posterior mean or calculated from coverage rows that lack a normalized numerator. Multi-pack products contribute their verified pack count. Ambiguous partial openings are excluded rather than imputed.

## Evidence tiers

- **A:** directly countable complete opening with strong catalog match.
- **B:** complete count supported by consistent structured/context evidence.
- **C:** useful sighting/activity but incomplete denominator or weaker evidence.
- **D:** mention/discovery only.

Tier is evidence quality, not source popularity. Source policy, deterministic validation and AI agreement can only reduce eligibility, not promote unsupported evidence.

## Coverage denominator versus rate eligibility

A verified `pack_count` can be a real denominator for public coverage without
being the denominator `n` of an observed-rate calculation. Coverage-only public
studies persist to `ingest.public_study_coverage_observations`, whose schema has
no numerator or inference fields. The public projection may sum their packs and
count openings and independent source domains, but it cannot calculate a rate
from those rows. Statistical rates require separate admission to
`ingest.public_study_observations`, or an exact reviewed public-study contract
whose current verified row carries the same immutable evidence hash, with an
explicit `sir_pack` metric and qualifying-hit numerator. The public v3
projection keeps `packsObserved` separate from `ratePacksObserved`, so rows
without numerators can never dilute the displayed fraction.

The Pokesup M5 contract is ordinal 6 and deliberately stops at the coverage
ledger. Its source policy has `statistics_eligible_default=true` because that is
an invariant of the existing fenced coverage preflight; the field does not
grant statistical eligibility. Ordinal 6 is excluded from the statistical
ledger and every promotion path, and its contract contains no qualifying-hit
count, metric, or metric version. Its actual field is `pack_count=30`. After the
first verified live collection, the coverage response may show 30 packs,
1 opening, and 1 source, while numerator, observed rate, posterior, baseline,
interval, delta, and signal remain absent. `SAR` is not mapped to `SIR`.

The product version identity is `ja/M5/アビスアイ/booster_box` and
`observed_at` is the article publication timestamp. JP is Tier-B product-market
evidence (`country_code=JP`, `geography_basis=product_market`,
`geography_confidence=tier_b`), not a publisher-country, author-address, or
opening-location claim. The official
[Japanese M5 product page](https://www.pokemon-card.com/ex/m5/) corroborates
only the Japanese product identity and cannot establish any Pokesup location.

Within this M5 review, Australia (`AU`), China (`CN`), Russia (`RU`), Canada
(`CA`), Mexico (`MX`), and Brazil (`BR`) have no qualified observation. An
outline is not an observation and cannot contribute to any coverage or rate
count.

## Dedupe and quality

Canonical URL/platform IDs prevent repeat ingestion; content fingerprints and normalized opening identities catch reposts/cross-posts. Suspected duplicates are linked and excluded. Catalog/set/product/rarity consistency, count bounds, date plausibility and source policy are checked before aggregation.

## Empirical-Bayes estimate

For `h` qualifying hits among `n` eligible packs, freeze a versioned baseline probability `p0` and let `k=BAYES_PRIOR_STRENGTH` (default `50`):

```text
alpha0 = k*p0                       beta0 = k*(1-p0)
alpha  = alpha0+h                   beta  = beta0+(n-h)
posterior_mean = alpha/(alpha+beta) = (h+k*p0)/(n+k)
90% interval = [BetaQuantile(0.05, alpha, beta), BetaQuantile(0.95, alpha, beta)]
```

The baseline fallback order in `config/rarity-taxonomy.yaml` is `(set, language, product type)`, `(set, language)`, then `set`. A baseline must not be silently learned from the same comparison slice. Publish the posterior mean/interval with `n`, opening count, independent post-dedupe source-policy/provenance count, window, freshness, baseline, and methodology version.

## Exact signal algorithm and environment

Defaults are `MIN_RATE_DISPLAY_PACKS=30`, `MIN_SIGNAL_PACKS=200`, `MIN_SIGNAL_SOURCES=3`, `MIN_PRACTICAL_UPLIFT=0.20`, `MIN_WATCH_PROBABILITY=0.90`, and `MIN_ANOMALY_PROBABILITY=0.95`. `MIN_RATE_DISPLAY_PACKS` remains the aggregate-inference publication gate; it does not suppress literal reviewed arithmetic. The tested boundaries are exact: 29 packs or only 2 independent sources may show an exact `hits / rate packs` sample fraction, but must hide baseline, posterior, interval, delta, and signal; 30 packs with 3 sources may proceed to reviewed posterior context; 199 packs cannot signal; and 200 packs with 3 sources may proceed to the probability/uplift gates. Watch must not exceed anomaly.

For `p0>0`, set `delta=(posterior_mean-p0)/p0`, `cutoff=min(1,p0*(1+MIN_PRACTICAL_UPLIFT))`, and `q=P(p>=cutoff | Beta(alpha,beta)) = 1-BetaCDF(cutoff,alpha,beta)`.

Apply labels in order:

1. If an exact normalized numerator and denominator exist, publish their literal descriptive sample fraction and rate; otherwise publish no rate.
2. `n < MIN_RATE_DISPLAY_PACKS` or independent source count `< MIN_SIGNAL_SOURCES`: **Insufficient sample** and publish null posterior mean, baseline, interval, delta, and signal even when the raw sample rate is visible.
3. Otherwise the reviewed aggregate publisher may display posterior context. If `n < MIN_SIGNAL_PACKS`, baseline is missing/zero, or `delta < MIN_PRACTICAL_UPLIFT`: **No significant signal**.
4. All gates pass and `q >= MIN_ANOMALY_PROBABILITY`: **Possible anomaly**.
5. Else all gates pass and `q >= MIN_WATCH_PROBABILITY`: **Watch**.
6. Otherwise: **No significant signal**.

Multiple cuts and repeated monitoring increase false positives; labels are exploratory and must show the tested scope/window. Never turn a posterior probability into a guarantee. Settings/DTOs are static contracts until the aggregate implementation is run against a migrated database.

## Global country map

The global v3 map is a country-level view of the same qualifying-hit metric, not
a ranking of countries. It publishes at most one cell per official ISO alpha-2
code and selects one shared latest complete period, so countries from different
windows are never mixed. A missing cell means no public country observation; a
present cell exposes verified coverage counts. It uses the quantitative rate
scale only when an exact normalized numerator and separate rate denominator are
available; otherwise it uses the no-numerator pattern. Baseline, posterior,
interval, delta, and signal remain independently gated.

A threshold-sufficient denominator does not become a published inference merely
because its count gates are met. If the versioned baseline, posterior, and
interval publisher has not completed, v3 keeps the row visible as **Inference
pending** and continues to return every inference field as null. The pending
state is an operational publication state, not a fifth statistical signal.

Map colours use fixed absolute scales rather than the minimum and maximum of the
current snapshot. The exact table remains authoritative. TCGdex catalog rows and
global discovery activity never create a denominator or colour a country.

The **Pack coverage** layer uses a fixed absolute 0–1,500 pack scale to show
verified sample volume by country. It is not a hit-rate comparison or an
estimate of representative demand. The **Observed rate** layer shows direct
sample arithmetic wherever exact counts exist, regardless of sample size. The
**Baseline delta** layer still follows the inference thresholds, while countries
without a reviewed observation remain neutral.

The original five reviewed public-study inputs use publisher country as a
coarse Tier-B geography basis. They do not assert the physical opening location
and must not be shown as city/store evidence. They span US, GB, and SG: 91
verified packs from two independent domains in the United States, 107 from two
in the United Kingdom, and 54 from one in Singapore. Pokesup ordinal 6 is the
first product-market case. The phase-one Asia contracts also use product-market
attribution for South Korea, Taiwan, and Thailand. Their verified denominators
are JP 30, KR 30, TW 40, and TH 10 packs; none has a normalized SIR numerator,
so none publishes a sample rate or enters a statistical cohort.

## Authorized opening review and aggregate admission

An accepted authorized-opening submission is not automatically a statistical
input. Before it can enter a private aggregate cohort, an owner must record an
immutable binding from the opaque authorized-source identity to one explicitly
declared independent source domain, then admit the exact accepted observation
through a separate immutable admission record. An authorized admission's
canonical opening fingerprint must equal its immutable private provenance HMAC;
the same collision namespace is reserved for reviewed public studies. A source
identity mapped to conflicting independent domains fails closed rather than
counting toward source diversity.

The cohort resolver is evaluated **as of** a timestamp: it includes only an
admitted observation whose authorization was valid when accepted, whose catalog
and denominator contract still match, and which had not been retracted by that
time. Retraction excludes the observation from later cohorts without mutating
the accepted evidence needed to reproduce an earlier one. This bridge is a
private input contract only; it does not calculate a posterior, publish a rate,
or colour the country map. Bluesky, Nostr, Mastodon, YouTube, and other social
discovery records remain discovery-only unless separately reviewed as complete
opening evidence under this contract.

## Reproducibility

Each result must retain configuration/catalog/methodology version, eligibility filters, observation window, counts, source diversity, prior/baseline identity and build SHA. Method changes create a new aggregate version; they do not silently rewrite the meaning of old screenshots/exports.
