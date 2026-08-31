begin;

-- This is a denominator-only, publisher-country study. The private policy
-- retains the reviewed numerator so the fenced verifier can reject drift, but
-- the public projection below never exposes it or derives a rate.
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
  'public_study_tcgtalk_sg_54',
  'tcgTalk Perfect Order 54-pack study',
  'public_web',
  'tcgtalk.com',
  'https://tcgtalk.com/blog/perfect-order-pull-rates-what-singapore-collectors-can-expect-1774442400232',
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
    "study_key":"tcgtalk-perfect-order-sg-54-v1",
    "canonical_url":"https://tcgtalk.com/blog/perfect-order-pull-rates-what-singapore-collectors-can-expect-1774442400232",
    "collector_version":"public-study-tcgtalk-perfect-order-v1",
    "parser_version":"tcgtalk-perfect-order-evidence-v1",
    "country_code":"SG",
    "country_name":"Singapore",
    "geography_basis":"publisher_country",
    "geography_confidence":"tier_b",
    "set_external_id":"me03",
    "product_scope":"booster_bundle",
    "pack_count":54,
    "qualifying_hit_pack_count":1,
    "qualifying_metric":"sir_pack",
    "metric_version":"global-sir-v1",
    "observed_at":"2026-03-25T12:40:00Z",
    "denominator_complete":true
  }'::jsonb,
  'public-study-tcgtalk-perfect-order-v1',
  86400,
  false
);

insert into ingest.source_request_gates (source_key)
values ('public_study_tcgtalk_sg_54');

-- Keep ordinals 1-4 immutable and append Singapore as ordinal 5. This
-- owner-only helper is shared by every fenced coverage boundary and the
-- browser projection, so the private evidence facts cannot drift between
-- queue admission, persistence, and public output.
create or replace function ingest.reviewed_public_study_contracts()
returns table(
  ordinal integer,
  study_key text,
  policy_key text,
  public_id text,
  public_name text,
  public_note text,
  display_name text,
  domain text,
  canonical_url text,
  policy_version text,
  config jsonb,
  evidence_excerpt text,
  title_fragments text[]
)
language sql
immutable
security invoker
parallel safe
set search_path = pg_catalog
as $$
  values
    (
      1,
      'comicbook-perfect-order-us-55-v1'::text,
      'public_study_comicbook_us_55'::text,
      'comicbook_perfect_order_study'::text,
      'ComicBook Perfect Order study'::text,
      'Reviewed 55-pack public study attributed to the United States; its rate remains withheld until the independent-source threshold is met.'::text,
      'ComicBook Perfect Order 55-pack study'::text,
      'comicbook.com'::text,
      'https://comicbook.com/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates'::text,
      'public-study-comicbook-perfect-order-v1'::text,
      '{
        "study_key":"comicbook-perfect-order-us-55-v1",
        "canonical_url":"https://comicbook.com/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates",
        "collector_version":"public-study-comicbook-perfect-order-v1",
        "parser_version":"comicbook-perfect-order-evidence-v1",
        "country_code":"US",
        "country_name":"United States",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "set_external_id":"me03",
        "product_scope":"all",
        "pack_count":55,
        "qualifying_hit_pack_count":1,
        "qualifying_metric":"sir_pack",
        "metric_version":"global-sir-v1",
        "observed_at":"2026-03-19T21:00:00Z",
        "denominator_complete":true
      }'::jsonb,
      E'In total, I opened 55 boosters from the upcoming Perfect Order lineup.\n1 Special Illustration Rare'::text,
      array['Opened 55 Packs', 'Perfect Order', 'Pull Rates']::text[]
    ),
    (
      2,
      'wargamer-chaos-rising-gb-17-v1',
      'public_study_wargamer_gb_17',
      'wargamer_chaos_rising_study',
      'Wargamer Chaos Rising study',
      'Reviewed 17-pack public study attributed to the United Kingdom; its rate remains withheld until the pack and independent-source thresholds are met.',
      'Wargamer Chaos Rising 17-pack study',
      'www.wargamer.com',
      'https://www.wargamer.com/pokemon-trading-card-game/chaos-rising-preview',
      'public-study-wargamer-chaos-rising-v1',
      '{
        "study_key":"wargamer-chaos-rising-gb-17-v1",
        "canonical_url":"https://www.wargamer.com/pokemon-trading-card-game/chaos-rising-preview",
        "collector_version":"public-study-wargamer-chaos-rising-v1",
        "parser_version":"wargamer-chaos-rising-evidence-v1",
        "country_code":"GB",
        "country_name":"United Kingdom",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "set_external_id":"me04",
        "product_scope":"all",
        "pack_count":17,
        "qualifying_hit_pack_count":0,
        "qualifying_metric":"sir_pack",
        "metric_version":"global-sir-v1",
        "observed_at":"2026-05-11T00:00:00Z",
        "denominator_complete":true
      }'::jsonb,
      E'after opening the 17 Pokémon Chaos Rising packs Wargamer was sent ahead of release, my opinion remains positive on those fronts.\nmissing out on any SIR mega hits.',
      array['opened Pokémon Chaos Rising packs early', 'blessing and a curse']::text[]
    ),
    (
      3,
      'cardchill-ascended-heroes-gb-90-v1',
      'public_study_cardchill_gb_90',
      'cardchill_ascended_heroes_study',
      'CardChill Ascended Heroes study',
      'Reviewed 90-pack ETB study attributed to the United Kingdom; its rate remains withheld until the independent-source threshold is met.',
      'CardChill Ascended Heroes 90-pack study',
      'cardchill.com',
      'https://cardchill.com/article/ripping-10-ascended-heroes-etbs-is-the-mega-attack-pull-rate-real',
      'public-study-cardchill-ascended-heroes-v1',
      '{
        "study_key":"cardchill-ascended-heroes-gb-90-v1",
        "canonical_url":"https://cardchill.com/article/ripping-10-ascended-heroes-etbs-is-the-mega-attack-pull-rate-real",
        "collector_version":"public-study-cardchill-ascended-heroes-v1",
        "parser_version":"cardchill-ascended-heroes-evidence-v1",
        "country_code":"GB",
        "country_name":"United Kingdom",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "set_external_id":"me02.5",
        "product_scope":"etb",
        "pack_count":90,
        "qualifying_hit_pack_count":1,
        "qualifying_metric":"sir_pack",
        "metric_version":"global-sir-v1",
        "observed_at":"2026-03-03T11:26:21Z",
        "denominator_complete":true
      }'::jsonb,
      E'I finally sat down with a stack of 10 Ascended Heroes Elite Trainer Boxes.\nOut of 90 packs, I pulled 19 Double Rare (ex) cards.\nAcross 10 ETBs, I pulled exactly one SIR.',
      array['Ripping 10 Ascended Heroes ETBs', 'Mega Attack', 'Pull Rate Real']::text[]
    ),
    (
      4,
      'bleedingcool-phantasmal-flames-us-36-v1',
      'public_study_bleedingcool_us_36',
      'bleedingcool_phantasmal_flames_study',
      'Bleeding Cool Phantasmal Flames study',
      'Reviewed 36-pack booster-box study attributed to the United States; its rate remains withheld until the independent-source threshold is met.',
      'Bleeding Cool Phantasmal Flames 36-pack study',
      'bleedingcool.com',
      'https://bleedingcool.com/games/opening-pokemon-tcg-mega-evolution-phantasmal-flames-products',
      'public-study-bleedingcool-phantasmal-flames-v1',
      '{
        "study_key":"bleedingcool-phantasmal-flames-us-36-v1",
        "canonical_url":"https://bleedingcool.com/games/opening-pokemon-tcg-mega-evolution-phantasmal-flames-products",
        "collector_version":"public-study-bleedingcool-phantasmal-flames-v1",
        "parser_version":"bleedingcool-phantasmal-flames-evidence-v1",
        "country_code":"US",
        "country_name":"United States",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "set_external_id":"me02",
        "product_scope":"booster_box",
        "pack_count":36,
        "qualifying_hit_pack_count":1,
        "qualifying_metric":"sir_pack",
        "metric_version":"global-sir-v1",
        "observed_at":"2026-01-03T16:12:04Z",
        "denominator_complete":true
      }'::jsonb,
      E'Now, the meat and potatoes: the booster box.\nA booster box contains 36 packs, which essentially guarantees some fire.\nMy Secret Rare count here is a whopping eight, made up of five Illustration Rares, two Full Art Trainer Supporters, and, the biggest hit, a Special Illustration Rare ex.',
      array['Opening Pokémon TCG', 'Phantasmal Flames Products']::text[]
    ),
    (
      5,
      'tcgtalk-perfect-order-sg-54-v1'::text,
      'public_study_tcgtalk_sg_54'::text,
      'tcgtalk_perfect_order_study'::text,
      'tcgTalk Perfect Order study'::text,
      'Reviewed 54-pack public study attributed to Singapore''s publisher country; physical opening location is not claimed and its rate remains withheld.'::text,
      'tcgTalk Perfect Order 54-pack study'::text,
      'tcgtalk.com'::text,
      'https://tcgtalk.com/blog/perfect-order-pull-rates-what-singapore-collectors-can-expect-1774442400232'::text,
      'public-study-tcgtalk-perfect-order-v1'::text,
      '{
        "study_key":"tcgtalk-perfect-order-sg-54-v1",
        "canonical_url":"https://tcgtalk.com/blog/perfect-order-pull-rates-what-singapore-collectors-can-expect-1774442400232",
        "collector_version":"public-study-tcgtalk-perfect-order-v1",
        "parser_version":"tcgtalk-perfect-order-evidence-v1",
        "country_code":"SG",
        "country_name":"Singapore",
        "geography_basis":"publisher_country",
        "geography_confidence":"tier_b",
        "set_external_id":"me03",
        "product_scope":"booster_bundle",
        "pack_count":54,
        "qualifying_hit_pack_count":1,
        "qualifying_metric":"sir_pack",
        "metric_version":"global-sir-v1",
        "observed_at":"2026-03-25T12:40:00Z",
        "denominator_complete":true
      }'::jsonb,
      E'Based on community opening of 9 booster bundles (54 packs total)\nOut of 54 packs opened, the community pull rate held roughly true: 1 SIR per 54 packs in this particular opening, with the Meowth EX SIR being the pull.'::text,
      array['Perfect Order Pull Rates', 'Singapore Collectors Can Expect']::text[]
    );
$$;

alter function ingest.reviewed_public_study_contracts() owner to postgres;
revoke all on function ingest.reviewed_public_study_contracts()
  from public, anon, authenticated, service_role;
comment on function ingest.reviewed_public_study_contracts() is
  'Owner-only immutable reviewed-study facts. Includes private numerator and exact evidence; never grant this function to API or worker roles.';

-- The 020 function bodies are otherwise unchanged. Rewrite only the exact
-- reviewed ordinal predicate and fail closed if that prior migration has
-- drifted, so every boundary is extended together or none is changed.
do $$
declare
  function_oid regprocedure;
  source_definition text;
  updated_definition text;
begin
  foreach function_oid in array ARRAY[
    'ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure,
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure,
    'ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamptz,integer)'::regprocedure,
    'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)'::regprocedure,
    'public.get_public_study_coverage_v1()'::regprocedure
  ]
  loop
    source_definition := pg_get_functiondef(function_oid::oid);
    if position('contracts.ordinal in (3, 4)' in source_definition) = 0 then
      raise exception using
        errcode = '55000',
        message = 'reviewed coverage function is missing the expected 020 ordinal predicate',
        detail = function_oid::text;
    end if;
    updated_definition := replace(
      source_definition,
      'contracts.ordinal in (3, 4)',
      'contracts.ordinal in (3, 4, 5)'
    );
    if updated_definition = source_definition then
      raise exception using
        errcode = '55000',
        message = 'reviewed coverage function ordinal extension was not applied',
        detail = function_oid::text;
    end if;
    execute updated_definition;
  end loop;
end;
$$;

comment on function ingest.finalize_public_study_coverage_job_v1(
  uuid, text, bigint, text, jsonb
) is
  'Generation-fenced verifier for three reviewed denominator-only observations. It cannot publish hit counts or inference.';

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
        'tcgtalk-perfect-order-sg-54-v1'
      )
    )
  );

commit;
