begin;
select plan(11);

select is(
  (select title_fragments from ingest.reviewed_public_study_contracts() where ordinal = 30),
  array['Auckland Card Show 2025 Recap']::text[],
  'the title contract matches the actual adapter title, not body facts'
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
begin
  select * into strict reviewed from ingest.reviewed_public_study_contracts()
    where ordinal = 30 and study_key = 'auckland-show-mighty-ape-nz-105-v1';
  select id into queued from ingest.enqueue_public_study_coverage_job_v1(
    reviewed.study_key, 999, 'pgtap-auckland-real-title', null, 3
  );
  select id, lease_generation into claimed, generation from ingest.claim_jobs_v2(
    'pgtap-auckland-worker', array['source.public_study.opening'], 1, 600
  );
  if claimed is distinct from queued then
    raise exception 'Expected the exact NZ coverage job';
  end if;
  select begun.acquired into acquired from ingest.begin_public_study_job_v2(
    queued, 'pgtap-auckland-worker', generation, reviewed.study_key
  ) as begun;
  if acquired is distinct from true then
    raise exception 'Expected the fenced request gate';
  end if;
  result := jsonb_build_object(
    'version', 1, 'study_key', reviewed.study_key, 'source_url', reviewed.canonical_url,
    'title', 'Auckland Card Show 2025 Recap: New Zealand’s Biggest Card Event',
    'evidence_excerpt', reviewed.evidence_excerpt,
    'evidence_sha256', encode(extensions.digest(convert_to(reviewed.evidence_excerpt, 'UTF8'), 'sha256'), 'hex'),
    'collector_version', reviewed.config ->> 'collector_version',
    'parser_version', reviewed.config ->> 'parser_version',
    'source_policy_version', reviewed.policy_version
  );
  begin
    perform ingest.finalize_public_study_coverage_job_v1(
      queued, 'pgtap-auckland-worker', generation, reviewed.study_key,
      jsonb_set(result, '{title}', to_jsonb('105 packs'::text))
    );
    raise exception 'Body facts must not substitute for the report title';
  exception when invalid_parameter_value then
    null;
  end;
  perform ingest.finalize_public_study_coverage_job_v1(
    queued, 'pgtap-auckland-worker', generation, reviewed.study_key, result
  );
end;
$runtime$;
$test$, 'the real title completes a fenced job while a body-only title is rejected');

select is(
  (select status::text from ingest.jobs where dedupe_key = 'pgtap-auckland-real-title'),
  'completed', 'successful finalization completes the claimed job'
);
select is(
  (select jsonb_build_object('observations', count(*), 'packs', sum(pack_count))
   from ingest.public_study_coverage_observations
   where study_key = 'auckland-show-mighty-ape-nz-105-v1'),
  '{"observations":1,"packs":105}'::jsonb,
  'refreshing the seeded observation never duplicates its pack'
);
select is(
  (select count(*) from ingest.public_study_observations
   where study_key = 'auckland-show-mighty-ape-nz-105-v1'),
  0::bigint, 'coverage refresh still adds no rate numerator'
);
select ok(
  not has_function_privilege('anon', 'ingest.reviewed_public_study_contracts()', 'EXECUTE')
  and not has_function_privilege('service_role', 'ingest.reviewed_public_study_contracts()', 'EXECUTE'),
  'the private registry remains closed'
);
select is(
  (select config ->> 'set_language' from ingest.reviewed_public_study_contracts() where ordinal = 30),
  'und', 'unknown language never defaults to English'
);
select is(
  (select config ->> 'set_scope' from ingest.reviewed_public_study_contracts() where ordinal = 30),
  'mixed_multi_expansion', 'mixed sets are not assigned an invented single catalog set'
);
select is(
  (select count(*) from ingest.reviewed_public_study_contracts()), 33::bigint,
  'all 32 earlier contracts and the new contract survive'
);
select ok(ingest.reviewed_public_study_gates_ready_v1(), 'all source gates remain ready');
select is(
  (select value - 'updatedAt' from jsonb_array_elements(
    public.get_public_study_coverage_v3() -> 'countries'
  ) where value ->> 'countryCode' = 'NZ'),
  '{"countryCode":"NZ","countryName":"New Zealand","openings":1,
    "packsObserved":105,"independentSources":1,"collectionClass":"coverage_only",
    "dataVersions":["und · mixed-pokemon-tcg-2025 · Mixed Pokémon TCG expansions · all products"],
    "coverageAttributionBases":["publisher_country"]}'::jsonb,
  'public country payload contains only the one reviewed mixed-language cohort'
);
select * from finish();
rollback;
