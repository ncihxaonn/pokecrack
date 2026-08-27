# Operations runbook

## Routine checks

Daily for the released TCGdex core: collector, scheduler, and watchdog healthy; no non-core containers; catalog job backlog/lease expiry; `catalog.sync_state` freshness/item count; database/storage/egress thresholds; backup marker age/size; and TCGdex terms/API errors. Weekly: failed jobs, unused images, provenance checks, and restore-drill schedule. Monthly: source/terms review, dependency/image updates, access review, key rotation plan and free-tier capacity trend. AI/browser checks are not part of this release.

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

Deploy only a reviewed exact 40-character SHA with `deploy/scripts/deploy.sh --service-set tcgdex`. The atomic manifest advances only after the exact three-service set is healthy and records that set; it never claims a full deployment. If a release fails, preserve status/health evidence, choose a known-good post-migration-compatible commit and run `deploy/scripts/rollback.sh EXPLICIT_SHA --service-set tcgdex`; database rollback is never automatic. The script does not stop pre-existing non-core containers—retire those only through a separately approved operation.

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
