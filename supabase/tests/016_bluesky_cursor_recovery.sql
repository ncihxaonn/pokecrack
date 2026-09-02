-- A stale Jetstream replay cursor may be cleared only by the dedicated
-- generation-fenced recovery RPC.  The recovery preserves private activity
-- history and aggregate counters, does not claim freshness, and leaves a
-- redacted audit record.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

create function pg_temp.sqlstate_of(statement text)
returns text
language plpgsql
volatile
as $$
begin
  execute statement;
  return null;
exception
  when others then
    return sqlstate;
end;
$$;

select has_function(
  'ingest',
  'recover_bluesky_cursor_too_old_job_v1',
  array['uuid', 'text', 'bigint', 'bigint'],
  'the typed Bluesky stale-cursor recovery boundary exists'
);
select ok(
  (
    select prosecdef
      and proowner = (select oid from pg_roles where rolname = 'postgres')
      and coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
    from pg_proc
    where oid =
      'ingest.recover_bluesky_cursor_too_old_job_v1(uuid,text,bigint,bigint)'::regprocedure
  )
  and has_function_privilege(
    'service_role',
    'ingest.recover_bluesky_cursor_too_old_job_v1(uuid,text,bigint,bigint)',
    'execute'
  )
  and not has_function_privilege(
    'anon',
    'ingest.recover_bluesky_cursor_too_old_job_v1(uuid,text,bigint,bigint)',
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'ingest.recover_bluesky_cursor_too_old_job_v1(uuid,text,bigint,bigint)',
    'execute'
  )
  and not has_function_privilege(
    'public',
    'ingest.recover_bluesky_cursor_too_old_job_v1(uuid,text,bigint,bigint)',
    'execute'
  ),
  'only service_role receives the postgres-owned fixed-search-path recovery RPC'
);
select ok(
  position(
    'checkpoint.last_cursor is distinct from expected_start_cursor'
    in pg_get_functiondef(
      'ingest.recover_bluesky_cursor_too_old_job_v1(uuid,text,bigint,bigint)'::regprocedure
    )
  ) > 0
  and position(
    'checkpoint.last_collected_at > recovery_time - interval ''15 minutes'''
    in pg_get_functiondef(
      'ingest.recover_bluesky_cursor_too_old_job_v1(uuid,text,bigint,bigint)'::regprocedure
    )
  ) > 0
  and position(
    'preserved_activity_rows'
    in pg_get_functiondef(
      'ingest.recover_bluesky_cursor_too_old_job_v1(uuid,text,bigint,bigint)'::regprocedure
    )
  ) > 0,
  'the recovery requires an exact stale checkpoint and explicitly audits preserved activity'
);

with event_time as materialized (
  select clock_timestamp() as value
)
insert into ingest.bluesky_jetstream_candidates (
  at_uri, public_url, text_excerpt, record_sha256, published_at,
  source_policy_id, source_policy_version, collector_version,
  first_seen_at, last_seen_at, last_cursor, deleted_at, expires_at,
  is_demo, created_at, updated_at
)
select
  'at://did:plc:recoverfixtureabcdefghijkl/app.bsky.feed.post/recoverycandidate',
  'https://bsky.app/profile/did:plc:recoverfixtureabcdefghijkl/post/recoverycandidate',
  'Bounded recovery fixture', repeat('a', 64), null,
  policies.id, 'bluesky-jetstream-v1', 'bluesky-jetstream-v1',
  event_time.value, event_time.value, 899, null,
  event_time.value + interval '30 days', false, event_time.value, event_time.value
from ingest.source_policies as policies
cross join event_time
where policies.source_key = 'bluesky_jetstream';

with event_time as materialized (
  select clock_timestamp() as value
)
insert into ingest.bluesky_jetstream_observations (
  source_policy_id, cursor, at_uri, operation, public_url, text_excerpt,
  record_sha256, published_at, observed_at, expires_at, is_demo
)
select
  policies.id, 899,
  'at://did:plc:recoverfixtureabcdefghijkl/app.bsky.feed.post/recoverycandidate',
  'upsert',
  'https://bsky.app/profile/did:plc:recoverfixtureabcdefghijkl/post/recoverycandidate',
  'Bounded recovery fixture', repeat('a', 64), null,
  event_time.value, event_time.value + interval '30 days', false
from ingest.source_policies as policies
cross join event_time
where policies.source_key = 'bluesky_jetstream';

update ingest.bluesky_jetstream_checkpoints as checkpoints
set last_cursor = 900,
    last_collected_at = clock_timestamp() - interval '16 minutes',
    events_seen_total = 42,
    bytes_seen_total = 4200,
    candidates_seen_total = 6,
    deletions_seen_total = 4,
    updated_at = clock_timestamp()
from ingest.source_policies as policies
where checkpoints.source_policy_id = policies.id
  and policies.source_key = 'bluesky_jetstream';
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '2 seconds'
where source_key = 'bluesky_jetstream';
insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'be140000-0000-4000-8000-000000000001',
  'source.bluesky.jetstream', '{}'::jsonb, 'running', 1,
  clock_timestamp(), clock_timestamp() + interval '10 minutes',
  'bluesky-recovery-worker', 1, false
);
set local role service_role;
create temporary table bluesky_recovery_begin on commit drop as
select * from ingest.begin_bluesky_jetstream_job(
  'be140000-0000-4000-8000-000000000001',
  'bluesky-recovery-worker',
  1
);
reset role;
create temporary table bluesky_recovery_before on commit drop as
select
  checkpoints.last_collected_at,
  checkpoints.events_seen_total,
  checkpoints.bytes_seen_total,
  checkpoints.candidates_seen_total,
  checkpoints.deletions_seen_total,
  (
    select policies.last_success_at
    from ingest.source_policies as policies
    where policies.source_key = 'bluesky_jetstream'
  ) as last_success_at,
  (select count(*)::integer from ingest.bluesky_jetstream_candidates) as candidate_count,
  (select count(*)::integer from ingest.bluesky_jetstream_observations) as observation_count,
  coalesce(
    (
      select jsonb_agg(to_jsonb(candidates) order by candidates.at_uri)
      from ingest.bluesky_jetstream_candidates as candidates
    ),
    '[]'::jsonb
  ) as candidate_rows,
  coalesce(
    (
      select jsonb_agg(to_jsonb(observations) order by observations.cursor)
      from ingest.bluesky_jetstream_observations as observations
    ),
    '[]'::jsonb
  ) as observation_rows
from ingest.bluesky_jetstream_checkpoints as checkpoints;

select ok(
  (select acquired and retry_at is null and start_cursor = 900
   from bluesky_recovery_begin),
  'only a held lease can begin with the stale non-null checkpoint cursor'
);
select is(
  (
    select count(*)::integer
    from ingest.recover_bluesky_cursor_too_old_job_v1(
      'be140000-0000-4000-8000-000000000001',
      'another-worker',
      1,
      900
    )
  ),
  0,
  'another worker cannot recover a lease it does not own'
);
select is(
  (
    select count(*)::integer
    from ingest.recover_bluesky_cursor_too_old_job_v1(
      'be140000-0000-4000-8000-000000000001',
      'bluesky-recovery-worker',
      2,
      900
    )
  ),
  0,
  'a stale lease generation cannot recover the current job lease'
);
select is(
  pg_temp.sqlstate_of($sql$
    select * from ingest.recover_bluesky_cursor_too_old_job_v1(
      'be140000-0000-4000-8000-000000000001',
      'bluesky-recovery-worker',
      1,
      901
    )
  $sql$),
  '40001',
  'a recovery must compare the worker start cursor to the exact current checkpoint'
);
select ok(
  (select last_cursor = 900 from ingest.bluesky_jetstream_checkpoints)
  and (select status = 'running' from ingest.jobs
       where id = 'be140000-0000-4000-8000-000000000001')
  and (select owner_job_id = 'be140000-0000-4000-8000-000000000001'::uuid
       from ingest.source_request_gates where source_key = 'bluesky_jetstream'),
  'lost-worker and mismatched-cursor attempts are inert'
);
set local role service_role;
create temporary table bluesky_recovery_completed on commit drop as
select * from ingest.recover_bluesky_cursor_too_old_job_v1(
  'be140000-0000-4000-8000-000000000001',
  'bluesky-recovery-worker',
  1,
  900
);
reset role;
select is(
  (select count(*)::integer from bluesky_recovery_completed),
  1,
  'the service-role worker path clears only the exact stale cursor under its active lease'
);
select ok(
  (select status = 'completed'
      and locked_by is null
      and locked_at is null
      and lock_expires_at is null
   from ingest.jobs
   where id = 'be140000-0000-4000-8000-000000000001')
  and (select owner_job_id is null
       and owner_lease_generation is null
       and active_until is null
   from ingest.source_request_gates
   where source_key = 'bluesky_jetstream'),
  'successful recovery completes only its fenced job and releases its request gate'
);
select ok(
  (select checkpoints.last_cursor is null
      and checkpoints.last_collected_at = before.last_collected_at
      and checkpoints.events_seen_total = before.events_seen_total
      and checkpoints.bytes_seen_total = before.bytes_seen_total
      and checkpoints.candidates_seen_total = before.candidates_seen_total
      and checkpoints.deletions_seen_total = before.deletions_seen_total
   from ingest.bluesky_jetstream_checkpoints as checkpoints
   cross join bluesky_recovery_before as before)
  and (select count(*)::integer from ingest.bluesky_jetstream_candidates)
      = (select candidate_count from bluesky_recovery_before)
  and (select count(*)::integer from ingest.bluesky_jetstream_observations)
      = (select observation_count from bluesky_recovery_before)
  and (
    select jsonb_agg(to_jsonb(candidates) order by candidates.at_uri)
    from ingest.bluesky_jetstream_candidates as candidates
  ) = (select candidate_rows from bluesky_recovery_before)
  and (
    select jsonb_agg(to_jsonb(observations) order by observations.cursor)
    from ingest.bluesky_jetstream_observations as observations
  ) = (select observation_rows from bluesky_recovery_before)
  and (
    select policies.last_success_at is not distinct from before.last_success_at
    from ingest.source_policies as policies
    cross join bluesky_recovery_before as before
    where policies.source_key = 'bluesky_jetstream'
  ),
  'recovery clears only the checkpoint cursor and preserves health counters and private activity rows'
);
select ok(
  1 = (
    select count(*)::integer
    from ingest.admin_audit_log as audit
    where audit.action = 'bluesky.cursor_reset'
      and audit.object_type = 'ingest.bluesky_jetstream_checkpoints'
      and audit.object_id = 'bluesky_jetstream'
      and audit.detail = jsonb_build_object(
        'automatic', true,
        'reason', 'jetstream_cursor_too_old',
        'resume_mode', 'fresh_only',
        'previous_cursor_present', true,
        'preserved_counters', true,
        'preserved_activity_rows', true
      )
      and not audit.is_demo
  )
  and not exists (
    select 1
    from ingest.admin_audit_log as audit
    where audit.action = 'bluesky.cursor_reset'
      and audit.detail ? 'previous_cursor'
  ),
  'recovery writes one redacted audit record without the prior cursor value'
);
select ok(
  not has_table_privilege(
    'service_role',
    'ingest.bluesky_jetstream_checkpoints',
    'UPDATE'
  )
  and not has_table_privilege(
    'service_role',
    'ingest.bluesky_jetstream_checkpoints',
    'INSERT'
  )
  and not has_table_privilege(
    'service_role',
    'ingest.bluesky_jetstream_checkpoints',
    'DELETE'
  ),
  'service_role still cannot mutate the checkpoint directly'
);

select * from finish();
rollback;
