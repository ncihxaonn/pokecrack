# Registered restricted sources

All discovered sources may be tracked, but being listed is not permission to
collect them or evidence that their pack counts are independent. Enabled source
policies remain in `config/sources.yaml`; research references stay in
`data/research/global-studies.json` and the accumulating global research batches.

## Card Shop Live — publisher authorization required

- Website: [Card Shop Live](https://cardshoplive.com/).
- Restriction evidence: [store terms, section 12](https://cardshoplive.com/policies/terms-of-service),
  reviewed earlier on 2026-09-08, prohibits spider/crawl/scrape.
- Registered as disabled, including subdomains, with no collector routes,
  zero content retention and no statistical eligibility.
- The later web-tool recheck returned a non-retryable safe-open error. This is
  a tool observation, not proof that the publisher returned HTTP403 or changed
  its policy. No alternative access route was attempted after that error.
- Vulnerability status: **not established**. A permissive robots file or an
  accessible public page is not a demonstrated access-control vulnerability.

The user may contact the publisher. A suitable factual request is: “We would
like permission to include minimal opening-study counts and source links in
PokeCrack. Your terms appear to prohibit crawling; is there an approved API,
export, or written permission for this use?” Do not claim a confirmed security
flaw without supporting evidence and an appropriately authorized assessment.

No message has been sent. Publisher permission, if obtained, must be checked
for exact scope before a reviewed policy change enables collection. This
inventory entry is not itself a live dashboard entry or production admission.

## DigitalTQ — publisher authorization required

Reviewed on 2026-09-08: [terms of use](https://www.digitaltq.com/terms-of-use),
under Use Of This Website, prohibit automated bots or scripts. Registered
disabled including subdomains, with no routes, retention or statistical eligibility.
The [151 report](https://www.digitaltq.com/pokemon-151-pull-rates-pokemon-tcg)
describes 700 boosters using both the site's own pulls and third-party sources;
this is not evidence of 700 additional independent packs. No retry or alternate
collection route was attempted after identifying the restriction. The robots
lookup failed in the web tool; this does not establish its policy or HTTP status.
No vulnerability has been established and no publisher has been contacted.
