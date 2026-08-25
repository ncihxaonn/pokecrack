#!/usr/bin/env bash
set -Eeuo pipefail
IFS=$'\n\t'
umask 077

SCRIPT_DIR=$(CDPATH='' cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd -P)
BACKUP_DIR=${BACKUP_DIR:-/opt/pokecrack/backups}
DAILY=${BACKUP_RETENTION_DAILY:-7}
WEEKLY=${BACKUP_RETENTION_WEEKLY:-4}
DATABASE_URL_FILE=${SUPABASE_DB_URL_FILE:-}

die() {
  printf 'backup: %s\n' "$*" >&2
  exit 1
}

for command in pg_dump gzip python3 date mktemp stat; do
  command -v "$command" >/dev/null 2>&1 || die "required command not found: $command"
done
[[ $BACKUP_DIR == /* ]] || die "BACKUP_DIR must be an absolute path"
[[ $DAILY =~ ^[0-9]+$ ]] || die "BACKUP_RETENTION_DAILY must be a non-negative integer"
[[ $WEEKLY =~ ^[0-9]+$ ]] || die "BACKUP_RETENTION_WEEKLY must be a non-negative integer"
[[ ! -L $BACKUP_DIR ]] || die "BACKUP_DIR must not be a symbolic link"

if [[ -n $DATABASE_URL_FILE ]]; then
  [[ -f $DATABASE_URL_FILE && ! -L $DATABASE_URL_FILE ]] || die "SUPABASE_DB_URL_FILE must name a regular, non-symlink file"
  database_url_mode=$(stat -c '%a' -- "$DATABASE_URL_FILE")
  [[ $database_url_mode =~ ^[0-7]{3,4}$ ]] || die "could not validate SUPABASE_DB_URL_FILE permissions"
  database_url_permissions=$((8#$database_url_mode))
  (( (database_url_permissions & 0077) == 0 )) || die "SUPABASE_DB_URL_FILE must be owner-only (mode 0400 or 0600)"
  [[ $(stat -c '%u' -- "$DATABASE_URL_FILE") == "$EUID" ]] || die "SUPABASE_DB_URL_FILE must be owned by the backup process user"
  IFS= read -r database_url < "$DATABASE_URL_FILE" || die "could not read SUPABASE_DB_URL_FILE"
else
  database_url=${SUPABASE_DB_URL:-}
fi
unset SUPABASE_DB_URL
[[ -n $database_url ]] || die "SUPABASE_DB_URL_FILE or SUPABASE_DB_URL is required"

install -d -m 0700 -- "$BACKUP_DIR"
[[ -d $BACKUP_DIR && ! -L $BACKUP_DIR ]] || die "backup directory is not a real directory"
chmod 0700 -- "$BACKUP_DIR"

timestamp=$(date -u +%Y%m%dT%H%M%SZ)
[[ $timestamp =~ ^[0-9]{8}T[0-9]{6}Z$ ]] || die "date returned an invalid UTC timestamp"
filename="pokecrack-${timestamp}.sql.gz"
final_path="$BACKUP_DIR/$filename"
[[ ! -e $final_path && ! -L $final_path ]] || die "backup already exists for timestamp $timestamp"

temporary=$(mktemp "$BACKUP_DIR/.backup-${timestamp}.partial.XXXXXXXX")
marker_temporary=''
cleanup() {
  local status=$?
  [[ ! -e ${temporary:-} ]] || rm -f -- "$temporary"
  if [[ -n ${marker_temporary:-} && -e $marker_temporary ]]; then
    rm -f -- "$marker_temporary"
  fi
  exit "$status"
}
trap cleanup EXIT HUP INT TERM

# PGDATABASE keeps the credential out of process arguments and command output.
PGDATABASE=$database_url pg_dump \
  --format=plain \
  --no-owner \
  --no-privileges \
  --encoding=UTF8 \
  | gzip -9 > "$temporary"
unset database_url

[[ -s $temporary ]] || die "compressed backup is empty"
gzip --test -- "$temporary" || die "compressed backup failed gzip validation"
python3 -c 'import gzip, pathlib, sys
path = pathlib.Path(sys.argv[1])
count = 0
with gzip.open(path, "rb") as stream:
    while chunk := stream.read(1024 * 1024):
        count += len(chunk)
if count == 0:
    raise SystemExit("uncompressed backup is empty")
' "$temporary" >/dev/null

chmod 0600 -- "$temporary"
mv -- "$temporary" "$final_path"

marker_temporary=$(mktemp "$BACKUP_DIR/.last-successful-backup.XXXXXXXX")
printf '%s\ncompleted_at=%s\n' "$filename" "$timestamp" > "$marker_temporary"
chmod 0600 -- "$marker_temporary"
mv -f -- "$marker_temporary" "$BACKUP_DIR/.last-successful-backup"
marker_temporary=''

python3 "$SCRIPT_DIR/../lib/prune_backups.py" \
  --directory "$BACKUP_DIR" \
  --daily "$DAILY" \
  --weekly "$WEEKLY" \
  --protect "$filename"

compressed_bytes=$(stat -c '%s' -- "$final_path")
printf 'Backup completed: %s (%s compressed bytes).\n' "$filename" "$compressed_bytes"
trap - EXIT HUP INT TERM
