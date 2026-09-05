-- Brazil reviewed public-study registry, policy gate, and statistical contract.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select plan(25);

select ok(
  exists (
    select 1
    from ingest.source_policies
    where source_key = 'public_study_pontocom_br_48'
      and display_name = 'PontoCOM Heróis Excelsos Brazil 48-pack study'
      and domain = 'pontocomdesenvolvimento.net'
      and base_url = 'https://pontocomdesenvolvimento.net/postagem/1028/herois-excelsos-vale-a-pena-abrir-uma-case-lacrada'
      and version = 'public-study-pontocom-herois-excelsos-v1'
      and enabled
      and statistics_eligible_default
      and not is_demo
  ),
  'Brazil PontoCOM source policy is exact and live'
);

select is(
  (select config ->> 'study_key' from ingest.source_policies where source_key = 'public_study_pontocom_br_48'),
  'pontocom-herois-excelsos-br-48-v1',
  'Brazil policy records the reviewed study key'
);
select is(
  (select config ->> 'set_language' from ingest.source_policies where source_key = 'public_study_pontocom_br_48'),
  'pt-BR',
  'Brazil policy records pt-BR'
);
select is(
  (select config ->> 'set_name' from ingest.source_policies where source_key = 'public_study_pontocom_br_48'),
  'Heróis Excelsos',
  'Brazil policy records the native set name'
);
select is(
  (select config ->> 'product_scope' from ingest.source_policies where source_key = 'public_study_pontocom_br_48'),
  'four_pack_blister',
  'Brazil policy keeps four-pack blister product identity'
);
select is(
  (select config ->> 'denominator_derivation' from ingest.source_policies where source_key = 'public_study_pontocom_br_48'),
  '12×4',
  'Brazil policy records the explicit 12×4 denominator derivation'
);
select is(
  (select (config ->> 'pack_count')::integer from ingest.source_policies where source_key = 'public_study_pontocom_br_48'),
  48,
  'Brazil policy records 48 packs'
);
select is(
  (select (config ->> 'qualifying_hit_pack_count')::integer from ingest.source_policies where source_key = 'public_study_pontocom_br_48'),
  1,
  'Brazil policy records exactly one normalized SIR hit pack'
);
select is(
  (select config #>> '{card_rarity_mapping,0,official_rarity_en}' from ingest.source_policies where source_key = 'public_study_pontocom_br_48'),
  'Special Illustration Rare',
  'Mega Meganium ex is mapped to official Special Illustration Rare'
);
select is(
  (select config #>> '{card_rarity_mapping,1,official_rarity_en}' from ingest.source_policies where source_key = 'public_study_pontocom_br_48'),
  'Illustration Rare',
  'Mawile is not normalized as SIR'
);
select is(
  (select config #>> '{card_rarity_mapping,2,official_rarity_en}' from ingest.source_policies where source_key = 'public_study_pontocom_br_48'),
  'Illustration Rare',
  'Heliolisk is not normalized as SIR'
);

select ok(
  exists (
    select 1 from ingest.source_request_gates
    where source_key = 'public_study_pontocom_br_48'
  ),
  'Brazil source request gate exists'
);
select ok(
  ingest.reviewed_public_study_gates_ready_v1(),
  'all current reviewed public-study gates are ready'
);
select is(
  (
    select count(*)::integer
    from ingest.reviewed_public_study_contracts()
    where ordinal between 1 and 10
  ),
  10,
  'reviewed public-study registry retains its ten-contract Brazil prefix'
);
select ok(
  exists (
    select 1
    from ingest.reviewed_public_study_contracts()
    where ordinal = 10
      and study_key = 'pontocom-herois-excelsos-br-48-v1'
      and policy_key = 'public_study_pontocom_br_48'
      and evidence_excerpt like 'ABRI uma CASE com 12 Blisters Quadruplos%'
      and public_note like '%1/48%'
      and public_note like '%Mawile 246/217%'
      and public_note like '%Heliolisk 229/217%'
  ),
  'Brazil contract is ordinal 10 with the public 1/48 note and IR boundary'
);
select matches(
  pg_get_constraintdef(
    (select oid from pg_constraint
     where conrelid = 'ingest.public_study_observations'::regclass
       and conname = 'public_study_observations_product_check')
  ),
  'four_pack_blister',
  'statistical ledger admits the exact Brazil product scope'
);
select matches(
  pg_get_functiondef(
    'ingest.begin_public_study_job(uuid,text,bigint)'::regprocedure
  ),
  'pontocom-herois-excelsos-br-48-v1',
  'begin RPC allowlists Brazil'
);
select matches(
  pg_get_functiondef(
    'ingest.finalize_public_study_job(uuid,text,bigint,jsonb)'::regprocedure
  ),
  'ABRI uma CASE com 12 Blisters Quadruplos',
  'finalize RPC pins the reviewed Brazil evidence'
);
select matches(
  pg_get_constraintdef(
    (select oid from pg_constraint
     where conrelid = 'ingest.jobs'::regclass
       and conname = 'jobs_live_scheduled_enqueue_allowlist_check')
  ),
  'pontocom-herois-excelsos-br-48-v1',
  'scheduled job table boundary allowlists Brazil'
);

select ok(
  exists (
    select 1
    from ingest.public_study_coverage_observations as coverage
    join ingest.source_policies as policies
      on policies.id = coverage.source_policy_id
    where coverage.study_key = 'pontocom-herois-excelsos-br-48-v1'
      and coverage.country_code = 'BR'
      and coverage.country_name = 'Brazil'
      and coverage.source_observed_at = '2026-01-26T23:29:00Z'::timestamptz
      and coverage.pack_count = 48
      and coverage.set_external_id = 'me02.5'
      and coverage.product_scope = 'four_pack_blister'
      and coverage.evidence_sha256 = '4788f28b2e61c0b1879d287da82e4c45712ba7ba0a84cb1599c32611e1968da6'
      and coverage.first_verified_at = coverage.last_verified_at
      and not coverage.is_demo
      and policies.source_key = 'public_study_pontocom_br_48'
  ),
  'manual timestamped review seeds one exact Brazil coverage observation'
);

select ok(
  exists (
    select 1
    from jsonb_array_elements(
      public.get_public_study_coverage_v3() -> 'countries'
    ) as country
    where country ->> 'countryCode' = 'BR'
  ),
  'public v3 includes Brazil in the current country list'
);

select is(
  (
    select country ->> 'ratePacksObserved'
    from jsonb_array_elements(
      public.get_public_study_coverage_v3() -> 'countries'
    ) as country
    where country ->> 'countryCode' = 'BR'
  ),
  '48',
  'public v3 exposes the exact 48-pack Brazil denominator'
);

select is(
  (
    select country ->> 'qualifyingHitPacks'
    from jsonb_array_elements(
      public.get_public_study_coverage_v3() -> 'countries'
    ) as country
    where country ->> 'countryCode' = 'BR'
  ),
  '1',
  'public v3 exposes exactly one normalized Brazil SIR pack'
);

select is(
  (
    select round((country ->> 'observedRate')::numeric, 6)::text
    from jsonb_array_elements(
      public.get_public_study_coverage_v3() -> 'countries'
    ) as country
    where country ->> 'countryCode' = 'BR'
  ),
  '0.020833',
  'public v3 computes the descriptive Brazil rate as 1/48'
);

select ok(
  not exists (
    select 1
    from jsonb_array_elements(
      public.get_public_study_coverage_v3() -> 'countries'
    ) as country
    where country ->> 'countryCode' = 'BR'
      and (
        country ? 'baselineRate'
        or country ? 'posteriorMean'
        or country ? 'credibleInterval'
        or country ? 'deltaFromBaseline'
        or country ? 'signal'
      )
  ),
  'Brazil direct sample arithmetic does not publish inference fields'
);

select * from finish();
rollback;
