-- Transaction-local fixtures exercise the production RPCs; no network evidence
-- or live collection is implied. The migration must not seed this observation.
begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select is(
  (select array_agg(ordinal order by ordinal) from ingest.reviewed_public_study_contracts()),
  array(select generate_series(1, 32)), 'all 32 reviewed contract ordinals exist'
);
select is(
  (select count(*) from ingest.public_study_coverage_observations
   where study_key = 'tekemero-munikis-zero-jp-30-v1'),
  0::bigint, 'migration creates no Tekemero observation before collection'
);
create temporary table jp_before as
select coalesce(sum((c ->> 'packsObserved')::bigint), 0) as packs,
       coalesce(sum((c ->> 'openings')::bigint), 0) as openings
from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries') c
where c ->> 'countryCode' = 'JP';
select is(
  (select title_fragments from ingest.reviewed_public_study_contracts() where ordinal = 32),
  array['ムニキスゼロ', '30パック']::text[],
  'exact article title is distinct from its denominator excerpt'
);
select is(
  (select encode(extensions.digest(convert_to(evidence_excerpt, 'UTF8'), 'sha256'), 'hex')
   from ingest.reviewed_public_study_contracts() where ordinal = 32),
  'f13f9c05c779e0ce65a203f961420ffe7bec4fb7b688079c073824fd7dd40f93',
  'minimal UTF8 evidence hash agrees with the backup contract'
);
select is(
  (select jsonb_build_object(
    'language', config -> 'set_language', 'set', config -> 'set_external_id',
    'basis', config -> 'geography_basis', 'openingCountry', config -> 'opening_country',
    'openedAt', config -> 'opened_at',
    'observedAt', config -> 'observed_at'
  ) from ingest.reviewed_public_study_contracts() where ordinal = 32),
  '{"language":"ja","set":"M3","basis":"product_market",
    "openingCountry":null,"openedAt":null,
    "observedAt":"2026-07-15T06:48:03Z"}'::jsonb,
  'Japanese product-market identity does not infer physical opening geography or time'
);
select ok(exists (
  select 1 from ingest.source_policies p
  join ingest.reviewed_public_study_contracts() c
    on c.policy_key = p.source_key and c.config = p.config and c.policy_version = p.version
  where c.ordinal = 32 and p.display_name = 'Tekemero M3 30-pack coverage'
    and p.domain = c.domain and p.base_url = c.canonical_url
    and p.enabled and not p.is_demo and p.source_kind = 'public_web'
    and p.collector_type = 'scrapling_http' and p.access_mode = 'public'
    and p.robots_policy = 'respect' and p.routes = array['scrapling_http']::text[]
    and not p.include_subdomains and p.browser_profile is null
    and p.min_delay_seconds = 30 and p.max_pages_per_run = 2
    and p.max_items_per_run = 1 and p.max_concurrency = 1
    and p.statistics_eligible_default and p.retention_days = 730
    and p.expected_interval_seconds = 86400
), 'the immutable policy retains the existing bounded static collection contract');
select ok(ingest.reviewed_public_study_gates_ready_v1(), '32 policy gates are ready');
select ok(exists (
  select 1 from ingest.source_request_gates where source_key = 'public_study_tekemero_jp_30'
    and owner_job_id is null and active_until is null
), 'the new source starts with an idle request gate');
select ok(
  not has_function_privilege('anon', 'ingest.reviewed_public_study_contracts()', 'EXECUTE')
  and not has_function_privilege('authenticated', 'ingest.reviewed_public_study_contracts()', 'EXECUTE')
  and not has_function_privilege('service_role', 'ingest.reviewed_public_study_contracts()', 'EXECUTE')
  and not has_table_privilege('anon', 'ingest.public_study_coverage_observations', 'SELECT')
  and not has_table_privilege('service_role', 'ingest.public_study_coverage_observations', 'INSERT'),
  'the registry and coverage ledger retain private ACLs'
);
select ok(
  has_function_privilege('service_role',
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)', 'EXECUTE')
  and not has_function_privilege('anon',
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)', 'EXECUTE'),
  'worker ingress remains the existing typed finalizer'
);

select lives_ok($test$
do $runtime$
declare
  reviewed record;
  queued uuid;
  claimed uuid;
  generation bigint;
  acquired boolean;
  result jsonb;
  slot_at timestamptz := date_trunc('minute', clock_timestamp());
  completed_count integer;
  drift jsonb;
begin
  select * into strict reviewed from ingest.reviewed_public_study_contracts()
    where ordinal = 32 and study_key = 'tekemero-munikis-zero-jp-30-v1';
  select id into queued from ingest.enqueue_scheduled_public_study_coverage_job_v1(
    'public_study_' || reviewed.study_key, slot_at, reviewed.study_key, 999, 3
  );
  if queued is null then raise exception 'Scheduled Tekemero job was not enqueued'; end if;
  select id, lease_generation into claimed, generation from ingest.claim_jobs_v2(
    'pgtap-tekemero-worker', array['source.public_study.opening'], 1, 600
  );
  if claimed is distinct from queued then raise exception 'Wrong coverage job claimed'; end if;
  select begun.acquired into acquired from ingest.begin_public_study_job_v2(
    queued, 'pgtap-tekemero-worker', generation, reviewed.study_key
  ) begun;
  if acquired is distinct from true then raise exception 'Request gate not acquired'; end if;
  result := jsonb_build_object(
    'version', 1, 'study_key', reviewed.study_key, 'source_url', reviewed.canonical_url,
    'title', 'ムニキスゼロ 30パック',
    'evidence_excerpt', '30パック',
    'evidence_sha256', 'f13f9c05c779e0ce65a203f961420ffe7bec4fb7b688079c073824fd7dd40f93',
    'collector_version', 'public-study-tekemero-munikis-zero-v1',
    'parser_version', 'tekemero-munikis-zero-30-evidence-v1',
    'source_policy_version', 'public-study-tekemero-munikis-zero-v1'
  );
  if exists (select 1 from ingest.finalize_public_study_coverage_job_v1(
    queued, 'pgtap-tekemero-worker', generation + 1, reviewed.study_key, result
  )) then raise exception 'Stale generation admitted evidence'; end if;
  begin
    perform ingest.finalize_public_study_coverage_job_v1(
      queued, 'pgtap-tekemero-worker', generation, reviewed.study_key,
      jsonb_set(result, '{title}', to_jsonb('30パック'::text))
    );
    raise exception 'Body-only title was accepted';
  exception when invalid_parameter_value then null;
  end;
  begin
    perform ingest.finalize_public_study_coverage_job_v1(
      queued, 'pgtap-tekemero-worker', generation, reviewed.study_key,
      result || '{"pack_count":753}'::jsonb
    );
    raise exception 'External study count was accepted';
  exception when invalid_parameter_value then null;
  end;
  foreach drift in array array[
    '{"set_language":"en"}'::jsonb,
    '{"set_language":"cs"}'::jsonb,
    '{"set_external_id":"me04"}'::jsonb,
    '{"set_name":"Different expansion"}'::jsonb,
    '{"product_scope":"all"}'::jsonb
  ] loop
    begin
      update ingest.source_policies set config = config || drift
        where source_key = reviewed.policy_key;
      perform ingest.finalize_public_study_coverage_job_v1(
        queued, 'pgtap-tekemero-worker', generation, reviewed.study_key, result
      );
      raise exception 'Changed source product or language was accepted';
    exception when sqlstate '55000' then null;
    end;
  end loop;
  foreach drift in array array[
    '{"source_url":"https://tekemero.com/260715-01/"}'::jsonb,
    '{"parser_version":"unreviewed"}'::jsonb,
    '{"evidence_sha256":"0000000000000000000000000000000000000000000000000000000000000000"}'::jsonb,
    '{"numerator":1,"rate":0.1}'::jsonb,
    '{"version":2}'::jsonb
  ] loop
    begin
      perform ingest.finalize_public_study_coverage_job_v1(
        queued, 'pgtap-tekemero-worker', generation, reviewed.study_key, result || drift
      );
      raise exception 'Invalid schema, identity or statistical payload was accepted';
    exception when invalid_parameter_value then null;
    end;
  end loop;
  if exists(select 1 from ingest.public_study_coverage_observations
    where study_key = reviewed.study_key) then raise exception 'Rejected evidence created an observation'; end if;
  select count(*) into completed_count from ingest.finalize_public_study_coverage_job_v1(
    queued, 'pgtap-tekemero-worker', generation, reviewed.study_key, result
  );
  if completed_count <> 1 then raise exception 'First finalization did not complete'; end if;
  if exists (select 1 from ingest.finalize_public_study_coverage_job_v1(
    queued, 'pgtap-tekemero-worker', generation, reviewed.study_key, result
  )) then raise exception 'Completed lease was reusable'; end if;
  perform ingest.enqueue_scheduled_public_study_coverage_job_v1(
    'public_study_' || reviewed.study_key, slot_at, reviewed.study_key, 999, 3
  );
  if (select count(*) from ingest.jobs where payload = jsonb_build_object('study_key', reviewed.study_key)) <> 1 then
    raise exception 'Completed schedule slot was duplicated';
  end if;

  -- Advance only the synthetic pacing marker instead of sleeping in the test.
  update ingest.source_policies set last_attempt_at = clock_timestamp() - interval '1 minute'
    where source_key = reviewed.policy_key;
  select id into queued from ingest.enqueue_public_study_coverage_job_v1(
    reviewed.study_key, 999, 'pgtap-tekemero-refresh', null, 3
  );
  select id, lease_generation into claimed, generation from ingest.claim_jobs_v2(
    'pgtap-tekemero-worker', array['source.public_study.opening'], 1, 600
  );
  if claimed is distinct from queued then raise exception 'Wrong refresh job claimed'; end if;
  select begun.acquired into acquired from ingest.begin_public_study_job_v2(
    queued, 'pgtap-tekemero-worker', generation, reviewed.study_key
  ) begun;
  if acquired is distinct from true then raise exception 'Refresh gate not acquired'; end if;
  select count(*) into completed_count from ingest.finalize_public_study_coverage_job_v1(
    queued, 'pgtap-tekemero-worker', generation, reviewed.study_key, result
  );
  if completed_count <> 1 then raise exception 'Refresh did not complete'; end if;
end;
$runtime$;
$test$, 'fenced first admission and refresh reject invalid evidence and deduplicate retries');

select is(
  (select jsonb_build_object('observations', count(*), 'packs', sum(pack_count))
   from ingest.public_study_coverage_observations where study_key = 'tekemero-munikis-zero-jp-30-v1'),
  '{"observations":1,"packs":30}'::jsonb, 'first admission plus refresh retains one 30-pack cohort'
);
select is(
  (select count(*) from ingest.public_study_observations where study_key = 'tekemero-munikis-zero-jp-30-v1'),
  0::bigint, 'no statistical observation or numerator is created'
);
select is(
  (select source_observed_at from ingest.public_study_coverage_observations
   where study_key = 'tekemero-munikis-zero-jp-30-v1'),
  '2026-07-15 06:48:03+00'::timestamptz, 'original publication timestamp is preserved, not inferred opening time'
);
select is(
  (select (c ->> 'packsObserved')::bigint - b.packs
   from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries') c
   cross join jp_before b where c ->> 'countryCode' = 'JP'),
  30::numeric, 'public Japan coverage gains exactly 30 packs'
);
select is(
  (select (c ->> 'openings')::bigint - b.openings
   from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries') c
   cross join jp_before b where c ->> 'countryCode' = 'JP'),
  1::numeric, 'public Japan coverage gains one cohort despite refresh'
);
select ok(not exists (
  select 1 from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries') c
  where c ->> 'countryCode' = 'JP' and (c ? 'rate' or c ? 'numerator')
), 'coverage adds no numerator or rate');
select ok(exists (
  select 1 from ingest.source_request_gates where source_key = 'public_study_tekemero_jp_30'
    and owner_job_id is null and active_until is null
), 'successful finalization releases the Tekemero gate');
select * from finish();
rollback;
