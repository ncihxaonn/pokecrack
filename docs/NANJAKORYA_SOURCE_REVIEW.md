# Star Birth 100-pack report: reviewed admission contract

Reviewed 2026-09-08 for the worldwide multi-source dataset. Original source:
<https://nanjakorya.com/1123>. This is one 100-pack cohort, not nine independent
sources; the nine consecutive opening segments cover 1–100 without overlap.
The 31–50 segment consists of the packs from a premium trainer box, not its
guaranteed separate cards. The sample mixes loose packs and that product.

## Access and provenance

The exact article and robots URL returned HTTP200 on MAM, using the declared
`PokecrackMetadataCollector/0.1 (+https://pokecrack.vercel.app)` agent.
`https://nanjakorya.com/robots.txt` allows the article; only the WordPress admin
path is disallowed. Article and homepage navigation plus a site-specific search
did not reveal separate terms/privacy pages. This is not a permission grant.
The copyright footer remains applicable. Scope is limited to noncreative
numerical facts, short product/rarity labels, source link and evidence digest;
no article-body or media copying/retention. Recheck access/rights before enabling
the route and disable it on relevant drift. No credentials or outreach used.

Article metadata consistently supplies publication2022-02-22T05:40:46+09:00 and
modification2022-06-03T20:00:22+09:00. Neither timestamp proves when the packs
were physically opened. Physical country is unknown; Japanese language/product
does not establish an opening location.

The [official S9 product page](https://www.pokemon-card.com/ex/s9/index.html)
confirms Japanese Star Birth and its2022-01-14 release. The
[official premium trainer product](https://www.pokemon-card.com/products/s/sk.html)
confirms twenty S9 packs are included separately from guaranteed product cards.
These product pages do not prove any opening or publisher location.

## Exact counts and live parser check

RR16, RRR6, SR4, HR1 across100packs. These are rarity **card** counts, not an
SIR numerator and not independent probabilities that may be summed across slots.
The deterministic parser verifies every reported segment against its count tuple
and rejects missing, duplicate or changed segments. It keeps publication and
opening timestamps separate and performs no network calls or admission itself.

On MAM, an isolated capped container fetched robots and the exact article with
redirects disabled, parsed the live HTML in memory, and returned these counts.
No raw HTML/media was saved. A fresh MAM check on 2026-09-08 verified the live
adapter and robots policy with redirects disabled and a 30-second request gap.
The complete report digest (including premium-box attribution) is
`b5dc75b772fb6b63a198c72f43193e76e2fd48f332ec546dd1800062640552ad`.
The minimal retained title excerpt digest is separately
`e9c87d754c51746c9af0cf3c85d164bfee5bf90c84e69e8c65ca46cfda2601e9`.
The adapter validates the complete report before returning that short excerpt.
Structured policy facts retain RR16/RRR6/SR4/HR1, the 80/20 pack split, and
explicit null opening country/date. These counts never populate SIR fields.

## Remaining release work

The source is registered under the single cohort key
`nanjakorya-star-birth-jp-100-v1`, append-only contract ordinal 27.
Migration creation used Supabase CLI 2.116.0 on MAM; the generated timestamp
20260908020719 is ordered after the existing future-dated ledger as 20261013.
The public source note distinguishes native card counts from pack rates and
product-market geography from unknown physical opening location. Run full Worker,
database (if changed), backup-contract and Web checks, structured review,
GitHub release and runtime verification before claiming new live data.

## Other candidate excluded from automatic collection

Card Shop Live's1728-pack Scarlet & Violet report has explicit counts but its
store terms section12 prohibit spider/crawl/scrape. Robots allow does not
override that source-policy restriction. Do not enable its collector, bypass
the restriction through another route, or contact the publisher. Keep searching
other primary sources. This restriction does not block independent sources.
