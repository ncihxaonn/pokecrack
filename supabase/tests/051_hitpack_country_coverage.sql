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
   where study_key = 'hitpack-pitch-black-cz-36-v1'),
  0::bigint, 'migration creates no Hitpack observation before collection'
);
select ok(not exists (
  select 1 from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries') c
  where c ->> 'countryCode' = 'CZ'
), 'an enabled policy alone publishes no Czechia packs');
select is(
  (select title_fragments from ingest.reviewed_public_study_contracts() where ordinal = 31),
  array['Pokémon Pitch Black pull rates: co padlo z 36 boosterů?']::text[],
  'exact article title is distinct from its denominator excerpt'
);
select is(
  (select encode(extensions.digest(convert_to(evidence_excerpt, 'UTF8'), 'sha256'), 'hex')
   from ingest.reviewed_public_study_contracts() where ordinal = 31),
  'b7aca4213dc83f3fde4407985da20807f6cc4cb230db7ebadff32c2915f571ee',
  'minimal UTF8 evidence hash agrees with the backup contract'
);
select is(
  (select jsonb_build_object(
    'language', config -> 'set_language', 'set', config -> 'set_external_id',
    'basis', config -> 'geography_basis', 'openingCountry', config -> 'opening_country',
    'openedAt', config -> 'opened_at', 'precision', config -> 'publication_time_precision',
    'observedAt', config -> 'observed_at'
  ) from ingest.reviewed_public_study_contracts() where ordinal = 31),
  '{"language":"und","set":"me05","basis":"publisher_country",
    "openingCountry":null,"openedAt":null,"precision":"day",
    "observedAt":"2026-07-28T00:00:00Z"}'::jsonb,
  'unknown card language and physical geography survive the date-only publication contract'
);
select ok(exists (
  select 1 from ingest.source_policies p
  join ingest.reviewed_public_study_contracts() c
    on c.policy_key = p.source_key and c.config = p.config and c.policy_version = p.version
  where c.ordinal = 31 and p.display_name = 'Hitpack Pitch Black 36-pack coverage'
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
select ok(ingest.reviewed_public_study_gates_ready_v1(), '33 policy gates are ready');
select ok(exists (
  select 1 from ingest.source_request_gates where source_key = 'public_study_hitpack_cz_36'
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

-- Supply the normal catalog prerequisite only in this rolled-back test.
-- Its English catalog identity does not establish the report's card language.
insert into catalog.sets (
  external_source, external_id, name, slug, language, is_active, is_demo
) values ('tcgdex', 'me05', 'Pitch Black', 'pgtap-hitpack-pitch-black', 'en', true, false)
on conflict on constraint sets_external_identity_unique
do update set is_active = true, is_demo = false;

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
    where ordinal = 31 and study_key = 'hitpack-pitch-black-cz-36-v1';
  select id into queued from ingest.enqueue_scheduled_public_study_coverage_job_v1(
    'public_study_' || reviewed.study_key, slot_at, reviewed.study_key, 999, 3
  );
  if queued is null then raise exception 'Scheduled Hitpack job was not enqueued'; end if;
  select id, lease_generation into claimed, generation from ingest.claim_jobs_v2(
    'pgtap-hitpack-worker', array['source.public_study.opening'], 1, 600
  );
  if claimed is distinct from queued then raise exception 'Wrong coverage job claimed'; end if;
  select begun.acquired into acquired from ingest.begin_public_study_job_v2(
    queued, 'pgtap-hitpack-worker', generation, reviewed.study_key
  ) begun;
  if acquired is distinct from true then raise exception 'Request gate not acquired'; end if;
  result := jsonb_build_object(
    'version', 1, 'study_key', reviewed.study_key, 'source_url', reviewed.canonical_url,
    'title', 'Pokémon Pitch Black pull rates: co padlo z 36 boosterů?',
    'evidence_excerpt', '36 balíčků',
    'evidence_sha256', 'b7aca4213dc83f3fde4407985da20807f6cc4cb230db7ebadff32c2915f571ee',
    'collector_version', 'public-study-hitpack-pitch-black-v1',
    'parser_version', 'hitpack-pitch-black-36-evidence-v1',
    'source_policy_version', 'public-study-hitpack-pitch-black-v1'
  );
  if exists (select 1 from ingest.finalize_public_study_coverage_job_v1(
    queued, 'pgtap-hitpack-worker', generation + 1, reviewed.study_key, result
  )) then raise exception 'Stale generation admitted evidence'; end if;
  begin
    perform ingest.finalize_public_study_coverage_job_v1(
      queued, 'pgtap-hitpack-worker', generation, reviewed.study_key,
      jsonb_set(result, '{title}', to_jsonb('36 balíčků'::text))
    );
    raise exception 'Body-only title was accepted';
  exception when invalid_parameter_value then null;
  end;
  begin
    perform ingest.finalize_public_study_coverage_job_v1(
      queued, 'pgtap-hitpack-worker', generation, reviewed.study_key,
      result || '{"pack_count":753}'::jsonb
    );
    raise exception 'External study count was accepted';
  exception when invalid_parameter_value then null;
  end;
  begin
    update catalog.sets set is_active = false
      where external_source = 'tcgdex' and external_id = 'me05' and language = 'en';
    perform ingest.finalize_public_study_coverage_job_v1(
      queued, 'pgtap-hitpack-worker', generation, reviewed.study_key, result
    );
    raise exception 'Missing live catalog identity was bypassed';
  exception when sqlstate '55000' then null;
  end;
  begin
    update catalog.sets set name = 'Different expansion'
      where external_source = 'tcgdex' and external_id = 'me05' and language = 'en';
    perform ingest.finalize_public_study_coverage_job_v1(
      queued, 'pgtap-hitpack-worker', generation, reviewed.study_key, result
    );
    raise exception 'Wrong catalog product name was accepted';
  exception when sqlstate '55000' then null;
  end;
  begin
    update catalog.sets set is_demo = true
      where external_source = 'tcgdex' and external_id = 'me05' and language = 'en';
    perform ingest.finalize_public_study_coverage_job_v1(
      queued, 'pgtap-hitpack-worker', generation, reviewed.study_key, result
    );
    raise exception 'Demo catalog identity was accepted';
  exception when sqlstate '55000' then null;
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
        queued, 'pgtap-hitpack-worker', generation, reviewed.study_key, result
      );
      raise exception 'Changed source product or language was accepted';
    exception when sqlstate '55000' then null;
    end;
  end loop;
  if exists(select 1 from ingest.public_study_coverage_observations
    where study_key = reviewed.study_key) then raise exception 'Rejected evidence created an observation'; end if;
  select count(*) into completed_count from ingest.finalize_public_study_coverage_job_v1(
    queued, 'pgtap-hitpack-worker', generation, reviewed.study_key, result
  );
  if completed_count <> 1 then raise exception 'First finalization did not complete'; end if;
  if exists (select 1 from ingest.finalize_public_study_coverage_job_v1(
    queued, 'pgtap-hitpack-worker', generation, reviewed.study_key, result
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
    reviewed.study_key, 999, 'pgtap-hitpack-refresh', null, 3
  );
  select id, lease_generation into claimed, generation from ingest.claim_jobs_v2(
    'pgtap-hitpack-worker', array['source.public_study.opening'], 1, 600
  );
  if claimed is distinct from queued then raise exception 'Wrong refresh job claimed'; end if;
  select begun.acquired into acquired from ingest.begin_public_study_job_v2(
    queued, 'pgtap-hitpack-worker', generation, reviewed.study_key
  ) begun;
  if acquired is distinct from true then raise exception 'Refresh gate not acquired'; end if;
  select count(*) into completed_count from ingest.finalize_public_study_coverage_job_v1(
    queued, 'pgtap-hitpack-worker', generation, reviewed.study_key, result
  );
  if completed_count <> 1 then raise exception 'Refresh did not complete'; end if;
end;
$runtime$;
$test$, 'fenced first admission and refresh reject invalid evidence and deduplicate retries');

select is(
  (select jsonb_build_object('observations', count(*), 'packs', sum(pack_count))
   from ingest.public_study_coverage_observations where study_key = 'hitpack-pitch-black-cz-36-v1'),
  '{"observations":1,"packs":36}'::jsonb, 'first admission plus refresh retains one 36-pack cohort'
);
select is(
  (select count(*) from ingest.public_study_observations where study_key = 'hitpack-pitch-black-cz-36-v1'),
  0::bigint, 'no statistical observation or numerator is created'
);
select is(
  (select source_observed_at from ingest.public_study_coverage_observations
   where study_key = 'hitpack-pitch-black-cz-36-v1'),
  '2026-07-28 00:00:00+00'::timestamptz, 'publication date stays the reviewed UTC day bucket'
);
select is(
  (select c - 'updatedAt' from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries') c
   where c ->> 'countryCode' = 'CZ'),
  '{"countryCode":"CZ","countryName":"Czechia","openings":1,"packsObserved":36,
    "independentSources":1,"collectionClass":"coverage_only",
    "dataVersions":["und · me05 · Pitch Black · booster box"],
    "coverageAttributionBases":["publisher_country"]}'::jsonb,
  'public Czechia coverage exposes 36 packs and one cohort with no rate or inferred language'
);
select ok(exists (
  select 1 from ingest.source_request_gates where source_key = 'public_study_hitpack_cz_36'
    and owner_job_id is null and active_until is null
), 'successful finalization releases the Hitpack gate');
select * from finish();
rollback;
