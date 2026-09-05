create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select has_function(
  'public',
  'get_public_study_coverage_v3',
  array[]::text[],
  'the exact observed-sample projection exists'
);
select is(
  (select proowner::regrole::text
   from pg_proc
   where oid = 'public.get_public_study_coverage_v3()'::regprocedure),
  'postgres',
  'the observed-sample projection is postgres-owned'
);
select ok(
  (select prosecdef
   from pg_proc
   where oid = 'public.get_public_study_coverage_v3()'::regprocedure)
  and (select coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
       from pg_proc
       where oid = 'public.get_public_study_coverage_v3()'::regprocedure),
  'the observed-sample projection is SECURITY DEFINER with a fixed search path'
);
select ok(
  has_function_privilege('anon', 'public.get_public_study_coverage_v3()'::regprocedure, 'execute')
  and has_function_privilege('authenticated', 'public.get_public_study_coverage_v3()'::regprocedure, 'execute')
  and not has_function_privilege('service_role', 'public.get_public_study_coverage_v3()'::regprocedure, 'execute')
  and not has_function_privilege('public', 'public.get_public_study_coverage_v3()'::regprocedure, 'execute'),
  'only browser API roles can execute the observed-sample projection'
);

select is(
  public.get_public_study_coverage_v3() ->> 'schemaVersion',
  '3.0.0',
  'the browser contract is explicitly versioned as v3'
);
select set_eq(
  $$
    select key
    from jsonb_object_keys(public.get_public_study_coverage_v3()) as keys(key)
  $$,
  $$values ('countries'::text), ('period'), ('schemaVersion'), ('sets'), ('sources')$$,
  'v3 preserves the bounded public root shape'
);

-- Exercise both statistical-ledger and coverage-ledger numerator paths, plus a
-- coverage-only contract. The exact source evidence remains private; only the
-- noncreative arithmetic is public.
insert into catalog.sets (
  external_source,
  external_id,
  name,
  slug,
  language,
  release_date,
  series_name,
  rarity_taxonomy,
  metadata,
  is_active,
  is_demo
) values
  (
    'tcgdex', 'me03', 'Perfect Order', 'observed-rate-perfect-order',
    'en', '2026-03-27', 'Mega Evolution', '{}'::jsonb, '{}'::jsonb,
    true, false
  ),
  (
    'tcgdex', 'me04', 'Chaos Rising', 'observed-rate-chaos-rising',
    'en', '2026-05-15', 'Mega Evolution', '{}'::jsonb, '{}'::jsonb,
    true, false
  )
on conflict (external_source, external_id, language, is_demo) do update set
  is_active = true,
  updated_at = excluded.updated_at;

set local role service_role;
do $public_study_ingestion$
declare
  comic_job_id uuid;
  comic_generation bigint;
  wargamer_job_id uuid;
  wargamer_generation bigint;
  acquired_value boolean;
  comic_excerpt constant text := E'In total, I opened 55 boosters from the upcoming Perfect Order lineup.\n1 Special Illustration Rare';
  wargamer_excerpt constant text := E'after opening the 17 Pokémon Chaos Rising packs Wargamer was sent ahead of release, my opinion remains positive on those fronts.\nmissing out on any SIR mega hits.';
begin
  select jobs.id
  into comic_job_id
  from ingest.enqueue_job_v1(
    'source.public_study.opening',
    '{"study_key":"comicbook-perfect-order-us-55-v1"}'::jsonb,
    30,
    'pgtap:observed-rate:comic'
  ) as jobs;
  select jobs.id, jobs.lease_generation
  into comic_job_id, comic_generation
  from ingest.claim_jobs_v2(
    'pgtap-observed-rate-comic',
    array['source.public_study.opening'],
    1,
    600
  ) as jobs;
  select begun.acquired
  into acquired_value
  from ingest.begin_public_study_job(
    comic_job_id,
    'pgtap-observed-rate-comic',
    comic_generation
  ) as begun;
  if acquired_value is distinct from true then
    raise exception 'ComicBook observed-rate preflight was not acquired';
  end if;
  perform ingest.finalize_public_study_job(
    comic_job_id,
    'pgtap-observed-rate-comic',
    comic_generation,
    jsonb_build_object(
      'version', 1,
      'study_key', 'comicbook-perfect-order-us-55-v1',
      'source_url', 'https://comicbook.com/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates',
      'title', 'I Opened 55 Packs from Pokemon TCG Perfect Order — Pull Rates',
      'evidence_excerpt', comic_excerpt,
      'evidence_sha256',
        'a48e4b6d54243254a8c5a951161238679ecc7d053676b48555022e582428818d',
      'collector_version', 'public-study-comicbook-perfect-order-v1',
      'parser_version', 'comicbook-perfect-order-evidence-v1',
      'source_policy_version', 'public-study-comicbook-perfect-order-v1'
    )
  );

  select jobs.id
  into wargamer_job_id
  from ingest.enqueue_job_v1(
    'source.public_study.opening',
    '{"study_key":"wargamer-chaos-rising-gb-17-v1"}'::jsonb,
    29,
    'pgtap:observed-rate:wargamer'
  ) as jobs;
  select jobs.id, jobs.lease_generation
  into wargamer_job_id, wargamer_generation
  from ingest.claim_jobs_v2(
    'pgtap-observed-rate-wargamer',
    array['source.public_study.opening'],
    1,
    600
  ) as jobs;
  select begun.acquired
  into acquired_value
  from ingest.begin_public_study_job(
    wargamer_job_id,
    'pgtap-observed-rate-wargamer',
    wargamer_generation
  ) as begun;
  if acquired_value is distinct from true then
    raise exception 'Wargamer observed-rate preflight was not acquired';
  end if;
  perform ingest.finalize_public_study_job(
    wargamer_job_id,
    'pgtap-observed-rate-wargamer',
    wargamer_generation,
    jsonb_build_object(
      'version', 1,
      'study_key', 'wargamer-chaos-rising-gb-17-v1',
      'source_url', 'https://www.wargamer.com/pokemon-trading-card-game/chaos-rising-preview',
      'title', 'I opened Pokémon Chaos Rising packs early — a blessing and a curse',
      'evidence_excerpt', wargamer_excerpt,
      'evidence_sha256',
        '6ff5f864ad2c4c4637b5b8e2456dbdfe1ec6f544521f9e2f552d89c065c6f18e',
      'collector_version', 'public-study-wargamer-chaos-rising-v1',
      'parser_version', 'wargamer-chaos-rising-evidence-v1',
      'source_policy_version', 'public-study-wargamer-chaos-rising-v1'
    )
  );
end;
$public_study_ingestion$;
reset role;

insert into ingest.public_study_coverage_observations (
  study_key,
  source_policy_id,
  country_code,
  country_name,
  source_observed_at,
  pack_count,
  set_external_id,
  product_scope,
  collector_version,
  parser_version,
  source_policy_version,
  evidence_sha256,
  first_verified_at,
  last_verified_at,
  is_demo
)
select
  contracts.study_key,
  policies.id,
  contracts.config ->> 'country_code',
  contracts.config ->> 'country_name',
  (contracts.config ->> 'observed_at')::timestamptz,
  (contracts.config ->> 'pack_count')::integer,
  contracts.config ->> 'set_external_id',
  contracts.config ->> 'product_scope',
  contracts.config ->> 'collector_version',
  contracts.config ->> 'parser_version',
  contracts.policy_version,
  encode(
    extensions.digest(convert_to(contracts.evidence_excerpt, 'UTF8'), 'sha256'),
    'hex'
  ),
  statement_timestamp(),
  statement_timestamp(),
  false
from ingest.reviewed_public_study_contracts() as contracts
join ingest.source_policies as policies
  on policies.source_key = contracts.policy_key
  and not policies.is_demo
where contracts.study_key in (
  'cardchill-ascended-heroes-gb-90-v1',
  'bleedingcool-phantasmal-flames-us-36-v1',
  'tcgtalk-perfect-order-sg-54-v1',
  'pokesup-abyss-eye-jp-30-v1'
)
on conflict (study_key) do update
set source_policy_id = excluded.source_policy_id,
    country_code = excluded.country_code,
    country_name = excluded.country_name,
    source_observed_at = excluded.source_observed_at,
    pack_count = excluded.pack_count,
    set_external_id = excluded.set_external_id,
    product_scope = excluded.product_scope,
    collector_version = excluded.collector_version,
    parser_version = excluded.parser_version,
    source_policy_version = excluded.source_policy_version,
    evidence_sha256 = excluded.evidence_sha256,
    last_verified_at = excluded.last_verified_at,
    is_demo = false;

select is(
  (
    select (country.item ->> 'ratePacksObserved')::bigint
    from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries')
      as country(item)
    where country.item ->> 'countryCode' = 'US'
  ),
  91::bigint,
  'United States combines its statistical and coverage-ledger rate denominators once'
);
select is(
  (
    select (country.item ->> 'qualifyingHitPacks')::bigint
    from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries')
      as country(item)
    where country.item ->> 'countryCode' = 'US'
  ),
  2::bigint,
  'United States combines exact normalized numerators without double counting'
);
select is(
  (
    select round((country.item ->> 'observedRate')::numeric, 12)
    from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries')
      as country(item)
    where country.item ->> 'countryCode' = 'US'
  ),
  round(2::numeric / 91::numeric, 12),
  'United States publishes the literal 2 / 91 sample rate'
);
select is(
  (
    select (country.item ->> 'ratePacksObserved')::bigint
    from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries')
      as country(item)
    where country.item ->> 'countryCode' = 'GB'
  ),
  107::bigint,
  'United Kingdom includes both the 17-pack zero-hit study and 90-pack study'
);
select is(
  (
    select (country.item ->> 'qualifyingHitPacks')::bigint
    from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries')
      as country(item)
    where country.item ->> 'countryCode' = 'GB'
  ),
  1::bigint,
  'a verified zero numerator remains in the denominator instead of disappearing'
);
select is(
  (
    select round((country.item ->> 'observedRate')::numeric, 12)
    from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries')
      as country(item)
    where country.item ->> 'countryCode' = 'GB'
  ),
  round(1::numeric / 107::numeric, 12),
  'United Kingdom publishes the literal 1 / 107 sample rate'
);
select ok(
  exists (
    select 1
    from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'sources')
      as source(item)
    where source.item ->> 'id' = 'wargamer_chaos_rising_study'
      and (source.item -> 'coverage' ->> 'ratePacksObserved')::bigint = 17
      and (source.item -> 'coverage' ->> 'qualifyingHitPacks')::bigint = 0
      and (source.item -> 'coverage' ->> 'observedRate')::numeric = 0
  ),
  'a source-level zero numerator is published as the real 0 / 17 sample'
);

select is(
  (
    select (country.item ->> 'ratePacksObserved')::bigint
    from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries')
      as country(item)
    where country.item ->> 'countryCode' = 'SG'
  ),
  54::bigint,
  'Singapore publishes its exact reviewed rate denominator'
);
select is(
  (
    select (country.item ->> 'qualifyingHitPacks')::bigint
    from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries')
      as country(item)
    where country.item ->> 'countryCode' = 'SG'
  ),
  1::bigint,
  'Singapore publishes its exact reviewed qualifying-hit numerator'
);
select is(
  (
    select round((country.item ->> 'observedRate')::numeric, 12)
    from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries')
      as country(item)
    where country.item ->> 'countryCode' = 'SG'
  ),
  round(1::numeric / 54::numeric, 12),
  'Singapore observedRate is exact numerator divided by exact denominator'
);
select is(
  (
    select country.item ->> 'collectionClass'
    from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries')
      as country(item)
    where country.item ->> 'countryCode' = 'SG'
  ),
  'observed_sample',
  'a fully rate-eligible bucket is labelled as an observed sample'
);
select ok(
  exists (
    select 1
    from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'sources')
      as source(item)
    where source.item ->> 'id' = 'tcgtalk_perfect_order_study'
      and (source.item -> 'coverage' ->> 'ratePacksObserved')::bigint = 54
      and (source.item -> 'coverage' ->> 'qualifyingHitPacks')::bigint = 1
      and round((source.item -> 'coverage' ->> 'observedRate')::numeric, 12)
        = round(1::numeric / 54::numeric, 12)
      and source.item ->> 'note' like '%Singapore%Exact normalized numerator%'
  ),
  'the reviewed source card exposes the same exact arithmetic and retains attribution'
);

select ok(
  exists (
    select 1
    from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries')
      as country(item)
    where country.item ->> 'countryCode' = 'JP'
      and country.item ->> 'collectionClass' = 'coverage_only'
      and not country.item ?| array[
        'ratePacksObserved',
        'qualifyingHitPacks',
        'observedRate'
      ]
  ),
  'a reviewed Asian denominator with no normalized SIR numerator remains coverage-only'
);
select ok(
  not exists (
    select 1
    from jsonb_array_elements(public.get_public_study_coverage_v3() -> 'countries')
      as country(item)
    where country.item ?| array[
      'baselineRate',
      'posteriorMean',
      'credibleInterval',
      'deltaFromBaseline',
      'signal'
    ]
  ),
  'country sample arithmetic never smuggles in inference fields'
);
select unlike(
  public.get_public_study_coverage_v3()::text,
  '%evidenceExcerpt%',
  'the v3 payload never exposes evidence text'
);
select unlike(
  public.get_public_study_coverage_v3()::text,
  '%studyKey%',
  'the v3 payload never exposes private study identity'
);
select ok(
  not exists (
    select 1
    from jsonb_array_elements(public.get_public_study_coverage_v2() -> 'countries')
      as country(item)
    where country.item ?| array[
      'ratePacksObserved',
      'qualifyingHitPacks',
      'observedRate'
    ]
  ),
  'the backward-compatible v2 contract remains denominator-only'
);

set local role anon;
select is(
  public.get_public_study_coverage_v3() ->> 'schemaVersion',
  '3.0.0',
  'anon can read the exact observed-sample projection'
);
reset role;

set local role authenticated;
select is(
  public.get_public_study_coverage_v3() ->> 'schemaVersion',
  '3.0.0',
  'authenticated can read the exact observed-sample projection'
);
reset role;

select * from finish();
rollback;
