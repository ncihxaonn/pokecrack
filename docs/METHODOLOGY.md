# Statistical methodology

## Claim being made

Pokecrack reports **observed openings in the collected sample**. It does not estimate factory guarantees, identify “hot” packs, promise future pulls, rank lucky stores, or advise purchases. Selection, publication, geography, product and platform biases remain.

## Eligibility and denominator

Primary rates include an opening only if all are true: accepted validation; complete opening; known positive pack count; nonduplicate; evidence tier A/B; `statistics_eligible=true`; and the set/product/rarity maps to the versioned catalog. Tier C may support auxiliary activity; tier D is activity-only. Neither provides a denominator. Social sources default to ineligible until a documented validation proves otherwise.

The denominator is packs observed, not posts, videos, boxes or hits. The public observed rate is exactly `hit_count / pack_count`; it must never be replaced by the empirical-Bayes posterior mean. Multi-pack products contribute their verified pack count. Ambiguous partial openings are excluded rather than imputed.

## Evidence tiers

- **A:** directly countable complete opening with strong catalog match.
- **B:** complete count supported by consistent structured/context evidence.
- **C:** useful sighting/activity but incomplete denominator or weaker evidence.
- **D:** mention/discovery only.

Tier is evidence quality, not source popularity. Source policy, deterministic validation and AI agreement can only reduce eligibility, not promote unsupported evidence.

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

Defaults are `MIN_RATE_DISPLAY_PACKS=30`, `MIN_SIGNAL_PACKS=200`, `MIN_SIGNAL_SOURCES=3`, `MIN_PRACTICAL_UPLIFT=0.20`, `MIN_WATCH_PROBABILITY=0.90`, and `MIN_ANOMALY_PROBABILITY=0.95`. The tested boundaries are exact: 29 packs or only 2 independent sources hides every inference field; 30 packs with 3 sources can display the observed rate and posterior context; 199 packs cannot signal; and 200 packs with 3 sources may proceed to the probability/uplift gates. Watch must not exceed anomaly.

For `p0>0`, set `delta=(posterior_mean-p0)/p0`, `cutoff=min(1,p0*(1+MIN_PRACTICAL_UPLIFT))`, and `q=P(p>=cutoff | Beta(alpha,beta)) = 1-BetaCDF(cutoff,alpha,beta)`.

Apply labels in order:

1. `n < MIN_RATE_DISPLAY_PACKS` or independent source count `< MIN_SIGNAL_SOURCES`: **Insufficient sample** and publish null observed rate, posterior mean, baseline, interval, and delta.
2. Otherwise display the rate and posterior context. If `n < MIN_SIGNAL_PACKS`, baseline is missing/zero, or `delta < MIN_PRACTICAL_UPLIFT`: **No significant signal**.
3. All gates pass and `q >= MIN_ANOMALY_PROBABILITY`: **Possible anomaly**.
4. Else all gates pass and `q >= MIN_WATCH_PROBABILITY`: **Watch**.
5. Otherwise: **No significant signal**.

Multiple cuts and repeated monitoring increase false positives; labels are exploratory and must show the tested scope/window. Never turn a posterior probability into a guarantee. Settings/DTOs are static contracts until the aggregate implementation is run against a migrated database.

## Global country map

The global v2 map is a country-level view of the same qualifying-hit metric, not
a ranking of countries. It publishes at most one cell per official ISO alpha-2
code and selects one shared latest complete period, so countries from different
windows are never mixed. A missing cell means no public country observation; a
present insufficient cell uses a withheld pattern and exposes counts but no rate,
baseline, posterior, interval, delta, or hit numerator.

Map colours use fixed absolute scales rather than the minimum and maximum of the
current snapshot. The exact table remains authoritative. TCGdex catalog rows and
global discovery activity never create a denominator or colour a country.

## Reproducibility

Each result must retain configuration/catalog/methodology version, eligibility filters, observation window, counts, source diversity, prior/baseline identity and build SHA. Method changes create a new aggregate version; they do not silently rewrite the meaning of old screenshots/exports.
