begin;

-- pg_dump must take ACCESS SHARE while retaining the opaque gate's schema.
-- PostgreSQL 17's MAINTAIN privilege permits that lock without exposing rows.
do $backup_gate_lock$
begin
  if current_setting('server_version_num')::integer < 170000 then
    raise exception using
      errcode = '0A000',
      message = 'PokeCrack request-gate backups require PostgreSQL 17 or newer';
  end if;
  execute 'grant maintain on table ingest.source_request_gates to service_role';
end;
$backup_gate_lock$;

commit;
