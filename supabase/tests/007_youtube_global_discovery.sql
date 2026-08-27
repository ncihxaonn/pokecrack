-- Dedicated, unlogged, metadata-only global YouTube discovery cache.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select plan(63);

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

create function pg_temp.youtube_item(
  video_id text,
  title text default 'Bounded metadata discovery',
  published_at text default null
)
returns jsonb
language sql
volatile
as $$
  select jsonb_build_object(
    'external_id', video_id,
    'source_url', 'https://www.youtube.com/watch?v=' || video_id,
    'title', title,
    'published_at', published_at,
    'collector_version', 'youtube-global-discovery-v1',
    'source_policy_version', 'youtube-global-discovery-v1'
  );
$$;

create function pg_temp.youtube_result(
  query_name text,
  video_id text,
  title text default 'Bounded metadata discovery',
  published_at text default null
)
returns jsonb
language sql
volatile
as $$
  select jsonb_build_object(
    'version', 1,
    'query_name', query_name,
    'items', jsonb_build_array(
      pg_temp.youtube_item(video_id, title, published_at)
    )
  );
$$;

select has_table(
  'ingest', 'youtube_discoveries',
  'dedicated YouTube activity cache exists'
);
select ok(
  to_regclass('ingest.source_discoveries') is null,
  'legacy source-linked discovery provenance does not exist'
);
select is(
  (select relpersistence from pg_class
   where oid = 'ingest.youtube_discoveries'::regclass),
  'u',
  'YouTube activity cache is UNLOGGED and excluded from WAL replication'
);
select ok(
  (select relrowsecurity and relforcerowsecurity
   from pg_class where oid = 'ingest.youtube_discoveries'::regclass),
  'YouTube activity cache enables and forces RLS'
);
select ok(
  has_table_privilege('service_role', 'ingest.youtube_discoveries', 'select')
    and not has_table_privilege('service_role', 'ingest.youtube_discoveries', 'insert')
    and not has_table_privilege('service_role', 'ingest.youtube_discoveries', 'update')
    and not has_table_privilege('service_role', 'ingest.youtube_discoveries', 'delete'),
  'service_role may inspect but never directly mutate the cache'
);
select ok(
  not has_table_privilege('anon', 'ingest.youtube_discoveries', 'select')
    and not has_table_privilege('authenticated', 'ingest.youtube_discoveries', 'select'),
  'public roles cannot inspect the private cache'
);
select set_eq(
  $$select column_name::text
    from information_schema.columns
    where table_schema = 'ingest' and table_name = 'youtube_discoveries'$$,
  $$values
    ('video_id'::text), ('source_policy_id'), ('source_url'), ('title'),
    ('published_at'), ('first_seen_at'), ('last_seen_at'), ('expires_at'),
    ('is_demo'), ('created_at'), ('updated_at')$$,
  'dedicated cache exposes only the approved exact fields'
);
select is(
  (select count(*)::integer
   from information_schema.columns
   where table_schema = 'ingest'
     and table_name = 'youtube_discoveries'
     and column_name in (
       'source_item_id', 'query_name', 'job_id', 'result_rank',
       'channel_country_code', 'geography_status', 'geography_basis',
       'metadata', 'text_excerpt', 'author_hash', 'content_hash', 'language'
     )),
  0,
  'cache stores no query, job, geography, description, hash, language, or evidence link'
);
select is(
  (select pg_get_constraintdef(oid)
   from pg_constraint
   where conrelid = 'ingest.youtube_discoveries'::regclass
     and conname = 'youtube_discoveries_source_policy_id_fkey'),
  'FOREIGN KEY (source_policy_id) REFERENCES ingest.source_policies(id) ON UPDATE RESTRICT ON DELETE RESTRICT',
  'cache binds only to its source policy'
);
select matches(
  (select pg_get_constraintdef(oid)
   from pg_constraint
   where conrelid = 'ingest.youtube_discoveries'::regclass
     and conname = 'youtube_discoveries_live_only_check'),
  '(?is)check \(\(not is_demo\)\)',
  'dedicated cache cannot contain demo rows'
);
select matches(
  (select pg_get_constraintdef(oid)
   from pg_constraint
   where conrelid = 'ingest.youtube_discoveries'::regclass
     and conname = 'youtube_discoveries_time_check'),
  '(?is)expires_at = \(last_seen_at \+ .+28 days',
  'row invariant fixes expiry to last seen plus 28 days'
);
select ok(
  (select source_kind = 'official_api'
      and domain = 'youtube.googleapis.com'
      and base_url = 'https://youtube.googleapis.com/youtube/v3'
      and enabled
      and collector_type = 'official_api'
      and access_mode = 'official_api'
      and robots_policy = 'not_applicable'
      and routes = array['official_api']::text[]
      and min_delay_seconds = 2
      and max_pages_per_run = 1
      and max_items_per_run = 25
      and max_concurrency = 1
      and not statistics_eligible_default
      and retention_days = 28
      and config = '{"metadata_only":true,"media_download":false,"max_response_bytes":2097152,"query_allowlist":["pokemon-tcg-booster-box-opening","pokemon-tcg-etb-opening","pokemon-tcg-booster-bundle-opening","pokemon-tcg-pack-opening","pokemon-tcg-opening-batch-code"]}'::jsonb
      and version = 'youtube-global-discovery-v1'
      and expected_interval_seconds = 21600
      and not is_demo
   from ingest.source_policies
   where source_key = 'youtube_discovery'),
  'exact bounded live YouTube policy is provisioned'
);
select is(
  (select count(*)::integer from ingest.source_request_gates
   where source_key in ('tcgdex_catalog', 'youtube_discovery')),
  2,
  'both bounded official API sources have durable request gates'
);
select ok(
  (select owner_job_id is null and owner_lease_generation is null
      and acquired_at is null and active_until is null
   from ingest.source_request_gates where source_key = 'youtube_discovery'),
  'YouTube request gate starts unowned'
);
select matches(
  (select pg_get_constraintdef(oid)
   from pg_constraint
   where conrelid = 'ingest.source_request_gates'::regclass
     and conname = 'source_request_gates_source_check'),
  '\^\[a-z0-9\]',
  'request gates accept canonical source keys rather than one hard-coded source'
);
select has_function(
  'ingest', 'begin_youtube_discovery_job',
  array['uuid', 'text', 'bigint'],
  'typed pre-network YouTube gate exists'
);
select has_function(
  'ingest', 'finalize_youtube_discovery_job',
  array['uuid', 'text', 'bigint', 'jsonb'],
  'typed YouTube finalizer exists'
);
select ok(
  (select prosecdef
   from pg_proc
   where oid = 'ingest.begin_youtube_discovery_job(uuid,text,bigint)'::regprocedure)
    and has_function_privilege(
      'service_role',
      'ingest.begin_youtube_discovery_job(uuid,text,bigint)',
      'execute'
    ),
  'only the service boundary receives the SECURITY DEFINER begin RPC'
);
select ok(
  (select prosecdef
   from pg_proc
   where oid = 'ingest.finalize_youtube_discovery_job(uuid,text,bigint,jsonb)'::regprocedure)
    and has_function_privilege(
      'service_role',
      'ingest.finalize_youtube_discovery_job(uuid,text,bigint,jsonb)',
      'execute'
    )
    and not has_function_privilege(
      'anon',
      'ingest.finalize_youtube_discovery_job(uuid,text,bigint,jsonb)',
      'execute'
    ),
  'only the service boundary receives the SECURITY DEFINER finalizer'
);
select is(
  (select pg_get_constraintdef(oid)
   from pg_constraint
   where conrelid = 'ingest.source_items'::regclass
     and conname = 'source_items_duplicate_cluster_mode_fkey'),
  'FOREIGN KEY (duplicate_cluster_id, is_demo) REFERENCES ingest.source_items(id, is_demo) ON UPDATE RESTRICT ON DELETE SET NULL (duplicate_cluster_id)',
  'duplicate clusters use an exact mode-scoped self-reference'
);

insert into ingest.source_policies (
  id, source_key, display_name, source_kind, domain, base_url, enabled,
  collector_type, access_mode, robots_policy, routes, include_subdomains,
  min_delay_seconds, max_pages_per_run, max_items_per_run, max_concurrency,
  statistics_eligible_default, retention_days, config, version,
  expected_interval_seconds, is_demo
) values (
  'fd000000-0000-4000-8000-000000000001',
  'mode_cluster_test', 'Mode cluster test', 'manual_import',
  'mode-cluster.pokecrack.invalid', 'https://mode-cluster.pokecrack.invalid',
  true, 'manual_import', 'manual', 'not_applicable',
  array['manual_import']::text[], false, 0, 1, 10, 1, false, 30,
  '{}'::jsonb, 'test-v1', 3600, false
);
insert into ingest.source_items (
  id, source_policy_id, platform, external_id, source_url, normalized_url,
  domain, content_hash, collector_type, collector_version,
  source_policy_version, access_mode, is_demo
) values
  (
    'fd100000-0000-4000-8000-000000000001',
    'fd000000-0000-4000-8000-000000000001',
    'mode-test', 'demo-target',
    'https://mode-cluster.pokecrack.invalid/demo-target',
    'https://mode-cluster.pokecrack.invalid/demo-target',
    'mode-cluster.pokecrack.invalid', repeat('1', 64),
    'manual_import', 'test-v1', 'test-v1', 'manual', true
  ),
  (
    'fd100000-0000-4000-8000-000000000002',
    'fd000000-0000-4000-8000-000000000001',
    'mode-test', 'live-target',
    'https://mode-cluster.pokecrack.invalid/live-target',
    'https://mode-cluster.pokecrack.invalid/live-target',
    'mode-cluster.pokecrack.invalid', repeat('2', 64),
    'manual_import', 'test-v1', 'test-v1', 'manual', false
  ),
  (
    'fd100000-0000-4000-8000-000000000003',
    'fd000000-0000-4000-8000-000000000001',
    'mode-test', 'live-member',
    'https://mode-cluster.pokecrack.invalid/live-member',
    'https://mode-cluster.pokecrack.invalid/live-member',
    'mode-cluster.pokecrack.invalid', repeat('3', 64),
    'manual_import', 'test-v1', 'test-v1', 'manual', false
  );
select is(
  pg_temp.sqlstate_of($sql$
    update ingest.source_items
    set duplicate_cluster_id = 'fd100000-0000-4000-8000-000000000001'
    where id = 'fd100000-0000-4000-8000-000000000003'
  $sql$),
  '23503',
  'a live source cannot join a demo duplicate cluster'
);
select lives_ok(
  $$update ingest.source_items
    set duplicate_cluster_id = 'fd100000-0000-4000-8000-000000000002'
    where id = 'fd100000-0000-4000-8000-000000000003'$$,
  'same-mode source items may form a duplicate cluster'
);
select is(
  pg_temp.sqlstate_of($sql$
    update ingest.source_items
    set is_demo = true
    where id = 'fd100000-0000-4000-8000-000000000002'
  $sql$),
  '23503',
  'a referenced duplicate target mode cannot be updated'
);
delete from ingest.source_items
where id = 'fd100000-0000-4000-8000-000000000002';
select ok(
  (select duplicate_cluster_id is null and not is_demo
   from ingest.source_items
   where id = 'fd100000-0000-4000-8000-000000000003'),
  'deleting a target nulls only duplicate_cluster_id and preserves source mode'
);

select is(
  pg_temp.sqlstate_of($sql$
    insert into ingest.youtube_discoveries (
      video_id, source_policy_id, source_url, first_seen_at, last_seen_at,
      expires_at, is_demo
    ) select
      'demoreject1', id, 'https://www.youtube.com/watch?v=demoreject1',
      clock_timestamp(), clock_timestamp(),
      clock_timestamp() + interval '28 days', true
    from ingest.source_policies where source_key = 'youtube_discovery'
  $sql$),
  '23514',
  'table constraint rejects demo cache rows even for an owner'
);
select is(
  pg_temp.sqlstate_of($sql$
    insert into ingest.youtube_discoveries (
      video_id, source_policy_id, source_url, first_seen_at, last_seen_at,
      expires_at, is_demo
    ) select
      'expirybad01', id, 'https://www.youtube.com/watch?v=expirybad01',
      clock_timestamp(), clock_timestamp(),
      clock_timestamp() + interval '29 days', false
    from ingest.source_policies where source_key = 'youtube_discovery'
  $sql$),
  '23514',
  'table constraint rejects any expiry beyond the fixed 28-day boundary'
);

insert into ingest.jobs (
  id, job_type, payload, available_at, retention_until, is_demo
) values (
  'fd200000-0000-4000-8000-000000000001',
  'source.youtube.discovery',
  '{"query_name":"pokemon-tcg-booster-box-opening"}'::jsonb,
  clock_timestamp() - interval '1 minute',
  clock_timestamp() + interval '90 days',
  false
);
create temporary table youtube_claim_one on commit drop as
select * from ingest.claim_jobs_v2(
  'youtube-worker', array['source.youtube.discovery'], 1, 600
);
select is(
  (select count(*)::integer from youtube_claim_one),
  1,
  'one live YouTube job is claimed'
);
select is(
  (select lease_generation from youtube_claim_one),
  1::bigint,
  'first YouTube claim receives generation one'
);
create temporary table youtube_gate_one on commit drop as
select * from ingest.begin_youtube_discovery_job(
  'fd200000-0000-4000-8000-000000000001', 'youtube-worker', 1
);
select ok(
  (select acquired and retry_at is null from youtube_gate_one),
  'valid allowlisted job acquires the pre-network request gate'
);
select ok(
  (select gates.owner_job_id = jobs.id
      and gates.owner_lease_generation = jobs.lease_generation
      and gates.active_until = jobs.lock_expires_at
   from ingest.source_request_gates as gates
   join ingest.jobs as jobs on jobs.id = gates.owner_job_id
   where gates.source_key = 'youtube_discovery'),
  'request gate is fenced to the exact job generation and lease'
);
select is(
  (select count(*)::integer
   from ingest.begin_youtube_discovery_job(
     'fd200000-0000-4000-8000-000000000001', 'youtube-worker', 2
   )),
  0,
  'a stale generation cannot acquire or disturb the request gate'
);
select throws_ok(
  $$select * from ingest.finalize_youtube_discovery_job(
    'fd200000-0000-4000-8000-000000000001', 'youtube-worker', 1,
    '{"version":1,"query_name":"pokemon-tcg-booster-box-opening","items":[],"extra":true}'::jsonb
  )$$,
  '22023', 'YouTube result must match the exact bounded v1 contract',
  'unexpected root keys are rejected before persistence'
);
select ok(
  (select status = 'running'
   from ingest.jobs where id = 'fd200000-0000-4000-8000-000000000001')
    and (select owner_job_id = 'fd200000-0000-4000-8000-000000000001'::uuid
         from ingest.source_request_gates where source_key = 'youtube_discovery'),
  'contract rejection leaves the fenced job and gate untouched'
);
select throws_ok(
  $sql$select * from ingest.finalize_youtube_discovery_job(
    'fd200000-0000-4000-8000-000000000001', 'youtube-worker', 1,
    jsonb_set(
      pg_temp.youtube_result(
        'pokemon-tcg-booster-box-opening', 'nullfield01'
      ),
      '{items,0,normalized_url}',
      '"https://www.youtube.com/watch?v=nullfield01"'::jsonb
    )
  )$sql$,
  '22023', 'YouTube items must use the exact bounded v1 item contract',
  'legacy normalized URL fields are rejected instead of persisted'
);
select throws_ok(
  $sql$select * from ingest.finalize_youtube_discovery_job(
    'fd200000-0000-4000-8000-000000000001', 'youtube-worker', 1,
    jsonb_set(
      pg_temp.youtube_result(
        'pokemon-tcg-booster-box-opening', 'nullfield01'
      ),
      '{items,0,text_excerpt}', 'null'::jsonb
    )
  )$sql$,
  '22023', 'YouTube items must use the exact bounded v1 item contract',
  'description placeholders are absent rather than accepted as null'
);
select throws_ok(
  $sql$select * from ingest.finalize_youtube_discovery_job(
    'fd200000-0000-4000-8000-000000000001', 'youtube-worker', 1,
    jsonb_set(
      pg_temp.youtube_result(
        'pokemon-tcg-booster-box-opening', 'nullfield01'
      ),
      '{items,0,metadata}', '{}'::jsonb
    )
  )$sql$,
  '22023', 'YouTube items must use the exact bounded v1 item contract',
  'derived metadata objects are rejected instead of persisted'
);
select throws_ok(
  $sql$select * from ingest.finalize_youtube_discovery_job(
    'fd200000-0000-4000-8000-000000000001', 'youtube-worker', 1,
    jsonb_set(
      pg_temp.youtube_result(
        'pokemon-tcg-booster-box-opening', 'nullfield01'
      ),
      '{items,0,language}', 'null'::jsonb
    )
  )$sql$,
  '22023', 'YouTube items must use the exact bounded v1 item contract',
  'language placeholders are absent rather than accepted as null'
);
select throws_ok(
  $sql$select * from ingest.finalize_youtube_discovery_job(
    'fd200000-0000-4000-8000-000000000001', 'youtube-worker', 1,
    jsonb_build_object(
      'version', 1,
      'query_name', 'pokemon-tcg-booster-box-opening',
      'items', (
        select jsonb_agg(
          pg_temp.youtube_item(
            lpad(numbers.value::text, 11, '0')
          )
        )
        from generate_series(0, 25) as numbers(value)
      )
    )
  )$sql$,
  '22023', 'YouTube result must contain at most 25 items',
  'more than twenty-five items are rejected before persistence'
);
select throws_ok(
  $sql$select * from ingest.finalize_youtube_discovery_job(
    'fd200000-0000-4000-8000-000000000001', 'youtube-worker', 1,
    jsonb_build_object(
      'version', 1,
      'query_name', 'pokemon-tcg-booster-box-opening',
      'items', jsonb_build_array(
        pg_temp.youtube_item('duplicate01'),
        pg_temp.youtube_item('duplicate01')
      )
    )
  )$sql$,
  '22023', 'YouTube result identities must be unique within one query',
  'duplicate video identities fail closed'
);
select throws_ok(
  $sql$select * from ingest.finalize_youtube_discovery_job(
    'fd200000-0000-4000-8000-000000000001', 'youtube-worker', 1,
    pg_temp.youtube_result(
      'pokemon-tcg-booster-box-opening', 'controlbad1',
      E'bad\ntitle'
    )
  )$sql$,
  '22023', 'YouTube item identity, title, or version is invalid',
  'control characters in titles fail closed'
);

create temporary table downstream_before on commit drop as
select
  (select count(*) from ingest.source_items) as source_items,
  (select count(*) from ingest.extraction_runs) as extraction_runs,
  (select count(*) from ingest.openings) as openings,
  (select count(*) from ingest.batch_sightings) as batch_sightings;
create temporary table youtube_complete_one on commit drop as
select * from ingest.finalize_youtube_discovery_job(
  'fd200000-0000-4000-8000-000000000001', 'youtube-worker', 1,
  jsonb_build_object(
    'version', 1,
    'query_name', 'pokemon-tcg-booster-box-opening',
    'items', jsonb_build_array(
      pg_temp.youtube_item(
        'abcdefghijk',
        'First bounded title',
        '2026-08-20T00:00:00Z'
      ),
      pg_temp.youtube_item('modeguard01')
    )
  )
);
select is(
  (select count(*)::integer from youtube_complete_one),
  1,
  'valid bounded metadata atomically completes one job'
);
select ok(
  (select status = 'completed' and completed_at is not null
      and locked_by is null and lock_expires_at is null
   from ingest.jobs where id = 'fd200000-0000-4000-8000-000000000001'),
  'successful finalization clears the fenced job lease'
);
select ok(
  (select owner_job_id is null and owner_lease_generation is null
      and acquired_at is null and active_until is null
   from ingest.source_request_gates where source_key = 'youtube_discovery'),
  'successful finalization releases the exact request gate'
);
select is(
  (select count(*)::integer from ingest.youtube_discoveries),
  2,
  'two unique videos create exactly two dedicated cache rows'
);
select ok(
  (select source_url = 'https://www.youtube.com/watch?v=abcdefghijk'
      and title = 'First bounded title'
      and published_at = '2026-08-20 00:00:00+00'::timestamptz
      and first_seen_at = last_seen_at
      and expires_at = last_seen_at + interval '28 days'
      and not is_demo
      and source_policy_id = (
        select id from ingest.source_policies
        where source_key = 'youtube_discovery'
      )
   from ingest.youtube_discoveries where video_id = 'abcdefghijk'),
  'cache persists only exact direct API fields with a DB-clock 28-day expiry'
);
select ok(
  (select row(
      (select count(*) from ingest.source_items),
      (select count(*) from ingest.extraction_runs),
      (select count(*) from ingest.openings),
      (select count(*) from ingest.batch_sightings)
    ) = row(
      source_items, extraction_runs, openings, batch_sightings
    )
   from downstream_before),
  'YouTube finalization creates no source, extraction, opening, or batch row'
);
select ok(
  (select last_success_at is not null
      and last_attempt_at is not null
      and last_success_at >= last_attempt_at
   from ingest.source_policies where source_key = 'youtube_discovery'),
  'successful post-network finalization records policy success'
);
select is(
  (select count(*)::integer from ingest.finalize_youtube_discovery_job(
    'fd200000-0000-4000-8000-000000000001', 'youtube-worker', 1,
    pg_temp.youtube_result(
      'pokemon-tcg-booster-box-opening', 'abcdefghijk'
    )
  )),
  0,
  'repeating a completed finalizer is a no-op'
);

insert into ingest.jobs (
  id, job_type, payload, available_at, retention_until, is_demo
) values (
  'fd200000-0000-4000-8000-000000000002',
  'source.youtube.discovery',
  '{"query_name":"pokemon-tcg-booster-box-opening"}'::jsonb,
  clock_timestamp() - interval '1 minute',
  clock_timestamp() + interval '90 days',
  false
);
select * from ingest.claim_jobs_v2(
  'youtube-repeat', array['source.youtube.discovery'], 1, 600
);
select ok(
  (select not acquired and retry_at is not null
   from ingest.begin_youtube_discovery_job(
     'fd200000-0000-4000-8000-000000000002', 'youtube-repeat', 1
   )),
  'successful network use cools down the immediately following job'
);
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '10 seconds'
where source_key = 'youtube_discovery';
select ok(
  (select acquired and retry_at is null
   from ingest.begin_youtube_discovery_job(
     'fd200000-0000-4000-8000-000000000002', 'youtube-repeat', 1
   )),
  'the next job acquires after the bounded cooldown'
);
select is(
  (select count(*)::integer from ingest.finalize_youtube_discovery_job(
    'fd200000-0000-4000-8000-000000000002', 'youtube-repeat', 1,
    pg_temp.youtube_result(
      'pokemon-tcg-booster-box-opening',
      'abcdefghijk',
      'Refreshed bounded title',
      '2026-08-21T00:00:00Z'
    )
  )),
  1,
  'rediscovery finalizes through the same fenced RPC'
);
select is(
  (select count(*)::integer from ingest.youtube_discoveries),
  2,
  'rediscovery upserts by video_id without duplicating cache identity'
);
select ok(
  (select title = 'Refreshed bounded title'
      and published_at = '2026-08-21 00:00:00+00'::timestamptz
      and first_seen_at < last_seen_at
   from ingest.youtube_discoveries where video_id = 'abcdefghijk'),
  'rediscovery preserves first seen while refreshing direct API fields'
);
select ok(
  (select expires_at = last_seen_at + interval '28 days'
      and expires_at + interval '1 day'
        < last_seen_at + interval '30 days'
   from ingest.youtube_discoveries where video_id = 'abcdefghijk'),
  '28-day expiry leaves a full daily-cleanup margin below 30 days'
);

insert into ingest.jobs (
  id, job_type, payload, available_at, retention_until, is_demo
) values (
  'fd200000-0000-4000-8000-000000000003',
  'source.youtube.discovery',
  '{"query_name":"pokemon-tcg-etb-opening"}'::jsonb,
  clock_timestamp() - interval '1 minute',
  clock_timestamp() + interval '90 days',
  false
);
select * from ingest.claim_jobs_v2(
  'youtube-empty', array['source.youtube.discovery'], 1, 600
);
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '10 seconds'
where source_key = 'youtube_discovery';
select * from ingest.begin_youtube_discovery_job(
  'fd200000-0000-4000-8000-000000000003', 'youtube-empty', 1
);
select is(
  (select count(*)::integer from ingest.finalize_youtube_discovery_job(
    'fd200000-0000-4000-8000-000000000003', 'youtube-empty', 1,
    '{"version":1,"query_name":"pokemon-tcg-etb-opening","items":[]}'::jsonb
  )),
  1,
  'an empty official API result still completes the fenced job'
);
select is(
  (select count(*)::integer from ingest.youtube_discoveries),
  2,
  'an empty result invents no cache identity'
);

insert into ingest.youtube_discoveries (
  video_id, source_policy_id, source_url, title, published_at,
  first_seen_at, last_seen_at, expires_at, is_demo
) with seen as materialized (
  select clock_timestamp() as seen_at
)
select
  'expirevid01', id, 'https://www.youtube.com/watch?v=expirevid01',
  null, null,
  seen.seen_at - interval '29 days',
  seen.seen_at - interval '29 days',
  seen.seen_at - interval '1 day',
  false
from ingest.source_policies
cross join seen
where source_key = 'youtube_discovery';
insert into ingest.youtube_discoveries (
  video_id, source_policy_id, source_url, title, published_at,
  first_seen_at, last_seen_at, expires_at, is_demo
) with seen as materialized (
  select clock_timestamp() as seen_at
)
select
  'freshvideo1', id, 'https://www.youtube.com/watch?v=freshvideo1',
  null, null,
  seen.seen_at, seen.seen_at,
  seen.seen_at + interval '28 days',
  false
from ingest.source_policies
cross join seen
where source_key = 'youtube_discovery';
insert into ingest.jobs (
  id, job_type, payload, available_at, retention_until, is_demo
) values (
  'fd200000-0000-4000-8000-000000000004',
  'maintenance.cleanup', '{}'::jsonb,
  clock_timestamp() - interval '1 minute',
  clock_timestamp() + interval '90 days',
  false
);
select * from ingest.claim_jobs_v2(
  'youtube-retention', array['maintenance.cleanup'], 1, 600
);
select is(
  (select count(*)::integer from ingest.finalize_cleanup_job(
    'fd200000-0000-4000-8000-000000000004', 'youtube-retention', 1
  )),
  1,
  'retention runs only through the fenced cleanup finalizer'
);
select is(
  (select count(*)::integer from ingest.youtube_discoveries
   where video_id = 'expirevid01'),
  0,
  'expired dedicated cache rows are hard-deleted independently'
);
select is(
  (select count(*)::integer from ingest.youtube_discoveries
   where video_id = 'freshvideo1'),
  1,
  'unexpired dedicated cache rows survive cleanup'
);
select ok(
  not has_function_privilege(
    'service_role',
    'ingest.prune_expired_ephemera_v2(timestamp with time zone,integer)',
    'execute'
  ),
  'service_role cannot bypass fenced retention cleanup'
);

select is(
  pg_temp.sqlstate_of(
    $$select * from ingest.enqueue_scheduled_job_v1(
      'unapproved-live-job-test',
      date_trunc('minute', clock_timestamp()),
      'unapproved.live.job',
      '{}'::jsonb
    )$$
  ),
  '22023',
  'scheduled enqueue cannot bypass the live job-type allowlist'
);
select is(
  (select count(*)::integer
   from ingest.schedule_slots
   where schedule_name = 'unapproved-live-job-test'),
  0,
  'a rejected scheduled job rolls back its durable slot reservation'
);
select is(
  pg_temp.sqlstate_of(
    $$select * from ingest.enqueue_scheduled_job_v1(
      'unapproved-youtube-payload-test',
      date_trunc('minute', clock_timestamp()),
      'source.youtube.discovery',
      '{"query_name":"unapproved-query"}'::jsonb
    )$$
  ),
  '22023',
  'scheduled YouTube enqueue requires one exact approved query payload'
);

select * from finish();
rollback;
