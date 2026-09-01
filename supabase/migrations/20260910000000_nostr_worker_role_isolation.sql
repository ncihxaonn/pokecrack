begin;

-- Nostr has a separate NOLOGIN capability role.  The external NOINHERIT
-- login and its random password are provisioned by an account-owner operation
-- after this migration; no password or login credential is stored in SQL.
do $roles$
declare
  role_is_exact boolean;
begin
  if not exists (
    select 1 from pg_catalog.pg_roles
    where rolname = 'pokecrack_nostr_worker'
  ) then
    create role pokecrack_nostr_worker
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
    where rolname = 'pokecrack_nostr_worker';
    if role_is_exact is distinct from true then
      raise exception using
        errcode = '55000',
        message = 'existing pokecrack_nostr_worker role is not the reviewed NOLOGIN contract';
    end if;
  end if;
end;
$roles$;

revoke all privileges on schema ingest from pokecrack_nostr_worker;
revoke all privileges on all tables in schema ingest from pokecrack_nostr_worker;
revoke all privileges on all sequences in schema ingest from pokecrack_nostr_worker;
revoke all privileges on all functions in schema ingest from pokecrack_nostr_worker;
grant usage on schema ingest to pokecrack_nostr_worker;

-- The isolated collector owns its own minute schedule.  The generic scheduler
-- never receives Nostr enablement or the dedicated database capability.
create or replace function ingest.enqueue_due_nostr_relay_jobs_v1(
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
  relay_key text;
  relay_count integer;
  scheduled_count integer := 0;
begin
  if p_worker_id is null
    or p_worker_id !~ '^nostr-collector-[a-z0-9][a-z0-9_.-]{0,63}$'
  then
    raise exception using
      errcode = '22023',
      message = 'worker_id must use the dedicated Nostr collector prefix';
  end if;

  foreach relay_key in array array['primal', 'nos_lol', 'nostr_net']::text[] loop
    select count(*)::integer
    into relay_count
    from ingest.enqueue_scheduled_job_v1(
      'nostr_' || relay_key,
      scheduled_for,
      'source.nostr.relay',
      jsonb_build_object('relay_key', relay_key),
      -49,
      3
    );
    if relay_count <> 1 then
      raise exception using
        errcode = '55000',
        message = 'dedicated Nostr scheduling did not return one exact job';
    end if;
    scheduled_count := scheduled_count + relay_count;
  end loop;

  if scheduled_count <> 3 then
    raise exception using
      errcode = '55000',
      message = 'dedicated Nostr scheduling did not return three exact jobs';
  end if;
  return scheduled_count;
end;
$function$;

-- The claim wrapper fixes the job type and batch size.  The capability role
-- never receives EXECUTE on the generic caller-controlled claim function.
create or replace function ingest.claim_nostr_relay_jobs_v1(
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
    or p_worker_id !~ '^nostr-collector-[a-z0-9][a-z0-9_.-]{0,63}$'
  then
    raise exception using
      errcode = '22023',
      message = 'worker_id must use the dedicated Nostr collector prefix';
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
  where exhausted.job_type = 'source.nostr.relay'
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
    where jobs.job_type = 'source.nostr.relay'
      and jobs.attempts < jobs.max_attempts
      and not jobs.is_demo
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

create or replace function ingest.heartbeat_nostr_relay_job_v1(
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
    or p_worker_id !~ '^nostr-collector-[a-z0-9][a-z0-9_.-]{0,63}$'
  then
    raise exception using
      errcode = '22023',
      message = 'worker_id must use the dedicated Nostr collector prefix';
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
    or leased_job.job_type <> 'source.nostr.relay'
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
    and jobs.job_type = 'source.nostr.relay'
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
  where gates.owner_job_id = p_job_id
    and gates.owner_lease_generation = p_lease_generation;

  return next renewed_job;
end;
$function$;

create or replace function ingest.fail_nostr_relay_job_v1(
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
  cooldown_recorded_at timestamptz;
begin
  if p_job_id is null then
    raise exception using errcode = '22023', message = 'job_id must not be null';
  end if;
  if p_worker_id is null
    or p_worker_id !~ '^nostr-collector-[a-z0-9][a-z0-9_.-]{0,63}$'
  then
    raise exception using
      errcode = '22023',
      message = 'worker_id must use the dedicated Nostr collector prefix';
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
    or leased_job.job_type <> 'source.nostr.relay'
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
    and jobs.job_type = 'source.nostr.relay'
    and jobs.status = 'running'
    and jobs.locked_by = p_worker_id
    and jobs.lease_generation = p_lease_generation
    and jobs.lock_expires_at > lease_checked_at
    and not jobs.is_demo
  returning jobs.* into failed_job;

  if not found then
    return;
  end if;

  cooldown_recorded_at := clock_timestamp();
  update ingest.source_policies as policies
  set last_attempt_at = greatest(
        coalesce(policies.last_attempt_at, '-infinity'::timestamptz),
        cooldown_recorded_at
      ),
      last_failure_at = cooldown_recorded_at,
      updated_at = cooldown_recorded_at
  from ingest.source_request_gates as gates
  where gates.owner_job_id = p_job_id
    and gates.owner_lease_generation = p_lease_generation
    and policies.source_key = gates.source_key
    and policies.source_key in (
      'nostr_relay_primal', 'nostr_relay_nos_lol', 'nostr_relay_nostr_net'
    )
    and not policies.is_demo;

  update ingest.source_request_gates as gates
  set owner_job_id = null,
      owner_lease_generation = null,
      acquired_at = null,
      active_until = null
  where gates.owner_job_id = p_job_id
    and gates.owner_lease_generation = p_lease_generation
    and gates.source_key in (
      'nostr_relay_primal', 'nostr_relay_nos_lol', 'nostr_relay_nostr_net'
    );

  return next failed_job;
end;
$function$;

create or replace function ingest.pause_nostr_relay_job_v1(
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
    or p_worker_id !~ '^nostr-collector-[a-z0-9][a-z0-9_.-]{0,63}$'
  then
    raise exception using
      errcode = '22023',
      message = 'worker_id must use the dedicated Nostr collector prefix';
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
    and jobs.job_type = 'source.nostr.relay'
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
  where gates.owner_job_id = p_job_id
    and gates.owner_lease_generation = p_lease_generation
    and gates.source_key in (
      'nostr_relay_primal', 'nostr_relay_nos_lol', 'nostr_relay_nostr_net'
    );

  return next paused_job;
end;
$function$;

-- Health is also fixed to the dedicated worker type, so the capability role
-- cannot impersonate a scheduler, watchdog or the multi-source collector.
create or replace function ingest.upsert_nostr_worker_heartbeat_v1(
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
    or p_worker_id !~ '^nostr-collector-[a-z0-9][a-z0-9_.-]{0,63}$'
  then
    raise exception using
      errcode = '22023',
      message = 'worker_id must use the dedicated Nostr collector prefix';
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
      message = 'metadata must match the exact live Nostr health contract';
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
    'nostr-collector',
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

-- Re-check the immutable relay policy and checkpoint contract at runtime
-- without granting the network process any direct table capability.  The
-- result is deliberately a single boolean: no policy ids, cursors, endpoints
-- from rows, or activity data cross the capability boundary.
create or replace function ingest.nostr_worker_runtime_ready_v1()
returns boolean
language sql
stable
security definer
set search_path = pg_catalog
as $function$
with expected_relays(
  relay_key, source_key, display_name, domain, endpoint, nip11_url
) as (
  values
    ('primal', 'nostr_relay_primal',
      'Nostr relay relay.primal.net discovery', 'relay.primal.net',
      'wss://relay.primal.net/', 'https://relay.primal.net/'),
    ('nos_lol', 'nostr_relay_nos_lol',
      'Nostr relay nos.lol discovery', 'nos.lol',
      'wss://nos.lol/', 'https://nos.lol/'),
    ('nostr_net', 'nostr_relay_nostr_net',
      'Nostr relay relay.nostr.net discovery', 'relay.nostr.net',
      'wss://relay.nostr.net/', 'https://relay.nostr.net/')
),
expected_tags(ordinal, tag) as (
  values
    (1, 'pokemontcg'), (2, 'PokemonTCG'),
    (3, 'pokemoncards'), (4, 'PokemonCards'),
    (5, 'ポケカ'), (6, 'ポケモンカード'), (7, '포켓몬카드'),
    (8, '宝可梦卡牌'), (9, '寶可夢卡牌')
),
expected_contracts as (
  select
    relays.*,
    jsonb_build_object(
      'relay_key', relays.relay_key,
      'endpoint', relays.endpoint,
      'nip11_url', relays.nip11_url,
      'protocol', 'nip01',
      'policy_state', 'degraded_missing_relay_specific_terms',
      'required_nips', jsonb_build_array(1, 9, 11),
      'approved_tags', (
        select jsonb_agg(tags.tag order by tags.ordinal)
        from expected_tags as tags
      ),
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
runtime_contract as (
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
      and not policies.is_demo
      and gates.source_key = expected.source_key
      and checkpoints.source_policy_id = policies.id
      and checkpoints.relay_key = expected.relay_key
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
  from expected_contracts as expected
  left join ingest.source_policies as policies
    on policies.source_key = expected.source_key
  left join ingest.source_request_gates as gates
    on gates.source_key = expected.source_key
  left join ingest.nostr_relay_checkpoints as checkpoints
    on checkpoints.relay_key = expected.relay_key
)
select coalesce(
  (select count(*) = 3 and bool_and(valid) from runtime_contract)
  and (select count(*) = 3 from ingest.source_policies
    where source_key like 'nostr_relay_%')
  and (select count(*) = 3 from ingest.source_request_gates
    where source_key like 'nostr_relay_%')
  and (select count(*) = 3 from ingest.nostr_relay_checkpoints),
  false
);
$function$;

-- Expose only the reviewed, non-secret policy fields needed for the process
-- to compare the exact runtime contract.  This is not a table grant and does
-- not include ids, timestamps, gate ownership, cursors, or activity rows.
create or replace function ingest.get_nostr_worker_policy_snapshot_v1()
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
    'relay_key', policies.config -> 'relay_key',
    'endpoint', policies.config -> 'endpoint',
    'nip11_url', policies.config -> 'nip11_url',
    'protocol', policies.config -> 'protocol',
    'policy_state', policies.config -> 'policy_state',
    'required_nips', policies.config -> 'required_nips',
    'approved_tags', policies.config -> 'approved_tags',
    'replay_overlap_seconds', policies.config -> 'replay_overlap_seconds',
    'stream_window_seconds', policies.config -> 'stream_window_seconds',
    'max_events', policies.config -> 'max_events',
    'max_message_bytes', policies.config -> 'max_message_bytes',
    'max_stream_bytes', policies.config -> 'max_stream_bytes',
    'max_candidates', policies.config -> 'max_candidates',
    'max_deletions', policies.config -> 'max_deletions',
    'max_delete_targets', policies.config -> 'max_delete_targets',
    'statistics_eligible', policies.config -> 'statistics_eligible'
  ) as config,
  policies.version,
  policies.expected_interval_seconds,
  policies.is_demo
from ingest.source_policies as policies
where policies.source_key in (
  'nostr_relay_primal', 'nostr_relay_nos_lol', 'nostr_relay_nostr_net'
);
$function$;

-- Remove Nostr from the generic service_role queue lifecycle.  Each exact
-- source function is patched only when its reviewed predecessor text occurs
-- once; schema drift aborts the migration.
do $generic_isolation$
declare
  definition text;
  updated_definition text;
  old_claim_sweep constant text := $needle$  where exhausted.attempts >= exhausted.max_attempts
    and not exhausted.is_demo$needle$;
  new_claim_sweep constant text := $needle$  where exhausted.job_type <> 'source.nostr.relay'
    and exhausted.attempts >= exhausted.max_attempts
    and not exhausted.is_demo$needle$;
  old_claimable constant text := $needle$    where j.attempts < j.max_attempts
      and not j.is_demo$needle$;
  new_claimable constant text := $needle$    where j.job_type <> 'source.nostr.relay'
      and j.attempts < j.max_attempts
      and not j.is_demo$needle$;
  old_leased_guard constant text := $needle$  if leased_job.is_demo
    or leased_job.status <> 'running'$needle$;
  new_leased_guard constant text := $needle$  if leased_job.is_demo
    or leased_job.job_type = 'source.nostr.relay'
    or leased_job.status <> 'running'$needle$;
  old_pause_guard constant text := $needle$  where jobs.id = p_job_id
    and jobs.status = 'running'$needle$;
  new_pause_guard constant text := $needle$  where jobs.id = p_job_id
    and jobs.job_type <> 'source.nostr.relay'
    and jobs.status = 'running'$needle$;
  old_nostr_worker_guard constant text := $needle$  if worker_id is null
    or btrim(worker_id) = ''
    or char_length(worker_id) > 160
  then$needle$;
  new_nostr_worker_guard constant text := $needle$  if worker_id is null
    or worker_id !~ '^nostr-collector-[a-z0-9][a-z0-9_.-]{0,63}$'
  then$needle$;
begin
  select pg_get_functiondef(
    'ingest.claim_jobs_v2(text,text[],integer,integer)'::regprocedure
  ) into definition;
  if definition is null
    or length(definition) - length(replace(definition, old_claim_sweep, ''))
      <> length(old_claim_sweep)
    or length(definition) - length(replace(definition, old_claimable, ''))
      <> length(old_claimable)
  then
    raise exception using
      errcode = '55000',
      message = 'claim_jobs_v2 no longer matches the reviewed Nostr isolation points';
  end if;
  updated_definition := replace(
    replace(definition, old_claim_sweep, new_claim_sweep),
    old_claimable,
    new_claimable
  );
  if updated_definition = definition
    or position(old_claim_sweep in updated_definition) <> 0
    or position(old_claimable in updated_definition) <> 0
    or position(new_claim_sweep in updated_definition) = 0
    or position(new_claimable in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'claim_jobs_v2 Nostr isolation did not match exactly';
  end if;
  execute updated_definition;

  select pg_get_functiondef(
    'ingest.heartbeat_job_v2(uuid,text,bigint,integer)'::regprocedure
  ) into definition;
  if definition is null
    or length(definition) - length(replace(definition, old_leased_guard, ''))
      <> length(old_leased_guard)
  then
    raise exception using
      errcode = '55000',
      message = 'heartbeat_job_v2 no longer matches the reviewed Nostr isolation point';
  end if;
  updated_definition := replace(definition, old_leased_guard, new_leased_guard);
  if updated_definition = definition
    or position(old_leased_guard in updated_definition) <> 0
    or position(new_leased_guard in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'heartbeat_job_v2 Nostr isolation did not match exactly';
  end if;
  execute updated_definition;

  select pg_get_functiondef(
    'ingest.fail_job_v2(uuid,text,bigint,text,text,boolean)'::regprocedure
  ) into definition;
  if definition is null
    or length(definition) - length(replace(definition, old_leased_guard, ''))
      <> length(old_leased_guard)
  then
    raise exception using
      errcode = '55000',
      message = 'fail_job_v2 no longer matches the reviewed Nostr isolation point';
  end if;
  updated_definition := replace(definition, old_leased_guard, new_leased_guard);
  if updated_definition = definition
    or position(old_leased_guard in updated_definition) <> 0
    or position(new_leased_guard in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'fail_job_v2 Nostr isolation did not match exactly';
  end if;
  execute updated_definition;

  select pg_get_functiondef(
    'ingest.pause_job_for_budget_v2(uuid,text,bigint,timestamptz)'::regprocedure
  ) into definition;
  if definition is null
    or length(definition) - length(replace(definition, old_pause_guard, ''))
      <> length(old_pause_guard)
  then
    raise exception using
      errcode = '55000',
      message = 'pause_job_for_budget_v2 no longer matches the reviewed Nostr isolation point';
  end if;
  updated_definition := replace(definition, old_pause_guard, new_pause_guard);
  if updated_definition = definition
    or position(old_pause_guard in updated_definition) <> 0
    or position(new_pause_guard in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'pause_job_for_budget_v2 Nostr isolation did not match exactly';
  end if;
  execute updated_definition;

  select pg_get_functiondef(
    'ingest.begin_nostr_relay_job(uuid,text,bigint,text)'::regprocedure
  ) into definition;
  if definition is null
    or length(definition) - length(replace(definition, old_nostr_worker_guard, ''))
      <> length(old_nostr_worker_guard)
  then
    raise exception using
      errcode = '55000',
      message = 'begin_nostr_relay_job no longer matches the reviewed worker identity point';
  end if;
  updated_definition := replace(
    definition, old_nostr_worker_guard, new_nostr_worker_guard
  );
  if updated_definition = definition
    or position(old_nostr_worker_guard in updated_definition) <> 0
    or position(new_nostr_worker_guard in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'begin_nostr_relay_job worker identity update did not match exactly';
  end if;
  execute updated_definition;

  select pg_get_functiondef(
    'ingest.finalize_nostr_relay_job(uuid,text,bigint,jsonb)'::regprocedure
  ) into definition;
  if definition is null
    or length(definition) - length(replace(definition, old_nostr_worker_guard, ''))
      <> length(old_nostr_worker_guard)
  then
    raise exception using
      errcode = '55000',
      message = 'finalize_nostr_relay_job no longer matches the reviewed worker identity point';
  end if;
  updated_definition := replace(
    definition, old_nostr_worker_guard, new_nostr_worker_guard
  );
  if updated_definition = definition
    or position(old_nostr_worker_guard in updated_definition) <> 0
    or position(new_nostr_worker_guard in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'finalize_nostr_relay_job worker identity update did not match exactly';
  end if;
  execute updated_definition;
end;
$generic_isolation$;

alter function ingest.claim_jobs_v2(text, text[], integer, integer) owner to postgres;
alter function ingest.heartbeat_job_v2(uuid, text, bigint, integer) owner to postgres;
alter function ingest.fail_job_v2(uuid, text, bigint, text, text, boolean) owner to postgres;
alter function ingest.pause_job_for_budget_v2(uuid, text, bigint, timestamptz) owner to postgres;
alter function ingest.begin_nostr_relay_job(uuid, text, bigint, text) owner to postgres;
alter function ingest.finalize_nostr_relay_job(uuid, text, bigint, jsonb) owner to postgres;

alter function ingest.claim_nostr_relay_jobs_v1(text, integer) owner to postgres;
alter function ingest.enqueue_due_nostr_relay_jobs_v1(text) owner to postgres;
alter function ingest.heartbeat_nostr_relay_job_v1(uuid, text, bigint, integer) owner to postgres;
alter function ingest.fail_nostr_relay_job_v1(uuid, text, bigint, text, text, boolean) owner to postgres;
alter function ingest.pause_nostr_relay_job_v1(uuid, text, bigint, timestamptz) owner to postgres;
alter function ingest.upsert_nostr_worker_heartbeat_v1(text, text, jsonb) owner to postgres;
alter function ingest.nostr_worker_runtime_ready_v1() owner to postgres;
alter function ingest.get_nostr_worker_policy_snapshot_v1() owner to postgres;

revoke all on function ingest.claim_nostr_relay_jobs_v1(text, integer)
  from public, anon, authenticated, service_role, pokecrack_nostr_worker;
revoke all on function ingest.enqueue_due_nostr_relay_jobs_v1(text)
  from public, anon, authenticated, service_role, pokecrack_nostr_worker;
revoke all on function ingest.heartbeat_nostr_relay_job_v1(uuid, text, bigint, integer)
  from public, anon, authenticated, service_role, pokecrack_nostr_worker;
revoke all on function ingest.fail_nostr_relay_job_v1(uuid, text, bigint, text, text, boolean)
  from public, anon, authenticated, service_role, pokecrack_nostr_worker;
revoke all on function ingest.pause_nostr_relay_job_v1(uuid, text, bigint, timestamptz)
  from public, anon, authenticated, service_role, pokecrack_nostr_worker;
revoke all on function ingest.upsert_nostr_worker_heartbeat_v1(text, text, jsonb)
  from public, anon, authenticated, service_role, pokecrack_nostr_worker;
revoke all on function ingest.nostr_worker_runtime_ready_v1()
  from public, anon, authenticated, service_role, pokecrack_nostr_worker;
revoke all on function ingest.get_nostr_worker_policy_snapshot_v1()
  from public, anon, authenticated, service_role, pokecrack_nostr_worker;

grant execute on function ingest.claim_nostr_relay_jobs_v1(text, integer)
  to pokecrack_nostr_worker;
grant execute on function ingest.enqueue_due_nostr_relay_jobs_v1(text)
  to pokecrack_nostr_worker;
grant execute on function ingest.heartbeat_nostr_relay_job_v1(uuid, text, bigint, integer)
  to pokecrack_nostr_worker;
grant execute on function ingest.fail_nostr_relay_job_v1(uuid, text, bigint, text, text, boolean)
  to pokecrack_nostr_worker;
grant execute on function ingest.pause_nostr_relay_job_v1(uuid, text, bigint, timestamptz)
  to pokecrack_nostr_worker;
grant execute on function ingest.upsert_nostr_worker_heartbeat_v1(text, text, jsonb)
  to pokecrack_nostr_worker;
grant execute on function ingest.nostr_worker_runtime_ready_v1()
  to pokecrack_nostr_worker;
grant execute on function ingest.get_nostr_worker_policy_snapshot_v1()
  to pokecrack_nostr_worker;

-- Move the two typed persistence effects away from service_role.  Existing
-- collector processes must keep Nostr disabled; the dedicated process is the
-- only capability holder after this forward migration.
revoke all on function ingest.begin_nostr_relay_job(uuid, text, bigint, text)
  from public, anon, authenticated, service_role, pokecrack_nostr_worker;
revoke all on function ingest.finalize_nostr_relay_job(uuid, text, bigint, jsonb)
  from public, anon, authenticated, service_role, pokecrack_nostr_worker;
grant execute on function ingest.begin_nostr_relay_job(uuid, text, bigint, text)
  to pokecrack_nostr_worker;
grant execute on function ingest.finalize_nostr_relay_job(uuid, text, bigint, jsonb)
  to pokecrack_nostr_worker;

-- Explicitly deny the generic queue/health surface to the Nostr capability.
revoke all on function ingest.claim_jobs_v2(text, text[], integer, integer)
  from pokecrack_nostr_worker;
revoke all on function ingest.heartbeat_job_v2(uuid, text, bigint, integer)
  from pokecrack_nostr_worker;
revoke all on function ingest.fail_job_v2(uuid, text, bigint, text, text, boolean)
  from pokecrack_nostr_worker;
revoke all on function ingest.pause_job_for_budget_v2(uuid, text, bigint, timestamptz)
  from pokecrack_nostr_worker;
revoke all on function ingest.upsert_worker_heartbeat_v1(text, text, text, jsonb)
  from pokecrack_nostr_worker;

-- Public social status is computed by an owner SECURITY DEFINER projection;
-- neither a web service credential nor the Nostr network process needs direct
-- reads of the private hashed activity ledger.
drop policy if exists nostr_candidates_service_role_select
  on ingest.nostr_relay_candidates;
drop policy if exists nostr_observations_service_role_select
  on ingest.nostr_relay_observations;
drop policy if exists nostr_checkpoints_service_role_select
  on ingest.nostr_relay_checkpoints;
revoke all privileges on table
  ingest.nostr_relay_candidates,
  ingest.nostr_relay_observations,
  ingest.nostr_relay_checkpoints
  from public, anon, authenticated, service_role, pokecrack_nostr_worker;

-- V2 composes the 090 release checks with the exact two isolated login/group
-- contracts.  The old V1 attestation becomes owner-only; the deploy login can
-- execute exactly this one function and nothing else in ingest.
create or replace function ingest.verify_nostr_release_v2()
returns jsonb
language sql
stable
security definer
set search_path = pg_catalog
as $attestation$
with base_contract as (
  select ingest.verify_nostr_release_v1()
    - array['attestor_role_exact', 'nostr_policies_exact', 'nostr_acl_exact']::text[]
    as payload
),
expected_worker_functions(signature) as (
  values
    ('ingest.enqueue_due_nostr_relay_jobs_v1(text)'::text),
    ('ingest.claim_nostr_relay_jobs_v1(text,integer)'::text),
    ('ingest.heartbeat_nostr_relay_job_v1(uuid,text,bigint,integer)'::text),
    ('ingest.fail_nostr_relay_job_v1(uuid,text,bigint,text,text,boolean)'::text),
    ('ingest.pause_nostr_relay_job_v1(uuid,text,bigint,timestamp with time zone)'::text),
    ('ingest.upsert_nostr_worker_heartbeat_v1(text,text,jsonb)'::text),
    ('ingest.nostr_worker_runtime_ready_v1()'::text),
    ('ingest.get_nostr_worker_policy_snapshot_v1()'::text),
    ('ingest.begin_nostr_relay_job(uuid,text,bigint,text)'::text),
    ('ingest.finalize_nostr_relay_job(uuid,text,bigint,jsonb)'::text)
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
    on login_role.rolname = 'pokecrack_nostr_worker_login'
  where group_role.rolname = 'pokecrack_nostr_worker'
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
nostr_relations as (
  select relations.oid, relations.relowner, relations.relacl
  from pg_catalog.pg_class as relations
  where relations.oid = any(array[
    'ingest.nostr_relay_candidates'::regclass,
    'ingest.nostr_relay_observations'::regclass,
    'ingest.nostr_relay_checkpoints'::regclass
  ]::oid[])
),
nostr_sequences as (
  select relations.oid, relations.relowner, relations.relacl
  from pg_catalog.pg_class as relations
  where relations.oid = pg_get_serial_sequence(
    'ingest.nostr_relay_observations', 'id'
  )::regclass
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
  cross join lateral aclexplode(coalesce(
    columns.attacl, '{}'::aclitem[]
  )) as grants
  where columns.attrelid in (select oid from ingest_relations)
    and columns.attnum > 0
    and not columns.attisdropped
),
nostr_relation_acl_grants as (
  select
    relations.oid,
    relations.relowner,
    grants.grantee,
    grants.privilege_type
  from nostr_relations as relations
  cross join lateral aclexplode(coalesce(
    relations.relacl,
    acldefault('r'::"char", relations.relowner)
  )) as grants
),
nostr_column_acl_grants as (
  select
    columns.attrelid as oid,
    relations.relowner,
    grants.grantee,
    grants.privilege_type
  from pg_catalog.pg_attribute as columns
  join nostr_relations as relations on relations.oid = columns.attrelid
  cross join lateral aclexplode(coalesce(
    columns.attacl, '{}'::aclitem[]
  )) as grants
  where columns.attrelid in (select oid from nostr_relations)
    and columns.attnum > 0
    and not columns.attisdropped
),
nostr_sequence_acl_grants as (
  select
    sequences.oid,
    sequences.relowner,
    grants.grantee,
    grants.privilege_type
  from nostr_sequences as sequences
  cross join lateral aclexplode(coalesce(
    sequences.relacl,
    acldefault('s'::"char", sequences.relowner)
  )) as grants
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
attestor_function_acl_grants as (
  select
    functions.oid,
    functions.proowner,
    functions.prosecdef,
    functions.proconfig,
    grants.grantee,
    grants.privilege_type,
    grants.is_grantable
  from pg_catalog.pg_proc as functions
  cross join lateral aclexplode(coalesce(
    functions.proacl,
    acldefault('f'::"char", functions.proowner)
  )) as grants
  where functions.oid = 'ingest.verify_nostr_release_v2()'::regprocedure
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
    )) as pause_definition,
    lower(pg_get_functiondef(
      'ingest.complete_job_v2(uuid,text,bigint)'::regprocedure
    )) as complete_definition,
    lower(pg_get_functiondef(
      'ingest.begin_nostr_relay_job(uuid,text,bigint,text)'::regprocedure
    )) as begin_definition,
    lower(pg_get_functiondef(
      'ingest.finalize_nostr_relay_job(uuid,text,bigint,jsonb)'::regprocedure
    )) as finalize_definition
)
select base_contract.payload || jsonb_build_object(
  'ledger_100', (
    select count(*) = 1
    from supabase_migrations.schema_migrations
    where version = '20260910000000'
      and name = 'nostr_worker_role_isolation'
  ),
  'nostr_policies_exact', (
    select count(*) = 0
    from pg_catalog.pg_policies
    where schemaname = 'ingest'
      and tablename in (
        'nostr_relay_candidates',
        'nostr_relay_observations',
        'nostr_relay_checkpoints'
      )
  ),
  'nostr_acl_exact', (
    (select count(*) = 1 from nostr_sequences)
    -- Three PG17 tables must expose exactly the eight owner privileges each,
    -- zero column grants, and the identity sequence's three owner privileges.
    -- This categorical ACL proof covers every privilege kind without a
    -- privilege-name allowlist and rejects every non-owner grantee.
    and (select count(*) = 24
      and count(distinct grants.privilege_type) = 8
      and bool_and(grants.grantee = grants.relowner)
      from nostr_relation_acl_grants as grants)
    and (select count(*) = 0 from nostr_column_acl_grants)
    and (select count(*) = 3
      and count(distinct grants.privilege_type) = 3
      and bool_and(grants.grantee = grants.relowner)
      from nostr_sequence_acl_grants as grants)
    and not exists (
      select 1
      from nostr_relations as relations
      cross join unnest(array[
        'service_role', 'anon', 'authenticated',
        'pokecrack_nostr_worker', 'pokecrack_nostr_attestor'
      ]::name[]) as checked_roles(role_name)
      where has_table_privilege(checked_roles.role_name, relations.oid, 'SELECT')
        or has_table_privilege(checked_roles.role_name, relations.oid, 'INSERT')
        or has_table_privilege(checked_roles.role_name, relations.oid, 'UPDATE')
        or has_table_privilege(checked_roles.role_name, relations.oid, 'DELETE')
        or has_table_privilege(checked_roles.role_name, relations.oid, 'REFERENCES')
        or has_table_privilege(checked_roles.role_name, relations.oid, 'TRIGGER')
        or has_table_privilege(checked_roles.role_name, relations.oid, 'MAINTAIN')
        or has_any_column_privilege(
          checked_roles.role_name,
          relations.oid,
          'SELECT,INSERT,UPDATE,REFERENCES'
        )
    )
    and not exists (
      select 1
      from nostr_relation_acl_grants as grants
      cross join unnest(array[
        'service_role', 'anon', 'authenticated',
        'pokecrack_nostr_worker', 'pokecrack_nostr_attestor'
      ]::name[]) as checked_roles(role_name)
      where case
        when grants.grantee = 0 then true
        else pg_has_role(checked_roles.role_name, grants.grantee, 'USAGE')
      end
    )
    and not exists (
      select 1
      from nostr_relations as relations
      cross join unnest(array[
        'service_role', 'anon', 'authenticated',
        'pokecrack_nostr_worker', 'pokecrack_nostr_attestor'
      ]::name[]) as checked_roles(role_name)
      where pg_has_role(
        checked_roles.role_name, relations.relowner, 'USAGE'
      )
    )
    and not exists (
      select 1
      from nostr_column_acl_grants as grants
      cross join unnest(array[
        'service_role', 'anon', 'authenticated',
        'pokecrack_nostr_worker', 'pokecrack_nostr_attestor'
      ]::name[]) as checked_roles(role_name)
      where case
        when grants.grantee = 0 then true
        else pg_has_role(checked_roles.role_name, grants.grantee, 'USAGE')
      end
    )
    and not exists (
      select 1
      from nostr_sequences as sequences
      cross join unnest(array[
        'service_role', 'anon', 'authenticated',
        'pokecrack_nostr_worker', 'pokecrack_nostr_attestor'
      ]::name[]) as checked_roles(role_name)
      where has_sequence_privilege(
        checked_roles.role_name, sequences.oid, 'USAGE'
      )
        or has_sequence_privilege(
          checked_roles.role_name, sequences.oid, 'SELECT'
        )
        or has_sequence_privilege(
          checked_roles.role_name, sequences.oid, 'UPDATE'
        )
        or pg_has_role(
          checked_roles.role_name, sequences.relowner, 'USAGE'
        )
    )
    and not exists (
      select 1
      from nostr_sequence_acl_grants as grants
      cross join unnest(array[
        'service_role', 'anon', 'authenticated',
        'pokecrack_nostr_worker', 'pokecrack_nostr_attestor'
      ]::name[]) as checked_roles(role_name)
      where case
        when grants.grantee = 0 then true
        else pg_has_role(checked_roles.role_name, grants.grantee, 'USAGE')
      end
    )
  ),
  'attestor_role_exact', (
    (select count(*) = 1
      and count(*) filter (where group_valid and login_valid) = 1
      from attestor_roles)
    and (select count(*) = 1
      and bool_and(
        not memberships.admin_option
          and not memberships.inherit_option
          and memberships.set_option
      )
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
    and has_schema_privilege('pokecrack_nostr_attestor', 'ingest', 'USAGE')
    and not has_schema_privilege('pokecrack_nostr_attestor', 'ingest', 'CREATE')
    and has_function_privilege(
      'pokecrack_nostr_attestor',
      'ingest.verify_nostr_release_v2()',
      'EXECUTE'
    )
    and (select count(distinct grants.oid) = 1
      and bool_and(
        pg_get_userbyid(grants.proowner) = 'postgres'
        and grants.prosecdef
        and coalesce(grants.proconfig, '{}'::text[])
          = array['search_path=pg_catalog']::text[]
      )
      from attestor_function_acl_grants as grants)
    and not exists (
      select 1 from ingest_functions as functions
      where functions.oid <> 'ingest.verify_nostr_release_v2()'::regprocedure
        and has_function_privilege(
          'pokecrack_nostr_attestor', functions.oid, 'EXECUTE'
        )
    )
    and not exists (
      select 1
      from attestor_function_acl_grants as grants
      cross join attestor_roles as roles
      where grants.privilege_type <> 'EXECUTE'
        or grants.is_grantable
        or grants.grantee not in (grants.proowner, roles.group_oid)
    )
    and not exists (
      select 1 from ingest_relations as relations
      where has_table_privilege('pokecrack_nostr_attestor', relations.oid, 'SELECT')
        or has_table_privilege('pokecrack_nostr_attestor', relations.oid, 'INSERT')
        or has_table_privilege('pokecrack_nostr_attestor', relations.oid, 'UPDATE')
        or has_table_privilege('pokecrack_nostr_attestor', relations.oid, 'DELETE')
        or has_table_privilege('pokecrack_nostr_attestor', relations.oid, 'REFERENCES')
        or has_table_privilege('pokecrack_nostr_attestor', relations.oid, 'TRIGGER')
        or has_table_privilege('pokecrack_nostr_attestor', relations.oid, 'MAINTAIN')
        or has_any_column_privilege(
          'pokecrack_nostr_attestor', relations.oid,
          'SELECT,INSERT,UPDATE,REFERENCES'
        )
    )
    and not exists (
      select 1 from ingest_relation_acl_grants as grants
      where case
        when grants.grantee = 0 then true
        else pg_has_role(
          'pokecrack_nostr_attestor', grants.grantee, 'USAGE'
        )
      end
    )
    and not exists (
      select 1 from ingest_relations as relations
      where pg_has_role(
        'pokecrack_nostr_attestor', relations.relowner, 'USAGE'
      )
    )
    and not exists (
      select 1 from ingest_sequences as sequences
      where has_sequence_privilege('pokecrack_nostr_attestor', sequences.oid, 'USAGE')
        or has_sequence_privilege('pokecrack_nostr_attestor', sequences.oid, 'SELECT')
        or has_sequence_privilege('pokecrack_nostr_attestor', sequences.oid, 'UPDATE')
    )
    and not has_schema_privilege(
      'pokecrack_nostr_attestor_login', 'ingest', 'USAGE'
    )
    and not exists (
      select 1 from ingest_functions as functions
      where has_function_privilege(
        'pokecrack_nostr_attestor_login', functions.oid, 'EXECUTE'
      )
    )
    and not exists (
      select 1 from ingest_relations as relations
      where has_table_privilege('pokecrack_nostr_attestor_login', relations.oid, 'SELECT')
        or has_table_privilege('pokecrack_nostr_attestor_login', relations.oid, 'INSERT')
        or has_table_privilege('pokecrack_nostr_attestor_login', relations.oid, 'UPDATE')
        or has_table_privilege('pokecrack_nostr_attestor_login', relations.oid, 'DELETE')
        or has_table_privilege('pokecrack_nostr_attestor_login', relations.oid, 'REFERENCES')
        or has_table_privilege('pokecrack_nostr_attestor_login', relations.oid, 'TRIGGER')
        or has_table_privilege('pokecrack_nostr_attestor_login', relations.oid, 'MAINTAIN')
        or has_any_column_privilege(
          'pokecrack_nostr_attestor_login', relations.oid,
          'SELECT,INSERT,UPDATE,REFERENCES'
        )
    )
    and not exists (
      select 1 from ingest_relation_acl_grants as grants
      where case
        when grants.grantee = 0 then true
        else pg_has_role(
          'pokecrack_nostr_attestor_login', grants.grantee, 'USAGE'
        )
      end
    )
    and not exists (
      select 1 from ingest_relations as relations
      where pg_has_role(
        'pokecrack_nostr_attestor_login', relations.relowner, 'USAGE'
      )
    )
    and not exists (
      select 1 from ingest_sequences as sequences
      where has_sequence_privilege('pokecrack_nostr_attestor_login', sequences.oid, 'USAGE')
        or has_sequence_privilege('pokecrack_nostr_attestor_login', sequences.oid, 'SELECT')
        or has_sequence_privilege('pokecrack_nostr_attestor_login', sequences.oid, 'UPDATE')
    )
    and not exists (
      select 1
      from pg_catalog.pg_db_role_setting as settings
      join attestor_roles as roles
        on settings.setrole in (roles.group_oid, roles.login_oid)
    )
    and not exists (
      select 1
      from owned_catalog_objects as objects
      join attestor_roles as roles
        on objects.owner_oid in (roles.group_oid, roles.login_oid)
    )
  ),
  'nostr_worker_role_exact', (
    (select count(*) = 1
      and count(*) filter (where group_valid and login_valid) = 1
      from worker_roles)
    and (select count(*) = 1
      and bool_and(
        not memberships.admin_option
          and not memberships.inherit_option
          and memberships.set_option
      )
      from pg_catalog.pg_auth_members as memberships
      join worker_roles as roles on roles.group_oid = memberships.roleid
      where memberships.member = roles.login_oid)
    and not exists (
      select 1
      from pg_catalog.pg_auth_members as memberships
      join worker_roles as roles on roles.login_oid = memberships.member
      where memberships.roleid <> roles.group_oid
    )
    and not exists (
      select 1
      from pg_catalog.pg_auth_members as memberships
      join worker_roles as roles on roles.group_oid = memberships.roleid
      where memberships.member <> roles.login_oid
    )
    and not exists (
      select 1
      from pg_catalog.pg_auth_members as memberships
      join worker_roles as roles on roles.group_oid = memberships.member
    )
    and has_schema_privilege('pokecrack_nostr_worker', 'ingest', 'USAGE')
    and not has_schema_privilege('pokecrack_nostr_worker', 'ingest', 'CREATE')
    and (select count(*) = 10
      and bool_and(has_function_privilege(
        'pokecrack_nostr_worker', signatures.signature, 'EXECUTE'
      ))
      from expected_worker_functions as signatures)
    and (select count(distinct grants.oid) = 10
      and bool_and(
        pg_get_userbyid(grants.proowner) = 'postgres'
        and grants.prosecdef
        and coalesce(grants.proconfig, '{}'::text[])
          = array['search_path=pg_catalog']::text[]
      )
      from worker_function_acl_grants as grants)
    and not exists (
      select 1 from ingest_functions as functions
      where not exists (
        select 1
        from expected_worker_functions as expected
        where functions.oid = expected.signature::regprocedure
      )
      and has_function_privilege(
        'pokecrack_nostr_worker', functions.oid, 'EXECUTE'
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
    and not exists (
      select 1 from ingest_relations as relations
      where has_table_privilege('pokecrack_nostr_worker', relations.oid, 'SELECT')
        or has_table_privilege('pokecrack_nostr_worker', relations.oid, 'INSERT')
        or has_table_privilege('pokecrack_nostr_worker', relations.oid, 'UPDATE')
        or has_table_privilege('pokecrack_nostr_worker', relations.oid, 'DELETE')
        or has_table_privilege('pokecrack_nostr_worker', relations.oid, 'REFERENCES')
        or has_table_privilege('pokecrack_nostr_worker', relations.oid, 'TRIGGER')
        or has_table_privilege('pokecrack_nostr_worker', relations.oid, 'MAINTAIN')
        or has_any_column_privilege(
          'pokecrack_nostr_worker', relations.oid,
          'SELECT,INSERT,UPDATE,REFERENCES'
        )
    )
    and not exists (
      select 1 from ingest_relation_acl_grants as grants
      where case
        when grants.grantee = 0 then true
        else pg_has_role('pokecrack_nostr_worker', grants.grantee, 'USAGE')
      end
    )
    and not exists (
      select 1 from ingest_relations as relations
      where pg_has_role(
        'pokecrack_nostr_worker', relations.relowner, 'USAGE'
      )
    )
    and not exists (
      select 1 from ingest_sequences as sequences
      where has_sequence_privilege('pokecrack_nostr_worker', sequences.oid, 'USAGE')
        or has_sequence_privilege('pokecrack_nostr_worker', sequences.oid, 'SELECT')
        or has_sequence_privilege('pokecrack_nostr_worker', sequences.oid, 'UPDATE')
    )
    and not has_schema_privilege(
      'pokecrack_nostr_worker_login', 'ingest', 'USAGE'
    )
    and not exists (
      select 1 from ingest_functions as functions
      where has_function_privilege(
        'pokecrack_nostr_worker_login', functions.oid, 'EXECUTE'
      )
    )
    and not exists (
      select 1 from ingest_relations as relations
      where has_table_privilege('pokecrack_nostr_worker_login', relations.oid, 'SELECT')
        or has_table_privilege('pokecrack_nostr_worker_login', relations.oid, 'INSERT')
        or has_table_privilege('pokecrack_nostr_worker_login', relations.oid, 'UPDATE')
        or has_table_privilege('pokecrack_nostr_worker_login', relations.oid, 'DELETE')
        or has_table_privilege('pokecrack_nostr_worker_login', relations.oid, 'REFERENCES')
        or has_table_privilege('pokecrack_nostr_worker_login', relations.oid, 'TRIGGER')
        or has_table_privilege('pokecrack_nostr_worker_login', relations.oid, 'MAINTAIN')
        or has_any_column_privilege(
          'pokecrack_nostr_worker_login', relations.oid,
          'SELECT,INSERT,UPDATE,REFERENCES'
        )
    )
    and not exists (
      select 1 from ingest_relation_acl_grants as grants
      where case
        when grants.grantee = 0 then true
        else pg_has_role(
          'pokecrack_nostr_worker_login', grants.grantee, 'USAGE'
        )
      end
    )
    and not exists (
      select 1 from ingest_relations as relations
      where pg_has_role(
        'pokecrack_nostr_worker_login', relations.relowner, 'USAGE'
      )
    )
    and not exists (
      select 1 from ingest_sequences as sequences
      where has_sequence_privilege('pokecrack_nostr_worker_login', sequences.oid, 'USAGE')
        or has_sequence_privilege('pokecrack_nostr_worker_login', sequences.oid, 'SELECT')
        or has_sequence_privilege('pokecrack_nostr_worker_login', sequences.oid, 'UPDATE')
    )
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
    and (select bool_and(not has_function_privilege(
      'service_role', signatures.signature, 'EXECUTE'
    )) from expected_worker_functions as signatures)
    and (select
      claim_definition like '%where exhausted.job_type <> ''source.nostr.relay''%'
      and claim_definition like '%where j.job_type <> ''source.nostr.relay''%'
      and heartbeat_definition like '%leased_job.job_type = ''source.nostr.relay''%'
      and fail_definition like '%leased_job.job_type = ''source.nostr.relay''%'
      and pause_definition like '%jobs.job_type <> ''source.nostr.relay''%'
      and complete_definition like '%''source.nostr.relay''%'
      and begin_definition like '%worker_id !~ ''^nostr-collector-%'
      and finalize_definition like '%worker_id !~ ''^nostr-collector-%'
      from generic_definitions)
  )
)
from base_contract;
$attestation$;

alter function ingest.verify_nostr_release_v2() owner to postgres;
revoke all on function ingest.verify_nostr_release_v1()
  from public, anon, authenticated, service_role, pokecrack_nostr_attestor;
revoke all on function ingest.verify_nostr_release_v2()
  from public, anon, authenticated, service_role, pokecrack_nostr_attestor,
    pokecrack_nostr_worker;
grant execute on function ingest.verify_nostr_release_v2()
  to pokecrack_nostr_attestor;

comment on function ingest.claim_nostr_relay_jobs_v1(text, integer) is
  'Capability-scoped single-job claim for live source.nostr.relay only.';
comment on function ingest.enqueue_due_nostr_relay_jobs_v1(text) is
  'Capability-scoped idempotent current-minute scheduler for the three reviewed Nostr relays.';
comment on function ingest.heartbeat_nostr_relay_job_v1(uuid, text, bigint, integer) is
  'Capability-scoped fenced heartbeat for an existing live Nostr relay job only.';
comment on function ingest.fail_nostr_relay_job_v1(uuid, text, bigint, text, text, boolean) is
  'Capability-scoped fenced failure transition for an existing live Nostr relay job only.';
comment on function ingest.pause_nostr_relay_job_v1(uuid, text, bigint, timestamptz) is
  'Capability-scoped fenced pause for an existing live Nostr relay job only.';
comment on function ingest.upsert_nostr_worker_heartbeat_v1(text, text, jsonb) is
  'Capability-scoped exact health heartbeat for the isolated Nostr collector.';
comment on function ingest.nostr_worker_runtime_ready_v1() is
  'Boolean-only exact relay policy and checkpoint proof for the isolated Nostr collector.';
comment on function ingest.get_nostr_worker_policy_snapshot_v1() is
  'Reviewed non-secret relay policy projection for exact isolated-worker readiness checks.';
comment on function ingest.verify_nostr_release_v2() is
  'Least-privilege hosted Nostr release attestation including isolated worker and deploy identities.';

commit;
