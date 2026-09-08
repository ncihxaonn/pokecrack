begin;
select plan(6);

select is(
  (select title_fragments from ingest.reviewed_public_study_contracts() where ordinal = 29),
  array['タイ語版ポケモンカードをタイのドンキホーテで買って開封してみる。']::text[],
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
    where ordinal = 29 and study_key = 'bokunotebook-vstar-universe-th-1-v1';
  select id into queued from ingest.enqueue_public_study_coverage_job_v1(
    reviewed.study_key, 999, 'pgtap-bokunotebook-real-title', null, 3
  );
  select id, lease_generation into claimed, generation from ingest.claim_jobs_v2(
    'pgtap-bokunotebook-worker', array['source.public_study.opening'], 1, 600
  );
  if claimed is distinct from queued then
    raise exception 'Expected the exact Thai coverage job';
  end if;
  select begun.acquired into acquired from ingest.begin_public_study_job_v2(
    queued, 'pgtap-bokunotebook-worker', generation, reviewed.study_key
  ) as begun;
  if acquired is distinct from true then
    raise exception 'Expected the fenced request gate';
  end if;
  result := jsonb_build_object(
    'version', 1, 'study_key', reviewed.study_key, 'source_url', reviewed.canonical_url,
    'title', 'タイ語版ポケモンカードをタイのドンキホーテで買って開封してみる。',
    'evidence_excerpt', reviewed.evidence_excerpt,
    'evidence_sha256', encode(extensions.digest(convert_to(reviewed.evidence_excerpt, 'UTF8'), 'sha256'), 'hex'),
    'collector_version', reviewed.config ->> 'collector_version',
    'parser_version', reviewed.config ->> 'parser_version',
    'source_policy_version', reviewed.policy_version
  );
  begin
    perform ingest.finalize_public_study_coverage_job_v1(
      queued, 'pgtap-bokunotebook-worker', generation, reviewed.study_key,
      jsonb_set(result, '{title}', to_jsonb('1パック VSTARユニバース 全部で10枚'::text))
    );
    raise exception 'Body facts must not substitute for the report title';
  exception when invalid_parameter_value then
    null;
  end;
  perform ingest.finalize_public_study_coverage_job_v1(
    queued, 'pgtap-bokunotebook-worker', generation, reviewed.study_key, result
  );
end;
$runtime$;
$test$, 'the real title completes a fenced job while a body-only title is rejected');

select is(
  (select status::text from ingest.jobs where dedupe_key = 'pgtap-bokunotebook-real-title'),
  'completed', 'successful finalization completes the claimed job'
);
select is(
  (select jsonb_build_object('observations', count(*), 'packs', sum(pack_count))
   from ingest.public_study_coverage_observations
   where study_key = 'bokunotebook-vstar-universe-th-1-v1'),
  '{"observations":1,"packs":1}'::jsonb,
  'refreshing the seeded observation never duplicates its pack'
);
select is(
  (select count(*) from ingest.public_study_observations
   where study_key = 'bokunotebook-vstar-universe-th-1-v1'),
  0::bigint, 'coverage refresh still adds no rate numerator'
);
select ok(
  not has_function_privilege('anon', 'ingest.reviewed_public_study_contracts()', 'EXECUTE')
  and not has_function_privilege('service_role', 'ingest.reviewed_public_study_contracts()', 'EXECUTE'),
  'the private registry remains closed'
);
select * from finish();
rollback;
