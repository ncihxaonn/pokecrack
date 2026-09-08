begin;
select plan(11);

select is(
  (select count(*) from ingest.reviewed_public_study_contracts()
   where ordinal = 28 and study_key = 'nanjakorya-paradigm-jp-100-v1'),
  1::bigint, 'Paradigm Trigger appends exactly ordinal 28'
);
select is(
  (select pack_count from ingest.public_study_coverage_observations
   where study_key = 'nanjakorya-paradigm-jp-100-v1'),
  100, 'new complete primary cohort has 100 packs'
);
select is(
  (select pack_count from ingest.public_study_coverage_observations
   where study_key = 'nanjakorya-star-birth-jp-100-v1'),
  100, 'same publisher Star Birth cohort remains independent and unchanged'
);
select is(
  (select evidence_sha256 from ingest.public_study_coverage_observations
   where study_key = 'nanjakorya-paradigm-jp-100-v1'),
  'ee845effa99200b85ff4380f16380f80aeec68a5398fc7d68a4b552c2cb16203',
  'minimal retained title digest is exact'
);
select ok(ingest.reviewed_public_study_gates_ready_v1(), '28-source request gates ready');
select ok(
  not has_function_privilege('anon', 'ingest.reviewed_public_study_contracts()', 'EXECUTE')
  and not has_function_privilege('service_role', 'ingest.reviewed_public_study_contracts()', 'EXECUTE'),
  'private registry permissions remain closed'
);
select is(
  (select config -> 'rarity_card_counts' from ingest.reviewed_public_study_contracts() where ordinal = 28),
  '{"RR":14,"RRR":7,"SR":1,"HR":2}'::jsonb, 'native source counts preserved'
);
select ok(
  not (select config ?| array['qualifying_hit_pack_count', 'qualifying_metric', 'metric_version']
       from ingest.reviewed_public_study_contracts() where ordinal = 28),
  'no normalized numerator added'
);
select ok(
  (select config -> 'opening_country' = 'null'::jsonb
     and config -> 'opened_at' = 'null'::jsonb
     and config ->> 'geography_basis' = 'product_market'
     and config ->> 'observed_at' = '2022-10-21T11:10:35Z'
   from ingest.reviewed_public_study_contracts() where ordinal = 28),
  'publication and product market do not invent physical opening facts'
);
select is(
  (select count(*) from ingest.public_study_observations
   where study_key = 'nanjakorya-paradigm-jp-100-v1'),
  0::bigint, 'new cohort never enters hit-rate observation table'
);
select ok(
  (select config -> 'source_label_inconsistencies' = 'true'::jsonb
   from ingest.reviewed_public_study_contracts() where ordinal = 28),
  'source label inconsistencies remain explicitly visible'
);
select * from finish();
rollback;
