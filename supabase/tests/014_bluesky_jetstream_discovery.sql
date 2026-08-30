-- Bounded public Bluesky Jetstream discovery, fencing, replay, and redaction.
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

create function pg_temp.bluesky_candidate(
  event_cursor bigint,
  at_uri text,
  excerpt text default 'Pokemon TCG pack opening',
  content_hash text default null,
  published_at text default null
)
returns jsonb
language sql
immutable
as $$
  select jsonb_build_object(
    'cursor', event_cursor,
    'at_uri', at_uri,
    'public_url', 'https://bsky.app/profile/' || split_part(at_uri, '/', 3)
      || '/post/' || split_part(at_uri, '/', 5),
    'text_excerpt', excerpt,
    'record_sha256', coalesce(content_hash, repeat('a', 64)),
    'published_at', published_at
  );
$$;

create function pg_temp.bluesky_deletion(event_cursor bigint, at_uri text)
returns jsonb
language sql
immutable
as $$
  select jsonb_build_object('cursor', event_cursor, 'at_uri', at_uri);
$$;

create function pg_temp.bluesky_result(
  start_cursor bigint,
  end_cursor bigint,
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
    'start_cursor', start_cursor,
    'end_cursor', end_cursor,
    'events_seen', events_seen,
    'bytes_seen', bytes_seen,
    'candidates', candidates,
    'deletions', deletions
  );
$$;

select has_table('ingest', 'bluesky_jetstream_candidates',
  'private Bluesky candidate cache exists');
select has_table('ingest', 'bluesky_jetstream_observations',
  'private immutable Bluesky event ledger exists');
select has_table('ingest', 'bluesky_jetstream_checkpoints',
  'private Bluesky cursor checkpoint exists');

select set_eq(
  $$select column_name::text from information_schema.columns
    where table_schema = 'ingest' and table_name = 'bluesky_jetstream_candidates'$$,
  $$values
    ('at_uri'::text), ('public_url'), ('text_excerpt'), ('record_sha256'),
    ('published_at'), ('source_policy_id'), ('source_policy_version'),
    ('collector_version'), ('first_seen_at'), ('last_seen_at'), ('last_cursor'),
    ('deleted_at'), ('expires_at'), ('is_demo'), ('created_at'), ('updated_at')$$,
  'candidate cache has only the reviewed private activity fields'
);
select set_eq(
  $$select column_name::text from information_schema.columns
    where table_schema = 'ingest' and table_name = 'bluesky_jetstream_observations'$$,
  $$values
    ('id'::text), ('source_policy_id'), ('cursor'), ('at_uri'), ('operation'),
    ('public_url'), ('text_excerpt'), ('record_sha256'), ('published_at'),
    ('observed_at'), ('expires_at'), ('is_demo')$$,
  'event ledger has only bounded replay fields'
);
select set_eq(
  $$select column_name::text from information_schema.columns
    where table_schema = 'ingest' and table_name = 'bluesky_jetstream_checkpoints'$$,
  $$values
    ('source_policy_id'::text), ('endpoint'), ('protocol'), ('collection'),
    ('last_cursor'), ('last_collected_at'), ('events_seen_total'),
    ('bytes_seen_total'), ('candidates_seen_total'), ('deletions_seen_total'),
    ('is_demo'), ('created_at'), ('updated_at')$$,
  'checkpoint stores only private protocol and aggregate health state'
);

select ok(
  (select bool_and(relrowsecurity and relforcerowsecurity)
   from pg_class
   where oid in (
     'ingest.bluesky_jetstream_candidates'::regclass,
     'ingest.bluesky_jetstream_observations'::regclass,
     'ingest.bluesky_jetstream_checkpoints'::regclass
   )),
  'all Bluesky tables enable and force RLS'
);
select ok(
  has_table_privilege('service_role', 'ingest.bluesky_jetstream_candidates', 'select')
    and not has_table_privilege('service_role', 'ingest.bluesky_jetstream_candidates', 'insert')
    and not has_table_privilege('service_role', 'ingest.bluesky_jetstream_candidates', 'update')
    and not has_table_privilege('service_role', 'ingest.bluesky_jetstream_candidates', 'delete'),
  'service_role may inspect but never mutate Bluesky candidates directly'
);
select ok(
  has_table_privilege('service_role', 'ingest.bluesky_jetstream_observations', 'select')
    and not has_table_privilege('service_role', 'ingest.bluesky_jetstream_observations', 'insert')
    and not has_table_privilege('service_role', 'ingest.bluesky_jetstream_observations', 'update')
    and not has_table_privilege('service_role', 'ingest.bluesky_jetstream_observations', 'delete'),
  'service_role may inspect but never mutate Bluesky observations directly'
);
select ok(
  has_table_privilege('service_role', 'ingest.bluesky_jetstream_checkpoints', 'select')
    and not has_table_privilege('service_role', 'ingest.bluesky_jetstream_checkpoints', 'insert')
    and not has_table_privilege('service_role', 'ingest.bluesky_jetstream_checkpoints', 'update')
    and not has_table_privilege('service_role', 'ingest.bluesky_jetstream_checkpoints', 'delete'),
  'service_role may inspect but never mutate the Bluesky checkpoint directly'
);
select ok(
  not has_table_privilege('anon', 'ingest.bluesky_jetstream_candidates', 'select')
    and not has_table_privilege('authenticated', 'ingest.bluesky_jetstream_candidates', 'select')
    and not has_table_privilege('anon', 'ingest.bluesky_jetstream_observations', 'select')
    and not has_table_privilege('authenticated', 'ingest.bluesky_jetstream_checkpoints', 'select'),
  'browser roles cannot inspect private Bluesky state'
);

select ok(
  (select source_kind = 'official_api'
      and domain = 'jetstream.us-west.bsky.network'
      and base_url = 'wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents'
      and enabled
      and collector_type = 'bluesky_jetstream'
      and access_mode = 'official_api'
      and robots_policy = 'not_applicable'
      and routes = array['bluesky_jetstream']::text[]
      and min_delay_seconds = 1
      and max_pages_per_run = 1
      and max_items_per_run = 100
      and max_concurrency = 1
      and not statistics_eligible_default
      and retention_days = 30
      and config = '{
        "endpoint":"wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents",
        "collection":"app.bsky.feed.post",
        "operations":["create","update","delete"],
        "kinds":["commit"],
        "subprotocol":"xrpc.v1.json",
        "stream_window_seconds":40,
        "max_events":10000,
        "max_message_bytes":262144,
        "max_stream_bytes":2097152,
        "max_candidates":100,
        "max_deletions":100,
        "max_excerpt_chars":500,
        "keyword_registry":"bluesky-keywords-v1",
        "statistics_eligible":false
      }'::jsonb
      and version = 'bluesky-jetstream-v1'
      and expected_interval_seconds = 60
      and not is_demo
   from ingest.source_policies where source_key = 'bluesky_jetstream'),
  'exact reviewed West Jetstream policy is provisioned'
);
select matches(
  (select pg_get_constraintdef(oid)
   from pg_constraint
   where conrelid = 'ingest.source_policies'::regclass
     and conname = 'source_policies_base_url_check'),
  'char_length\(base_url\) <= 2048',
  'adding the WSS endpoint preserves the global source URL length bound'
);
select ok(
  (select last_cursor is null
      and last_collected_at is null
      and endpoint = 'wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents'
      and protocol = 'xrpc.v1.json'
      and collection = 'app.bsky.feed.post'
   from ingest.bluesky_jetstream_checkpoints),
  'initial checkpoint is nullable and pinned to the exact protocol'
);

select has_function('ingest', 'begin_bluesky_jetstream_job',
  array['uuid', 'text', 'bigint'], 'typed pre-stream Bluesky gate exists');
select has_function('ingest', 'finalize_bluesky_jetstream_job',
  array['uuid', 'text', 'bigint', 'jsonb'], 'typed atomic Bluesky finalizer exists');
select has_function('ingest', 'prune_bluesky_jetstream_v1',
  array['timestamptz', 'integer'], 'bounded private Bluesky cleanup exists');
select has_function('public', 'get_public_social_discovery_v1',
  array[]::text[], 'strict browser-safe social discovery RPC exists');
select ok(
  (select prosecdef and coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc where oid =
     'ingest.begin_bluesky_jetstream_job(uuid,text,bigint)'::regprocedure)
    and has_function_privilege(
      'service_role', 'ingest.begin_bluesky_jetstream_job(uuid,text,bigint)', 'execute'
    )
    and not has_function_privilege(
      'anon', 'ingest.begin_bluesky_jetstream_job(uuid,text,bigint)', 'execute'
    ),
  'only service_role receives the fixed-search-path SECURITY DEFINER begin RPC'
);
select ok(
  (select prosecdef and coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc where oid =
     'ingest.finalize_bluesky_jetstream_job(uuid,text,bigint,jsonb)'::regprocedure)
    and has_function_privilege(
      'service_role', 'ingest.finalize_bluesky_jetstream_job(uuid,text,bigint,jsonb)', 'execute'
    )
    and not has_function_privilege(
      'authenticated', 'ingest.finalize_bluesky_jetstream_job(uuid,text,bigint,jsonb)', 'execute'
    ),
  'only service_role receives the fixed-search-path SECURITY DEFINER finalizer'
);
select ok(
  not has_function_privilege(
    'service_role', 'ingest.prune_bluesky_jetstream_v1(timestamptz,integer)', 'execute'
  ),
  'worker roles cannot invoke private retention independently of a cleanup lease'
);
select ok(
  (select prosecdef and proowner::regrole::text = 'postgres'
      and coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc where oid = 'public.get_public_social_discovery_v1()'::regprocedure)
    and has_function_privilege(
      'anon', 'public.get_public_social_discovery_v1()', 'execute'
    )
    and has_function_privilege(
      'authenticated', 'public.get_public_social_discovery_v1()', 'execute'
    )
    and not has_function_privilege(
      'service_role', 'public.get_public_social_discovery_v1()', 'execute'
    ),
  'only browser roles receive the owner-controlled public health projection'
);
select matches(
  pg_get_functiondef(
    'ingest.enqueue_scheduled_job_v1(text,timestamptz,text,jsonb,integer,integer)'::regprocedure
  ),
  'source\.bluesky\.jetstream',
  'scheduled enqueue retains the exact Bluesky job allowlist'
);
select matches(
  pg_get_functiondef('ingest.complete_job_v2(uuid,text,bigint)'::regprocedure),
  'source\.bluesky\.jetstream',
  'generic completion rejects the dedicated Bluesky job type'
);
select matches(
  (select pg_get_constraintdef(oid)
   from pg_constraint
   where conrelid = 'ingest.jobs'::regclass
     and conname = 'jobs_live_scheduled_enqueue_allowlist_check'),
  'source\.bluesky\.jetstream',
  'scheduled Bluesky jobs remain guarded at the table boundary'
);
select is(ingest.bluesky_cursor_v1('0'), 0::bigint,
  'canonical zero cursor is accepted');
select is(
  pg_temp.sqlstate_of($sql$select ingest.bluesky_cursor_v1('01')$sql$),
  '22023',
  'noncanonical decimal cursors fail closed'
);

select is(
  public.get_public_social_discovery_v1() ->> 'schemaVersion',
  '1.0.0',
  'public social health uses the exact schema version'
);
select is(
  jsonb_array_length(public.get_public_social_discovery_v1() -> 'sources'),
  1,
  'public social health exposes exactly one reviewed source'
);
select ok(
  (public.get_public_social_discovery_v1() #>> '{sources,0,id}') = 'bluesky_jetstream'
    and (public.get_public_social_discovery_v1() #>> '{sources,0,status}') = 'delayed'
    and (public.get_public_social_discovery_v1() #>> '{sources,0,lastCollectedAt}') is null,
  'uncollected source is explicit and delayed rather than fabricated as operational'
);
select doesnt_match(
  public.get_public_social_discovery_v1()::text,
  '(?i)(at://|did:|cursor|record_sha|text_excerpt|source_policy|gate|wss://|payload)',
  'public social health exposes no post, text, hash, cursor, endpoint, gate, policy, or payload'
);

insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'be000000-0000-4000-8000-000000000001',
  'source.bluesky.jetstream', '{}'::jsonb, 'running', 1,
  clock_timestamp(), clock_timestamp() + interval '10 minutes',
  'bluesky-worker-1', 1, false
);
create temporary table bluesky_begin_one on commit drop as
select * from ingest.begin_bluesky_jetstream_job(
  'be000000-0000-4000-8000-000000000001', 'bluesky-worker-1', 1
);
select ok(
  (select acquired and retry_at is null and start_cursor is null
   from bluesky_begin_one),
  'first live stream acquires from the nullable initial checkpoint'
);
select is(
  pg_temp.sqlstate_of($sql$
    select * from ingest.finalize_bluesky_jetstream_job(
      'be000000-0000-4000-8000-000000000001', 'bluesky-worker-1', 1,
      '{"version":"1.0.0","start_cursor":null,"end_cursor":null,"events_seen":0,"bytes_seen":0,"candidates":[],"deletions":[],"extra":true}'::jsonb
    )
  $sql$),
  '22023',
  'unexpected root keys fail closed before any write'
);
select ok(
  (select status = 'running' from ingest.jobs
   where id = 'be000000-0000-4000-8000-000000000001')
    and (select last_cursor is null from ingest.bluesky_jetstream_checkpoints),
  'contract rejection leaves the job and nullable checkpoint unchanged'
);
select is(
  pg_temp.sqlstate_of($sql$
    select * from ingest.finalize_bluesky_jetstream_job(
      'be000000-0000-4000-8000-000000000001', 'bluesky-worker-1', 1,
      jsonb_set(
        pg_temp.bluesky_result(null, 101, 1, 64,
          jsonb_build_array(pg_temp.bluesky_candidate(
            101,
            'at://did:plc:abcdefghijklmnopqrstuvwx/app.bsky.feed.post/3firstpost'
          ))
        ),
        '{end_cursor}', '"101"'::jsonb
      )
    )
  $sql$),
  '22023',
  'string cursors are rejected because the worker contract is numeric-or-null'
);
select is(
  pg_temp.sqlstate_of($sql$
    select * from ingest.finalize_bluesky_jetstream_job(
      'be000000-0000-4000-8000-000000000001', 'bluesky-worker-1', 1,
      pg_temp.bluesky_result(
        null, 102, 2, 128,
        jsonb_build_array(pg_temp.bluesky_candidate(
          101,
          'at://did:plc:abcdefghijklmnopqrstuvwx/app.bsky.feed.post/3firstpost'
        )),
        jsonb_build_array(pg_temp.bluesky_deletion(
          101,
          'at://did:plc:zyxwvutsrqponmlkjihgfedc/app.bsky.feed.post/3unknown'
        ))
      )
    )
  $sql$),
  '22023',
  'candidate and deletion sequence conflicts fail closed'
);
select lives_ok(
  $sql$select * from ingest.finalize_bluesky_jetstream_job(
    'be000000-0000-4000-8000-000000000001', 'bluesky-worker-1', 1,
    pg_temp.bluesky_result(
      null, 103, 3, 512,
      jsonb_build_array(pg_temp.bluesky_candidate(
        101,
        'at://did:plc:abcdefghijklmnopqrstuvwx/app.bsky.feed.post/3firstpost'
      )),
      jsonb_build_array(pg_temp.bluesky_deletion(
        102,
        'at://did:plc:zyxwvutsrqponmlkjihgfedc/app.bsky.feed.post/3unknown'
      ))
    )
  )$sql$,
  'valid first nullable-cursor slice finalizes atomically'
);
select ok(
  (select status = 'completed' and locked_by is null
   from ingest.jobs where id = 'be000000-0000-4000-8000-000000000001')
    and (select owner_job_id is null
         from ingest.source_request_gates where source_key = 'bluesky_jetstream'),
  'successful finalization completes the fenced job and releases its exact gate'
);
select ok(
  (select last_cursor = 103 and events_seen_total = 3
      and bytes_seen_total = 512 and candidates_seen_total = 1
      and deletions_seen_total = 1 and last_collected_at is not null
   from ingest.bluesky_jetstream_checkpoints),
  'initial NULL checkpoint advances atomically through nonmatching valid commits'
);
select is(
  (select count(*)::integer from ingest.bluesky_jetstream_candidates),
  1,
  'unknown deletion writes no synthetic candidate'
);
select is(
  (select count(*)::integer from ingest.bluesky_jetstream_observations),
  2,
  'candidate and unknown deletion both retain immutable private event identity'
);
select ok(
  (select last_cursor = 101 and deleted_at is null
      and public_url = 'https://bsky.app/profile/did:plc:abcdefghijklmnopqrstuvwx/post/3firstpost'
      and text_excerpt = 'Pokemon TCG pack opening'
      and record_sha256 = repeat('a', 64)
   from ingest.bluesky_jetstream_candidates
   where at_uri = 'at://did:plc:abcdefghijklmnopqrstuvwx/app.bsky.feed.post/3firstpost'),
  'candidate stores only the exact bounded worker fields'
);
select ok(
  (public.get_public_social_discovery_v1() #>> '{sources,0,status}') = 'operational'
    and (public.get_public_social_discovery_v1() #>> '{sources,0,lastCollectedAt}') is not null,
  'fresh successful collection becomes operational in the safe public projection'
);

update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '2 seconds'
where source_key = 'bluesky_jetstream';
insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'be000000-0000-4000-8000-000000000002',
  'source.bluesky.jetstream', '{}'::jsonb, 'running', 1,
  clock_timestamp(), clock_timestamp() + interval '10 minutes',
  'bluesky-worker-2', 1, false
);
select * from ingest.begin_bluesky_jetstream_job(
  'be000000-0000-4000-8000-000000000002', 'bluesky-worker-2', 1
);
select lives_ok(
  $sql$select * from ingest.finalize_bluesky_jetstream_job(
    'be000000-0000-4000-8000-000000000002', 'bluesky-worker-2', 1,
    pg_temp.bluesky_result(
      103, 104, 1, 96, '[]'::jsonb,
      jsonb_build_array(pg_temp.bluesky_deletion(
        104,
        'at://did:plc:abcdefghijklmnopqrstuvwx/app.bsky.feed.post/3firstpost'
      ))
    )
  )$sql$,
  'known candidate can be tombstoned by a newer delete event'
);
select ok(
  (select last_cursor = 104 and deleted_at is not null
   from ingest.bluesky_jetstream_candidates
   where at_uri = 'at://did:plc:abcdefghijklmnopqrstuvwx/app.bsky.feed.post/3firstpost'),
  'known deletion advances the candidate cursor and records a tombstone'
);
create temporary table known_delete_time on commit drop as
select deleted_at
from ingest.bluesky_jetstream_candidates
where at_uri = 'at://did:plc:abcdefghijklmnopqrstuvwx/app.bsky.feed.post/3firstpost';

-- Simulate an externally observed checkpoint lag after the event rows were
-- durably written. The same immutable delete must be a no-op, not a conflict.
update ingest.bluesky_jetstream_checkpoints set last_cursor = 103;
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '2 seconds'
where source_key = 'bluesky_jetstream';
insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'be000000-0000-4000-8000-000000000003',
  'source.bluesky.jetstream', '{}'::jsonb, 'running', 1,
  clock_timestamp(), clock_timestamp() + interval '10 minutes',
  'bluesky-worker-3', 1, false
);
select * from ingest.begin_bluesky_jetstream_job(
  'be000000-0000-4000-8000-000000000003', 'bluesky-worker-3', 1
);
select lives_ok(
  $sql$select * from ingest.finalize_bluesky_jetstream_job(
    'be000000-0000-4000-8000-000000000003', 'bluesky-worker-3', 1,
    pg_temp.bluesky_result(
      103, 104, 1, 96, '[]'::jsonb,
      jsonb_build_array(pg_temp.bluesky_deletion(
        104,
        'at://did:plc:abcdefghijklmnopqrstuvwx/app.bsky.feed.post/3firstpost'
      ))
    )
  )$sql$,
  'same known delete cursor replays idempotently after checkpoint lag'
);
select ok(
  (select candidates.deleted_at = known.deleted_at
   from ingest.bluesky_jetstream_candidates as candidates
   cross join known_delete_time as known
   where candidates.at_uri = 'at://did:plc:abcdefghijklmnopqrstuvwx/app.bsky.feed.post/3firstpost'),
  'idempotent delete replay does not refresh or mutate the tombstone'
);

update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '2 seconds'
where source_key = 'bluesky_jetstream';
insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'be000000-0000-4000-8000-000000000004',
  'source.bluesky.jetstream', '{}'::jsonb, 'running', 1,
  clock_timestamp(), clock_timestamp() + interval '10 minutes',
  'bluesky-worker-4', 1, false
);
select * from ingest.begin_bluesky_jetstream_job(
  'be000000-0000-4000-8000-000000000004', 'bluesky-worker-4', 1
);
select lives_ok(
  $sql$select * from ingest.finalize_bluesky_jetstream_job(
    'be000000-0000-4000-8000-000000000004', 'bluesky-worker-4', 1,
    pg_temp.bluesky_result(
      104, 105, 1, 128,
      jsonb_build_array(pg_temp.bluesky_candidate(
        105,
        'at://did:plc:abcdefghijklmnopqrstuvwx/app.bsky.feed.post/3firstpost',
        'Fresh Pokemon TCG booster opening', repeat('b', 64)
      ))
    )
  )$sql$,
  'newer upsert after a delete is accepted'
);
select ok(
  (select last_cursor = 105 and deleted_at is null
      and text_excerpt = 'Fresh Pokemon TCG booster opening'
      and record_sha256 = repeat('b', 64)
   from ingest.bluesky_jetstream_candidates
   where at_uri = 'at://did:plc:abcdefghijklmnopqrstuvwx/app.bsky.feed.post/3firstpost'),
  'newer upsert clears the tombstone and refreshes direct worker fields'
);

with event_time as materialized (
  select clock_timestamp() as value
)
insert into ingest.bluesky_jetstream_observations (
  source_policy_id, cursor, at_uri, operation, public_url, text_excerpt,
  record_sha256, published_at, observed_at, expires_at, is_demo
)
select id, 106,
  'at://did:plc:qwertyuiopasdfghjklzxcvb/app.bsky.feed.post/3replay',
  'upsert',
  'https://bsky.app/profile/did:plc:qwertyuiopasdfghjklzxcvb/post/3replay',
  'Replay exact', repeat('c', 64), null,
  event_time.value, event_time.value + interval '30 days', false
from ingest.source_policies
cross join event_time
where source_key = 'bluesky_jetstream';
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '2 seconds'
where source_key = 'bluesky_jetstream';
insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'be000000-0000-4000-8000-000000000005',
  'source.bluesky.jetstream', '{}'::jsonb, 'running', 1,
  clock_timestamp(), clock_timestamp() + interval '10 minutes',
  'bluesky-worker-5', 1, false
);
select * from ingest.begin_bluesky_jetstream_job(
  'be000000-0000-4000-8000-000000000005', 'bluesky-worker-5', 1
);
select is(
  pg_temp.sqlstate_of($sql$
    select * from ingest.finalize_bluesky_jetstream_job(
      'be000000-0000-4000-8000-000000000005', 'bluesky-worker-5', 1,
      pg_temp.bluesky_result(
        105, 106, 1, 128,
        jsonb_build_array(pg_temp.bluesky_candidate(
          106,
          'at://did:plc:qwertyuiopasdfghjklzxcvb/app.bsky.feed.post/3replay',
          'Replay exact', repeat('d', 64)
        ))
      )
    )
  $sql$),
  '22023',
  'same source cursor with different immutable fields fails closed'
);
select lives_ok(
  $sql$select * from ingest.finalize_bluesky_jetstream_job(
    'be000000-0000-4000-8000-000000000005', 'bluesky-worker-5', 1,
    pg_temp.bluesky_result(
      105, 106, 1, 128,
      jsonb_build_array(pg_temp.bluesky_candidate(
        106,
        'at://did:plc:qwertyuiopasdfghjklzxcvb/app.bsky.feed.post/3replay',
        'Replay exact', repeat('c', 64)
      ))
    )
  )$sql$,
  'same source cursor with every immutable field equal replays idempotently'
);
select is(
  (select count(*)::integer from ingest.bluesky_jetstream_observations
   where cursor = 106),
  1,
  'idempotent candidate replay never duplicates its event observation'
);

select throws_ok(
  $$select * from ingest.enqueue_scheduled_job_v1(
    'wrong_bluesky_name', date_trunc('minute', clock_timestamp()),
    'source.bluesky.jetstream', '{}'::jsonb, 0, 5
  )$$,
  '22023',
  'Bluesky jobs require an empty payload and the exact bluesky_jetstream schedule',
  'Bluesky scheduled enqueue requires its canonical schedule name'
);
create temporary table bluesky_scheduled_job on commit drop as
select * from ingest.enqueue_scheduled_job_v1(
  'bluesky_jetstream', date_trunc('minute', clock_timestamp()),
  'source.bluesky.jetstream', '{}'::jsonb, 0, 5
);
select is(
  (select count(*)::integer from bluesky_scheduled_job),
  1,
  'canonical every-minute schedule enqueues one exact Bluesky job'
);
select throws_ok(
  $$select * from ingest.enqueue_job_v1(
    'source.bluesky.jetstream', '{"unexpected":true}'::jsonb
  )$$,
  '22023', 'Bluesky jobs require an empty payload',
  'direct Bluesky enqueue rejects every worker-controlled payload key'
);

with stale_time as materialized (
  select clock_timestamp() - interval '31 days' as value
)
insert into ingest.bluesky_jetstream_candidates (
  at_uri, public_url, text_excerpt, record_sha256, published_at,
  source_policy_id, source_policy_version, collector_version,
  first_seen_at, last_seen_at, last_cursor, deleted_at, expires_at,
  is_demo, created_at, updated_at
)
select
  'at://did:plc:mnbvcxzlkjhgfdsaqwertyui/app.bsky.feed.post/3expired',
  'https://bsky.app/profile/did:plc:mnbvcxzlkjhgfdsaqwertyui/post/3expired',
  'Expired bounded activity', repeat('e', 64), null,
  id, 'bluesky-jetstream-v1', 'bluesky-jetstream-v1',
  stale_time.value - interval '1 day',
  stale_time.value, 1000, null,
  stale_time.value + interval '30 days', false,
  stale_time.value - interval '1 day', stale_time.value
from ingest.source_policies
cross join stale_time
where source_key = 'bluesky_jetstream';
with stale_time as materialized (
  select clock_timestamp() - interval '31 days' as value
)
insert into ingest.bluesky_jetstream_observations (
  source_policy_id, cursor, at_uri, operation, observed_at, expires_at, is_demo
)
select id, 1001,
  'at://did:plc:mnbvcxzlkjhgfdsaqwertyui/app.bsky.feed.post/3expired-delete',
  'delete', stale_time.value,
  stale_time.value + interval '30 days', false
from ingest.source_policies
cross join stale_time
where source_key = 'bluesky_jetstream';
insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'be000000-0000-4000-8000-000000000006',
  'maintenance.cleanup', '{}'::jsonb, 'running', 1,
  clock_timestamp(), clock_timestamp() + interval '10 minutes',
  'cleanup-worker', 1, false
);
select lives_ok(
  $$select * from ingest.finalize_cleanup_job(
    'be000000-0000-4000-8000-000000000006', 'cleanup-worker', 1
  )$$,
  'fenced cleanup prunes bounded expired Bluesky activity'
);
select ok(
  not exists (
    select 1 from ingest.bluesky_jetstream_candidates
    where at_uri like '%/3expired'
  )
    and not exists (
      select 1 from ingest.bluesky_jetstream_observations where cursor = 1001
    ),
  'cleanup deletes both selected expired private row classes'
);
select is(
  (select count(*)::integer from ingest.bluesky_jetstream_checkpoints),
  1,
  'cleanup always retains the monotonic source checkpoint'
);

select * from finish();
rollback;
