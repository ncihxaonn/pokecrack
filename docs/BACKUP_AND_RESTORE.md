# Backup and restore

## Database backup

`deploy/scripts/backup.sh` requires PostgreSQL 17 `pg_dump`/`psql`, `gzip`, Python and either `SUPABASE_DB_URL_FILE` (preferred) or `SUPABASE_DB_URL`. The URL must explicitly use `sslmode=require`, `verify-ca`, or `verify-full`. The login in that DSN must be allowed to `SET ROLE service_role`; `pg_dump` does so explicitly because inherited membership alone does not inherit the role's `BYPASSRLS` attribute, and each independent `psql` preflight session starts with the same explicit role switch. A fixed runner receives the URL only on standard input, validates its shape, removes every inherited `PG*` variable, and maps only allowlisted URL fields into the libpq child environment for `psql` or `pg_dump`. The URL therefore stays out of child arguments and normal output. The script writes with umask `077`, creates `pokecrack-YYYYMMDDTHHMMSSZ.sql.gz`, validates compressed and non-empty uncompressed content, moves atomically, then writes `.last-successful-backup`.

Before compression, the plain dump passes through a fail-closed retention sanitizer. It accepts only coherent migration states: the pre-YouTube schema has neither the exact policy nor the cache table; the post-YouTube schema has both the exact policy and exactly one supported `CREATE UNLOGGED TABLE ingest.youtube_discoveries`; the optional post-public-study state additionally has all five reviewed source policies plus one regular `ingest.public_study_observations` ledger; the Bluesky state requires its exact policy plus all three regular private tables; and the Nostr state introduced by migration `20260906000000` requires exactly three reviewed relay policies plus all three regular private tables (`ingest.nostr_relay_candidates`, `ingest.nostr_relay_observations`, and `ingest.nostr_relay_checkpoints`). In those final states, retained checkpoints must be non-demo rows bound to their exact preflight policy, relay key, endpoint, protocol, and canonical non-negative counters (one row per relay for Nostr). The public-study ledger's PostgreSQL column/type inventory, check-constraint inventory, exact `COPY` column order, reviewed study identities, source-policy binding, UUIDs, UTC timestamps, facts, versions, and SHA-256 evidence hashes are all validated before any dump byte is emitted. Any extra column (including raw HTML), unexpected study, escaped text, or row/schema drift fails closed. YouTube cache rows and all Bluesky/Nostr candidate and observation rows are removed while their schemas remain available from the dump; Bluesky and Nostr checkpoints are retained so a restore cannot silently replay an unbounded stream. Nostr candidate/observation data—including raw content, public keys, signatures, and event IDs—is never retained in a logical backup. The regular `ingest.source_request_gates` schema must appear exactly once with the exact PostgreSQL 17 columns, checks, primary key, forced/enabled RLS, and zero row-level security policies. `pg_dump` excludes that table's data plus all disposable Bluesky/Nostr activity rows; the sanitizer independently rejects any gate or private-activity `COPY`/`INSERT`, then inserts only the canonical TCGdex, YouTube, Bluesky, three Nostr relay, and five reviewed public-study source keys with null lease ownership immediately before the dump enables RLS. This prevents a restored database from inheriting a live or stale collector lock and does not require a restore role with `BYPASSRLS` for those canonical rows.

PostgreSQL 17 `MAINTAIN` is granted to `service_role` only because `pg_dump` must take the gate table's schema lock even when its data is excluded. The role still has no `SELECT` or row-mutation privilege on that table. `MAINTAIN` can also perform table-maintenance operations, so separating a dedicated `NOINHERIT` backup login/role from the worker credential remains a release prerequisite; the current grant is a bounded compatibility step, not the desired steady-state credential model.

A partial state, logged/temporary/duplicate/unsupported target definition, any request-gate policy, missing/duplicate TCGdex policy, or preflight/dump mismatch fails before any output byte is produced. Generic `ingest.source_items` rows are not selected or removed. The raw snapshot is spooled only to an unlinked mode-`0600` temporary file. Role-switched `psql` sessions independently validate the live state without putting the database URL in arguments; the dump mapping remains authoritative and any malformed policy, table, COPY/INSERT shape or command failure aborts the backup without advancing the success marker. Consequently, managed logical backups cannot extend the YouTube API cache beyond its 28-day database lifecycle or retain Nostr activity beyond its 30-day database lifecycle, and they never retain request-gate lease state.

Provider-managed automatic backups and point-in-time recovery are outside this
filter. Revalidate their actual retention for the exact Supabase plan before
enabling YouTube, Bluesky, or Nostr collection; keep each feature off if any
retained snapshot could outlive its source-data retention boundary.

## Nostr backup/PITR enablement gate

Nostr migration `20260906000000` creates the private three-relay ledgers and
forward migration `20260909000000` raises the independent cleanup budget to
`750000` rows per activity table. Migration `20260910000000` removes the Nostr
ledger and typed execution path from `service_role` and adds the dedicated
worker/attestor capability proof. That budget strictly covers the documented
`648000`-row worst case (three relays × 100 candidates and observations per
minute × 36 hours) with headroom; it does not change provider backup or PITR
retention.

When `NOSTR_COLLECTION_ENABLED=true`,
`deploy/lib/verify_nostr_release.py --env-file /etc/pokecrack/nostr.env` is a
required machine-checkable preflight before any service replacement. It reads
only the separate least-privilege TLS DSN in
`SUPABASE_NOSTR_PREFLIGHT_DB_URL` and keeps that URL out of the `psql` argv and
output; it rejects an absent or byte-for-byte reused worker
`NOSTR_SUPABASE_DB_URL` and every unreviewed environment key.
The URL must authenticate exactly as `pokecrack_nostr_attestor_login` and set
the single libpq option `-c role=pokecrack_nostr_attestor`. The login is
`NOINHERIT`, has connection limit 2 and exactly one non-admin membership; the
group is `NOLOGIN`, cannot read or mutate any relation or sequence and can
execute only the 100 version-two `SECURITY DEFINER` attestation RPC. The
separate worker login selects only `pokecrack_nostr_worker`, whose group has the
ten exact Nostr RPCs: seven queue/heartbeat/persistence capabilities, one
idempotent current-minute scheduler, one boolean runtime-contract proof, and
one reviewed non-secret policy projection.
It still has no direct relation/sequence or generic queue access.
Both groups and logins must have no role-level configuration, unexpected
membership, or owned schema/relation/function/type/database object. Neither
login may inherit or join `service_role` or another worker role. The RPC has a
fixed search path and returns only the exact 15-key boolean contract. The
preflight fails closed unless the hosted ledger contains migrations `060`,
`090`, and `100` with their exact names, the three source policies and idle
request gates are exact, the three private tables have forced RLS and zero
browser/service/worker policies or direct ACL, the checkpoints and 750000-row
cleanup/finalizer contract are intact, both dedicated role/login/membership
contracts remain exact, and
public v2 returns the reviewed Bluesky-first/Nostr-second shape with its exact
ACL. A false or absent Nostr flag is a successful no-op, so unrelated
Bluesky-only maintenance is not blocked. The login and its random password are
created by a separate account-owner operation after migration; an owner DSN is
never persisted on the VPS.

The logical sanitizer removes all Nostr candidate and observation rows and
retains only the three checkpoint rows; it cannot sanitize provider-managed
snapshots or PITR history. This repository has no evidence that the exact
Personal Supabase plan currently provides a sufficient Nostr retention/PITR
window. Before changing the flag to true, an operator must record an
account-specific assertion covering automatic-backup retention, PITR window,
restore access, and provider-side exclusion semantics, then complete a fresh
isolated restore drill. Until that assertion and drill are recorded,
`NOSTR_COLLECTION_ENABLED` remains false and the deployment preflight must not
be bypassed.

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
RESTORE_SQL=$(mktemp /tmp/pokecrack-restore.XXXXXXXX.sql)
trap 'rm -f "$RESTORE_SQL"' EXIT HUP INT TERM
chmod 0600 "$RESTORE_SQL"
gzip --decompress --stdout "$BACKUP" > "$RESTORE_SQL"
printf '%s' "$RESTORE_DB_URL" \
  | python3 deploy/lib/run_with_database_url.py -- \
      psql -X --set ON_ERROR_STOP=on --file "$RESTORE_SQL"
unset RESTORE_DB_URL
rm -f "$RESTORE_SQL"
trap - EXIT HUP INT TERM
```

The sanitizer places the canonical gate rows before `ENABLE ROW LEVEL SECURITY`; isolated pre- and post-YouTube restores have succeeded with fresh owner roles that do not have `BYPASSRLS`. Because the dump omits owner/privilege restoration, apply the reviewed role/grant/RLS configuration appropriate to the fresh project. Then verify: all migration/schema objects; `ingest.youtube_discoveries` exists as `UNLOGGED` but contains zero restored rows; Bluesky and Nostr candidates/observations contain zero restored rows while their exact checkpoints remain; Nostr has exactly three checkpoint rows bound to the reviewed relay keys, endpoints, NIP-11 URLs, `nip01`, approved tags and non-negative counters; `ingest.source_request_gates` is a regular forced-RLS table with no policies and exactly the expected canonical source keys, each with null owner/generation/acquisition/expiry fields; expected table counts/ranges; foreign-key integrity; statistics-eligibility constraints; private schemas unavailable to anon/authenticated; intended public-safe reads; no credentials/session cookies in tables; and application fixture/live smoke behavior. Record backup filename/checksum, source SHA/migration set, drill target, duration, checks performed, failures and destruction confirmation. Destroy/sanitize the drill target afterward.

## Production recovery

Declare an incident, stop writers/collectors, identify the recovery point and affected migrations, preserve evidence, restore to a fresh target first, validate, then cut over credentials deliberately. Do not pipe a dump into the live database as an ad-hoc rollback. Schema defects get a reviewed forward migration. Rotate DB credentials after a suspected backup leak.
