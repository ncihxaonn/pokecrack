-- Bounded multi-relay NIP-01 discovery: policy, fencing, replay, tombstones,
-- cleanup, and public redaction.
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

select has_table('ingest', 'nostr_relay_candidates',
  'private Nostr candidate ledger exists');
select has_table('ingest', 'nostr_relay_observations',
  'private per-relay Nostr observation ledger exists');
select has_table('ingest', 'nostr_relay_checkpoints',
  'private Nostr checkpoint ledger exists');

select set_eq(
  $$select column_name::text from information_schema.columns
    where table_schema = 'ingest' and table_name = 'nostr_relay_candidates'$$,
  $$values
    ('event_id'::text), ('source_policy_id'), ('relay_key'), ('author_sha256'),
    ('content_sha256'), ('matched_tags'), ('published_at'), ('first_seen_at'),
    ('last_seen_at'), ('deleted_at'), ('expires_at'), ('activity_only'),
    ('statistics_eligible'), ('is_demo'), ('created_at'), ('updated_at')$$,
  'candidate ledger contains only bounded hashed activity fields'
);
select set_eq(
  $$select column_name::text from information_schema.columns
    where table_schema = 'ingest' and table_name = 'nostr_relay_observations'$$,
  $$values
    ('id'::text), ('relay_key'), ('source_policy_id'), ('event_id'), ('operation'),
    ('author_sha256'), ('content_sha256'), ('matched_tags'), ('published_at'),
    ('target_event_ids'), ('observed_at'), ('expires_at'), ('activity_only'),
    ('statistics_eligible'), ('is_demo')$$,
  'observation ledger contains no raw signed event fields'
);
select set_eq(
  $$select column_name::text from information_schema.columns
    where table_schema = 'ingest' and table_name = 'nostr_relay_checkpoints'$$,
  $$values
    ('source_policy_id'::text), ('relay_key'), ('endpoint'), ('nip11_url'),
    ('protocol'), ('approved_tags'), ('last_checkpoint'), ('events_seen_total'),
    ('bytes_seen_total'), ('candidates_seen_total'), ('deletions_seen_total'),
    ('is_demo'), ('created_at'), ('updated_at')$$,
  'checkpoint stores nullable timestamptz progress and fixed relay metadata'
);

select ok(
  (select bool_and(relrowsecurity and relforcerowsecurity)
   from pg_class
   where oid in (
     'ingest.nostr_relay_candidates'::regclass,
     'ingest.nostr_relay_observations'::regclass,
     'ingest.nostr_relay_checkpoints'::regclass
   )),
  'all Nostr tables enable and force RLS'
);
select ok(
  (select bool_and(
      not has_table_privilege('service_role', table_name, 'select')
      and not has_table_privilege('service_role', table_name, 'insert')
      and not has_table_privilege('service_role', table_name, 'update')
      and not has_table_privilege('service_role', table_name, 'delete')
      and not has_table_privilege('pokecrack_nostr_worker', table_name, 'select')
    )
   from unnest(array[
     'ingest.nostr_relay_candidates'::text,
     'ingest.nostr_relay_observations'::text,
     'ingest.nostr_relay_checkpoints'::text
   ]) as tables(table_name)),
  'neither service_role nor the Nostr capability can read private Nostr state directly'
);
select ok(
  not has_table_privilege('anon', 'ingest.nostr_relay_candidates', 'select')
    and not has_table_privilege('authenticated', 'ingest.nostr_relay_observations', 'select'),
  'browser roles cannot inspect private Nostr state'
);

select is(
  (select count(*)::integer from ingest.source_policies
   where source_key in (
     'nostr_relay_primal', 'nostr_relay_nos_lol', 'nostr_relay_nostr_net'
   )),
  3,
  'exactly three Nostr source policies are provisioned'
);
select ok(
  (select bool_and(
      source_kind = 'public_web'
      and enabled
      and collector_type = 'nostr_relay'
      and access_mode = 'public'
      and robots_policy = 'not_applicable'
      and routes = array['nostr_relay']::text[]
      and min_delay_seconds = 1
      and max_pages_per_run = 1
      and max_items_per_run = 100
      and max_concurrency = 1
      and not statistics_eligible_default
      and retention_days = 30
      and version = 'nostr-multi-relay-v1'
      and expected_interval_seconds = 60
      and not is_demo
      and config ->> 'protocol' = 'nip01'
      and config ->> 'policy_state' = 'degraded_missing_relay_specific_terms'
      and jsonb_array_length(config -> 'approved_tags') = 9
    )
   from ingest.source_policies
   where source_key in (
     'nostr_relay_primal', 'nostr_relay_nos_lol', 'nostr_relay_nostr_net'
   )),
  'Nostr source policies retain the exact activity-only worker contract'
);
select set_eq(
  $$select base_url::text from ingest.source_policies
    where source_key in ('nostr_relay_primal','nostr_relay_nos_lol','nostr_relay_nostr_net')$$,
  $$values ('wss://relay.primal.net/'::text), ('wss://nos.lol/'), ('wss://relay.nostr.net/')$$,
  'only the three reviewed relay endpoints are registered'
);
select ok(
  (select bool_and(last_checkpoint is null and protocol = 'nip01'
      and cardinality(approved_tags) = 9)
   from ingest.nostr_relay_checkpoints),
  'all relay checkpoints start nullable and pinned to NIP-01'
);

select has_function('ingest', 'begin_nostr_relay_job',
  array['uuid', 'text', 'bigint', 'text'], 'typed Nostr preflight exists');
select has_function('ingest', 'finalize_nostr_relay_job',
  array['uuid', 'text', 'bigint', 'jsonb'], 'typed Nostr finalizer exists');
select has_function('ingest', 'prune_nostr_relay_v1',
  array['timestamptz', 'integer'], 'bounded Nostr cleanup exists');
select has_function('public', 'get_public_social_discovery_v2',
  array[]::text[], 'Bluesky-first Nostr public tuple exists');

select ok(
  (select prosecdef and coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc where oid =
     'ingest.begin_nostr_relay_job(uuid,text,bigint,text)'::regprocedure)
    and has_function_privilege(
      'pokecrack_nostr_worker', 'ingest.begin_nostr_relay_job(uuid,text,bigint,text)', 'execute'
    )
    and not has_function_privilege(
      'service_role', 'ingest.begin_nostr_relay_job(uuid,text,bigint,text)', 'execute'
    )
    and not has_function_privilege(
      'anon', 'ingest.begin_nostr_relay_job(uuid,text,bigint,text)', 'execute'
    ),
  'only the isolated Nostr capability receives the fenced Nostr begin RPC'
);
select ok(
  (select prosecdef and coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc where oid =
     'ingest.finalize_nostr_relay_job(uuid,text,bigint,jsonb)'::regprocedure)
    and has_function_privilege(
      'pokecrack_nostr_worker', 'ingest.finalize_nostr_relay_job(uuid,text,bigint,jsonb)', 'execute'
    )
    and not has_function_privilege(
      'service_role', 'ingest.finalize_nostr_relay_job(uuid,text,bigint,jsonb)', 'execute'
    )
    and not has_function_privilege(
      'authenticated', 'ingest.finalize_nostr_relay_job(uuid,text,bigint,jsonb)', 'execute'
    ),
  'only the isolated Nostr capability receives the fenced Nostr finalizer'
);
select ok(
  not has_function_privilege(
    'service_role', 'ingest.prune_nostr_relay_v1(timestamptz,integer)', 'execute'
  ),
  'worker roles cannot invoke Nostr cleanup outside a maintenance lease'
);

select is(
  public.get_public_social_discovery_v2() ->> 'schemaVersion',
  '2.0.0',
  'public social v2 uses the exact schema version'
);
select is(
  jsonb_array_length(public.get_public_social_discovery_v2() -> 'sources'),
  2,
  'public social v2 exposes exactly Bluesky then Nostr'
);
select ok(
  (public.get_public_social_discovery_v2() #>> '{sources,0,id}') = 'bluesky_jetstream'
    and (public.get_public_social_discovery_v2() #>> '{sources,1,id}') = 'nostr_multi_relay'
    and (public.get_public_social_discovery_v2() #>> '{sources,1,url}') =
      'https://github.com/nostr-protocol/nips/blob/master/01.md',
  'public social v2 returns the exact safe source tuple order and URLs'
);
select doesnt_match(
  public.get_public_social_discovery_v2()::text,
  '(?i)(event_id|author_sha|content_sha|pubkey|signature|profile|media|wss://|policy_id|source_policy|gate|payload)',
  'public social v2 exposes no private identifiers, content, relay endpoints, or payload'
);

create function pg_temp.nostr_candidate(
  event_id text,
  author_sha256 text default repeat('a', 64),
  content_sha256 text default repeat('b', 64),
  published_at text default null,
  matched_tags jsonb default '["pokemontcg"]'::jsonb,
  relay_key text default 'primal'
)
returns jsonb
language sql
immutable
as $$
  select jsonb_build_object(
    'event_id', event_id,
    'author_sha256', author_sha256,
    'published_at', published_at,
    'content_sha256', content_sha256,
    'matched_tags', matched_tags,
    'relay_key', relay_key,
    'activity_only', true,
    'statistics_eligible', false
  );
$$;

create function pg_temp.nostr_deletion(
  event_id text,
  author_sha256 text,
  published_at text,
  target_event_ids jsonb,
  relay_key text default 'primal'
)
returns jsonb
language sql
immutable
as $$
  select jsonb_build_object(
    'event_id', event_id,
    'author_sha256', author_sha256,
    'published_at', published_at,
    'kind', 5,
    'relay_key', relay_key,
    'target_event_ids', target_event_ids
  );
$$;

create function pg_temp.nostr_result(
  relay_key text,
  since timestamptz,
  until timestamptz,
  checkpoint timestamptz,
  events_seen bigint,
  bytes_seen bigint,
  candidates jsonb default '[]'::jsonb,
  deletions jsonb default '[]'::jsonb
)
returns jsonb
language sql
immutable
as $$
  select jsonb_build_object(
    'version', '1.0.0',
    'relay_key', relay_key,
    'since', to_char(since at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
    'until', to_char(until at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
    'checkpoint', case when checkpoint is null then null
      else to_char(checkpoint at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"') end,
    'incomplete', false,
    'events_seen', events_seen,
    'bytes_seen', bytes_seen,
    'candidates', candidates,
    'deletions', deletions
  );
$$;

insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'a6000000-0000-4000-8000-000000000001',
  'source.nostr.relay', '{"relay_key":"primal"}'::jsonb, 'running', 1,
  clock_timestamp(), clock_timestamp() + interval '10 minutes',
  'nostr-collector-1', 1, false
);
create temporary table nostr_begin_one on commit drop as
select * from ingest.begin_nostr_relay_job(
  'a6000000-0000-4000-8000-000000000001', 'nostr-collector-1', 1, 'primal'
);
select ok(
  (select acquired and retry_at is null and checkpoint is null
      and since < until and recent_candidate_ids = '{}'::text[]
   from nostr_begin_one),
  'first Nostr relay slice acquires from the nullable checkpoint'
);

select is(
  pg_temp.sqlstate_of($sql$
    select * from ingest.finalize_nostr_relay_job(
      'a6000000-0000-4000-8000-000000000001', 'nostr-collector-1', 1,
      jsonb_build_object(
        'version', '1.0.0', 'relay_key', 'primal',
        'since', '2000-01-01T00:00:00Z', 'until', '2000-01-01T00:00:01Z',
        'checkpoint', null, 'incomplete', false, 'events_seen', 0,
        'bytes_seen', 0, 'candidates', '[]'::jsonb, 'deletions', '[]'::jsonb,
        'extra', true
      )
    )
  $sql$),
  '22023',
  'unexpected root keys fail closed before any Nostr write'
);
select ok(
  (select status = 'running' from ingest.jobs
   where id = 'a6000000-0000-4000-8000-000000000001')
    and (select last_checkpoint is null from ingest.nostr_relay_checkpoints
         where relay_key = 'primal'),
  'contract rejection leaves the live job and checkpoint unchanged'
);

select lives_ok(
  $sql$select * from ingest.finalize_nostr_relay_job(
    'a6000000-0000-4000-8000-000000000001', 'nostr-collector-1', 1,
    pg_temp.nostr_result(
      'primal',
      (select since from nostr_begin_one),
      (select until from nostr_begin_one),
      null,
      1,
      128,
      jsonb_build_array(pg_temp.nostr_candidate(
        repeat('1', 64), repeat('a', 64), repeat('b', 64),
        to_char((select until from nostr_begin_one) at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"')
      )),
      '[]'::jsonb
    )
  )$sql$,
  'valid first Nostr slice finalizes atomically'
);
select ok(
  (select status = 'completed' and locked_by is null from ingest.jobs
   where id = 'a6000000-0000-4000-8000-000000000001')
    and (select owner_job_id is null from ingest.source_request_gates
         where source_key = 'nostr_relay_primal')
    and (select last_checkpoint is not null from ingest.nostr_relay_checkpoints
         where relay_key = 'primal'),
  'successful Nostr finalization advances the checkpoint and releases the gate'
);
select is(
  (select count(*)::integer from ingest.nostr_relay_candidates
   where event_id = repeat('1', 64)),
  1,
  'a kind-1 event creates one global candidate'
);
select is(
  (select count(*)::integer from ingest.nostr_relay_observations
   where event_id = repeat('1', 64) and relay_key = 'primal'),
  1,
  'the candidate observation is idempotently recorded per relay'
);
set local role anon;
select set_config(
  'pokecrack_test.nostr_public_after_candidate',
  public.get_public_social_discovery_v2()::text,
  true
);
reset role;
select matches(
  current_setting('pokecrack_test.nostr_public_after_candidate', true)::jsonb
    #>> '{sources,1,note}',
  '^1 of 3 reviewed public relays collected recently; 1 retained tag-matched activity candidates\.',
  'the anon public projection can count retained activity after worker-table policies are removed'
);

-- A duplicate trigger inside the same whole NIP-01 second must defer before
-- taking the request gate. Seed a future whole-second checkpoint to make the
-- edge deterministic without depending on test-runner speed.
create temporary table nostr_checkpoint_before_defer on commit drop as
select last_checkpoint
from ingest.nostr_relay_checkpoints
where relay_key = 'primal';
update ingest.nostr_relay_checkpoints
set last_checkpoint = date_trunc('second', clock_timestamp()) + interval '10 seconds'
where relay_key = 'primal';
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '2 seconds'
where source_key = 'nostr_relay_primal';
insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'a6000000-0000-4000-8000-000000000005', 'source.nostr.relay',
  '{"relay_key":"primal"}'::jsonb, 'running', 1, clock_timestamp(),
  clock_timestamp() + interval '10 minutes', 'nostr-collector-5', 1, false
);
create temporary table nostr_begin_same_second on commit drop as
select * from ingest.begin_nostr_relay_job(
  'a6000000-0000-4000-8000-000000000005', 'nostr-collector-5', 1, 'primal'
);
select ok(
  (select not acquired
      and retry_at = checkpoint + interval '1 second'
      and recent_candidate_ids = '{}'::text[]
   from nostr_begin_same_second)
    and (select owner_job_id is null
         from ingest.source_request_gates
         where source_key = 'nostr_relay_primal')
    and (public.get_public_social_discovery_v2()
         #>> '{sources,1,lastCollectedAt}') is null,
  'same-second Nostr re-entry defers before taking the request gate'
);
update ingest.nostr_relay_checkpoints
set last_checkpoint = saved.last_checkpoint
from nostr_checkpoint_before_defer as saved
where relay_key = 'primal';

select throws_ok(
  $$select * from ingest.enqueue_scheduled_job_v1(
    'wrong_nostr_name', date_trunc('minute', clock_timestamp()),
    'source.nostr.relay', '{"relay_key":"primal"}'::jsonb, 0, 5
  )$$,
  '22023',
  'Nostr jobs require one exact relay_key and canonical schedule name',
  'scheduled Nostr enqueue requires its canonical relay schedule'
);
create temporary table nostr_scheduled_job on commit drop as
select * from ingest.enqueue_scheduled_job_v1(
  'nostr_primal', date_trunc('minute', clock_timestamp()),
  'source.nostr.relay', '{"relay_key":"primal"}'::jsonb, 0, 5
);
select is((select count(*)::integer from nostr_scheduled_job), 1,
  'canonical Nostr schedule enqueues one exact relay job');
select throws_ok(
  $$select * from ingest.enqueue_job_v1(
    'source.nostr.relay', '{"relay_key":"primal","extra":true}'::jsonb
  )$$,
  '22023', 'Nostr jobs require one exact relay_key',
  'direct Nostr enqueue rejects extra payload fields'
);

-- Same-author, non-older tombstones mutate the candidate; unknown, older, and
-- cross-author references remain harmless while their private observations stay.
do $$
begin
  perform pg_sleep(1.05);
end;
$$;
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '2 seconds'
where source_key = 'nostr_relay_primal';
insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'a6000000-0000-4000-8000-000000000002', 'source.nostr.relay',
  '{"relay_key":"primal"}'::jsonb, 'running', 1, clock_timestamp(),
  clock_timestamp() + interval '10 minutes', 'nostr-collector-2', 1, false
);
create temporary table nostr_begin_two on commit drop as
select * from ingest.begin_nostr_relay_job(
  'a6000000-0000-4000-8000-000000000002', 'nostr-collector-2', 1, 'primal'
);
select lives_ok(
  $sql$select * from ingest.finalize_nostr_relay_job(
    'a6000000-0000-4000-8000-000000000002', 'nostr-collector-2', 1,
    pg_temp.nostr_result(
      'primal', (select since from nostr_begin_two), (select until from nostr_begin_two),
      (select checkpoint from nostr_begin_two), 3, 256, '[]'::jsonb,
      jsonb_build_array(
        pg_temp.nostr_deletion(
          repeat('2', 64), repeat('a', 64),
          to_char((select until from nostr_begin_two) at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
          jsonb_build_array(repeat('1', 64), repeat('3', 64))
        )
      )
    )
  )$sql$,
  'same-author newer delete records a tombstone without synthesizing unknown targets'
);
select ok(
  (select deleted_at is not null from ingest.nostr_relay_candidates
   where event_id = repeat('1', 64)),
  'same-author delete tombstones the known candidate'
);
select is(
  (select count(*)::integer from ingest.nostr_relay_candidates),
  1,
  'unknown delete targets do not create candidates'
);

do $$
begin
  perform pg_sleep(1.05);
end;
$$;
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '2 seconds'
where source_key = 'nostr_relay_primal';
insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'a6000000-0000-4000-8000-000000000003', 'source.nostr.relay',
  '{"relay_key":"primal"}'::jsonb, 'running', 1, clock_timestamp(),
  clock_timestamp() + interval '10 minutes', 'nostr-collector-3', 1, false
);
create temporary table nostr_begin_three on commit drop as
select * from ingest.begin_nostr_relay_job(
  'a6000000-0000-4000-8000-000000000003', 'nostr-collector-3', 1, 'primal'
);
select lives_ok(
  $sql$select * from ingest.finalize_nostr_relay_job(
    'a6000000-0000-4000-8000-000000000003', 'nostr-collector-3', 1,
    pg_temp.nostr_result(
      'primal', (select since from nostr_begin_three), (select until from nostr_begin_three),
      (select checkpoint from nostr_begin_three), 1, 96, '[]'::jsonb,
      jsonb_build_array(pg_temp.nostr_deletion(
        repeat('4', 64), repeat('c', 64),
        to_char((select until from nostr_begin_three) at time zone 'UTC', 'YYYY-MM-DD"T"HH24:MI:SS.US"Z"'),
        jsonb_build_array(repeat('1', 64))
      ))
    )
  )$sql$,
  'cross-author delete observation is retained but cannot poison the candidate'
);
select ok(
  (select deleted_at is not null and author_sha256 = repeat('a', 64)
   from ingest.nostr_relay_candidates where event_id = repeat('1', 64)),
  'cross-author delete leaves the original candidate tombstone unchanged'
);

do $$
begin
  perform pg_sleep(1.05);
end;
$$;
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '2 seconds'
where source_key = 'nostr_relay_primal';
insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'a6000000-0000-4000-8000-000000000004', 'source.nostr.relay',
  '{"relay_key":"primal"}'::jsonb, 'running', 1, clock_timestamp(),
  clock_timestamp() + interval '10 minutes', 'nostr-collector-4', 1, false
);
create temporary table nostr_begin_four on commit drop as
select * from ingest.begin_nostr_relay_job(
  'a6000000-0000-4000-8000-000000000004', 'nostr-collector-4', 1, 'primal'
);
select throws_ok(
  $$select * from ingest.complete_job_v2(
    'a6000000-0000-4000-8000-000000000004', 'nostr-collector-4', 1
  )$$,
  '22023', 'typed live jobs require their dedicated fenced finalizer',
  'generic completion rejects typed Nostr jobs'
);
select is(
  pg_temp.sqlstate_of($sql$
    select * from ingest.finalize_nostr_relay_job(
      'a6000000-0000-4000-8000-000000000004', 'nostr-collector-4', 1,
      pg_temp.nostr_result(
        'primal', (select since from nostr_begin_four),
        (select until from nostr_begin_four) - interval '1 second',
        (select checkpoint from nostr_begin_four), 0, 0
      )
    )
  $sql$),
  '40001',
  'tampered until timestamps fail the fenced window before any write'
);

with stale_time as materialized (
  select clock_timestamp() - interval '31 days' as value
)
insert into ingest.nostr_relay_candidates (
  event_id, source_policy_id, relay_key, author_sha256, content_sha256,
  matched_tags, published_at, first_seen_at, last_seen_at, expires_at,
  activity_only, statistics_eligible, is_demo, created_at, updated_at
)
select repeat('e', 64), id, 'primal', repeat('a', 64), repeat('b', 64),
  array['pokemontcg']::text[], stale_time.value, stale_time.value - interval '1 day',
  stale_time.value, stale_time.value + interval '30 days', true, false, false,
  stale_time.value - interval '1 day', stale_time.value
from ingest.source_policies cross join stale_time
where source_key = 'nostr_relay_primal';
with stale_time as materialized (
  select clock_timestamp() - interval '31 days' as value
)
insert into ingest.nostr_relay_observations (
  relay_key, source_policy_id, event_id, operation, author_sha256,
  content_sha256, matched_tags, published_at, target_event_ids,
  observed_at, expires_at, activity_only, statistics_eligible, is_demo
)
select 'primal', id, repeat('f', 64), 'upsert', repeat('a', 64), repeat('c', 64),
  array['pokemontcg']::text[], stale_time.value, '{}'::text[], stale_time.value,
  stale_time.value + interval '30 days', true, false, false
from ingest.source_policies cross join stale_time
where source_key = 'nostr_relay_primal';
select lives_ok(
  $$select * from ingest.prune_nostr_relay_v1(clock_timestamp(), 1)$$,
  'bounded Nostr cleanup accepts an independent one-row budget'
);
select is(
  (select count(*)::integer from ingest.nostr_relay_checkpoints),
  3,
  'cleanup retains all three relay checkpoints'
);

select * from finish();
rollback;
