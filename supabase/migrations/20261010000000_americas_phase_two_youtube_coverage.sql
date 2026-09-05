begin;

-- Five exact public YouTube watch pages add reviewed publisher-country coverage
-- for Costa Rica, Colombia, Ecuador, Peru, and Uruguay. These contracts retain
-- only immutable metadata facts and complete pack denominators; none claims a
-- normalized qualifying-hit numerator or publishes a rate.
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
  'public_study_cofre_lab_chilling_reign_cr_4',
  'Cofre Lab Chilling Reign 4-pack coverage',
  'public_web',
  'www.youtube.com',
  'https://www.youtube.com/watch?v=15eGmqByP0I',
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
    "study_key":"cofre-lab-chilling-reign-cr-4-v1",
    "canonical_url":"https://www.youtube.com/watch?v=15eGmqByP0I",
    "fetch_url":"https://www.youtube.com/watch?v=15eGmqByP0I",
    "collector_version":"public-study-cofre-lab-chilling-reign-youtube-v1",
    "parser_version":"cofre-lab-chilling-reign-evidence-v1",
    "country_code":"CR",
    "country_name":"Costa Rica",
    "geography_basis":"publisher_country",
    "geography_confidence":"tier_b",
    "publisher_country_url":"https://www.youtube.com/@cofrelab/about",
    "publisher_channel_id":"UCqYl3y-wsJqvwow5_tIa22A",
    "publisher_country_evidence":"country:\"Costa Rica\"",
    "publisher_country_checked_at":"2026-09-05",
    "geography_review_method":"manual_static_channel_about_review",
    "set_external_id":"swsh6",
    "set_language":"und",
    "set_language_basis":"source_does_not_state_card_language",
    "set_name":"Chilling Reign",
    "set_official_url":"https://press.pokemon.com/en/MEDIA-ALERT-New-Pokemon-Trading-Card-Game-Sword-ShieldChilling-Reign-E",
    "product_name":"Sword & Shield—Chilling Reign Build & Battle Box",
    "product_scope":"build_and_battle",
    "pack_count":4,
    "denominator_basis":"source_named_prerelease_box_plus_official_4_pack_spec",
    "denominator_derivation":"one_build_and_battle_box_x_4",
    "source_published_at":"2021-06-05T22:54:03-07:00",
    "observed_at":"2021-06-06T05:54:03Z",
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
  'public-study-cofre-lab-chilling-reign-youtube-v1',
  86400,
  false
),
(
  'public_study_pokeyabros_perfect_order_co_2',
  'Pokeyabros Perfect Order 2-pack coverage',
  'public_web',
  'www.youtube.com',
  'https://www.youtube.com/watch?v=n_PdWg27x-o',
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
    "study_key":"pokeyabros-perfect-order-co-2-v1",
    "canonical_url":"https://www.youtube.com/watch?v=n_PdWg27x-o",
    "fetch_url":"https://www.youtube.com/watch?v=n_PdWg27x-o",
    "collector_version":"public-study-pokeyabros-perfect-order-youtube-v1",
    "parser_version":"pokeyabros-perfect-order-evidence-v1",
    "country_code":"CO",
    "country_name":"Colombia",
    "geography_basis":"publisher_country",
    "geography_confidence":"tier_b",
    "publisher_country_url":"https://www.youtube.com/@Pokeyabros/about",
    "publisher_channel_id":"UC6iMHQS7wp-WVH_pD4leBZw",
    "publisher_country_evidence":"country:\"Colombia\"",
    "publisher_country_checked_at":"2026-09-05",
    "geography_review_method":"manual_static_channel_about_review",
    "set_external_id":"me03",
    "set_language":"und",
    "set_language_basis":"source_does_not_state_card_language",
    "set_name":"Perfect Order",
    "set_official_url":"https://www.pokemon.com/us/features/art-of-the-pokemon-tcg-mega-evolution-perfect-order-expansion",
    "product_name":"Two Perfect Order booster packs",
    "product_scope":"all",
    "pack_count":2,
    "denominator_basis":"source_declared_two_booster_opening",
    "denominator_derivation":"source_declared_2_packs",
    "source_published_at":"2026-09-04T07:00:23-07:00",
    "observed_at":"2026-09-04T14:00:23Z",
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
  'public-study-pokeyabros-perfect-order-youtube-v1',
  86400,
  false
),
(
  'public_study_andree_insane_cards_cosmic_eclipse_ec_20',
  'Andree Insane Cards Cosmic Eclipse 20-pack coverage',
  'public_web',
  'www.youtube.com',
  'https://www.youtube.com/watch?v=wDDCbJKFTCw',
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
    "study_key":"andree-insane-cards-cosmic-eclipse-ec-20-v1",
    "canonical_url":"https://www.youtube.com/watch?v=wDDCbJKFTCw",
    "fetch_url":"https://www.youtube.com/watch?v=wDDCbJKFTCw",
    "collector_version":"public-study-andree-insane-cards-cosmic-eclipse-youtube-v1",
    "parser_version":"andree-insane-cards-cosmic-eclipse-evidence-v1",
    "country_code":"EC",
    "country_name":"Ecuador",
    "geography_basis":"publisher_country",
    "geography_confidence":"tier_b",
    "publisher_country_url":"https://www.youtube.com/@andreeinsanecards/about",
    "publisher_channel_id":"UCvg1acSdKlzcCXAQQKcMvqg",
    "publisher_country_evidence":"country:\"Ecuador\"",
    "publisher_country_checked_at":"2026-09-05",
    "geography_review_method":"manual_static_channel_about_review",
    "set_external_id":"sm12",
    "set_language":"und",
    "set_language_basis":"source_does_not_state_card_language",
    "set_name":"Cosmic Eclipse",
    "set_official_url":"https://www.pokemon.com/us/pokemon-tcg/sun-moon-cosmic-eclipse",
    "product_name":"Twenty Cosmic Eclipse booster packs",
    "product_scope":"all",
    "pack_count":20,
    "denominator_basis":"source_declared_twenty_booster_opening",
    "denominator_derivation":"source_declared_20_packs",
    "source_published_at":"2023-06-27T14:00:07-07:00",
    "observed_at":"2023-06-27T21:00:07Z",
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
  'public-study-andree-insane-cards-cosmic-eclipse-youtube-v1',
  86400,
  false
),
(
  'public_study_thekeiplay_lost_origin_pe_36',
  'TheKeiPlay Lost Origin 36-pack coverage',
  'public_web',
  'www.youtube.com',
  'https://www.youtube.com/watch?v=YKHGiYIhsQU',
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
    "study_key":"thekeiplay-lost-origin-pe-36-v1",
    "canonical_url":"https://www.youtube.com/watch?v=YKHGiYIhsQU",
    "fetch_url":"https://www.youtube.com/watch?v=YKHGiYIhsQU",
    "collector_version":"public-study-thekeiplay-lost-origin-youtube-v1",
    "parser_version":"thekeiplay-lost-origin-evidence-v1",
    "country_code":"PE",
    "country_name":"Peru",
    "geography_basis":"publisher_country",
    "geography_confidence":"tier_b",
    "publisher_country_url":"https://www.youtube.com/@TheKeiPlay/about",
    "publisher_channel_id":"UChAro6QS0gP88qhgOTBnuSA",
    "publisher_country_evidence":"country:\"Peru\"",
    "publisher_country_checked_at":"2026-09-05",
    "geography_review_method":"manual_static_channel_about_review",
    "set_external_id":"swsh11",
    "set_language":"und",
    "set_language_basis":"source_does_not_state_card_language",
    "set_name":"Lost Origin",
    "set_official_url":"https://www.pokemon.com/us/news/enter-to-win-pokemon-tcg-sword-shield-era-booster-display-boxes",
    "product_name":"Sword & Shield—Lost Origin Booster Display Box",
    "product_scope":"booster_box",
    "pack_count":36,
    "denominator_basis":"source_named_complete_box_plus_official_36_pack_spec",
    "denominator_derivation":"one_complete_booster_display_x_36",
    "source_published_at":"2022-09-05T11:00:12-07:00",
    "observed_at":"2022-09-05T18:00:12Z",
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
  'public-study-thekeiplay-lost-origin-youtube-v1',
  86400,
  false
),
(
  'public_study_gringo_gameplays_silver_tempest_uy_36',
  'Gringo-GamePlays Silver Tempest 36-pack coverage',
  'public_web',
  'www.youtube.com',
  'https://www.youtube.com/watch?v=lYzM0jtPLKw',
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
    "study_key":"gringo-gameplays-silver-tempest-uy-36-v1",
    "canonical_url":"https://www.youtube.com/watch?v=lYzM0jtPLKw",
    "fetch_url":"https://www.youtube.com/watch?v=lYzM0jtPLKw",
    "collector_version":"public-study-gringo-gameplays-silver-tempest-youtube-v1",
    "parser_version":"gringo-gameplays-silver-tempest-evidence-v1",
    "country_code":"UY",
    "country_name":"Uruguay",
    "geography_basis":"publisher_country",
    "geography_confidence":"tier_b",
    "publisher_country_url":"https://www.youtube.com/@gringo-gameplays8987/about",
    "publisher_channel_id":"UCqxdkBJE9jPp0JEv6eA7riQ",
    "publisher_country_evidence":"country:\"Uruguay\"",
    "publisher_country_checked_at":"2026-09-05",
    "geography_review_method":"manual_static_channel_about_review",
    "set_external_id":"swsh12",
    "set_language":"und",
    "set_language_basis":"source_does_not_state_card_language",
    "set_name":"Silver Tempest",
    "set_official_url":"https://www.pokemon.com/us/news/enter-to-win-pokemon-tcg-sword-shield-era-booster-display-boxes",
    "product_name":"Sword & Shield—Silver Tempest Booster Display Box",
    "product_scope":"booster_box",
    "pack_count":36,
    "denominator_basis":"source_named_booster_box_plus_official_36_pack_spec",
    "denominator_derivation":"one_booster_display_x_36",
    "source_published_at":"2023-03-30T10:14:02-07:00",
    "observed_at":"2023-03-30T17:14:02Z",
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
  'public-study-gringo-gameplays-silver-tempest-youtube-v1',
  86400,
  false
);

insert into ingest.source_request_gates (source_key)
values
  ('public_study_cofre_lab_chilling_reign_cr_4'),
  ('public_study_pokeyabros_perfect_order_co_2'),
  ('public_study_andree_insane_cards_cosmic_eclipse_ec_20'),
  ('public_study_thekeiplay_lost_origin_pe_36'),
  ('public_study_gringo_gameplays_silver_tempest_uy_36');

create or replace function ingest.reviewed_public_study_gates_ready_v1()
returns boolean
language sql
stable
security definer
parallel safe
set search_path = pg_catalog
as $$
  select count(*) = 24
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
    'public_study_pokemaniaco_lucas_cl_36',
    'public_study_cofre_lab_chilling_reign_cr_4',
    'public_study_pokeyabros_perfect_order_co_2',
    'public_study_andree_insane_cards_cosmic_eclipse_ec_20',
    'public_study_thekeiplay_lost_origin_pe_36',
    'public_study_gringo_gameplays_silver_tempest_uy_36'
  );
$$;

alter function ingest.reviewed_public_study_gates_ready_v1() owner to postgres;
revoke all on function ingest.reviewed_public_study_gates_ready_v1()
  from public, anon, authenticated, service_role;
grant execute on function ingest.reviewed_public_study_gates_ready_v1()
  to service_role;
comment on function ingest.reviewed_public_study_gates_ready_v1() is
  'Boolean-only readiness check for all exact reviewed public-study request gates; it exposes no gate identity or lease state.';

-- Append ordinals 20 through 24 only when the exact Chile ordinal-19 suffix
-- remains present. All five contracts are denominator-only.
do $migration$
declare
  definition text;
  updated_definition text;
  old_suffix text := $old$
      array['¡Apertura Anticipada! Booster Box completa de Phantasmal Flames -  Pokémon TCG']::text[]
    );$old$;
  new_suffix text := $new$
      array['¡Apertura Anticipada! Booster Box completa de Phantasmal Flames -  Pokémon TCG']::text[]
    ),
    (
      20,
      'cofre-lab-chilling-reign-cr-4-v1'::text,
      'public_study_cofre_lab_chilling_reign_cr_4'::text,
      'cofre_lab_chilling_reign_study'::text,
      'Cofre Lab Chilling Reign 4-pack study'::text,
      'Reviewed Costa Rica publisher-country coverage: the exact source identifies a Chilling Reign prerelease-box opening, while the official Build & Battle specification supplies the four-pack denominator. Physical opening location and card language are not claimed. No normalized qualifying-hit numerator exists, so no rate or inference is published.'::text,
      'Cofre Lab Chilling Reign 4-pack coverage'::text,
      'www.youtube.com'::text,
      'https://www.youtube.com/watch?v=15eGmqByP0I'::text,
      'public-study-cofre-lab-chilling-reign-youtube-v1'::text,
      '{
        "study_key":"cofre-lab-chilling-reign-cr-4-v1",
        "canonical_url":"https://www.youtube.com/watch?v=15eGmqByP0I",
        "fetch_url":"https://www.youtube.com/watch?v=15eGmqByP0I",
        "collector_version":"public-study-cofre-lab-chilling-reign-youtube-v1",
        "parser_version":"cofre-lab-chilling-reign-evidence-v1",
        "country_code":"CR",
        "country_name":"Costa Rica",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "publisher_country_url":"https://www.youtube.com/@cofrelab/about",
        "publisher_channel_id":"UCqYl3y-wsJqvwow5_tIa22A",
        "publisher_country_evidence":"country:\"Costa Rica\"",
        "publisher_country_checked_at":"2026-09-05",
        "geography_review_method":"manual_static_channel_about_review",
        "set_external_id":"swsh6",
        "set_language":"und",
        "set_language_basis":"source_does_not_state_card_language",
        "set_name":"Chilling Reign",
        "set_official_url":"https://press.pokemon.com/en/MEDIA-ALERT-New-Pokemon-Trading-Card-Game-Sword-ShieldChilling-Reign-E",
        "product_name":"Sword & Shield—Chilling Reign Build & Battle Box",
        "product_scope":"build_and_battle",
        "pack_count":4,
        "denominator_basis":"source_named_prerelease_box_plus_official_4_pack_spec",
        "denominator_derivation":"one_build_and_battle_box_x_4",
        "source_published_at":"2021-06-05T22:54:03-07:00",
        "observed_at":"2021-06-06T05:54:03Z",
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
      E'Unboxing Pre Release *Chilling Reign- *Reinado Escalofriante #pokemon tcg\nEl día de hoy estaremos haciendo Unboxing del Pre Release de *Chilling Reign* o *Reinado Escalofriente* · official Build & Battle Box = 4 packs'::text,
      array['Unboxing Pre Release *Chilling Reign- *Reinado Escalofriante #pokemon tcg']::text[]
    ),
    (
      21,
      'pokeyabros-perfect-order-co-2-v1'::text,
      'public_study_pokeyabros_perfect_order_co_2'::text,
      'pokeyabros_perfect_order_study'::text,
      'Pokeyabros Perfect Order 2-pack study'::text,
      'Reviewed Colombia publisher-country coverage: the exact source declares an opening of two Perfect Order booster packs. Physical opening location and card language are not claimed. No normalized qualifying-hit numerator exists, so no rate or inference is published.'::text,
      'Pokeyabros Perfect Order 2-pack coverage'::text,
      'www.youtube.com'::text,
      'https://www.youtube.com/watch?v=n_PdWg27x-o'::text,
      'public-study-pokeyabros-perfect-order-youtube-v1'::text,
      '{
        "study_key":"pokeyabros-perfect-order-co-2-v1",
        "canonical_url":"https://www.youtube.com/watch?v=n_PdWg27x-o",
        "fetch_url":"https://www.youtube.com/watch?v=n_PdWg27x-o",
        "collector_version":"public-study-pokeyabros-perfect-order-youtube-v1",
        "parser_version":"pokeyabros-perfect-order-evidence-v1",
        "country_code":"CO",
        "country_name":"Colombia",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "publisher_country_url":"https://www.youtube.com/@Pokeyabros/about",
        "publisher_channel_id":"UC6iMHQS7wp-WVH_pD4leBZw",
        "publisher_country_evidence":"country:\"Colombia\"",
        "publisher_country_checked_at":"2026-09-05",
        "geography_review_method":"manual_static_channel_about_review",
        "set_external_id":"me03",
        "set_language":"und",
        "set_language_basis":"source_does_not_state_card_language",
        "set_name":"Perfect Order",
        "set_official_url":"https://www.pokemon.com/us/features/art-of-the-pokemon-tcg-mega-evolution-perfect-order-expansion",
        "product_name":"Two Perfect Order booster packs",
        "product_scope":"all",
        "pack_count":2,
        "denominator_basis":"source_declared_two_booster_opening",
        "denominator_derivation":"source_declared_2_packs",
        "source_published_at":"2026-09-04T07:00:23-07:00",
        "observed_at":"2026-09-04T14:00:23Z",
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
      E'🎁¿PREMIO O FRACASO? #579 BOOSTER PACK OPENING PERFECT ORDER\n🎁 ¡Abrimos dos boosters de Pokémon TCG! 🎴'::text,
      array['🎁¿PREMIO O FRACASO? #579 BOOSTER PACK OPENING PERFECT ORDER']::text[]
    ),
    (
      22,
      'andree-insane-cards-cosmic-eclipse-ec-20-v1'::text,
      'public_study_andree_insane_cards_cosmic_eclipse_ec_20'::text,
      'andree_insane_cards_cosmic_eclipse_study'::text,
      'Andree Insane Cards Cosmic Eclipse 20-pack study'::text,
      'Reviewed Ecuador publisher-country coverage: the exact source declares an opening of 20 Cosmic Eclipse booster packs. Physical opening location and card language are not claimed. No normalized qualifying-hit numerator exists, so no rate or inference is published.'::text,
      'Andree Insane Cards Cosmic Eclipse 20-pack coverage'::text,
      'www.youtube.com'::text,
      'https://www.youtube.com/watch?v=wDDCbJKFTCw'::text,
      'public-study-andree-insane-cards-cosmic-eclipse-youtube-v1'::text,
      '{
        "study_key":"andree-insane-cards-cosmic-eclipse-ec-20-v1",
        "canonical_url":"https://www.youtube.com/watch?v=wDDCbJKFTCw",
        "fetch_url":"https://www.youtube.com/watch?v=wDDCbJKFTCw",
        "collector_version":"public-study-andree-insane-cards-cosmic-eclipse-youtube-v1",
        "parser_version":"andree-insane-cards-cosmic-eclipse-evidence-v1",
        "country_code":"EC",
        "country_name":"Ecuador",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "publisher_country_url":"https://www.youtube.com/@andreeinsanecards/about",
        "publisher_channel_id":"UCvg1acSdKlzcCXAQQKcMvqg",
        "publisher_country_evidence":"country:\"Ecuador\"",
        "publisher_country_checked_at":"2026-09-05",
        "geography_review_method":"manual_static_channel_about_review",
        "set_external_id":"sm12",
        "set_language":"und",
        "set_language_basis":"source_does_not_state_card_language",
        "set_name":"Cosmic Eclipse",
        "set_official_url":"https://www.pokemon.com/us/pokemon-tcg/sun-moon-cosmic-eclipse",
        "product_name":"Twenty Cosmic Eclipse booster packs",
        "product_scope":"all",
        "pack_count":20,
        "denominator_basis":"source_declared_twenty_booster_opening",
        "denominator_derivation":"source_declared_20_packs",
        "source_published_at":"2023-06-27T14:00:07-07:00",
        "observed_at":"2023-06-27T21:00:07Z",
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
      E'🔥 Buscando a #Charizard Ep6: Abriendo 20 #CosmicEclipse Booster Packs LA MEJOR APERTURA DE YOUTUBE!\nEn esta oprtunidad vamos a darle con 20 de boosters de #CosmicEclipse'::text,
      array['🔥 Buscando a #Charizard Ep6: Abriendo 20 #CosmicEclipse Booster Packs LA MEJOR APERTURA DE YOUTUBE!']::text[]
    ),
    (
      23,
      'thekeiplay-lost-origin-pe-36-v1'::text,
      'public_study_thekeiplay_lost_origin_pe_36'::text,
      'thekeiplay_lost_origin_study'::text,
      'TheKeiPlay Lost Origin 36-pack study'::text,
      'Reviewed Peru publisher-country coverage: the exact source names a complete Lost Origin booster-box opening, while the official Sword & Shield display specification supplies the 36-pack denominator. Physical opening location and card language are not claimed. No normalized qualifying-hit numerator exists, so no rate or inference is published.'::text,
      'TheKeiPlay Lost Origin 36-pack coverage'::text,
      'www.youtube.com'::text,
      'https://www.youtube.com/watch?v=YKHGiYIhsQU'::text,
      'public-study-thekeiplay-lost-origin-youtube-v1'::text,
      '{
        "study_key":"thekeiplay-lost-origin-pe-36-v1",
        "canonical_url":"https://www.youtube.com/watch?v=YKHGiYIhsQU",
        "fetch_url":"https://www.youtube.com/watch?v=YKHGiYIhsQU",
        "collector_version":"public-study-thekeiplay-lost-origin-youtube-v1",
        "parser_version":"thekeiplay-lost-origin-evidence-v1",
        "country_code":"PE",
        "country_name":"Peru",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "publisher_country_url":"https://www.youtube.com/@TheKeiPlay/about",
        "publisher_channel_id":"UChAro6QS0gP88qhgOTBnuSA",
        "publisher_country_evidence":"country:\"Peru\"",
        "publisher_country_checked_at":"2026-09-05",
        "geography_review_method":"manual_static_channel_about_review",
        "set_external_id":"swsh11",
        "set_language":"und",
        "set_language_basis":"source_does_not_state_card_language",
        "set_name":"Lost Origin",
        "set_official_url":"https://www.pokemon.com/us/news/enter-to-win-pokemon-tcg-sword-shield-era-booster-display-boxes",
        "product_name":"Sword & Shield—Lost Origin Booster Display Box",
        "product_scope":"booster_box",
        "pack_count":36,
        "denominator_basis":"source_named_complete_box_plus_official_36_pack_spec",
        "denominator_derivation":"one_complete_booster_display_x_36",
        "source_published_at":"2022-09-05T11:00:12-07:00",
        "observed_at":"2022-09-05T18:00:12Z",
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
      E'MEGA Apertura!!!😱 Booster Box 💥LOST ORIGIN (Origen Perdido)\nApertura Completa de una Booster Box deel set de Lost Origin. · official display = 36 packs'::text,
      array['MEGA Apertura!!!😱 Booster Box 💥LOST ORIGIN (Origen Perdido)']::text[]
    ),
    (
      24,
      'gringo-gameplays-silver-tempest-uy-36-v1'::text,
      'public_study_gringo_gameplays_silver_tempest_uy_36'::text,
      'gringo_gameplays_silver_tempest_study'::text,
      'Gringo-GamePlays Silver Tempest 36-pack study'::text,
      'Reviewed Uruguay publisher-country coverage: the exact source title names a Silver Tempest booster-box opening, while the official Sword & Shield display specification supplies the 36-pack denominator. The source description is empty; physical opening location and card language are not claimed. No normalized qualifying-hit numerator exists, so no rate or inference is published.'::text,
      'Gringo-GamePlays Silver Tempest 36-pack coverage'::text,
      'www.youtube.com'::text,
      'https://www.youtube.com/watch?v=lYzM0jtPLKw'::text,
      'public-study-gringo-gameplays-silver-tempest-youtube-v1'::text,
      '{
        "study_key":"gringo-gameplays-silver-tempest-uy-36-v1",
        "canonical_url":"https://www.youtube.com/watch?v=lYzM0jtPLKw",
        "fetch_url":"https://www.youtube.com/watch?v=lYzM0jtPLKw",
        "collector_version":"public-study-gringo-gameplays-silver-tempest-youtube-v1",
        "parser_version":"gringo-gameplays-silver-tempest-evidence-v1",
        "country_code":"UY",
        "country_name":"Uruguay",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "publisher_country_url":"https://www.youtube.com/@gringo-gameplays8987/about",
        "publisher_channel_id":"UCqxdkBJE9jPp0JEv6eA7riQ",
        "publisher_country_evidence":"country:\"Uruguay\"",
        "publisher_country_checked_at":"2026-09-05",
        "geography_review_method":"manual_static_channel_about_review",
        "set_external_id":"swsh12",
        "set_language":"und",
        "set_language_basis":"source_does_not_state_card_language",
        "set_name":"Silver Tempest",
        "set_official_url":"https://www.pokemon.com/us/news/enter-to-win-pokemon-tcg-sword-shield-era-booster-display-boxes",
        "product_name":"Sword & Shield—Silver Tempest Booster Display Box",
        "product_scope":"booster_box",
        "pack_count":36,
        "denominator_basis":"source_named_booster_box_plus_official_36_pack_spec",
        "denominator_derivation":"one_booster_display_x_36",
        "source_published_at":"2023-03-30T10:14:02-07:00",
        "observed_at":"2023-03-30T17:14:02Z",
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
      E'TCG Pokémon Uruguay  Unboxing  Booster BOX Silver Tempest + Codigos TCG Live\nBooster BOX Silver Tempest · official display = 36 packs'::text,
      array['TCG Pokémon Uruguay  Unboxing  Booster BOX Silver Tempest + Codigos TCG Live']::text[]
    );$new$;
begin
  select pg_get_functiondef(
    'ingest.reviewed_public_study_contracts()'::regprocedure
  )
  into definition;

  if definition is null
    or position(old_suffix in definition) = 0
    or position('cofre-lab-chilling-reign-cr-4-v1' in definition) > 0
    or position('pokeyabros-perfect-order-co-2-v1' in definition) > 0
    or position('andree-insane-cards-cosmic-eclipse-ec-20-v1' in definition) > 0
    or position('thekeiplay-lost-origin-pe-36-v1' in definition) > 0
    or position('gringo-gameplays-silver-tempest-uy-36-v1' in definition) > 0
    or (
      select array_agg(contracts.ordinal order by contracts.ordinal)
      from ingest.reviewed_public_study_contracts() as contracts
    ) is distinct from array[
      1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19
    ]::integer[]
  then
    raise exception using
      errcode = '55000',
      message = 'reviewed public-study registry is not the expected ordinal-19 definition';
  end if;

  updated_definition := replace(definition, old_suffix, new_suffix);
  if updated_definition = definition then
    raise exception using
      errcode = '55000',
      message = 'Americas phase-two reviewed coverage registry extension was not applied';
  end if;
  execute updated_definition;
end;
$migration$;

alter function ingest.reviewed_public_study_contracts() owner to postgres;
revoke all on function ingest.reviewed_public_study_contracts()
  from public, anon, authenticated, service_role;
comment on function ingest.reviewed_public_study_contracts() is
  'Owner-only immutable reviewed-study facts. Includes private historical facts and exact bounded coverage evidence; never grant this function to API or worker roles.';

-- Move all denominator-only queue and persistence boundaries together.
do $migration$
declare
  function_oid regprocedure;
  source_definition text;
  updated_definition text;
  old_predicate text :=
    'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19)';
  new_predicate text :=
    'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24)';
begin
  foreach function_oid in array ARRAY[
    'ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure,
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure,
    'ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamptz,integer)'::regprocedure,
    'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)'::regprocedure
  ]
  loop
    source_definition := pg_get_functiondef(function_oid::oid);
    if position(old_predicate in source_definition) = 0
      or position(new_predicate in source_definition) > 0
    then
      raise exception using
        errcode = '55000',
        message = 'reviewed coverage function is missing the expected ordinal-19 predicate',
        detail = function_oid::text;
    end if;
    updated_definition := replace(source_definition, old_predicate, new_predicate);
    if updated_definition = source_definition then
      raise exception using
        errcode = '55000',
        message = 'reviewed coverage ordinal-20-through-24 extension was not applied',
        detail = function_oid::text;
    end if;
    execute updated_definition;
  end loop;
end;
$migration$;

-- Coverage is an evidence register, not a recency leaderboard. Derive the
-- public period start from the earliest nonfuture reviewed contract so an old,
-- accurately dated source remains visible instead of being silently discarded
-- by the former 365-day display window. The end remains the current UTC date.
do $migration$
declare
  function_oid regprocedure;
  source_definition text;
  updated_definition text;
  old_window constant text := $window$(statement_timestamp() at time zone 'UTC')::date - 364 as period_start$window$;
  new_window constant text := $window$coalesce(
      (
        select min(
          (
            (contracts.config ->> 'observed_at')::timestamptz
              at time zone 'UTC'
          )::date
        )
        from ingest.reviewed_public_study_contracts() as contracts
        where contracts.config ->> 'observed_at' is not null
          and (contracts.config ->> 'observed_at')::timestamptz
            <= statement_timestamp()
      ),
      (statement_timestamp() at time zone 'UTC')::date
    ) as period_start$window$;
begin
  foreach function_oid in array array[
    'public.get_public_study_coverage_v2()'::regprocedure,
    'public.get_public_study_coverage_v3()'::regprocedure
  ]
  loop
    source_definition := pg_get_functiondef(function_oid::oid);
    if position(old_window in source_definition) = 0
      or position(new_window in source_definition) > 0
    then
      raise exception using
        errcode = '55000',
        message = 'public reviewed coverage function is missing the expected 365-day display window',
        detail = function_oid::text;
    end if;

    updated_definition := replace(source_definition, old_window, new_window);
    if updated_definition = source_definition then
      raise exception using
        errcode = '55000',
        message = 'public reviewed evidence-range update was not applied',
        detail = function_oid::text;
    end if;
    execute updated_definition;
  end loop;
end;
$migration$;

alter function public.get_public_study_coverage_v2() owner to postgres;
revoke all on function public.get_public_study_coverage_v2()
  from public, anon, authenticated, service_role;
grant execute on function public.get_public_study_coverage_v2()
  to anon, authenticated;

alter function public.get_public_study_coverage_v3() owner to postgres;
revoke all on function public.get_public_study_coverage_v3()
  from public, anon, authenticated, service_role;
grant execute on function public.get_public_study_coverage_v3()
  to anon, authenticated;

comment on function public.get_public_study_coverage_v2() is
  'Registry-driven denominator-safe coverage over the complete reviewed, nonfuture evidence range, with per-country source-native language, set, and product data versions; never returns evidence, numerator, policy, job, gate, or inference fields.';

comment on function public.get_public_study_coverage_v3() is
  'Complete reviewed, nonfuture coverage plus exact descriptive SIR-pack sample arithmetic when both a normalized numerator and denominator are verified; publishes no baseline, posterior, interval, delta, signal, evidence body, or private policy identity.';

comment on function ingest.finalize_public_study_coverage_job_v1(
  uuid, text, bigint, text, jsonb
) is
  'Generation-fenced verifier for reviewed denominator-only contracts through ordinal 24. English contracts require the exact live TCGdex catalog, except the two exact source-native Puerto Rico product identities; explicit non-English or undetermined-language (`und`) contracts require a bounded source-native set name and official set URL. It cannot publish a numerator or inference.';

-- Seed the five manually verified coverage facts immediately. Hash every exact
-- retained excerpt inside PostgreSQL before accepting the observation.
do $migration$
declare
  reviewed record;
  policy_id uuid;
  computed_sha256 text;
begin
  for reviewed in
    select *
    from (
      values
      (
        'cofre-lab-chilling-reign-cr-4-v1'::text,
        'public_study_cofre_lab_chilling_reign_cr_4'::text,
        'Cofre Lab Chilling Reign 4-pack coverage'::text,
        'https://www.youtube.com/watch?v=15eGmqByP0I'::text,
        'UCqYl3y-wsJqvwow5_tIa22A'::text,
        'CR'::text,
        'Costa Rica'::text,
        '2021-06-06T05:54:03Z'::timestamptz,
        4::integer,
        'swsh6'::text,
        'build_and_battle'::text,
        'public-study-cofre-lab-chilling-reign-youtube-v1'::text,
        'cofre-lab-chilling-reign-evidence-v1'::text,
        '8b307620e562e591d30922b077bb65960a50fd0be272e6c844c4233e536fc167'::text,
        E'Unboxing Pre Release *Chilling Reign- *Reinado Escalofriante #pokemon tcg\nEl día de hoy estaremos haciendo Unboxing del Pre Release de *Chilling Reign* o *Reinado Escalofriente* · official Build & Battle Box = 4 packs'::text
      ),
      (
        'pokeyabros-perfect-order-co-2-v1',
        'public_study_pokeyabros_perfect_order_co_2',
        'Pokeyabros Perfect Order 2-pack coverage',
        'https://www.youtube.com/watch?v=n_PdWg27x-o',
        'UC6iMHQS7wp-WVH_pD4leBZw',
        'CO',
        'Colombia',
        '2026-09-04T14:00:23Z'::timestamptz,
        2,
        'me03',
        'all',
        'public-study-pokeyabros-perfect-order-youtube-v1',
        'pokeyabros-perfect-order-evidence-v1',
        '0414e5fcd9d3708873ed5c84e78f9c523fb66ba7a30211d8f798c12c5533b7f8',
        E'🎁¿PREMIO O FRACASO? #579 BOOSTER PACK OPENING PERFECT ORDER\n🎁 ¡Abrimos dos boosters de Pokémon TCG! 🎴'
      ),
      (
        'andree-insane-cards-cosmic-eclipse-ec-20-v1',
        'public_study_andree_insane_cards_cosmic_eclipse_ec_20',
        'Andree Insane Cards Cosmic Eclipse 20-pack coverage',
        'https://www.youtube.com/watch?v=wDDCbJKFTCw',
        'UCvg1acSdKlzcCXAQQKcMvqg',
        'EC',
        'Ecuador',
        '2023-06-27T21:00:07Z'::timestamptz,
        20,
        'sm12',
        'all',
        'public-study-andree-insane-cards-cosmic-eclipse-youtube-v1',
        'andree-insane-cards-cosmic-eclipse-evidence-v1',
        '9ebb6592d57fc2b452bbbd00b71e4e69633eec0a389069b1e475f4489a8fb0e9',
        E'🔥 Buscando a #Charizard Ep6: Abriendo 20 #CosmicEclipse Booster Packs LA MEJOR APERTURA DE YOUTUBE!\nEn esta oprtunidad vamos a darle con 20 de boosters de #CosmicEclipse'
      ),
      (
        'thekeiplay-lost-origin-pe-36-v1',
        'public_study_thekeiplay_lost_origin_pe_36',
        'TheKeiPlay Lost Origin 36-pack coverage',
        'https://www.youtube.com/watch?v=YKHGiYIhsQU',
        'UChAro6QS0gP88qhgOTBnuSA',
        'PE',
        'Peru',
        '2022-09-05T18:00:12Z'::timestamptz,
        36,
        'swsh11',
        'booster_box',
        'public-study-thekeiplay-lost-origin-youtube-v1',
        'thekeiplay-lost-origin-evidence-v1',
        '4c7a43da824a182cf0a550e46e21c34f1caadca259ff99d6485819ae95dd04ee',
        E'MEGA Apertura!!!😱 Booster Box 💥LOST ORIGIN (Origen Perdido)\nApertura Completa de una Booster Box deel set de Lost Origin. · official display = 36 packs'
      ),
      (
        'gringo-gameplays-silver-tempest-uy-36-v1',
        'public_study_gringo_gameplays_silver_tempest_uy_36',
        'Gringo-GamePlays Silver Tempest 36-pack coverage',
        'https://www.youtube.com/watch?v=lYzM0jtPLKw',
        'UCqxdkBJE9jPp0JEv6eA7riQ',
        'UY',
        'Uruguay',
        '2023-03-30T17:14:02Z'::timestamptz,
        36,
        'swsh12',
        'booster_box',
        'public-study-gringo-gameplays-silver-tempest-youtube-v1',
        'gringo-gameplays-silver-tempest-evidence-v1',
        '5f65c8f1ceca00fe06f56dbf684c50f1ca4116ce084aa9fbd4ead930b19d7264',
        E'TCG Pokémon Uruguay  Unboxing  Booster BOX Silver Tempest + Codigos TCG Live\nBooster BOX Silver Tempest · official display = 36 packs'
      )
    ) as rows(
      study_key,
      source_key,
      display_name,
      source_url,
      publisher_channel_id,
      country_code,
      country_name,
      observed_at,
      pack_count,
      set_external_id,
      product_scope,
      collector_version,
      parser_version,
      evidence_sha256,
      evidence_excerpt
    )
  loop
    computed_sha256 := encode(
      extensions.digest(convert_to(reviewed.evidence_excerpt, 'UTF8'), 'sha256'),
      'hex'
    );
    if computed_sha256 <> reviewed.evidence_sha256 then
      raise exception using
        errcode = '55000',
        message = format('%s evidence hash does not match the immutable excerpt', reviewed.study_key);
    end if;

    select policies.id
    into policy_id
    from ingest.source_policies as policies
    where policies.source_key = reviewed.source_key
      and policies.display_name = reviewed.display_name
      and policies.domain = 'www.youtube.com'
      and policies.base_url = reviewed.source_url
      and policies.version = reviewed.collector_version
      and policies.config ->> 'study_key' = reviewed.study_key
      and policies.config ->> 'publisher_channel_id' = reviewed.publisher_channel_id
      and policies.config ->> 'country_code' = reviewed.country_code
      and policies.config ->> 'set_external_id' = reviewed.set_external_id
      and policies.config ->> 'set_language' = 'und'
      and policies.config ->> 'set_language_basis' = 'source_does_not_state_card_language'
      and policies.config ->> 'product_scope' = reviewed.product_scope
      and policies.config ->> 'pack_count' = reviewed.pack_count::text
      and policies.config ->> 'observed_at' = to_char(
        reviewed.observed_at at time zone 'UTC',
        'YYYY-MM-DD"T"HH24:MI:SS"Z"'
      )
      and not (policies.config ? 'qualifying_hit_pack_count')
      and not (policies.config ? 'qualifying_metric')
      and not (policies.config ? 'metric_version')
      and policies.enabled
      and policies.statistics_eligible_default
      and not policies.is_demo;

    if policy_id is null then
      raise exception using
        errcode = '55000',
        message = format('%s reviewed source policy is unavailable or drifted', reviewed.study_key);
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
    ) values (
      reviewed.study_key,
      policy_id,
      reviewed.country_code,
      reviewed.country_name,
      reviewed.observed_at,
      reviewed.pack_count,
      reviewed.set_external_id,
      reviewed.product_scope,
      reviewed.collector_version,
      reviewed.parser_version,
      reviewed.collector_version,
      reviewed.evidence_sha256,
      statement_timestamp(),
      statement_timestamp(),
      false
    );
  end loop;
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
        'pokemaniaco-lucas-phantasmal-flames-cl-36-v1',
        'cofre-lab-chilling-reign-cr-4-v1',
        'pokeyabros-perfect-order-co-2-v1',
        'andree-insane-cards-cosmic-eclipse-ec-20-v1',
        'thekeiplay-lost-origin-pe-36-v1',
        'gringo-gameplays-silver-tempest-uy-36-v1'
      )
    )
  );

commit;
