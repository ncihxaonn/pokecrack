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

case "$table_state" in
  $'rp\tru\trp\trp\ttrue')
    youtube_discoveries=present
    public_studies=present
    ;;
  $'rp\tru\trp\t0\ttrue')
    youtube_discoveries=present
    public_studies=absent
    ;;
  $'rp\t0\trp\t0\ttrue')
    youtube_discoveries=absent
    public_studies=absent
    ;;
  *)
    unset database_url
    die "database retention preflight requires logged policy/gate tables, gate MAINTAIN, the public-study ledger either absent or logged, and youtube_discoveries either absent or UNLOGGED"
    ;;
esac

policy_query="set role service_role;
select id::text from ingest.source_policies where source_key = 'youtube_discovery' order by id::text;"
if ! youtube_policy_id=$(run_database_command psql -X --set=ON_ERROR_STOP=1 --tuples-only --no-align --quiet --command "$policy_query" 2>/dev/null); then
  unset database_url
  die "database retention policy lookup failed"
fi
if [[ $youtube_policy_id == *$'\n'* ]]; then
  unset database_url
  die "database retention policy lookup was ambiguous"
fi

sanitizer_arguments=(
  --source-policies present
  --youtube-discoveries "$youtube_discoveries"
  --public-studies "$public_studies"
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
# credential out of process arguments and command output. Gate rows are live
# lease state; retain the schema under MAINTAIN but never request their data.
if ! run_database_command pg_dump \
  --format=plain \
  --role=service_role \
  --no-owner \
  --no-privileges \
  --encoding=UTF8 \
  --exclude-table-data=ingest.source_request_gates \
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
