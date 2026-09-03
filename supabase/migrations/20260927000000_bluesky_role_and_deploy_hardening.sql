begin;

-- The Bluesky capability role is created here only when it is missing.  A
-- separately provisioned owner login is intentionally never created or
-- modified by a migration: its password remains outside the repository.
do $roles$
declare
  bluesky_role_oid oid;
  role_is_exact boolean;
begin
  if not exists (
    select 1
    from pg_catalog.pg_roles
    where rolname = 'pokecrack_bluesky_worker'
  ) then
    create role pokecrack_bluesky_worker
      nologin
      noinherit
      nosuperuser
      nocreatedb
      nocreaterole
      noreplication
      nobypassrls
      connection limit -1;

    select roles.oid
    into bluesky_role_oid
    from pg_catalog.pg_roles as roles
    where roles.rolname = 'pokecrack_bluesky_worker';

    -- Keep the creator edge tied to the actual migration owner.  A
    -- non-superuser CREATEROLE actor can receive PostgreSQL's bootstrap
    -- ADMIN-only edge; a superuser receives no implicit edge, so create the
    -- same constrained edge explicitly.  No fixed account name is trusted.
    if not exists (
      select 1
      from pg_catalog.pg_auth_members as memberships
      where memberships.roleid = bluesky_role_oid
        and memberships.admin_option
        and not memberships.inherit_option
        and not memberships.set_option
        and exists (
          select 1
          from pg_catalog.pg_roles as grantor
          where grantor.oid = memberships.grantor
            and grantor.rolsuper
        )
        and exists (
          select 1
          from pg_catalog.pg_roles as owner
          where owner.oid = memberships.member
            and (owner.rolsuper or owner.rolcreaterole)
        )
    ) then
      if exists (
        select 1
        from pg_catalog.pg_auth_members as memberships
        where memberships.roleid = bluesky_role_oid
      ) then
        raise exception using
          errcode = '55000',
          message = 'fresh Bluesky creator edge is not isolated';
      end if;

      grant pokecrack_bluesky_worker
        to current_user
        with admin true, inherit false, set false;
    end if;
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
    where rolname = 'pokecrack_bluesky_worker';
    if role_is_exact is distinct from true then
      raise exception using
        errcode = '55000',
        message = 'existing pokecrack_bluesky_worker role is not the reviewed NOLOGIN contract';
    end if;
  end if;
end;
$roles$;

-- This SECURITY DEFINER proof is deliberately boolean-only.  It lets the
-- host preflight use the named owner-provisioned login without granting that
-- login table reads, and it reports drift rather than repairing it.  In
-- particular, no password, membership, role setting, owner, or ACL is
-- normalised here.
create or replace function ingest.verify_bluesky_release_v1()
returns jsonb
language sql
stable
security definer
set search_path = pg_catalog, pg_temp
as $attestation$
with as_of as (
  select statement_timestamp() as observed_at
),
expected_worker_functions(signature) as (
  values
    ('ingest.enqueue_due_bluesky_jetstream_jobs_v1(text)'::text),
    ('ingest.claim_bluesky_jetstream_jobs_v1(text,integer)'::text),
    ('ingest.heartbeat_bluesky_jetstream_job_v1(uuid,text,bigint,integer)'::text),
    ('ingest.fail_bluesky_jetstream_job_v1(uuid,text,bigint,text,text,boolean)'::text),
    ('ingest.pause_bluesky_jetstream_job_v1(uuid,text,bigint,timestamp with time zone)'::text),
    ('ingest.upsert_bluesky_worker_heartbeat_v1(text,text,jsonb)'::text),
    ('ingest.bluesky_worker_runtime_ready_v1()'::text),
    ('ingest.get_bluesky_worker_policy_snapshot_v1()'::text),
    ('ingest.begin_bluesky_jetstream_job_v1(uuid,text,bigint)'::text),
    ('ingest.finalize_bluesky_jetstream_job_v1(uuid,text,bigint,jsonb)'::text),
    ('ingest.recover_bluesky_cursor_too_old_job_v2(uuid,text,bigint,bigint)'::text),
    ('ingest.verify_bluesky_release_v1()'::text)
),
worker_roles as (
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
      and group_role.rolconnlimit = -1
      and coalesce(group_role.rolconfig, '{}'::text[]) = '{}'::text[] as group_valid,
    login_role.oid is not null
      and not login_role.rolsuper
      and not login_role.rolinherit
      and not login_role.rolcreaterole
      and not login_role.rolcreatedb
      and login_role.rolcanlogin
      and not login_role.rolreplication
      and not login_role.rolbypassrls
      and login_role.rolconnlimit = 2
      and coalesce(login_role.rolconfig, '{}'::text[]) = '{}'::text[] as login_valid
  from pg_catalog.pg_roles as group_role
  left join pg_catalog.pg_roles as login_role
    on login_role.rolname = 'pokecrack_bluesky_worker_login'
  where group_role.rolname = 'pokecrack_bluesky_worker'
),
worker_memberships as (
  select
    memberships.roleid,
    memberships.member,
    memberships.grantor,
    memberships.admin_option,
    memberships.inherit_option,
    memberships.set_option,
    roles.group_oid,
    roles.login_oid,
    memberships.admin_option
      and not memberships.inherit_option
      and not memberships.set_option
      and exists (
        select 1
        from pg_catalog.pg_roles as grantor
        where grantor.oid = memberships.grantor
          and grantor.rolsuper
      )
      and exists (
        select 1
        from pg_catalog.pg_roles as owner
        where owner.oid = memberships.member
          and (owner.rolsuper or owner.rolcreaterole)
      ) as creator_edge_valid,
    roles.login_oid is not null
      and memberships.member = roles.login_oid
      and roles.login_valid
      and not memberships.admin_option
      and not memberships.inherit_option
      and memberships.set_option
      and not exists (
        select 1
        from pg_catalog.pg_auth_members as other_memberships
        where other_memberships.member = roles.login_oid
          and other_memberships.roleid <> roles.group_oid
      ) as dedicated_login_edge_valid
  from pg_catalog.pg_auth_members as memberships
  cross join worker_roles as roles
  where memberships.roleid = roles.group_oid
),
ingest_relations as (
  select relations.oid, relations.relowner, relations.relacl
  from pg_catalog.pg_class as relations
  join pg_catalog.pg_namespace as namespaces
    on namespaces.oid = relations.relnamespace
  where namespaces.nspname = 'ingest'
    and relations.relkind in ('r', 'p', 'v', 'm', 'f')
),
ingest_sequences as (
  select relations.oid, relations.relowner, relations.relacl
  from pg_catalog.pg_class as relations
  join pg_catalog.pg_namespace as namespaces
    on namespaces.oid = relations.relnamespace
  where namespaces.nspname = 'ingest'
    and relations.relkind = 'S'
),
ingest_functions as (
  select functions.oid
  from pg_catalog.pg_proc as functions
  join pg_catalog.pg_namespace as namespaces
    on namespaces.oid = functions.pronamespace
  where namespaces.nspname = 'ingest'
),
worker_function_acl_grants as (
  select
    functions.oid,
    functions.proowner,
    functions.prosecdef,
    functions.proconfig,
    grants.grantee,
    grants.privilege_type,
    grants.is_grantable
  from expected_worker_functions as expected
  join pg_catalog.pg_proc as functions
    on functions.oid = expected.signature::regprocedure
  cross join lateral aclexplode(coalesce(
    functions.proacl,
    acldefault('f'::"char", functions.proowner)
  )) as grants
),
ingest_relation_acl_grants as (
  select relations.oid, grants.grantee
  from ingest_relations as relations
  cross join lateral aclexplode(coalesce(
    relations.relacl,
    acldefault('r'::"char", relations.relowner)
  )) as grants
),
ingest_column_acl_grants as (
  select columns.attrelid as oid, grants.grantee
  from pg_catalog.pg_attribute as columns
  cross join lateral aclexplode(columns.attacl) as grants
  where columns.attrelid in (select oid from ingest_relations)
    and columns.attnum > 0
    and not columns.attisdropped
),
bluesky_relations as (
  select relations.oid, relations.relowner, relations.relacl
  from pg_catalog.pg_class as relations
  join pg_catalog.pg_namespace as namespaces
    on namespaces.oid = relations.relnamespace
  where namespaces.nspname = 'ingest'
    and relations.relname in (
      'bluesky_jetstream_candidates',
      'bluesky_jetstream_observations',
      'bluesky_jetstream_checkpoints'
    )
),
bluesky_relation_acl_grants as (
  select
    relations.oid,
    relations.relowner,
    grants.grantee,
    grants.privilege_type,
    grants.is_grantable
  from bluesky_relations as relations
  cross join lateral aclexplode(coalesce(
    relations.relacl,
    acldefault('r'::"char", relations.relowner)
  )) as grants
),
bluesky_column_acl_grants as (
  select columns.attrelid as oid, grants.grantee, grants.privilege_type
  from pg_catalog.pg_attribute as columns
  cross join lateral aclexplode(columns.attacl) as grants
  where columns.attrelid in (select oid from bluesky_relations)
    and columns.attnum > 0
    and not columns.attisdropped
),
bluesky_sequences as (
  select relations.oid, relations.relowner, relations.relacl
  from pg_catalog.pg_class as relations
  where relations.oid = pg_get_serial_sequence(
    'ingest.bluesky_jetstream_observations', 'id'
  )::regclass
),
bluesky_sequence_acl_grants as (
  select
    sequences.oid,
    sequences.relowner,
    grants.grantee,
    grants.privilege_type,
    grants.is_grantable
  from bluesky_sequences as sequences
  cross join lateral aclexplode(coalesce(
    sequences.relacl,
    acldefault('s'::"char", sequences.relowner)
  )) as grants
),
owned_catalog_objects(owner_oid) as (
  select namespaces.nspowner from pg_catalog.pg_namespace as namespaces
  union all
  select relations.relowner from pg_catalog.pg_class as relations
  union all
  select functions.proowner from pg_catalog.pg_proc as functions
  union all
  select types.typowner from pg_catalog.pg_type as types
  union all
  select databases.datdba from pg_catalog.pg_database as databases
  union all
  select defaults.defaclrole from pg_catalog.pg_default_acl as defaults
  union all
  select extensions.extowner from pg_catalog.pg_extension as extensions
  union all
  select wrappers.fdwowner from pg_catalog.pg_foreign_data_wrapper as wrappers
  union all
  select servers.srvowner from pg_catalog.pg_foreign_server as servers
  union all
  select tablespaces.spcowner from pg_catalog.pg_tablespace as tablespaces
  union all
  select publications.pubowner from pg_catalog.pg_publication as publications
  union all
  select subscriptions.subowner from pg_catalog.pg_subscription as subscriptions
  union all
  select triggers.evtowner from pg_catalog.pg_event_trigger as triggers
  union all
  select languages.lanowner from pg_catalog.pg_language as languages
  union all
  select collations.collowner from pg_catalog.pg_collation as collations
  union all
  select conversions.conowner from pg_catalog.pg_conversion as conversions
  union all
  select dictionaries.dictowner from pg_catalog.pg_ts_dict as dictionaries
  union all
  select configurations.cfgowner from pg_catalog.pg_ts_config as configurations
  union all
  select operators.oprowner from pg_catalog.pg_operator as operators
  union all
  select classes.opcowner from pg_catalog.pg_opclass as classes
  union all
  select families.opfowner from pg_catalog.pg_opfamily as families
  union all
  select statistics.stxowner from pg_catalog.pg_statistic_ext as statistics
  union all
  select objects.lomowner from pg_catalog.pg_largeobject_metadata as objects
  union all
  select mappings.umuser from pg_catalog.pg_user_mapping as mappings
  where mappings.umuser <> 0
),
generic_definitions as (
  select
    lower(pg_get_functiondef(
      'ingest.claim_jobs_v2(text,text[],integer,integer)'::regprocedure
    )) as claim_definition,
    lower(pg_get_functiondef(
      'ingest.heartbeat_job_v2(uuid,text,bigint,integer)'::regprocedure
    )) as heartbeat_definition,
    lower(pg_get_functiondef(
      'ingest.fail_job_v2(uuid,text,bigint,text,text,boolean)'::regprocedure
    )) as fail_definition,
    lower(pg_get_functiondef(
      'ingest.pause_job_for_budget_v2(uuid,text,bigint,timestamptz)'::regprocedure
    )) as pause_definition
)
select jsonb_build_object(
  'postgresql17', current_setting('server_version_num')::integer >= 170000,
  'ledger_210', (
    select count(*) = 1
    from supabase_migrations.schema_migrations
    where version = '20260921000000'
      and name = 'bluesky_worker_role_isolation'
  ),
  'ledger_260', (
    select count(*) = 1
    from supabase_migrations.schema_migrations
    where version = '20260926000000'
      and name = 'bluesky_generic_queue_guard'
  ),
  'ledger_270', (
    select count(*) = 1
    from supabase_migrations.schema_migrations
    where version = '20260927000000'
      and name = 'bluesky_role_and_deploy_hardening'
  ),
  'bluesky_worker_role_exact', (
    (select count(*) = 1
      and count(*) filter (where group_valid and login_valid) = 1
      from worker_roles)
    -- The creator edge is tied to the actual bootstrap owner/grantor rather
    -- than a fixed account name.  A provisioned login is the only optional
    -- second edge and can only SET this capability.
    and (select count(*) = (1
      + case when bool_or(roles.login_oid is null) then 0 else 1 end)
      and count(*) filter (where memberships.creator_edge_valid) = 1
      and count(*) filter (where memberships.dedicated_login_edge_valid)
        = case when bool_or(roles.login_oid is null) then 0 else 1 end
      and bool_and(
        memberships.creator_edge_valid
        or memberships.dedicated_login_edge_valid
      )
      from worker_memberships as memberships
      cross join worker_roles as roles)
    -- The capability must not itself be a member of service_role, postgres,
    -- another worker, or any other role.
    and not exists (
      select 1
      from pg_catalog.pg_auth_members as memberships
      cross join worker_roles as roles
      where memberships.member = roles.group_oid
    )
    -- The login may only SET the exact capability with no inherited/admin
    -- edge; an accidental service_role or worker membership fails closed.
    and not exists (
      select 1
      from pg_catalog.pg_auth_members as memberships
      join worker_roles as roles on roles.login_oid = memberships.member
      where memberships.roleid <> roles.group_oid
    )
    and not exists (
      select 1
      from worker_memberships as memberships
      where not (
        memberships.creator_edge_valid
        or memberships.dedicated_login_edge_valid
      )
    )
    and has_schema_privilege(
      'pokecrack_bluesky_worker', 'ingest', 'USAGE'
    )
    and not has_schema_privilege(
      'pokecrack_bluesky_worker', 'ingest', 'CREATE'
    )
    and not exists (
      select 1
      from worker_roles as roles
      where roles.login_oid is not null
        and has_schema_privilege(roles.login_oid, 'ingest', 'USAGE')
    )
    and (select count(*) = 12
      and bool_and(has_function_privilege(
        'pokecrack_bluesky_worker', signatures.signature, 'EXECUTE'
      ))
      from expected_worker_functions as signatures)
    and (select count(distinct grants.oid) = 12
      and bool_and(
        pg_get_userbyid(grants.proowner) = 'postgres'
        and grants.prosecdef
        and coalesce(grants.proconfig, '{}'::text[])
          = array['search_path=pg_catalog, pg_temp']::text[]
      )
      from worker_function_acl_grants as grants)
    -- No extra ingest function can be reached by the capability, including
    -- a future or drifted generic queue function.
    and not exists (
      select 1 from ingest_functions as functions
      where not exists (
        select 1
        from expected_worker_functions as expected
        where functions.oid = expected.signature::regprocedure
      )
      and has_function_privilege(
        'pokecrack_bluesky_worker', functions.oid, 'EXECUTE'
      )
    )
    and not exists (
      select 1
      from worker_function_acl_grants as grants
      cross join worker_roles as roles
      where grants.privilege_type <> 'EXECUTE'
        or grants.is_grantable
        or grants.grantee not in (grants.proowner, roles.group_oid)
    )
    -- No direct table, view, foreign-table, column, or sequence capability;
    -- all data writes remain behind the fixed SECURITY DEFINER wrappers.
    and not exists (
      select 1 from ingest_relations as relations
      where has_table_privilege('pokecrack_bluesky_worker', relations.oid, 'SELECT')
        or has_table_privilege('pokecrack_bluesky_worker', relations.oid, 'INSERT')
        or has_table_privilege('pokecrack_bluesky_worker', relations.oid, 'UPDATE')
        or has_table_privilege('pokecrack_bluesky_worker', relations.oid, 'DELETE')
        or has_table_privilege('pokecrack_bluesky_worker', relations.oid, 'REFERENCES')
        or has_table_privilege('pokecrack_bluesky_worker', relations.oid, 'TRIGGER')
        or has_table_privilege('pokecrack_bluesky_worker', relations.oid, 'MAINTAIN')
        or has_any_column_privilege(
          'pokecrack_bluesky_worker', relations.oid,
          'SELECT,INSERT,UPDATE,REFERENCES'
        )
    )
    and not exists (
      select 1
      from ingest_relation_acl_grants as grants
      where case
        when grants.grantee = 0 then true
        else pg_has_role('pokecrack_bluesky_worker', grants.grantee, 'USAGE')
      end
    )
    and not exists (
      select 1
      from ingest_column_acl_grants as grants
      where case
        when grants.grantee = 0 then true
        else pg_has_role('pokecrack_bluesky_worker', grants.grantee, 'USAGE')
      end
    )
    and not exists (
      select 1 from ingest_relations as relations
      where pg_has_role(
        'pokecrack_bluesky_worker', relations.relowner, 'USAGE'
      )
    )
    and not exists (
      select 1 from ingest_sequences as sequences
      where has_sequence_privilege('pokecrack_bluesky_worker', sequences.oid, 'USAGE')
        or has_sequence_privilege('pokecrack_bluesky_worker', sequences.oid, 'SELECT')
        or has_sequence_privilege('pokecrack_bluesky_worker', sequences.oid, 'UPDATE')
    )
    and not exists (
      select 1
      from worker_roles as roles
      join ingest_functions as functions on roles.login_oid is not null
      where has_function_privilege(roles.login_oid, functions.oid, 'EXECUTE')
    )
    and not exists (
      select 1
      from worker_roles as roles
      join ingest_relations as relations on roles.login_oid is not null
      where has_table_privilege(roles.login_oid, relations.oid, 'SELECT')
        or has_table_privilege(roles.login_oid, relations.oid, 'INSERT')
        or has_table_privilege(roles.login_oid, relations.oid, 'UPDATE')
        or has_table_privilege(roles.login_oid, relations.oid, 'DELETE')
        or has_table_privilege(roles.login_oid, relations.oid, 'REFERENCES')
        or has_table_privilege(roles.login_oid, relations.oid, 'TRIGGER')
        or has_table_privilege(roles.login_oid, relations.oid, 'MAINTAIN')
        or has_any_column_privilege(
          roles.login_oid, relations.oid, 'SELECT,INSERT,UPDATE,REFERENCES'
        )
    )
    and not exists (
      select 1
      from worker_roles as roles
      join ingest_relation_acl_grants as grants on roles.login_oid is not null
      where case
        when grants.grantee = 0 then true
        else pg_has_role(roles.login_oid, grants.grantee, 'USAGE')
      end
    )
    and not exists (
      select 1
      from worker_roles as roles
      join ingest_relations as relations on roles.login_oid is not null
      where pg_has_role(roles.login_oid, relations.relowner, 'USAGE')
    )
    and not exists (
      select 1
      from worker_roles as roles
      join ingest_sequences as sequences on roles.login_oid is not null
      where has_sequence_privilege(roles.login_oid, sequences.oid, 'USAGE')
        or has_sequence_privilege(roles.login_oid, sequences.oid, 'SELECT')
        or has_sequence_privilege(roles.login_oid, sequences.oid, 'UPDATE')
    )
    -- Role-level settings include both ALTER ROLE ... SET and per-database
    -- settings. The check is intentionally read-only and catches either.
    and not exists (
      select 1
      from pg_catalog.pg_db_role_setting as settings
      join worker_roles as roles
        on settings.setrole in (roles.group_oid, roles.login_oid)
    )
    and not exists (
      select 1
      from owned_catalog_objects as objects
      join worker_roles as roles
        on objects.owner_oid in (roles.group_oid, roles.login_oid)
    )
    -- The capability must not retain any generic queue lifecycle entry point.
    and (select bool_and(not has_function_privilege(
      'pokecrack_bluesky_worker', signatures.signature, 'EXECUTE'
    )) from (values
      ('ingest.claim_jobs_v2(text,text[],integer,integer)'::text),
      ('ingest.heartbeat_job_v2(uuid,text,bigint,integer)'::text),
      ('ingest.fail_job_v2(uuid,text,bigint,text,text,boolean)'::text),
      ('ingest.pause_job_for_budget_v2(uuid,text,bigint,timestamp with time zone)'::text),
      ('ingest.upsert_worker_heartbeat_v1(text,text,text,jsonb)'::text)
    ) as signatures(signature))
    and (select
      claim_definition like '%source.bluesky.jetstream%'
      and heartbeat_definition like '%source.bluesky.jetstream%'
      and fail_definition like '%source.bluesky.jetstream%'
      and pause_definition like '%source.bluesky.jetstream%'
      from generic_definitions)
  ),
  'bluesky_policy_exact', (
    exists (
      select 1
      from ingest.source_policies as policies
      where policies.source_key = 'bluesky_jetstream'
        and policies.display_name = 'Bluesky Jetstream discovery'
        and policies.source_kind = 'official_api'
        and policies.domain = 'jetstream.us-west.bsky.network'
        and policies.base_url =
          'wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents'
        and policies.enabled
        and policies.collector_type = 'bluesky_jetstream'
        and policies.access_mode = 'official_api'
        and policies.robots_policy = 'not_applicable'
        and policies.routes = array['bluesky_jetstream']::text[]
        and not policies.include_subdomains
        and policies.min_delay_seconds = 1
        and policies.max_pages_per_run = 1
        and policies.max_items_per_run = 100
        and policies.max_concurrency = 1
        and policies.browser_profile is null
        and not policies.statistics_eligible_default
        and policies.retention_days = 30
        and policies.config = '{
          "endpoint":"wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents",
          "collection":"app.bsky.feed.post",
          "operations":["create","update","delete"],
          "kinds":["commit"],
          "subprotocol":"xrpc.v1.json",
          "stream_window_seconds":10,
          "max_events":10000,
          "max_message_bytes":262144,
          "max_stream_bytes":2097152,
          "max_candidates":100,
          "max_deletions":100,
          "max_excerpt_chars":500,
          "keyword_registry":"bluesky-keywords-v1",
          "statistics_eligible":false
        }'::jsonb
        and policies.version = 'bluesky-jetstream-v1'
        and policies.expected_interval_seconds = 60
        and not policies.is_demo
    )
    and (select count(*) = 1
      and coalesce(bool_and(
        (
          gates.owner_job_id is null
          and gates.owner_lease_generation is null
          and gates.acquired_at is null
          and gates.active_until is null
        )
        or (
          gates.owner_job_id is not null
          and gates.owner_lease_generation >= 1
          and gates.acquired_at is not null
          and gates.acquired_at <= as_of.observed_at
          and gates.active_until is not null
          and gates.active_until > gates.acquired_at
          and gates.active_until > as_of.observed_at
          and jobs.id = gates.owner_job_id
          and jobs.status = 'running'
          and jobs.job_type = 'source.bluesky.jetstream'
          and jobs.payload = '{}'::jsonb
          and not jobs.is_demo
          and jobs.attempts < jobs.max_attempts
          and jobs.locked_by ~ '^bluesky-collector-[a-z0-9][a-z0-9_.-]{0,63}$'
          and jobs.locked_at is not null
          and jobs.locked_at <= as_of.observed_at
          and jobs.lease_generation = gates.owner_lease_generation
          and jobs.lock_expires_at is not null
          and jobs.lock_expires_at > jobs.locked_at
          and jobs.lock_expires_at > as_of.observed_at
          and jobs.lock_expires_at = gates.active_until
        )
      ), false)
      from ingest.source_request_gates as gates
      cross join as_of
      left join ingest.jobs as jobs
        on jobs.id = gates.owner_job_id
      where gates.source_key = 'bluesky_jetstream')
  ),
  'bluesky_acl_exact', (
    -- The three private tables retain PostgreSQL's complete owner ACL plus
    -- the historical service_role SELECT-only projection.  This categorical
    -- ACL proof rejects every unexpected table/column grant or owner drift.
    (select count(*) = 3
      and count(*) filter (
        where relations.relkind = 'r'
          and relations.relrowsecurity
          and relations.relforcerowsecurity
          and pg_get_userbyid(relations.relowner) = 'postgres'
      ) = 3
      from bluesky_relations as relations)
    and (select count(*) = 27
      and count(*) filter (where grants.grantee = grants.relowner) = 24
      and count(*) filter (
        where grants.grantee = 'service_role'::regrole
          and grants.privilege_type = 'SELECT'
      ) = 3
      and count(distinct grants.privilege_type) filter (
        where grants.grantee = grants.relowner
      ) = 8
      and bool_and(not grants.is_grantable)
      from bluesky_relation_acl_grants as grants)
    and (select count(*) = 0 from bluesky_column_acl_grants)
    and (select count(*) = 3
      and count(*) filter (where grants.grantee = grants.relowner) = 3
      and count(distinct grants.privilege_type) = 3
      and bool_and(not grants.is_grantable)
      from bluesky_sequence_acl_grants as grants)
    and (select count(*) = 1
      and bool_and(pg_get_userbyid(sequences.relowner) = 'postgres')
      from bluesky_sequences as sequences)
    and not exists (
      select 1
      from bluesky_relation_acl_grants as grants
      where grants.grantee not in (grants.relowner, 'service_role'::regrole)
    )
    and (select count(*) = 3 and bool_and(
      has_table_privilege('service_role', relations.oid, 'SELECT')
        and not has_table_privilege('service_role', relations.oid, 'INSERT')
        and not has_table_privilege('service_role', relations.oid, 'UPDATE')
        and not has_table_privilege('service_role', relations.oid, 'DELETE')
        and not has_table_privilege('anon', relations.oid, 'SELECT')
        and not has_table_privilege('authenticated', relations.oid, 'SELECT')
    ) from bluesky_relations as relations)
    and not exists (
      select 1
      from bluesky_sequences as sequences
      cross join unnest(array[
        'service_role', 'anon', 'authenticated',
        'pokecrack_bluesky_worker'
      ]::name[]) as checked_roles(role_name)
      where has_sequence_privilege(checked_roles.role_name, sequences.oid, 'USAGE')
        or has_sequence_privilege(checked_roles.role_name, sequences.oid, 'SELECT')
        or has_sequence_privilege(checked_roles.role_name, sequences.oid, 'UPDATE')
        or pg_has_role(checked_roles.role_name, sequences.relowner, 'USAGE')
    )
    and (select count(*) = 3
      from pg_catalog.pg_policies as policies
      where policies.schemaname = 'ingest'
        and policies.tablename in (
          'bluesky_jetstream_candidates',
          'bluesky_jetstream_observations',
          'bluesky_jetstream_checkpoints'
        ))
    and (select count(*) = 3 and bool_and(
      policies.policyname = expected.policy_name
        and policies.cmd = 'SELECT'
        and policies.roles = array['service_role']::name[]
        and lower(replace(coalesce(policies.qual, ''), ' ', '')) = '(notis_demo)'
        and policies.with_check is null
    )
      from (values
        ('bluesky_jetstream_candidates', 'bluesky_candidates_service_role_select'),
        ('bluesky_jetstream_observations', 'bluesky_observations_service_role_select'),
        ('bluesky_jetstream_checkpoints', 'bluesky_checkpoints_service_role_select')
      ) as expected(table_name, policy_name)
      left join pg_catalog.pg_policies as policies
        on policies.schemaname = 'ingest'
        and policies.tablename = expected.table_name)
  )
);
$attestation$;

alter function ingest.verify_bluesky_release_v1() owner to postgres;
revoke all on function ingest.verify_bluesky_release_v1()
  from public, anon, authenticated, service_role, pokecrack_bluesky_worker;
grant execute on function ingest.verify_bluesky_release_v1()
  to pokecrack_bluesky_worker;

comment on function ingest.verify_bluesky_release_v1() is
  'Boolean-only Bluesky role/login/deployment attestation; callable only through the fixed Bluesky capability role and never repairs drift.';

commit;
