begin;
select plan(10);

select is(
  (select count(*) from ingest.reviewed_public_study_contracts()
   where ordinal = 27 and study_key = 'nanjakorya-star-birth-jp-100-v1'),
  1::bigint, 'Japanese Star Birth contract is append-only ordinal 27'
);
select is(
  (select config ->> 'geography_basis' from ingest.reviewed_public_study_contracts()
   where ordinal = 27),
  'product_market', 'product market does not claim physical opening location'
);
select is(
  (select pack_count from ingest.public_study_coverage_observations
   where study_key = 'nanjakorya-star-birth-jp-100-v1'),
  100, 'one complete cohort, not nine segments or rarity card counts'
);
select is(
  (select evidence_sha256 from ingest.public_study_coverage_observations
   where study_key = 'nanjakorya-star-birth-jp-100-v1'),
  'e9c87d754c51746c9af0cf3c85d164bfee5bf90c84e69e8c65ca46cfda2601e9',
  'exact minimal report fact hash'
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
   where item ->> 'countryCode' = 'JP'),
  'coverage_only', 'public Japan entry is coverage only, never a hit rate'
);
select ok(
  not (select config ?| array['qualifying_hit_pack_count', 'qualifying_metric', 'metric_version']
       from ingest.reviewed_public_study_contracts() where ordinal = 27),
  'no numerator can enter the rate pipeline'
);

select is(
  (select config -> 'rarity_card_counts' from ingest.reviewed_public_study_contracts()
   where ordinal = 27),
  '{"RR":16,"RRR":6,"SR":4,"HR":1}'::jsonb,
  'native rarity card counts retained without becoming rate numerators'
);
select ok(
  (select config -> 'opening_country' = 'null'::jsonb
     and config -> 'opened_at' = 'null'::jsonb
     and config ->> 'observed_at' = '2022-02-21T20:40:46Z'
   from ingest.reviewed_public_study_contracts() where ordinal = 27),
  'publication date does not invent opening date or physical geography'
);
select * from finish();
rollback;
