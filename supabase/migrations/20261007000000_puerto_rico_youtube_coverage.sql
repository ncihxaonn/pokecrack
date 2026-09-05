begin;

-- Two exact public YouTube watch pages from one reviewed Puerto Rico
-- publisher provide complete pack denominators. Neither page provides a
-- normalized SIR-pack numerator, so both remain coverage-only.
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
  'public_study_richards_bricks_pr_18',
  'Richard''s Bricks Mega Charizard X ex 18-pack study',
  'public_web',
  'www.youtube.com',
  'https://www.youtube.com/watch?v=OON-ICjlrd4',
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
    "study_key":"richards-bricks-charizard-upc-pr-18-v1",
    "canonical_url":"https://www.youtube.com/watch?v=OON-ICjlrd4",
    "fetch_url":"https://www.youtube.com/watch?v=OON-ICjlrd4",
    "collector_version":"public-study-richards-bricks-youtube-v1",
    "parser_version":"richards-bricks-charizard-upc-evidence-v1",
    "country_code":"PR",
    "country_name":"Puerto Rico",
    "geography_basis":"publisher_country",
    "geography_confidence":"tier_b",
    "publisher_country_url":"https://www.youtube.com/@Richards_Bricks/about",
    "publisher_channel_id":"UCP2PM8ZRJ_fiKlzJNGc02pQ",
    "publisher_country_evidence":"country:\"Puerto Rico\"",
    "publisher_country_checked_at":"2026-09-05",
    "geography_review_method":"manual_static_channel_about_review",
    "set_external_id":"mixed-tpci-2025",
    "set_scope":"mixed_multi_expansion",
    "set_name":"Mixed English TPCI expansions",
    "product_name":"Mega Charizard X ex Ultra-Premium Collection",
    "product_scope":"all",
    "pack_count":18,
    "observed_at":"2025-12-24T11:03:10Z",
    "denominator_complete":true,
    "robots_url":"https://www.youtube.com/robots.txt",
    "robots_checked_at":"2026-09-05",
    "robots_decision":"watch_route_not_disallowed",
    "terms_url":"https://www.youtube.com/static?template=terms",
    "terms_checked_at":"2026-09-05",
    "terms_effective_date":"2023-12-15",
    "terms_status":"public_browse_static_metadata_only",
    "rights_scope":"minimal_noncreative_facts_no_media_transcript_or_body_reuse"
  }'::jsonb,
  'public-study-richards-bricks-youtube-v1',
  86400,
  false
),
(
  'public_study_richards_bricks_pr_36',
  'Richard''s Bricks Mega Evolution 36-pack study',
  'public_web',
  'm.youtube.com',
  'https://m.youtube.com/watch?v=p_8k9ZkHV_0',
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
    "study_key":"richards-bricks-mega-evolution-box-pr-36-v1",
    "canonical_url":"https://m.youtube.com/watch?v=p_8k9ZkHV_0",
    "fetch_url":"https://m.youtube.com/watch?v=p_8k9ZkHV_0",
    "collector_version":"public-study-richards-bricks-youtube-v1",
    "parser_version":"richards-bricks-mega-evolution-box-evidence-v1",
    "country_code":"PR",
    "country_name":"Puerto Rico",
    "geography_basis":"publisher_country",
    "geography_confidence":"tier_b",
    "publisher_country_url":"https://www.youtube.com/@Richards_Bricks/about",
    "publisher_channel_id":"UCP2PM8ZRJ_fiKlzJNGc02pQ",
    "publisher_country_evidence":"country:\"Puerto Rico\"",
    "publisher_country_checked_at":"2026-09-05",
    "geography_review_method":"manual_static_channel_about_review",
    "set_external_id":"me01",
    "set_scope":"single_expansion",
    "set_name":"Mega Evolution",
    "product_name":"Mega Evolution Booster Box",
    "product_scope":"booster_box",
    "pack_count":36,
    "observed_at":"2025-10-20T15:30:33Z",
    "denominator_complete":true,
    "robots_url":"https://m.youtube.com/robots.txt",
    "robots_checked_at":"2026-09-05",
    "robots_decision":"watch_route_not_disallowed",
    "terms_url":"https://www.youtube.com/static?template=terms",
    "terms_checked_at":"2026-09-05",
    "terms_effective_date":"2023-12-15",
    "terms_status":"public_browse_static_metadata_only",
    "rights_scope":"minimal_noncreative_facts_no_media_transcript_or_body_reuse"
  }'::jsonb,
  'public-study-richards-bricks-youtube-v1',
  86400,
  false
);

insert into ingest.source_request_gates (source_key)
values
  ('public_study_richards_bricks_pr_18'),
  ('public_study_richards_bricks_pr_36');

create or replace function ingest.reviewed_public_study_gates_ready_v1()
returns boolean
language sql
stable
security definer
parallel safe
set search_path = pg_catalog
as $$
  select count(*) = 12
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
    'public_study_richards_bricks_pr_36'
  );
$$;

alter function ingest.reviewed_public_study_gates_ready_v1() owner to postgres;
revoke all on function ingest.reviewed_public_study_gates_ready_v1()
  from public, anon, authenticated, service_role;
grant execute on function ingest.reviewed_public_study_gates_ready_v1()
  to service_role;
comment on function ingest.reviewed_public_study_gates_ready_v1() is
  'Boolean-only readiness check for all exact reviewed public-study request gates; it exposes no gate identity or lease state.';

-- Append ordinals 11 and 12 only when the exact Brazil ordinal-10 suffix is
-- still present. Both contracts pin the same public publisher channel ID and
-- explicitly omit every normalized numerator and inference field.
do $migration$
declare
  definition text;
  updated_definition text;
  old_suffix text := $old$
      array['Heróis Excelsos: Vale a Pena ABRIR Uma CASE LACRADA?']::text[]
    );$old$;
  new_suffix text := $new$
      array['Heróis Excelsos: Vale a Pena ABRIR Uma CASE LACRADA?']::text[]
    ),
    (
      11,
      'richards-bricks-charizard-upc-pr-18-v1'::text,
      'public_study_richards_bricks_pr_18'::text,
      'richards_bricks_charizard_upc_study'::text,
      'Richards Bricks Mega Charizard X ex UPC study'::text,
      'Reviewed Puerto Rico publisher-country coverage: 18 packs from a mixed-expansion Mega Charizard X ex Ultra-Premium Collection. The public channel About metadata identifies Puerto Rico, but no physical opening location is claimed. No normalized SIR-pack numerator exists, so no rate or inference is published.'::text,
      'Richard''s Bricks Mega Charizard X ex 18-pack study'::text,
      'www.youtube.com'::text,
      'https://www.youtube.com/watch?v=OON-ICjlrd4'::text,
      'public-study-richards-bricks-youtube-v1'::text,
      '{
        "study_key":"richards-bricks-charizard-upc-pr-18-v1",
        "canonical_url":"https://www.youtube.com/watch?v=OON-ICjlrd4",
        "fetch_url":"https://www.youtube.com/watch?v=OON-ICjlrd4",
        "collector_version":"public-study-richards-bricks-youtube-v1",
        "parser_version":"richards-bricks-charizard-upc-evidence-v1",
        "country_code":"PR",
        "country_name":"Puerto Rico",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "publisher_country_url":"https://www.youtube.com/@Richards_Bricks/about",
        "publisher_channel_id":"UCP2PM8ZRJ_fiKlzJNGc02pQ",
        "publisher_country_evidence":"country:\"Puerto Rico\"",
        "publisher_country_checked_at":"2026-09-05",
        "geography_review_method":"manual_static_channel_about_review",
        "set_external_id":"mixed-tpci-2025",
        "set_scope":"mixed_multi_expansion",
        "set_name":"Mixed English TPCI expansions",
        "product_name":"Mega Charizard X ex Ultra-Premium Collection",
        "product_scope":"all",
        "pack_count":18,
        "observed_at":"2025-12-24T11:03:10Z",
        "denominator_complete":true,
        "robots_url":"https://www.youtube.com/robots.txt",
        "robots_checked_at":"2026-09-05",
        "robots_decision":"watch_route_not_disallowed",
        "terms_url":"https://www.youtube.com/static?template=terms",
        "terms_checked_at":"2026-09-05",
        "terms_effective_date":"2023-12-15",
        "terms_status":"public_browse_static_metadata_only",
        "rights_scope":"minimal_noncreative_facts_no_media_transcript_or_body_reuse"
      }'::jsonb,
      E'Abriendo el Mega Charizard X ex Ultra-Premium Collection\nBooster Pack (18)'::text,
      array['Abriendo el Mega Charizard X ex Ultra-Premium Collection']::text[]
    ),
    (
      12,
      'richards-bricks-mega-evolution-box-pr-36-v1'::text,
      'public_study_richards_bricks_pr_36'::text,
      'richards_bricks_mega_evolution_box_study'::text,
      'Richards Bricks Mega Evolution Booster Box study'::text,
      'Reviewed Puerto Rico publisher-country coverage: one complete 36-pack Mega Evolution booster box. The public channel About metadata identifies Puerto Rico, but no physical opening location is claimed. No normalized SIR-pack numerator exists, so no rate or inference is published.'::text,
      'Richard''s Bricks Mega Evolution 36-pack study'::text,
      'm.youtube.com'::text,
      'https://m.youtube.com/watch?v=p_8k9ZkHV_0'::text,
      'public-study-richards-bricks-youtube-v1'::text,
      '{
        "study_key":"richards-bricks-mega-evolution-box-pr-36-v1",
        "canonical_url":"https://m.youtube.com/watch?v=p_8k9ZkHV_0",
        "fetch_url":"https://m.youtube.com/watch?v=p_8k9ZkHV_0",
        "collector_version":"public-study-richards-bricks-youtube-v1",
        "parser_version":"richards-bricks-mega-evolution-box-evidence-v1",
        "country_code":"PR",
        "country_name":"Puerto Rico",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "publisher_country_url":"https://www.youtube.com/@Richards_Bricks/about",
        "publisher_channel_id":"UCP2PM8ZRJ_fiKlzJNGc02pQ",
        "publisher_country_evidence":"country:\"Puerto Rico\"",
        "publisher_country_checked_at":"2026-09-05",
        "geography_review_method":"manual_static_channel_about_review",
        "set_external_id":"me01",
        "set_scope":"single_expansion",
        "set_name":"Mega Evolution",
        "product_name":"Mega Evolution Booster Box",
        "product_scope":"booster_box",
        "pack_count":36,
        "observed_at":"2025-10-20T15:30:33Z",
        "denominator_complete":true,
        "robots_url":"https://m.youtube.com/robots.txt",
        "robots_checked_at":"2026-09-05",
        "robots_decision":"watch_route_not_disallowed",
        "terms_url":"https://www.youtube.com/static?template=terms",
        "terms_checked_at":"2026-09-05",
        "terms_effective_date":"2023-12-15",
        "terms_status":"public_browse_static_metadata_only",
        "rights_scope":"minimal_noncreative_facts_no_media_transcript_or_body_reuse"
      }'::jsonb,
      E'Mega Evolution Booster Box unboxing\n36 booster packs from the Pokémon TCG: Mega Evolution expansion'::text,
      array['Mega Evolution Booster Box unboxing']::text[]
    );$new$;
begin
  select pg_get_functiondef(
    'ingest.reviewed_public_study_contracts()'::regprocedure
  )
  into definition;

  if definition is null
    or position(old_suffix in definition) = 0
    or position('richards-bricks-charizard-upc-pr-18-v1' in definition) > 0
    or position('richards-bricks-mega-evolution-box-pr-36-v1' in definition) > 0
    or (
      select array_agg(contracts.ordinal order by contracts.ordinal)
      from ingest.reviewed_public_study_contracts() as contracts
    ) is distinct from array[1, 2, 3, 4, 5, 6, 7, 8, 9, 10]::integer[]
  then
    raise exception using
      errcode = '55000',
      message = 'reviewed public-study registry is not the expected ordinal-10 definition';
  end if;

  updated_definition := replace(definition, old_suffix, new_suffix);
  if updated_definition = definition then
    raise exception using
      errcode = '55000',
      message = 'Puerto Rico reviewed coverage registry extension was not applied';
  end if;
  execute updated_definition;
end;
$migration$;

alter function ingest.reviewed_public_study_contracts() owner to postgres;
revoke all on function ingest.reviewed_public_study_contracts()
  from public, anon, authenticated, service_role;
comment on function ingest.reviewed_public_study_contracts() is
  'Owner-only immutable reviewed-study facts. Includes private historical facts and exact bounded coverage evidence; never grant this function to API or worker roles.';

-- Move all four denominator-only queue/persistence boundaries together.
-- Ordinal 10 remains on the separate statistical path; only the two new
-- coverage contracts are added here.
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
      'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9)'
      in source_definition
    ) = 0
      or position(
        'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12)'
        in source_definition
      ) > 0
    then
      raise exception using
        errcode = '55000',
        message = 'reviewed coverage function is missing the expected ordinal-9 predicate',
        detail = function_oid::text;
    end if;
    updated_definition := replace(
      source_definition,
      'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9)',
      'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12)'
    );
    if updated_definition = source_definition then
      raise exception using
        errcode = '55000',
        message = 'reviewed coverage ordinal-11/12 extension was not applied',
        detail = function_oid::text;
    end if;
    execute updated_definition;
  end loop;
end;
$migration$;

-- Both Puerto Rico products have immutable source-native set identities in the
-- reviewed evidence. Permit only these two exact contracts to refresh without
-- depending on a prior TCGdex catalog sync: the 18-pack product is explicitly
-- mixed across English TPCI expansions, while the 36-pack product explicitly
-- names Mega Evolution/me01. Every other English contract still requires its
-- exact live catalog row; the non-English official-set path is unchanged.
do $migration$
declare
  definition text;
  updated_definition text;
  old_prefix text := $old$
  if not (
    (
      coalesce(nullif(reviewed.config ->> 'set_language', ''), 'en') = 'en'
  $old$;
  new_prefix text := $new$
  if not (
    (
      reviewed.study_key = 'richards-bricks-charizard-upc-pr-18-v1'
      and reviewed.config ->> 'set_external_id' = 'mixed-tpci-2025'
      and reviewed.config ->> 'set_scope' = 'mixed_multi_expansion'
      and reviewed.config ->> 'product_scope' = 'all'
      and not (reviewed.config ? 'set_language')
    )
    or (
      reviewed.study_key = 'richards-bricks-mega-evolution-box-pr-36-v1'
      and reviewed.config ->> 'set_external_id' = 'me01'
      and reviewed.config ->> 'set_scope' = 'single_expansion'
      and reviewed.config ->> 'set_name' = 'Mega Evolution'
      and reviewed.config ->> 'product_scope' = 'booster_box'
      and not (reviewed.config ? 'set_language')
    )
    or (
      coalesce(nullif(reviewed.config ->> 'set_language', ''), 'en') = 'en'
  $new$;
begin
  select pg_get_functiondef(
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure
  )
  into definition;

  if definition is null
    or position(old_prefix in definition) = 0
    or position('mixed-tpci-2025' in definition) > 0
  then
    raise exception using
      errcode = '55000',
      message = 'coverage finalizer is not the expected catalog-gated definition';
  end if;

  updated_definition := replace(definition, old_prefix, new_prefix);
  if updated_definition = definition then
    raise exception using
      errcode = '55000',
      message = 'Puerto Rico reviewed set identities were not added to the coverage finalizer';
  end if;
  execute updated_definition;
end;
$migration$;

comment on function ingest.finalize_public_study_coverage_job_v1(
  uuid, text, bigint, text, jsonb
) is
  'Generation-fenced verifier for nine reviewed denominator-only contracts. English contracts require the exact live TCGdex catalog, except the two exact source-native Puerto Rico product identities; explicit non-English contracts require a bounded source-native set name and official set URL. It cannot publish a numerator or inference.';

-- Public source counts represent independent publishers, not transport host
-- aliases. A reviewed publisher identity wins when present; older contracts
-- continue to fall back to their exact domain.
do $migration$
declare
  definition text;
  updated_definition text;
  old_columns text := $old$
    reviewed.domain,
    reviewed.canonical_url,
  $old$;
  new_columns text := $new$
    reviewed.domain,
    coalesce(
      nullif(reviewed.config ->> 'publisher_channel_id', ''),
      reviewed.domain
    ) as publisher_identity,
    reviewed.canonical_url,
  $new$;
  old_count text := 'count(distinct rows.domain)::integer';
  new_count text := 'count(distinct rows.publisher_identity)::integer';
begin
  select pg_get_functiondef(
    'public.get_public_study_coverage_v2()'::regprocedure
  )
  into definition;

  if definition is null
    or position(old_columns in definition) = 0
    or (
      char_length(definition) - char_length(replace(definition, old_count, ''))
    ) / char_length(old_count) <> 2
    or position('publisher_identity' in definition) > 0
  then
    raise exception using
      errcode = '55000',
      message = 'public coverage projection is not the expected domain-count definition';
  end if;

  updated_definition := replace(definition, old_columns, new_columns);
  updated_definition := replace(updated_definition, old_count, new_count);
  if updated_definition = definition then
    raise exception using
      errcode = '55000',
      message = 'publisher identity source-count projection was not applied';
  end if;
  execute updated_definition;
end;
$migration$;

comment on function public.get_public_study_coverage_v2() is
  'Reviewed global denominator coverage with exact source-native data versions. Independent source counts use an explicit reviewed publisher identity when present and otherwise the exact source domain; publishes no numerator, pull rate, baseline, posterior, interval, delta, or signal.';

-- Seed the two facts that were manually verified from the exact static watch
-- metadata and publisher About page. This makes the real coverage visible
-- immediately without pretending a scheduled collector already ran.
do $migration$
declare
  policy_18_id uuid;
  policy_36_id uuid;
  verification_time timestamptz := statement_timestamp();
  evidence_18 text :=
    'ee0ec8cb243d26d0fc8d46b4788bb8eff2205353466c0d8e0c3c2d7cd48293f1';
  evidence_36 text :=
    '97371af1d78a7d91e48e55a02f0376d4cd399297ea50fc150b3d966963e2d18c';
begin
  if evidence_18 <> encode(
    extensions.digest(
      convert_to(
        E'Abriendo el Mega Charizard X ex Ultra-Premium Collection\nBooster Pack (18)',
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  ) then
    raise exception using errcode = '55000',
      message = 'Puerto Rico 18-pack evidence hash does not match the immutable excerpt';
  end if;

  if evidence_36 <> encode(
    extensions.digest(
      convert_to(
        E'Mega Evolution Booster Box unboxing\n36 booster packs from the Pokémon TCG: Mega Evolution expansion',
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  ) then
    raise exception using errcode = '55000',
      message = 'Puerto Rico 36-pack evidence hash does not match the immutable excerpt';
  end if;

  select policies.id
  into policy_18_id
  from ingest.source_policies as policies
  where policies.source_key = 'public_study_richards_bricks_pr_18'
    and policies.display_name = 'Richard''s Bricks Mega Charizard X ex 18-pack study'
    and policies.domain = 'www.youtube.com'
    and policies.base_url = 'https://www.youtube.com/watch?v=OON-ICjlrd4'
    and policies.version = 'public-study-richards-bricks-youtube-v1'
    and policies.config ->> 'study_key' = 'richards-bricks-charizard-upc-pr-18-v1'
    and policies.config ->> 'publisher_channel_id' = 'UCP2PM8ZRJ_fiKlzJNGc02pQ'
    and policies.config ->> 'set_external_id' = 'mixed-tpci-2025'
    and policies.config ->> 'set_scope' = 'mixed_multi_expansion'
    and policies.config ->> 'pack_count' = '18'
    and not (policies.config ? 'qualifying_hit_pack_count')
    and not (policies.config ? 'qualifying_metric')
    and not (policies.config ? 'metric_version')
    and policies.enabled
    and policies.statistics_eligible_default
    and not policies.is_demo;

  select policies.id
  into policy_36_id
  from ingest.source_policies as policies
  where policies.source_key = 'public_study_richards_bricks_pr_36'
    and policies.display_name = 'Richard''s Bricks Mega Evolution 36-pack study'
    and policies.domain = 'm.youtube.com'
    and policies.base_url = 'https://m.youtube.com/watch?v=p_8k9ZkHV_0'
    and policies.version = 'public-study-richards-bricks-youtube-v1'
    and policies.config ->> 'study_key' =
      'richards-bricks-mega-evolution-box-pr-36-v1'
    and policies.config ->> 'publisher_channel_id' = 'UCP2PM8ZRJ_fiKlzJNGc02pQ'
    and policies.config ->> 'set_external_id' = 'me01'
    and policies.config ->> 'set_scope' = 'single_expansion'
    and policies.config ->> 'pack_count' = '36'
    and not (policies.config ? 'qualifying_hit_pack_count')
    and not (policies.config ? 'qualifying_metric')
    and not (policies.config ? 'metric_version')
    and policies.enabled
    and policies.statistics_eligible_default
    and not policies.is_demo;

  if policy_18_id is null or policy_36_id is null then
    raise exception using errcode = '55000',
      message = 'Puerto Rico reviewed source policy is unavailable or drifted';
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
    'richards-bricks-charizard-upc-pr-18-v1',
    policy_18_id,
    'PR',
    'Puerto Rico',
    '2025-12-24T11:03:10Z'::timestamptz,
    18,
    'mixed-tpci-2025',
    'all',
    'public-study-richards-bricks-youtube-v1',
    'richards-bricks-charizard-upc-evidence-v1',
    'public-study-richards-bricks-youtube-v1',
    evidence_18,
    verification_time,
    verification_time,
    false
  ),
  (
    'richards-bricks-mega-evolution-box-pr-36-v1',
    policy_36_id,
    'PR',
    'Puerto Rico',
    '2025-10-20T15:30:33Z'::timestamptz,
    36,
    'me01',
    'booster_box',
    'public-study-richards-bricks-youtube-v1',
    'richards-bricks-mega-evolution-box-evidence-v1',
    'public-study-richards-bricks-youtube-v1',
    evidence_36,
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
        'richards-bricks-mega-evolution-box-pr-36-v1'
      )
    )
  );

commit;
