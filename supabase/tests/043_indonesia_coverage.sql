begin;
select plan(8);

select is(
  (select count(*) from ingest.reviewed_public_study_contracts()
   where ordinal = 26 and study_key = 'bikuhime-hantaman-pertama-a-id-20-v1'),
  1::bigint, 'Indonesian first-box contract is append-only ordinal 26'
);
select is(
  (select config ->> 'geography_basis' from ingest.reviewed_public_study_contracts()
   where ordinal = 26),
  'product_market', 'product market does not claim physical opening location'
);
select is(
  (select pack_count from ingest.public_study_coverage_observations
   where study_key = 'bikuhime-hantaman-pertama-a-id-20-v1'),
  20, 'one complete first Set A box, not all three boxes or card counts'
);
select is(
  (select evidence_sha256 from ingest.public_study_coverage_observations
   where study_key = 'bikuhime-hantaman-pertama-a-id-20-v1'),
  '693653031f398c3006a7aa6d3b476c968f5b3f67d6452e73d904ed1ef377b328',
  'exact minimal first-box fact hash'
);
select ok(ingest.reviewed_public_study_gates_ready_v1(), 'new request gate is ready');
select ok(
  not has_function_privilege('anon', 'ingest.reviewed_public_study_contracts()', 'EXECUTE')
  and not has_function_privilege('service_role', 'ingest.reviewed_public_study_contracts()', 'EXECUTE'),
  'private registry remains inaccessible to clients and workers'
);
select is(
  (select item ->> 'collectionClass'
   from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries') as countries(item)
   where item ->> 'countryCode' = 'ID'),
  'coverage_only', 'public Indonesia entry is coverage only, never a hit rate'
);
select ok(
  not (select config ?| array['qualifying_hit_pack_count', 'qualifying_metric', 'metric_version']
       from ingest.reviewed_public_study_contracts() where ordinal = 26),
  'no numerator can enter the rate pipeline'
);

select * from finish();
rollback;
