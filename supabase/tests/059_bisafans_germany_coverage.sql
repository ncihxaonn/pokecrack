-- Transaction-local fixtures exercise the production RPCs; no network evidence
-- or live collection is implied. The migration must not seed this observation.
begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select is(
  (select array_agg(ordinal order by ordinal) from ingest.reviewed_public_study_contracts()),
  array(select generate_series(1, 33)), 'all 33 reviewed contract ordinals exist'
);
select is(
  (select count(*) from ingest.public_study_coverage_observations
   where study_key = 'bisafans-flying-fists-de-36-v1'),
  0::bigint, 'migration creates no Bisafans observation before collection'
);
select is(
  (select title_fragments from ingest.reviewed_public_study_contracts() where ordinal = 33),
  array['Statistiken']::text[],
  'the exact page heading is distinct from the two-line evidence excerpt'
);
select is(
  (select encode(extensions.digest(convert_to(evidence_excerpt, 'UTF8'), 'sha256'), 'hex')
   from ingest.reviewed_public_study_contracts() where ordinal = 33),
  'd31a4d8e74d80d5835f1613b4d392068a0fe91b2bf04d84462f54eae5f5824f4',
  'minimal UTF8 evidence hash agrees with the backup contract'
);
select is(
  (select jsonb_build_object(
    'country', config -> 'country_code', 'language', config -> 'set_language',
    'set', config -> 'set_external_id', 'setName', config -> 'set_name',
    'basis', config -> 'geography_basis', 'openingCountry', config -> 'opening_country',
    'openedAt', config -> 'opened_at', 'observedAt', config -> 'observed_at'
  ) from ingest.reviewed_public_study_contracts() where ordinal = 33),
  '{"country":"DE","language":"de","set":"xy3","setName":"Fliegende Fäuste",
    "basis":"publisher_country","openingCountry":null,"openedAt":null,
    "observedAt":"2026-09-11T00:00:00Z"}'::jsonb,
  'Germany and German product identity do not infer physical opening geography or time'
);
select ok(exists (
  select 1 from ingest.source_policies p
  join ingest.reviewed_public_study_contracts() c
    on c.policy_key = p.source_key and c.config = p.config and c.policy_version = p.version
  where c.ordinal = 33 and p.display_name = 'Bisafans Fliegende Fäuste 36-pack coverage'
    and p.domain = c.domain and p.base_url = c.canonical_url
    and p.enabled and not p.is_demo and p.source_kind = 'public_web'
    and p.collector_type = 'scrapling_http' and p.access_mode = 'public'
    and p.robots_policy = 'respect' and p.routes = array['scrapling_http']::text[]
    and not p.include_subdomains and p.browser_profile is null
    and p.min_delay_seconds = 30 and p.max_pages_per_run = 2
    and p.max_items_per_run = 1 and p.max_concurrency = 1
    and p.statistics_eligible_default and p.retention_days = 730
    and p.expected_interval_seconds = 86400
), 'the immutable policy retains the bounded German static collection contract');
select ok(ingest.reviewed_public_study_gates_ready_v1(), '33 policy gates are ready');
select ok(exists (
  select 1 from ingest.source_request_gates where source_key = 'public_study_bisafans_de_36'
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

create temporary table de_before as
select coalesce(sum((c ->> 'packsObserved')::bigint), 0) as packs,
       coalesce(sum((c ->> 'openings')::bigint), 0) as openings
from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries') c
where c ->> 'countryCode' = 'DE';

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
begin
  select * into strict reviewed from ingest.reviewed_public_study_contracts()
    where ordinal = 33 and study_key = 'bisafans-flying-fists-de-36-v1';
  select id into queued from ingest.enqueue_scheduled_public_study_coverage_job_v1(
    'public_study_' || reviewed.study_key, slot_at, reviewed.study_key, 999, 3
  );
  if queued is null then raise exception 'Scheduled Bisafans job was not enqueued'; end if;
  select id, lease_generation into claimed, generation from ingest.claim_jobs_v2(
    'pgtap-bisafans-worker', array['source.public_study.opening'], 1, 600
  );
  if claimed is distinct from queued then raise exception 'Wrong coverage job claimed'; end if;
  select begun.acquired into acquired from ingest.begin_public_study_job_v2(
    queued, 'pgtap-bisafans-worker', generation, reviewed.study_key
  ) begun;
  if acquired is distinct from true then raise exception 'Request gate not acquired'; end if;
  result := jsonb_build_object(
    'version', 1, 'study_key', reviewed.study_key, 'source_url', reviewed.canonical_url,
    'title', 'Statistiken',
    'evidence_excerpt', E'Da wir zu jeder Pokémon Sammelkartenerweiterung ein Boosterdisplay mit 36 Packungen öffnen\nIn XY Fliegende Fäuste waren in unserem Display 47 Karten der Seltenheitsstufe Rare oder seltener.',
    'evidence_sha256', 'd31a4d8e74d80d5835f1613b4d392068a0fe91b2bf04d84462f54eae5f5824f4',
    'collector_version', 'public-study-bisafans-flying-fists-v1',
    'parser_version', 'bisafans-flying-fists-evidence-v1',
    'source_policy_version', 'public-study-bisafans-flying-fists-v1'
  );
  if exists (select 1 from ingest.finalize_public_study_coverage_job_v1(
    queued, 'pgtap-bisafans-worker', generation + 1, reviewed.study_key, result
  )) then raise exception 'Stale generation admitted evidence'; end if;
  begin
    perform ingest.finalize_public_study_coverage_job_v1(
      queued, 'pgtap-bisafans-worker', generation, reviewed.study_key,
      result || '{"pack_count":37}'::jsonb
    );
    raise exception 'Unexpected result fields were accepted';
  exception when invalid_parameter_value then null;
  end;
  select count(*) into completed_count from ingest.finalize_public_study_coverage_job_v1(
    queued, 'pgtap-bisafans-worker', generation, reviewed.study_key, result
  );
  if completed_count <> 1 then raise exception 'First finalization did not complete'; end if;
  if exists (select 1 from ingest.finalize_public_study_coverage_job_v1(
    queued, 'pgtap-bisafans-worker', generation, reviewed.study_key, result
  )) then raise exception 'Completed lease was reusable'; end if;
  perform ingest.enqueue_scheduled_public_study_coverage_job_v1(
    'public_study_' || reviewed.study_key, slot_at, reviewed.study_key, 999, 3
  );
  if (select count(*) from ingest.jobs where payload = jsonb_build_object('study_key', reviewed.study_key)) <> 1 then
    raise exception 'Completed schedule slot was duplicated';
  end if;
end;
$runtime$;
$test$, 'fenced non-English evidence admits only the exact coverage cohort');

select is(
  (select jsonb_build_object('observations', count(*), 'packs', sum(pack_count))
   from ingest.public_study_coverage_observations
   where study_key = 'bisafans-flying-fists-de-36-v1'),
  '{"observations":1,"packs":36}'::jsonb,
  'one complete display is retained as one 36-pack denominator cohort'
);
select is(
  (select count(*) from ingest.public_study_observations
   where study_key = 'bisafans-flying-fists-de-36-v1'),
  0::bigint, 'no statistical observation or numerator is created'
);
select is(
  (select (c ->> 'packsObserved')::bigint - b.packs
   from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries') c
   cross join de_before b where c ->> 'countryCode' = 'DE'),
  36::numeric, 'public Germany coverage gains exactly 36 packs'
);
select is(
  (select (c ->> 'openings')::bigint - b.openings
   from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries') c
   cross join de_before b where c ->> 'countryCode' = 'DE'),
  1::numeric, 'public Germany coverage gains one cohort'
);
select ok(not exists (
  select 1 from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries') c
  where c ->> 'countryCode' = 'DE' and (c ? 'rate' or c ? 'numerator')
), 'coverage adds no numerator or rate');
select ok(exists (
  select 1 from ingest.source_request_gates where source_key = 'public_study_bisafans_de_36'
    and owner_job_id is null and active_until is null
), 'successful finalization releases the Bisafans gate');
select * from finish();
rollback;
