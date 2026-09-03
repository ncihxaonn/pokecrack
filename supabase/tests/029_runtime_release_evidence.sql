-- Runtime release evidence is a private aggregate-only capability. It must not
-- become a second service-role or public projection of ingest data.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select has_function(
  'ingest', 'get_runtime_release_evidence_v1',
  array['timestamp with time zone', 'integer', 'integer', 'text'],
  'the runtime release evidence RPC exists with an exact service-set parameter'
);

select ok(
  (select prosecdef
      and coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog, pg_temp']
   from pg_catalog.pg_proc
   where oid = 'ingest.get_runtime_release_evidence_v1(timestamptz,integer,integer,text)'::regprocedure),
  'the runtime evidence RPC is SECURITY DEFINER with a fixed search_path'
);

select is(
  (select pg_catalog.pg_get_userbyid(proowner)
   from pg_catalog.pg_proc
   where oid = 'ingest.get_runtime_release_evidence_v1(timestamptz,integer,integer,text)'::regprocedure),
  'postgres',
  'the runtime evidence RPC remains owned by postgres'
);

select set_eq(
  $$select coalesce(grantees.rolname, 'public')::text
    from pg_catalog.pg_proc as procedures
    cross join lateral aclexplode(
      coalesce(procedures.proacl, acldefault('f', procedures.proowner))
    ) as grants
    left join pg_catalog.pg_roles as grantees on grantees.oid = grants.grantee
    where procedures.oid =
      'ingest.get_runtime_release_evidence_v1(timestamptz,integer,integer,text)'::regprocedure
      and grants.privilege_type = 'EXECUTE'$$,
  $$values ('postgres'::text), ('pokecrack_runtime_monitor')$$,
  'only postgres and the dedicated monitor capability can execute the RPC'
);

select ok(
  not has_function_privilege('public', 'ingest.get_runtime_release_evidence_v1(timestamptz,integer,integer,text)', 'execute')
  and not has_function_privilege('anon', 'ingest.get_runtime_release_evidence_v1(timestamptz,integer,integer,text)', 'execute')
  and not has_function_privilege('authenticated', 'ingest.get_runtime_release_evidence_v1(timestamptz,integer,integer,text)', 'execute')
  and not has_function_privilege('service_role', 'ingest.get_runtime_release_evidence_v1(timestamptz,integer,integer,text)', 'execute'),
  'public, browser roles, and service_role cannot execute the private RPC'
);

select ok(
  (select not rolsuper and not rolinherit and not rolcreaterole and not rolcreatedb
      and not rolcanlogin and not rolreplication and not rolbypassrls
      and rolconnlimit = -1
   from pg_catalog.pg_roles
   where rolname = 'pokecrack_runtime_monitor'),
  'the monitor capability is an exact NOLOGIN NOINHERIT least-privilege role'
);

select ok(
  has_schema_privilege('pokecrack_runtime_monitor', 'ingest', 'USAGE')
  and not has_table_privilege('pokecrack_runtime_monitor', 'ingest.source_policies', 'SELECT')
  and not has_table_privilege('pokecrack_runtime_monitor', 'ingest.jobs', 'SELECT')
  and not has_table_privilege('pokecrack_runtime_monitor', 'ingest.worker_heartbeats', 'SELECT'),
  'the monitor has schema usage only and no direct ingest table reads'
);

select ok(
  coalesce((
    select coalesce(roles.rolconfig, '{}'::text[]) = '{}'::text[]
    from pg_catalog.pg_roles as roles
    where roles.rolname = 'pokecrack_runtime_monitor'
  ), false),
  'the monitor capability has no role-level settings'
);

select ok(
  not exists (
    select 1
    from pg_catalog.pg_auth_members as memberships
    where memberships.member = 'pokecrack_runtime_monitor'::regrole
  ),
  'the monitor capability is not a member of another role'
);

select ok(
  not exists (
    select 1
    from pg_catalog.pg_db_role_setting as settings
    where settings.setrole = 'pokecrack_runtime_monitor'::regrole
  ),
  'the monitor capability has no database-level role settings'
);

select ok(
  not exists (
    select 1 from pg_catalog.pg_namespace as namespaces
    where namespaces.nspowner = 'pokecrack_runtime_monitor'::regrole
    union all
    select 1 from pg_catalog.pg_class as relations
    where relations.relowner = 'pokecrack_runtime_monitor'::regrole
    union all
    select 1 from pg_catalog.pg_proc as procedures
    where procedures.proowner = 'pokecrack_runtime_monitor'::regrole
    union all
    select 1 from pg_catalog.pg_database as databases
    where databases.datdba = 'pokecrack_runtime_monitor'::regrole
    union all
    select 1 from pg_catalog.pg_tablespace as tablespaces
    where tablespaces.spcowner = 'pokecrack_runtime_monitor'::regrole
  ),
  'the monitor capability owns no database objects'
);

select ok(
  not exists (
    select 1
    from pg_catalog.pg_namespace as namespaces
    cross join lateral aclexplode(
      coalesce(namespaces.nspacl, acldefault('n', namespaces.nspowner))
    ) as grants
    where grants.grantee = 'pokecrack_runtime_monitor'::regrole
      and not (
        namespaces.nspname = 'ingest'
        and grants.privilege_type = 'USAGE'
      )
  ),
  'the monitor capability has no unexpected direct schema grants'
);

select ok(
  not exists (
    select 1
    from pg_catalog.pg_class as relations
    cross join lateral aclexplode(
      coalesce(relations.relacl, acldefault('r', relations.relowner))
    ) as grants
    where grants.grantee = 'pokecrack_runtime_monitor'::regrole
  ),
  'the monitor capability has no direct relation grants'
);

select ok(
  not exists (
    select 1
    from pg_catalog.pg_proc as procedures
    cross join lateral aclexplode(
      coalesce(procedures.proacl, acldefault('f', procedures.proowner))
    ) as grants
    where grants.grantee = 'pokecrack_runtime_monitor'::regrole
      and (
        procedures.oid <> 'ingest.get_runtime_release_evidence_v1(timestamptz,integer,integer,text)'::regprocedure
        or grants.privilege_type <> 'EXECUTE'
      )
  ),
  'the monitor capability has only the private runtime verifier execute grant'
);

select ok(
  not exists (
    select 1
    from pg_catalog.pg_auth_members as memberships
    join pg_catalog.pg_roles as members on members.oid = memberships.member
    join pg_catalog.pg_roles as owner on owner.oid = memberships.member
    join pg_catalog.pg_roles as grantor on grantor.oid = memberships.grantor
    where memberships.roleid = 'pokecrack_runtime_monitor'::regrole
      and not (
        memberships.admin_option
        and not memberships.inherit_option
        and not memberships.set_option
        and grantor.rolsuper
        and (owner.rolsuper or owner.rolcreaterole)
      )
      and not (
        members.rolname = 'pokecrack_runtime_monitor_login'
        and not memberships.admin_option
        and not memberships.inherit_option
        and memberships.set_option
      )
  ),
  'the monitor capability has only exact approved membership edges'
);

select is(
  jsonb_typeof(ingest.get_runtime_release_evidence_v1(
    now() - interval '1 minute', 21600, 180, 'tcgdex'
  )),
  'object',
  'the RPC returns a JSON object'
);

select set_eq(
  $$select jsonb_object_keys(ingest.get_runtime_release_evidence_v1(
    now() - interval '1 minute', 21600, 180, 'tcgdex'
  ))$$,
  $$values
    ('schema_version'), ('status'), ('release_age_seconds'), ('grace_seconds'),
    ('workers'), ('sources'), ('schedule'), ('queue'), ('checkpoints'), ('cleanup')$$,
  'the top-level result contains only bounded evidence sections'
);

select ok(
  not (ingest.get_runtime_release_evidence_v1(
    now() - interval '1 minute', 21600, 180, 'tcgdex'
  ))::text ~* '"(payload|url|cursor|policy_id|gate_id|worker_id|job_id|credential|identity)"\s*:',
  'the result contains no payload, URL, cursor, identifier, credential, or identity keys'
);

select is(
  ingest.get_runtime_release_evidence_v1(
    now() - interval '1 minute',
    p_grace_seconds => 172800,
    p_heartbeat_stale_seconds => 3600,
    p_service_set => 'tcgdex'
  ) ->> 'status' in ('healthy', 'warming_up', 'failed'),
  true,
  'the status is explicit and never silently omitted'
);

select throws_ok(
  $$select ingest.get_runtime_release_evidence_v1(
      now() - interval '1 minute', 172801, 180, 'tcgdex'
    )$$,
  NULL,
  'invalid runtime evidence grace window',
  'the RPC rejects an unbounded grace window'
);

select throws_ok(
  $$select ingest.get_runtime_release_evidence_v1(
      now() - interval '1 minute', 21600, 29, 'tcgdex'
    )$$,
  NULL,
  'invalid runtime evidence heartbeat window',
  'the RPC rejects an unsafe heartbeat window'
);

select throws_ok(
  $$select ingest.get_runtime_release_evidence_v1(
      now() - interval '1 minute', 21600, 180, 'unknown-service-set'
    )$$,
  NULL,
  'invalid runtime evidence service set',
  'the RPC rejects an unapproved service set'
);

select throws_ok(
  $$select ingest.get_runtime_release_evidence_v1(
      now() + interval '6 minutes', 21600, 180, 'tcgdex'
    )$$,
  NULL,
  'runtime evidence release start is in the future',
  'the RPC rejects a release timestamp too far in the future'
);

grant select on ingest.jobs to pokecrack_runtime_monitor;

select throws_ok(
  $$select ingest.get_runtime_release_evidence_v1(
      now() - interval '1 minute', 21600, 180, 'tcgdex'
    )$$,
  NULL,
  'runtime evidence monitor capability has drifted',
  'a direct monitor table grant fails closed at runtime'
);

revoke select on ingest.jobs from pokecrack_runtime_monitor;
alter role pokecrack_runtime_monitor inherit;

select throws_ok(
  $$select ingest.get_runtime_release_evidence_v1(
      now() - interval '1 minute', 21600, 180, 'tcgdex'
    )$$,
  NULL,
  'runtime evidence monitor capability has drifted',
  'a drifted monitor attribute fails closed at runtime'
);

select * from finish();
rollback;
