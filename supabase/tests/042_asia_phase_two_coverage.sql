begin;
select plan(7);

select is(
  (select count(*) from ingest.reviewed_public_study_contracts()
   where ordinal = 25 and study_key = 'garbage-rips-gem-vol2-cn-1-v1'),
  1::bigint, 'Chinese product-market contract is append-only ordinal 25'
);
select is(
  (select config ->> 'geography_basis' from ingest.reviewed_public_study_contracts()
   where ordinal = 25),
  'product_market', 'does not claim the US publisher opened the pack in China'
);
select is(
  (select pack_count from ingest.public_study_coverage_observations
   where study_key = 'garbage-rips-gem-vol2-cn-1-v1'),
  1, 'one complete pack, not the four cards or a full booster box'
);
select is(
  (select evidence_sha256 from ingest.public_study_coverage_observations
   where study_key = 'garbage-rips-gem-vol2-cn-1-v1'),
  'a53e1e4f4b881e8d7f8ba006764aae8b8e27323ffa1a41a138caf5c05ff1c804',
  'observation retains the exact minimal fact hash'
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
   where item ->> 'countryCode' = 'CN'),
  'coverage_only', 'public China entry is coverage only, never a fabricated hit rate'
);

select * from finish();
rollback;
