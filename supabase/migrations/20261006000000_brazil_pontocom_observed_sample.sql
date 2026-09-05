begin;

-- Brazil's reviewed product is a four-pack blister. Keep the statistical
-- ledger vocabulary exact instead of coercing it to booster_bundle.
alter table ingest.public_study_observations
  drop constraint public_study_observations_product_check;
alter table ingest.public_study_observations
  add constraint public_study_observations_product_check check (
    product_scope in ('all', 'booster_box', 'etb', 'booster_bundle', 'four_pack_blister')
  );

alter table ingest.public_study_coverage_observations
  drop constraint public_study_coverage_product_check;
alter table ingest.public_study_coverage_observations
  add constraint public_study_coverage_product_check check (
    product_scope in (
      'all', 'booster_box', 'etb', 'booster_bundle', 'value_bundle', 'four_pack_blister'
    )
  );

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
  'public_study_pontocom_br_48',
  'PontoCOM Heróis Excelsos Brazil 48-pack study',
  'public_web',
  'pontocomdesenvolvimento.net',
  'https://pontocomdesenvolvimento.net/postagem/1028/herois-excelsos-vale-a-pena-abrir-uma-case-lacrada',
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
    "study_key":"pontocom-herois-excelsos-br-48-v1",
    "canonical_url":"https://pontocomdesenvolvimento.net/postagem/1028/herois-excelsos-vale-a-pena-abrir-uma-case-lacrada",
    "collector_version":"public-study-pontocom-herois-excelsos-v1",
    "parser_version":"pontocom-herois-excelsos-evidence-v1",
    "country_code":"BR",
    "country_name":"Brazil",
    "geography_basis":"publisher_country",
    "geography_confidence":"tier_b",
    "set_external_id":"me02.5",
    "set_language":"pt-BR",
    "set_name":"Heróis Excelsos",
    "set_official_url":"https://www.pokemon.com/br/pokemon-estampas-ilustradas/cartas-de-pokemon/series/me2pt5/",
    "product_scope":"four_pack_blister",
    "product_name":"Blister Quádruplo",
    "source_native_product":"12 Blisters Quadruplos",
    "pack_count":48,
    "denominator_derivation":"12×4",
    "qualifying_hit_pack_count":1,
    "qualifying_metric":"sir_pack",
    "metric_version":"global-sir-v1",
    "source_published_at":"2026-01-26T20:29:00-03:00",
    "observed_at":"2026-01-26T23:29:00Z",
    "denominator_complete":true,
    "video_url":"https://www.youtube.com/watch?v=idfg-A54S1k",
    "video_id":"idfg-A54S1k",
    "video_embed_url":"https://www.youtube.com/embed/idfg-A54S1k",
    "video_review_method":"manual_timestamped_video_review",
    "video_reviewed_at":"2026-09-05",
    "video_review_timestamps":[
      {"at":"00:07","finding":"12 Blisters Quadruplos"},
      {"at":"02:34-02:58","card_name":"Mega Meganium ex","card_number":"272/217","normalized_rarity":"SIR"},
      {"at":"16:49-16:56","card_name":"Mawile","card_number":"246/217","normalized_rarity":"IR"},
      {"at":"19:49-20:08","card_name":"Heliolisk","card_number":"229/217","normalized_rarity":"IR"},
      {"at":"22:07","finding":"manual summary of two generic art cards"}
    ],
    "card_rarity_mapping":[
      {"card_name":"Mega Meganium ex","card_number":"272/217","official_url":"https://www.pokemon.com/br/pokemon-estampas-ilustradas/cartas-de-pokemon/series/me2pt5/272/","official_rarity_en":"Special Illustration Rare","official_rarity_pt_br":"Ilustração Rara Especial","normalized_rarity":"SIR","counts_as_sir":true},
      {"card_name":"Mawile","card_number":"246/217","official_url":"https://www.pokemon.com/br/pokemon-estampas-ilustradas/cartas-de-pokemon/series/me2pt5/246/","official_rarity_en":"Illustration Rare","official_rarity_pt_br":"Ilustração Rara","normalized_rarity":"IR","counts_as_sir":false},
      {"card_name":"Heliolisk","card_number":"229/217","official_url":"https://www.pokemon.com/br/pokemon-estampas-ilustradas/cartas-de-pokemon/series/me2pt5/229/","official_rarity_en":"Illustration Rare","official_rarity_pt_br":"Ilustração Rara","normalized_rarity":"IR","counts_as_sir":false}
    ],
    "robots_url":"https://pontocomdesenvolvimento.net/robots.txt",
    "robots_checked_at":"2026-09-05",
    "robots_status":"404_not_found_live_collection_blocked",
    "terms_checked_at":"2026-09-05",
    "terms_status":"publisher_terms_not_found_in_review",
    "rights_scope":"minimal_noncreative_facts_no_media_or_body_reuse"
  }'::jsonb,
  'public-study-pontocom-herois-excelsos-v1',
  86400,
  false
);

insert into ingest.source_request_gates (source_key)
values ('public_study_pontocom_br_48');

create or replace function ingest.reviewed_public_study_gates_ready_v1()
returns boolean
language sql
stable
security definer
parallel safe
set search_path = pg_catalog
as $$
  select count(*) = 10
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
    'public_study_pontocom_br_48'
  );
$$;

alter function ingest.reviewed_public_study_gates_ready_v1() owner to postgres;
revoke all on function ingest.reviewed_public_study_gates_ready_v1()
  from public, anon, authenticated, service_role;
grant execute on function ingest.reviewed_public_study_gates_ready_v1()
  to service_role;
comment on function ingest.reviewed_public_study_gates_ready_v1() is
  'Boolean-only readiness check for all exact reviewed public-study request gates; it exposes no gate identity or lease state.';

-- Append the reviewed Brazil contract after the Asia phase-one ordinal-9
-- suffix. This keeps the public registry immutable and ordered.
do $migration$
declare
  definition text;
  updated_definition text;
  old_suffix text := $old$
      array['รีวิว การ์ดโปเกมอน', 'วิวัฒนาการดรีมex', 'เติมเด็คให้แข็งแกร่ง']::text[]
    );$old$;
  new_suffix text := $new$
      array['รีวิว การ์ดโปเกมอน', 'วิวัฒนาการดรีมex', 'เติมเด็คให้แข็งแกร่ง']::text[]
    ),
    (
      10,
      'pontocom-herois-excelsos-br-48-v1'::text,
      'public_study_pontocom_br_48'::text,
      'pontocom_herois_excelsos_study'::text,
      'PontoCOM Heróis Excelsos study'::text,
      'Reviewed Brazil public study: 48 packs from 12 four-pack blisters and exactly 1 normalized SIR (Mega Meganium ex 272/217); Mawile 246/217 and Heliolisk 229/217 are official Illustration Rare only. Public v3 observed sample is 1/48. Attribution is to the publisher/product market, not a physical opening location; card rarity mapping is grounded in the official Brazil catalog and the result is a manual timestamped video review.'::text,
      'PontoCOM Heróis Excelsos Brazil 48-pack study'::text,
      'pontocomdesenvolvimento.net'::text,
      'https://pontocomdesenvolvimento.net/postagem/1028/herois-excelsos-vale-a-pena-abrir-uma-case-lacrada'::text,
      'public-study-pontocom-herois-excelsos-v1'::text,
      '{
        "study_key":"pontocom-herois-excelsos-br-48-v1",
        "canonical_url":"https://pontocomdesenvolvimento.net/postagem/1028/herois-excelsos-vale-a-pena-abrir-uma-case-lacrada",
        "collector_version":"public-study-pontocom-herois-excelsos-v1",
        "parser_version":"pontocom-herois-excelsos-evidence-v1",
        "country_code":"BR",
        "country_name":"Brazil",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "set_external_id":"me02.5",
        "set_language":"pt-BR",
        "set_name":"Heróis Excelsos",
        "set_official_url":"https://www.pokemon.com/br/pokemon-estampas-ilustradas/cartas-de-pokemon/series/me2pt5/",
        "product_scope":"four_pack_blister",
        "product_name":"Blister Quádruplo",
        "source_native_product":"12 Blisters Quadruplos",
        "pack_count":48,
        "denominator_derivation":"12×4",
        "qualifying_hit_pack_count":1,
        "qualifying_metric":"sir_pack",
        "metric_version":"global-sir-v1",
        "source_published_at":"2026-01-26T20:29:00-03:00",
        "observed_at":"2026-01-26T23:29:00Z",
        "denominator_complete":true,
        "video_url":"https://www.youtube.com/watch?v=idfg-A54S1k",
        "video_id":"idfg-A54S1k",
        "video_embed_url":"https://www.youtube.com/embed/idfg-A54S1k",
        "video_review_method":"manual_timestamped_video_review",
        "video_reviewed_at":"2026-09-05",
        "video_review_timestamps":[
          {"at":"00:07","finding":"12 Blisters Quadruplos"},
          {"at":"02:34-02:58","card_name":"Mega Meganium ex","card_number":"272/217","normalized_rarity":"SIR"},
          {"at":"16:49-16:56","card_name":"Mawile","card_number":"246/217","normalized_rarity":"IR"},
          {"at":"19:49-20:08","card_name":"Heliolisk","card_number":"229/217","normalized_rarity":"IR"},
          {"at":"22:07","finding":"manual summary of two generic art cards"}
        ],
        "card_rarity_mapping":[
          {"card_name":"Mega Meganium ex","card_number":"272/217","official_url":"https://www.pokemon.com/br/pokemon-estampas-ilustradas/cartas-de-pokemon/series/me2pt5/272/","official_rarity_en":"Special Illustration Rare","official_rarity_pt_br":"Ilustração Rara Especial","normalized_rarity":"SIR","counts_as_sir":true},
          {"card_name":"Mawile","card_number":"246/217","official_url":"https://www.pokemon.com/br/pokemon-estampas-ilustradas/cartas-de-pokemon/series/me2pt5/246/","official_rarity_en":"Illustration Rare","official_rarity_pt_br":"Ilustração Rara","normalized_rarity":"IR","counts_as_sir":false},
          {"card_name":"Heliolisk","card_number":"229/217","official_url":"https://www.pokemon.com/br/pokemon-estampas-ilustradas/cartas-de-pokemon/series/me2pt5/229/","official_rarity_en":"Illustration Rare","official_rarity_pt_br":"Ilustração Rara","normalized_rarity":"IR","counts_as_sir":false}
        ],
        "robots_url":"https://pontocomdesenvolvimento.net/robots.txt",
        "robots_checked_at":"2026-09-05",
        "robots_status":"404_not_found_live_collection_blocked",
        "terms_checked_at":"2026-09-05",
        "terms_status":"publisher_terms_not_found_in_review",
        "rights_scope":"minimal_noncreative_facts_no_media_or_body_reuse"
      }'::jsonb,
      'ABRI uma CASE com 12 Blisters Quadruplos de Pokémon TCG – Heróis Excelsos ANTES DO LANÇAMENTO OFICIAL!'::text,
      array['Heróis Excelsos: Vale a Pena ABRIR Uma CASE LACRADA?']::text[]
    );$new$;
begin
  select pg_get_functiondef('ingest.reviewed_public_study_contracts()'::regprocedure)
    into definition;
  if definition is null
    or position(old_suffix in definition) = 0
    or position('pontocom-herois-excelsos-br-48-v1' in definition) > 0
    or (select count(*) from ingest.reviewed_public_study_contracts()) <> 9
  then
    raise exception using errcode = '55000',
      message = 'reviewed public-study registry is not the expected ordinal-9 definition';
  end if;
  updated_definition := replace(definition, old_suffix, new_suffix);
  if updated_definition = definition then
    raise exception using errcode = '55000',
      message = 'Brazil reviewed public-study registry extension was not applied';
  end if;
  execute updated_definition;
end;
$migration$;

alter function ingest.reviewed_public_study_contracts() owner to postgres;
revoke all on function ingest.reviewed_public_study_contracts()
  from public, anon, authenticated, service_role;
comment on function ingest.reviewed_public_study_contracts() is
  'Owner-only immutable reviewed-study facts. Includes private historical facts and exact bounded coverage evidence; never grant this function to API or worker roles.';

-- The article's robots.txt endpoint returned 404 at review time, so the live
-- collector correctly remains fail-closed. Record the already completed
-- timestamped human review in the denominator-only ledger instead of
-- pretending that a network collection succeeded. The numerator remains only
-- in the immutable reviewed contract above; public v3 may expose its direct
-- 1/48 arithmetic, but no inferential statistic is created here.
do $migration$
declare
  policy_id uuid;
  verification_time timestamptz := statement_timestamp();
  evidence_hash text := '4788f28b2e61c0b1879d287da82e4c45712ba7ba0a84cb1599c32611e1968da6';
begin
  if evidence_hash <> encode(
    extensions.digest(
      convert_to(
        'ABRI uma CASE com 12 Blisters Quadruplos de Pokémon TCG – Heróis Excelsos ANTES DO LANÇAMENTO OFICIAL!',
        'UTF8'
      ),
      'sha256'
    ),
    'hex'
  ) then
    raise exception using errcode = '55000',
      message = 'Brazil reviewed evidence hash does not match the immutable excerpt';
  end if;

  select policies.id
  into policy_id
  from ingest.source_policies as policies
  where policies.source_key = 'public_study_pontocom_br_48'
    and policies.display_name = 'PontoCOM Heróis Excelsos Brazil 48-pack study'
    and policies.domain = 'pontocomdesenvolvimento.net'
    and policies.base_url = 'https://pontocomdesenvolvimento.net/postagem/1028/herois-excelsos-vale-a-pena-abrir-uma-case-lacrada'
    and policies.version = 'public-study-pontocom-herois-excelsos-v1'
    and policies.config ->> 'study_key' = 'pontocom-herois-excelsos-br-48-v1'
    and policies.config ->> 'video_review_method' = 'manual_timestamped_video_review'
    and policies.config ->> 'video_reviewed_at' = '2026-09-05'
    and policies.config ->> 'qualifying_metric' = 'sir_pack'
    and policies.config ->> 'metric_version' = 'global-sir-v1'
    and policies.config ->> 'qualifying_hit_pack_count' = '1'
    and policies.enabled
    and policies.statistics_eligible_default
    and not policies.is_demo;

  if policy_id is null then
    raise exception using errcode = '55000',
      message = 'Brazil reviewed source policy is unavailable or drifted';
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
    'pontocom-herois-excelsos-br-48-v1',
    policy_id,
    'BR',
    'Brazil',
    '2026-01-26T23:29:00Z'::timestamptz,
    48,
    'me02.5',
    'four_pack_blister',
    'public-study-pontocom-herois-excelsos-v1',
    'pontocom-herois-excelsos-evidence-v1',
    'public-study-pontocom-herois-excelsos-v1',
    evidence_hash,
    verification_time,
    verification_time,
    false
  );
end;
$migration$;

-- Keep the full latest scheduled-job boundary (including Bluesky, Nostr, and
-- Mastodon) while adding only the exact Brazil study identity.
alter table ingest.jobs
  drop constraint jobs_live_scheduled_enqueue_allowlist_check;
alter table ingest.jobs
  add constraint jobs_live_scheduled_enqueue_allowlist_check
  check (
    is_demo
    or dedupe_key is null
    or dedupe_key !~ '^schedule:'
    or (
      job_type in (
        'catalog.tcgdex.sets.sync',
        'maintenance.cleanup',
        'source.bluesky.jetstream'
      )
      and payload = '{}'::jsonb
    )
    or (
      job_type = 'source.nostr.relay'
      and payload ?& array['relay_key']
      and payload - array['relay_key'] = '{}'::jsonb
      and jsonb_typeof(payload -> 'relay_key') = 'string'
      and payload ->> 'relay_key' in ('primal', 'nos_lol', 'nostr_net')
    )
    or (
      job_type = 'source.youtube.discovery'
      and payload ?& array['query_name']
      and payload - array['query_name'] = '{}'::jsonb
      and jsonb_typeof(payload -> 'query_name') = 'string'
      and payload ->> 'query_name' in (
        'pokemon-tcg-booster-box-opening',
        'pokemon-tcg-etb-opening',
        'pokemon-tcg-booster-bundle-opening',
        'pokemon-tcg-pack-opening',
        'pokemon-tcg-opening-batch-code'
      )
    )
    or (
      job_type = 'source.public_study.opening'
      and payload ?& array['study_key']
      and payload - array['study_key'] = '{}'::jsonb
      and jsonb_typeof(payload -> 'study_key') = 'string'
      and payload ->> 'study_key' in (
        'comicbook-perfect-order-us-55-v1',
        'wargamer-chaos-rising-gb-17-v1',
        'pontocom-herois-excelsos-br-48-v1'
      )
    )
    or (
      job_type = 'source.mastodon.public_hashtag'
      and payload ?& array['instance_key', 'tag_key']
      and payload - array['instance_key', 'tag_key'] = '{}'::jsonb
      and jsonb_typeof(payload -> 'instance_key') = 'string'
      and jsonb_typeof(payload -> 'tag_key') = 'string'
      and payload ->> 'instance_key' = 'mastodon_social'
      and payload ->> 'tag_key' in (
        'pokemontcg', 'pokemoncards', 'pokeca_ja', 'pokemon_card_ja',
        'pokemon_card_ko', 'pokemon_card_zh_hans', 'pokemon_card_zh_hant'
      )
    )
  );

-- Extend the two public-study enqueue allowlists and their source-key binding.
do $migration$
declare
  function_oid regprocedure;
  definition text;
  updated_definition text;
  old_allowlist text := $old$
        'comicbook-perfect-order-us-55-v1',
        'wargamer-chaos-rising-gb-17-v1'
  $old$;
  new_allowlist text := $new$
        'comicbook-perfect-order-us-55-v1',
        'wargamer-chaos-rising-gb-17-v1',
        'pontocom-herois-excelsos-br-48-v1'
  $new$;
  old_case text := $oldcase$
          when 'comicbook-perfect-order-us-55-v1'
            then 'public_study_comicbook_us_55'
          else 'public_study_wargamer_gb_17'
  $oldcase$;
  new_case text := $newcase$
          when 'comicbook-perfect-order-us-55-v1'
            then 'public_study_comicbook_us_55'
          when 'pontocom-herois-excelsos-br-48-v1'
            then 'public_study_pontocom_br_48'
          else 'public_study_wargamer_gb_17'
  $newcase$;
begin
  foreach function_oid in array ARRAY[
    'ingest.enqueue_scheduled_job_v1(text,timestamptz,text,jsonb,integer,integer)'::regprocedure,
    'ingest.enqueue_job_v1(text,jsonb,integer,text,timestamptz,integer)'::regprocedure
  ] loop
    select pg_get_functiondef(function_oid::oid) into definition;
    if position(old_allowlist in definition) = 0
      or position(old_case in definition) = 0
    then
      raise exception using errcode = '55000',
        message = 'public-study enqueue RPC is not the expected two-source definition',
        detail = function_oid::text;
    end if;
    updated_definition := replace(definition, old_allowlist, new_allowlist);
    updated_definition := replace(updated_definition, old_case, new_case);
    execute updated_definition;
  end loop;
end;
$migration$;

-- Extend begin/finalize with the exact Brazil policy/config/evidence contract.
do $migration$
declare
  function_oid regprocedure;
  definition text;
  updated_definition text;
  old_allowlist text := $old$
      'comicbook-perfect-order-us-55-v1',
      'wargamer-chaos-rising-gb-17-v1'
  $old$;
  new_allowlist text := $new$
      'comicbook-perfect-order-us-55-v1',
      'wargamer-chaos-rising-gb-17-v1',
      'pontocom-herois-excelsos-br-48-v1'
  $new$;
  old_branch text := $oldbranch$
  else
    policy_key := 'public_study_wargamer_gb_17';
  $oldbranch$;
  begin_branch text := $beginbranch$
  elsif requested_study_key = 'pontocom-herois-excelsos-br-48-v1' then
    policy_key := 'public_study_pontocom_br_48';
    expected_domain := 'pontocomdesenvolvimento.net';
    expected_url := 'https://pontocomdesenvolvimento.net/postagem/1028/herois-excelsos-vale-a-pena-abrir-uma-case-lacrada';
    expected_display_name := 'PontoCOM Heróis Excelsos Brazil 48-pack study';
    expected_version := 'public-study-pontocom-herois-excelsos-v1';
    expected_config := $json$
    {
      "study_key":"pontocom-herois-excelsos-br-48-v1",
      "canonical_url":"https://pontocomdesenvolvimento.net/postagem/1028/herois-excelsos-vale-a-pena-abrir-uma-case-lacrada",
      "collector_version":"public-study-pontocom-herois-excelsos-v1",
      "parser_version":"pontocom-herois-excelsos-evidence-v1",
      "country_code":"BR","country_name":"Brazil","geography_basis":"publisher_country","geography_confidence":"tier_b",
      "set_external_id":"me02.5","set_language":"pt-BR","set_name":"Heróis Excelsos",
      "set_official_url":"https://www.pokemon.com/br/pokemon-estampas-ilustradas/cartas-de-pokemon/series/me2pt5/",
      "product_scope":"four_pack_blister","product_name":"Blister Quádruplo","source_native_product":"12 Blisters Quadruplos",
      "pack_count":48,"denominator_derivation":"12×4","qualifying_hit_pack_count":1,"qualifying_metric":"sir_pack","metric_version":"global-sir-v1",
      "source_published_at":"2026-01-26T20:29:00-03:00","observed_at":"2026-01-26T23:29:00Z","denominator_complete":true,
      "video_url":"https://www.youtube.com/watch?v=idfg-A54S1k","video_id":"idfg-A54S1k","video_embed_url":"https://www.youtube.com/embed/idfg-A54S1k",
      "video_review_method":"manual_timestamped_video_review","video_reviewed_at":"2026-09-05",
      "video_review_timestamps":[{"at":"00:07","finding":"12 Blisters Quadruplos"},{"at":"02:34-02:58","card_name":"Mega Meganium ex","card_number":"272/217","normalized_rarity":"SIR"},{"at":"16:49-16:56","card_name":"Mawile","card_number":"246/217","normalized_rarity":"IR"},{"at":"19:49-20:08","card_name":"Heliolisk","card_number":"229/217","normalized_rarity":"IR"},{"at":"22:07","finding":"manual summary of two generic art cards"}],
      "card_rarity_mapping":[{"card_name":"Mega Meganium ex","card_number":"272/217","official_url":"https://www.pokemon.com/br/pokemon-estampas-ilustradas/cartas-de-pokemon/series/me2pt5/272/","official_rarity_en":"Special Illustration Rare","official_rarity_pt_br":"Ilustração Rara Especial","normalized_rarity":"SIR","counts_as_sir":true},{"card_name":"Mawile","card_number":"246/217","official_url":"https://www.pokemon.com/br/pokemon-estampas-ilustradas/cartas-de-pokemon/series/me2pt5/246/","official_rarity_en":"Illustration Rare","official_rarity_pt_br":"Ilustração Rara","normalized_rarity":"IR","counts_as_sir":false},{"card_name":"Heliolisk","card_number":"229/217","official_url":"https://www.pokemon.com/br/pokemon-estampas-ilustradas/cartas-de-pokemon/series/me2pt5/229/","official_rarity_en":"Illustration Rare","official_rarity_pt_br":"Ilustração Rara","normalized_rarity":"IR","counts_as_sir":false}],
      "robots_url":"https://pontocomdesenvolvimento.net/robots.txt","robots_checked_at":"2026-09-05","robots_status":"404_not_found_live_collection_blocked","terms_checked_at":"2026-09-05","terms_status":"publisher_terms_not_found_in_review","rights_scope":"minimal_noncreative_facts_no_media_or_body_reuse"
    }
    $json$::jsonb;
  else
    policy_key := 'public_study_wargamer_gb_17';
  $beginbranch$;
  finalize_branch text := $finalbranch$
  elsif requested_study_key = 'pontocom-herois-excelsos-br-48-v1' then
    policy_key := 'public_study_pontocom_br_48';
    expected_domain := 'pontocomdesenvolvimento.net';
    expected_url := 'https://pontocomdesenvolvimento.net/postagem/1028/herois-excelsos-vale-a-pena-abrir-uma-case-lacrada';
    expected_display_name := 'PontoCOM Heróis Excelsos Brazil 48-pack study';
    expected_version := 'public-study-pontocom-herois-excelsos-v1';
    expected_evidence := E'ABRI uma CASE com 12 Blisters Quadruplos de Pokémon TCG – Heróis Excelsos ANTES DO LANÇAMENTO OFICIAL!';
    expected_config := $json$
    {
      "study_key":"pontocom-herois-excelsos-br-48-v1","canonical_url":"https://pontocomdesenvolvimento.net/postagem/1028/herois-excelsos-vale-a-pena-abrir-uma-case-lacrada","collector_version":"public-study-pontocom-herois-excelsos-v1","parser_version":"pontocom-herois-excelsos-evidence-v1","country_code":"BR","country_name":"Brazil","geography_basis":"publisher_country","geography_confidence":"tier_b","set_external_id":"me02.5","set_language":"pt-BR","set_name":"Heróis Excelsos","set_official_url":"https://www.pokemon.com/br/pokemon-estampas-ilustradas/cartas-de-pokemon/series/me2pt5/","product_scope":"four_pack_blister","product_name":"Blister Quádruplo","source_native_product":"12 Blisters Quadruplos","pack_count":48,"denominator_derivation":"12×4","qualifying_hit_pack_count":1,"qualifying_metric":"sir_pack","metric_version":"global-sir-v1","source_published_at":"2026-01-26T20:29:00-03:00","observed_at":"2026-01-26T23:29:00Z","denominator_complete":true,"video_url":"https://www.youtube.com/watch?v=idfg-A54S1k","video_id":"idfg-A54S1k","video_embed_url":"https://www.youtube.com/embed/idfg-A54S1k","video_review_method":"manual_timestamped_video_review","video_reviewed_at":"2026-09-05","video_review_timestamps":[{"at":"00:07","finding":"12 Blisters Quadruplos"},{"at":"02:34-02:58","card_name":"Mega Meganium ex","card_number":"272/217","normalized_rarity":"SIR"},{"at":"16:49-16:56","card_name":"Mawile","card_number":"246/217","normalized_rarity":"IR"},{"at":"19:49-20:08","card_name":"Heliolisk","card_number":"229/217","normalized_rarity":"IR"},{"at":"22:07","finding":"manual summary of two generic art cards"}],"card_rarity_mapping":[{"card_name":"Mega Meganium ex","card_number":"272/217","official_url":"https://www.pokemon.com/br/pokemon-estampas-ilustradas/cartas-de-pokemon/series/me2pt5/272/","official_rarity_en":"Special Illustration Rare","official_rarity_pt_br":"Ilustração Rara Especial","normalized_rarity":"SIR","counts_as_sir":true},{"card_name":"Mawile","card_number":"246/217","official_url":"https://www.pokemon.com/br/pokemon-estampas-ilustradas/cartas-de-pokemon/series/me2pt5/246/","official_rarity_en":"Illustration Rare","official_rarity_pt_br":"Ilustração Rara","normalized_rarity":"IR","counts_as_sir":false},{"card_name":"Heliolisk","card_number":"229/217","official_url":"https://www.pokemon.com/br/pokemon-estampas-ilustradas/cartas-de-pokemon/series/me2pt5/229/","official_rarity_en":"Illustration Rare","official_rarity_pt_br":"Ilustração Rara","normalized_rarity":"IR","counts_as_sir":false}],"robots_url":"https://pontocomdesenvolvimento.net/robots.txt","robots_checked_at":"2026-09-05","robots_status":"404_not_found_live_collection_blocked","terms_checked_at":"2026-09-05","terms_status":"publisher_terms_not_found_in_review","rights_scope":"minimal_noncreative_facts_no_media_or_body_reuse"
    }
    $json$::jsonb;
  else
    policy_key := 'public_study_wargamer_gb_17';
  $finalbranch$;
begin
  foreach function_oid in array ARRAY[
    'ingest.begin_public_study_job(uuid,text,bigint)'::regprocedure,
    'ingest.finalize_public_study_job(uuid,text,bigint,jsonb)'::regprocedure
  ] loop
    select pg_get_functiondef(function_oid::oid) into definition;
    if position(old_allowlist in definition) = 0
      or position(old_branch in definition) = 0
    then
      raise exception using errcode = '55000',
        message = 'public-study worker RPC is not the expected two-source definition',
        detail = function_oid::text;
    end if;
    updated_definition := replace(definition, old_allowlist, new_allowlist);
    if function_oid::text = 'ingest.begin_public_study_job(uuid,text,bigint)' then
      updated_definition := replace(updated_definition, old_branch, begin_branch);
    else
      updated_definition := replace(updated_definition, old_branch, finalize_branch);
    end if;
    execute updated_definition;
  end loop;
end;
$migration$;

-- The finalizer also pins the reviewed article title to the Brazil scope.
do $migration$
declare
  definition text;
  updated_definition text;
  old_guard text := $old$
    or (
      requested_study_key = 'wargamer-chaos-rising-gb-17-v1'
      and (
        position('opened Pokémon Chaos Rising packs early' in result_title) = 0
        or position('blessing and a curse' in result_title) = 0
      )
    )
  $old$;
  new_guard text := $new$
    or (
      requested_study_key = 'wargamer-chaos-rising-gb-17-v1'
      and (
        position('opened Pokémon Chaos Rising packs early' in result_title) = 0
        or position('blessing and a curse' in result_title) = 0
      )
    )
    or (
      requested_study_key = 'pontocom-herois-excelsos-br-48-v1'
      and (
        position('Heróis Excelsos' in result_title) = 0
        or position('ABRIR Uma CASE' in result_title) = 0
        or position('LACRADA' in result_title) = 0
      )
    )
  $new$;
begin
  select pg_get_functiondef('ingest.finalize_public_study_job(uuid,text,bigint,jsonb)'::regprocedure)
    into definition;
  if position(old_guard in definition) = 0 then
    raise exception using errcode = '55000',
      message = 'public-study finalizer title guard is not the expected definition';
  end if;
  updated_definition := replace(definition, old_guard, new_guard);
  execute updated_definition;
end;
$migration$;

alter function ingest.begin_public_study_job(uuid, text, bigint) owner to postgres;
revoke all on function ingest.begin_public_study_job(uuid, text, bigint)
  from public, anon, authenticated, service_role;
grant execute on function ingest.begin_public_study_job(uuid, text, bigint)
  to service_role;
alter function ingest.finalize_public_study_job(uuid, text, bigint, jsonb) owner to postgres;
revoke all on function ingest.finalize_public_study_job(uuid, text, bigint, jsonb)
  from public, anon, authenticated, service_role;
grant execute on function ingest.finalize_public_study_job(uuid, text, bigint, jsonb)
  to service_role;

commit;
