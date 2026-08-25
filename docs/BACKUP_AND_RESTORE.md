# Backup and restore

## Database backup

`deploy/scripts/backup.sh` requires `pg_dump`, `gzip`, Python and either `SUPABASE_DB_URL_FILE` (preferred) or `SUPABASE_DB_URL`. It keeps the URL out of process arguments/output, writes with umask `077`, creates `pokecrack-YYYYMMDDTHHMMSSZ.sql.gz`, validates compressed and non-empty uncompressed content, moves atomically, then writes `.last-successful-backup`.

Defaults retain the newest backup on each of the newest 7 UTC dates plus the newest backup in each of the newest 4 ISO weeks (union). Unknown files are untouched and every managed deletion is logged. Schedule from a restricted systemd timer/cron environment, for example:

```bash
SUPABASE_DB_URL_FILE=/etc/pokecrack/supabase-db-url \
BACKUP_DIR=/opt/pokecrack/backups \
deploy/scripts/backup.sh
```

Alert on nonzero exit, stale/missing marker, unexpected size change and low disk. A success marker proves local dump validation, not off-site durability or restorability.

## Off-site and profile policy

Encrypt database backups before transfer, use a destination/account separate from the VPS, restrict retention/access, and test key recovery. Never commit/upload unencrypted dumps. Persistent browser profiles contain live cookies/tokens and are excluded by default; `PROFILE_BACKUP_ENABLED=false`. Prefer reauthentication. Any encrypted profile backup needs separate threat review, key file outside the VPS backup, short retention and tested revocation.

## Restore drill (fresh isolated target)

Never test against production. Provision a fresh disposable PostgreSQL/Supabase-compatible target with no public access and enough capacity. Select a retained file by explicit name and verify gzip before connecting:

```bash
BACKUP=/opt/pokecrack/backups/pokecrack-YYYYMMDDTHHMMSSZ.sql.gz
gzip --test "$BACKUP"
export PGDATABASE="$RESTORE_DB_URL"
gzip --decompress --stdout "$BACKUP" | psql --set ON_ERROR_STOP=on
unset PGDATABASE RESTORE_DB_URL
```

Because the dump omits owner/privilege restoration, apply the reviewed role/grant/RLS configuration appropriate to the fresh project. Then verify: all migration/schema objects; expected table counts/ranges; foreign-key integrity; statistics-eligibility constraints; private schemas unavailable to anon/authenticated; intended public-safe reads; no credentials/session cookies in tables; and application fixture/live smoke behavior. Record backup filename/checksum, source SHA/migration set, drill target, duration, checks performed, failures and destruction confirmation. Destroy/sanitize the drill target afterward.

## Production recovery

Declare an incident, stop writers/collectors, identify the recovery point and affected migrations, preserve evidence, restore to a fresh target first, validate, then cut over credentials deliberately. Do not pipe a dump into the live database as an ad-hoc rollback. Schema defects get a reviewed forward migration. Rotate DB credentials after a suspected backup leak.
