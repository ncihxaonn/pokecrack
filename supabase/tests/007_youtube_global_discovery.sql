-- Live global YouTube metadata discovery, provenance, fencing, and retention.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select plan(82);

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

create function pg_temp.sqlstate_of_deferred(statement text)
returns text
language plpgsql
volatile
as $$
declare
  caught_sqlstate text;
begin
  execute statement;
  set constraints all immediate;
  return null;
exception
  when others then
    caught_sqlstate := sqlstate;
    set constraints all deferred;
    return caught_sqlstate;
end;
$$;

create function pg_temp.youtube_item(
  video_id text,
  query_name text,
  channel_country_code text default null,
  title text default 'Bounded metadata discovery'
)
returns jsonb
language sql
volatile
as $$
  select jsonb_build_object(
    'external_id', video_id,
    'source_url', 'https://www.youtube.com/watch?v=' || video_id,
    'normalized_url', 'https://www.youtube.com/watch?v=' || video_id,
    'title', title,
    'text_excerpt', null,
    'published_at', null,
    'author_hash', null,
    'content_hash', null,
    'language', 'en',
    'metadata', jsonb_build_object(
      'query_name', query_name,
      'metadata_only', true,
      'media_download', false,
      'discovery_scope', 'global',
      'geography_status', case
        when channel_country_code is null then 'unresolved'
        else 'channel_country_proxy'
      end,
      'evidence_tier', 'D',
      'statistics_eligible', false,
      'parser_version', 'youtube-metadata-v1',
      'product_type_hints', jsonb_build_array('booster_box'),
      'batch_code_hints', jsonb_build_array('AB12-XY'),
      'channel_country_code', channel_country_code,
      'geography_basis', case
        when channel_country_code is null then 'unresolved'
        else 'youtube_channel_country'
      end
    ),
    'collector_version', 'youtube-global-discovery-v1',
    'source_policy_version', 'youtube-global-discovery-v1'
  );
$$;

create function pg_temp.youtube_result(
  query_name text,
  video_id text,
  channel_country_code text default null,
  title text default 'Bounded metadata discovery'
)
returns jsonb
language sql
volatile
as $$
  select jsonb_build_object(
    'version', 1,
    'query_name', query_name,
    'items', jsonb_build_array(
      pg_temp.youtube_item(video_id, query_name, channel_country_code, title)
    )
  );
$$;

select has_table('ingest', 'source_discoveries', 'private source discovery provenance exists');
select col_is_null('ingest', 'source_items', 'content_hash', 'metadata-only source items may have no content hash');
select ok(
  (select i.indisunique
      and pg_get_indexdef(i.indexrelid) ilike '%(normalized_url, is_demo)%'
   from pg_index i
   where i.indexrelid = 'ingest.source_items_normalized_url_uidx'::regclass),
  'normalized URL identity is unique inside live/demo mode'
);
select ok(
  (select i.indisunique
      and pg_get_indexdef(i.indexrelid) ilike '%(platform, external_id, is_demo)%'
   from pg_index i
   where i.indexrelid = 'ingest.source_items_platform_external_uidx'::regclass),
  'platform identity is unique inside live/demo mode'
);
select ok(
  (select enabled
      and not is_demo
      and display_name = 'YouTube Global Discovery API'
      and source_kind = 'official_api'
      and domain = 'youtube.googleapis.com'
      and base_url = 'https://youtube.googleapis.com/youtube/v3'
      and collector_type = 'official_api'
      and access_mode = 'official_api'
      and robots_policy = 'not_applicable'
      and routes = array['official_api']::text[]
      and not include_subdomains
      and min_delay_seconds = 2
      and max_pages_per_run = 2
      and max_items_per_run = 50
      and max_concurrency = 1
      and browser_profile is null
      and not statistics_eligible_default
      and retention_days = 30
      and version = 'youtube-global-discovery-v1'
      and expected_interval_seconds = 21600
   from ingest.source_policies
   where source_key = 'youtube_discovery'),
  'the exact bounded live YouTube policy is provisioned'
);
select matches(
  (select pg_get_constraintdef(oid)
   from pg_constraint
   where conrelid = 'ingest.source_request_gates'::regclass
     and conname = 'source_request_gates_source_check'),
  '\^\[a-z0-9\]',
  'request gates accept canonical source keys instead of one hard-coded source'
);
select is(
  (select count(*)::integer from ingest.source_request_gates
   where source_key in ('tcgdex_catalog', 'youtube_discovery')),
  2,
  'both bounded official API sources have durable gates'
);
select ok(
  (select owner_job_id is null and owner_lease_generation is null
      and acquired_at is null and active_until is null
   from ingest.source_request_gates where source_key = 'youtube_discovery'),
  'YouTube request gate starts unowned'
);
select ok(
  (select relrowsecurity and relforcerowsecurity
   from pg_class where oid = 'ingest.source_discoveries'::regclass),
  'source discoveries force RLS'
);
select ok(
  has_table_privilege('service_role', 'ingest.source_discoveries', 'select')
    and not has_table_privilege('service_role', 'ingest.source_discoveries', 'insert')
    and not has_table_privilege('service_role', 'ingest.source_discoveries', 'update')
    and not has_table_privilege('service_role', 'ingest.source_discoveries', 'delete'),
  'service_role may inspect but never directly mutate provenance'
);
select ok(
  not has_table_privilege('anon', 'ingest.source_discoveries', 'select')
    and not has_table_privilege('authenticated', 'ingest.source_discoveries', 'select'),
  'public roles cannot inspect private discovery provenance'
);
select is(
  (select count(*)::integer
   from pg_trigger
   where not tgisinternal
     and tgrelid in (
       'ingest.source_items'::regclass,
       'ingest.extraction_runs'::regclass,
       'ingest.openings'::regclass,
       'ingest.batch_sightings'::regclass
     )
     and tgname in (
       'source_items_reject_youtube_discovery_duplicate_cluster',
       'source_items_reject_youtube_discovery_policy_rebind',
       'extraction_runs_reject_youtube_discovery',
       'openings_reject_youtube_discovery',
       'batch_sightings_reject_youtube_discovery'
     )
     and tgenabled = 'O'),
  5,
  'metadata-only promotion and duplicate-cluster invariants are enabled on every boundary'
);
select is(
  (select count(*)::integer
   from pg_trigger
   where not tgisinternal
     and tgname in (
       'source_items_enforce_youtube_discovery_end_state',
       'source_discoveries_enforce_youtube_discovery_end_state',
       'extraction_runs_enforce_youtube_discovery_end_state',
       'openings_enforce_youtube_discovery_end_state',
       'batch_sightings_enforce_youtube_discovery_end_state'
     )
     and tgconstraint <> 0
     and tgdeferrable
     and tginitdeferred
     and tgenabled = 'O'),
  5,
  'deferred end-state invariants close sibling writable-CTE snapshot gaps'
);
select ok(
  not has_function_privilege(
    'service_role',
    'ingest.is_youtube_discovery_metadata_source(uuid,uuid)',
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'ingest.reject_youtube_discovery_evidence_reference()',
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'ingest.reject_youtube_discovery_duplicate_cluster()',
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'ingest.reject_youtube_discovery_policy_rebind()',
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'ingest.enforce_youtube_discovery_metadata_end_state()',
    'execute'
  ),
  'service_role cannot invoke or replace trigger-only metadata classifiers'
);
select has_function(
  'ingest', 'begin_youtube_discovery_job', array['uuid', 'text', 'bigint'],
  'typed YouTube pre-network gate exists'
);
select ok(
  (select prosecdef from pg_proc
   where oid = 'ingest.begin_youtube_discovery_job(uuid,text,bigint)'::regprocedure),
  'YouTube begin is SECURITY DEFINER'
);
select ok(
  has_function_privilege(
    'service_role', 'ingest.begin_youtube_discovery_job(uuid,text,bigint)', 'execute'
  ) and not has_function_privilege(
    'anon', 'ingest.begin_youtube_discovery_job(uuid,text,bigint)', 'execute'
  ),
  'only the service boundary can begin YouTube discovery'
);
select has_function(
  'ingest', 'finalize_youtube_discovery_job',
  array['uuid', 'text', 'bigint', 'jsonb'],
  'typed YouTube finalizer exists'
);
select ok(
  (select prosecdef and proretset and prorettype = 'ingest.jobs'::regtype
   from pg_proc
   where oid = 'ingest.finalize_youtube_discovery_job(uuid,text,bigint,jsonb)'::regprocedure),
  'YouTube finalizer is SECURITY DEFINER and returns the completed job'
);
select ok(
  has_function_privilege(
    'service_role',
    'ingest.finalize_youtube_discovery_job(uuid,text,bigint,jsonb)', 'execute'
  ) and not has_function_privilege(
    'anon', 'ingest.finalize_youtube_discovery_job(uuid,text,bigint,jsonb)', 'execute'
  ),
  'only the service boundary can finalize YouTube discovery'
);
select ok(
  not exists (
    select 1
    from pg_proc p
    cross join lateral aclexplode(coalesce(p.proacl, acldefault('f', p.proowner))) acl
    where p.oid = 'ingest.finalize_youtube_discovery_job(uuid,text,bigint,jsonb)'::regprocedure
      and acl.grantee = 0
      and acl.privilege_type = 'EXECUTE'
  ),
  'PUBLIC cannot finalize YouTube discovery'
);
select ok(
  not exists (
    select 1 from information_schema.columns
    where table_schema = 'ingest' and table_name = 'source_discoveries'
      and column_name in ('country_code', 'region_id', 'store_id', 'retailer_id')
  ),
  'discovery provenance has no observed-opening geography columns'
);
select is(
  (select count(*)::integer
   from pg_constraint
   where conrelid in (
       'ingest.source_items'::regclass,
       'ingest.jobs'::regclass
     )
     and conname in ('source_items_id_mode_unique', 'jobs_id_mode_unique')
     and contype = 'u'),
  2,
  'source item and job identities expose immutable composite mode keys'
);
select ok(
  (select pg_get_constraintdef(oid) =
      'FOREIGN KEY (source_item_id, is_demo) REFERENCES ingest.source_items(id, is_demo) ON UPDATE RESTRICT ON DELETE CASCADE'
   from pg_constraint
   where conrelid = 'ingest.source_discoveries'::regclass
     and conname = 'source_discoveries_source_item_mode_fkey')
  and
  (select pg_get_constraintdef(oid) =
      'FOREIGN KEY (job_id, is_demo) REFERENCES ingest.jobs(id, is_demo) ON UPDATE RESTRICT ON DELETE RESTRICT'
   from pg_constraint
   where conrelid = 'ingest.source_discoveries'::regclass
     and conname = 'source_discoveries_job_mode_fkey'),
  'source discovery provenance binds source and job mode without update cascades'
);

-- Prove live identities can coexist with visibly synthetic fixtures.
insert into ingest.source_policies (
  id, source_key, display_name, source_kind, domain, base_url, enabled,
  collector_type, access_mode, robots_policy, routes, statistics_eligible_default,
  retention_days, config, version, expected_interval_seconds, is_demo
) values (
  'fd000000-0000-4000-8000-000000000001', 'youtube_demo_test',
  'YouTube Demo Test', 'fixture', 'youtube.demo.invalid',
  'https://youtube.demo.invalid', false, 'manual_import', 'manual',
  'not_applicable', array['manual_import'], false, 30, '{}', 'test-v1', 3600, true
);
insert into ingest.source_items (
  id, source_policy_id, platform, external_id, source_url, normalized_url,
  domain, title, content_hash, collector_type, collector_version,
  source_policy_version, access_mode, usage_classification, source_kind,
  language, status, metadata, expires_at, is_demo
) values (
  'fd100000-0000-4000-8000-000000000001',
  'fd000000-0000-4000-8000-000000000001',
  'youtube', 'abcdefghijk',
  'https://www.youtube.com/watch?v=abcdefghijk',
  'https://www.youtube.com/watch?v=abcdefghijk',
  'youtube.com', 'Synthetic duplicate identity', null, 'manual_import',
  'test-v1', 'test-v1', 'manual', 'activity_only', 'fixture', 'en',
  'activity_only', '{"synthetic":true}', clock_timestamp() + interval '30 days', true
);
select is(
  (select count(*)::integer from ingest.source_items
   where platform = 'youtube' and external_id = 'abcdefghijk' and is_demo),
  1,
  'a synthetic YouTube identity is explicitly demo-scoped'
);

insert into ingest.jobs (
  id, job_type, payload, status, priority, attempts, max_attempts,
  available_at, retention_until, is_demo
) values (
  'fd200000-0000-4000-8000-000000000001', 'source.youtube.discovery',
  '{"query_name":"pokemon-tcg-booster-box-opening"}', 'pending', 100,
  0, 5, clock_timestamp() - interval '1 minute',
  clock_timestamp() + interval '90 days', false
);
insert into ingest.jobs (
  id, job_type, payload, status, priority, attempts, max_attempts,
  available_at, retention_until, is_demo
) values (
  'fd200000-0000-4000-8000-000000000010',
  'source.youtube.discovery.mode-test', '{}', 'pending', 0, 0, 5,
  clock_timestamp() + interval '1 day', clock_timestamp() + interval '90 days', true
);
create temporary table youtube_claim_one on commit drop as
select * from ingest.claim_jobs_v2(
  'youtube-worker', array['source.youtube.discovery'], 1, 600
);
select is((select count(*)::integer from youtube_claim_one), 1, 'a YouTube job can be claimed once');
select is((select lease_generation from youtube_claim_one), 1::bigint, 'first YouTube claim receives generation one');

update ingest.source_policies
set last_attempt_at = null
where source_key = 'youtube_discovery';
create temporary table youtube_begin_one on commit drop as
select * from ingest.begin_youtube_discovery_job(
  'fd200000-0000-4000-8000-000000000001', 'youtube-worker', 1
);
select ok(
  (select count(*) = 1 and bool_and(acquired) and max(retry_at) is null
   from youtube_begin_one),
  'a valid allowlisted job acquires the pre-network gate'
);
select ok(
  (select gates.owner_job_id = jobs.id
      and gates.owner_lease_generation = jobs.lease_generation
      and gates.active_until = jobs.lock_expires_at
      and gates.active_until >= gates.acquired_at + interval '75 seconds'
   from ingest.source_request_gates gates
   join ingest.jobs jobs on jobs.id = gates.owner_job_id
   where gates.source_key = 'youtube_discovery'),
  'begin persists the exact job generation and a transport-safe lease'
);
select is(
  (select count(*)::integer from ingest.heartbeat_job_v2(
    'fd200000-0000-4000-8000-000000000001', 'youtube-worker', 2, 600
  )),
  0,
  'a stale heartbeat cannot renew a YouTube lease or gate'
);
select is(
  (select count(*)::integer from ingest.heartbeat_job_v2(
    'fd200000-0000-4000-8000-000000000001', 'youtube-worker', 1, 600
  )),
  1,
  'the current heartbeat renews the YouTube lease'
);
select ok(
  (select gates.active_until = jobs.lock_expires_at
   from ingest.source_request_gates gates
   join ingest.jobs jobs on jobs.id = gates.owner_job_id
   where gates.source_key = 'youtube_discovery'),
  'generalized heartbeat keeps the matching YouTube gate aligned'
);

select throws_ok(
  $$select * from ingest.finalize_youtube_discovery_job(
    'fd200000-0000-4000-8000-000000000001', 'youtube-worker', 1,
    '{"version":1,"query_name":"pokemon-tcg-booster-box-opening","items":[],"extra":true}'::jsonb
  )$$,
  '22023', 'YouTube result must match the exact bounded v1 contract',
  'unexpected result keys are rejected before persistence'
);
select ok(
  (select status = 'running' from ingest.jobs
   where id = 'fd200000-0000-4000-8000-000000000001')
    and (select owner_job_id = 'fd200000-0000-4000-8000-000000000001'::uuid
         from ingest.source_request_gates where source_key = 'youtube_discovery'),
  'contract rejection leaves the job and request gate untouched'
);

create temporary table youtube_completed_one on commit drop as
select * from ingest.finalize_youtube_discovery_job(
  'fd200000-0000-4000-8000-000000000001', 'youtube-worker', 1,
  jsonb_build_object(
    'version', 1,
    'query_name', 'pokemon-tcg-booster-box-opening',
    'items', jsonb_build_array(
      pg_temp.youtube_item(
        'abcdefghijk', 'pokemon-tcg-booster-box-opening', 'US'
      ),
      pg_temp.youtube_item(
        'modeguard01', 'pokemon-tcg-booster-box-opening', null
      )
    )
  )
);
select is(
  (select count(*)::integer from youtube_completed_one),
  1,
  'fresh metadata finalizes through the null-only duplicate-cluster guard'
);
select ok(
  (select status = 'completed' and completed_at is not null
      and locked_by is null and lock_expires_at is null
   from ingest.jobs where id = 'fd200000-0000-4000-8000-000000000001'),
  'valid finalization atomically completes and unlocks the job'
);
select ok(
  (select owner_job_id is null and owner_lease_generation is null
      and acquired_at is null and active_until is null
   from ingest.source_request_gates where source_key = 'youtube_discovery'),
  'valid finalization releases the exact request gate'
);
select ok(
  (select platform = 'youtube'
      and domain = 'youtube.com'
      and content_hash is null
      and collector_type = 'official_api'
      and access_mode = 'official_api'
      and usage_classification = 'activity_only'
      and status = 'activity_only'
      and source_kind = 'official_api'
      and language = 'en'
      and not is_demo
      and expires_at > clock_timestamp() + interval '29 days'
      and expires_at <= clock_timestamp() + interval '30 days 1 minute'
   from ingest.source_items
   where platform = 'youtube' and external_id = 'abcdefghijk' and not is_demo),
  'YouTube metadata is forced to private live activity-only fields and 30-day retention'
);
select ok(
  (select query_name = 'pokemon-tcg-booster-box-opening'
      and result_rank = 1
      and channel_country_code = 'US'
      and geography_status = 'channel_country_proxy'
      and geography_basis = 'youtube_channel_country'
      and not is_demo
   from ingest.source_discoveries
   where source_item_id = (
     select id from ingest.source_items
     where platform = 'youtube' and external_id = 'abcdefghijk' and not is_demo
   )),
  'official channel country is stored only as a labelled proxy in provenance'
);
select is(
  (select count(*)::integer from ingest.source_items
   where platform = 'youtube' and external_id = 'abcdefghijk'),
  2,
  'the same upstream identity can coexist once per live/demo mode'
);
select is(
  pg_temp.sqlstate_of($sql$
    update ingest.source_items
    set is_demo = true
    where platform = 'youtube' and external_id = 'modeguard01' and not is_demo
  $sql$),
  '23503',
  'composite provenance prevents rebinding a live source item into demo mode'
);
select is(
  pg_temp.sqlstate_of($sql$
    update ingest.jobs
    set is_demo = true
    where id = 'fd200000-0000-4000-8000-000000000001'
  $sql$),
  '23503',
  'composite provenance prevents rebinding its live job into demo mode'
);
select is(
  pg_temp.sqlstate_of($sql$
    insert into ingest.source_discoveries (
      source_item_id, query_name, job_id, first_seen_at, last_seen_at,
      result_rank, geography_status, geography_basis, is_demo
    ) values (
      'fd100000-0000-4000-8000-000000000001',
      'pokemon-tcg-etb-opening',
      'fd200000-0000-4000-8000-000000000001',
      clock_timestamp(), clock_timestamp(), 40,
      'unresolved', 'unresolved', false
    )
  $sql$),
  '23503',
  'a live provenance row cannot reference a demo source item'
);
select is(
  pg_temp.sqlstate_of($sql$
    insert into ingest.source_discoveries (
      source_item_id, query_name, job_id, first_seen_at, last_seen_at,
      result_rank, geography_status, geography_basis, is_demo
    ) values (
      (select id from ingest.source_items
       where platform = 'youtube' and external_id = 'modeguard01' and not is_demo),
      'pokemon-tcg-etb-opening',
      'fd200000-0000-4000-8000-000000000010',
      clock_timestamp(), clock_timestamp(), 41,
      'unresolved', 'unresolved', false
    )
  $sql$),
  '23503',
  'a live provenance row cannot reference a demo job'
);
select is(
  (select count(*)::integer from ingest.openings
   where source_item_id = (
     select id from ingest.source_items
     where platform = 'youtube' and external_id = 'abcdefghijk' and not is_demo
   )),
  0,
  'metadata discovery creates no statistical opening'
);
select is(
  (select count(*)::integer from ingest.finalize_youtube_discovery_job(
    'fd200000-0000-4000-8000-000000000001', 'youtube-worker', 1,
    pg_temp.youtube_result('pokemon-tcg-booster-box-opening', 'abcdefghijk', 'US')
  )),
  0,
  'repeating a completed finalizer is a no-op'
);

-- A later job for the same query refreshes one identity and one provenance row.
insert into ingest.jobs (
  id, job_type, payload, status, priority, attempts, max_attempts,
  available_at, retention_until, is_demo
) values (
  'fd200000-0000-4000-8000-000000000002', 'source.youtube.discovery',
  '{"query_name":"pokemon-tcg-booster-box-opening"}', 'pending', 100,
  0, 5, clock_timestamp() - interval '1 minute',
  clock_timestamp() + interval '90 days', false
);
create temporary table youtube_claim_two on commit drop as
select * from ingest.claim_jobs_v2(
  'youtube-worker', array['source.youtube.discovery'], 1, 600
);
create temporary table youtube_success_cooldown on commit drop as
select * from ingest.begin_youtube_discovery_job(
  'fd200000-0000-4000-8000-000000000002', 'youtube-worker', 1
);
select ok(
  (select not cooldown.acquired
      and cooldown.retry_at >= policies.last_attempt_at + interval '2 seconds'
   from youtube_success_cooldown as cooldown
   cross join ingest.source_policies as policies
   where policies.source_key = 'youtube_discovery'),
  'a successful post-network finalizer cools down the next job for two seconds'
);
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '3 seconds'
where source_key = 'youtube_discovery';
select * from ingest.begin_youtube_discovery_job(
  'fd200000-0000-4000-8000-000000000002', 'youtube-worker', 1
);
select * from ingest.finalize_youtube_discovery_job(
  'fd200000-0000-4000-8000-000000000002', 'youtube-worker', 1,
  pg_temp.youtube_result(
    'pokemon-tcg-booster-box-opening', 'abcdefghijk', null, 'Refreshed title'
  )
);
select is(
  (select count(*)::integer from ingest.source_items
   where platform = 'youtube' and external_id = 'abcdefghijk' and not is_demo),
  1,
  'repeat discovery upserts one live source identity'
);
select ok(
  (select count(*) = 1
      and bool_and(job_id = 'fd200000-0000-4000-8000-000000000002'::uuid)
      and min(first_seen_at) <= max(last_seen_at)
      and max(channel_country_code) is null
      and max(geography_status) = 'unresolved'
      and max(geography_basis) = 'unresolved'
   from ingest.source_discoveries
   where source_item_id = (
     select id from ingest.source_items
     where platform = 'youtube' and external_id = 'abcdefghijk' and not is_demo
   )),
  'repeat discovery preserves first seen and refreshes latest unresolved provenance'
);
select is(
  (select title from ingest.source_items
   where platform = 'youtube' and external_id = 'abcdefghijk' and not is_demo),
  'Refreshed title',
  'repeat discovery refreshes bounded metadata without duplicating identity'
);

-- Rediscovery refreshes metadata/provenance but cannot demote a later reviewed
-- evidence decision or erase its processing history.
update ingest.source_items
set usage_classification = 'statistics',
    status = 'accepted',
    attempt_count = 4,
    last_error_code = 'review-note',
    last_error_message = 'preserve reviewed processing history',
    last_error_at = clock_timestamp()
where platform = 'youtube' and external_id = 'abcdefghijk' and not is_demo;
insert into ingest.jobs (
  id, job_type, payload, status, priority, attempts, max_attempts,
  available_at, retention_until, is_demo
) values (
  'fd200000-0000-4000-8000-000000000008', 'source.youtube.discovery',
  '{"query_name":"pokemon-tcg-booster-box-opening"}', 'pending', 100,
  0, 5, clock_timestamp() - interval '1 minute',
  clock_timestamp() + interval '90 days', false
);
select * from ingest.claim_jobs_v2(
  'youtube-reviewed', array['source.youtube.discovery'], 1, 600
);
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '3 seconds'
where source_key = 'youtube_discovery';
select * from ingest.begin_youtube_discovery_job(
  'fd200000-0000-4000-8000-000000000008', 'youtube-reviewed', 1
);
select * from ingest.finalize_youtube_discovery_job(
  'fd200000-0000-4000-8000-000000000008', 'youtube-reviewed', 1,
  pg_temp.youtube_result(
    'pokemon-tcg-booster-box-opening', 'abcdefghijk', 'CA', 'Reviewed refresh'
  )
);
select ok(
  (select usage_classification = 'statistics'
      and status = 'accepted'
      and attempt_count = 4
      and last_error_code = 'review-note'
      and last_error_message = 'preserve reviewed processing history'
      and last_error_at is not null
   from ingest.source_items
   where platform = 'youtube' and external_id = 'abcdefghijk' and not is_demo),
  'rediscovery preserves reviewed evidence decisions, attempts, and errors'
);

-- Control characters fail closed, while a valid zero-item API response is a
-- successful discovery run rather than a fabricated observation.
insert into ingest.jobs (
  id, job_type, payload, status, priority, attempts, max_attempts,
  available_at, retention_until, is_demo
) values (
  'fd200000-0000-4000-8000-000000000009', 'source.youtube.discovery',
  '{"query_name":"pokemon-tcg-etb-opening"}', 'pending', 100,
  0, 5, clock_timestamp() - interval '1 minute',
  clock_timestamp() + interval '90 days', false
);
select * from ingest.claim_jobs_v2(
  'youtube-empty', array['source.youtube.discovery'], 1, 600
);
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '3 seconds'
where source_key = 'youtube_discovery';
select * from ingest.begin_youtube_discovery_job(
  'fd200000-0000-4000-8000-000000000009', 'youtube-empty', 1
);
select throws_ok(
  $$select * from ingest.finalize_youtube_discovery_job(
    'fd200000-0000-4000-8000-000000000009', 'youtube-empty', 1,
    jsonb_build_object(
      'version', 1,
      'query_name', 'pokemon-tcg-etb-opening',
      'items', jsonb_build_array(
        jsonb_set(
          pg_temp.youtube_item(
            'control0001', 'pokemon-tcg-etb-opening', null
          ),
          '{title}',
          to_jsonb('bad' || chr(1))
        )
      )
    )
  )$$,
  '22023', 'YouTube item identity, hash, language, text, or version is invalid',
  'disallowed control characters fail closed before persistence'
);
select is(
  (select count(*)::integer from ingest.finalize_youtube_discovery_job(
    'fd200000-0000-4000-8000-000000000009', 'youtube-empty', 1,
    '{"version":1,"query_name":"pokemon-tcg-etb-opening","items":[]}'::jsonb
  )),
  1,
  'a valid empty result completes without inventing a source item'
);

-- Pre- and post-network policy kill switches fail closed.
insert into ingest.jobs (
  id, job_type, payload, status, priority, attempts, max_attempts,
  available_at, retention_until, is_demo
) values (
  'fd200000-0000-4000-8000-000000000003', 'source.youtube.discovery',
  '{"query_name":"pokemon-tcg-etb-opening"}', 'pending', 100,
  0, 5, clock_timestamp() - interval '1 minute',
  clock_timestamp() + interval '90 days', false
);
select * from ingest.claim_jobs_v2(
  'youtube-kill-pre', array['source.youtube.discovery'], 1, 600
);
update ingest.source_policies set enabled = false where source_key = 'youtube_discovery';
select throws_ok(
  $$select * from ingest.begin_youtube_discovery_job(
    'fd200000-0000-4000-8000-000000000003', 'youtube-kill-pre', 1
  )$$,
  '55000', 'live YouTube discovery source policy is unavailable or disabled',
  'disabled policy blocks network acquisition'
);
select ok(
  (select owner_job_id is null from ingest.source_request_gates
   where source_key = 'youtube_discovery'),
  'pre-network kill switch grants no request gate'
);
update ingest.source_policies set enabled = true where source_key = 'youtube_discovery';
select * from ingest.fail_job_v2(
  'fd200000-0000-4000-8000-000000000003', 'youtube-kill-pre', 1,
  'policy_disabled', 'bounded test failure', false
);

insert into ingest.jobs (
  id, job_type, payload, status, priority, attempts, max_attempts,
  available_at, retention_until, is_demo
) values (
  'fd200000-0000-4000-8000-000000000004', 'source.youtube.discovery',
  '{"query_name":"pokemon-tcg-booster-bundle-opening"}', 'pending', 100,
  0, 5, clock_timestamp() - interval '1 minute',
  clock_timestamp() + interval '90 days', false
);
select * from ingest.claim_jobs_v2(
  'youtube-kill-post', array['source.youtube.discovery'], 1, 600
);
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '3 seconds'
where source_key = 'youtube_discovery';
select * from ingest.begin_youtube_discovery_job(
  'fd200000-0000-4000-8000-000000000004', 'youtube-kill-post', 1
);
update ingest.source_policies set enabled = false where source_key = 'youtube_discovery';
select throws_ok(
  $$select * from ingest.finalize_youtube_discovery_job(
    'fd200000-0000-4000-8000-000000000004', 'youtube-kill-post', 1,
    '{"version":1,"query_name":"pokemon-tcg-booster-bundle-opening","items":[]}'::jsonb
  )$$,
  '55000', 'live YouTube discovery source policy is unavailable or disabled',
  'policy changes after network I/O abort all persistence'
);
select ok(
  (select status = 'running' from ingest.jobs
   where id = 'fd200000-0000-4000-8000-000000000004')
    and (select owner_job_id = 'fd200000-0000-4000-8000-000000000004'::uuid
         from ingest.source_request_gates where source_key = 'youtube_discovery'),
  'post-network kill switch leaves the fenced job and gate for failure handling'
);
update ingest.source_policies set enabled = true where source_key = 'youtube_discovery';
select * from ingest.fail_job_v2(
  'fd200000-0000-4000-8000-000000000004', 'youtube-kill-post', 1,
  'policy_disabled', 'bounded test failure', false
);
select ok(
  (select owner_job_id is null and owner_lease_generation is null
   from ingest.source_request_gates where source_key = 'youtube_discovery'),
  'generalized failure releases the current YouTube request gate'
);

-- Existing live identities cannot be silently rebound by a conflicting URL.
insert into ingest.source_policies (
  id, source_key, display_name, source_kind, domain, base_url, enabled,
  collector_type, access_mode, robots_policy, routes, statistics_eligible_default,
  retention_days, config, version, expected_interval_seconds, is_demo
) values (
  'fd000000-0000-4000-8000-000000000002', 'youtube_conflict_test',
  'YouTube Conflict Test', 'manual_import', 'youtube-conflict.invalid',
  'https://youtube-conflict.invalid', false, 'manual_import', 'manual',
  'not_applicable', array['manual_import'], false, 30, '{}', 'test-v1', 3600, false
);
insert into ingest.source_items (
  id, source_policy_id, platform, external_id, source_url, normalized_url,
  domain, title, content_hash, collector_type, collector_version,
  source_policy_version, access_mode, usage_classification, source_kind,
  language, status, metadata, expires_at, is_demo
) values (
  'fd100000-0000-4000-8000-000000000002',
  'fd000000-0000-4000-8000-000000000002',
  'youtube', 'zzzzzzzzzzz',
  'https://www.youtube.com/watch?v=zzzzzzzzzzz',
  'https://www.youtube.com/watch?v=yyyyyyyyyyy',
  'youtube.com', 'Conflicting identity', null, 'manual_import', 'test-v1',
  'test-v1', 'manual', 'activity_only', 'manual_import', 'en',
  'activity_only', '{}', clock_timestamp() + interval '30 days', false
);
insert into ingest.jobs (
  id, job_type, payload, status, priority, attempts, max_attempts,
  available_at, retention_until, is_demo
) values (
  'fd200000-0000-4000-8000-000000000005', 'source.youtube.discovery',
  '{"query_name":"pokemon-tcg-pack-opening"}', 'pending', 100,
  0, 5, clock_timestamp() - interval '1 minute',
  clock_timestamp() + interval '90 days', false
);
select * from ingest.claim_jobs_v2(
  'youtube-conflict', array['source.youtube.discovery'], 1, 600
);
create temporary table youtube_failure_cooldown on commit drop as
select * from ingest.begin_youtube_discovery_job(
  'fd200000-0000-4000-8000-000000000005', 'youtube-conflict', 1
);
select ok(
  (select not cooldown.acquired
      and cooldown.retry_at >= policies.last_attempt_at + interval '2 seconds'
      and policies.last_failure_at = policies.last_attempt_at
   from youtube_failure_cooldown as cooldown
   cross join ingest.source_policies as policies
   where policies.source_key = 'youtube_discovery'),
  'a fenced post-network failure records attention and cools down the next job'
);
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '3 seconds'
where source_key = 'youtube_discovery';
select * from ingest.begin_youtube_discovery_job(
  'fd200000-0000-4000-8000-000000000005', 'youtube-conflict', 1
);
select throws_ok(
  $$select * from ingest.finalize_youtube_discovery_job(
    'fd200000-0000-4000-8000-000000000005', 'youtube-conflict', 1,
    jsonb_build_object(
      'version', 1,
      'query_name', 'pokemon-tcg-pack-opening',
      'items', jsonb_build_array(
        pg_temp.youtube_item(
          'rollback001', 'pokemon-tcg-pack-opening', null
        ),
        pg_temp.youtube_item(
          'yyyyyyyyyyy', 'pokemon-tcg-pack-opening', null
        )
      )
    )
  )$$,
  '23505', 'YouTube discovery identity conflicts with an existing live source item',
  'a normalized URL cannot be rebound to another platform identity'
);
select is(
  (select count(*)::integer from ingest.source_items
   where platform = 'youtube'
     and external_id in ('rollback001', 'yyyyyyyyyyy')),
  0,
  'a later identity conflict rolls back earlier source effects atomically'
);
select * from ingest.fail_job_v2(
  'fd200000-0000-4000-8000-000000000005', 'youtube-conflict', 1,
  'identity_conflict', 'bounded test failure', false
);

-- Exact parser metadata and item count bounds roll back before any upsert.
insert into ingest.jobs (
  id, job_type, payload, status, priority, attempts, max_attempts,
  available_at, retention_until, is_demo
) values (
  'fd200000-0000-4000-8000-000000000006', 'source.youtube.discovery',
  '{"query_name":"pokemon-tcg-opening-batch-code"}', 'pending', 100,
  0, 5, clock_timestamp() - interval '1 minute',
  clock_timestamp() + interval '90 days', false
);
select * from ingest.claim_jobs_v2(
  'youtube-bounds', array['source.youtube.discovery'], 1, 600
);
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '3 seconds'
where source_key = 'youtube_discovery';
select * from ingest.begin_youtube_discovery_job(
  'fd200000-0000-4000-8000-000000000006', 'youtube-bounds', 1
);
select throws_ok(
  $$select * from ingest.finalize_youtube_discovery_job(
    'fd200000-0000-4000-8000-000000000006', 'youtube-bounds', 1,
    jsonb_build_object(
      'version', 1,
      'query_name', 'pokemon-tcg-opening-batch-code',
      'items', (
        select jsonb_agg(pg_temp.youtube_item(
          lpad(index::text, 11, 'x'), 'pokemon-tcg-opening-batch-code', null
        ))
        from generate_series(1, 51) as values(index)
      )
    )
  )$$,
  '22023', 'YouTube result must contain at most 50 items',
  'more than fifty metadata items are rejected before persistence'
);
select is(
  (select count(*)::integer from ingest.source_items
   where source_policy_id = (
     select id from ingest.source_policies where source_key = 'youtube_discovery'
   ) and external_id like 'xxxxxxxx%'),
  0,
  'oversized item arrays persist nothing'
);
select * from ingest.fail_job_v2(
  'fd200000-0000-4000-8000-000000000006', 'youtube-bounds', 1,
  'bounded_contract', 'bounded test failure', false
);

-- The immutable provenance clock is authoritative for hard 30-day deletion.
-- Even a broad service role may rebind the policy and extend the cached expiry,
-- but it cannot promote the discovery row into evidence or a dedupe cluster.
create temporary table youtube_expired_identity on commit drop as
select id
from ingest.source_items
where platform = 'youtube' and external_id = 'abcdefghijk' and not is_demo;
update ingest.source_discoveries
set first_seen_at = clock_timestamp() - interval '40 days',
    last_seen_at = clock_timestamp() - interval '40 days'
where source_item_id = (
  select id from ingest.source_items
  where platform = 'youtube' and external_id = 'abcdefghijk' and not is_demo
);

insert into ingest.source_items (
  id, source_policy_id, platform, external_id, source_url, normalized_url,
  domain, title, content_hash, collector_type, collector_version,
  source_policy_version, access_mode, usage_classification, source_kind,
  language, status, metadata, expires_at, is_demo
) values
  (
    'fd100000-0000-4000-8000-000000000003',
    'fd000000-0000-4000-8000-000000000002',
    'manual-test', 'cluster-member',
    'https://youtube-conflict.invalid/cluster-member',
    'https://youtube-conflict.invalid/cluster-member',
    'youtube-conflict.invalid', 'Ordinary cluster member', null,
    'manual_import', 'test-v1', 'test-v1', 'manual', 'activity_only',
    'manual_import', 'en', 'activity_only', '{}',
    clock_timestamp() + interval '30 days', false
  ),
  (
    'fd100000-0000-4000-8000-000000000004',
    'fd000000-0000-4000-8000-000000000002',
    'manual-test', 'cluster-target',
    'https://youtube-conflict.invalid/cluster-target',
    'https://youtube-conflict.invalid/cluster-target',
    'youtube-conflict.invalid', 'Ordinary cluster target', null,
    'manual_import', 'test-v1', 'test-v1', 'manual', 'activity_only',
    'manual_import', 'en', 'activity_only', '{}',
    clock_timestamp() + interval '30 days', false
  ),
  (
    'fd100000-0000-4000-8000-000000000005',
    'fd000000-0000-4000-8000-000000000002',
    'manual-test', 'writable-cte-source',
    'https://youtube-conflict.invalid/writable-cte-source',
    'https://youtube-conflict.invalid/writable-cte-source',
    'youtube-conflict.invalid', 'Ordinary unreferenced source', null,
    'manual_import', 'test-v1', 'test-v1', 'manual', 'activity_only',
    'manual_import', 'en', 'activity_only', '{}',
    clock_timestamp() + interval '30 days', false
  );
update ingest.source_items
set duplicate_cluster_id = 'fd100000-0000-4000-8000-000000000004'
where id = 'fd100000-0000-4000-8000-000000000003';

grant usage on schema extensions to service_role;
set local role service_role;
select is(
  pg_temp.sqlstate_of($sql$
    with rebound as (
      update ingest.source_items
      set source_policy_id = (
        select id from ingest.source_policies where source_key = 'youtube_discovery'
      )
      where id = 'fd100000-0000-4000-8000-000000000005'
      returning id
    )
    insert into ingest.extraction_runs (
      id, source_item_id, stage, provider, model, prompt_version, input_hash,
      started_at, expires_at, is_demo
    )
    select
      'fd300000-0000-4000-8000-000000000002', rebound.id,
      'extract', 'bounded-test', 'deterministic-v1', 'test-v1', repeat('f', 64),
      clock_timestamp(), clock_timestamp() + interval '30 days', false
    from rebound
  $sql$),
  '23514',
  'a writable CTE cannot atomically rebind an ordinary source and add evidence'
);
select is(
  pg_temp.sqlstate_of_deferred($sql$
    with inserted_source as (
      insert into ingest.source_items (
        id, source_policy_id, platform, external_id, source_url, normalized_url,
        domain, title, content_hash, collector_type, collector_version,
        source_policy_version, access_mode, usage_classification, source_kind,
        language, status, metadata, expires_at, is_demo
      ) values (
        'fd100000-0000-4000-8000-000000000006',
        (select id from ingest.source_policies where source_key = 'youtube_discovery'),
        'youtube', 'ctebypass01',
        'https://www.youtube.com/watch?v=ctebypass01',
        'https://www.youtube.com/watch?v=ctebypass01',
        'youtube.com', 'Sibling CTE metadata', null,
        'official_api', 'youtube-global-discovery-v1',
        'youtube-global-discovery-v1', 'official_api', 'activity_only',
        'official_api', 'en', 'activity_only',
        pg_temp.youtube_item(
          'ctebypass01', 'pokemon-tcg-booster-box-opening', null
        ) -> 'metadata',
        clock_timestamp() + interval '30 days', false
      )
      returning id
    )
    insert into ingest.extraction_runs (
      id, source_item_id, stage, provider, model, prompt_version, input_hash,
      started_at, expires_at, is_demo
    )
    select
      'fd300000-0000-4000-8000-000000000003', inserted_source.id,
      'extract', 'bounded-test', 'deterministic-v1', 'test-v1', repeat('a', 64),
      clock_timestamp(), clock_timestamp() + interval '30 days', false
    from inserted_source
  $sql$),
  '23514',
  'deferred invariants reject sibling CTE insertion of discovery metadata and evidence'
);
select is(
  pg_temp.sqlstate_of($sql$
    update ingest.source_items
    set source_policy_id = (
      select id from ingest.source_policies where source_key = 'youtube_discovery'
    )
    where id = '71000000-0000-4000-8000-000000000001'
  $sql$),
  '23514',
  'a source with existing extraction, opening, and batch evidence cannot be rebound into discovery'
);
select is(
  pg_temp.sqlstate_of($sql$
    update ingest.source_items
    set source_policy_id = (
      select id from ingest.source_policies where source_key = 'youtube_discovery'
    )
    where id = 'fd100000-0000-4000-8000-000000000003'
  $sql$),
  '23514',
  'an ordinary duplicate-cluster member cannot be rebound into discovery'
);
update ingest.source_items
set duplicate_cluster_id = null
where id = 'fd100000-0000-4000-8000-000000000003';
update ingest.source_items
set duplicate_cluster_id = 'fd100000-0000-4000-8000-000000000003'
where id = 'fd100000-0000-4000-8000-000000000004';
select is(
  pg_temp.sqlstate_of($sql$
    update ingest.source_items
    set source_policy_id = (
      select id from ingest.source_policies where source_key = 'youtube_discovery'
    )
    where id = 'fd100000-0000-4000-8000-000000000003'
  $sql$),
  '23514',
  'an ordinary duplicate-cluster target cannot be rebound into discovery'
);
select lives_ok(
  $$update ingest.source_items
    set source_policy_id = 'fd000000-0000-4000-8000-000000000002',
        expires_at = clock_timestamp() + interval '10 years'
    where platform = 'youtube' and external_id = 'abcdefghijk' and not is_demo$$,
  'service_role may rebind policy/cache fields but cannot erase immutable provenance'
);
select is(
  pg_temp.sqlstate_of($sql$
    insert into ingest.extraction_runs (
      id, source_item_id, stage, provider, model, prompt_version, input_hash,
      started_at, expires_at, is_demo
    ) values (
      'fd300000-0000-4000-8000-000000000001',
      (select id from ingest.source_items
       where platform = 'youtube' and external_id = 'abcdefghijk' and not is_demo),
      'extract', 'bounded-test', 'deterministic-v1', 'test-v1', repeat('e', 64),
      clock_timestamp(), clock_timestamp() + interval '30 days', false
    )
  $sql$),
  '23514',
  'a rebound discovery cannot be inserted into extraction runs'
);
select is(
  pg_temp.sqlstate_of($sql$
    update ingest.extraction_runs
    set source_item_id = (
      select id from ingest.source_items
      where platform = 'youtube' and external_id = 'abcdefghijk' and not is_demo
    )
    where id = '72000000-0000-4000-8000-000000000001'
  $sql$),
  '23514',
  'an extraction run cannot be updated onto rebound discovery metadata'
);
select is(
  pg_temp.sqlstate_of($sql$
    insert into ingest.openings (
      id, source_item_id, extraction_run_id, set_id, product_id, language,
      pack_count, complete_opening, country_code, region_id, retailer_id,
      store_id, batch_code, purchase_date, opened_at, observed_at, evidence_tier,
      overall_confidence, eligible_for_statistics, methodology_version,
      validation_status, public_status, source_kind, expires_at, is_demo
    )
    select
      'fd400000-0000-4000-8000-000000000001',
      (select id from ingest.source_items
       where platform = 'youtube' and external_id = 'abcdefghijk' and not is_demo),
      extraction_run_id, set_id, product_id, language, pack_count,
      complete_opening, country_code, region_id, retailer_id, store_id,
      batch_code, purchase_date, opened_at, observed_at, evidence_tier,
      overall_confidence, eligible_for_statistics, methodology_version,
      validation_status, public_status, source_kind, expires_at, false
    from ingest.openings
    where id = '73000000-0000-4000-8000-000000000001'
  $sql$),
  '23514',
  'a rebound discovery cannot be inserted into openings'
);
select is(
  pg_temp.sqlstate_of($sql$
    update ingest.openings
    set source_item_id = (
      select id from ingest.source_items
      where platform = 'youtube' and external_id = 'abcdefghijk' and not is_demo
    )
    where id = '73000000-0000-4000-8000-000000000001'
  $sql$),
  '23514',
  'an opening cannot be updated onto rebound discovery metadata'
);
select is(
  pg_temp.sqlstate_of($sql$
    insert into ingest.batch_sightings (
      id, source_item_id, opening_id, set_id, product_id, region_id, retailer_id,
      store_id, batch_code, normalized_batch_code, pack_quantity, activity_only,
      confidence, observed_at, expires_at, is_demo
    )
    select
      'fd500000-0000-4000-8000-000000000001',
      (select id from ingest.source_items
       where platform = 'youtube' and external_id = 'abcdefghijk' and not is_demo),
      opening_id, set_id, product_id, region_id, retailer_id, store_id,
      batch_code, normalized_batch_code, pack_quantity, activity_only,
      confidence, observed_at, expires_at, false
    from ingest.batch_sightings
    where id = '75000000-0000-4000-8000-000000000001'
  $sql$),
  '23514',
  'a rebound discovery cannot be inserted into batch sightings'
);
select is(
  pg_temp.sqlstate_of($sql$
    update ingest.batch_sightings
    set source_item_id = (
      select id from ingest.source_items
      where platform = 'youtube' and external_id = 'abcdefghijk' and not is_demo
    )
    where id = '75000000-0000-4000-8000-000000000001'
  $sql$),
  '23514',
  'a batch sighting cannot be updated onto rebound discovery metadata'
);
select is(
  pg_temp.sqlstate_of($sql$
    update ingest.source_items
    set duplicate_cluster_id = '71000000-0000-4000-8000-000000000001'
    where platform = 'youtube' and external_id = 'abcdefghijk' and not is_demo
  $sql$),
  '23514',
  'rebound discovery metadata cannot join a downstream duplicate cluster'
);
select is(
  pg_temp.sqlstate_of($sql$
    update ingest.source_items
    set duplicate_cluster_id = (
      select id from ingest.source_items
      where platform = 'youtube' and external_id = 'abcdefghijk' and not is_demo
    )
    where id = '71000000-0000-4000-8000-000000000002'
  $sql$),
  '23514',
  'rebound discovery metadata cannot become another source cluster target'
);
reset role;

insert into ingest.jobs (
  id, job_type, payload, status, priority, attempts, max_attempts,
  available_at, retention_until, is_demo
) values (
  'fd200000-0000-4000-8000-000000000007', 'maintenance.cleanup', '{}',
  'pending', 100, 0, 5, clock_timestamp() - interval '1 minute',
  clock_timestamp() + interval '90 days', false
);
select * from ingest.claim_jobs_v2(
  'youtube-retention', array['maintenance.cleanup'], 1, 600
);
select is(
  (select count(*)::integer from ingest.finalize_cleanup_job(
    'fd200000-0000-4000-8000-000000000007', 'youtube-retention', 1
  )),
  1,
  'retention runs only through the fenced cleanup finalizer'
);
select is(
  (select count(*)::integer from ingest.source_items
   where platform = 'youtube' and external_id = 'abcdefghijk' and not is_demo),
  0,
  'expired rebound YouTube metadata is deleted despite its extended cache expiry'
);
select is(
  (select count(*)::integer from ingest.source_discoveries
   where source_item_id = (select id from youtube_expired_identity)),
  0,
  'expired source discovery provenance cascades with its source item'
);
select ok(
  not has_function_privilege(
    'service_role',
    'ingest.prune_expired_ephemera_v2(timestamp with time zone,integer)',
    'execute'
  ),
  'service_role cannot bypass fenced cleanup to call retention directly'
);
select lives_ok(
  'set constraints all immediate',
  'all legitimate discovery writes satisfy deferred end-state invariants'
);

select * from finish();
rollback;
