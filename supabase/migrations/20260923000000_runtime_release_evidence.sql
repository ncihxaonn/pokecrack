begin;

-- This capability is intentionally separate from worker roles.  An operator may
-- provision a NOINHERIT login outside migrations and grant it membership in this
-- role; the application never receives a monitor credential.
do $roles$
begin
  if not exists (select 1 from pg_roles where rolname = 'pokecrack_runtime_monitor') then
    create role pokecrack_runtime_monitor
      nologin noinherit nosuperuser nocreatedb nocreaterole noreplication nobypassrls
      connection limit -1;
  end if;

  revoke all on schema ingest from pokecrack_runtime_monitor;
  revoke all on all tables in schema ingest from pokecrack_runtime_monitor;
  revoke all on all sequences in schema ingest from pokecrack_runtime_monitor;
  revoke all on all functions in schema ingest from pokecrack_runtime_monitor;
  grant usage on schema ingest to pokecrack_runtime_monitor;
end;
$roles$;

create or replace function ingest.get_runtime_release_evidence_v1(
  p_release_started_at timestamptz default null,
  p_grace_seconds integer default 21600,
  p_heartbeat_stale_seconds integer default 180
)
returns jsonb
language plpgsql
stable
parallel restricted
security definer
set search_path = pg_catalog
as $function$
declare
  observed_at timestamptz := statement_timestamp();
  release_age_seconds bigint;
  within_grace boolean;

  worker_expected_count bigint;
  worker_observed_count bigint;
  worker_healthy_count bigint;
  worker_stale_count bigint;
  worker_missing_count bigint;
  worker_future_count bigint;
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

  if p_release_started_at is not null
     and p_release_started_at > observed_at + make_interval(mins => 5) then
    raise exception 'runtime evidence release start is in the future';
  end if;

  release_age_seconds := case
    when p_release_started_at is null then null
    else greatest(0, floor(extract(epoch from (observed_at - p_release_started_at)))::bigint)
  end;
  within_grace := p_release_started_at is null
    or release_age_seconds <= p_grace_seconds;

  -- Only the expected worker-type aggregate is returned; worker identifiers and
  -- current-job identifiers are deliberately never selected into the result.
  with expected(worker_type) as (
    values ('collector'::text), ('scheduler'::text), ('watchdog'::text)
  ), latest as (
    select worker_type, max(last_seen_at) as last_seen_at
    from ingest.worker_heartbeats
    where is_demo = false
    group by worker_type
  )
  select
    count(*)::bigint,
    count(latest.worker_type)::bigint,
    count(*) filter (where latest.last_seen_at is not null
      and latest.last_seen_at <= observed_at
      and latest.last_seen_at >= observed_at - make_interval(secs => p_heartbeat_stale_seconds))::bigint,
    count(*) filter (where latest.last_seen_at is not null
      and latest.last_seen_at < observed_at - make_interval(secs => p_heartbeat_stale_seconds))::bigint,
    count(*) filter (where latest.last_seen_at is null)::bigint,
    count(*) filter (where latest.last_seen_at > observed_at)::bigint,
    max(greatest(0, floor(extract(epoch from (observed_at - latest.last_seen_at)))::bigint))
      filter (where latest.last_seen_at is not null and latest.last_seen_at <= observed_at)
  into worker_expected_count, worker_observed_count, worker_healthy_count,
       worker_stale_count, worker_missing_count, worker_future_count,
       worker_max_age_seconds
  from expected
  left join latest using (worker_type);

  worker_status := case
    when worker_stale_count > 0 or worker_missing_count > 0 or worker_future_count > 0 then
      case when within_grace then 'warming_up' else 'failed' end
    else 'healthy'
  end;

  -- Source state is observed, not asserted. Disabled policies are reported as
  -- disabled and do not create a false failure for an intentionally disabled
  -- integration. A source's expected interval is used only to form an age band.
  select
    count(*)::bigint,
    count(*) filter (where enabled)::bigint,
    count(*) filter (where not enabled)::bigint,
    count(*) filter (where enabled and last_success_at is not null
      and last_success_at <= observed_at
      and last_success_at >= observed_at
        - make_interval(secs => greatest(expected_interval_seconds * 2, 300)))::bigint,
    count(*) filter (where enabled and last_success_at is not null
      and last_success_at <= observed_at
      and last_success_at < observed_at
        - make_interval(secs => greatest(expected_interval_seconds * 2, 300)))::bigint,
    count(*) filter (where enabled and last_success_at is null)::bigint,
    count(*) filter (where enabled and last_success_at > observed_at)::bigint,
    count(*) filter (where enabled and p_release_started_at is not null
      and last_success_at >= p_release_started_at)::bigint
  into source_configured_count, source_enabled_count, source_disabled_count,
       source_fresh_count, source_stale_count, source_never_succeeded_count,
       source_future_count, source_advanced_count
  from ingest.source_policies;

  source_status := case
    when source_enabled_count = 0 then 'not_enabled'
    when source_stale_count > 0 or source_never_succeeded_count > 0 or source_future_count > 0 then
      case when within_grace then 'warming_up' else 'failed' end
    else 'healthy'
  end;

  -- Schedule slots are joined to jobs only for aggregate outcome evidence. No
  -- schedule, job, payload, or source identifiers are returned.
  with slot_rows as (
    select slots.slot_at, jobs.status, jobs.updated_at,
      (jobs.id is not null) as has_job
    from ingest.schedule_slots as slots
    left join ingest.jobs as jobs
      on jobs.id = slots.job_id
      and jobs.is_demo = false
    where slots.slot_at <= observed_at
      and (p_release_started_at is null or slots.slot_at >= p_release_started_at)
  )
  select
    count(*)::bigint,
    count(*) filter (where has_job)::bigint,
    count(*) filter (where not has_job)::bigint
  into schedule_slot_count, schedule_slots_with_job_count, schedule_orphan_slot_count
  from slot_rows;

  with slot_rows as (
    select slots.slot_at, jobs.status, jobs.updated_at
    from ingest.schedule_slots as slots
    left join ingest.jobs as jobs
      on jobs.id = slots.job_id
      and jobs.is_demo = false
    where slots.slot_at <= observed_at
      and (p_release_started_at is null or slots.slot_at >= p_release_started_at)
  )
  select slot_at, updated_at, case when status is null then 'missing' else status end
  into latest_slot_at, latest_job_updated_at, latest_job_status
  from slot_rows
  order by slot_at desc
  limit 1;

  latest_slot_age_seconds := case
    when latest_slot_at is null then null
    else greatest(0, floor(extract(epoch from (observed_at - latest_slot_at)))::bigint)
  end;
  latest_job_age_seconds := case
    when latest_job_updated_at is null then null
    else greatest(0, floor(extract(epoch from (observed_at - latest_job_updated_at)))::bigint)
  end;

  schedule_status := case
    when schedule_slot_count = 0 then case when within_grace then 'warming_up' else 'never' end
    when latest_job_status in ('failed', 'dead', 'cancelled') then 'failed'
    when latest_job_status = 'missing' then case when within_grace then 'warming_up' else 'stale' end
    when latest_slot_age_seconds > 129600
      or coalesce(latest_job_age_seconds, latest_slot_age_seconds) > 129600 then 'stale'
    else 'advancing'
  end;

  select
    count(*) filter (where status in ('pending', 'running', 'completed', 'failed', 'dead', 'cancelled'))::bigint,
    count(*) filter (where status = 'pending')::bigint,
    count(*) filter (where status = 'running')::bigint,
    count(*) filter (where status = 'completed')::bigint,
    count(*) filter (where status = 'failed')::bigint,
    count(*) filter (where status = 'dead')::bigint,
    count(*) filter (where status = 'cancelled')::bigint,
    count(*) filter (where created_at > observed_at)::bigint,
    count(*) filter (where status = 'pending'
      and created_at <= observed_at
      and observed_at - created_at < make_interval(mins => 5))::bigint,
    count(*) filter (where status = 'pending'
      and observed_at - created_at >= make_interval(mins => 5)
      and observed_at - created_at < make_interval(hours => 1))::bigint,
    count(*) filter (where status = 'pending'
      and observed_at - created_at >= make_interval(hours => 1)
      and observed_at - created_at < make_interval(hours => 6))::bigint,
    count(*) filter (where status = 'pending'
      and observed_at - created_at >= make_interval(hours => 6))::bigint
  into queue_live_job_count, queue_pending_count, queue_running_count,
       queue_completed_count, queue_failed_count, queue_dead_count,
       queue_cancelled_count, queue_future_created_count,
       queue_pending_under_5m, queue_pending_5m_to_1h,
       queue_pending_1h_to_6h, queue_pending_over_6h
  from ingest.jobs
  where is_demo = false;

  queue_status := case
    when queue_dead_count > 0 or queue_pending_over_6h > 0 then 'failed'
    when queue_pending_count > 0 or queue_running_count > 0 then 'backlog'
    else 'healthy'
  end;

  -- The optional checkpoint tables intentionally contribute only a timestamp
  -- and a presence bit. Cursor/status/relay/instance values remain private.
  with checkpoints as (
    select policies.enabled, policies.expected_interval_seconds,
      states.last_checked_at as freshness_at,
      (states.last_checked_at is not null) as has_value
    from ingest.source_policies as policies
    left join catalog.sync_state as states
      on states.source = 'tcgdex'
      and states.scope = 'sets'
      and states.language = 'en'
      and states.is_demo = false
    where policies.source_key = 'tcgdex_catalog'
      and policies.is_demo = false
    union all
    select policies.enabled, policies.expected_interval_seconds,
      checkpoints.last_collected_at,
      (checkpoints.last_collected_at is not null)
    from ingest.source_policies as policies
    left join ingest.bluesky_jetstream_checkpoints as checkpoints
      on checkpoints.source_policy_id = policies.id
      and checkpoints.is_demo = false
    where policies.source_key = 'bluesky_jetstream'
      and policies.is_demo = false
    union all
    select policies.enabled, policies.expected_interval_seconds,
      case when checkpoints.last_checkpoint is null then null else checkpoints.updated_at end,
      (checkpoints.last_checkpoint is not null)
    from ingest.source_policies as policies
    left join ingest.nostr_relay_checkpoints as checkpoints
      on checkpoints.source_policy_id = policies.id
      and checkpoints.is_demo = false
    where policies.source_key = 'nostr_relay'
      and policies.is_demo = false
    union all
    select policies.enabled, policies.expected_interval_seconds,
      checkpoints.last_collected_at,
      (checkpoints.last_collected_at is not null)
    from ingest.source_policies as policies
    left join ingest.mastodon_public_hashtag_checkpoints as checkpoints
      on checkpoints.source_policy_id = policies.id
      and checkpoints.is_demo = false
    where policies.source_key = 'mastodon_social'
      and policies.is_demo = false
  )
  select
    count(*) filter (where enabled)::bigint,
    count(*) filter (where enabled and has_value)::bigint,
    count(*) filter (where enabled and has_value and freshness_at <= observed_at
      and freshness_at >= observed_at
        - make_interval(secs => greatest(expected_interval_seconds * 2, 300)))::bigint,
    count(*) filter (where enabled and has_value and freshness_at <= observed_at
      and freshness_at < observed_at
        - make_interval(secs => greatest(expected_interval_seconds * 2, 300)))::bigint,
    count(*) filter (where enabled and not has_value)::bigint,
    count(*) filter (where enabled and freshness_at > observed_at)::bigint
  into checkpoint_expected_count, checkpoint_observed_count,
       checkpoint_fresh_count, checkpoint_stale_count,
       checkpoint_never_collected_count, checkpoint_future_count
  from checkpoints;

  checkpoint_status := case
    when checkpoint_expected_count = 0 then 'not_enabled'
    when checkpoint_stale_count > 0 or checkpoint_never_collected_count > 0 or checkpoint_future_count > 0 then
      case when within_grace then 'warming_up' else 'failed' end
    else 'healthy'
  end;

  with cleanup_rows as (
    select slots.slot_at, jobs.status, jobs.completed_at
    from ingest.schedule_slots as slots
    left join ingest.jobs as jobs
      on jobs.id = slots.job_id
      and jobs.is_demo = false
    where slots.schedule_name = 'cleanup'
      and slots.slot_at <= observed_at
      and (p_release_started_at is null or slots.slot_at >= p_release_started_at)
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
      and slots.slot_at <= observed_at
      and (p_release_started_at is null or slots.slot_at >= p_release_started_at)
  )
  select case when status is null then 'missing' else status end, completed_at
  into cleanup_latest_status, cleanup_latest_completed_at
  from cleanup_rows
  order by slot_at desc
  limit 1;

  cleanup_latest_age_seconds := case
    when cleanup_latest_completed_at is null then null
    else greatest(0, floor(extract(epoch from (observed_at - cleanup_latest_completed_at)))::bigint)
  end;

  cleanup_status := case
    when cleanup_slot_count = 0 then case when within_grace then 'warming_up' else 'never' end
    when cleanup_latest_status in ('failed', 'dead', 'cancelled') then 'failed'
    when cleanup_latest_status <> 'completed' or cleanup_latest_completed_at is null then
      case when within_grace then 'warming_up' else 'stale' end
    when cleanup_latest_age_seconds > 129600 then 'stale'
    else 'healthy'
  end;

  overall_status := case
    when queue_status = 'failed'
      or schedule_status = 'failed'
      or cleanup_status = 'failed' then 'failed'
    when worker_status = 'healthy'
      and schedule_status = 'advancing'
      and queue_status in ('healthy', 'backlog')
      and cleanup_status = 'healthy'
      and source_status in ('healthy', 'not_enabled')
      and checkpoint_status in ('healthy', 'not_enabled') then 'healthy'
    when within_grace then 'warming_up'
    else 'failed'
  end;

  return jsonb_build_object(
    'schema_version', '1.0.0',
    'status', overall_status,
    'release_age_seconds', release_age_seconds,
    'grace_seconds', p_grace_seconds,
    'workers', jsonb_build_object(
      'expected_count', worker_expected_count,
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
      'latest_job_status', coalesce(latest_job_status, 'none'),
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

alter function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer) owner to postgres;
revoke all on function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer)
  from public, anon, authenticated, service_role;
grant execute on function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer)
  to pokecrack_runtime_monitor;

comment on function ingest.get_runtime_release_evidence_v1(timestamptz, integer, integer)
  is 'Private aggregate-only release verifier; never returns identifiers, payloads, URLs, cursors, or source text.';

commit;
