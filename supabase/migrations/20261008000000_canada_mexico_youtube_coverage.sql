begin;

-- Two exact public YouTube watch pages provide complete pack denominators for
-- reviewed publisher-country coverage in Mexico and Canada. Neither source
-- supplies a normalized SIR-pack numerator, so both remain coverage-only.
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
) values
(
  'public_study_indigo_geek_mx_50',
  'Indigo Geek Megaevolución 50-pack coverage',
  'public_web',
  'www.youtube.com',
  'https://www.youtube.com/watch?v=KNCSNJNcjJ8',
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
    "study_key":"indigo-geek-megaevolucion-mx-50-v1",
    "canonical_url":"https://www.youtube.com/watch?v=KNCSNJNcjJ8",
    "fetch_url":"https://www.youtube.com/watch?v=KNCSNJNcjJ8",
    "collector_version":"public-study-indigo-geek-megaevolucion-youtube-v1",
    "parser_version":"indigo-geek-megaevolucion-evidence-v1",
    "country_code":"MX",
    "country_name":"Mexico",
    "geography_basis":"publisher_country",
    "geography_confidence":"tier_b",
    "publisher_country_url":"https://www.youtube.com/@IndigoGeek/about",
    "publisher_channel_id":"UCGri3BoVzarWIYCzg8MEQjw",
    "publisher_country_evidence":"country:\"Mexico\"",
    "publisher_country_checked_at":"2026-09-05",
    "geography_review_method":"manual_static_channel_about_review",
    "set_external_id":"me01",
    "set_language":"es-MX",
    "set_name":"Megaevolución",
    "set_official_url":"https://tcg.pokemon.com/es-mx/expansions/mega-evolution/",
    "product_name":"ETB + Booster Box + Combina y Combate",
    "product_scope":"all",
    "pack_count":50,
    "observed_at":"2025-09-12T13:00:41Z",
    "source_published_at":"2025-09-12T06:00:41-07:00",
    "denominator_complete":true,
    "denominator_basis":"source_declared_complete_opening",
    "source_native_products":["etb","booster_box","combina_y_combate"],
    "robots_url":"https://www.youtube.com/robots.txt",
    "robots_checked_at":"2026-09-05",
    "robots_decision":"watch_route_not_disallowed",
    "terms_url":"https://www.youtube.com/static?template=terms",
    "terms_checked_at":"2026-09-05",
    "terms_effective_date":"2023-12-15",
    "terms_status":"public_browse_static_metadata_only",
    "rights_scope":"minimal_noncreative_facts_no_media_transcript_or_body_reuse"
  }'::jsonb,
  'public-study-indigo-geek-megaevolucion-youtube-v1',
  86400,
  false
),
(
  'public_study_pokehanna_ca_9',
  'PokeHanna Ascended Heroes 9-pack coverage',
  'public_web',
  'www.youtube.com',
  'https://www.youtube.com/watch?v=Jj0IxqUYat8',
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
    "study_key":"pokehanna-ascended-heroes-ca-9-v1",
    "canonical_url":"https://www.youtube.com/watch?v=Jj0IxqUYat8",
    "fetch_url":"https://www.youtube.com/watch?v=Jj0IxqUYat8",
    "collector_version":"public-study-pokehanna-ascended-heroes-youtube-v1",
    "parser_version":"pokehanna-ascended-heroes-evidence-v1",
    "country_code":"CA",
    "country_name":"Canada",
    "geography_basis":"publisher_country",
    "geography_confidence":"tier_b",
    "publisher_country_url":"https://www.youtube.com/@PokeHanna/about",
    "publisher_channel_id":"UC6stWaGoj-9rsEOzYv56ftQ",
    "publisher_country_evidence":"country:\"Canada\"",
    "publisher_country_checked_at":"2026-09-05",
    "geography_review_method":"manual_static_channel_about_review",
    "set_external_id":"me02.5",
    "set_language":"en",
    "set_name":"Ascended Heroes",
    "set_official_url":"https://www.pokemon.com/us/pokemon-tcg/product-gallery/mega-evolution-ascended-heroes-elite-trainer-box",
    "product_name":"Ascended Heroes Elite Trainer Box",
    "product_scope":"etb",
    "pack_count":9,
    "observed_at":"2026-04-05T18:00:15Z",
    "source_published_at":"2026-04-05T11:00:15-07:00",
    "denominator_complete":true,
    "denominator_basis":"source_named_standard_etb_plus_official_9_pack_spec",
    "denominator_derivation":"one_standard_etb_x_9",
    "robots_url":"https://www.youtube.com/robots.txt",
    "robots_checked_at":"2026-09-05",
    "robots_decision":"watch_route_not_disallowed",
    "terms_url":"https://www.youtube.com/static?template=terms",
    "terms_checked_at":"2026-09-05",
    "terms_effective_date":"2023-12-15",
    "terms_status":"public_browse_static_metadata_only",
    "rights_scope":"minimal_noncreative_facts_no_media_transcript_or_body_reuse"
  }'::jsonb,
  'public-study-pokehanna-ascended-heroes-youtube-v1',
  86400,
  false
);

insert into ingest.source_request_gates (source_key)
values
  ('public_study_indigo_geek_mx_50'),
  ('public_study_pokehanna_ca_9');

create or replace function ingest.reviewed_public_study_gates_ready_v1()
returns boolean
language sql
stable
security definer
parallel safe
set search_path = pg_catalog
as $$
  select count(*) = 14
  from ingest.source_request_gates as gates
  where gates.source_key in (
    'public_study_comicbook_us_55',
    'public_study_wargamer_gb_17',
    'public_study_cardchill_gb_90',
    'public_study_bleedingcool_us_36',
    'public_study_tcgtalk_sg_54',
    'public_study_pokesup_jp_30',
    'public_study_limitsend_kr_30',
    'public_study_buyfunlife_tw_40',
    'public_study_allonline_th_10',
    'public_study_pontocom_br_48',
    'public_study_richards_bricks_pr_18',
    'public_study_richards_bricks_pr_36',
    'public_study_indigo_geek_mx_50',
    'public_study_pokehanna_ca_9'
  );
$$;

alter function ingest.reviewed_public_study_gates_ready_v1() owner to postgres;
revoke all on function ingest.reviewed_public_study_gates_ready_v1()
  from public, anon, authenticated, service_role;
grant execute on function ingest.reviewed_public_study_gates_ready_v1()
  to service_role;
comment on function ingest.reviewed_public_study_gates_ready_v1() is
  'Boolean-only readiness check for all exact reviewed public-study request gates; it exposes no gate identity or lease state.';

-- Append ordinals 13 and 14 only when the exact Puerto Rico ordinal-12 suffix
-- is still present. Both new contracts explicitly omit normalized numerators.
do $migration$
declare
  definition text;
  updated_definition text;
  old_suffix text := $old$
      array['Mega Evolution Booster Box unboxing']::text[]
    );$old$;
  new_suffix text := $new$
      array['Mega Evolution Booster Box unboxing']::text[]
    ),
    (
      13,
      'indigo-geek-megaevolucion-mx-50-v1'::text,
      'public_study_indigo_geek_mx_50'::text,
      'indigo_geek_megaevolucion_study'::text,
      'Indigo GEEK Megaevolución 50-pack study'::text,
      'Reviewed Mexico publisher-country coverage: one source-declared complete 50-pack Megaevolución opening spanning an ETB, booster box, and Combina y Combate product. The public channel About metadata identifies Mexico, but no physical opening location is claimed. No normalized SIR-pack numerator exists, so no rate or inference is published.'::text,
      'Indigo Geek Megaevolución 50-pack coverage'::text,
      'www.youtube.com'::text,
      'https://www.youtube.com/watch?v=KNCSNJNcjJ8'::text,
      'public-study-indigo-geek-megaevolucion-youtube-v1'::text,
      '{
        "study_key":"indigo-geek-megaevolucion-mx-50-v1",
        "canonical_url":"https://www.youtube.com/watch?v=KNCSNJNcjJ8",
        "fetch_url":"https://www.youtube.com/watch?v=KNCSNJNcjJ8",
        "collector_version":"public-study-indigo-geek-megaevolucion-youtube-v1",
        "parser_version":"indigo-geek-megaevolucion-evidence-v1",
        "country_code":"MX",
        "country_name":"Mexico",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "publisher_country_url":"https://www.youtube.com/@IndigoGeek/about",
        "publisher_channel_id":"UCGri3BoVzarWIYCzg8MEQjw",
        "publisher_country_evidence":"country:\"Mexico\"",
        "publisher_country_checked_at":"2026-09-05",
        "geography_review_method":"manual_static_channel_about_review",
        "set_external_id":"me01",
        "set_language":"es-MX",
        "set_name":"Megaevolución",
        "set_official_url":"https://tcg.pokemon.com/es-mx/expansions/mega-evolution/",
        "product_name":"ETB + Booster Box + Combina y Combate",
        "product_scope":"all",
        "pack_count":50,
        "observed_at":"2025-09-12T13:00:41Z",
        "source_published_at":"2025-09-12T06:00:41-07:00",
        "denominator_complete":true,
        "denominator_basis":"source_declared_complete_opening",
        "source_native_products":["etb","booster_box","combina_y_combate"],
        "robots_url":"https://www.youtube.com/robots.txt",
        "robots_checked_at":"2026-09-05",
        "robots_decision":"watch_route_not_disallowed",
        "terms_url":"https://www.youtube.com/static?template=terms",
        "terms_checked_at":"2026-09-05",
        "terms_effective_date":"2023-12-15",
        "terms_status":"public_browse_static_metadata_only",
        "rights_scope":"minimal_noncreative_facts_no_media_transcript_or_body_reuse"
      }'::jsonb,
      E'Abrimos 50 SOBRES de la nueva expansión de Pokémon JCC: Megaevolución\n50 sobres · ETB · booster box · Combina y combate'::text,
      array['Abrimos 50 SOBRES de la nueva expansión de Pokémon JCC: Megaevolución']::text[]
    ),
    (
      14,
      'pokehanna-ascended-heroes-ca-9-v1'::text,
      'public_study_pokehanna_ca_9'::text,
      'pokehanna_ascended_heroes_study'::text,
      'PokéHanna Ascended Heroes 9-pack study'::text,
      'Reviewed Canada publisher-country coverage: the source declares all packs from an ordinarily named Ascended Heroes Elite Trainer Box, paired with the official nine-pack standard-ETB specification. The public channel About metadata identifies Canada, but no physical opening location is claimed. No normalized SIR-pack numerator exists, so no rate or inference is published.'::text,
      'PokeHanna Ascended Heroes 9-pack coverage'::text,
      'www.youtube.com'::text,
      'https://www.youtube.com/watch?v=Jj0IxqUYat8'::text,
      'public-study-pokehanna-ascended-heroes-youtube-v1'::text,
      '{
        "study_key":"pokehanna-ascended-heroes-ca-9-v1",
        "canonical_url":"https://www.youtube.com/watch?v=Jj0IxqUYat8",
        "fetch_url":"https://www.youtube.com/watch?v=Jj0IxqUYat8",
        "collector_version":"public-study-pokehanna-ascended-heroes-youtube-v1",
        "parser_version":"pokehanna-ascended-heroes-evidence-v1",
        "country_code":"CA",
        "country_name":"Canada",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "publisher_country_url":"https://www.youtube.com/@PokeHanna/about",
        "publisher_channel_id":"UC6stWaGoj-9rsEOzYv56ftQ",
        "publisher_country_evidence":"country:\"Canada\"",
        "publisher_country_checked_at":"2026-09-05",
        "geography_review_method":"manual_static_channel_about_review",
        "set_external_id":"me02.5",
        "set_language":"en",
        "set_name":"Ascended Heroes",
        "set_official_url":"https://www.pokemon.com/us/pokemon-tcg/product-gallery/mega-evolution-ascended-heroes-elite-trainer-box",
        "product_name":"Ascended Heroes Elite Trainer Box",
        "product_scope":"etb",
        "pack_count":9,
        "observed_at":"2026-04-05T18:00:15Z",
        "source_published_at":"2026-04-05T11:00:15-07:00",
        "denominator_complete":true,
        "denominator_basis":"source_named_standard_etb_plus_official_9_pack_spec",
        "denominator_derivation":"one_standard_etb_x_9",
        "robots_url":"https://www.youtube.com/robots.txt",
        "robots_checked_at":"2026-09-05",
        "robots_decision":"watch_route_not_disallowed",
        "terms_url":"https://www.youtube.com/static?template=terms",
        "terms_checked_at":"2026-09-05",
        "terms_effective_date":"2023-12-15",
        "terms_status":"public_browse_static_metadata_only",
        "rights_scope":"minimal_noncreative_facts_no_media_transcript_or_body_reuse"
      }'::jsonb,
      E'Opening The Ascended Heroes ETB! (Pokémon card opening)\nopening all the packs · Ascended Heroes Elite Trainer Box · standard ETB = 9 packs'::text,
      array['Opening The Ascended Heroes ETB! (Pokémon card opening)']::text[]
    );$new$;
begin
  select pg_get_functiondef(
    'ingest.reviewed_public_study_contracts()'::regprocedure
  )
  into definition;

  if definition is null
    or position(old_suffix in definition) = 0
    or position('indigo-geek-megaevolucion-mx-50-v1' in definition) > 0
    or position('pokehanna-ascended-heroes-ca-9-v1' in definition) > 0
    or (
      select array_agg(contracts.ordinal order by contracts.ordinal)
      from ingest.reviewed_public_study_contracts() as contracts
    ) is distinct from array[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12]::integer[]
  then
    raise exception using
      errcode = '55000',
      message = 'reviewed public-study registry is not the expected ordinal-12 definition';
  end if;

  updated_definition := replace(definition, old_suffix, new_suffix);
  if updated_definition = definition then
    raise exception using
      errcode = '55000',
      message = 'Canada/Mexico reviewed coverage registry extension was not applied';
  end if;
  execute updated_definition;
end;
$migration$;

alter function ingest.reviewed_public_study_contracts() owner to postgres;
revoke all on function ingest.reviewed_public_study_contracts()
  from public, anon, authenticated, service_role;
comment on function ingest.reviewed_public_study_contracts() is
  'Owner-only immutable reviewed-study facts. Includes private historical facts and exact bounded coverage evidence; never grant this function to API or worker roles.';

-- Move all four denominator-only queue and persistence boundaries together.
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
    if position(
      'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12)'
      in source_definition
    ) = 0
      or position(
        'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14)'
        in source_definition
      ) > 0
    then
      raise exception using
        errcode = '55000',
        message = 'reviewed coverage function is missing the expected ordinal-12 predicate',
        detail = function_oid::text;
    end if;
    updated_definition := replace(
      source_definition,
      'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12)',
      'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14)'
    );
    if updated_definition = source_definition then
      raise exception using
        errcode = '55000',
        message = 'reviewed coverage ordinal-13/14 extension was not applied',
        detail = function_oid::text;
    end if;
    execute updated_definition;
  end loop;
end;
$migration$;

comment on function ingest.finalize_public_study_coverage_job_v1(
  uuid, text, bigint, text, jsonb
) is
  'Generation-fenced verifier for eleven reviewed denominator-only contracts. English contracts require the exact live TCGdex catalog, except the two exact source-native Puerto Rico product identities; explicit non-English contracts require a bounded source-native set name and official set URL. It cannot publish a numerator or inference.';

-- Seed the two facts manually verified from exact static watch metadata,
-- publisher About metadata, and the official nine-pack ETB product page. This
-- makes real coverage visible immediately without claiming a scheduled run.
do $migration$
declare
  mexico_policy_id uuid;
  canada_policy_id uuid;
  verification_time timestamptz := statement_timestamp();
  mexico_evidence text :=
    'c270707bfa43c79b8362a4cf5cab1bad377f0da4402904e0af02fe62c7bdb1d2';
  canada_evidence text :=
    'd9c012acf1e003942eebdefda80058358f85ca1c718e59e5edd4dcd25b9c3ce9';
begin
  if mexico_evidence <> encode(
    extensions.digest(
      convert_to(
        E'Abrimos 50 SOBRES de la nueva expansión de Pokémon JCC: Megaevolución\n50 sobres · ETB · booster box · Combina y combate',
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  ) then
    raise exception using errcode = '55000',
      message = 'Mexico 50-pack evidence hash does not match the immutable excerpt';
  end if;

  if canada_evidence <> encode(
    extensions.digest(
      convert_to(
        E'Opening The Ascended Heroes ETB! (Pokémon card opening)\nopening all the packs · Ascended Heroes Elite Trainer Box · standard ETB = 9 packs',
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  ) then
    raise exception using errcode = '55000',
      message = 'Canada 9-pack evidence hash does not match the immutable excerpt';
  end if;

  select policies.id
  into mexico_policy_id
  from ingest.source_policies as policies
  where policies.source_key = 'public_study_indigo_geek_mx_50'
    and policies.display_name = 'Indigo Geek Megaevolución 50-pack coverage'
    and policies.domain = 'www.youtube.com'
    and policies.base_url = 'https://www.youtube.com/watch?v=KNCSNJNcjJ8'
    and policies.version = 'public-study-indigo-geek-megaevolucion-youtube-v1'
    and policies.config ->> 'study_key' = 'indigo-geek-megaevolucion-mx-50-v1'
    and policies.config ->> 'publisher_channel_id' = 'UCGri3BoVzarWIYCzg8MEQjw'
    and policies.config ->> 'set_external_id' = 'me01'
    and policies.config ->> 'set_language' = 'es-MX'
    and policies.config ->> 'pack_count' = '50'
    and not (policies.config ? 'qualifying_hit_pack_count')
    and not (policies.config ? 'qualifying_metric')
    and not (policies.config ? 'metric_version')
    and policies.enabled
    and policies.statistics_eligible_default
    and not policies.is_demo;

  select policies.id
  into canada_policy_id
  from ingest.source_policies as policies
  where policies.source_key = 'public_study_pokehanna_ca_9'
    and policies.display_name = 'PokeHanna Ascended Heroes 9-pack coverage'
    and policies.domain = 'www.youtube.com'
    and policies.base_url = 'https://www.youtube.com/watch?v=Jj0IxqUYat8'
    and policies.version = 'public-study-pokehanna-ascended-heroes-youtube-v1'
    and policies.config ->> 'study_key' = 'pokehanna-ascended-heroes-ca-9-v1'
    and policies.config ->> 'publisher_channel_id' = 'UC6stWaGoj-9rsEOzYv56ftQ'
    and policies.config ->> 'set_external_id' = 'me02.5'
    and policies.config ->> 'set_language' = 'en'
    and policies.config ->> 'product_scope' = 'etb'
    and policies.config ->> 'pack_count' = '9'
    and not (policies.config ? 'qualifying_hit_pack_count')
    and not (policies.config ? 'qualifying_metric')
    and not (policies.config ? 'metric_version')
    and policies.enabled
    and policies.statistics_eligible_default
    and not policies.is_demo;

  if mexico_policy_id is null or canada_policy_id is null then
    raise exception using errcode = '55000',
      message = 'Canada/Mexico reviewed source policy is unavailable or drifted';
  end if;

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
  ) values
  (
    'indigo-geek-megaevolucion-mx-50-v1',
    mexico_policy_id,
    'MX',
    'Mexico',
    '2025-09-12T13:00:41Z'::timestamptz,
    50,
    'me01',
    'all',
    'public-study-indigo-geek-megaevolucion-youtube-v1',
    'indigo-geek-megaevolucion-evidence-v1',
    'public-study-indigo-geek-megaevolucion-youtube-v1',
    mexico_evidence,
    verification_time,
    verification_time,
    false
  ),
  (
    'pokehanna-ascended-heroes-ca-9-v1',
    canada_policy_id,
    'CA',
    'Canada',
    '2026-04-05T18:00:15Z'::timestamptz,
    9,
    'me02.5',
    'etb',
    'public-study-pokehanna-ascended-heroes-youtube-v1',
    'pokehanna-ascended-heroes-evidence-v1',
    'public-study-pokehanna-ascended-heroes-youtube-v1',
    canada_evidence,
    verification_time,
    verification_time,
    false
  );
end;
$migration$;

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
        'pokesup-abyss-eye-jp-30-v1',
        'limitsend-inferno-x-kr-30-v1',
        'buyfunlife-ninja-spinner-tw-40-v1',
        'allonline-mega-dream-ex-th-10-v1',
        'richards-bricks-charizard-upc-pr-18-v1',
        'richards-bricks-mega-evolution-box-pr-36-v1',
        'indigo-geek-megaevolucion-mx-50-v1',
        'pokehanna-ascended-heroes-ca-9-v1'
      )
    )
  );

commit;
