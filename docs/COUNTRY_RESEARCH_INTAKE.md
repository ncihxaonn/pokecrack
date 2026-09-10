# Country research intake

The manual country research workflow searches the 249 ISO country/area entries
in `scripts/country_targets.py`, in regional order. A successful sweep is
research coverage, **not** proof that every country has qualifying opening data.
An empty search result does not mean zero real-world openings. The map and its
public counts continue to use independently verified observations only.

## Reference-to-evidence bridge

1. The MAM research process has bounded web-search access and no production
   database credentials. Its output is untrusted research, not executable policy.
2. The separate publishing step validates the unified research ledger and
   reconstructs the deduplicated country ledger. It saves that research record
   and ledger artifact **before** attempting runtime intake.
3. `scripts/research_intake.py` produces a strict, count-free manifest: canonical
   HTTPS reference URLs, report-group hashes, conflict flags and a snapshot hash.
   It does not transmit pack counts, country claims, prose or media.
4. The SSH bridge targets only `/home/codex/pokecrack` on the approved MAM VPS.
   It requires the running collector image and installed checkout to match the
   exact GitHub workflow revision, then calls `pokecrack-worker intake-research`
   over stdin. A workflow/checkout/image mismatch pauses intake until the same
   reviewed revision is deployed; the durable history retries on a later run.
5. The collector uses its existing database connection for one private,
   transactionally bounded import. It cannot directly read/update the intake
   tables or enable the feature. Browser roles cannot access the importer.
6. Only exact URLs within an already-approved source family and reviewed
   product scope can enter that family's pending-evidence queue. Fixed-contract
   duplicates, owner tombstones, unreviewed products and conflicting references
   cannot create a new fetch candidate. Existing source request gates, policy
   expiry, job leases, evidence parsing, cohort identity and admission checks
   still apply before any public denominator changes.

Unknown websites remain private references; this version does **not** authorize
generic crawling or automatically approve a new host, product or adapter.
Denied/challenged sources are not bypassed. Missing opening location is never
inferred from the country search, language, domain or publisher address.

## Idempotency and bounds

- Repeated URLs have one durable reference row. The report-group hash identifies
  a research grouping, not proof of independent physical packs. Full report
  provenance remains in the validated unified research ledger.
- Conflict flags are sticky. Later research cannot silently clear them. They
  block new candidate creation; untrusted research also cannot retract an
  already independently admitted observation. Retractions use the reviewed
  owner/family workflow.
- Manifests are limited to 2 MiB and 10,000 references. The private queue has a
  10,000-reference operational cap. Overflow fails atomically instead of
  silently dropping or evicting research; it requires a reviewed capacity or
  retention change. This is a bounded first bridge, not unlimited ingestion.
- On intake failure, the report is already durable. Subsequent runs rebuild
  the full history and retry idempotently. A failed SSH/database call cannot
  mark a reference as published or move research counts into public statistics.
- Public logs/result artifacts contain only bounded scalar counts and hashes.
  No private connection string is given to the workflow or research process.

## Activation and release gates

Both gates default off:

- repository variable `COUNTRY_RESEARCH_INTAKE_ENABLED=true` enables the final
  workflow bridge step;
- owner-controlled `ingest.research_intake_control.enabled=true` permits writes
  through the private importer.

Activate only after reviewed GitHub merge, passing full CI, a fresh encrypted
production backup with isolated restore verification, migration to the approved
Personal Supabase project, and reviewed MAM deployment of that same revision.
Verify identity, target and existing approvals before either control change.
The SQL activation is an owner operation, never a collector privilege.
Pause either gate to stop intake; neither control changes existing public data.

Backups retain only the exact minimal reference schema, canonical links, hashes,
conflict flags and timestamps. The sanitizer validates both tables and always
rewrites intake enablement to **false** in restored copies. Schema drift,
additional payload columns, permissive policies, missing controls and duplicate
or malformed rows fail before a backup is emitted.

## Verification before claiming success

Check the workflow's count-only intake artifact against the deployed revision,
then inspect the owner-visible private queue counts and the existing family's
normal scheduled jobs. A reference insertion or pending-evidence job is not an
admission. Claim new live packs only after the independent admission, public RPC
and rendered site agree. An unchanged count is legitimate when no new eligible,
nonduplicate opening has been verified. This bridge alone does not close every
production-readiness item in `docs/IMPLEMENTATION_NOTES.md`.
