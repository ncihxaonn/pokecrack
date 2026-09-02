-- Runtime release evidence is a private aggregate-only capability. It must not
-- become a second service-role or public projection of ingest data.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select has_function(
  'ingest', 'get_runtime_release_evidence_v1',
  array['timestamp with time zone', 'integer', 'integer'],
  'the runtime release evidence RPC exists with bounded parameters'
);

select ok(
  (select prosecdef
      and coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_catalog.pg_proc
   where oid = 'ingest.get_runtime_release_evidence_v1(timestamptz,integer,integer)'::regprocedure),
  'the runtime evidence RPC is SECURITY DEFINER with a fixed search_path'
);

select set_eq(
  $$select coalesce(grantees.rolname, 'public')::text
    from pg_catalog.pg_proc as procedures
    cross join lateral aclexplode(
      coalesce(procedures.proacl, acldefault('f', procedures.proowner))
    ) as grants
    left join pg_catalog.pg_roles as grantees on grantees.oid = grants.grantee
    where procedures.oid =
      'ingest.get_runtime_release_evidence_v1(timestamptz,integer,integer)'::regprocedure
      and grants.privilege_type = 'EXECUTE'$$,
  $$values ('postgres'::text), ('pokecrack_runtime_monitor')$$,
  'only postgres and the dedicated monitor capability can execute the RPC'
);

select ok(
  not has_function_privilege('public', 'ingest.get_runtime_release_evidence_v1(timestamptz,integer,integer)', 'execute')
  and not has_function_privilege('anon', 'ingest.get_runtime_release_evidence_v1(timestamptz,integer,integer)', 'execute')
  and not has_function_privilege('authenticated', 'ingest.get_runtime_release_evidence_v1(timestamptz,integer,integer)', 'execute')
  and not has_function_privilege('service_role', 'ingest.get_runtime_release_evidence_v1(timestamptz,integer,integer)', 'execute'),
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

select is(
  jsonb_typeof(ingest.get_runtime_release_evidence_v1()),
  'object',
  'the RPC returns a JSON object'
);

select set_eq(
  $$select jsonb_object_keys(ingest.get_runtime_release_evidence_v1())$$,
  $$values
    ('schema_version'), ('status'), ('release_age_seconds'), ('grace_seconds'),
    ('workers'), ('sources'), ('schedule'), ('queue'), ('checkpoints'), ('cleanup')$$,
  'the top-level result contains only bounded evidence sections'
);

select ok(
  not (ingest.get_runtime_release_evidence_v1())::text ~* '"(payload|url|cursor|policy_id|gate_id|worker_id|job_id|credential|identity)"\s*:',
  'the result contains no payload, URL, cursor, identifier, credential, or identity keys'
);

select is(
  ingest.get_runtime_release_evidence_v1(
    p_grace_seconds => 172800,
    p_heartbeat_stale_seconds => 3600
  ) ->> 'status' in ('healthy', 'warming_up', 'failed'),
  true,
  'the status is explicit and never silently omitted'
);

select throws_ok(
  $$select ingest.get_runtime_release_evidence_v1(p_grace_seconds => 172801)$$,
  NULL,
  'invalid runtime evidence grace window',
  'the RPC rejects an unbounded grace window'
);

select throws_ok(
  $$select ingest.get_runtime_release_evidence_v1(p_heartbeat_stale_seconds => 29)$$,
  NULL,
  'invalid runtime evidence heartbeat window',
  'the RPC rejects an unsafe heartbeat window'
);

select * from finish();
rollback;
