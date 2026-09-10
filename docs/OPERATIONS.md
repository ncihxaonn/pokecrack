# Operations runbook

## Routine checks

For each released TCGdex UTC window (02:00 and 14:00): collector, scheduler, and watchdog healthy; no non-core containers; catalog job backlog/lease expiry; `catalog.sync_state` freshness/item count; database/storage/egress thresholds; backup marker age/size; and TCGdex terms/API errors. The durable slot list should show at most one catalog job per window; a missed window is eligible for bounded catch-up. After a release, run the optional aggregate verifier with the exact deployment SHA and release start:

```bash
deploy/scripts/verify-runtime-release.sh EXACT_LOWERCASE_40_CHARACTER_SHA \
  --env-file /etc/pokecrack/production.env \
  --service-set tcgdex \
  --release-started-at 2026-09-03T00:00:00Z
```

Treat `healthy` as advancing evidence, `warming_up` as an expected first-run
grace state, exit 1 as a release failure, and exit 2 as `inconclusive` (schema,
role, service-set, running-image, or marker evidence unavailable). Missing or
unreadable backup markers stay inconclusive during grace; do not broaden the
owner-only backup directory to make them readable. For a Nostr release, pass
`--service-set tcgdex-nostr --nostr-env-file /etc/pokecrack/nostr.env`; this
explicitly scopes the expected Nostr heartbeat, checkpoint, and schedules. The
same command supports Bluesky with
`--service-set tcgdex-bluesky --bluesky-env-file /etc/pokecrack/bluesky.env`;
that service set is mandatory during deployment, forces `--require-healthy`,
and scopes the Bluesky worker, policy, schedule, queue, and durable cursor.
The command is read-only and emits
only safe aggregates; do not paste environment files or container inspection
into an incident. Weekly: failed jobs, unused images, provenance checks, and
restore-drill schedule. Monthly: source/terms
review, dependency/image updates, access review, key rotation plan and
free-tier capacity trend.
AI/browser checks are not part of this release.

Use the secret environment file without printing expanded config:

```bash
export DEPLOY_SHA="$(git rev-parse HEAD)"
docker compose --env-file /etc/pokecrack/production.env \
  -f deploy/compose.prod.yml ps
docker compose --env-file /etc/pokecrack/production.env \
  -f deploy/compose.prod.yml exec -T collector pokecrack-worker health
```

Review logs narrowly and redact before sharing. Never run `docker compose config` without `--quiet` against real secrets.

## Release and rollback

Deploy only a reviewed exact 40-character SHA with `deploy/scripts/deploy.sh --service-set tcgdex`. The script rejects an existing explicit `SCHEDULE_CATALOG_SYNC=0 2 * * *` (including quoted dotenv values or an inherited shell value) before checkout or Compose activity, because that retired once-daily value would silently disable the 14:00 UTC window. It leaves other deliberate operator overrides untouched; an omitted value uses the checked-in `0 2,14 * * *` default. The atomic manifest advances only after the exact three-service set is healthy and records that set; it never claims a full deployment. If a release fails, preserve status/health evidence, choose a known-good post-migration-compatible commit and run `deploy/scripts/rollback.sh EXPLICIT_SHA --service-set tcgdex`; database rollback is never automatic. The script does not stop pre-existing non-core containers—retire those only through a separately approved operation.

Run `deploy/scripts/cleanup.sh --env-file /etc/pokecrack/production.env` periodically. It removes stopped project containers and unused labeled images only; profiles, extensions, backups and volumes are preserved.

## Alerts and thresholds

Defaults warn/critically alert around database 350/425 MB, storage 700/850 MB and monthly egress 3.5 GB. These are operational thresholds, not guaranteed provider telemetry. Configure a supported metric source or enter verified values; never fabricate usage. AI daily/monthly budget breach pauses calls. Backup age, worker heartbeat expiry, repeated auth failure, queue growth and source 403/429 are actionable alerts. Optional SMTP credentials stay VPS-only.

## Incident playbooks

- **Source block/terms change:** disable source policy, stop retries, preserve minimal audit metadata, review terms/robots, delete retained content if required.
- **Credential/profile concern:** stop `auth-browser`, revoke sessions/API keys, restrict profile volume, rotate noVNC/SSH/provider secrets, inspect access logs; do not archive cookies for analysis.
- **AI anomaly/cost spike:** disable live provider, retain bounded run/version metadata, use fixture mode, investigate prompts/model/version and budget ledger.
- **Database pressure:** stop new collection before destructive cleanup; back up, identify retention-safe private rows, verify public aggregates, then prune through reviewed jobs.
- **Bad deployment:** do not advance success manually; explicit code rollback, then investigate. Use a forward migration for schema repair.
- **Backup failure:** alert immediately, keep prior backups, fix credentials/disk, rerun and perform a fresh restore drill.

For browser reauthentication, use the exact SSH tunnel in `OPENCLI_VPS.md`; manual CAPTCHA/2FA only. Record incident timeline, affected data/accounts, revocations, recovery SHA and follow-up controls without embedding secrets.

### Fixed public-study source pauses

An operator may disable a reviewed fixed source using its existing exact
`ingest.source_policies` row. A disabled source is an operational pause, not a
missing shared service dependency: health still requires all reviewed source
identities, configuration bounds, tables, least-privilege ACLs and fenced RPCs.
This does not authorize collection from a disabled source. Its begin/finalize
gates and the live public projections continue to require `enabled=true`.
An already-running HTTP request cannot be recalled by a later policy change.

This health distinction does not delete observations, remove source-link
metadata, change fixed daily schedules, or retry rejected jobs. Existing queued
or scheduled jobs remain subject to the disabled-policy rejection; investigate
their source-specific failures independently of the shared heartbeat. Public
source metadata may remain visible with a paused status. Any required content
or link removal needs its own exact scope; do not treat a healthy heartbeat as
proof that a paused source has been removed or reauthorized.
