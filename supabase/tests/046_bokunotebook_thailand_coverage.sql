begin;
select plan(11);

select is(
  (select count(*) from ingest.reviewed_public_study_contracts()
   where ordinal = 29 and study_key = 'bokunotebook-vstar-universe-th-1-v1'),
  1::bigint, 'Thai VSTAR Universe appends exact ordinal 29'
);
select is(
  (select pack_count from ingest.public_study_coverage_observations
   where study_key = 'bokunotebook-vstar-universe-th-1-v1'),
  1, 'one real pack, not the ten cards inside it'
);
select is(
  (select pack_count from ingest.public_study_coverage_observations
   where study_key = 'allonline-mega-dream-ex-th-10-v1'),
  10, 'existing Thai source remains unchanged and independent'
);
select is(
  (select evidence_sha256 from ingest.public_study_coverage_observations
   where study_key = 'bokunotebook-vstar-universe-th-1-v1'),
  '575413295f78946c02ce9c97319f4688652a55d113df54b57c7fed3f626a9f31', 'minimal factual evidence digest is exact'
);
select ok(ingest.reviewed_public_study_gates_ready_v1(), '29-source request gates ready');
select ok(
  not has_function_privilege('anon', 'ingest.reviewed_public_study_contracts()', 'EXECUTE')
  and not has_function_privilege('service_role', 'ingest.reviewed_public_study_contracts()', 'EXECUTE'),
  'private registry permissions remain closed'
);
select is(
  (select config ->> 'set_language' from ingest.reviewed_public_study_contracts() where ordinal = 29),
  'th', 'Thai product is not pooled into Japanese S12a'
);
select ok(
  not (select config ?| array['qualifying_hit_pack_count', 'qualifying_metric', 'metric_version']
       from ingest.reviewed_public_study_contracts() where ordinal = 29),
  'no normalized numerator or probability added'
);
select ok(
  (select config -> 'opening_country' = 'null'::jsonb
     and config -> 'opened_at' = 'null'::jsonb
     and config ->> 'geography_basis' = 'product_market'
     and config ->> 'observed_at' = '2026-07-01T12:01:46Z'
   from ingest.reviewed_public_study_contracts() where ordinal = 29),
  'publication and product market do not invent opening place/date'
);
select is(
  (select count(*) from ingest.public_study_observations
   where study_key = 'bokunotebook-vstar-universe-th-1-v1'),
  0::bigint, 'new pack never enters the rate observation table'
);
select is(
  (select config ->> 'observed_card_count' from ingest.reviewed_public_study_contracts() where ordinal = 29),
  '10', 'card count remains distinct from pack count'
);
select * from finish();
rollback;
