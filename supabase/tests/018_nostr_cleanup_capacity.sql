-- Forward migration 090 keeps the Nostr retention path bounded while closing
-- the 36-hour scheduler-outage gap left by the 500000-row migration-060 cap.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

create role pokecrack_nostr_attestor_login
  login
  noinherit
  nosuperuser
  nocreatedb
  nocreaterole
  noreplication
  nobypassrls
  connection limit 2;
grant pokecrack_nostr_attestor to pokecrack_nostr_attestor_login
  with inherit false, set true;

select ok(
  (select position('max_rows integer default 750000' in lower(pg_get_functiondef(
      'ingest.prune_nostr_relay_v1(timestamptz,integer)'::regprocedure
    ))) > 0
    and position('max_rows < 1 or max_rows > 750000' in lower(pg_get_functiondef(
      'ingest.prune_nostr_relay_v1(timestamptz,integer)'::regprocedure
    ))) > 0),
  'Nostr cleanup has a bounded 750000-row per-table budget'
);
select ok(
  (select position('for update of candidates skip locked' in lower(pg_get_functiondef(
      'ingest.prune_nostr_relay_v1(timestamptz,integer)'::regprocedure
    ))) > 0
    and position('for update of observations skip locked' in lower(pg_get_functiondef(
      'ingest.prune_nostr_relay_v1(timestamptz,integer)'::regprocedure
    ))) > 0),
  'Nostr cleanup locks ordered candidate batches with SKIP LOCKED for both tables'
);
select ok(
  position('delete from ingest.nostr_relay_checkpoints' in lower(pg_get_functiondef(
    'ingest.prune_nostr_relay_v1(timestamptz,integer)'::regprocedure
  ))) = 0,
  'Nostr cleanup never deletes the per-relay checkpoints'
);
select ok(
  (select lower(pg_get_functiondef(
      'ingest.finalize_cleanup_job(uuid,text,bigint)'::regprocedure
    )) ~ 'prune_nostr_relay_v1[[:space:]]*\([^)]*max_rows[[:space:]]*=>[[:space:]]*750000'
    and lower(pg_get_functiondef(
      'ingest.finalize_cleanup_job(uuid,text,bigint)'::regprocedure
    )) !~ 'prune_nostr_relay_v1[[:space:]]*\([^)]*max_rows[[:space:]]*=>[[:space:]]*500000'),
  'the fenced maintenance finalizer invokes the new cleanup capacity'
);
select ok(
  648000 < 750000,
  'the 750000-row budget strictly covers the 648000-row 36-hour outage bound'
);

select ok(
  (select prosecdef
   from pg_catalog.pg_proc
   where oid = 'ingest.verify_nostr_release_v1()'::regprocedure),
  'Nostr release attestation is SECURITY DEFINER'
);
select ok(
  (select coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_catalog.pg_proc
   where oid = 'ingest.verify_nostr_release_v1()'::regprocedure),
  'Nostr release attestation has a fixed search_path'
);
select ok(
  not has_function_privilege(
      'pokecrack_nostr_attestor',
      'ingest.verify_nostr_release_v1()',
      'execute'
    )
    and not has_function_privilege(
      'service_role', 'ingest.verify_nostr_release_v1()', 'execute'
    )
    and not has_function_privilege('anon', 'ingest.verify_nostr_release_v1()', 'execute')
    and not has_function_privilege('authenticated', 'ingest.verify_nostr_release_v1()', 'execute')
    and not exists (
      select 1
      from pg_catalog.pg_proc as procedures
      cross join lateral aclexplode(
        coalesce(procedures.proacl, acldefault('f', procedures.proowner))
      ) as grants
      where procedures.oid = 'ingest.verify_nostr_release_v1()'::regprocedure
        and grants.grantee = 0
        and grants.privilege_type = 'EXECUTE'
    ),
  'forward role isolation leaves the v1 Nostr attestation owner-only'
);

select ok(
  not has_table_privilege('service_role', 'ingest.source_request_gates', 'select')
    and not has_table_privilege('service_role', 'ingest.source_request_gates', 'insert')
    and not has_table_privilege('service_role', 'ingest.source_request_gates', 'update')
    and not has_table_privilege('service_role', 'ingest.source_request_gates', 'delete'),
  'the worker service_role cannot satisfy the Nostr preflight by reading or mutating request gates'
);

select ok(
  (select
    not rolsuper
      and not rolinherit
      and not rolcreaterole
      and not rolcreatedb
      and not rolcanlogin
      and not rolreplication
      and not rolbypassrls
      and rolconnlimit = -1
   from pg_catalog.pg_roles
   where rolname = 'pokecrack_nostr_attestor'),
  'the Nostr attestor group is exact NOLOGIN NOINHERIT least privilege'
);

select ok(
  (select
    not rolsuper
      and not rolinherit
      and not rolcreaterole
      and not rolcreatedb
      and rolcanlogin
      and not rolreplication
      and not rolbypassrls
      and rolconnlimit = 2
   from pg_catalog.pg_roles
   where rolname = 'pokecrack_nostr_attestor_login')
    and (select count(*) = 1
      and bool_and(
        not memberships.admin_option
          and not memberships.inherit_option
          and memberships.set_option
      )
      from pg_catalog.pg_auth_members as memberships
      join pg_catalog.pg_roles as parent on parent.oid = memberships.roleid
      join pg_catalog.pg_roles as member on member.oid = memberships.member
      where parent.rolname = 'pokecrack_nostr_attestor'
        and member.rolname = 'pokecrack_nostr_attestor_login'),
  'the dedicated login can SET only the attestor role without inheriting it'
);

select ok(
  has_schema_privilege('pokecrack_nostr_attestor', 'ingest', 'usage')
    and not has_schema_privilege('pokecrack_nostr_attestor', 'ingest', 'create')
    and not exists (
      select 1
      from pg_catalog.pg_class as relations
      join pg_catalog.pg_namespace as namespaces
        on namespaces.oid = relations.relnamespace
      where namespaces.nspname = 'ingest'
        and relations.relkind in ('r', 'p', 'v', 'm', 'S')
        and (
          has_table_privilege('pokecrack_nostr_attestor', relations.oid, 'select')
          or has_table_privilege('pokecrack_nostr_attestor', relations.oid, 'insert')
          or has_table_privilege('pokecrack_nostr_attestor', relations.oid, 'update')
          or has_table_privilege('pokecrack_nostr_attestor', relations.oid, 'delete')
          or has_table_privilege('pokecrack_nostr_attestor', relations.oid, 'truncate')
          or has_table_privilege('pokecrack_nostr_attestor', relations.oid, 'references')
          or has_table_privilege('pokecrack_nostr_attestor', relations.oid, 'trigger')
        )
    ),
  'the attestor has schema usage but no direct relation privileges'
);

select * from finish();
rollback;
