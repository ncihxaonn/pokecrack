#!/usr/bin/env bash
set -Eeuo pipefail
umask 077
artifact=$1
report=$2
[[ -f "$artifact" && ! -L "$artifact" && "$report" == /* ]]
restore_root=$(mktemp -d /tmp/pokecrack-isolated-restore.XXXXXXXX)
cleanup() {
  pg_ctl -D "$restore_root/data" -m immediate stop >/dev/null 2>&1 || true
  # This exact directory was allocated by this invocation.
  rm -rf -- "$restore_root"
}
trap cleanup EXIT
initdb -D "$restore_root/data" -U postgres --auth-local=trust --auth-host=reject >/dev/null
pg_ctl -D "$restore_root/data" -l "$restore_root/server.log" -o "-c listen_addresses='' -c unix_socket_directories='$restore_root'" -w start >/dev/null
psql_args=(-X -h "$restore_root" -U postgres -d postgres -v ON_ERROR_STOP=1)
psql "${psql_args[@]}" >/dev/null <<'SQL'
DROP SCHEMA public;
CREATE ROLE anon;
CREATE ROLE authenticated;
CREATE ROLE service_role;
CREATE ROLE supabase_admin;
CREATE ROLE authenticator;
CREATE SCHEMA auth;
CREATE SCHEMA extensions;
CREATE EXTENSION pgcrypto WITH SCHEMA extensions;
CREATE FUNCTION auth.jwt() RETURNS jsonb LANGUAGE sql STABLE AS $$ SELECT '{}'::jsonb $$;
CREATE FUNCTION auth.uid() RETURNS uuid LANGUAGE sql STABLE AS $$ SELECT NULL::uuid $$;
SQL
gzip --test "$artifact"
gzip -dc "$artifact" | psql "${psql_args[@]}" > "$restore_root/restore.log" 2>&1
psql "${psql_args[@]}" --tuples-only --no-align > "$restore_root/counts" <<'SQL'
SELECT count(*) FROM supabase_migrations.schema_migrations;
SELECT count(*) FROM ingest.source_request_gates;
SELECT relrowsecurity AND relforcerowsecurity FROM pg_class WHERE oid='ingest.source_request_gates'::regclass;
SELECT count(*) FROM pg_policies WHERE schemaname='ingest' AND tablename='source_request_gates';
SQL
python3 - "$restore_root/counts" "$report" "$artifact" <<'PY'
import hashlib, json, sys
from pathlib import Path
counts = Path(sys.argv[1]).read_text().splitlines()
assert len(counts) == 4 and int(counts[0]) > 0 and int(counts[1]) > 0
assert counts[2:] == ['t', '0'], counts
report = {'status': 'passed', 'migration_rows': int(counts[0]), 'gate_rows': int(counts[1]), 'gate_forced_rls': True, 'gate_policies': 0, 'decrypted_gzip_sha256': hashlib.sha256(Path(sys.argv[3]).read_bytes()).hexdigest()}
Path(sys.argv[2]).write_text(json.dumps(report) + '\n')
PY
cleanup
trap - EXIT
test ! -e "$restore_root"
printf 'Isolated PostgreSQL restore passed; disposable target destroyed\n'
