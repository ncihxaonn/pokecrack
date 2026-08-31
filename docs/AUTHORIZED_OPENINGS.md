# Authorized opening evidence

This operator path is for a person who has verified that an opening bundle is
authorized to be submitted and reviewed. It is not a social-media scraper, an
automatic promotion path, or permission to republish a creator's content.
YouTube, Bluesky, and Nostr discovery remain activity-only. A discovery match
may help an owner find evidence, but it cannot become an opening observation
without separate authorization and human review.

## Privacy boundary

The version `1.0.0` JSONL bundle contains exactly one flat object per line and
never contains a URL, post text, handle, author name, account ID, raw response,
media, cookie, token, or database credential. It carries only:

- a stable opaque submission key;
- an optional discovery platform (`youtube`, `bluesky`, `nostr`, or `direct`)
  and optional discovery-candidate SHA-256;
- owner-produced, domain-separated **HMAC-SHA-256** references for source
  identity, authorization, and provenance deduplication;
- a SHA-256 of the separately controlled evidence artifact;
- the reviewed country, geography basis/confidence, language, TCGdex set,
  product scope, observation time, complete pack denominator, qualifying-hit
  pack count, and requested eligibility.

Do not create the identity, authorization, or provenance references with an
ordinary SHA-256 of a low-entropy handle, URL, email address, or name. Produce
them outside this CLI using an owner-held secret and domain-separated HMAC
canonicalization. The CLI accepts the resulting lowercase 64-character
fingerprints only; it never accepts or stores the raw inputs. Keep the evidence
artifact and authorization record in the owner's approved private evidence
store, not in Git or the JSONL bundle.

The validator rejects unknown or duplicate JSON keys, non-canonical Unicode,
control characters, non-canonical UTC timestamps, non-ISO countries, language
or TCGdex ID drift, incomplete denominators, booleans masquerading as numbers,
oversized files, and duplicate submission/provenance identities. One bundle is
submitted in one explicit database transaction.

## Operator workflow

Validate locally without a database connection:

```bash
cd services/worker
uv run pokecrack-worker authorized-opening submit /secure/path/bundle.jsonl --dry-run
```

Dry-run output contains counts only. It does not print the path, payload,
fingerprints, country facts, or a database URL.

Live submission requires `DATA_MODE=live` and the ordinary bounded submit DSN
in `SUPABASE_DB_URL`:

```bash
uv run pokecrack-worker authorized-opening submit /secure/path/bundle.jsonl
```

Review access is deliberately separate. `list`, `review`, and `retract` require
a dedicated review-role connection in `AUTHORIZED_OPENING_REVIEW_DB_URL`; they
do not read or require `SUPABASE_DB_URL`. The database role can invoke only the
list, review, and retraction RPCs and has no direct table access. Live
review/retraction also requires an
owner-held secret of at least 32 bytes in
`AUTHORIZED_OPENING_REVIEW_HMAC_KEY`. The secret stays in the VPS secret store
and is never passed as a command argument or printed.

```bash
uv run pokecrack-worker authorized-opening list --state queued --limit 50
uv run pokecrack-worker authorized-opening review \
  11111111-1111-4111-8111-111111111111 \
  --expected-revision 1 \
  --decision in_review \
  --actor reviewer-01 \
  --reason review_started
```

The raw actor is NFKC-validated and converted locally to a domain-separated
HMAC reference. It is never sent to PostgreSQL or printed. Review transitions
are revision-fenced and reason-coded:

- `in_review`: `review_started`
- `accepted_statistics`: `evidence_verified`
- `accepted_activity_only`: `activity_only`
- `duplicate`: `duplicate_provenance` or `duplicate_source`
- `rejected`: `authorization_invalid`, `evidence_incomplete`,
  `geography_unverified`, `denominator_incomplete`, or `reviewer_rejected`
- `expired`: `policy_expired`

`queued` is submit-only. The normal path is `queued` to `in_review` and then one
terminal decision. CLI output is restricted to UUIDs, revision/state, counts,
and the bounded non-identity facts needed for review. Submission keys and all
fingerprints remain suppressed.

Authorization withdrawal, evidence correction, privacy requests, and policy
takedowns use the reviewer-only append-only retraction path:

```bash
uv run pokecrack-worker authorized-opening retract \
  22222222-2222-4222-8222-222222222222 \
  --actor reviewer-01 \
  --reason privacy_request
```

The exact retraction reasons are `authorization_revoked`, `evidence_corrected`,
`privacy_request`, and `policy_takedown`. A retraction never rewrites immutable
evidence history; it appends a fenced audit event and excludes the observation
from subsequent publication. Live output contains only the observation UUID
and `retracted` status.

## Publication boundary

`statisticsEligible: true` is only a request for review. It does not establish
authorization, eligibility, independence, geography, or a published rate.
Acceptance still requires a complete denominator, verified evidence, a current
TCGdex set, valid authorization, and the database's immutable review checks.
Accepted activity-only records never enter rate statistics.

Even an accepted statistical opening does not directly color the world map.
Country rates remain withheld until the independent-source and pack thresholds
are met and the separately reviewed aggregate publisher calculates the fixed,
auditable methodology. Sparse or one-source countries must continue to display
coverage/insufficient-sample state rather than a fabricated hit rate.
