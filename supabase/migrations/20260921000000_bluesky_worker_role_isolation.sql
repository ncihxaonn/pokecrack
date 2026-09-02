begin;

-- Bluesky has an independently schedulable network lane.  The capability
-- role is NOLOGIN/NOINHERIT; the account-owner provisions a separate login
-- and password after this migration and selects this role through the fixed
-- libpq startup option documented by the deployment artifacts.
do $roles$
declare
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

revoke all privileges on schema ingest from pokecrack_bluesky_worker;
revoke all privileges on all tables in schema ingest from pokecrack_bluesky_worker;
revoke all privileges on all sequences in schema ingest from pokecrack_bluesky_worker;
revoke all privileges on all functions in schema ingest from pokecrack_bluesky_worker;
revoke all privileges on table
  ingest.bluesky_jetstream_candidates,
  ingest.bluesky_jetstream_observations,
  ingest.bluesky_jetstream_checkpoints,
  ingest.jobs,
  ingest.source_request_gates,
  ingest.source_policies,
  ingest.worker_heartbeats
from pokecrack_bluesky_worker;
grant usage on schema ingest to pokecrack_bluesky_worker;

-- The isolated collector owns the one current-minute Bluesky schedule.  The
-- generic scheduler is intentionally not involved in this lane.
create or replace function ingest.enqueue_due_bluesky_jetstream_jobs_v1(
  p_worker_id text
)
returns integer
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $function$
declare
  scheduled_for timestamptz := date_trunc('minute', clock_timestamp(), 'UTC');
  scheduled_count integer;
begin
  if p_worker_id is null
    or p_worker_id !~ '^bluesky-collector-[a-z0-9][a-z0-9_.-]{0,63}$'
  then
    raise exception using
      errcode = '22023',
      message = 'worker_id must use the dedicated Bluesky collector prefix';
  end if;

  select count(*)::integer
  into scheduled_count
  from ingest.enqueue_scheduled_job_v1(
    'bluesky_jetstream',
    scheduled_for,
    'source.bluesky.jetstream',
    '{}'::jsonb,
    -50,
    3
  );
  if scheduled_count <> 1 then
    raise exception using
      errcode = '55000',
      message = 'dedicated Bluesky scheduling did not return one exact job';
  end if;
  return scheduled_count;
end;
$function$;

-- Runtime readiness is a boolean-only proof over the reviewed, live policy,
-- request gate, and durable cursor.  The worker does not receive a policy id,
-- endpoint, cursor, or activity row through this check.
create or replace function ingest.bluesky_worker_runtime_ready_v1()
returns boolean
language sql
stable
security definer
set search_path = pg_catalog
as $function$
with expected_policy as (
  select
    'bluesky_jetstream'::text as source_key,
    'Bluesky Jetstream discovery'::text as display_name,
    'official_api'::text as source_kind,
    'jetstream.us-west.bsky.network'::text as domain,
    'wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents'::text as base_url,
    'bluesky_jetstream'::text as collector_type,
    jsonb_build_object(
      'endpoint', 'wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents',
      'collection', 'app.bsky.feed.post',
      'operations', jsonb_build_array('create', 'update', 'delete'),
      'kinds', jsonb_build_array('commit'),
      'subprotocol', 'xrpc.v1.json',
      'stream_window_seconds', 10,
      'max_events', 10000,
      'max_message_bytes', 262144,
      'max_stream_bytes', 2097152,
      'max_candidates', 100,
      'max_deletions', 100,
      'max_excerpt_chars', 500,
      'keyword_registry', 'bluesky-keywords-v1',
      'statistics_eligible', false
    ) as config
),
policy_contract as (
  select
    policies.id,
    policies.source_key = expected.source_key
      and policies.display_name = expected.display_name
      and policies.source_kind = expected.source_kind
      and policies.domain = expected.domain
      and policies.base_url = expected.base_url
      and policies.enabled
      and policies.collector_type = expected.collector_type
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
      and policies.config = expected.config
      and policies.version = 'bluesky-jetstream-v1'
      and policies.expected_interval_seconds = 60
      and not policies.is_demo as valid
  from expected_policy as expected
  left join ingest.source_policies as policies
    on policies.source_key = expected.source_key
),
checkpoint_contract as (
  select
    policy.id is not null
      and checkpoints.source_policy_id = policy.id
      and checkpoints.endpoint = policy.base_url
      and checkpoints.protocol = 'xrpc.v1.json'
      and checkpoints.collection = 'app.bsky.feed.post'
      and (
        checkpoints.last_cursor is null
        or checkpoints.last_cursor >= 0
      )
      and checkpoints.events_seen_total >= 0
      and checkpoints.bytes_seen_total >= 0
      and checkpoints.candidates_seen_total >= 0
      and checkpoints.deletions_seen_total >= 0
      and not checkpoints.is_demo as valid
  from policy_contract as policy
  left join ingest.bluesky_jetstream_checkpoints as checkpoints
    on checkpoints.source_policy_id = policy.id
),
gate_contract as (
  select count(*) = 1 as valid
  from ingest.source_request_gates as gates
  where gates.source_key = 'bluesky_jetstream'
)
select coalesce(
  (select count(*) = 1 and bool_and(valid) from policy_contract)
  and (select count(*) = 1 and bool_and(valid) from checkpoint_contract)
  and (select valid from gate_contract),
  false
);
$function$;

-- This projection is intentionally limited to the same non-secret policy
-- fields used by the worker's local contract comparison.  It never exposes
-- ids, timestamps, cursor values, gate ownership, or activity data.
create or replace function ingest.get_bluesky_worker_policy_snapshot_v1()
returns table(
  source_key text,
  display_name text,
  source_kind text,
  domain text,
  base_url text,
  enabled boolean,
  collector_type text,
  access_mode text,
  robots_policy text,
  routes text[],
  include_subdomains boolean,
  min_delay_seconds numeric,
  max_pages_per_run integer,
  max_items_per_run integer,
  max_concurrency integer,
  browser_profile text,
  statistics_eligible_default boolean,
  retention_days integer,
  config jsonb,
  version text,
  expected_interval_seconds integer,
  is_demo boolean
)
language sql
stable
security definer
set search_path = pg_catalog
as $function$
select
  policies.source_key,
  policies.display_name,
  policies.source_kind,
  policies.domain,
  policies.base_url,
  policies.enabled,
  policies.collector_type,
  policies.access_mode,
  policies.robots_policy,
  policies.routes,
  policies.include_subdomains,
  policies.min_delay_seconds,
  policies.max_pages_per_run,
  policies.max_items_per_run,
  policies.max_concurrency,
  policies.browser_profile,
  policies.statistics_eligible_default,
  policies.retention_days,
  jsonb_build_object(
    'endpoint', policies.config -> 'endpoint',
    'collection', policies.config -> 'collection',
    'operations', policies.config -> 'operations',
    'kinds', policies.config -> 'kinds',
    'subprotocol', policies.config -> 'subprotocol',
    'stream_window_seconds', policies.config -> 'stream_window_seconds',
    'max_events', policies.config -> 'max_events',
    'max_message_bytes', policies.config -> 'max_message_bytes',
    'max_stream_bytes', policies.config -> 'max_stream_bytes',
    'max_candidates', policies.config -> 'max_candidates',
    'max_deletions', policies.config -> 'max_deletions',
    'max_excerpt_chars', policies.config -> 'max_excerpt_chars',
    'keyword_registry', policies.config -> 'keyword_registry',
    'statistics_eligible', policies.config -> 'statistics_eligible'
  ) as config,
  policies.version,
  policies.expected_interval_seconds,
  policies.is_demo
from ingest.source_policies as policies
where policies.source_key = 'bluesky_jetstream';
$function$;

create or replace function ingest.claim_bluesky_jetstream_jobs_v1(
  p_worker_id text,
  p_lease_seconds integer
)
returns setof ingest.jobs
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $function$
declare
  sweep_time timestamptz := clock_timestamp();
  claim_time timestamptz;
begin
  if p_worker_id is null
    or p_worker_id !~ '^bluesky-collector-[a-z0-9][a-z0-9_.-]{0,63}$'
  then
    raise exception using
      errcode = '22023',
      message = 'worker_id must use the dedicated Bluesky collector prefix';
  end if;
  if p_lease_seconds is null or p_lease_seconds < 60 or p_lease_seconds > 86400 then
    raise exception using
      errcode = '22023',
      message = 'lease_seconds must be between 60 and 86400';
  end if;

  update ingest.jobs as exhausted
  set status = 'dead',
      lease_generation = case
        when exhausted.status = 'running' then exhausted.lease_generation + 1
        else exhausted.lease_generation
      end,
      locked_by = null,
      locked_at = null,
      lock_expires_at = null,
      last_error_code = case
        when exhausted.status = 'running' then 'lease_expired_max_attempts'
        else 'max_attempts_exhausted'
      end,
      last_error_message = case
        when exhausted.status = 'running' then 'expired lease exhausted the maximum attempts'
        else 'job reached the maximum attempts before claim'
      end,
      completed_at = sweep_time,
      updated_at = sweep_time
  where exhausted.job_type = 'source.bluesky.jetstream'
    and exhausted.attempts >= exhausted.max_attempts
    and not exhausted.is_demo
    and (
      (exhausted.status = 'pending' and exhausted.available_at <= sweep_time)
      or (exhausted.status = 'running' and exhausted.lock_expires_at <= sweep_time)
    );

  claim_time := clock_timestamp();
  return query
  with claimable as materialized (
    select jobs.id
    from ingest.jobs as jobs
    where jobs.job_type = 'source.bluesky.jetstream'
      and jobs.attempts < jobs.max_attempts
      and not jobs.is_demo
      and jobs.payload = '{}'::jsonb
      and (
        (jobs.status = 'pending' and jobs.available_at <= claim_time)
        or (jobs.status = 'running' and jobs.lock_expires_at <= claim_time)
      )
    order by jobs.priority desc, jobs.available_at, jobs.created_at, jobs.id
    for update of jobs skip locked
    limit 1
  )
  update ingest.jobs as jobs
  set status = 'running',
      lease_generation = jobs.lease_generation + 1,
      locked_at = claim_time,
      lock_expires_at = claim_time + make_interval(secs => p_lease_seconds),
      locked_by = p_worker_id,
      attempts = jobs.attempts + 1,
      last_error_code = null,
      last_error_message = null,
      updated_at = claim_time,
      completed_at = null
  from claimable
  where jobs.id = claimable.id
  returning jobs.*;
end;
$function$;

create or replace function ingest.heartbeat_bluesky_jetstream_job_v1(
  p_job_id uuid,
  p_worker_id text,
  p_lease_generation bigint,
  p_lease_seconds integer
)
returns setof ingest.jobs
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $function$
declare
  leased_job ingest.jobs%rowtype;
  renewed_job ingest.jobs%rowtype;
  lease_checked_at timestamptz;
begin
  if p_job_id is null then
    raise exception using errcode = '22023', message = 'job_id must not be null';
  end if;
  if p_worker_id is null
    or p_worker_id !~ '^bluesky-collector-[a-z0-9][a-z0-9_.-]{0,63}$'
  then
    raise exception using
      errcode = '22023',
      message = 'worker_id must use the dedicated Bluesky collector prefix';
  end if;
  if p_lease_generation is null or p_lease_generation < 1 then
    raise exception using
      errcode = '22023',
      message = 'lease_generation must be positive';
  end if;
  if p_lease_seconds is null or p_lease_seconds < 60 or p_lease_seconds > 86400 then
    raise exception using
      errcode = '22023',
      message = 'lease_seconds must be between 60 and 86400';
  end if;

  select jobs.*
  into leased_job
  from ingest.jobs as jobs
  where jobs.id = p_job_id
  for update of jobs;

  if not found then
    return;
  end if;

  lease_checked_at := clock_timestamp();
  if leased_job.is_demo
    or leased_job.job_type <> 'source.bluesky.jetstream'
    or leased_job.payload <> '{}'::jsonb
    or leased_job.status <> 'running'
    or leased_job.locked_by is distinct from p_worker_id
    or leased_job.lease_generation <> p_lease_generation
    or leased_job.lock_expires_at is null
    or leased_job.lock_expires_at <= lease_checked_at
  then
    return;
  end if;

  update ingest.jobs as jobs
  set lock_expires_at = lease_checked_at + make_interval(secs => p_lease_seconds),
      updated_at = lease_checked_at
  where jobs.id = p_job_id
    and jobs.job_type = 'source.bluesky.jetstream'
    and jobs.status = 'running'
    and jobs.locked_by = p_worker_id
    and jobs.lease_generation = p_lease_generation
    and jobs.lock_expires_at > lease_checked_at
    and not jobs.is_demo
  returning jobs.* into renewed_job;

  if not found then
    return;
  end if;

  update ingest.source_request_gates as gates
  set active_until = renewed_job.lock_expires_at
  where gates.source_key = 'bluesky_jetstream'
    and gates.owner_job_id = p_job_id
    and gates.owner_lease_generation = p_lease_generation;

  return next renewed_job;
end;
$function$;

create or replace function ingest.fail_bluesky_jetstream_job_v1(
  p_job_id uuid,
  p_worker_id text,
  p_lease_generation bigint,
  p_error_code text,
  p_error_message text,
  p_retryable boolean
)
returns setof ingest.jobs
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $function$
declare
  leased_job ingest.jobs%rowtype;
  failed_job ingest.jobs%rowtype;
  lease_checked_at timestamptz;
  failure_time timestamptz;
begin
  if p_job_id is null then
    raise exception using errcode = '22023', message = 'job_id must not be null';
  end if;
  if p_worker_id is null
    or p_worker_id !~ '^bluesky-collector-[a-z0-9][a-z0-9_.-]{0,63}$'
  then
    raise exception using
      errcode = '22023',
      message = 'worker_id must use the dedicated Bluesky collector prefix';
  end if;
  if p_lease_generation is null or p_lease_generation < 1 then
    raise exception using
      errcode = '22023',
      message = 'lease_generation must be positive';
  end if;
  if p_error_code is null or btrim(p_error_code) = '' or char_length(p_error_code) > 160 then
    raise exception using
      errcode = '22023',
      message = 'error_code must contain 1 to 160 characters';
  end if;
  if p_error_message is null or char_length(p_error_message) > 8000 then
    raise exception using
      errcode = '22023',
      message = 'error_message must contain at most 8000 characters';
  end if;
  if p_retryable is null then
    raise exception using errcode = '22023', message = 'retryable must not be null';
  end if;

  select jobs.*
  into leased_job
  from ingest.jobs as jobs
  where jobs.id = p_job_id
  for update of jobs;

  if not found then
    return;
  end if;

  lease_checked_at := clock_timestamp();
  if leased_job.is_demo
    or leased_job.job_type <> 'source.bluesky.jetstream'
    or leased_job.payload <> '{}'::jsonb
    or leased_job.status <> 'running'
    or leased_job.locked_by is distinct from p_worker_id
    or leased_job.lease_generation <> p_lease_generation
    or leased_job.lock_expires_at is null
    or leased_job.lock_expires_at <= lease_checked_at
  then
    return;
  end if;

  update ingest.jobs as jobs
  set status = case
        when not p_retryable or jobs.attempts >= jobs.max_attempts then 'dead'
        else 'pending'
      end,
      available_at = case
        when not p_retryable or jobs.attempts >= jobs.max_attempts then jobs.available_at
        else lease_checked_at + make_interval(
          secs => least(
            3600,
            30 * power(2, least(10, greatest(0, jobs.attempts - 1)))
          )::integer
        )
      end,
      locked_by = null,
      locked_at = null,
      lock_expires_at = null,
      completed_at = case
        when not p_retryable or jobs.attempts >= jobs.max_attempts then lease_checked_at
        else null
      end,
      last_error_code = p_error_code,
      last_error_message = p_error_message,
      updated_at = lease_checked_at
  where jobs.id = p_job_id
    and jobs.job_type = 'source.bluesky.jetstream'
    and jobs.status = 'running'
    and jobs.locked_by = p_worker_id
    and jobs.lease_generation = p_lease_generation
    and jobs.lock_expires_at > lease_checked_at
    and not jobs.is_demo
  returning jobs.* into failed_job;

  if not found then
    return;
  end if;

  failure_time := clock_timestamp();
  update ingest.source_policies as policies
  set last_attempt_at = greatest(
        coalesce(policies.last_attempt_at, '-infinity'::timestamptz),
        failure_time
      ),
      last_failure_at = failure_time,
      updated_at = failure_time
  from ingest.source_request_gates as gates
  where gates.source_key = 'bluesky_jetstream'
    and gates.owner_job_id = p_job_id
    and gates.owner_lease_generation = p_lease_generation
    and policies.source_key = gates.source_key
    and not policies.is_demo;

  update ingest.source_request_gates as gates
  set owner_job_id = null,
      owner_lease_generation = null,
      acquired_at = null,
      active_until = null
  where gates.source_key = 'bluesky_jetstream'
    and gates.owner_job_id = p_job_id
    and gates.owner_lease_generation = p_lease_generation;

  return next failed_job;
end;
$function$;

create or replace function ingest.pause_bluesky_jetstream_job_v1(
  p_job_id uuid,
  p_worker_id text,
  p_lease_generation bigint,
  p_retry_at timestamptz
)
returns setof ingest.jobs
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $function$
declare
  pause_time timestamptz;
  paused_job ingest.jobs%rowtype;
begin
  if p_job_id is null then
    raise exception using errcode = '22023', message = 'job_id must not be null';
  end if;
  if p_worker_id is null
    or p_worker_id !~ '^bluesky-collector-[a-z0-9][a-z0-9_.-]{0,63}$'
  then
    raise exception using
      errcode = '22023',
      message = 'worker_id must use the dedicated Bluesky collector prefix';
  end if;
  if p_lease_generation is null or p_lease_generation < 1 then
    raise exception using
      errcode = '22023',
      message = 'lease_generation must be positive';
  end if;
  pause_time := clock_timestamp();
  if p_retry_at is null
    or p_retry_at <= pause_time
    or p_retry_at > pause_time + interval '31 days'
  then
    raise exception using
      errcode = '22023',
      message = 'retry_at must be within the next 31 days';
  end if;

  update ingest.jobs as jobs
  set status = 'pending',
      attempts = greatest(0, jobs.attempts - 1),
      available_at = p_retry_at,
      locked_by = null,
      locked_at = null,
      lock_expires_at = null,
      completed_at = null,
      last_error_code = null,
      last_error_message = null,
      updated_at = pause_time
  where jobs.id = p_job_id
    and jobs.job_type = 'source.bluesky.jetstream'
    and jobs.status = 'running'
    and jobs.locked_by = p_worker_id
    and jobs.lease_generation = p_lease_generation
    and jobs.lock_expires_at > pause_time
    and not jobs.is_demo
  returning jobs.* into paused_job;

  if not found then
    return;
  end if;

  update ingest.source_request_gates as gates
  set owner_job_id = null,
      owner_lease_generation = null,
      acquired_at = null,
      active_until = null
  where gates.source_key = 'bluesky_jetstream'
    and gates.owner_job_id = p_job_id
    and gates.owner_lease_generation = p_lease_generation;

  return next paused_job;
end;
$function$;

-- Health writes are fixed to the dedicated worker type and carry no secret or
-- activity data. The only accepted metadata is the exact live health shape.
create or replace function ingest.upsert_bluesky_worker_heartbeat_v1(
  p_worker_id text,
  p_version text,
  p_metadata jsonb
)
returns table(last_seen_at timestamptz)
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $function$
declare
  heartbeat_time timestamptz := clock_timestamp();
begin
  if p_worker_id is null
    or p_worker_id !~ '^bluesky-collector-[a-z0-9][a-z0-9_.-]{0,63}$'
  then
    raise exception using
      errcode = '22023',
      message = 'worker_id must use the dedicated Bluesky collector prefix';
  end if;
  if p_version is null or btrim(p_version) = '' or char_length(p_version) > 80 then
    raise exception using
      errcode = '22023',
      message = 'version must contain 1 to 80 characters';
  end if;
  if p_metadata is null
    or jsonb_typeof(p_metadata) is distinct from 'object'
    or p_metadata - array['command', 'data_mode', 'max_concurrency', 'role_ready'] <> '{}'::jsonb
    or not (p_metadata ?& array['command', 'data_mode', 'max_concurrency', 'role_ready'])
    or p_metadata ->> 'command' <> 'health'
    or p_metadata ->> 'data_mode' <> 'live'
    or p_metadata -> 'max_concurrency' is distinct from '1'::jsonb
    or p_metadata -> 'role_ready' is distinct from 'true'::jsonb
    or octet_length(p_metadata::text) > 1024
  then
    raise exception using
      errcode = '22023',
      message = 'metadata must match the exact live Bluesky health contract';
  end if;

  return query
  insert into ingest.worker_heartbeats as heartbeats (
    worker_id,
    worker_type,
    version,
    last_seen_at,
    metadata,
    is_demo
  ) values (
    p_worker_id,
    'bluesky-collector',
    p_version,
    heartbeat_time,
    p_metadata,
    false
  )
  on conflict (worker_id)
  do update set
    worker_type = excluded.worker_type,
    version = excluded.version,
    last_seen_at = excluded.last_seen_at,
    metadata = heartbeats.metadata || excluded.metadata
  where not heartbeats.is_demo
  returning heartbeats.last_seen_at;
end;
$function$;

-- Typed persistence retains the existing cursor/gate/fencing implementation.
-- These forwarding wrappers add the fixed identity check while keeping the
-- capability role's direct typed-function surface closed.
create or replace function ingest.begin_bluesky_jetstream_job_v1(
  p_job_id uuid,
  p_worker_id text,
  p_lease_generation bigint
)
returns table(acquired boolean, retry_at timestamptz, start_cursor bigint)
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $function$
begin
  if p_worker_id is null
    or p_worker_id !~ '^bluesky-collector-[a-z0-9][a-z0-9_.-]{0,63}$'
  then
    raise exception using errcode = '22023', message =
      'worker_id must use the dedicated Bluesky collector prefix';
  end if;
  return query select * from ingest.begin_bluesky_jetstream_job(
    p_job_id, p_worker_id, p_lease_generation
  );
end;
$function$;

create or replace function ingest.finalize_bluesky_jetstream_job_v1(
  p_job_id uuid,
  p_worker_id text,
  p_lease_generation bigint,
  p_result jsonb
)
returns setof ingest.jobs
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $function$
begin
  if p_worker_id is null
    or p_worker_id !~ '^bluesky-collector-[a-z0-9][a-z0-9_.-]{0,63}$'
  then
    raise exception using errcode = '22023', message =
      'worker_id must use the dedicated Bluesky collector prefix';
  end if;
  return query select * from ingest.finalize_bluesky_jetstream_job(
    p_job_id, p_worker_id, p_lease_generation, p_result
  );
end;
$function$;

create or replace function ingest.recover_bluesky_cursor_too_old_job_v2(
  p_job_id uuid,
  p_worker_id text,
  p_lease_generation bigint,
  p_expected_start_cursor bigint
)
returns setof ingest.jobs
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $function$
begin
  if p_worker_id is null
    or p_worker_id !~ '^bluesky-collector-[a-z0-9][a-z0-9_.-]{0,63}$'
  then
    raise exception using errcode = '22023', message =
      'worker_id must use the dedicated Bluesky collector prefix';
  end if;
  return query select * from ingest.recover_bluesky_cursor_too_old_job_v1(
    p_job_id, p_worker_id, p_lease_generation, p_expected_start_cursor
  );
end;
$function$;

alter function ingest.begin_bluesky_jetstream_job_v1(uuid, text, bigint)
  owner to postgres;
alter function ingest.finalize_bluesky_jetstream_job_v1(uuid, text, bigint, jsonb)
  owner to postgres;
alter function ingest.recover_bluesky_cursor_too_old_job_v2(uuid, text, bigint, bigint)
  owner to postgres;
revoke all on function ingest.begin_bluesky_jetstream_job_v1(uuid, text, bigint)
  from public, anon, authenticated, service_role, pokecrack_bluesky_worker;
revoke all on function ingest.finalize_bluesky_jetstream_job_v1(uuid, text, bigint, jsonb)
  from public, anon, authenticated, service_role, pokecrack_bluesky_worker;
revoke all on function ingest.recover_bluesky_cursor_too_old_job_v2(uuid, text, bigint, bigint)
  from public, anon, authenticated, service_role, pokecrack_bluesky_worker;
grant execute on function ingest.begin_bluesky_jetstream_job_v1(uuid, text, bigint)
  to pokecrack_bluesky_worker;
grant execute on function ingest.finalize_bluesky_jetstream_job_v1(uuid, text, bigint, jsonb)
  to pokecrack_bluesky_worker;
grant execute on function ingest.recover_bluesky_cursor_too_old_job_v2(uuid, text, bigint, bigint)
  to pokecrack_bluesky_worker;

alter function ingest.enqueue_due_bluesky_jetstream_jobs_v1(text)
  owner to postgres;
alter function ingest.claim_bluesky_jetstream_jobs_v1(text, integer)
  owner to postgres;
alter function ingest.heartbeat_bluesky_jetstream_job_v1(uuid, text, bigint, integer)
  owner to postgres;
alter function ingest.fail_bluesky_jetstream_job_v1(uuid, text, bigint, text, text, boolean)
  owner to postgres;
alter function ingest.pause_bluesky_jetstream_job_v1(uuid, text, bigint, timestamptz)
  owner to postgres;
alter function ingest.upsert_bluesky_worker_heartbeat_v1(text, text, jsonb)
  owner to postgres;
alter function ingest.bluesky_worker_runtime_ready_v1()
  owner to postgres;
alter function ingest.get_bluesky_worker_policy_snapshot_v1()
  owner to postgres;
revoke all on function ingest.enqueue_due_bluesky_jetstream_jobs_v1(text)
  from public, anon, authenticated, service_role, pokecrack_bluesky_worker;
revoke all on function ingest.claim_bluesky_jetstream_jobs_v1(text, integer)
  from public, anon, authenticated, service_role, pokecrack_bluesky_worker;
revoke all on function ingest.heartbeat_bluesky_jetstream_job_v1(uuid, text, bigint, integer)
  from public, anon, authenticated, service_role, pokecrack_bluesky_worker;
revoke all on function ingest.fail_bluesky_jetstream_job_v1(uuid, text, bigint, text, text, boolean)
  from public, anon, authenticated, service_role, pokecrack_bluesky_worker;
revoke all on function ingest.pause_bluesky_jetstream_job_v1(uuid, text, bigint, timestamptz)
  from public, anon, authenticated, service_role, pokecrack_bluesky_worker;
revoke all on function ingest.upsert_bluesky_worker_heartbeat_v1(text, text, jsonb)
  from public, anon, authenticated, service_role, pokecrack_bluesky_worker;
revoke all on function ingest.bluesky_worker_runtime_ready_v1()
  from public, anon, authenticated, service_role, pokecrack_bluesky_worker;
revoke all on function ingest.get_bluesky_worker_policy_snapshot_v1()
  from public, anon, authenticated, service_role, pokecrack_bluesky_worker;
grant execute on function ingest.enqueue_due_bluesky_jetstream_jobs_v1(text)
  to pokecrack_bluesky_worker;
grant execute on function ingest.claim_bluesky_jetstream_jobs_v1(text, integer)
  to pokecrack_bluesky_worker;
grant execute on function ingest.heartbeat_bluesky_jetstream_job_v1(uuid, text, bigint, integer)
  to pokecrack_bluesky_worker;
grant execute on function ingest.fail_bluesky_jetstream_job_v1(uuid, text, bigint, text, text, boolean)
  to pokecrack_bluesky_worker;
grant execute on function ingest.pause_bluesky_jetstream_job_v1(uuid, text, bigint, timestamptz)
  to pokecrack_bluesky_worker;
grant execute on function ingest.upsert_bluesky_worker_heartbeat_v1(text, text, jsonb)
  to pokecrack_bluesky_worker;
grant execute on function ingest.bluesky_worker_runtime_ready_v1()
  to pokecrack_bluesky_worker;
grant execute on function ingest.get_bluesky_worker_policy_snapshot_v1()
  to pokecrack_bluesky_worker;

-- The forwarding wrappers are the only typed entry points for the isolated
-- role. The historical function names remain owner/service-role compatible
-- for legacy callers until their separately approved credential transition.
revoke all on function ingest.begin_bluesky_jetstream_job(uuid, text, bigint)
  from pokecrack_bluesky_worker;
revoke all on function ingest.finalize_bluesky_jetstream_job(uuid, text, bigint, jsonb)
  from pokecrack_bluesky_worker;
revoke all on function ingest.recover_bluesky_cursor_too_old_job_v1(uuid, text, bigint, bigint)
  from pokecrack_bluesky_worker;

commit;
