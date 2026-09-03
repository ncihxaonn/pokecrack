begin;

-- The original three-argument verifier established the capability boundary.
-- This overload adds an explicit, fail-closed service-set contract.  The old
-- overload remains owned by postgres for migration compatibility, but its
-- monitor execute grant is revoked below so an operational login can only use
-- this hardened entrypoint.
create or replace function ingest.get_runtime_release_evidence_v1(
  p_release_started_at timestamptz,
  p_grace_seconds integer,
  p_heartbeat_stale_seconds integer,
  p_service_set text
)
returns jsonb
language plpgsql
stable
parallel restricted
security definer
set search_path = pg_catalog, pg_temp
as $function$
declare
  observed_at timestamptz := statement_timestamp();
  release_age_seconds bigint;
  within_grace boolean;

  expected_worker_types text[];
  expected_source_keys text[];
  expected_job_types text[];
  expected_schedule_names text[] := array['catalog_sync', 'cleanup']::text[];
  expected_worker_count bigint;
  expected_source_count bigint;
  expected_schedule_count bigint := 2;

  caller_oid oid;
  monitor_oid oid;

  worker_observed_count bigint;
  worker_healthy_count bigint;
  worker_stale_count bigint;
  worker_missing_count bigint;
  worker_future_count bigint;
  worker_advanced_count bigint;
  worker_max_age_seconds bigint;
  worker_status text;

  source_configured_count bigint;
  source_enabled_count bigint;
  source_disabled_count bigint;
  source_fresh_count bigint;
  source_stale_count bigint;
  source_never_succeeded_count bigint;
  source_future_count bigint;
  source_advanced_count bigint;
  source_status text;

  schedule_slot_count bigint;
  schedule_slots_with_job_count bigint;
  schedule_orphan_slot_count bigint;
  schedule_failed_count bigint;
  schedule_stale_count bigint;
  schedule_future_count bigint;
  latest_slot_at timestamptz;
  latest_job_updated_at timestamptz;
  latest_job_status text;
  latest_slot_age_seconds bigint;
  latest_job_age_seconds bigint;
  schedule_status text;

  queue_live_job_count bigint;
  queue_pending_count bigint;
  queue_running_count bigint;
  queue_completed_count bigint;
  queue_failed_count bigint;
  queue_dead_count bigint;
  queue_cancelled_count bigint;
  queue_future_created_count bigint;
  queue_pending_under_5m bigint;
  queue_pending_5m_to_1h bigint;
  queue_pending_1h_to_6h bigint;
  queue_pending_over_6h bigint;
  queue_status text;

  checkpoint_expected_count bigint;
  checkpoint_observed_count bigint;
  checkpoint_fresh_count bigint;
  checkpoint_stale_count bigint;
  checkpoint_never_collected_count bigint;
  checkpoint_future_count bigint;
  checkpoint_advanced_count bigint;
  checkpoint_status text;

  cleanup_slot_count bigint;
  cleanup_completed_count bigint;
  cleanup_latest_status text;
  cleanup_latest_completed_at timestamptz;
  cleanup_latest_age_seconds bigint;
  cleanup_status text;

  overall_status text;
begin
  if p_grace_seconds is null or p_grace_seconds < 0 or p_grace_seconds > 172800 then
    raise exception 'invalid runtime evidence grace window';
  end if;

  if p_heartbeat_stale_seconds is null
     or p_heartbeat_stale_seconds < 30
     or p_heartbeat_stale_seconds > 3600 then
    raise exception 'invalid runtime evidence heartbeat window';
  end if;

  if p_release_started_at is null then
    raise exception 'runtime evidence release start is required';
  end if;

  if p_release_started_at > observed_at + make_interval(mins => 5) then
    raise exception 'runtime evidence release start is in the future';
  end if;

  if p_release_started_at < observed_at - make_interval(days => 30) then
    raise exception 'runtime evidence release start is outside the bounded verification window';
  end if;

  case p_service_set
    when 'tcgdex' then
      expected_worker_types := array['collector', 'scheduler', 'watchdog']::text[];
      expected_source_keys := array['tcgdex_catalog']::text[];
      expected_job_types := array[
        'catalog.tcgdex.sets.sync',
        'maintenance.cleanup'
      ]::text[];
    when 'tcgdex-nostr' then
      expected_worker_types := array[
        'collector', 'scheduler', 'watchdog', 'nostr-collector'
      ]::text[];
      expected_source_keys := array[
        'tcgdex_catalog',
        'nostr_relay_primal',
        'nostr_relay_nos_lol',
        'nostr_relay_nostr_net'
      ]::text[];
      expected_job_types := array[
        'catalog.tcgdex.sets.sync',
        'maintenance.cleanup',
        'source.nostr.relay'
      ]::text[];
    else
      raise exception 'invalid runtime evidence service set';
  end case;

  expected_worker_count := cardinality(expected_worker_types);
  expected_source_count := cardinality(expected_source_keys);
  release_age_seconds := greatest(
    0,
    floor(extract(epoch from (observed_at - p_release_started_at)))::bigint
  );
  within_grace := release_age_seconds <= p_grace_seconds;

  -- PostgreSQL executes SECURITY DEFINER functions as the owner, so inspect
  -- session_user rather than current_user.  Verify the capability itself on
  -- every call as well: a drifted group role could otherwise grant its caller
  -- table access after SET ROLE even when the login remains well-formed.
  select roles.oid
  into monitor_oid
  from pg_catalog.pg_roles as roles
  where roles.rolname = 'pokecrack_runtime_monitor';

  if monitor_oid is null
     or not exists (
       select 1
       from pg_catalog.pg_roles as roles
       where roles.oid = monitor_oid
         and not roles.rolcanlogin
         and not roles.rolinherit
         and not roles.rolsuper
         and not roles.rolcreatedb
         and not roles.rolcreaterole
         and not roles.rolreplication
         and not roles.rolbypassrls
         and roles.rolconnlimit = -1
         and coalesce(roles.rolconfig, '{}'::text[]) = '{}'::text[]
     )
     or exists (
       select 1
       from pg_catalog.pg_auth_members as memberships
       where memberships.member = monitor_oid
         and memberships.roleid <> monitor_oid
     )
     or exists (
       select 1
       from pg_catalog.pg_db_role_setting as settings
       where settings.setrole = monitor_oid
     )
     or exists (
       select 1 from pg_catalog.pg_namespace as namespaces where namespaces.nspowner = monitor_oid
     )
     or exists (
       select 1 from pg_catalog.pg_class as relations where relations.relowner = monitor_oid
     )
     or exists (
       select 1 from pg_catalog.pg_proc as procedures where procedures.proowner = monitor_oid
     )
     or exists (
       select 1 from pg_catalog.pg_database as databases where databases.datdba = monitor_oid
     )
     or exists (
       select 1 from pg_catalog.pg_tablespace as tablespaces where tablespaces.spcowner = monitor_oid
     )
     or exists (
       select 1
       from pg_catalog.pg_namespace as namespaces
       cross join lateral aclexplode(
         coalesce(namespaces.nspacl, '{}'::aclitem[])
       ) as grants
       where grants.grantee = monitor_oid
         and not (
           namespaces.nspname = 'ingest'
           and grants.privilege_type = 'USAGE'
         )
     )
     or exists (
       select 1
       from pg_catalog.pg_class as relations
       cross join lateral aclexplode(
         coalesce(relations.relacl, '{}'::aclitem[])
       ) as grants
       where grants.grantee = monitor_oid
     )
     or exists (
       select 1
       from pg_catalog.pg_proc as procedures
       cross join lateral aclexplode(
         coalesce(procedures.proacl, '{}'::aclitem[])
       ) as grants
       where grants.grantee = monitor_oid
         and (
           procedures.oid <> 'ingest.get_runtime_release_evidence_v1(timestamptz,integer,integer,text)'::regprocedure
           or grants.privilege_type <> 'EXECUTE'
         )
     )
     or (select count(*) from pg_catalog.pg_auth_members as memberships
         where memberships.roleid = monitor_oid
           and memberships.member = memberships.grantor
           and memberships.admin_option
           and not memberships.inherit_option
           and not memberships.set_option) > 1
     or exists (
       select 1
       from pg_catalog.pg_auth_members as memberships
       join pg_catalog.pg_roles as members on members.oid = memberships.member
       where memberships.roleid = monitor_oid
         and not (
           memberships.member = memberships.grantor
           and memberships.admin_option
           and not memberships.inherit_option
           and not memberships.set_option
         )
         and not (
           members.rolname = 'pokecrack_runtime_monitor_login'
           and not memberships.admin_option
           and not memberships.inherit_option
           and memberships.set_option
         )
     )
     or (select count(*) from pg_catalog.pg_auth_members as memberships
         join pg_catalog.pg_roles as members on members.oid = memberships.member
         where memberships.roleid = monitor_oid
           and members.rolname = 'pokecrack_runtime_monitor_login'
           and not memberships.admin_option
           and not memberships.inherit_option
           and memberships.set_option) > 1 then
    raise exception 'runtime evidence monitor capability has drifted';
  end if;

  -- The migration runner (postgres) is intentionally allowed for installation
  -- tests.  Every operational login is otherwise the exact NOINHERIT, SET-only
  -- member of the capability and must have no direct application grants.
  if session_user <> 'postgres' then
    select roles.oid
    into caller_oid
    from pg_catalog.pg_roles as roles
    where roles.rolname = session_user;

    if caller_oid is null
       or not exists (
         select 1
         from pg_catalog.pg_roles as roles
         where roles.oid = caller_oid
           and roles.rolcanlogin
           and not roles.rolinherit
           and not roles.rolsuper
           and not roles.rolcreatedb
           and not roles.rolcreaterole
           and not roles.rolreplication
           and not roles.rolbypassrls
           and roles.rolconnlimit = 2
           and coalesce(roles.rolconfig, '{}'::text[]) = '{}'::text[]
       )
       or (select count(*) from pg_catalog.pg_auth_members as memberships
           where memberships.member = caller_oid) <> 1
       or not exists (
         select 1
         from pg_catalog.pg_auth_members as memberships
         where memberships.member = caller_oid
           and memberships.roleid = monitor_oid
           and memberships.set_option
           and not memberships.inherit_option
           and not memberships.admin_option
       ) then
      raise exception 'runtime evidence monitor login is not an exact capability member';
    end if;

    if exists (
      select 1 from pg_catalog.pg_namespace as namespaces where namespaces.nspowner = caller_oid
    )
    or exists (
      select 1 from pg_catalog.pg_class as relations where relations.relowner = caller_oid
    )
    or exists (
      select 1 from pg_catalog.pg_proc as procedures where procedures.proowner = caller_oid
    )
    or exists (
      select 1 from pg_catalog.pg_database as databases where databases.datdba = caller_oid
    )
    or exists (
      select 1 from pg_catalog.pg_tablespace as tablespaces where tablespaces.spcowner = caller_oid
    ) then
      raise exception 'runtime evidence monitor login owns application objects';
    end if;

    if exists (
      select 1
      from pg_catalog.pg_namespace as namespaces
      cross join lateral aclexplode(
        coalesce(namespaces.nspacl, '{}'::aclitem[])
      ) as grants
      where grants.grantee = caller_oid
    )
    or exists (
      select 1
      from pg_catalog.pg_class as relations
      cross join lateral aclexplode(
        coalesce(relations.relacl, '{}'::aclitem[])
      ) as grants
      where grants.grantee = caller_oid
    )
    or exists (
      select 1
      from pg_catalog.pg_proc as procedures
      cross join lateral aclexplode(
        coalesce(procedures.proacl, '{}'::aclitem[])
      ) as grants
      where grants.grantee = caller_oid
    ) then
      raise exception 'runtime evidence monitor login has direct application grants';
    end if;
  end if;

  with expected(worker_type) as (
    select unnest(expected_worker_types)
  ), latest as (
    select heartbeats.worker_type, max(heartbeats.last_seen_at) as last_seen_at
    from ingest.worker_heartbeats as heartbeats
    where heartbeats.is_demo = false
      and heartbeats.worker_type = any(expected_worker_types)
    group by heartbeats.worker_type
  )
  select
    count(latest.worker_type)::bigint,
    count(*) filter (
      where latest.last_seen_at is not null
        and latest.last_seen_at <= observed_at
        and latest.last_seen_at >= observed_at
          - make_interval(secs => p_heartbeat_stale_seconds)
    )::bigint,
    count(*) filter (
      where latest.last_seen_at is not null
        and latest.last_seen_at < observed_at
          - make_interval(secs => p_heartbeat_stale_seconds)
    )::bigint,
    count(*) filter (where latest.last_seen_at is null)::bigint,
    count(*) filter (where latest.last_seen_at > observed_at)::bigint,
    count(*) filter (where latest.last_seen_at >= p_release_started_at
      and latest.last_seen_at <= observed_at)::bigint,
    max(greatest(0, floor(extract(epoch from (observed_at - latest.last_seen_at)))::bigint))
      filter (where latest.last_seen_at is not null and latest.last_seen_at <= observed_at)
  into worker_observed_count, worker_healthy_count, worker_stale_count,
       worker_missing_count, worker_future_count, worker_advanced_count,
       worker_max_age_seconds
  from expected
  left join latest using (worker_type);

  worker_status := case
    when worker_observed_count <> expected_worker_count
      or worker_healthy_count <> expected_worker_count
      or worker_stale_count > 0
      or worker_missing_count > 0
      or worker_future_count > 0
      or worker_advanced_count <> expected_worker_count then
      case when within_grace then 'warming_up' else 'failed' end
    else 'healthy'
  end;

  with expected(source_key) as (
    select unnest(expected_source_keys)
  )
  select
    count(policies.id)::bigint,
    count(*) filter (where policies.enabled)::bigint,
    count(*) filter (where policies.id is not null and not policies.enabled)::bigint,
    count(*) filter (
      where policies.enabled
        and policies.last_success_at is not null
        and policies.last_success_at <= observed_at
        and policies.last_success_at >= observed_at
          - make_interval(secs => greatest(policies.expected_interval_seconds * 2, 300))
    )::bigint,
    count(*) filter (
      where policies.enabled
        and policies.last_success_at is not null
        and policies.last_success_at <= observed_at
        and policies.last_success_at < observed_at
          - make_interval(secs => greatest(policies.expected_interval_seconds * 2, 300))
    )::bigint,
    count(*) filter (where policies.enabled and policies.last_success_at is null)::bigint,
    count(*) filter (where policies.enabled and policies.last_success_at > observed_at)::bigint,
    count(*) filter (
      where policies.enabled
        and policies.last_success_at >= p_release_started_at
        and policies.last_success_at <= observed_at
    )::bigint
  into source_configured_count, source_enabled_count, source_disabled_count,
       source_fresh_count, source_stale_count, source_never_succeeded_count,
       source_future_count, source_advanced_count
  from expected
  left join ingest.source_policies as policies
    on policies.source_key = expected.source_key
    and policies.is_demo = false;

  source_status := case
    when source_configured_count <> expected_source_count
      or source_enabled_count <> expected_source_count
      or source_disabled_count > 0
      or source_fresh_count <> expected_source_count
      or source_stale_count > 0
      or source_never_succeeded_count > 0
      or source_future_count > 0
      or source_advanced_count <> expected_source_count then
      case when within_grace then 'warming_up' else 'failed' end
    else 'healthy'
  end;

  with expected(source_key) as (
    select unnest(expected_source_keys)
  ), checkpoint_rows as (
    select
      expected.source_key,
      policies.expected_interval_seconds,
      case
        when expected.source_key = 'tcgdex_catalog' then catalog_state.last_checked_at
        when nostr_checkpoints.last_checkpoint is null then null
        else nostr_checkpoints.updated_at
      end as freshness_at
    from expected
    left join ingest.source_policies as policies
      on policies.source_key = expected.source_key
      and policies.is_demo = false
    left join catalog.sync_state as catalog_state
      on expected.source_key = 'tcgdex_catalog'
      and catalog_state.source = 'tcgdex'
      and catalog_state.scope = 'sets'
      and catalog_state.language = 'en'
      and catalog_state.is_demo = false
    left join ingest.nostr_relay_checkpoints as nostr_checkpoints
      on expected.source_key <> 'tcgdex_catalog'
      and nostr_checkpoints.source_policy_id = policies.id
      and nostr_checkpoints.is_demo = false
  )
  select
    count(*)::bigint,
    count(*) filter (where freshness_at is not null)::bigint,
    count(*) filter (
      where freshness_at is not null
        and freshness_at <= observed_at
        and freshness_at >= observed_at
          - make_interval(secs => greatest(expected_interval_seconds * 2, 300))
    )::bigint,
    count(*) filter (
      where freshness_at is not null
        and freshness_at <= observed_at
        and freshness_at < observed_at
          - make_interval(secs => greatest(expected_interval_seconds * 2, 300))
    )::bigint,
    count(*) filter (where freshness_at is null)::bigint,
    count(*) filter (where freshness_at > observed_at)::bigint,
    count(*) filter (
      where freshness_at >= p_release_started_at
        and freshness_at <= observed_at
    )::bigint
  into checkpoint_expected_count, checkpoint_observed_count,
       checkpoint_fresh_count, checkpoint_stale_count,
       checkpoint_never_collected_count, checkpoint_future_count,
       checkpoint_advanced_count
  from checkpoint_rows;

  checkpoint_status := case
    when checkpoint_observed_count <> expected_source_count
      or checkpoint_fresh_count <> expected_source_count
      or checkpoint_stale_count > 0
      or checkpoint_never_collected_count > 0
      or checkpoint_future_count > 0
      or checkpoint_advanced_count <> expected_source_count then
      case when within_grace then 'warming_up' else 'failed' end
    else 'healthy'
  end;

  with expected(schedule_name) as (
    select unnest(expected_schedule_names)
  ), latest as (
    select
      expected.schedule_name,
      slots.slot_at,
      jobs.status,
      jobs.updated_at,
      (jobs.id is not null) as has_job
    from expected
    left join lateral (
      select slots.slot_at, slots.job_id
      from ingest.schedule_slots as slots
      where slots.schedule_name = expected.schedule_name
        and slots.slot_at >= p_release_started_at
        and slots.slot_at <= observed_at
      order by slots.slot_at desc
      limit 1
    ) as slots on true
    left join ingest.jobs as jobs
      on jobs.id = slots.job_id
      and jobs.is_demo = false
  )
  select
    count(*) filter (where slot_at is not null)::bigint,
    count(*) filter (where has_job)::bigint,
    count(*) filter (where slot_at is not null and not has_job)::bigint,
    count(*) filter (where status in ('failed', 'dead', 'cancelled'))::bigint,
    count(*) filter (
      where slot_at is not null
        and (
          observed_at - slot_at > make_interval(hours => 36)
          or observed_at - coalesce(updated_at, slot_at) > make_interval(hours => 36)
        )
    )::bigint,
    count(*) filter (where updated_at > observed_at)::bigint,
    max(slot_at),
    max(updated_at) filter (where updated_at is not null),
    coalesce((array_agg(status order by slot_at desc nulls last)
      filter (where slot_at is not null))[1], 'none')
  into schedule_slot_count, schedule_slots_with_job_count,
       schedule_orphan_slot_count, schedule_failed_count, schedule_stale_count,
       schedule_future_count, latest_slot_at,
       latest_job_updated_at, latest_job_status
  from latest;

  latest_slot_age_seconds := case
    when latest_slot_at is null then null
    else greatest(0, floor(extract(epoch from (observed_at - latest_slot_at)))::bigint)
  end;
  latest_job_age_seconds := case
    when latest_job_updated_at is null then null
    else greatest(0, floor(extract(epoch from (observed_at - latest_job_updated_at)))::bigint)
  end;

  schedule_status := case
    when schedule_slot_count <> expected_schedule_count
      or schedule_slots_with_job_count <> expected_schedule_count
      or schedule_orphan_slot_count > 0
      or schedule_failed_count > 0
      or schedule_stale_count > 0
      or schedule_future_count > 0 then
      case when within_grace then 'warming_up' else 'failed' end
    else 'advancing'
  end;

  select
    count(*) filter (where jobs.status in ('pending', 'running', 'completed', 'failed', 'dead', 'cancelled'))::bigint,
    count(*) filter (where jobs.status = 'pending')::bigint,
    count(*) filter (where jobs.status = 'running')::bigint,
    count(*) filter (where jobs.status = 'completed')::bigint,
    count(*) filter (where jobs.status = 'failed')::bigint,
    count(*) filter (where jobs.status = 'dead')::bigint,
    count(*) filter (where jobs.status = 'cancelled')::bigint,
    count(*) filter (where jobs.created_at > observed_at)::bigint,
    count(*) filter (where jobs.status = 'pending'
      and jobs.created_at <= observed_at
      and observed_at - jobs.created_at < make_interval(mins => 5))::bigint,
    count(*) filter (where jobs.status = 'pending'
      and observed_at - jobs.created_at >= make_interval(mins => 5)
      and observed_at - jobs.created_at < make_interval(hours => 1))::bigint,
    count(*) filter (where jobs.status = 'pending'
      and observed_at - jobs.created_at >= make_interval(hours => 1)
      and observed_at - jobs.created_at < make_interval(hours => 6))::bigint,
    count(*) filter (where jobs.status = 'pending'
      and observed_at - jobs.created_at >= make_interval(hours => 6))::bigint
  into queue_live_job_count, queue_pending_count, queue_running_count,
       queue_completed_count, queue_failed_count, queue_dead_count,
       queue_cancelled_count, queue_future_created_count,
       queue_pending_under_5m, queue_pending_5m_to_1h,
       queue_pending_1h_to_6h, queue_pending_over_6h
  from ingest.jobs as jobs
  where jobs.is_demo = false
    and jobs.job_type = any(expected_job_types)
    and jobs.created_at >= p_release_started_at;

  queue_status := case
    when queue_failed_count > 0
      or queue_dead_count > 0
      or queue_cancelled_count > 0
      or queue_pending_over_6h > 0
      or queue_future_created_count > 0 then 'failed'
    when queue_pending_count > 0 or queue_running_count > 0 then 'backlog'
    else 'healthy'
  end;

  with cleanup_rows as (
    select slots.slot_at, jobs.status, jobs.completed_at
    from ingest.schedule_slots as slots
    left join ingest.jobs as jobs
      on jobs.id = slots.job_id
      and jobs.is_demo = false
    where slots.schedule_name = 'cleanup'
      and slots.slot_at >= p_release_started_at
      and slots.slot_at <= observed_at
  )
  select
    count(*)::bigint,
    count(*) filter (where status = 'completed')::bigint
  into cleanup_slot_count, cleanup_completed_count
  from cleanup_rows;

  with cleanup_rows as (
    select slots.slot_at, jobs.status, jobs.completed_at
    from ingest.schedule_slots as slots
    left join ingest.jobs as jobs
      on jobs.id = slots.job_id
      and jobs.is_demo = false
    where slots.schedule_name = 'cleanup'
      and slots.slot_at >= p_release_started_at
      and slots.slot_at <= observed_at
  )
  select coalesce(status, 'none'), completed_at
  into cleanup_latest_status, cleanup_latest_completed_at
  from cleanup_rows
  order by slot_at desc
  limit 1;

  cleanup_latest_age_seconds := case
    when cleanup_latest_completed_at is null then null
    else greatest(0, floor(extract(epoch from (observed_at - cleanup_latest_completed_at)))::bigint)
  end;

  cleanup_status := case
    when cleanup_slot_count = 0
      or cleanup_completed_count = 0
      or cleanup_latest_status in ('failed', 'dead', 'cancelled')
      or cleanup_latest_completed_at is null
      or cleanup_latest_age_seconds > 129600
      or cleanup_latest_completed_at > observed_at then
      case when within_grace then 'warming_up' else 'failed' end
    else 'healthy'
  end;

  overall_status := case
    when worker_status = 'failed'
      or source_status = 'failed'
      or schedule_status = 'failed'
      or queue_status = 'failed'
      or checkpoint_status = 'failed'
      or cleanup_status = 'failed' then 'failed'
    when worker_status = 'healthy'
      and source_status = 'healthy'
      and schedule_status = 'advancing'
      and queue_status in ('healthy', 'backlog')
      and checkpoint_status = 'healthy'
      and cleanup_status = 'healthy' then 'healthy'
    when within_grace then 'warming_up'
    else 'failed'
  end;

  return jsonb_build_object(
    'schema_version', '1.0.0',
    'status', overall_status,
    'release_age_seconds', release_age_seconds,
    'grace_seconds', p_grace_seconds,
    'workers', jsonb_build_object(
      'expected_count', expected_worker_count,
      'observed_count', worker_observed_count,
      'healthy_count', worker_healthy_count,
      'stale_count', worker_stale_count,
      'missing_count', worker_missing_count,
      'future_count', worker_future_count,
      'max_age_seconds', worker_max_age_seconds,
      'status', worker_status
    ),
    'sources', jsonb_build_object(
      'configured_count', source_configured_count,
      'enabled_count', source_enabled_count,
      'disabled_count', source_disabled_count,
      'fresh_count', source_fresh_count,
      'stale_count', source_stale_count,
      'never_succeeded_count', source_never_succeeded_count,
      'future_count', source_future_count,
      'advanced_since_release_count', source_advanced_count,
      'status', source_status
    ),
    'schedule', jsonb_build_object(
      'slot_count', schedule_slot_count,
      'slots_with_job_count', schedule_slots_with_job_count,
      'orphan_slot_count', schedule_orphan_slot_count,
      'latest_slot_age_seconds', latest_slot_age_seconds,
      'latest_job_age_seconds', latest_job_age_seconds,
      'latest_job_status', latest_job_status,
      'status', schedule_status
    ),
    'queue', jsonb_build_object(
      'live_job_count', queue_live_job_count,
      'pending_count', queue_pending_count,
      'running_count', queue_running_count,
      'completed_count', queue_completed_count,
      'failed_count', queue_failed_count,
      'dead_count', queue_dead_count,
      'cancelled_count', queue_cancelled_count,
      'future_created_count', queue_future_created_count,
      'pending_age_bands', jsonb_build_object(
        'under_5m', queue_pending_under_5m,
        '5m_to_1h', queue_pending_5m_to_1h,
        '1h_to_6h', queue_pending_1h_to_6h,
        'over_6h', queue_pending_over_6h
      ),
      'status', queue_status
    ),
    'checkpoints', jsonb_build_object(
      'expected_count', checkpoint_expected_count,
      'observed_count', checkpoint_observed_count,
      'fresh_count', checkpoint_fresh_count,
      'stale_count', checkpoint_stale_count,
      'never_collected_count', checkpoint_never_collected_count,
      'future_count', checkpoint_future_count,
      'status', checkpoint_status
    ),
    'cleanup', jsonb_build_object(
      'scheduled_count', cleanup_slot_count,
      'completed_count', cleanup_completed_count,
      'latest_status', coalesce(cleanup_latest_status, 'none'),
      'latest_age_seconds', cleanup_latest_age_seconds,
      'status', cleanup_status
    )
  );
end;
$function$;

alter function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer, text)
  owner to postgres;
revoke all on function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer, text)
  from public, anon, authenticated, service_role;
grant execute on function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer, text)
  to pokecrack_runtime_monitor;

-- Do not leave the pre-hardening overload as a bypass around the service-set
-- and monitor-login attestation above.
revoke execute on function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer)
  from pokecrack_runtime_monitor;

comment on function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer, text)
  is 'Private, service-set-scoped release verifier. Returns aggregate counts and states only; monitor logins are attested at call time.';

commit;
