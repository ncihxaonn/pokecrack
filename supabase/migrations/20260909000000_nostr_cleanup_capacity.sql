begin;

-- Migration 060 shipped a bounded 500,000-row recovery budget per activity
-- table.  Three relays can admit at most 300 candidates and 300 observations
-- per minute; a 36-hour scheduler outage can therefore leave 648,000 expired
-- rows in either table.  Keep the cleanup ordered, independently bounded and
-- lock-friendly, but raise the one-cycle budget to 750,000 (15.7% headroom).
-- Checkpoints remain outside both deletion paths.
create or replace function ingest.prune_nostr_relay_v1(
  cutoff timestamptz,
  max_rows integer default 750000
)
returns table(candidates_deleted integer, observations_deleted integer)
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $$
declare
  deleted_candidates integer := 0;
  deleted_observations integer := 0;
  batch_deleted integer := 0;
  batch_limit integer := 0;
begin
  if cutoff is null then
    raise exception using errcode = '22023', message = 'cutoff must not be null';
  end if;
  if max_rows is null or max_rows < 1 or max_rows > 750000 then
    raise exception using
      errcode = '22023',
      message = 'max_rows must be between 1 and 750000 per table';
  end if;

  loop
    batch_limit := least(10000, max_rows - deleted_candidates);
    exit when batch_limit <= 0;
    with locked_candidates as (
      select candidates.event_id
      from ingest.nostr_relay_candidates as candidates
      where candidates.expires_at <= cutoff
      order by candidates.expires_at, candidates.event_id
      for update of candidates skip locked
      limit batch_limit
    ), deleted as (
      delete from ingest.nostr_relay_candidates as candidates
      using locked_candidates
      where candidates.event_id = locked_candidates.event_id
      returning 1
    )
    select count(*)::integer into batch_deleted from deleted;
    deleted_candidates := deleted_candidates + batch_deleted;
    exit when batch_deleted < batch_limit;
  end loop;

  loop
    batch_limit := least(10000, max_rows - deleted_observations);
    exit when batch_limit <= 0;
    with locked_observations as (
      select observations.id
      from ingest.nostr_relay_observations as observations
      where observations.expires_at <= cutoff
      order by observations.expires_at, observations.id
      for update of observations skip locked
      limit batch_limit
    ), deleted as (
      delete from ingest.nostr_relay_observations as observations
      using locked_observations
      where observations.id = locked_observations.id
      returning 1
    )
    select count(*)::integer into batch_deleted from deleted;
    deleted_observations := deleted_observations + batch_deleted;
    exit when batch_deleted < batch_limit;
  end loop;

  return query select deleted_candidates, deleted_observations;
end;
$$;

alter function ingest.prune_nostr_relay_v1(timestamptz, integer)
  owner to postgres;
revoke all on function ingest.prune_nostr_relay_v1(timestamptz, integer)
  from public, anon, authenticated, service_role;
comment on function ingest.prune_nostr_relay_v1(timestamptz, integer) is
  'Owner-only ordered cleanup for private Nostr activity candidates and observations. The independent 750000-row per-table recovery budget covers 36 hours at the three-relay 300-row-per-minute bound; per-relay checkpoints are retained.';

-- The cleanup finalizer is replaced only when its migration-060 extension
-- point is still exact.  A drifted function must fail closed instead of
-- silently widening another maintenance path.
do $migration$
declare
  definition text;
  updated_definition text;
  old_cleanup_call constant text := $call$  perform ingest.prune_nostr_relay_v1(
    cutoff => lease_checked_at,
    max_rows => 500000
  );$call$;
  new_cleanup_call constant text := $call$  perform ingest.prune_nostr_relay_v1(
    cutoff => lease_checked_at,
    max_rows => 750000
  );$call$;
begin
  select pg_get_functiondef(
    'ingest.finalize_cleanup_job(uuid,text,bigint)'::regprocedure
  ) into definition;
  if definition is null
    or length(definition) - length(replace(definition, old_cleanup_call, ''))
      <> length(old_cleanup_call)
  then
    raise exception using
      errcode = '55000',
      message = 'finalize_cleanup_job no longer matches the migration-060 Nostr cleanup extension point';
  end if;
  updated_definition := replace(definition, old_cleanup_call, new_cleanup_call);
  if updated_definition = definition
    or position(new_cleanup_call in updated_definition) = 0
    or position(old_cleanup_call in updated_definition) <> 0
  then
    raise exception using
      errcode = '55000',
      message = 'finalize_cleanup_job Nostr cleanup capacity update did not match exactly';
  end if;
  execute updated_definition;
end;
$migration$;

alter function ingest.finalize_cleanup_job(uuid, text, bigint) owner to postgres;
revoke all on function ingest.finalize_cleanup_job(uuid, text, bigint)
  from public, anon, authenticated, service_role;
grant execute on function ingest.finalize_cleanup_job(uuid, text, bigint)
  to service_role;

-- The deployment preflight has its own NOLOGIN group role.  The external
-- NOINHERIT login is created separately with a random password and fixed
-- CONNECTION LIMIT 2, then selects this role through libpq startup options.
-- Neither the worker nor service_role can invoke this attestation.
do $roles$
declare
  role_is_exact boolean;
begin
  if not exists (
    select 1 from pg_catalog.pg_roles
    where rolname = 'pokecrack_nostr_attestor'
  ) then
    create role pokecrack_nostr_attestor
      nologin
      noinherit
      nosuperuser
      nocreatedb
      nocreaterole
      noreplication
      nobypassrls
      connection limit -1;
  else
    select
      not rolsuper
      and not rolinherit
      and not rolcreaterole
      and not rolcreatedb
      and not rolcanlogin
      and not rolreplication
      and not rolbypassrls
      and rolconnlimit = -1
    into role_is_exact
    from pg_catalog.pg_roles
    where rolname = 'pokecrack_nostr_attestor';
    if role_is_exact is distinct from true then
      raise exception using
        errcode = '55000',
        message = 'existing pokecrack_nostr_attestor role is not the reviewed NOLOGIN contract';
    end if;
  end if;
end;
$roles$;

revoke all privileges on schema ingest from pokecrack_nostr_attestor;
revoke all privileges on all tables in schema ingest from pokecrack_nostr_attestor;
revoke all privileges on all sequences in schema ingest from pokecrack_nostr_attestor;
revoke all privileges on all functions in schema ingest from pokecrack_nostr_attestor;
grant usage on schema ingest to pokecrack_nostr_attestor;

-- This SECURITY DEFINER function returns only the boolean contract needed by
-- the deploy gate.  It never returns application rows, identifiers, cursors,
-- payloads, credentials or migration SQL.
create or replace function ingest.verify_nostr_release_v1()
returns jsonb
language sql
stable
security definer
set search_path = pg_catalog
as $attestation$
with expected_relays(relay_key, source_key, display_name, domain, endpoint, nip11_url) as (
  values
    ('primal', 'nostr_relay_primal', 'Nostr relay relay.primal.net discovery',
      'relay.primal.net', 'wss://relay.primal.net/', 'https://relay.primal.net/'),
    ('nos_lol', 'nostr_relay_nos_lol', 'Nostr relay nos.lol discovery',
      'nos.lol', 'wss://nos.lol/', 'https://nos.lol/'),
    ('nostr_net', 'nostr_relay_nostr_net', 'Nostr relay relay.nostr.net discovery',
      'relay.nostr.net', 'wss://relay.nostr.net/', 'https://relay.nostr.net/')
),
expected_tags(ordinal, tag) as (
  values
    (1, 'pokemontcg'), (2, 'PokemonTCG'), (3, 'pokemoncards'), (4, 'PokemonCards'),
    (5, 'ポケカ'), (6, 'ポケモンカード'), (7, '포켓몬카드'), (8, '宝可梦卡牌'), (9, '寶可夢卡牌')
),
expected_configs as (
  select
    relays.*,
    jsonb_build_object(
      'relay_key', relays.relay_key,
      'endpoint', relays.endpoint,
      'nip11_url', relays.nip11_url,
      'protocol', 'nip01',
      'policy_state', 'degraded_missing_relay_specific_terms',
      'required_nips', jsonb_build_array(1, 9, 11),
      'approved_tags', (select jsonb_agg(tag order by ordinal) from expected_tags),
      'replay_overlap_seconds', 300,
      'stream_window_seconds', 15,
      'max_events', 100,
      'max_message_bytes', 262144,
      'max_stream_bytes', 2097152,
      'max_candidates', 100,
      'max_deletions', 100,
      'max_delete_targets', 16,
      'statistics_eligible', false
    ) as expected_config
  from expected_relays as relays
),
policy_contract as (
  select
    expected.source_key,
    policies.id is not null
      and policies.display_name = expected.display_name
      and policies.source_kind = 'public_web'
      and policies.domain = expected.domain
      and policies.base_url = expected.endpoint
      and policies.enabled
      and policies.collector_type = 'nostr_relay'
      and policies.access_mode = 'public'
      and policies.robots_policy = 'not_applicable'
      and policies.routes = array['nostr_relay']::text[]
      and not policies.include_subdomains
      and policies.min_delay_seconds = 1
      and policies.max_pages_per_run = 1
      and policies.max_items_per_run = 100
      and policies.max_concurrency = 1
      and policies.browser_profile is null
      and not policies.statistics_eligible_default
      and policies.retention_days = 30
      and policies.config = expected.expected_config
      and policies.version = 'nostr-multi-relay-v1'
      and policies.expected_interval_seconds = 60
      and not policies.is_demo as valid
  from expected_configs as expected
  left join ingest.source_policies as policies
    on policies.source_key = expected.source_key
),
gate_contract as (
  select
    expected.source_key,
    gates.source_key is not null
      and gates.owner_job_id is null
      and gates.owner_lease_generation is null
      and gates.acquired_at is null
      and gates.active_until is null as valid
  from expected_relays as expected
  left join ingest.source_request_gates as gates
    on gates.source_key = expected.source_key
),
nostr_tables(table_name) as (
  values
    ('nostr_relay_candidates'),
    ('nostr_relay_observations'),
    ('nostr_relay_checkpoints')
),
table_contract as (
  select
    tables.table_name,
    exists (
      select 1
      from pg_catalog.pg_class as classes
      join pg_catalog.pg_namespace as namespaces on namespaces.oid = classes.relnamespace
      where namespaces.nspname = 'ingest'
        and classes.relname = tables.table_name
        and classes.relkind = 'r'
        and classes.relpersistence = 'p'
        and classes.relrowsecurity
        and classes.relforcerowsecurity
    ) as valid
  from nostr_tables as tables
),
policy_names(table_name, policy_name) as (
  values
    ('nostr_relay_candidates', 'nostr_candidates_service_role_select'),
    ('nostr_relay_observations', 'nostr_observations_service_role_select'),
    ('nostr_relay_checkpoints', 'nostr_checkpoints_service_role_select')
),
policy_acl as (
  select
    expected.table_name,
    policies.policyname = expected.policy_name
      and policies.cmd = 'SELECT'
      and policies.roles = array['service_role']::name[]
      and lower(replace(coalesce(policies.qual, ''), ' ', '')) = '(notis_demo)'
      and policies.with_check is null as valid
  from policy_names as expected
  left join pg_catalog.pg_policies as policies
    on policies.schemaname = 'ingest'
    and policies.tablename = expected.table_name
    and policies.policyname = expected.policy_name
),
checkpoint_contract as (
  select
    checkpoints.relay_key,
    checkpoints.source_policy_id is not null
      and checkpoints.endpoint = expected.endpoint
      and checkpoints.nip11_url = expected.nip11_url
      and checkpoints.protocol = 'nip01'
      and checkpoints.approved_tags = array[
        'pokemontcg', 'PokemonTCG', 'pokemoncards', 'PokemonCards',
        'ポケカ', 'ポケモンカード', '포켓몬카드', '宝可梦卡牌', '寶可夢卡牌'
      ]::text[]
      and checkpoints.events_seen_total >= 0
      and checkpoints.bytes_seen_total >= 0
      and checkpoints.candidates_seen_total >= 0
      and checkpoints.deletions_seen_total >= 0
      and not checkpoints.is_demo as valid
  from expected_relays as expected
  left join ingest.nostr_relay_checkpoints as checkpoints
    on checkpoints.relay_key = expected.relay_key
),
cleanup_definition as (
  select lower(pg_get_functiondef(
    'ingest.prune_nostr_relay_v1(timestamptz,integer)'::regprocedure
  )) as prune_definition,
  lower(pg_get_functiondef(
    'ingest.finalize_cleanup_job(uuid,text,bigint)'::regprocedure
  )) as finalizer_definition
),
attestor_roles as (
  select
    group_role.oid as group_oid,
    login_role.oid as login_oid,
    not group_role.rolsuper
      and not group_role.rolinherit
      and not group_role.rolcreaterole
      and not group_role.rolcreatedb
      and not group_role.rolcanlogin
      and not group_role.rolreplication
      and not group_role.rolbypassrls
      and group_role.rolconnlimit = -1 as group_valid,
    login_role.oid is not null
      and not login_role.rolsuper
      and not login_role.rolinherit
      and not login_role.rolcreaterole
      and not login_role.rolcreatedb
      and login_role.rolcanlogin
      and not login_role.rolreplication
      and not login_role.rolbypassrls
      and login_role.rolconnlimit = 2 as login_valid
  from pg_catalog.pg_roles as group_role
  left join pg_catalog.pg_roles as login_role
    on login_role.rolname = 'pokecrack_nostr_attestor_login'
  where group_role.rolname = 'pokecrack_nostr_attestor'
)
select jsonb_build_object(
  'postgresql17', current_setting('server_version_num')::integer >= 170000,
  'ledger_060', (
    select count(*) = 1
    from supabase_migrations.schema_migrations
    where version = '20260906000000' and name = 'nostr_multi_relay_discovery'
  ),
  'ledger_090', (
    select count(*) = 1
    from supabase_migrations.schema_migrations
    where version = '20260909000000' and name = 'nostr_cleanup_capacity'
  ),
  'source_policies_exact', (
    (select count(*) = 3 and count(*) filter (where valid) = 3 from policy_contract)
    and not exists (
      select 1 from ingest.source_policies
      where source_key like 'nostr_relay_%'
        and source_key not in (
          'nostr_relay_primal', 'nostr_relay_nos_lol', 'nostr_relay_nostr_net'
        )
    )
  ),
  'request_gates_exact', (
    (select count(*) = 3 and count(*) filter (where valid) = 3 from gate_contract)
    and not exists (
      select 1 from ingest.source_request_gates
      where source_key like 'nostr_relay_%'
        and source_key not in (
          'nostr_relay_primal', 'nostr_relay_nos_lol', 'nostr_relay_nostr_net'
        )
    )
  ),
  'nostr_tables_rls_exact', (
    (select count(*) = 3 and count(*) filter (where valid) = 3 from table_contract)
    and (select count(*) = 3 from pg_catalog.pg_class as classes
      join pg_catalog.pg_namespace as namespaces on namespaces.oid = classes.relnamespace
      where namespaces.nspname = 'ingest'
        and classes.relname in (
          'nostr_relay_candidates', 'nostr_relay_observations', 'nostr_relay_checkpoints'
        )
        and classes.relkind = 'r')
  ),
  'nostr_policies_exact', (
    (select count(*) = 3 and count(*) filter (where valid) = 3 from policy_acl)
    and (select count(*) = 3 from pg_catalog.pg_policies
      where schemaname = 'ingest'
        and tablename in (
          'nostr_relay_candidates', 'nostr_relay_observations', 'nostr_relay_checkpoints'
        ))
  ),
  'nostr_acl_exact', (
    (select bool_and(
      has_table_privilege('service_role', format('ingest.%s', table_name)::regclass, 'SELECT')
      and not has_table_privilege('service_role', format('ingest.%s', table_name)::regclass, 'INSERT')
      and not has_table_privilege('service_role', format('ingest.%s', table_name)::regclass, 'UPDATE')
      and not has_table_privilege('service_role', format('ingest.%s', table_name)::regclass, 'DELETE')
      and not has_table_privilege('anon', format('ingest.%s', table_name)::regclass, 'SELECT')
      and not has_table_privilege('authenticated', format('ingest.%s', table_name)::regclass, 'SELECT')
    ) from nostr_tables)
    and not has_table_privilege('service_role', 'ingest.source_request_gates'::regclass, 'SELECT')
    and not has_table_privilege('service_role', 'ingest.source_request_gates'::regclass, 'INSERT')
    and not has_table_privilege('service_role', 'ingest.source_request_gates'::regclass, 'UPDATE')
    and not has_table_privilege('service_role', 'ingest.source_request_gates'::regclass, 'DELETE')
    and has_table_privilege(
      'service_role', 'ingest.source_request_gates'::regclass, 'MAINTAIN'
    )
    and (
      select count(*) = 1
        and count(*) filter (
          where grants.grantee = service_role.oid
            and grants.privilege_type = 'MAINTAIN'
            and not grants.is_grantable
        ) = 1
      from pg_catalog.pg_class as gates
      cross join pg_catalog.pg_roles as service_role
      cross join lateral aclexplode(coalesce(
        gates.relacl, acldefault('r'::"char", gates.relowner)
      )) as grants
      where gates.oid = 'ingest.source_request_gates'::regclass
        and service_role.rolname = 'service_role'
        and grants.grantee <> gates.relowner
        and pg_get_userbyid(gates.relowner) = 'postgres'
    )
  ),
  'nostr_checkpoints_exact', (
    (select count(*) = 3 and count(*) filter (where valid) = 3 from checkpoint_contract)
    and not exists (
      select 1 from ingest.nostr_relay_checkpoints
      where relay_key not in ('primal', 'nos_lol', 'nostr_net')
    )
  ),
  'cleanup_capacity_exact', (
    (select prune_definition like '%max_rows integer default 750000%'
      and prune_definition like '%max_rows < 1 or max_rows > 750000%'
      and prune_definition like '%for update of candidates skip locked%'
      and prune_definition like '%for update of observations skip locked%'
      and position('ingest.nostr_relay_checkpoints' in prune_definition) = 0
      and finalizer_definition like '%max_rows => 750000%'
      and finalizer_definition not like '%max_rows => 500000%'
      from cleanup_definition)
  ),
  'public_v2_shape_exact', (
    (select jsonb_array_length(payload -> 'sources') = 2
      and payload ->> 'schemaVersion' = '2.0.0'
      and payload #>> '{sources,0,id}' = 'bluesky_jetstream'
      and payload #>> '{sources,1,id}' = 'nostr_multi_relay'
      and payload #>> '{sources,1,url}' =
        'https://github.com/nostr-protocol/nips/blob/master/01.md'
      from (select public.get_public_social_discovery_v2() as payload) as result)
  ),
  'public_v2_acl_exact', (
    has_function_privilege('anon', 'public.get_public_social_discovery_v2()', 'EXECUTE')
    and has_function_privilege('authenticated', 'public.get_public_social_discovery_v2()', 'EXECUTE')
    and not has_function_privilege('service_role', 'public.get_public_social_discovery_v2()', 'EXECUTE')
    and not exists (
      select 1
      from pg_catalog.pg_proc as functions
      cross join lateral aclexplode(
        coalesce(functions.proacl, acldefault('f', functions.proowner))
      ) as grants
      where functions.oid = 'public.get_public_social_discovery_v2()'::regprocedure
        and grants.grantee = 0
        and grants.privilege_type = 'EXECUTE'
    )
  ),
  'attestor_role_exact', (
    (select count(*) = 1
      and count(*) filter (where group_valid and login_valid) = 1
      from attestor_roles)
    and (select count(*) = 1
      and count(*) filter (
        where not memberships.admin_option
          and not memberships.inherit_option
          and memberships.set_option
      ) = 1
      from pg_catalog.pg_auth_members as memberships
      join attestor_roles as roles on roles.group_oid = memberships.roleid
      where memberships.member = roles.login_oid)
    and not exists (
      select 1
      from pg_catalog.pg_auth_members as memberships
      join attestor_roles as roles on roles.login_oid = memberships.member
      where memberships.roleid <> roles.group_oid
    )
    and not exists (
      select 1
      from pg_catalog.pg_auth_members as memberships
      join attestor_roles as roles on roles.group_oid = memberships.roleid
      where memberships.member <> roles.login_oid
    )
    and not exists (
      select 1
      from pg_catalog.pg_auth_members as memberships
      join attestor_roles as roles on roles.group_oid = memberships.member
    )
    and has_schema_privilege(
      'pokecrack_nostr_attestor', 'ingest', 'USAGE'
    )
    and not has_schema_privilege(
      'pokecrack_nostr_attestor', 'ingest', 'CREATE'
    )
    and has_function_privilege(
      'pokecrack_nostr_attestor',
      'ingest.verify_nostr_release_v1()',
      'EXECUTE'
    )
    and not exists (
      select 1
      from pg_catalog.pg_proc as functions
      join pg_catalog.pg_namespace as namespaces
        on namespaces.oid = functions.pronamespace
      where namespaces.nspname = 'ingest'
        and functions.oid <> 'ingest.verify_nostr_release_v1()'::regprocedure
        and has_function_privilege(
          'pokecrack_nostr_attestor', functions.oid, 'EXECUTE'
        )
    )
    and not exists (
      select 1
      from pg_catalog.pg_class as relations
      join pg_catalog.pg_namespace as namespaces
        on namespaces.oid = relations.relnamespace
      where namespaces.nspname = 'ingest'
        and relations.relkind in ('r', 'p', 'v', 'm', 'S')
        and (
          has_table_privilege(
            'pokecrack_nostr_attestor', relations.oid, 'SELECT'
          )
          or has_table_privilege(
            'pokecrack_nostr_attestor', relations.oid, 'INSERT'
          )
          or has_table_privilege(
            'pokecrack_nostr_attestor', relations.oid, 'UPDATE'
          )
          or has_table_privilege(
            'pokecrack_nostr_attestor', relations.oid, 'DELETE'
          )
          or has_table_privilege(
            'pokecrack_nostr_attestor', relations.oid, 'REFERENCES'
          )
          or has_table_privilege(
            'pokecrack_nostr_attestor', relations.oid, 'TRIGGER'
          )
        )
    )
    and not exists (
      select 1
      from pg_catalog.pg_class as relations
      join pg_catalog.pg_namespace as namespaces
        on namespaces.oid = relations.relnamespace
      cross join attestor_roles as roles
      cross join lateral aclexplode(coalesce(
        relations.relacl,
        acldefault(
          case when relations.relkind = 'S' then 's'::"char" else 'r'::"char" end,
          relations.relowner
        )
      )) as grants
      where namespaces.nspname = 'ingest'
        and relations.relkind in ('r', 'p', 'v', 'm', 'S')
        and case
          when grants.grantee = 0 then true
          else pg_has_role(
            'pokecrack_nostr_attestor', grants.grantee, 'USAGE'
          )
        end
    )
    and not exists (
      select 1
      from pg_catalog.pg_class as relations
      join pg_catalog.pg_namespace as namespaces
        on namespaces.oid = relations.relnamespace
      where namespaces.nspname = 'ingest'
        and relations.relkind in ('r', 'p', 'v', 'm', 'S')
        and pg_has_role(
          'pokecrack_nostr_attestor', relations.relowner, 'USAGE'
        )
    )
  )
);
$attestation$;

alter function ingest.verify_nostr_release_v1() owner to postgres;
revoke all on function ingest.verify_nostr_release_v1()
  from public, anon, authenticated, service_role, pokecrack_nostr_attestor;
grant execute on function ingest.verify_nostr_release_v1()
  to pokecrack_nostr_attestor;
comment on function ingest.verify_nostr_release_v1() is
  'Least-privilege Nostr release attestation; callable only after SET ROLE pokecrack_nostr_attestor and returns named boolean checks.';

commit;
