begin;

-- Build & Battle boxes and three-pack blisters are denominator-only product
-- scopes. Extend only the coverage ledger vocabulary; the statistical opening
-- ledger remains unchanged.
alter table ingest.public_study_coverage_observations
  drop constraint public_study_coverage_product_check;
alter table ingest.public_study_coverage_observations
  add constraint public_study_coverage_product_check check (
    product_scope in (
      'all',
      'booster_box',
      'etb',
      'booster_bundle',
      'value_bundle',
      'four_pack_blister',
      'build_and_battle',
      'three_pack_blister'
    )
  );

-- Five exact public YouTube watch pages provide reviewed publisher-country
-- coverage in Panama, Guatemala, Argentina, and Chile. Each source names the
-- product being opened; the retained denominator is either stated by the source
-- or derived from the corresponding official product specification. The
-- sources do not state the card language and do not provide a normalized
-- SIR-pack numerator, so language is `und` and all rows are coverage-only.
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
  'public_study_tcg_market_panama_chaos_rising_6',
  'TCG Market Panamá Chaos Rising 6-pack coverage',
  'public_web',
  'www.youtube.com',
  'https://www.youtube.com/watch?v=fHQpNECg4y4',
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
    "study_key":"tcg-market-chaos-rising-pa-6-v1",
    "canonical_url":"https://www.youtube.com/watch?v=fHQpNECg4y4",
    "fetch_url":"https://www.youtube.com/watch?v=fHQpNECg4y4",
    "collector_version":"public-study-tcg-market-panama-chaos-rising-youtube-v1",
    "parser_version":"tcg-market-panama-chaos-rising-evidence-v1",
    "country_code":"PA",
    "country_name":"Panama",
    "geography_basis":"publisher_country",
    "geography_confidence":"tier_b",
    "publisher_country_url":"https://www.youtube.com/channel/UCa68xVUUIKE8dvcfxCcdyrQ/about",
    "publisher_channel_id":"UCa68xVUUIKE8dvcfxCcdyrQ",
    "publisher_country_evidence":"channel name: TCG Market Panamá; video description: Contenido exclusivo desde Panamá",
    "publisher_country_checked_at":"2026-09-05",
    "geography_review_method":"manual_static_watch_and_channel_name_review",
    "set_external_id":"me04",
    "set_language":"und",
    "set_language_basis":"source_does_not_state_card_language",
    "set_name":"Chaos Rising",
    "set_official_url":"https://www.pokemon.com/us/pokemon-tcg/product-gallery/mega-evolution-chaos-rising-booster-bundle",
    "product_name":"Chaos Rising Booster Bundle",
    "product_scope":"booster_bundle",
    "pack_count":6,
    "denominator_basis":"source_product_opening_plus_official_product_spec",
    "denominator_derivation":"source_opening_plus_official_6_pack_bundle_spec",
    "source_published_at":"2026-08-02T17:15:39-07:00",
    "observed_at":"2026-08-03T00:15:39Z",
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
  'public-study-tcg-market-panama-chaos-rising-youtube-v1',
  86400,
  false
),
(
  'public_study_tcg_market_panama_pitch_black_4',
  'TCG Market Panamá Pitch Black 4-pack coverage',
  'public_web',
  'www.youtube.com',
  'https://www.youtube.com/watch?v=6kb1MvcnMJE',
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
    "study_key":"tcg-market-pitch-black-pa-4-v1",
    "canonical_url":"https://www.youtube.com/watch?v=6kb1MvcnMJE",
    "fetch_url":"https://www.youtube.com/watch?v=6kb1MvcnMJE",
    "collector_version":"public-study-tcg-market-panama-pitch-black-youtube-v1",
    "parser_version":"tcg-market-panama-pitch-black-evidence-v1",
    "country_code":"PA",
    "country_name":"Panama",
    "geography_basis":"publisher_country",
    "geography_confidence":"tier_b",
    "publisher_country_url":"https://www.youtube.com/channel/UCa68xVUUIKE8dvcfxCcdyrQ/about",
    "publisher_channel_id":"UCa68xVUUIKE8dvcfxCcdyrQ",
    "publisher_country_evidence":"channel name: TCG Market Panamá; video description: Contenido exclusivo desde Panamá",
    "publisher_country_checked_at":"2026-09-05",
    "geography_review_method":"manual_static_watch_and_channel_name_review",
    "set_external_id":"me05",
    "set_language":"und",
    "set_language_basis":"source_does_not_state_card_language",
    "set_name":"Pitch Black",
    "set_official_url":"https://www.pokemon.com/us/news/pokemon-tcg-mega-evolution-pitch-black-product-showcase",
    "product_name":"Pitch Black Build & Battle Box",
    "product_scope":"build_and_battle",
    "pack_count":4,
    "denominator_basis":"source_product_opening_plus_official_product_spec",
    "denominator_derivation":"source_opening_plus_official_4_pack_build_and_battle_spec",
    "source_published_at":"2026-08-05T12:09:10-07:00",
    "observed_at":"2026-08-05T19:09:10Z",
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
  'public-study-tcg-market-panama-pitch-black-youtube-v1',
  86400,
  false
),
(
  'public_study_pokeshow_guatemala_megaevolution_3',
  'PokéShow Guatemala Mega Evolution 3-pack coverage',
  'public_web',
  'www.youtube.com',
  'https://www.youtube.com/watch?v=DWRdhUuIUvI',
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
    "study_key":"pokeshow-mega-evolution-gt-3-v1",
    "canonical_url":"https://www.youtube.com/watch?v=DWRdhUuIUvI",
    "fetch_url":"https://www.youtube.com/watch?v=DWRdhUuIUvI",
    "collector_version":"public-study-pokeshow-guatemala-megaevolution-youtube-v1",
    "parser_version":"pokeshow-guatemala-megaevolution-evidence-v1",
    "country_code":"GT",
    "country_name":"Guatemala",
    "geography_basis":"publisher_country",
    "geography_confidence":"tier_b",
    "publisher_country_url":"https://www.youtube.com/@pokeshowdemaddi/about",
    "publisher_channel_id":"UChG8m-xoKqrXJDCEoE2i9Jg",
    "publisher_country_evidence":"country:\"Guatemala\"; video description: desde Guatemala",
    "publisher_country_checked_at":"2026-09-05",
    "geography_review_method":"manual_static_channel_about_review",
    "set_external_id":"me01",
    "set_language":"und",
    "set_language_basis":"source_does_not_state_card_language",
    "set_name":"Mega Evolution",
    "set_official_url":"https://www.pokemoncenter.com/search/megacards",
    "product_name":"Mega Evolution Tripack (promo variant unspecified)",
    "product_scope":"three_pack_blister",
    "pack_count":3,
    "denominator_basis":"source_product_opening_plus_official_product_spec",
    "denominator_derivation":"source_opening_plus_official_3_pack_tripack_spec",
    "product_variant_claim":"not_claimed",
    "source_published_at":"2025-10-06T10:21:33-07:00",
    "observed_at":"2025-10-06T17:21:33Z",
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
  'public-study-pokeshow-guatemala-megaevolution-youtube-v1',
  86400,
  false
),
(
  'public_study_cartas_pokemon_argentina_pitch_black_36',
  'Cartas Pokemon Argentina Pitch Black 36-pack coverage',
  'public_web',
  'www.youtube.com',
  'https://www.youtube.com/watch?v=HcsWjycR1L0',
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
    "study_key":"cartas-pokemon-argentina-pitch-black-ar-36-v1",
    "canonical_url":"https://www.youtube.com/watch?v=HcsWjycR1L0",
    "fetch_url":"https://www.youtube.com/watch?v=HcsWjycR1L0",
    "collector_version":"public-study-cartas-pokemon-argentina-pitch-black-youtube-v1",
    "parser_version":"cartas-pokemon-argentina-pitch-black-evidence-v1",
    "country_code":"AR",
    "country_name":"Argentina",
    "geography_basis":"publisher_country",
    "geography_confidence":"tier_b",
    "publisher_country_url":"https://www.youtube.com/@pokemonargentinatcg/about",
    "publisher_channel_id":"UCGBtAPv7mLLRgdqeupj2kLg",
    "publisher_country_evidence":"country:\"Argentina\"",
    "publisher_country_checked_at":"2026-09-05",
    "geography_review_method":"manual_static_channel_about_review",
    "set_external_id":"me05",
    "set_language":"und",
    "set_language_basis":"source_does_not_state_card_language",
    "set_name":"Pitch Black",
    "set_official_url":"https://www.pokemon.com/us/news/pokemon-tcg-mega-evolution-pitch-black-product-showcase",
    "product_name":"Pitch Black Booster Display Box",
    "product_scope":"booster_box",
    "pack_count":36,
    "denominator_basis":"source_named_complete_box_plus_official_36_pack_spec",
    "denominator_derivation":"one_complete_booster_display_x_36",
    "source_published_at":"2026-07-17T11:18:50-07:00",
    "observed_at":"2026-07-17T18:18:50Z",
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
  'public-study-cartas-pokemon-argentina-pitch-black-youtube-v1',
  86400,
  false
),
(
  'public_study_pokemaniaco_lucas_cl_36',
  'Pokemaniaco Lucas Phantasmal Flames 36-pack coverage',
  'public_web',
  'www.youtube.com',
  'https://www.youtube.com/watch?v=Meg4AO9CqHE',
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
    "study_key":"pokemaniaco-lucas-phantasmal-flames-cl-36-v1",
    "canonical_url":"https://www.youtube.com/watch?v=Meg4AO9CqHE",
    "fetch_url":"https://www.youtube.com/watch?v=Meg4AO9CqHE",
    "collector_version":"public-study-pokemaniaco-lucas-phantasmal-flames-youtube-v1",
    "parser_version":"pokemaniaco-lucas-phantasmal-flames-evidence-v1",
    "country_code":"CL",
    "country_name":"Chile",
    "geography_basis":"publisher_country",
    "geography_confidence":"tier_b",
    "publisher_country_url":"https://www.youtube.com/@PokemaniacoLucas/about",
    "publisher_channel_id":"UCDKXzvS5YaUJwsHD1wNkWBw",
    "publisher_country_evidence":"country:\"Chile\"",
    "publisher_country_checked_at":"2026-09-05",
    "geography_review_method":"manual_static_channel_about_review",
    "set_external_id":"me02",
    "set_language":"und",
    "set_language_basis":"source_does_not_state_card_language",
    "set_name":"Phantasmal Flames",
    "set_official_url":"https://www.pokemon.com/us/news/pokemon-tcg-mega-evolution-phantasmal-flames-product-showcase",
    "product_name":"Phantasmal Flames Booster Display Box",
    "product_scope":"booster_box",
    "pack_count":36,
    "denominator_basis":"source_declared_complete_36_pack_opening",
    "denominator_derivation":"source_declared_36_packs",
    "source_published_at":"2025-11-13T08:00:06-08:00",
    "observed_at":"2025-11-13T16:00:06Z",
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
  'public-study-pokemaniaco-lucas-phantasmal-flames-youtube-v1',
  86400,
  false
);

insert into ingest.source_request_gates (source_key)
values
  ('public_study_tcg_market_panama_chaos_rising_6'),
  ('public_study_tcg_market_panama_pitch_black_4'),
  ('public_study_pokeshow_guatemala_megaevolution_3'),
  ('public_study_cartas_pokemon_argentina_pitch_black_36'),
  ('public_study_pokemaniaco_lucas_cl_36');

create or replace function ingest.reviewed_public_study_gates_ready_v1()
returns boolean
language sql
stable
security definer
parallel safe
set search_path = pg_catalog
as $$
  select count(*) = 19
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
    'public_study_pokehanna_ca_9',
    'public_study_tcg_market_panama_chaos_rising_6',
    'public_study_tcg_market_panama_pitch_black_4',
    'public_study_pokeshow_guatemala_megaevolution_3',
    'public_study_cartas_pokemon_argentina_pitch_black_36',
    'public_study_pokemaniaco_lucas_cl_36'
  );
$$;

alter function ingest.reviewed_public_study_gates_ready_v1() owner to postgres;
revoke all on function ingest.reviewed_public_study_gates_ready_v1()
  from public, anon, authenticated, service_role;
grant execute on function ingest.reviewed_public_study_gates_ready_v1()
  to service_role;
comment on function ingest.reviewed_public_study_gates_ready_v1() is
  'Boolean-only readiness check for all exact reviewed public-study request gates; it exposes no gate identity or lease state.';

-- Append ordinals 15 through 19 only when the exact Canada ordinal-14 suffix
-- is still present. Every appended contract explicitly omits a normalized
-- numerator and rate.
do $migration$
declare
  definition text;
  updated_definition text;
  old_suffix text := $old$
      array['Opening The Ascended Heroes ETB! (Pokémon card opening)']::text[]
    );$old$;
  new_suffix text := $new$
      array['Opening The Ascended Heroes ETB! (Pokémon card opening)']::text[]
    ),
    (
      15,
      'tcg-market-chaos-rising-pa-6-v1'::text,
      'public_study_tcg_market_panama_chaos_rising_6'::text,
      'tcg_market_panama_chaos_rising_study'::text,
      'TCG Market Panamá Chaos Rising 6-pack study'::text,
      'Reviewed Panama publisher-country coverage: the exact source names a Chaos Rising Booster Bundle opening and identifies Panama, while the official product specification supplies the six-pack denominator. This is not a frame-by-frame completion claim. No normalized SIR-pack numerator exists, so no rate or inference is published.'::text,
      'TCG Market Panamá Chaos Rising 6-pack coverage'::text,
      'www.youtube.com'::text,
      'https://www.youtube.com/watch?v=fHQpNECg4y4'::text,
      'public-study-tcg-market-panama-chaos-rising-youtube-v1'::text,
      '{
        "study_key":"tcg-market-chaos-rising-pa-6-v1",
        "canonical_url":"https://www.youtube.com/watch?v=fHQpNECg4y4",
        "fetch_url":"https://www.youtube.com/watch?v=fHQpNECg4y4",
        "collector_version":"public-study-tcg-market-panama-chaos-rising-youtube-v1",
        "parser_version":"tcg-market-panama-chaos-rising-evidence-v1",
        "country_code":"PA",
        "country_name":"Panama",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "publisher_country_url":"https://www.youtube.com/channel/UCa68xVUUIKE8dvcfxCcdyrQ/about",
        "publisher_channel_id":"UCa68xVUUIKE8dvcfxCcdyrQ",
        "publisher_country_evidence":"channel name: TCG Market Panamá; video description: Contenido exclusivo desde Panamá",
        "publisher_country_checked_at":"2026-09-05",
        "geography_review_method":"manual_static_watch_and_channel_name_review",
        "set_external_id":"me04",
        "set_language":"und",
        "set_language_basis":"source_does_not_state_card_language",
        "set_name":"Chaos Rising",
        "set_official_url":"https://www.pokemon.com/us/pokemon-tcg/product-gallery/mega-evolution-chaos-rising-booster-bundle",
        "product_name":"Chaos Rising Booster Bundle",
        "product_scope":"booster_bundle",
        "pack_count":6,
        "denominator_basis":"source_product_opening_plus_official_product_spec",
        "denominator_derivation":"source_opening_plus_official_6_pack_bundle_spec",
        "source_published_at":"2026-08-02T17:15:39-07:00",
        "observed_at":"2026-08-03T00:15:39Z",
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
      E'¡Nuestro PRIMER OPENING de Pokémon TCG! ¿Vale la pena Chaos Rising Booster Bundle?\nOpening del Booster Bundle · sobre por sobre · desde Panamá · official bundle = 6 packs'::text,
      array['¡Nuestro PRIMER OPENING de Pokémon TCG! ¿Vale la pena Chaos Rising Booster Bundle?']::text[]
    ),
    (
      16,
      'tcg-market-pitch-black-pa-4-v1'::text,
      'public_study_tcg_market_panama_pitch_black_4'::text,
      'tcg_market_panama_pitch_black_study'::text,
      'TCG Market Panamá Pitch Black 4-pack study'::text,
      'Reviewed Panama publisher-country coverage: the exact source names a Pitch Black Build & Battle opening and identifies Panama, while the official product specification supplies the four-pack denominator. This is not a frame-by-frame completion claim. No normalized SIR-pack numerator exists, so no rate or inference is published.'::text,
      'TCG Market Panamá Pitch Black 4-pack coverage'::text,
      'www.youtube.com'::text,
      'https://www.youtube.com/watch?v=6kb1MvcnMJE'::text,
      'public-study-tcg-market-panama-pitch-black-youtube-v1'::text,
      '{
        "study_key":"tcg-market-pitch-black-pa-4-v1",
        "canonical_url":"https://www.youtube.com/watch?v=6kb1MvcnMJE",
        "fetch_url":"https://www.youtube.com/watch?v=6kb1MvcnMJE",
        "collector_version":"public-study-tcg-market-panama-pitch-black-youtube-v1",
        "parser_version":"tcg-market-panama-pitch-black-evidence-v1",
        "country_code":"PA",
        "country_name":"Panama",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "publisher_country_url":"https://www.youtube.com/channel/UCa68xVUUIKE8dvcfxCcdyrQ/about",
        "publisher_channel_id":"UCa68xVUUIKE8dvcfxCcdyrQ",
        "publisher_country_evidence":"channel name: TCG Market Panamá; video description: Contenido exclusivo desde Panamá",
        "publisher_country_checked_at":"2026-09-05",
        "geography_review_method":"manual_static_watch_and_channel_name_review",
        "set_external_id":"me05",
        "set_language":"und",
        "set_language_basis":"source_does_not_state_card_language",
        "set_name":"Pitch Black",
        "set_official_url":"https://www.pokemon.com/us/news/pokemon-tcg-mega-evolution-pitch-black-product-showcase",
        "product_name":"Pitch Black Build & Battle Box",
        "product_scope":"build_and_battle",
        "pack_count":4,
        "denominator_basis":"source_product_opening_plus_official_product_spec",
        "denominator_derivation":"source_opening_plus_official_4_pack_build_and_battle_spec",
        "source_published_at":"2026-08-05T12:09:10-07:00",
        "observed_at":"2026-08-05T19:09:10Z",
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
      E'¡Abrimos la Build & Battle de Pitch Black! ¿Nos salió una carta increíble? | Pokémon TCG\nabrimos la Build & Battle · todo el contenido · official box = 4 packs'::text,
      array['¡Abrimos la Build & Battle de Pitch Black! ¿Nos salió una carta increíble? | Pokémon TCG']::text[]
    ),
    (
      17,
      'pokeshow-mega-evolution-gt-3-v1'::text,
      'public_study_pokeshow_guatemala_megaevolution_3'::text,
      'pokeshow_guatemala_megaevolution_study'::text,
      'PokéShow Guatemala Mega Evolution 3-pack study'::text,
      'Reviewed Guatemala publisher-country coverage: the exact source names a Mega Evolution Tripack opening and identifies Guatemala, while the official product listing supplies the three-pack denominator. The promo variant is unspecified and this is not a frame-by-frame completion claim. No normalized SIR-pack numerator exists, so no rate or inference is published.'::text,
      'PokéShow Guatemala Mega Evolution 3-pack coverage'::text,
      'www.youtube.com'::text,
      'https://www.youtube.com/watch?v=DWRdhUuIUvI'::text,
      'public-study-pokeshow-guatemala-megaevolution-youtube-v1'::text,
      '{
        "study_key":"pokeshow-mega-evolution-gt-3-v1",
        "canonical_url":"https://www.youtube.com/watch?v=DWRdhUuIUvI",
        "fetch_url":"https://www.youtube.com/watch?v=DWRdhUuIUvI",
        "collector_version":"public-study-pokeshow-guatemala-megaevolution-youtube-v1",
        "parser_version":"pokeshow-guatemala-megaevolution-evidence-v1",
        "country_code":"GT",
        "country_name":"Guatemala",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "publisher_country_url":"https://www.youtube.com/@pokeshowdemaddi/about",
        "publisher_channel_id":"UChG8m-xoKqrXJDCEoE2i9Jg",
        "publisher_country_evidence":"country:\"Guatemala\"; video description: desde Guatemala",
        "publisher_country_checked_at":"2026-09-05",
        "geography_review_method":"manual_static_channel_about_review",
        "set_external_id":"me01",
        "set_language":"und",
        "set_language_basis":"source_does_not_state_card_language",
        "set_name":"Mega Evolution",
        "set_official_url":"https://www.pokemoncenter.com/search/megacards",
        "product_name":"Mega Evolution Tripack (promo variant unspecified)",
        "product_scope":"three_pack_blister",
        "pack_count":3,
        "denominator_basis":"source_product_opening_plus_official_product_spec",
        "denominator_derivation":"source_opening_plus_official_3_pack_tripack_spec",
        "product_variant_claim":"not_claimed",
        "source_published_at":"2025-10-06T10:21:33-07:00",
        "observed_at":"2025-10-06T17:21:33Z",
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
      E'🦆 El Poder del Pato 💪 | Apertura MegaEvolution + Noticias y Pokeguamazos | PokéShow de Maddi\nAbriremos un Tripack de Mega Evolution · desde Guatemala · official tripack = 3 packs'::text,
      array['🦆 El Poder del Pato 💪 | Apertura MegaEvolution + Noticias y Pokeguamazos | PokéShow de Maddi']::text[]
    ),
    (
      18,
      'cartas-pokemon-argentina-pitch-black-ar-36-v1'::text,
      'public_study_cartas_pokemon_argentina_pitch_black_36'::text,
      'cartas_pokemon_argentina_pitch_black_study'::text,
      'Cartas Pokemon Argentina Pitch Black 36-pack study'::text,
      'Reviewed Argentina publisher-country coverage: the exact source names a complete Pitch Black box opening, while the official product showcase supplies the 36-pack booster-display denominator. Physical opening location and card language are not claimed. No normalized SIR-pack numerator exists, so no rate or inference is published.'::text,
      'Cartas Pokemon Argentina Pitch Black 36-pack coverage'::text,
      'www.youtube.com'::text,
      'https://www.youtube.com/watch?v=HcsWjycR1L0'::text,
      'public-study-cartas-pokemon-argentina-pitch-black-youtube-v1'::text,
      '{
        "study_key":"cartas-pokemon-argentina-pitch-black-ar-36-v1",
        "canonical_url":"https://www.youtube.com/watch?v=HcsWjycR1L0",
        "fetch_url":"https://www.youtube.com/watch?v=HcsWjycR1L0",
        "collector_version":"public-study-cartas-pokemon-argentina-pitch-black-youtube-v1",
        "parser_version":"cartas-pokemon-argentina-pitch-black-evidence-v1",
        "country_code":"AR",
        "country_name":"Argentina",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "publisher_country_url":"https://www.youtube.com/@pokemonargentinatcg/about",
        "publisher_channel_id":"UCGBtAPv7mLLRgdqeupj2kLg",
        "publisher_country_evidence":"country:\"Argentina\"",
        "publisher_country_checked_at":"2026-09-05",
        "geography_review_method":"manual_static_channel_about_review",
        "set_external_id":"me05",
        "set_language":"und",
        "set_language_basis":"source_does_not_state_card_language",
        "set_name":"Pitch Black",
        "set_official_url":"https://www.pokemon.com/us/news/pokemon-tcg-mega-evolution-pitch-black-product-showcase",
        "product_name":"Pitch Black Booster Display Box",
        "product_scope":"booster_box",
        "pack_count":36,
        "denominator_basis":"source_named_complete_box_plus_official_36_pack_spec",
        "denominator_derivation":"one_complete_booster_display_x_36",
        "source_published_at":"2026-07-17T11:18:50-07:00",
        "observed_at":"2026-07-17T18:18:50Z",
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
      E'Abrimos una caja de Pitch Black COMPLETA 😈\nOpening de Cartas Pokemon Pitch Black · caja completa · official booster display = 36 packs'::text,
      array['Abrimos una caja de Pitch Black COMPLETA 😈']::text[]
    ),
    (
      19,
      'pokemaniaco-lucas-phantasmal-flames-cl-36-v1'::text,
      'public_study_pokemaniaco_lucas_cl_36'::text,
      'pokemaniaco_lucas_phantasmal_flames_study'::text,
      'Pokemaniaco Lucas Phantasmal Flames 36-pack study'::text,
      'Reviewed Chile publisher-country coverage: the exact source declares a complete 36-pack Phantasmal Flames booster-box opening. Physical opening location and card language are not claimed. No normalized SIR-pack numerator exists, so no rate or inference is published.'::text,
      'Pokemaniaco Lucas Phantasmal Flames 36-pack coverage'::text,
      'www.youtube.com'::text,
      'https://www.youtube.com/watch?v=Meg4AO9CqHE'::text,
      'public-study-pokemaniaco-lucas-phantasmal-flames-youtube-v1'::text,
      '{
        "study_key":"pokemaniaco-lucas-phantasmal-flames-cl-36-v1",
        "canonical_url":"https://www.youtube.com/watch?v=Meg4AO9CqHE",
        "fetch_url":"https://www.youtube.com/watch?v=Meg4AO9CqHE",
        "collector_version":"public-study-pokemaniaco-lucas-phantasmal-flames-youtube-v1",
        "parser_version":"pokemaniaco-lucas-phantasmal-flames-evidence-v1",
        "country_code":"CL",
        "country_name":"Chile",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "publisher_country_url":"https://www.youtube.com/@PokemaniacoLucas/about",
        "publisher_channel_id":"UCDKXzvS5YaUJwsHD1wNkWBw",
        "publisher_country_evidence":"country:\"Chile\"",
        "publisher_country_checked_at":"2026-09-05",
        "geography_review_method":"manual_static_channel_about_review",
        "set_external_id":"me02",
        "set_language":"und",
        "set_language_basis":"source_does_not_state_card_language",
        "set_name":"Phantasmal Flames",
        "set_official_url":"https://www.pokemon.com/us/news/pokemon-tcg-mega-evolution-phantasmal-flames-product-showcase",
        "product_name":"Phantasmal Flames Booster Display Box",
        "product_scope":"booster_box",
        "pack_count":36,
        "denominator_basis":"source_declared_complete_36_pack_opening",
        "denominator_derivation":"source_declared_36_packs",
        "source_published_at":"2025-11-13T08:00:06-08:00",
        "observed_at":"2025-11-13T16:00:06Z",
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
      E'¡Apertura Anticipada! Booster Box completa de Phantasmal Flames -  Pokémon TCG\nabro 36 sobres de la nueva edición Phantasmal Flames · Booster Box completa'::text,
      array['¡Apertura Anticipada! Booster Box completa de Phantasmal Flames -  Pokémon TCG']::text[]
    );$new$;
begin
  select pg_get_functiondef(
    'ingest.reviewed_public_study_contracts()'::regprocedure
  )
  into definition;

  if definition is null
    or position(old_suffix in definition) = 0
    or position('tcg-market-chaos-rising-pa-6-v1' in definition) > 0
    or position('tcg-market-pitch-black-pa-4-v1' in definition) > 0
    or position('pokeshow-mega-evolution-gt-3-v1' in definition) > 0
    or position('cartas-pokemon-argentina-pitch-black-ar-36-v1' in definition) > 0
    or position('pokemaniaco-lucas-phantasmal-flames-cl-36-v1' in definition) > 0
    or (
      select array_agg(contracts.ordinal order by contracts.ordinal)
      from ingest.reviewed_public_study_contracts() as contracts
    ) is distinct from array[1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14]::integer[]
  then
    raise exception using
      errcode = '55000',
      message = 'reviewed public-study registry is not the expected ordinal-14 definition';
  end if;

  updated_definition := replace(definition, old_suffix, new_suffix);
  if updated_definition = definition then
    raise exception using
      errcode = '55000',
      message = 'Central/South America reviewed coverage registry extension was not applied';
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
      'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14)'
      in source_definition
    ) = 0
      or position(
        'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19)'
        in source_definition
      ) > 0
    then
      raise exception using
        errcode = '55000',
        message = 'reviewed coverage function is missing the expected ordinal-14 predicate',
        detail = function_oid::text;
    end if;
    updated_definition := replace(
      source_definition,
      'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14)',
      'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19)'
    );
    if updated_definition = source_definition then
      raise exception using
        errcode = '55000',
        message = 'reviewed coverage ordinal-15-through-19 extension was not applied',
        detail = function_oid::text;
    end if;
    execute updated_definition;
  end loop;
end;
$migration$;

-- `und` is an explicit ISO 639 undetermined-language code. Widen the existing
-- exact language-tag guard from two to two-or-three leading letters; all other
-- official-set, name, length, control-character, and English-catalog checks
-- remain unchanged.
do $migration$
declare
  definition text;
  updated_definition text;
  old_language_guard text := $old$
      and reviewed.config ->> 'set_language' ~ '^[a-z]{2}(-[A-Za-z0-9]{2,8})*$'
  $old$;
  new_language_guard text := $new$
      and reviewed.config ->> 'set_language' ~ '^[a-z]{2,3}(-[A-Za-z0-9]{2,8})*$'
  $new$;
  old_error text :=
    'coverage observation requires an exact live English TCGdex set or an explicitly named non-English official set';
  new_error text :=
    'coverage observation requires an exact live English TCGdex set or an explicitly named non-English or undetermined-language official set';
begin
  select pg_get_functiondef(
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure
  )
  into definition;

  if definition is null
    or position(old_language_guard in definition) = 0
    or position(new_language_guard in definition) > 0
    or position(old_error in definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'coverage finalizer is not the expected two-letter language definition';
  end if;

  updated_definition := replace(definition, old_language_guard, new_language_guard);
  updated_definition := replace(updated_definition, old_error, new_error);
  if updated_definition = definition
    or position(new_language_guard in updated_definition) = 0
    or position(new_error in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'coverage finalizer undetermined-language extension was not applied';
  end if;
  execute updated_definition;
end;
$migration$;

comment on function ingest.finalize_public_study_coverage_job_v1(
  uuid, text, bigint, text, jsonb
) is
  'Generation-fenced verifier for nineteen reviewed denominator-only contracts. English contracts require the exact live TCGdex catalog, except the two exact source-native Puerto Rico product identities; explicit non-English or undetermined-language (`und`) contracts require a bounded source-native set name and official set URL. It cannot publish a numerator or inference.';

-- Seed the five manually verified coverage facts immediately. Their source
-- product identity plus the official product specification establishes the
-- denominator; the rows do not claim a frame-by-frame review.
do $migration$
declare
  panama_chaos_policy_id uuid;
  panama_pitch_policy_id uuid;
  guatemala_policy_id uuid;
  argentina_policy_id uuid;
  chile_policy_id uuid;
  verification_time timestamptz := statement_timestamp();
  panama_chaos_evidence text :=
    'abb892071c34d353e811c9715174512bb47304ac72de2508d188e13956e3e4ef';
  panama_pitch_evidence text :=
    '055d48674555e3a9dc79ced8f5886c7960ad200c7c8bdc4383a5623b5e583857';
  guatemala_evidence text :=
    'b6c535ad4e34f0df39c8b9823a8a6e624fbb9a66c2da8329996b484b04a9feeb';
  argentina_evidence text :=
    '9332e272a335d9e81a6e42c702b5d49630357eaf4a7a8c10d9d5f9d40cc05690';
  chile_evidence text :=
    'dd5424daf2b83dde579788be5676d1a59403c49ebf516e4601d82ddaf3f6f74f';
begin
  if panama_chaos_evidence <> encode(
    extensions.digest(
      convert_to(
        E'¡Nuestro PRIMER OPENING de Pokémon TCG! ¿Vale la pena Chaos Rising Booster Bundle?\nOpening del Booster Bundle · sobre por sobre · desde Panamá · official bundle = 6 packs',
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  ) then
    raise exception using errcode = '55000',
      message = 'Panama Chaos Rising evidence hash does not match the immutable excerpt';
  end if;

  if panama_pitch_evidence <> encode(
    extensions.digest(
      convert_to(
        E'¡Abrimos la Build & Battle de Pitch Black! ¿Nos salió una carta increíble? | Pokémon TCG\nabrimos la Build & Battle · todo el contenido · official box = 4 packs',
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  ) then
    raise exception using errcode = '55000',
      message = 'Panama Pitch Black evidence hash does not match the immutable excerpt';
  end if;

  if guatemala_evidence <> encode(
    extensions.digest(
      convert_to(
        E'🦆 El Poder del Pato 💪 | Apertura MegaEvolution + Noticias y Pokeguamazos | PokéShow de Maddi\nAbriremos un Tripack de Mega Evolution · desde Guatemala · official tripack = 3 packs',
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  ) then
    raise exception using errcode = '55000',
      message = 'Guatemala Mega Evolution evidence hash does not match the immutable excerpt';
  end if;

  if argentina_evidence <> encode(
    extensions.digest(
      convert_to(
        E'Abrimos una caja de Pitch Black COMPLETA 😈\nOpening de Cartas Pokemon Pitch Black · caja completa · official booster display = 36 packs',
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  ) then
    raise exception using errcode = '55000',
      message = 'Argentina Pitch Black evidence hash does not match the immutable excerpt';
  end if;

  if chile_evidence <> encode(
    extensions.digest(
      convert_to(
        E'¡Apertura Anticipada! Booster Box completa de Phantasmal Flames -  Pokémon TCG\nabro 36 sobres de la nueva edición Phantasmal Flames · Booster Box completa',
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  ) then
    raise exception using errcode = '55000',
      message = 'Chile Phantasmal Flames evidence hash does not match the immutable excerpt';
  end if;

  select policies.id
  into panama_chaos_policy_id
  from ingest.source_policies as policies
  where policies.source_key = 'public_study_tcg_market_panama_chaos_rising_6'
    and policies.display_name = 'TCG Market Panamá Chaos Rising 6-pack coverage'
    and policies.domain = 'www.youtube.com'
    and policies.base_url = 'https://www.youtube.com/watch?v=fHQpNECg4y4'
    and policies.version = 'public-study-tcg-market-panama-chaos-rising-youtube-v1'
    and policies.config ->> 'study_key' = 'tcg-market-chaos-rising-pa-6-v1'
    and policies.config ->> 'publisher_channel_id' = 'UCa68xVUUIKE8dvcfxCcdyrQ'
    and policies.config ->> 'set_external_id' = 'me04'
    and policies.config ->> 'set_language' = 'und'
    and policies.config ->> 'set_language_basis' = 'source_does_not_state_card_language'
    and policies.config ->> 'product_scope' = 'booster_bundle'
    and policies.config ->> 'pack_count' = '6'
    and not (policies.config ? 'qualifying_hit_pack_count')
    and not (policies.config ? 'qualifying_metric')
    and not (policies.config ? 'metric_version')
    and policies.enabled
    and policies.statistics_eligible_default
    and not policies.is_demo;

  select policies.id
  into panama_pitch_policy_id
  from ingest.source_policies as policies
  where policies.source_key = 'public_study_tcg_market_panama_pitch_black_4'
    and policies.display_name = 'TCG Market Panamá Pitch Black 4-pack coverage'
    and policies.domain = 'www.youtube.com'
    and policies.base_url = 'https://www.youtube.com/watch?v=6kb1MvcnMJE'
    and policies.version = 'public-study-tcg-market-panama-pitch-black-youtube-v1'
    and policies.config ->> 'study_key' = 'tcg-market-pitch-black-pa-4-v1'
    and policies.config ->> 'publisher_channel_id' = 'UCa68xVUUIKE8dvcfxCcdyrQ'
    and policies.config ->> 'set_external_id' = 'me05'
    and policies.config ->> 'set_language' = 'und'
    and policies.config ->> 'set_language_basis' = 'source_does_not_state_card_language'
    and policies.config ->> 'product_scope' = 'build_and_battle'
    and policies.config ->> 'pack_count' = '4'
    and not (policies.config ? 'qualifying_hit_pack_count')
    and not (policies.config ? 'qualifying_metric')
    and not (policies.config ? 'metric_version')
    and policies.enabled
    and policies.statistics_eligible_default
    and not policies.is_demo;

  select policies.id
  into guatemala_policy_id
  from ingest.source_policies as policies
  where policies.source_key = 'public_study_pokeshow_guatemala_megaevolution_3'
    and policies.display_name = 'PokéShow Guatemala Mega Evolution 3-pack coverage'
    and policies.domain = 'www.youtube.com'
    and policies.base_url = 'https://www.youtube.com/watch?v=DWRdhUuIUvI'
    and policies.version = 'public-study-pokeshow-guatemala-megaevolution-youtube-v1'
    and policies.config ->> 'study_key' = 'pokeshow-mega-evolution-gt-3-v1'
    and policies.config ->> 'publisher_channel_id' = 'UChG8m-xoKqrXJDCEoE2i9Jg'
    and policies.config ->> 'set_external_id' = 'me01'
    and policies.config ->> 'set_language' = 'und'
    and policies.config ->> 'set_language_basis' = 'source_does_not_state_card_language'
    and policies.config ->> 'product_scope' = 'three_pack_blister'
    and policies.config ->> 'product_variant_claim' = 'not_claimed'
    and policies.config ->> 'pack_count' = '3'
    and not (policies.config ? 'qualifying_hit_pack_count')
    and not (policies.config ? 'qualifying_metric')
    and not (policies.config ? 'metric_version')
    and policies.enabled
    and policies.statistics_eligible_default
    and not policies.is_demo;

  select policies.id
  into argentina_policy_id
  from ingest.source_policies as policies
  where policies.source_key = 'public_study_cartas_pokemon_argentina_pitch_black_36'
    and policies.display_name = 'Cartas Pokemon Argentina Pitch Black 36-pack coverage'
    and policies.domain = 'www.youtube.com'
    and policies.base_url = 'https://www.youtube.com/watch?v=HcsWjycR1L0'
    and policies.version = 'public-study-cartas-pokemon-argentina-pitch-black-youtube-v1'
    and policies.config ->> 'study_key' = 'cartas-pokemon-argentina-pitch-black-ar-36-v1'
    and policies.config ->> 'publisher_channel_id' = 'UCGBtAPv7mLLRgdqeupj2kLg'
    and policies.config ->> 'set_external_id' = 'me05'
    and policies.config ->> 'set_language' = 'und'
    and policies.config ->> 'set_language_basis' = 'source_does_not_state_card_language'
    and policies.config ->> 'product_scope' = 'booster_box'
    and policies.config ->> 'pack_count' = '36'
    and not (policies.config ? 'qualifying_hit_pack_count')
    and not (policies.config ? 'qualifying_metric')
    and not (policies.config ? 'metric_version')
    and policies.enabled
    and policies.statistics_eligible_default
    and not policies.is_demo;

  select policies.id
  into chile_policy_id
  from ingest.source_policies as policies
  where policies.source_key = 'public_study_pokemaniaco_lucas_cl_36'
    and policies.display_name = 'Pokemaniaco Lucas Phantasmal Flames 36-pack coverage'
    and policies.domain = 'www.youtube.com'
    and policies.base_url = 'https://www.youtube.com/watch?v=Meg4AO9CqHE'
    and policies.version = 'public-study-pokemaniaco-lucas-phantasmal-flames-youtube-v1'
    and policies.config ->> 'study_key' = 'pokemaniaco-lucas-phantasmal-flames-cl-36-v1'
    and policies.config ->> 'publisher_channel_id' = 'UCDKXzvS5YaUJwsHD1wNkWBw'
    and policies.config ->> 'set_external_id' = 'me02'
    and policies.config ->> 'set_language' = 'und'
    and policies.config ->> 'set_language_basis' = 'source_does_not_state_card_language'
    and policies.config ->> 'product_scope' = 'booster_box'
    and policies.config ->> 'pack_count' = '36'
    and not (policies.config ? 'qualifying_hit_pack_count')
    and not (policies.config ? 'qualifying_metric')
    and not (policies.config ? 'metric_version')
    and policies.enabled
    and policies.statistics_eligible_default
    and not policies.is_demo;

  if panama_chaos_policy_id is null
    or panama_pitch_policy_id is null
    or guatemala_policy_id is null
    or argentina_policy_id is null
    or chile_policy_id is null
  then
    raise exception using errcode = '55000',
      message = 'Central/South America reviewed source policy is unavailable or drifted';
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
    'tcg-market-chaos-rising-pa-6-v1',
    panama_chaos_policy_id,
    'PA',
    'Panama',
    '2026-08-03T00:15:39Z'::timestamptz,
    6,
    'me04',
    'booster_bundle',
    'public-study-tcg-market-panama-chaos-rising-youtube-v1',
    'tcg-market-panama-chaos-rising-evidence-v1',
    'public-study-tcg-market-panama-chaos-rising-youtube-v1',
    panama_chaos_evidence,
    verification_time,
    verification_time,
    false
  ),
  (
    'tcg-market-pitch-black-pa-4-v1',
    panama_pitch_policy_id,
    'PA',
    'Panama',
    '2026-08-05T19:09:10Z'::timestamptz,
    4,
    'me05',
    'build_and_battle',
    'public-study-tcg-market-panama-pitch-black-youtube-v1',
    'tcg-market-panama-pitch-black-evidence-v1',
    'public-study-tcg-market-panama-pitch-black-youtube-v1',
    panama_pitch_evidence,
    verification_time,
    verification_time,
    false
  ),
  (
    'pokeshow-mega-evolution-gt-3-v1',
    guatemala_policy_id,
    'GT',
    'Guatemala',
    '2025-10-06T17:21:33Z'::timestamptz,
    3,
    'me01',
    'three_pack_blister',
    'public-study-pokeshow-guatemala-megaevolution-youtube-v1',
    'pokeshow-guatemala-megaevolution-evidence-v1',
    'public-study-pokeshow-guatemala-megaevolution-youtube-v1',
    guatemala_evidence,
    verification_time,
    verification_time,
    false
  ),
  (
    'cartas-pokemon-argentina-pitch-black-ar-36-v1',
    argentina_policy_id,
    'AR',
    'Argentina',
    '2026-07-17T18:18:50Z'::timestamptz,
    36,
    'me05',
    'booster_box',
    'public-study-cartas-pokemon-argentina-pitch-black-youtube-v1',
    'cartas-pokemon-argentina-pitch-black-evidence-v1',
    'public-study-cartas-pokemon-argentina-pitch-black-youtube-v1',
    argentina_evidence,
    verification_time,
    verification_time,
    false
  ),
  (
    'pokemaniaco-lucas-phantasmal-flames-cl-36-v1',
    chile_policy_id,
    'CL',
    'Chile',
    '2025-11-13T16:00:06Z'::timestamptz,
    36,
    'me02',
    'booster_box',
    'public-study-pokemaniaco-lucas-phantasmal-flames-youtube-v1',
    'pokemaniaco-lucas-phantasmal-flames-evidence-v1',
    'public-study-pokemaniaco-lucas-phantasmal-flames-youtube-v1',
    chile_evidence,
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
        'pokehanna-ascended-heroes-ca-9-v1',
        'tcg-market-chaos-rising-pa-6-v1',
        'tcg-market-pitch-black-pa-4-v1',
        'pokeshow-mega-evolution-gt-3-v1',
        'cartas-pokemon-argentina-pitch-black-ar-36-v1',
        'pokemaniaco-lucas-phantasmal-flames-cl-36-v1'
      )
    )
  );

commit;
