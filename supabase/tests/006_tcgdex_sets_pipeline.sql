-- Durable TCGdex sets scheduling, preflight, and fenced finalization contract.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select plan(121);

create temporary table tcgdex_test_times on commit drop as
select
  date_trunc('minute', clock_timestamp()) - interval '30 minutes' as slot_contract,
  date_trunc('minute', clock_timestamp()) - interval '29 minutes' as legacy_slot,
  date_trunc('minute', clock_timestamp()) - interval '20 minutes' as first_sync,
  date_trunc('minute', clock_timestamp()) - interval '19 minutes' as concurrent_sync,
  date_trunc('minute', clock_timestamp()) - interval '10 minutes' as unchanged_sync,
  date_trunc('minute', clock_timestamp()) - interval '9 minutes' as not_modified_sync,
  date_trunc('minute', clock_timestamp()) - interval '8 minutes' as changed_again_sync,
  date_trunc('minute', clock_timestamp()) - interval '7 minutes' as stale_base_sync;

select has_table('catalog', 'sync_state', 'catalog sync checkpoints exist');
select has_table('ingest', 'schedule_slots', 'durable schedule slots exist');
select has_table('ingest', 'source_request_gates', 'durable source request gate exists');
select ok(
  (select pg_get_constraintdef(oid) ilike '%unique (slug, is_demo)%'
   from pg_constraint
   where conrelid = 'catalog.sets'::regclass
     and conname = 'sets_slug_mode_unique'),
  'set slugs are unique inside each data mode'
);
select ok(
  (select pg_get_constraintdef(oid)
      ilike '%unique (external_source, external_id, language, is_demo)%'
   from pg_constraint
   where conrelid = 'catalog.sets'::regclass
     and conname = 'sets_external_identity_unique'),
  'set external identities are unique inside each data mode'
);
select ok(
  (select enabled
      and not is_demo
      and display_name = 'TCGdex Catalog API'
      and source_kind = 'official_api'
      and domain = 'api.tcgdex.net'
      and base_url = 'https://api.tcgdex.net/v2'
      and collector_type = 'official_api'
      and access_mode = 'official_api'
      and robots_policy = 'not_applicable'
      and routes = array['official_api']::text[]
      and not include_subdomains
      and min_delay_seconds = 10
      and max_pages_per_run = 1
      and max_items_per_run = 1000
      and max_concurrency = 1
      and browser_profile is null
      and not statistics_eligible_default
      and retention_days = 365
      and config = '{"scope":"sets","metadata_only":true}'::jsonb
      and version = 'tcgdex-sets-v1'
      and expected_interval_seconds = 86400
   from ingest.source_policies
   where source_key = 'tcgdex_catalog'),
  'the exact owner-approved live TCGdex policy is provisioned'
);
select ok(
  (select relrowsecurity and relforcerowsecurity
   from pg_class where oid = 'catalog.sync_state'::regclass),
  'sync state forces RLS'
);
select ok(has_table_privilege('service_role', 'catalog.sync_state', 'select'), 'service_role can read sync checkpoints');
select ok(not has_table_privilege('anon', 'catalog.sync_state', 'select'), 'anon cannot read sync checkpoints');
select ok(not has_table_privilege('service_role', 'catalog.sync_state', 'insert'), 'service_role cannot write sync checkpoints directly');
select ok(has_table_privilege('service_role', 'ingest.schedule_slots', 'select'), 'service_role can inspect schedule slots');
select ok(not has_table_privilege('service_role', 'ingest.schedule_slots', 'insert'), 'service_role cannot reserve slots directly');
select ok(
  (select relrowsecurity and relforcerowsecurity
   from pg_class where oid = 'ingest.source_request_gates'::regclass),
  'source request gate forces RLS'
);
select ok(
  not has_table_privilege('service_role', 'ingest.source_request_gates', 'select')
    and not has_table_privilege('service_role', 'ingest.source_request_gates', 'insert')
    and not has_table_privilege('service_role', 'ingest.source_request_gates', 'update')
    and not has_table_privilege('service_role', 'ingest.source_request_gates', 'delete'),
  'service_role has no direct source request gate privileges'
);
select ok(
  (select owner_job_id is null
      and owner_lease_generation is null
      and acquired_at is null
      and active_until is null
   from ingest.source_request_gates where source_key = 'tcgdex_catalog'),
  'the singleton TCGdex request gate starts unowned'
);

select has_function(
  'ingest', 'enqueue_scheduled_job_v1',
  array['text', 'timestamp with time zone', 'text', 'jsonb', 'integer', 'integer'],
  'durable scheduled enqueue exists'
);
select ok(
  (select prosecdef from pg_proc
   where oid = 'ingest.enqueue_scheduled_job_v1(text,timestamptz,text,jsonb,integer,integer)'::regprocedure),
  'scheduled enqueue is SECURITY DEFINER'
);
select ok(has_function_privilege('service_role', 'ingest.enqueue_scheduled_job_v1(text,timestamptz,text,jsonb,integer,integer)', 'execute'), 'service_role can enqueue a scheduled job');
select ok(not has_function_privilege('anon', 'ingest.enqueue_scheduled_job_v1(text,timestamptz,text,jsonb,integer,integer)', 'execute'), 'anon cannot enqueue scheduled jobs');

select has_function('ingest', 'begin_tcgdex_sets_job', array['uuid', 'text', 'bigint'], 'TCGdex pre-network gate exists');
select ok(
  (select prosecdef from pg_proc
   where oid = 'ingest.begin_tcgdex_sets_job(uuid,text,bigint)'::regprocedure),
  'TCGdex begin is SECURITY DEFINER'
);
select ok(has_function_privilege('service_role', 'ingest.begin_tcgdex_sets_job(uuid,text,bigint)', 'execute'), 'service_role can begin a TCGdex job');
select ok(not has_function_privilege('anon', 'ingest.begin_tcgdex_sets_job(uuid,text,bigint)', 'execute'), 'anon cannot begin a TCGdex job');

select has_function(
  'ingest', 'heartbeat_job_v2', array['uuid', 'text', 'bigint', 'integer'],
  'generation-fenced heartbeat RPC exists'
);
select ok(
  (select prosecdef from pg_proc
   where oid = 'ingest.heartbeat_job_v2(uuid,text,bigint,integer)'::regprocedure),
  'generation-fenced heartbeat is SECURITY DEFINER'
);
select ok(
  has_function_privilege(
    'service_role', 'ingest.heartbeat_job_v2(uuid,text,bigint,integer)', 'execute'
  ) and not has_function_privilege(
    'anon', 'ingest.heartbeat_job_v2(uuid,text,bigint,integer)', 'execute'
  ),
  'only the service boundary can execute the heartbeat RPC'
);

select has_function(
  'ingest', 'fail_job_v2',
  array['uuid', 'text', 'bigint', 'text', 'text', 'boolean'],
  'generation-fenced failure RPC exists'
);
select ok(
  (select prosecdef from pg_proc
   where oid = 'ingest.fail_job_v2(uuid,text,bigint,text,text,boolean)'::regprocedure),
  'generation-fenced failure is SECURITY DEFINER'
);
select ok(
  has_function_privilege(
    'service_role', 'ingest.fail_job_v2(uuid,text,bigint,text,text,boolean)', 'execute'
  ) and not has_function_privilege(
    'anon', 'ingest.fail_job_v2(uuid,text,bigint,text,text,boolean)', 'execute'
  ),
  'only the service boundary can execute the failure RPC'
);

select has_function('ingest', 'finalize_tcgdex_sets_job', array['uuid', 'text', 'bigint', 'jsonb'], 'typed TCGdex finalizer exists');
select ok(
  (select prosecdef from pg_proc
   where oid = 'ingest.finalize_tcgdex_sets_job(uuid,text,bigint,jsonb)'::regprocedure),
  'TCGdex finalizer is SECURITY DEFINER'
);
select ok(
  (select proretset and prorettype = 'ingest.jobs'::regtype
   from pg_proc
   where oid = 'ingest.finalize_tcgdex_sets_job(uuid,text,bigint,jsonb)'::regprocedure),
  'TCGdex finalizer returns the completed job row'
);
select ok(has_function_privilege('service_role', 'ingest.finalize_tcgdex_sets_job(uuid,text,bigint,jsonb)', 'execute'), 'service_role can finalize TCGdex jobs');
select ok(not has_function_privilege('anon', 'ingest.finalize_tcgdex_sets_job(uuid,text,bigint,jsonb)', 'execute'), 'anon cannot finalize TCGdex jobs');
select ok(
  not exists (
    select 1
    from pg_proc p
    cross join lateral aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) acl
    where p.oid = 'ingest.finalize_tcgdex_sets_job(uuid,text,bigint,jsonb)'::regprocedure
      and acl.grantee = 0
      and acl.privilege_type = 'EXECUTE'
  ),
  'PUBLIC cannot finalize TCGdex jobs'
);

select throws_ok(
  $$select * from ingest.enqueue_scheduled_job_v1('Bad Name', date_trunc('minute', clock_timestamp()), 'test.job')$$,
  '22023', 'schedule_name must use the canonical job-name format',
  'invalid schedule names are rejected'
);
select throws_ok(
  $$select * from ingest.enqueue_scheduled_job_v1('valid-name', date_trunc('minute', clock_timestamp()) + interval '1 second', 'test.job')$$,
  '22023', 'scheduled_for must be an exact UTC minute',
  'schedule slots must be exact minutes'
);
select throws_ok(
  $$select * from ingest.enqueue_scheduled_job_v1('too-old', date_trunc('minute', clock_timestamp()) - interval '37 hours', 'test.job')$$,
  '22023', 'scheduled_for must be within 36 hours past and 5 minutes future',
  'schedule catch-up is bounded to 36 hours'
);
select throws_ok(
  $$select * from ingest.enqueue_scheduled_job_v1('too-new', date_trunc('minute', clock_timestamp()) + interval '6 minutes', 'test.job')$$,
  '22023', 'scheduled_for must be within 36 hours past and 5 minutes future',
  'future scheduling is bounded to five minutes'
);
select throws_ok(
  $$select * from ingest.enqueue_scheduled_job_v1('bad-payload', date_trunc('minute', clock_timestamp()), 'test.job', '[]'::jsonb)$$,
  '22023', 'payload must be a JSON object no larger than 32768 bytes',
  'scheduled payloads must be bounded objects'
);

create temporary table legacy_schedule_job on commit drop as
select gen_random_uuid() as id;
insert into ingest.jobs (
  id, job_type, payload, status, priority, attempts, max_attempts,
  available_at, completed_at, dedupe_key, is_demo
)
select
  id,
  'legacy.slot',
  '{}'::jsonb,
  'completed',
  0,
  1,
  5,
  (select legacy_slot from tcgdex_test_times),
  clock_timestamp(),
  'schedule:legacy-slot:' || to_char(
    (select legacy_slot from tcgdex_test_times) at time zone 'UTC',
    'YYYYMMDD"T"HH24MISS"Z"'
  ),
  false
from legacy_schedule_job;

create temporary table adopted_legacy_job on commit drop as
select * from ingest.enqueue_scheduled_job_v1(
  'legacy-slot',
  (select legacy_slot from tcgdex_test_times),
  'legacy.slot'
);
select is(
  (select id from adopted_legacy_job),
  (select id from legacy_schedule_job),
  'a canonical pre-slot scheduler job is adopted instead of duplicated'
);
select is(
  (select job_id from ingest.schedule_slots
   where schedule_name = 'legacy-slot'
     and slot_at = (select legacy_slot from tcgdex_test_times)),
  (select id from legacy_schedule_job),
  'runtime reconciliation backfills the legacy durable slot identity'
);
select is(
  (select count(*)::integer from ingest.jobs
   where dedupe_key like 'schedule:legacy-slot:%'),
  1,
  'legacy slot adoption inserts no replacement job'
);

create temporary table first_slot_job on commit drop as
select * from ingest.enqueue_scheduled_job_v1(
  schedule_name => 'slot-contract',
  scheduled_for => (select slot_contract from tcgdex_test_times),
  job_type => 'slot.contract',
  payload => '{"bounded":true}',
  priority => 7,
  max_attempts => 3
);
select is((select count(*)::integer from first_slot_job), 1, 'first slot reservation returns one job');
select ok(
  (select status = 'pending'
      and not is_demo
      and priority = 7
      and max_attempts = 3
      and dedupe_key ~ '^schedule:slot-contract:[0-9]{8}T[0-9]{6}Z$'
   from first_slot_job),
  'scheduled job is live, bounded, and uses the canonical UTC dedupe key'
);
select is((select count(*)::integer from ingest.schedule_slots where schedule_name = 'slot-contract'), 1, 'exactly one slot is persisted');

create temporary table repeated_slot_job on commit drop as
select * from ingest.enqueue_scheduled_job_v1(
  'slot-contract',
  (select slot_contract from tcgdex_test_times),
  'slot.contract',
  '{"ignored":true}',
  99,
  9
);
select is((select id from repeated_slot_job), (select id from first_slot_job), 'repeating a slot returns its original job');
select is((select count(*)::integer from ingest.jobs where job_type = 'slot.contract'), 1, 'repeating a slot never inserts a second job');

update ingest.jobs
set status = 'completed', completed_at = clock_timestamp()
where id = (select id from first_slot_job);
create temporary table completed_slot_job on commit drop as
select * from ingest.enqueue_scheduled_job_v1(
  'slot-contract',
  (select slot_contract from tcgdex_test_times),
  'slot.contract'
);
select is((select status from completed_slot_job), 'completed', 'a completed slot returns the original completed job');
select is((select id from completed_slot_job), (select id from first_slot_job), 'completed slot identity is immutable');
select is((select count(*)::integer from ingest.jobs where job_type = 'slot.contract'), 1, 'completed active-dedupe release cannot duplicate a durable slot');

create temporary table tcgdex_job on commit drop as
select * from ingest.enqueue_scheduled_job_v1(
  'tcgdex-sets-test',
  (select first_sync from tcgdex_test_times),
  'catalog.tcgdex.sets.sync',
  '{}'::jsonb,
  20,
  5
);
select is((select count(*)::integer from tcgdex_job), 1, 'TCGdex scheduled job is created once');
create temporary table tcgdex_claim_one on commit drop as
select * from ingest.claim_jobs_v2('tcgdex-worker', array['catalog.tcgdex.sets.sync'], 1, 600);
select is((select count(*)::integer from tcgdex_claim_one), 1, 'TCGdex worker claims the scheduled job');
update ingest.jobs
set lock_expires_at = clock_timestamp() + interval '5 seconds'
where id = (select id from tcgdex_claim_one);

create temporary table empty_checkpoint on commit drop as
select * from ingest.begin_tcgdex_sets_job(
  (select id from tcgdex_claim_one), 'tcgdex-worker', 1
);
select ok(
  (select count(*) = 1 and bool_and(acquired) and max(retry_at) is null
      and max(etag) is null and max(content_sha256) is null
      and max(item_count) = 0 and max(revision) = 0
   from empty_checkpoint),
  'a valid first begin returns one empty checkpoint row'
);
select ok(
  (select last_attempt_at is not null and last_success_at is null
   from ingest.source_policies where source_key = 'tcgdex_catalog'),
  'begin records only the policy attempt timestamp'
);
select ok(
  (select gates.owner_job_id = jobs.id
      and gates.owner_lease_generation = jobs.lease_generation
      and gates.active_until = jobs.lock_expires_at
      and gates.active_until >= gates.acquired_at + interval '45 seconds'
   from ingest.source_request_gates gates
   join ingest.jobs jobs on jobs.id = gates.owner_job_id
   where gates.source_key = 'tcgdex_catalog'),
  'begin atomically renews a short lease and persists the matching request owner'
);

create temporary table concurrent_job on commit drop as
select * from ingest.enqueue_scheduled_job_v1(
  'tcgdex-sets-concurrent',
  (select concurrent_sync from tcgdex_test_times),
  'catalog.tcgdex.sets.sync'
);
select is((select count(*)::integer from concurrent_job), 1, 'a concurrent TCGdex job is scheduled');
create temporary table concurrent_claim on commit drop as
select * from ingest.claim_jobs_v2('tcgdex-worker-2', array['catalog.tcgdex.sets.sync'], 1, 600);
select is((select count(*)::integer from concurrent_claim), 1, 'a second worker can claim another TCGdex job');
create temporary table busy_checkpoint on commit drop as
select * from ingest.begin_tcgdex_sets_job(
  (select id from concurrent_claim), 'tcgdex-worker-2', 1
);
select ok(
  (select count(*) = 1 and bool_and(not acquired) and min(retry_at) is not null
      and max(etag) is null and max(content_sha256) is null
      and max(item_count) = 0 and max(revision) = 0
   from busy_checkpoint),
  'an owned durable gate returns structured deferral to another worker'
);
select is(
  (select owner_job_id from ingest.source_request_gates
   where source_key = 'tcgdex_catalog'),
  (select id from tcgdex_claim_one),
  'a busy preflight cannot replace the active request owner'
);

update ingest.jobs
set locked_at = clock_timestamp() - interval '2 minutes',
    lock_expires_at = clock_timestamp() - interval '1 minute'
where id = (select id from tcgdex_claim_one);
update ingest.source_request_gates
set acquired_at = clock_timestamp() - interval '2 minutes',
    active_until = clock_timestamp() - interval '1 minute'
where source_key = 'tcgdex_catalog';
select is(
  (select count(*)::integer from ingest.finalize_tcgdex_sets_job(
    (select id from tcgdex_claim_one), 'tcgdex-worker', 1,
    jsonb_build_object(
      'version', 1, 'expected_revision', 0,
      'outcome', 'changed', 'etag', '"v1"',
      'content_sha256', repeat('a', 64),
      'sets', jsonb_build_array(jsonb_build_object(
        'id', 'sv2', 'name', 'Paldea Evolved',
        'card_count_total', 279, 'card_count_official', 193
      ))
    )
  )),
  0,
  'expired lease performs no TCGdex finalization'
);
select is((select count(*)::integer from catalog.sets where external_source = 'tcgdex'), 0, 'expired finalization persists no sets');

create temporary table rate_limited_checkpoint on commit drop as
select * from ingest.begin_tcgdex_sets_job(
  (select id from concurrent_claim), 'tcgdex-worker-2', 1
);
select ok(
  (select count(*) = 1 and bool_and(not acquired) and min(retry_at) is not null
   from rate_limited_checkpoint),
  'global request spacing returns a structured deferral after gate expiry'
);
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '11 seconds'
where source_key = 'tcgdex_catalog';
create temporary table concurrent_checkpoint on commit drop as
select * from ingest.begin_tcgdex_sets_job(
  (select id from concurrent_claim), 'tcgdex-worker-2', 1
);
select ok(
  (select count(*) = 1 and bool_and(acquired) and max(retry_at) is null
      and max(revision) = 0
   from concurrent_checkpoint),
  'a globally serialized request begins after the ten-second boundary'
);

-- Reproduce the former visibility race deterministically: although this job's
-- locked_at sorts before the current owner, the persisted gate must still win.
update ingest.jobs
set locked_at = (select locked_at from ingest.jobs
                 where id = (select id from concurrent_claim)) - interval '1 minute',
    lock_expires_at = clock_timestamp() + interval '1 minute'
where id = (select id from tcgdex_claim_one);
create temporary table older_claim_deferred on commit drop as
select * from ingest.begin_tcgdex_sets_job(
  (select id from tcgdex_claim_one), 'tcgdex-worker', 1
);
select ok(
  (select count(*) = 1 and bool_and(not acquired) and min(retry_at) is not null
   from older_claim_deferred),
  'an older locked_at caller cannot displace the persisted request owner'
);

select is(
  (select count(*)::integer from ingest.fail_job_v2(
    (select id from concurrent_claim),
    'tcgdex-worker-2',
    2,
    'stale_failure',
    'stale generation must not release the request gate',
    false
  )),
  0,
  'a stale failure generation cannot transition the job'
);
select is(
  (select owner_job_id from ingest.source_request_gates
   where source_key = 'tcgdex_catalog'),
  (select id from concurrent_claim),
  'a stale failure generation cannot release the request gate'
);
create temporary table failed_concurrent_job on commit drop as
select * from ingest.fail_job_v2(
  (select id from concurrent_claim),
  'tcgdex-worker-2',
  1,
  'forced_test_failure',
  'bounded test failure',
  false
);
select is(
  (select status from failed_concurrent_job),
  'dead',
  'a current nonretryable failure dead-letters the fenced job'
);
select ok(
  (select owner_job_id is null and owner_lease_generation is null
      and acquired_at is null and active_until is null
   from ingest.source_request_gates where source_key = 'tcgdex_catalog'),
  'a current failure releases its request gate atomically'
);

update ingest.jobs
set locked_at = clock_timestamp() - interval '2 minutes',
    lock_expires_at = clock_timestamp() - interval '1 minute'
where id = (select id from tcgdex_claim_one);
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '11 seconds'
where source_key = 'tcgdex_catalog';

create temporary table tcgdex_claim_two on commit drop as
select * from ingest.claim_jobs_v2('tcgdex-worker', array['catalog.tcgdex.sets.sync'], 1, 600);
select is((select lease_generation from tcgdex_claim_two), 2::bigint, 'reclaim rotates the TCGdex lease generation');
select is(
  (select count(*)::integer from ingest.finalize_tcgdex_sets_job(
    (select id from tcgdex_claim_two), 'tcgdex-worker', 1,
    jsonb_build_object(
      'version', 1, 'expected_revision', 0,
      'outcome', 'changed', 'etag', '"v1"',
      'content_sha256', repeat('a', 64),
      'sets', jsonb_build_array(jsonb_build_object(
        'id', 'sv2', 'name', 'Paldea Evolved',
        'card_count_total', 279, 'card_count_official', 193
      ))
    )
  )),
  0,
  'stale generation performs no TCGdex finalization'
);
select is((select count(*)::integer from catalog.sets where external_source = 'tcgdex'), 0, 'stale generation persists no sets');

create temporary table reclaimed_checkpoint on commit drop as
select * from ingest.begin_tcgdex_sets_job(
  (select id from tcgdex_claim_two), 'tcgdex-worker', 2
);
select ok(
  (select count(*) = 1 and bool_and(acquired) and max(retry_at) is null
      and max(etag) is null and max(content_sha256) is null
      and max(item_count) = 0 and max(revision) = 0
   from reclaimed_checkpoint),
  'current reclaimed lease can begin with an empty checkpoint'
);
select is(
  (select count(*)::integer from ingest.heartbeat_job_v2(
    (select id from tcgdex_claim_two), 'tcgdex-worker', 1, 600
  )),
  0,
  'a stale heartbeat generation cannot renew the job or gate'
);
create temporary table renewed_tcgdex_job on commit drop as
select * from ingest.heartbeat_job_v2(
  (select id from tcgdex_claim_two), 'tcgdex-worker', 2, 600
);
select is(
  (select count(*)::integer from renewed_tcgdex_job),
  1,
  'the current generation can renew its job lease'
);
select ok(
  (select gates.owner_job_id = jobs.id
      and gates.owner_lease_generation = jobs.lease_generation
      and gates.active_until = jobs.lock_expires_at
   from ingest.source_request_gates gates
   join ingest.jobs jobs on jobs.id = gates.owner_job_id
   where gates.source_key = 'tcgdex_catalog'),
  'heartbeat atomically keeps the request gate expiry aligned to the job lease'
);

update ingest.source_policies set enabled = false where source_key = 'tcgdex_catalog';
select throws_ok(
  format(
    $$select * from ingest.begin_tcgdex_sets_job(%L::uuid, 'tcgdex-worker', 2)$$,
    (select id from tcgdex_claim_two)
  ),
  '55000', 'live TCGdex catalog source policy is unavailable or disabled',
  'disabled policy blocks network preflight'
);
select throws_ok(
  format(
    $$select * from ingest.finalize_tcgdex_sets_job(%L::uuid, 'tcgdex-worker', 2, %L::jsonb)$$,
    (select id from tcgdex_claim_two),
    jsonb_build_object(
      'version', 1, 'expected_revision', 0,
      'outcome', 'changed', 'etag', '"v1"',
      'content_sha256', repeat('a', 64),
      'sets', jsonb_build_array(jsonb_build_object(
        'id', 'sv2', 'name', 'Paldea Evolved',
        'card_count_total', 279, 'card_count_official', 193
      ))
    )::text
  ),
  '55000', 'live TCGdex catalog source policy is unavailable or disabled',
  'kill switch during GET blocks persistence'
);
select is((select count(*)::integer from catalog.sets where external_source = 'tcgdex'), 0, 'kill switch leaves catalog unchanged');
update ingest.source_policies set enabled = true where source_key = 'tcgdex_catalog';

update ingest.source_policies
set base_url = 'https://api.tcgdex.net/v2/'
where source_key = 'tcgdex_catalog';
select throws_ok(
  format(
    $$select * from ingest.begin_tcgdex_sets_job(%L::uuid, 'tcgdex-worker', 2)$$,
    (select id from tcgdex_claim_two)
  ),
  '55000', 'live TCGdex catalog source policy is unavailable or disabled',
  'a mutation to any fixed policy field blocks preflight'
);
select throws_ok(
  format(
    $$select * from ingest.finalize_tcgdex_sets_job(%L::uuid, 'tcgdex-worker', 2, %L::jsonb)$$,
    (select id from tcgdex_claim_two),
    jsonb_build_object(
      'version', 1, 'expected_revision', 0,
      'outcome', 'changed', 'etag', '"v1"',
      'content_sha256', repeat('a', 64),
      'sets', jsonb_build_array(jsonb_build_object(
        'id', 'sv2', 'name', 'Paldea Evolved',
        'card_count_total', 279, 'card_count_official', 193
      ))
    )::text
  ),
  '55000', 'live TCGdex catalog source policy is unavailable or disabled',
  'a fixed policy mutation during GET blocks finalization'
);
update ingest.source_policies
set base_url = 'https://api.tcgdex.net/v2'
where source_key = 'tcgdex_catalog';

update ingest.source_request_gates
set owner_lease_generation = 3
where source_key = 'tcgdex_catalog';
select throws_ok(
  format(
    $$select * from ingest.finalize_tcgdex_sets_job(%L::uuid, 'tcgdex-worker', 2, %L::jsonb)$$,
    (select id from tcgdex_claim_two),
    jsonb_build_object(
      'version', 1, 'expected_revision', 0,
      'outcome', 'changed', 'etag', '"v1"',
      'content_sha256', repeat('a', 64),
      'sets', jsonb_build_array(jsonb_build_object(
        'id', 'sv2', 'name', 'Paldea Evolved',
        'card_count_total', 279, 'card_count_official', 193
      ))
    )::text
  ),
  '55000', 'TCGdex request gate is not owned by this job lease',
  'finalization rejects a request gate owned by another generation'
);
update ingest.source_request_gates
set owner_lease_generation = 2
where source_key = 'tcgdex_catalog';

select throws_ok(
  format(
    $$select * from ingest.finalize_tcgdex_sets_job(%L::uuid, 'tcgdex-worker', 2, %L::jsonb)$$,
    (select id from tcgdex_claim_two),
    jsonb_build_object(
      'version', 1, 'expected_revision', 0,
      'outcome', 'changed', 'etag', '"v1"',
      'content_sha256', repeat('a', 64), 'sets', '[]'::jsonb
    )::text
  ),
  '22023',
  'changed TCGdex results require 1 to 1000 sets and other outcomes require none',
  'changed result cannot be empty'
);

select throws_ok(
  format(
    $$select * from ingest.finalize_tcgdex_sets_job(%L::uuid, 'tcgdex-worker', 2, %L::jsonb)$$,
    (select id from tcgdex_claim_two),
    jsonb_build_object(
      'version', 1, 'expected_revision', 0,
      'outcome', 'changed', 'etag', E'"v1\n"',
      'content_sha256', repeat('a', 64),
      'sets', jsonb_build_array(jsonb_build_object(
        'id', 'sv2', 'name', 'Paldea Evolved',
        'card_count_total', 279, 'card_count_official', 193
      ))
    )::text
  ),
  '22023', 'TCGdex result must match the exact bounded v1 contract',
  'ETags containing control characters are rejected'
);
select throws_ok(
  format(
    $$select * from ingest.finalize_tcgdex_sets_job(%L::uuid, 'tcgdex-worker', 2, %L::jsonb)$$,
    (select id from tcgdex_claim_two),
    jsonb_build_object(
      'version', 1, 'expected_revision', 0,
      'outcome', 'changed', 'etag', '"ÿ"',
      'content_sha256', repeat('a', 64),
      'sets', jsonb_build_array(jsonb_build_object(
        'id', 'sv2', 'name', 'Paldea Evolved',
        'card_count_total', 279, 'card_count_official', 193
      ))
    )::text
  ),
  '22023', 'TCGdex result must match the exact bounded v1 contract',
  'ETags must use a replay-safe ASCII entity-tag syntax'
);
select throws_ok(
  format(
    $$select * from ingest.finalize_tcgdex_sets_job(%L::uuid, 'tcgdex-worker', 2, %L::jsonb)$$,
    (select id from tcgdex_claim_two),
    jsonb_build_object(
      'version', 1, 'expected_revision', 0,
      'outcome', 'changed', 'etag', '"v1"',
      'content_sha256', repeat('a', 64),
      'sets', jsonb_build_array(jsonb_build_object(
        'id', 'sv2', 'name', E'Paldea\nEvolved',
        'card_count_total', 279, 'card_count_official', 193
      ))
    )::text
  ),
  '22023', 'TCGdex sets must use the exact bounded v1 set contract',
  'set ids and names reject control characters'
);
select throws_ok(
  format(
    $$select * from ingest.finalize_tcgdex_sets_job(%L::uuid, 'tcgdex-worker', 2, %L::jsonb)$$,
    (select id from tcgdex_claim_two),
    jsonb_build_object(
      'version', 1, 'expected_revision', 0,
      'outcome', 'changed', 'etag', '"v1"',
      'content_sha256', repeat('a', 64),
      'sets', jsonb_build_array(jsonb_build_object(
        'id', 'sv2', 'name', 'Paldea Evolved',
        'card_count_total', '279', 'card_count_official', 193
      ))
    )::text
  ),
  '22023', 'TCGdex sets must use the exact bounded v1 set contract',
  'wrongly typed numeric fields fail with the contract error'
);

create function pg_temp.reject_tcgdex_completion()
returns trigger language plpgsql as $$
begin
  if new.job_type = 'catalog.tcgdex.sets.sync' and new.status = 'completed' then
    raise exception using errcode = 'P0001', message = 'forced TCGdex completion failure';
  end if;
  return new;
end;
$$;
create trigger reject_tcgdex_completion
before update on ingest.jobs
for each row execute function pg_temp.reject_tcgdex_completion();

select throws_ok(
  format(
    $$select * from ingest.finalize_tcgdex_sets_job(%L::uuid, 'tcgdex-worker', 2, %L::jsonb)$$,
    (select id from tcgdex_claim_two),
    jsonb_build_object(
      'version', 1, 'expected_revision', 0,
      'outcome', 'changed', 'etag', '"v1"',
      'content_sha256', repeat('a', 64),
      'sets', jsonb_build_array(
        jsonb_build_object('id', 'sv2', 'name', 'Paldea Evolved', 'card_count_total', 279, 'card_count_official', 193),
        jsonb_build_object('id', 'sv3', 'name', 'Obsidian Flames', 'card_count_total', 230, 'card_count_official', 197)
      )
    )::text
  ),
  'P0001', 'forced TCGdex completion failure',
  'completion failure aborts the atomic TCGdex finalizer'
);
select is((select count(*)::integer from catalog.sets where external_source = 'tcgdex'), 0, 'catalog writes roll back with completion failure');
select is((select count(*)::integer from catalog.sync_state where source = 'tcgdex'), 0, 'checkpoint writes roll back with completion failure');
select is((select status from ingest.jobs where id = (select id from tcgdex_claim_two)), 'running', 'job completion rolls back with catalog writes');
select ok(
  (select owner_job_id = (select id from tcgdex_claim_two)
      and owner_lease_generation = 2
   from ingest.source_request_gates where source_key = 'tcgdex_catalog'),
  'a rolled-back completion cannot release the request gate'
);
drop trigger reject_tcgdex_completion on ingest.jobs;

insert into catalog.sets (
  external_source, external_id, name, slug, language, metadata, is_demo
) values (
  'tcgdex', 'sv2', 'Synthetic collision',
  'tcgdex-sv2-' || left(encode(extensions.digest(convert_to('sv2', 'UTF8'), 'sha256'), 'hex'), 16),
  'en', '{"synthetic":true}', true
);

create temporary table finalized_tcgdex_job on commit drop as
select * from ingest.finalize_tcgdex_sets_job(
  (select id from tcgdex_claim_two),
  'tcgdex-worker',
  2,
  jsonb_build_object(
    'version', 1,
    'expected_revision', 0,
    'outcome', 'changed',
    'etag', '"v1"',
    'content_sha256', repeat('a', 64),
    'sets', jsonb_build_array(
      jsonb_build_object('id', 'sv2', 'name', 'Paldea Evolved', 'card_count_total', 279, 'card_count_official', 193),
      jsonb_build_object('id', 'sv3', 'name', 'Obsidian Flames', 'card_count_total', 230, 'card_count_official', 197)
    )
  )
);
select is((select count(*)::integer from finalized_tcgdex_job), 1, 'valid TCGdex finalization returns one job');
select ok((select status = 'completed' and lease_generation = 2 from finalized_tcgdex_job), 'valid finalization completes the fenced job');
select is((select count(*)::integer from catalog.sets where external_source = 'tcgdex' and not is_demo), 2, 'valid finalization upserts every live set');
select is((select count(*)::integer from catalog.sets where external_source = 'tcgdex' and is_demo), 1, 'mode-scoped identity preserves the colliding demo set');
select is(
  (select metadata -> 'cardCount' from catalog.sets
   where external_source = 'tcgdex' and external_id = 'sv2' and not is_demo),
  '{"total":279,"official":193}'::jsonb,
  'TCGdex cardCount metadata is persisted exactly'
);
select ok(
  (select bool_and(char_length(slug) <= 160 and slug ~ '^[a-z0-9][a-z0-9-]*[a-z0-9]$')
   from catalog.sets where external_source = 'tcgdex'),
  'TCGdex slugs are deterministic and bounded by the catalog contract'
);
select ok(
  (select etag = '"v1"'
      and content_sha256 = repeat('a', 64)
      and item_count = 2
      and revision = 1
      and not is_demo
      and last_job_id = (select id from tcgdex_claim_two)
   from catalog.sync_state
   where source = 'tcgdex' and scope = 'sets' and language = 'en'),
  'changed result atomically writes the live checkpoint'
);
select ok(
  (select last_success_at is not null
      and (last_failure_at is null or last_failure_at <= last_success_at)
   from ingest.source_policies where source_key = 'tcgdex_catalog'),
  'successful finalization supersedes any earlier recorded request failure'
);
select ok(
  (select owner_job_id is null and owner_lease_generation is null
      and acquired_at is null and active_until is null
   from ingest.source_request_gates where source_key = 'tcgdex_catalog'),
  'successful finalization releases the request gate in the same transaction'
);
select is(
  (select count(*)::integer from ingest.finalize_tcgdex_sets_job(
    (select id from tcgdex_claim_two), 'tcgdex-worker', 2,
    '{"version":1,"expected_revision":1,"outcome":"not_modified","etag":"\"v1\"","content_sha256":"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa","sets":[]}'::jsonb
  )),
  0,
  'completed finalizer is idempotently fenced off'
);

create temporary table unchanged_job on commit drop as
select * from ingest.enqueue_scheduled_job_v1(
  'tcgdex-sets-unchanged',
  (select unchanged_sync from tcgdex_test_times),
  'catalog.tcgdex.sets.sync'
);
select is((select count(*)::integer from unchanged_job), 1, 'a later TCGdex slot creates one new job');
create temporary table unchanged_claim on commit drop as
select * from ingest.claim_jobs_v2('tcgdex-worker', array['catalog.tcgdex.sets.sync'], 1, 600);
select is((select count(*)::integer from unchanged_claim), 1, 'later TCGdex job can be claimed');
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '11 seconds'
where source_key = 'tcgdex_catalog';
create temporary table existing_checkpoint on commit drop as
select * from ingest.begin_tcgdex_sets_job((select id from unchanged_claim), 'tcgdex-worker', 1);
select ok(
  (select acquired and retry_at is null and etag = '"v1"'
      and content_sha256 = repeat('a', 64)
      and item_count = 2 and revision = 1
   from existing_checkpoint),
  'begin returns the exact persisted ETag/hash/count checkpoint'
);
create temporary table previous_change_time on commit drop as
select last_changed_at from catalog.sync_state
where source = 'tcgdex' and scope = 'sets' and language = 'en' and not is_demo;
select is(
  (select count(*)::integer from ingest.finalize_tcgdex_sets_job(
    (select id from unchanged_claim),
    'tcgdex-worker',
    1,
    jsonb_build_object(
      'version', 1, 'expected_revision', 1,
      'outcome', 'unchanged', 'etag', '"v2"',
      'content_sha256', repeat('a', 64), 'sets', '[]'::jsonb
    )
  )),
  1,
  'unchanged content can rotate only its ETag and complete'
);
select ok(
  (select states.etag = '"v2"'
      and states.item_count = 2
      and states.revision = 2
      and states.last_changed_at = previous.last_changed_at
   from catalog.sync_state states cross join previous_change_time previous
   where states.source = 'tcgdex' and states.scope = 'sets'
     and states.language = 'en' and not states.is_demo),
  'unchanged result preserves item count/change time while updating ETag'
);

create temporary table not_modified_job on commit drop as
select * from ingest.enqueue_scheduled_job_v1(
  'tcgdex-sets-not-modified',
  (select not_modified_sync from tcgdex_test_times),
  'catalog.tcgdex.sets.sync'
);
create temporary table not_modified_claim on commit drop as
select * from ingest.claim_jobs_v2('tcgdex-worker', array['catalog.tcgdex.sets.sync'], 1, 600);
select is((select count(*)::integer from not_modified_claim), 1, 'a 304-path TCGdex job can be claimed');
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '11 seconds'
where source_key = 'tcgdex_catalog';
create temporary table not_modified_checkpoint on commit drop as
select * from ingest.begin_tcgdex_sets_job(
  (select id from not_modified_claim), 'tcgdex-worker', 1
);
select ok(
  (select acquired and retry_at is null and revision = 2
   from not_modified_checkpoint),
  '304 work acquires the gate from checkpoint revision two'
);
select is(
  (select count(*)::integer from ingest.finalize_tcgdex_sets_job(
    (select id from not_modified_claim),
    'tcgdex-worker',
    1,
    jsonb_build_object(
      'version', 1, 'expected_revision', 2,
      'outcome', 'not_modified', 'etag', '"v2"',
      'content_sha256', repeat('a', 64), 'sets', '[]'::jsonb
    )
  )),
  1,
  'a real not_modified result completes successfully'
);
select ok(
  (select revision = 3 and etag = '"v2"' and content_sha256 = repeat('a', 64)
   from catalog.sync_state
   where source = 'tcgdex' and scope = 'sets' and language = 'en' and not is_demo),
  'successful 304 finalization advances only the checkpoint revision/check time'
);

create temporary table changed_again_job on commit drop as
select * from ingest.enqueue_scheduled_job_v1(
  'tcgdex-sets-changed-again',
  (select changed_again_sync from tcgdex_test_times),
  'catalog.tcgdex.sets.sync'
);
create temporary table changed_again_claim on commit drop as
select * from ingest.claim_jobs_v2('tcgdex-worker', array['catalog.tcgdex.sets.sync'], 1, 600);
select is((select count(*)::integer from changed_again_claim), 1, 'a later changed job can be claimed');
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '11 seconds'
where source_key = 'tcgdex_catalog';
create temporary table changed_again_checkpoint on commit drop as
select * from ingest.begin_tcgdex_sets_job(
  (select id from changed_again_claim), 'tcgdex-worker', 1
);
select ok(
  (select acquired and retry_at is null and revision = 3
   from changed_again_checkpoint),
  'later changed work acquires the gate from checkpoint revision three'
);
select throws_ok(
  format(
    $$select * from ingest.finalize_tcgdex_sets_job(%L::uuid, 'tcgdex-worker', 1, %L::jsonb)$$,
    (select id from changed_again_claim),
    jsonb_build_object(
      'version', 1, 'expected_revision', 3,
      'outcome', 'changed', 'etag', '"v3"',
      'content_sha256', repeat('a', 64),
      'sets', jsonb_build_array(jsonb_build_object(
        'id', 'sv2', 'name', 'Paldea Evolved',
        'card_count_total', 279, 'card_count_official', 193
      ))
    )::text
  ),
  '22023', 'changed TCGdex results require a new content hash',
  'changed cannot be used to replay the current checkpoint hash'
);
update catalog.sets
set is_active = false
where external_source = 'tcgdex' and external_id = 'sv2' and not is_demo;
select is(
  (select count(*)::integer from ingest.finalize_tcgdex_sets_job(
    (select id from changed_again_claim),
    'tcgdex-worker',
    1,
    jsonb_build_object(
      'version', 1, 'expected_revision', 3,
      'outcome', 'changed', 'etag', '"v3"',
      'content_sha256', repeat('b', 64),
      'sets', jsonb_build_array(
        jsonb_build_object('id', 'sv2', 'name', 'Paldea Evolved', 'card_count_total', 279, 'card_count_official', 193),
        jsonb_build_object('id', 'sv3', 'name', 'Obsidian Flames', 'card_count_total', 230, 'card_count_official', 197)
      )
    )
  )),
  1,
  'a genuinely changed result completes from its expected revision'
);
select ok(
  (select is_active from catalog.sets
   where external_source = 'tcgdex' and external_id = 'sv2' and not is_demo),
  'a returned upstream set is reactivated during upsert'
);
select ok(
  (select revision = 4 and content_sha256 = repeat('b', 64)
   from catalog.sync_state
   where source = 'tcgdex' and scope = 'sets' and language = 'en' and not is_demo),
  'changed persistence advances the checkpoint revision monotonically'
);

create temporary table stale_base_job on commit drop as
select * from ingest.enqueue_scheduled_job_v1(
  'tcgdex-sets-stale-base',
  (select stale_base_sync from tcgdex_test_times),
  'catalog.tcgdex.sets.sync'
);
create temporary table stale_base_claim on commit drop as
select * from ingest.claim_jobs_v2('tcgdex-worker', array['catalog.tcgdex.sets.sync'], 1, 600);
select is((select count(*)::integer from stale_base_claim), 1, 'a stale-base test job can be claimed');
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '11 seconds'
where source_key = 'tcgdex_catalog';
create temporary table stale_base_checkpoint on commit drop as
select * from ingest.begin_tcgdex_sets_job(
  (select id from stale_base_claim), 'tcgdex-worker', 1
);
select ok(
  (select acquired and retry_at is null and revision = 4
   from stale_base_checkpoint),
  'the stale-base job acquires the gate and observes revision four'
);
select throws_ok(
  format(
    $$select * from ingest.finalize_tcgdex_sets_job(%L::uuid, 'tcgdex-worker', 1, %L::jsonb)$$,
    (select id from stale_base_claim),
    jsonb_build_object(
      'version', 1, 'expected_revision', 3,
      'outcome', 'changed', 'etag', '"v4"',
      'content_sha256', repeat('c', 64),
      'sets', jsonb_build_array(jsonb_build_object(
        'id', 'sv2', 'name', 'Paldea Evolved',
        'card_count_total', 279, 'card_count_official', 193
      ))
    )::text
  ),
  '40001', 'TCGdex result was computed from a stale checkpoint revision',
  'checkpoint CAS rejects a response computed from an older base revision'
);
select ok(
  (select jobs.status = 'running' and states.revision = 4
      and gates.owner_job_id = jobs.id
      and gates.owner_lease_generation = jobs.lease_generation
   from ingest.jobs jobs
   cross join catalog.sync_state states
   cross join ingest.source_request_gates gates
   where jobs.id = (select id from stale_base_claim)
     and states.source = 'tcgdex' and states.scope = 'sets'
     and states.language = 'en' and not states.is_demo
     and gates.source_key = 'tcgdex_catalog'),
  'stale-base rejection leaves the job, checkpoint, and gate untouched'
);

select * from finish();
rollback;
