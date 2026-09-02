begin;

-- Jetstream can reject an otherwise valid, persisted cursor once it falls
-- below the upstream replay floor.  This is the only recovery boundary that
-- may clear the cursor: a worker must still hold the exact job generation and
-- request gate, the source contract must be intact, and the checkpoint must
-- be demonstrably stale.  The operation never removes activity rows, changes
-- their counters, or claims a successful collection; it simply allows the
-- next bounded slice to begin from Jetstream's current live stream.
create or replace function ingest.recover_bluesky_cursor_too_old_job_v1(
  job_id uuid,
  worker_id text,
  lease_generation bigint,
  expected_start_cursor bigint
)
returns setof ingest.jobs
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $$
declare
  leased_job ingest.jobs%rowtype;
  completed_job ingest.jobs%rowtype;
  request_gate ingest.source_request_gates%rowtype;
  checkpoint ingest.bluesky_jetstream_checkpoints%rowtype;
  policy_id uuid;
  lease_checked_at timestamptz;
  recovery_time timestamptz;
begin
  if job_id is null then
    raise exception using errcode = '22023', message = 'job_id must not be null';
  end if;
  if worker_id is null
    or btrim(worker_id) = ''
    or char_length(worker_id) > 160
  then
    raise exception using
      errcode = '22023',
      message = 'worker_id must contain 1 to 160 characters';
  end if;
  if lease_generation is null or lease_generation < 1 then
    raise exception using
      errcode = '22023',
      message = 'lease_generation must be positive';
  end if;
  if expected_start_cursor is null or expected_start_cursor < 0 then
    raise exception using
      errcode = '22023',
      message = 'expected_start_cursor must be a non-negative Jetstream sequence';
  end if;

  select jobs.*
  into leased_job
  from ingest.jobs as jobs
  where jobs.id = recover_bluesky_cursor_too_old_job_v1.job_id
  for update of jobs;

  if not found then
    return;
  end if;

  lease_checked_at := clock_timestamp();
  if leased_job.status <> 'running'
    or leased_job.locked_by is distinct from worker_id
    or leased_job.lease_generation <> lease_generation
    or leased_job.locked_at is null
    or leased_job.lock_expires_at is null
    or leased_job.lock_expires_at <= lease_checked_at
  then
    return;
  end if;

  if leased_job.is_demo
    or leased_job.job_type <> 'source.bluesky.jetstream'
    or leased_job.payload <> '{}'::jsonb
  then
    raise exception using
      errcode = '22023',
      message = 'Bluesky cursor recovery requires a live source.bluesky.jetstream job with an empty payload';
  end if;

  perform pg_advisory_xact_lock(
    hashtextextended('pokecrack:source:bluesky:jetstream:live', 0)
  );

  -- Match the reviewed 10-second runtime contract exactly.  A disabled or
  -- drifted source must not turn an upstream error into a checkpoint reset.
  select policies.id
  into policy_id
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
  for update of policies;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Bluesky Jetstream source policy is unavailable or drifted';
  end if;

  select gates.*
  into request_gate
  from ingest.source_request_gates as gates
  where gates.source_key = 'bluesky_jetstream'
  for update of gates;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Bluesky Jetstream request gate is unavailable';
  end if;

  select checkpoints.*
  into checkpoint
  from ingest.bluesky_jetstream_checkpoints as checkpoints
  where checkpoints.source_policy_id = policy_id
    and not checkpoints.is_demo
  for update of checkpoints;

  if not found then
    raise exception using
      errcode = '55000',
      message = 'live Bluesky Jetstream checkpoint is unavailable';
  end if;

  lease_checked_at := clock_timestamp();
  if leased_job.status <> 'running'
    or leased_job.locked_by is distinct from worker_id
    or leased_job.lease_generation <> lease_generation
    or leased_job.locked_at is null
    or leased_job.lock_expires_at is null
    or leased_job.lock_expires_at <= lease_checked_at
  then
    return;
  end if;

  if request_gate.owner_job_id is distinct from job_id
    or request_gate.owner_lease_generation is distinct from lease_generation
    or request_gate.active_until is null
    or request_gate.active_until <= lease_checked_at
  then
    raise exception using
      errcode = '55000',
      message = 'Bluesky cursor recovery does not own the active request gate';
  end if;

  if checkpoint.last_cursor is distinct from expected_start_cursor then
    raise exception using
      errcode = '40001',
      message = 'Bluesky checkpoint changed before cursor recovery';
  end if;

  recovery_time := clock_timestamp();
  if checkpoint.last_collected_at is null
    or checkpoint.last_collected_at > recovery_time - interval '15 minutes'
  then
    raise exception using
      errcode = '55000',
      message = 'Bluesky cursor recovery requires a stale checkpoint';
  end if;

  update ingest.bluesky_jetstream_checkpoints as checkpoints
  set last_cursor = null,
      updated_at = recovery_time
  where checkpoints.source_policy_id = policy_id
    and not checkpoints.is_demo
    and checkpoints.last_cursor is not distinct from expected_start_cursor
    and checkpoints.last_collected_at <= recovery_time - interval '15 minutes';
  if not found then
    raise exception using
      errcode = '40001',
      message = 'Bluesky checkpoint changed before cursor recovery';
  end if;

  -- The audit record deliberately contains no cursor, event, candidate, or
  -- account content.  It proves an automatic recovery occurred while keeping
  -- private activity data and the upstream sequence out of this ledger.
  insert into ingest.admin_audit_log (
    action,
    object_type,
    object_id,
    detail,
    occurred_at,
    retention_until,
    is_demo
  ) values (
    'bluesky.cursor_reset',
    'ingest.bluesky_jetstream_checkpoints',
    'bluesky_jetstream',
    jsonb_build_object(
      'automatic', true,
      'reason', 'jetstream_cursor_too_old',
      'resume_mode', 'fresh_only',
      'previous_cursor_present', true,
      'preserved_counters', true,
      'preserved_activity_rows', true
    ),
    recovery_time,
    recovery_time + interval '730 days',
    false
  );

  update ingest.jobs as jobs
  set status = 'completed',
      locked_by = null,
      locked_at = null,
      lock_expires_at = null,
      completed_at = recovery_time,
      last_error_code = null,
      last_error_message = null,
      updated_at = recovery_time
  where jobs.id = $1
    and jobs.status = 'running'
    and jobs.locked_by = $2
    and jobs.lease_generation = $3
    and jobs.lock_expires_at > recovery_time
    and not jobs.is_demo
  returning jobs.* into completed_job;
  if not found then
    raise exception using
      errcode = 'P0002',
      message = 'Bluesky cursor recovery lost its fenced lease';
  end if;

  update ingest.source_request_gates as gates
  set owner_job_id = null,
      owner_lease_generation = null,
      acquired_at = null,
      active_until = null
  where gates.source_key = 'bluesky_jetstream'
    and gates.owner_job_id = $1
    and gates.owner_lease_generation = $3;
  if not found then
    raise exception using
      errcode = 'P0002',
      message = 'Bluesky cursor recovery lost its request gate ownership';
  end if;

  return next completed_job;
end;
$$;

alter function ingest.recover_bluesky_cursor_too_old_job_v1(uuid, text, bigint, bigint)
  owner to postgres;
revoke all on function ingest.recover_bluesky_cursor_too_old_job_v1(uuid, text, bigint, bigint)
  from public, anon, authenticated, service_role;
grant execute on function ingest.recover_bluesky_cursor_too_old_job_v1(uuid, text, bigint, bigint)
  to service_role;
comment on function ingest.recover_bluesky_cursor_too_old_job_v1(uuid, text, bigint, bigint) is
  'Fenced audited Bluesky recovery for one upstream CursorTooOld rejection. It clears only a stale exact checkpoint and preserves all activity rows and counters.';

commit;
