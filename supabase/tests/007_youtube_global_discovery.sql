-- Live global YouTube metadata discovery, provenance, fencing, and retention.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select plan(58);

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
  pg_temp.youtube_result(
    'pokemon-tcg-booster-box-opening', 'abcdefghijk', 'US'
  )
);
select is((select count(*)::integer from youtube_completed_one), 1, 'valid metadata finalizes exactly once');
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

-- Retention deletes expired, unreferenced discovery metadata and cascades its
-- query provenance, but preserves an item that has entered extraction.
insert into ingest.source_items (
  id, source_policy_id, platform, external_id, source_url, normalized_url,
  domain, title, discovered_at, content_hash, collector_type, collector_version,
  source_policy_version, access_mode, usage_classification, source_kind,
  language, status, metadata, expires_at, is_demo
) values
  (
    'fd100000-0000-4000-8000-000000000003',
    (select id from ingest.source_policies where source_key = 'youtube_discovery'),
    'youtube', 'expire00001',
    'https://www.youtube.com/watch?v=expire00001',
    'https://www.youtube.com/watch?v=expire00001', 'youtube.com',
    'Expired unreferenced metadata', clock_timestamp() - interval '40 days',
    null, 'official_api', 'youtube-global-discovery-v1', 'youtube-global-discovery-v1',
    'official_api', 'activity_only', 'official_api', 'en', 'activity_only',
    pg_temp.youtube_item(
      'expire00001', 'pokemon-tcg-booster-box-opening', null
    ) -> 'metadata',
    clock_timestamp() - interval '1 day', false
  ),
  (
    'fd100000-0000-4000-8000-000000000004',
    (select id from ingest.source_policies where source_key = 'youtube_discovery'),
    'youtube', 'retain00001',
    'https://www.youtube.com/watch?v=retain00001',
    'https://www.youtube.com/watch?v=retain00001', 'youtube.com',
    'Expired referenced metadata', clock_timestamp() - interval '40 days',
    null, 'official_api', 'youtube-global-discovery-v1', 'youtube-global-discovery-v1',
    'official_api', 'activity_only', 'official_api', 'en', 'activity_only',
    pg_temp.youtube_item(
      'retain00001', 'pokemon-tcg-booster-box-opening', null
    ) -> 'metadata',
    clock_timestamp() - interval '1 day', false
  );
insert into ingest.source_discoveries (
  source_item_id, query_name, job_id, first_seen_at, last_seen_at, result_rank,
  channel_country_code, geography_status, geography_basis, is_demo
) values
  (
    'fd100000-0000-4000-8000-000000000003',
    'pokemon-tcg-booster-box-opening',
    'fd200000-0000-4000-8000-000000000001',
    clock_timestamp() - interval '40 days', clock_timestamp() - interval '40 days',
    2, null, 'unresolved', 'unresolved', false
  ),
  (
    'fd100000-0000-4000-8000-000000000004',
    'pokemon-tcg-booster-box-opening',
    'fd200000-0000-4000-8000-000000000001',
    clock_timestamp() - interval '40 days', clock_timestamp() - interval '40 days',
    3, null, 'unresolved', 'unresolved', false
  );
insert into ingest.extraction_runs (
  id, source_item_id, stage, provider, model, prompt_version, input_hash,
  started_at, expires_at, is_demo
) values (
  'fd300000-0000-4000-8000-000000000001',
  'fd100000-0000-4000-8000-000000000004',
  'extract', 'bounded-test', 'deterministic-v1', 'test-v1', repeat('e', 64),
  clock_timestamp() - interval '1 day', clock_timestamp() + interval '30 days', false
);
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
   where id = 'fd100000-0000-4000-8000-000000000003'),
  0,
  'expired unreferenced YouTube metadata is deleted'
);
select is(
  (select count(*)::integer from ingest.source_discoveries
   where source_item_id = 'fd100000-0000-4000-8000-000000000003'),
  0,
  'expired source discovery provenance cascades with its source item'
);
select is(
  (select count(*)::integer from ingest.source_items
   where id = 'fd100000-0000-4000-8000-000000000004'),
  1,
  'an expired YouTube item with an extraction reference is retained'
);
select is(
  (select count(*)::integer from ingest.source_discoveries
   where source_item_id = 'fd100000-0000-4000-8000-000000000004'),
  1,
  'retained referenced metadata keeps its query provenance'
);
select ok(
  not has_function_privilege(
    'service_role',
    'ingest.prune_expired_ephemera_v2(timestamp with time zone,integer)',
    'execute'
  ),
  'service_role cannot bypass fenced cleanup to call retention directly'
);

select * from finish();
rollback;
