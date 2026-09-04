begin;

-- Worker identity and adapter wiring are owned by the parallel worker change;
-- this migration deliberately owns only the database policy and coverage
-- contract, with statistical admission remaining fail-closed.

-- PokeSup is a reviewed public, denominator-only study. The policy config is
-- the runtime source-of-truth for the exact page, product market, rights
-- boundary, and review checkpoints. It deliberately contains no statistical
-- numerator or metric identity.
insert into ingest.source_policies (
  source_key,
  display_name,
  source_kind,
  domain,
  base_url,
  enabled,
  collector_type,
  access_mode,
  robots_policy,
  routes,
  include_subdomains,
  min_delay_seconds,
  max_pages_per_run,
  max_items_per_run,
  max_concurrency,
  statistics_eligible_default,
  retention_days,
  config,
  version,
  expected_interval_seconds,
  is_demo
) values (
  'public_study_pokesup_jp_30',
  'PokeSup Abyss Eye 30-pack study',
  'public_web',
  'pokesup.com',
  'https://pokesup.com/blog/unboxing-m5/',
  true,
  'scrapling_http',
  'public',
  'respect',
  array['scrapling_http']::text[],
  false,
  30,
  2,
  1,
  1,
  true,
  730,
  '{
    "study_key":"pokesup-abyss-eye-jp-30-v1",
    "canonical_url":"https://pokesup.com/blog/unboxing-m5/",
    "collector_version":"public-study-pokesup-abyss-eye-v1",
    "parser_version":"pokesup-abyss-eye-evidence-v1",
    "country_code":"JP",
    "country_name":"Japan",
    "geography_basis":"product_market",
    "geography_confidence":"tier_b",
    "set_external_id":"M5",
    "set_language":"ja",
    "set_name":"アビスアイ",
    "set_official_url":"https://www.pokemon-card.com/ex/m5/",
    "product_scope":"booster_box",
    "pack_count":30,
    "observed_at":"2026-05-22T12:01:44Z",
    "denominator_complete":true,
    "robots_url":"https://pokesup.com/robots.txt",
    "robots_checked_at":"2026-09-04",
    "terms_checked_at":"2026-09-04",
    "terms_status":"no_independent_terms_page",
    "rights_scope":"minimal_noncreative_facts_no_media_or_body_reuse"
  }'::jsonb,
  'public-study-pokesup-abyss-eye-v1',
  86400,
  false
);

insert into ingest.source_request_gates (source_key)
values ('public_study_pokesup_jp_30');

-- Append ordinal 6 without restating or re-authoring the five historical
-- private contracts. The exact suffix guard makes registry drift fail closed.
do $migration$
declare
  definition text;
  updated_definition text;
  old_suffix text := $old$
      array['Perfect Order Pull Rates', 'Singapore Collectors Can Expect']::text[]
    );$old$;
  new_suffix text := $new$
      array['Perfect Order Pull Rates', 'Singapore Collectors Can Expect']::text[]
    ),
    (
      6,
      'pokesup-abyss-eye-jp-30-v1'::text,
      'public_study_pokesup_jp_30'::text,
      'pokesup_abyss_eye_study'::text,
      'PokeSup Abyss Eye study'::text,
      'Reviewed 30-pack Japanese public coverage study attributed to the Japan product market; it is denominator-only and does not claim a physical opening location.'::text,
      'PokeSup Abyss Eye 30-pack study'::text,
      'pokesup.com'::text,
      'https://pokesup.com/blog/unboxing-m5/'::text,
      'public-study-pokesup-abyss-eye-v1'::text,
      '{
        "study_key":"pokesup-abyss-eye-jp-30-v1",
        "canonical_url":"https://pokesup.com/blog/unboxing-m5/",
        "collector_version":"public-study-pokesup-abyss-eye-v1",
        "parser_version":"pokesup-abyss-eye-evidence-v1",
        "country_code":"JP",
        "country_name":"Japan",
        "geography_basis":"product_market",
        "geography_confidence":"tier_b",
        "set_external_id":"M5",
        "set_language":"ja",
        "set_name":"アビスアイ",
        "set_official_url":"https://www.pokemon-card.com/ex/m5/",
        "product_scope":"booster_box",
        "pack_count":30,
        "observed_at":"2026-05-22T12:01:44Z",
        "denominator_complete":true,
        "robots_url":"https://pokesup.com/robots.txt",
        "robots_checked_at":"2026-09-04",
        "terms_checked_at":"2026-09-04",
        "terms_status":"no_independent_terms_page",
        "rights_scope":"minimal_noncreative_facts_no_media_or_body_reuse"
      }'::jsonb,
      E'ポケモンカード 拡張パック「アビスアイ」開封結果！レアリティ封入率検証（その1）\nアビスアイ開封（1箱目） 左1パック 左2パック 左3パック 左4パック 左5パック 左6パック 左7パック 左8パック 左9パック 左10パック 左11パック 左12パック 左13パック 左14パック 左15パック 右1パック 右2パック 右3パック 右4パック 右5パック 右6パック 右7パック 右8パック 右9パック 右10パック 右11パック 右12パック 右13パック 右14パック 右15パック'::text,
      array['アビスアイ', '開封結果', 'アビスアイ開封（1箱目）']::text[]
    );$new$;
begin
  select pg_get_functiondef(
    'ingest.reviewed_public_study_contracts()'::regprocedure
  )
  into definition;

  if definition is null
    or position(old_suffix in definition) = 0
    or position('pokesup-abyss-eye-jp-30-v1' in definition) > 0
  then
    raise exception using
      errcode = '55000',
      message = 'reviewed public-study registry is not the expected ordinal-5 definition';
  end if;

  updated_definition := replace(definition, old_suffix, new_suffix);
  if updated_definition = definition then
    raise exception using
      errcode = '55000',
      message = 'PokeSup registry ordinal extension was not applied';
  end if;
  execute updated_definition;
end;
$migration$;

alter function ingest.reviewed_public_study_contracts() owner to postgres;
revoke all on function ingest.reviewed_public_study_contracts()
  from public, anon, authenticated, service_role;
comment on function ingest.reviewed_public_study_contracts() is
  'Owner-only immutable reviewed-study facts. Includes private historical facts and exact bounded coverage evidence; never grant this function to API or worker roles.';

-- The country-data-version projection is intentionally the preceding
-- migration. Require its source-native non-English path before enabling this
-- contract, so a partial migration cannot silently drop the Japanese version.
do $dependency$
declare
  definition text;
begin
  select pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )
  into definition;
  if definition is null
    or position('config ->> ''set_language''' in definition) = 0
    or position('config ->> ''set_name''' in definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'country data version projection is required before PokeSup coverage';
  end if;
end;
$dependency$;

-- The four worker/coverage ingestion boundaries must move together. Do not
-- widen one queue or persistence path if the prior ordinal-5 implementation
-- drifted. The legacy v1 browser projection is intentionally not rewritten:
-- it remains fixed to the three ordinal-3/4/5 sources.
do $migration$
declare
  function_oid regprocedure;
  source_definition text;
  updated_definition text;
begin
  foreach function_oid in array ARRAY[
    'ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure,
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure,
    'ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamptz,integer)'::regprocedure,
    'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)'::regprocedure
  ]
  loop
    source_definition := pg_get_functiondef(function_oid::oid);
    if position('contracts.ordinal in (3, 4, 5)' in source_definition) = 0
      or position('contracts.ordinal in (3, 4, 5, 6)' in source_definition) > 0
    then
      raise exception using
        errcode = '55000',
        message = 'reviewed coverage function is missing the expected ordinal-5 predicate',
        detail = function_oid::text;
    end if;
    updated_definition := replace(
      source_definition,
      'contracts.ordinal in (3, 4, 5)',
      'contracts.ordinal in (3, 4, 5, 6)'
    );
    if updated_definition = source_definition then
      raise exception using
        errcode = '55000',
        message = 'reviewed coverage ordinal-6 extension was not applied',
        detail = function_oid::text;
    end if;
    execute updated_definition;
  end loop;
end;
$migration$;

-- Keep English contracts on the exact live English TCGdex catalog path. A
-- contract with an explicit non-English language may proceed only with a
-- source-native name and official set URL; no English catalog row is invented.
do $migration$
declare
  definition text;
  updated_definition text;
  old_check text := $old$
  if not exists (
    select 1
    from catalog.sets as sets
    where sets.external_source = 'tcgdex'
      and sets.external_id = reviewed.config ->> 'set_external_id'
      and sets.language = 'en'
      and sets.is_active
      and not sets.is_demo
  ) then
    raise exception using
      errcode = '55000',
      message = 'coverage observation requires its exact live TCGdex set';
  end if;$old$;
  new_check text := $new$
  if not (
    (
      coalesce(nullif(reviewed.config ->> 'set_language', ''), 'en') = 'en'
      and exists (
        select 1
        from catalog.sets as sets
        where sets.external_source = 'tcgdex'
          and sets.external_id = reviewed.config ->> 'set_external_id'
          and sets.language = 'en'
          and sets.is_active
          and not sets.is_demo
      )
    )
    or (
      reviewed.config ?& array['set_language', 'set_name', 'set_official_url']
      and jsonb_typeof(reviewed.config -> 'set_language') = 'string'
      and jsonb_typeof(reviewed.config -> 'set_name') = 'string'
      and jsonb_typeof(reviewed.config -> 'set_official_url') = 'string'
      and reviewed.config ->> 'set_language' ~ '^[a-z]{2}(-[A-Za-z0-9]{2,8})*$'
      and lower(reviewed.config ->> 'set_language') !~ '^en(-|$)'
      and nullif(btrim(reviewed.config ->> 'set_name'), '') is not null
      and char_length(reviewed.config ->> 'set_name') <= 160
      and reviewed.config ->> 'set_name' !~ '[[:cntrl:]]'
      and nullif(btrim(reviewed.config ->> 'set_official_url'), '') is not null
      and reviewed.config ->> 'set_official_url' ~ '^https://'
      and char_length(reviewed.config ->> 'set_official_url') <= 2048
      and reviewed.config ->> 'set_official_url' !~ '[[:cntrl:]]'
    )
  ) then
    raise exception using
      errcode = '55000',
      message = 'coverage observation requires an exact live English TCGdex set or an explicitly named non-English official set';
  end if;$new$;
begin
  select pg_get_functiondef(
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure
  )
  into definition;
  if definition is null
    or position(old_check in definition) = 0
    or position('set_language' in definition) > 0
  then
    raise exception using
      errcode = '55000',
      message = 'coverage finalizer is not the expected English-catalog definition';
  end if;
  updated_definition := replace(definition, old_check, new_check);
  if updated_definition = definition then
    raise exception using
      errcode = '55000',
      message = 'coverage finalizer non-English catalog extension was not applied';
  end if;
  execute updated_definition;
end;
$migration$;

comment on function ingest.finalize_public_study_coverage_job_v1(
  uuid, text, bigint, text, jsonb
) is
  'Generation-fenced verifier for six reviewed denominator-only observations. English contracts require the exact live TCGdex catalog; explicit non-English contracts require a bounded source-native set name and official set URL. It cannot publish a numerator or inference.';

alter table ingest.jobs
  drop constraint jobs_reviewed_coverage_schedule_allowlist_check;

alter table ingest.jobs
  add constraint jobs_reviewed_coverage_schedule_allowlist_check
  check (
    dedupe_key is null
    or dedupe_key !~ '^reviewed-coverage-schedule:'
    or is_demo
    or (
      job_type = 'source.public_study.opening'
      and payload ?& array['study_key']
      and payload - array['study_key'] = '{}'::jsonb
      and jsonb_typeof(payload -> 'study_key') = 'string'
      and payload ->> 'study_key' in (
        'cardchill-ascended-heroes-gb-90-v1',
        'bleedingcool-phantasmal-flames-us-36-v1',
        'tcgtalk-perfect-order-sg-54-v1',
        'pokesup-abyss-eye-jp-30-v1'
      )
    )
  );

-- Leave the statistical ledger schema and its two-study begin/finalize path
-- unchanged. Ordinal 6 is admitted only by the denominator-only coverage
-- boundaries above; a future statistical promotion would require its own
-- separately reviewed migration.

commit;
