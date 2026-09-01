#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
umask 077

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname "${BASH_SOURCE[0]}")" && pwd -P)
PORTABILITY_HELPER="$SCRIPT_DIR/../lib/shell_portability.sh"
DATABASE_URL_RUNNER="$SCRIPT_DIR/../lib/run_with_database_url.py"
# shellcheck disable=SC1090
source "$PORTABILITY_HELPER"
BACKUP_DIR=${BACKUP_DIR:-/opt/pokecrack/backups}
DAILY=${BACKUP_RETENTION_DAILY:-7}
WEEKLY=${BACKUP_RETENTION_WEEKLY:-4}
DATABASE_URL_FILE=${SUPABASE_DB_URL_FILE:-}

die() {
  printf 'backup: %s\n' "$*" >&2
  exit 1
}

for command in pg_dump psql gzip python3 date mktemp stat; do
  command -v "$command" >/dev/null 2>&1 || die "required command not found: $command"
done
[[ $BACKUP_DIR == /* ]] || die "BACKUP_DIR must be an absolute path"
[[ $DAILY =~ ^[0-9]+$ ]] || die "BACKUP_RETENTION_DAILY must be a non-negative integer"
[[ $WEEKLY =~ ^[0-9]+$ ]] || die "BACKUP_RETENTION_WEEKLY must be a non-negative integer"
[[ ! -L $BACKUP_DIR ]] || die "BACKUP_DIR must not be a symbolic link"

if [[ -n $DATABASE_URL_FILE ]]; then
  [[ $DATABASE_URL_FILE == /* && -f $DATABASE_URL_FILE && ! -L $DATABASE_URL_FILE ]] || die "SUPABASE_DB_URL_FILE must name an absolute regular, non-symlink file"
  database_url_mode=$(pokecrack_stat_mode "$DATABASE_URL_FILE") || die "could not validate SUPABASE_DB_URL_FILE permissions"
  [[ $database_url_mode =~ ^[0-7]{3,4}$ ]] || die "could not validate SUPABASE_DB_URL_FILE permissions"
  database_url_permissions=$((8#$database_url_mode))
  (( (database_url_permissions & 0077) == 0 )) || die "SUPABASE_DB_URL_FILE must be owner-only (mode 0400 or 0600)"
  [[ $(pokecrack_stat_uid "$DATABASE_URL_FILE") == "$EUID" ]] || die "SUPABASE_DB_URL_FILE must be owned by the backup process user"
  IFS= read -r database_url < "$DATABASE_URL_FILE" || die "could not read SUPABASE_DB_URL_FILE"
else
  database_url=${SUPABASE_DB_URL:-}
fi
unset SUPABASE_DB_URL
[[ -n $database_url ]] || die "SUPABASE_DB_URL_FILE or SUPABASE_DB_URL is required"

run_database_command() {
  printf '%s' "$database_url" | python3 "$DATABASE_URL_RUNNER" -- "$@"
}

install -d -m 0700 "$BACKUP_DIR"
[[ -d $BACKUP_DIR && ! -L $BACKUP_DIR ]] || die "backup directory is not a real directory"
chmod 0700 "$BACKUP_DIR"
SUCCESS_MARKER="$BACKUP_DIR/.last-successful-backup"
if [[ -e $SUCCESS_MARKER || -L $SUCCESS_MARKER ]]; then
  [[ -f $SUCCESS_MARKER && ! -L $SUCCESS_MARKER ]] || die "success marker must be a regular, non-symlink file"
fi

# Prove that both the policy registry and the dedicated disposable cache have
# the expected physical shape without placing the database URL in argv or
# output. The sanitizer checks the same policy/table pair inside the dump, so
# a schema race fails instead of retaining cache rows.
table_state_query="set role service_role;
select concat_ws(E'\\t',
  coalesce((
    select relkind::text || relpersistence::text
    from pg_catalog.pg_class
    where oid = to_regclass('ingest.source_policies')
  ), '0'),
  coalesce((
    select relkind::text || relpersistence::text
    from pg_catalog.pg_class
    where oid = to_regclass('ingest.youtube_discoveries')
  ), '0'),
  coalesce((
    select relkind::text || relpersistence::text
    from pg_catalog.pg_class
    where oid = to_regclass('ingest.source_request_gates')
  ), '0'),
  coalesce((
    select relkind::text || relpersistence::text
    from pg_catalog.pg_class
    where oid = to_regclass('ingest.public_study_observations')
  ), '0'),
  coalesce((
    select relkind::text || relpersistence::text
    from pg_catalog.pg_class
    where oid = to_regclass('ingest.bluesky_jetstream_candidates')
  ), '0'),
  coalesce((
    select relkind::text || relpersistence::text
    from pg_catalog.pg_class
    where oid = to_regclass('ingest.bluesky_jetstream_observations')
  ), '0'),
  coalesce((
    select relkind::text || relpersistence::text
    from pg_catalog.pg_class
    where oid = to_regclass('ingest.bluesky_jetstream_checkpoints')
  ), '0'),
  coalesce((
    select relkind::text || relpersistence::text
    from pg_catalog.pg_class
    where oid = to_regclass('ingest.nostr_relay_candidates')
  ), '0'),
  coalesce((
    select relkind::text || relpersistence::text
    from pg_catalog.pg_class
    where oid = to_regclass('ingest.nostr_relay_observations')
  ), '0'),
  coalesce((
    select relkind::text || relpersistence::text
    from pg_catalog.pg_class
    where oid = to_regclass('ingest.nostr_relay_checkpoints')
  ), '0'),
  coalesce((
    select relkind::text || relpersistence::text
    from pg_catalog.pg_class
    where oid = to_regclass('ingest.mastodon_public_hashtag_candidates')
  ), '0'),
  coalesce((
    select relkind::text || relpersistence::text
    from pg_catalog.pg_class
    where oid = to_regclass('ingest.mastodon_public_hashtag_observations')
  ), '0'),
  coalesce((
    select relkind::text || relpersistence::text
    from pg_catalog.pg_class
    where oid = to_regclass('ingest.mastodon_public_hashtag_checkpoints')
  ), '0'),
  coalesce((
    select relkind::text || relpersistence::text
    from pg_catalog.pg_class
    where oid = to_regclass('ingest.mastodon_rate_cooldowns')
  ), '0'),
  coalesce(has_table_privilege(
    'service_role',
    to_regclass('ingest.source_request_gates'),
    'MAINTAIN'
  )::text, 'false')
);"
if ! table_state=$(run_database_command psql -X --set=ON_ERROR_STOP=1 --tuples-only --no-align --quiet --command "$table_state_query" 2>/dev/null); then
  unset database_url
  die "database retention preflight failed"
fi

mastodon_public_hashtag=absent
table_state_fields=()
if [[ $table_state == *$'\t'* ]]; then
  IFS=$'\t' read -r -a table_state_fields <<< "$table_state"
fi
if [[ ${#table_state_fields[@]} == 15 ]]; then
  if [[ ${table_state_fields[0]} != rp || ${table_state_fields[2]} != rp || ${table_state_fields[14]} != true ]]; then
    unset database_url
    die "database retention preflight has an invalid policy/gate state"
  fi
  case "${table_state_fields[1]}" in
    ru) youtube_discoveries=present ;;
    0) youtube_discoveries=absent ;;
    *) unset database_url; die "database retention preflight has an invalid YouTube table state" ;;
  esac
  case "${table_state_fields[3]}" in
    rp) public_studies=present ;;
    0) public_studies=absent ;;
    *) unset database_url; die "database retention preflight has an invalid public-study table state" ;;
  esac
  if [[ ${table_state_fields[4]} == rp && ${table_state_fields[5]} == rp && ${table_state_fields[6]} == rp ]]; then
    bluesky_jetstream=present
  elif [[ ${table_state_fields[4]} == 0 && ${table_state_fields[5]} == 0 && ${table_state_fields[6]} == 0 ]]; then
    bluesky_jetstream=absent
  else
    unset database_url
    die "database retention preflight requires a coherent Bluesky table set"
  fi
  if [[ ${table_state_fields[7]} == rp && ${table_state_fields[8]} == rp && ${table_state_fields[9]} == rp ]]; then
    nostr_relay=present
  elif [[ ${table_state_fields[7]} == 0 && ${table_state_fields[8]} == 0 && ${table_state_fields[9]} == 0 ]]; then
    nostr_relay=absent
  else
    unset database_url
    die "database retention preflight requires a coherent Nostr table set"
  fi
  if [[ ${table_state_fields[10]} == rp && ${table_state_fields[11]} == rp && ${table_state_fields[12]} == rp && ${table_state_fields[13]} == rp ]]; then
    mastodon_public_hashtag=present
  elif [[ ${table_state_fields[10]} == 0 && ${table_state_fields[11]} == 0 && ${table_state_fields[12]} == 0 && ${table_state_fields[13]} == 0 ]]; then
    mastodon_public_hashtag=absent
  else
    unset database_url
    die "database retention preflight requires a coherent Mastodon table set"
  fi
else
case "$table_state" in
  # Pre-Nostr hosts return the original seven-table state.  Keep the
  # transition compatible while the new 10-table query rolls out.
  $'rp\tru\trp\trp\trp\trp\trp\ttrue')
    youtube_discoveries=present
    public_studies=present
    bluesky_jetstream=present
    nostr_relay=absent
    ;;
  $'rp\tru\trp\trp\t0\t0\t0\ttrue')
    youtube_discoveries=present
    public_studies=present
    bluesky_jetstream=absent
    nostr_relay=absent
    ;;
  $'rp\tru\trp\t0\t0\t0\t0\ttrue')
    youtube_discoveries=present
    public_studies=absent
    bluesky_jetstream=absent
    nostr_relay=absent
    ;;
  $'rp\t0\trp\t0\t0\t0\t0\ttrue')
    youtube_discoveries=absent
    public_studies=absent
    bluesky_jetstream=absent
    nostr_relay=absent
    ;;
  $'rp\tru\trp\trp\trp\trp\trp\t0\t0\t0\ttrue')
    youtube_discoveries=present
    public_studies=present
    bluesky_jetstream=present
    nostr_relay=absent
    ;;
  $'rp\tru\trp\trp\t0\t0\t0\t0\t0\t0\ttrue')
    youtube_discoveries=present
    public_studies=present
    bluesky_jetstream=absent
    nostr_relay=absent
    ;;
  $'rp\tru\trp\t0\t0\t0\t0\t0\t0\t0\ttrue')
    youtube_discoveries=present
    public_studies=absent
    bluesky_jetstream=absent
    nostr_relay=absent
    ;;
  $'rp\t0\trp\t0\t0\t0\t0\t0\t0\t0\ttrue')
    youtube_discoveries=absent
    public_studies=absent
    bluesky_jetstream=absent
    nostr_relay=absent
    ;;
  $'rp\tru\trp\trp\trp\trp\trp\trp\trp\trp\ttrue')
    youtube_discoveries=present
    public_studies=present
    bluesky_jetstream=present
    nostr_relay=present
    ;;
  $'rp\tru\trp\trp\t0\t0\t0\trp\trp\trp\ttrue')
    youtube_discoveries=present
    public_studies=present
    bluesky_jetstream=absent
    nostr_relay=present
    ;;
  $'rp\tru\trp\t0\t0\t0\t0\trp\trp\trp\ttrue')
    youtube_discoveries=present
    public_studies=absent
    bluesky_jetstream=absent
    nostr_relay=present
    ;;
  $'rp\t0\trp\t0\t0\t0\t0\trp\trp\trp\ttrue')
    youtube_discoveries=absent
    public_studies=absent
    bluesky_jetstream=absent
    nostr_relay=present
    ;;
  *)
    unset database_url
    die "database retention preflight requires logged policy/gate tables, gate MAINTAIN, coherent Bluesky/Nostr logged tables, the public-study ledger either absent or logged, and youtube_discoveries either absent or UNLOGGED"
    ;;
esac
fi

policy_query="set role service_role;
select id::text from ingest.source_policies where source_key = 'youtube_discovery' order by id::text;"
if ! youtube_policy_id=$(run_database_command psql -X --set=ON_ERROR_STOP=1 --tuples-only --no-align --quiet --command "$policy_query" 2>/dev/null); then
  unset database_url
  die "database retention policy lookup failed"
fi

bluesky_policy_query="set role service_role;
select id::text from ingest.source_policies where source_key = 'bluesky_jetstream' order by id::text;"
if ! bluesky_policy_id=$(run_database_command psql -X --set=ON_ERROR_STOP=1 --tuples-only --no-align --quiet --command "$bluesky_policy_query" 2>/dev/null); then
  unset database_url
  die "database Bluesky retention policy lookup failed"
fi
if [[ $bluesky_policy_id == *$'\n'* ]]; then
  unset database_url
  die "database Bluesky retention policy lookup was ambiguous"
fi

nostr_policy_ids=()
nostr_policy_query="set role service_role;
select source_key || E'\\t' || id::text from ingest.source_policies
where source_key in ('nostr_relay_primal', 'nostr_relay_nos_lol', 'nostr_relay_nostr_net')
order by case source_key
  when 'nostr_relay_primal' then 1
  when 'nostr_relay_nos_lol' then 2
  when 'nostr_relay_nostr_net' then 3
end;"
if ! nostr_policy_output=$(run_database_command psql -X --set=ON_ERROR_STOP=1 --tuples-only --no-align --quiet --command "$nostr_policy_query" 2>/dev/null); then
  unset database_url
  die "database Nostr retention policy lookup failed"
fi
if [[ $nostr_policy_output == *$'\n\n'* ]]; then
  unset database_url
  die "database Nostr retention policy lookup was ambiguous"
fi
if [[ -n $nostr_policy_output ]]; then
  expected_nostr_source_keys=(
    nostr_relay_primal
    nostr_relay_nos_lol
    nostr_relay_nostr_net
  )
  nostr_policy_index=0
  while IFS= read -r nostr_policy_id; do
    if [[ $nostr_policy_id != *$'\t'* ]]; then
      unset database_url
      die "database Nostr retention policy lookup was ambiguous"
    fi
    nostr_source_key=${nostr_policy_id%%$'\t'*}
    nostr_id=${nostr_policy_id#*$'\t'}
    if [[ -z $nostr_source_key || -z $nostr_id || $nostr_id == *$'\t'* ]]; then
      unset database_url
      die "database Nostr retention policy lookup was ambiguous"
    fi
    if [[ $nostr_policy_index -ge ${#expected_nostr_source_keys[@]} || $nostr_source_key != "${expected_nostr_source_keys[$nostr_policy_index]}" ]]; then
      unset database_url
      die "database Nostr retention policy lookup was ambiguous"
    fi
    nostr_policy_ids+=("$nostr_id")
    nostr_policy_index=$((nostr_policy_index + 1))
  done <<< "$nostr_policy_output"
fi
if [[ $youtube_policy_id == *$'\n'* ]]; then
  unset database_url
  die "database retention policy lookup was ambiguous"
fi

mastodon_policy_id=''
if [[ $mastodon_public_hashtag == present ]]; then
  mastodon_policy_query="set role service_role;
select id::text from ingest.source_policies where source_key = 'mastodon_social' order by id::text;"
  if ! mastodon_policy_id=$(run_database_command psql -X --set=ON_ERROR_STOP=1 --tuples-only --no-align --quiet --command "$mastodon_policy_query" 2>/dev/null); then
    unset database_url
    die "database Mastodon retention policy lookup failed"
  fi
  if [[ $mastodon_policy_id == *$'\n'* ]]; then
    unset database_url
    die "database Mastodon retention policy lookup was ambiguous"
  fi
fi

sanitizer_arguments=(
  --source-policies present
  --youtube-discoveries "$youtube_discoveries"
  --public-studies "$public_studies"
  --bluesky-jetstream "$bluesky_jetstream"
  --nostr-relay "$nostr_relay"
  --mastodon-public-hashtag "$mastodon_public_hashtag"
)
if [[ $youtube_discoveries == present ]]; then
  if [[ -z $youtube_policy_id ]]; then
    unset database_url
    die "database retention policy lookup returned no YouTube policy"
  fi
  if [[ ! $youtube_policy_id =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
    unset database_url
    die "database retention policy id was malformed"
  fi
  sanitizer_arguments+=(--youtube-policy-id "$youtube_policy_id")
elif [[ -n $youtube_policy_id ]]; then
  unset database_url
  die "database retention policy exists without youtube_discoveries"
fi
if [[ $bluesky_jetstream == present ]]; then
  if [[ -z $bluesky_policy_id ]]; then
    unset database_url
    die "database retention policy lookup returned no Bluesky policy"
  fi
  if [[ ! $bluesky_policy_id =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
    unset database_url
    die "database Bluesky retention policy id was malformed"
  fi
  sanitizer_arguments+=(--bluesky-policy-id "$bluesky_policy_id")
elif [[ -n $bluesky_policy_id ]]; then
  unset database_url
  die "database Bluesky retention policy exists without the exact private table set"
fi
if [[ $nostr_relay == present ]]; then
  if [[ ${#nostr_policy_ids[@]} != 3 ]]; then
    unset database_url
    die "database Nostr retention policy lookup must return exactly three policies"
  fi
  for nostr_policy_id in "${nostr_policy_ids[@]}"; do
    if [[ ! $nostr_policy_id =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
      unset database_url
      die "database Nostr retention policy id was malformed"
    fi
    sanitizer_arguments+=(--nostr-policy-id "$nostr_policy_id")
  done
elif [[ ${#nostr_policy_ids[@]} != 0 ]]; then
  unset database_url
  die "database Nostr retention policy exists without the exact private table set"
fi
if [[ $mastodon_public_hashtag == present ]]; then
  if [[ -z $mastodon_policy_id ]]; then
    unset database_url
    die "database Mastodon retention policy lookup returned no policy"
  fi
  if [[ ! $mastodon_policy_id =~ ^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$ ]]; then
    unset database_url
    die "database Mastodon retention policy id was malformed"
  fi
  sanitizer_arguments+=(--mastodon-policy-id "$mastodon_policy_id")
elif [[ -n $mastodon_policy_id ]]; then
  unset database_url
  die "database Mastodon retention policy exists without the exact Mastodon table set"
fi

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
[[ $timestamp =~ ^[0-9]{8}T[0-9]{6}Z$ ]] || die "date returned an invalid UTC timestamp"
filename="pokecrack-${timestamp}.sql.gz"
final_path="$BACKUP_DIR/$filename"
[[ ! -e $final_path && ! -L $final_path ]] || die "backup already exists for timestamp $timestamp"

temporary=$(mktemp "$BACKUP_DIR/.backup-${timestamp}.partial.XXXXXXXX")
marker_temporary=''
cleanup() {
  local status=$?
  [[ ! -e ${temporary:-} ]] || rm -f "$temporary"
  if [[ -n ${marker_temporary:-} && -e $marker_temporary ]]; then
    rm -f "$marker_temporary"
  fi
  exit "$status"
}
trap cleanup EXIT HUP INT TERM

# The URL runner translates stdin into libpq environment fields, keeping the
# credential out of process arguments and command output. Dump only the four
# Pokecrack application schemas plus the Supabase migration ledger. In
# particular, do not ask pg_dump to inspect provider-owned auth, storage,
# realtime, extensions, or other managed schemas.
#
# The independent preflights above still SET ROLE service_role so the retained
# data contract is checked through the reviewed application capability. The
# dump itself deliberately remains on the owner-capable login: Nostr isolation
# denies service_role direct relation access, and the migration ledger is not a
# worker capability. Exact schema inclusion keeps that owner authority bounded
# to the reviewed backup surface without broadening service_role grants.
if ! run_database_command pg_dump \
  --format=plain \
  --no-owner \
  --no-privileges \
  --encoding=UTF8 \
  --strict-names \
  --schema=catalog \
  --schema=ingest \
  --schema=analytics \
  --schema=public \
  --schema=supabase_migrations \
  --exclude-table-data=ingest.source_request_gates \
  --exclude-table-data=ingest.bluesky_jetstream_candidates \
  --exclude-table-data=ingest.bluesky_jetstream_observations \
  --exclude-table-data=ingest.nostr_relay_candidates \
  --exclude-table-data=ingest.nostr_relay_observations \
  --exclude-table-data=ingest.mastodon_public_hashtag_candidates \
  --exclude-table-data=ingest.mastodon_public_hashtag_observations \
  | python3 "$SCRIPT_DIR/../lib/sanitize_plain_backup.py" \
      "${sanitizer_arguments[@]}" \
  | gzip -9 > "$temporary"; then
  unset database_url
  die "database dump retention sanitization failed"
fi
unset database_url

[[ -s $temporary ]] || die "compressed backup is empty"
gzip -t "$temporary" || die "compressed backup failed gzip validation"
python3 -c 'import gzip, pathlib, sys
path = pathlib.Path(sys.argv[1])
count = 0
with gzip.open(path, "rb") as stream:
    while chunk := stream.read(1024 * 1024):
        count += len(chunk)
if count == 0:
    raise SystemExit("uncompressed backup is empty")
' "$temporary" >/dev/null

chmod 0600 "$temporary"
mv "$temporary" "$final_path"

marker_temporary=$(mktemp "$BACKUP_DIR/.last-successful-backup.XXXXXXXX")
printf '%s\ncompleted_at=%s\n' "$filename" "$timestamp" > "$marker_temporary"
chmod 0600 "$marker_temporary"
mv -f "$marker_temporary" "$SUCCESS_MARKER"
marker_temporary=''

python3 "$SCRIPT_DIR/../lib/prune_backups.py" \
  --directory "$BACKUP_DIR" \
  --daily "$DAILY" \
  --weekly "$WEEKLY" \
  --protect "$filename"

compressed_bytes=$(pokecrack_stat_size "$final_path") || die "could not determine compressed backup size"
printf 'Backup completed: %s (%s compressed bytes).\n' "$filename" "$compressed_bytes"
trap - EXIT HUP INT TERM
