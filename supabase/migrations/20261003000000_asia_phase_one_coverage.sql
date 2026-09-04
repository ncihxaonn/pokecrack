begin;

-- Taiwan's official 40-pack product is a value bundle, not a standard six-pack
-- booster bundle. Extend the denominator-only vocabulary without changing the
-- statistical opening ledger.
alter table ingest.public_study_coverage_observations
  drop constraint public_study_coverage_product_check;
alter table ingest.public_study_coverage_observations
  add constraint public_study_coverage_product_check check (
    product_scope in ('all', 'booster_box', 'etb', 'booster_bundle', 'value_bundle')
  );

-- Phase-one Asian public studies are denominator-only coverage records. Each
-- contract retains only the minimum factual text needed to prove one complete
-- opening and its exact pack denominator; no numerator or rate is admitted.
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
  'public_study_limitsend_kr_30',
  'LimitSend Inferno X 30-pack study',
  'public_web',
  'limitsend.tistory.com',
  'https://limitsend.tistory.com/entry/%ED%8F%AC%EC%BC%93%EB%AA%AC%EC%B9%B4%EB%93%9C-%EB%82%B1%EA%B0%9C%ED%8C%A9-%EA%B5%AC%EB%A7%A4%EB%A5%BC-%EC%A1%B0%EC%8B%AC%ED%95%B4%EC%95%BC-%ED%95%98%EB%8A%94-%EC%9D%B4%EC%9C%A0%EF%BD%9C%EC%9D%B8%ED%8E%98%EB%A5%B4%EB%85%B8X-%EC%A7%81%EC%A0%91-%EA%B0%9C%EB%B4%89%ED%95%B4%EB%B3%B4%EB%8B%88',
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
    "study_key":"limitsend-inferno-x-kr-30-v1",
    "canonical_url":"https://limitsend.tistory.com/entry/%ED%8F%AC%EC%BC%93%EB%AA%AC%EC%B9%B4%EB%93%9C-%EB%82%B1%EA%B0%9C%ED%8C%A9-%EA%B5%AC%EB%A7%A4%EB%A5%BC-%EC%A1%B0%EC%8B%AC%ED%95%B4%EC%95%BC-%ED%95%98%EB%8A%94-%EC%9D%B4%EC%9C%A0%EF%BD%9C%EC%9D%B8%ED%8E%98%EB%A5%B4%EB%85%B8X-%EC%A7%81%EC%A0%91-%EA%B0%9C%EB%B4%89%ED%95%B4%EB%B3%B4%EB%8B%88",
    "collector_version":"public-study-limitsend-inferno-x-v1",
    "parser_version":"limitsend-inferno-x-evidence-v1",
    "country_code":"KR",
    "country_name":"South Korea",
    "geography_basis":"product_market",
    "geography_confidence":"tier_b",
    "set_external_id":"M2",
    "set_language":"ko",
    "set_name":"인페르노X",
    "product_scope":"booster_box",
    "pack_count":30,
    "observed_at":"2026-08-20T14:20:28Z",
    "denominator_complete":true,
    "set_official_url":"https://pokemoncard.co.kr/card/838",
    "robots_url":"https://limitsend.tistory.com/robots.txt",
    "robots_checked_at":"2026-09-04",
    "terms_checked_at":"2026-09-04",
    "terms_status":"cc_by_nc_nd",
    "rights_scope":"minimal_noncreative_facts_no_media_or_body_reuse"
  }'::jsonb,
  'public-study-limitsend-inferno-x-v1',
  86400,
  false
),
(
  'public_study_buyfunlife_tw_40',
  'BuyFunLife Ninja Spinner 40-pack study',
  'public_web',
  'buyfunlife.com',
  'https://buyfunlife.com/pokemon-ninja-spinner-price-mur-guide/',
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
    "study_key":"buyfunlife-ninja-spinner-tw-40-v1",
    "canonical_url":"https://buyfunlife.com/pokemon-ninja-spinner-price-mur-guide/",
    "collector_version":"public-study-buyfunlife-ninja-spinner-v1",
    "parser_version":"buyfunlife-ninja-spinner-evidence-v1",
    "country_code":"TW",
    "country_name":"Taiwan",
    "geography_basis":"product_market",
    "geography_confidence":"tier_b",
    "set_external_id":"M4",
    "set_language":"zh-TW",
    "set_name":"忍者飛旋",
    "product_scope":"value_bundle",
    "pack_count":40,
    "observed_at":"2026-04-03T13:49:13Z",
    "denominator_complete":true,
    "set_official_url":"https://asia.pokemon-card.com/tw/archive/special/card/m4/",
    "robots_url":"https://buyfunlife.com/robots.txt",
    "robots_checked_at":"2026-09-04",
    "terms_checked_at":"2026-09-04",
    "terms_status":"site_disclaimer_reviewed",
    "rights_scope":"minimal_noncreative_facts_no_media_or_body_reuse"
  }'::jsonb,
  'public-study-buyfunlife-ninja-spinner-v1',
  86400,
  false
),
(
  'public_study_allonline_th_10',
  'ALL ONLINE Mega Dream ex 10-pack study',
  'public_web',
  'blog.allonline.7eleven.co.th',
  'https://blog.allonline.7eleven.co.th/collectibles-zone/pokemon-card-review-dream-evolution-ex-all-online/',
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
    "study_key":"allonline-mega-dream-ex-th-10-v1",
    "canonical_url":"https://blog.allonline.7eleven.co.th/collectibles-zone/pokemon-card-review-dream-evolution-ex-all-online/",
    "collector_version":"public-study-allonline-mega-dream-ex-v1",
    "parser_version":"allonline-mega-dream-ex-evidence-v1",
    "country_code":"TH",
    "country_name":"Thailand",
    "geography_basis":"product_market",
    "geography_confidence":"tier_b",
    "set_external_id":"MA3",
    "set_language":"th",
    "set_name":"วิวัฒนาการเมก้า ดรีมex",
    "product_scope":"booster_box",
    "pack_count":10,
    "observed_at":"2026-01-29T10:10:35Z",
    "denominator_complete":true,
    "set_official_url":"https://asia.pokemon-card.com/th/archives/6828/",
    "robots_url":"https://blog.allonline.7eleven.co.th/robots.txt",
    "robots_checked_at":"2026-09-04",
    "terms_checked_at":"2026-09-04",
    "terms_status":"allonline_terms_reviewed",
    "rights_scope":"minimal_noncreative_facts_no_media_or_body_reuse"
  }'::jsonb,
  'public-study-allonline-mega-dream-ex-v1',
  86400,
  false
);

insert into ingest.source_request_gates (source_key)
values
  ('public_study_limitsend_kr_30'),
  ('public_study_buyfunlife_tw_40'),
  ('public_study_allonline_th_10');

-- The worker role cannot read gate rows directly. Expose only the boolean
-- readiness fact so a missing per-source gate cannot pass health checks and
-- then fail every collection job at runtime.
create function ingest.reviewed_public_study_gates_ready_v1()
returns boolean
language sql
stable
security definer
parallel safe
set search_path = pg_catalog
as $$
  select count(*) = 9
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
    'public_study_allonline_th_10'
  );
$$;

alter function ingest.reviewed_public_study_gates_ready_v1() owner to postgres;
revoke all on function ingest.reviewed_public_study_gates_ready_v1()
  from public, anon, authenticated, service_role;
grant execute on function ingest.reviewed_public_study_gates_ready_v1()
  to service_role;
comment on function ingest.reviewed_public_study_gates_ready_v1() is
  'Boolean-only readiness check for all exact reviewed public-study request gates; it exposes no gate identity or lease state.';

-- Append ordinals 7-9 only if the exact PokeSup ordinal-6 suffix is present.
do $migration$
declare
  definition text;
  updated_definition text;
  old_suffix text := $old$
      array['アビスアイ', '開封結果', 'レアリティ封入率検証']::text[]
    );$old$;
  new_suffix text := $new$
      array['アビスアイ', '開封結果', 'レアリティ封入率検証']::text[]
    ),
    (
      7,
      'limitsend-inferno-x-kr-30-v1'::text,
      'public_study_limitsend_kr_30'::text,
      'limitsend_inferno_x_study'::text,
      'LimitSend Inferno X study'::text,
      'Reviewed 30-pack Korean public coverage study attributed to the South Korea product market; denominator-only with rates withheld.'::text,
      'LimitSend Inferno X 30-pack study'::text,
      'limitsend.tistory.com'::text,
      'https://limitsend.tistory.com/entry/%ED%8F%AC%EC%BC%93%EB%AA%AC%EC%B9%B4%EB%93%9C-%EB%82%B1%EA%B0%9C%ED%8C%A9-%EA%B5%AC%EB%A7%A4%EB%A5%BC-%EC%A1%B0%EC%8B%AC%ED%95%B4%EC%95%BC-%ED%95%98%EB%8A%94-%EC%9D%B4%EC%9C%A0%EF%BD%9C%EC%9D%B8%ED%8E%98%EB%A5%B4%EB%85%B8X-%EC%A7%81%EC%A0%91-%EA%B0%9C%EB%B4%89%ED%95%B4%EB%B3%B4%EB%8B%88'::text,
      'public-study-limitsend-inferno-x-v1'::text,
      '{
        "study_key":"limitsend-inferno-x-kr-30-v1",
        "canonical_url":"https://limitsend.tistory.com/entry/%ED%8F%AC%EC%BC%93%EB%AA%AC%EC%B9%B4%EB%93%9C-%EB%82%B1%EA%B0%9C%ED%8C%A9-%EA%B5%AC%EB%A7%A4%EB%A5%BC-%EC%A1%B0%EC%8B%AC%ED%95%B4%EC%95%BC-%ED%95%98%EB%8A%94-%EC%9D%B4%EC%9C%A0%EF%BD%9C%EC%9D%B8%ED%8E%98%EB%A5%B4%EB%85%B8X-%EC%A7%81%EC%A0%91-%EA%B0%9C%EB%B4%89%ED%95%B4%EB%B3%B4%EB%8B%88",
        "collector_version":"public-study-limitsend-inferno-x-v1",
        "parser_version":"limitsend-inferno-x-evidence-v1",
        "country_code":"KR",
        "country_name":"South Korea",
        "geography_basis":"product_market",
        "geography_confidence":"tier_b",
        "set_external_id":"M2",
        "set_language":"ko",
        "set_name":"인페르노X",
        "product_scope":"booster_box",
        "pack_count":30,
        "observed_at":"2026-08-20T14:20:28Z",
        "denominator_complete":true,
        "set_official_url":"https://pokemoncard.co.kr/card/838",
        "robots_url":"https://limitsend.tistory.com/robots.txt",
        "robots_checked_at":"2026-09-04",
        "terms_checked_at":"2026-09-04",
        "terms_status":"cc_by_nc_nd",
        "rights_scope":"minimal_noncreative_facts_no_media_or_body_reuse"
      }'::jsonb,
      E'인페르노X의 공식 구성은 다음과 같습니다. 1팩 : 5장 1박스 : 30팩 총 150장\n특히 직접 한 박스를 처음부터 끝까지 개봉하면서 팩의 상태와 나온 카드를 같이 비교해보니 상당히 재미있는 경험이었습니다.'::text,
      array['포켓몬카드 낱개팩 구매', '인페르노X 직접 개봉해보니']::text[]
    ),
    (
      8,
      'buyfunlife-ninja-spinner-tw-40-v1'::text,
      'public_study_buyfunlife_tw_40'::text,
      'buyfunlife_ninja_spinner_study'::text,
      'BuyFunLife Ninja Spinner study'::text,
      'Reviewed 40-pack Traditional Chinese public coverage study attributed to the Taiwan product market; denominator-only with rates withheld.'::text,
      'BuyFunLife Ninja Spinner 40-pack study'::text,
      'buyfunlife.com'::text,
      'https://buyfunlife.com/pokemon-ninja-spinner-price-mur-guide/'::text,
      'public-study-buyfunlife-ninja-spinner-v1'::text,
      '{
        "study_key":"buyfunlife-ninja-spinner-tw-40-v1",
        "canonical_url":"https://buyfunlife.com/pokemon-ninja-spinner-price-mur-guide/",
        "collector_version":"public-study-buyfunlife-ninja-spinner-v1",
        "parser_version":"buyfunlife-ninja-spinner-evidence-v1",
        "country_code":"TW",
        "country_name":"Taiwan",
        "geography_basis":"product_market",
        "geography_confidence":"tier_b",
        "set_external_id":"M4",
        "set_language":"zh-TW",
        "set_name":"忍者飛旋",
        "product_scope":"value_bundle",
        "pack_count":40,
        "observed_at":"2026-04-03T13:49:13Z",
        "denominator_complete":true,
        "set_official_url":"https://asia.pokemon-card.com/tw/archive/special/card/m4/",
        "robots_url":"https://buyfunlife.com/robots.txt",
        "robots_checked_at":"2026-09-04",
        "terms_checked_at":"2026-09-04",
        "terms_status":"site_disclaimer_reviewed",
        "rights_scope":"minimal_noncreative_facts_no_media_or_body_reuse"
      }'::jsonb,
      '我買了一整盒《忍者飛旋》加值組合（售價 $2025），拆了 40 包'::text,
      array['寶可夢忍者飛旋加值組合開箱', 'MUR機率多低']::text[]
    ),
    (
      9,
      'allonline-mega-dream-ex-th-10-v1'::text,
      'public_study_allonline_th_10'::text,
      'allonline_mega_dream_ex_study'::text,
      'ALL ONLINE Mega Dream ex study'::text,
      'Reviewed 10-pack Thai public coverage study attributed to the Thailand product market; denominator-only with rates withheld.'::text,
      'ALL ONLINE Mega Dream ex 10-pack study'::text,
      'blog.allonline.7eleven.co.th'::text,
      'https://blog.allonline.7eleven.co.th/collectibles-zone/pokemon-card-review-dream-evolution-ex-all-online/'::text,
      'public-study-allonline-mega-dream-ex-v1'::text,
      '{
        "study_key":"allonline-mega-dream-ex-th-10-v1",
        "canonical_url":"https://blog.allonline.7eleven.co.th/collectibles-zone/pokemon-card-review-dream-evolution-ex-all-online/",
        "collector_version":"public-study-allonline-mega-dream-ex-v1",
        "parser_version":"allonline-mega-dream-ex-evidence-v1",
        "country_code":"TH",
        "country_name":"Thailand",
        "geography_basis":"product_market",
        "geography_confidence":"tier_b",
        "set_external_id":"MA3",
        "set_language":"th",
        "set_name":"วิวัฒนาการเมก้า ดรีมex",
        "product_scope":"booster_box",
        "pack_count":10,
        "observed_at":"2026-01-29T10:10:35Z",
        "denominator_complete":true,
        "set_official_url":"https://asia.pokemon-card.com/th/archives/6828/",
        "robots_url":"https://blog.allonline.7eleven.co.th/robots.txt",
        "robots_checked_at":"2026-09-04",
        "terms_checked_at":"2026-09-04",
        "terms_status":"allonline_terms_reviewed",
        "rights_scope":"minimal_noncreative_facts_no_media_or_body_reuse"
      }'::jsonb,
      E'วันนี้จะขออาสาพาทุกคนไปเปิดกล่องรีวิว การ์ดเกม ชุด วิวัฒนาการดรีมex ซีรีส์ใหม่ล่าสุดนี้\nมาดูกันว่าตัวตึงที่ผมเปิดเจอมีตัวไหนบ้าง\n1 กล่อง = 10 ซอง >> 1 ซอง = 10 ใบ รวมเป็น 100 ใบ ราคา 1,600 บาท'::text,
      array['รีวิว การ์ดโปเกมอน', 'วิวัฒนาการดรีมex', 'เติมเด็คให้แข็งแกร่ง']::text[]
    );$new$;
begin
  select pg_get_functiondef(
    'ingest.reviewed_public_study_contracts()'::regprocedure
  )
  into definition;

  if definition is null
    or position(old_suffix in definition) = 0
    or position('limitsend-inferno-x-kr-30-v1' in definition) > 0
    or position('buyfunlife-ninja-spinner-tw-40-v1' in definition) > 0
    or position('allonline-mega-dream-ex-th-10-v1' in definition) > 0
    or (
      select array_agg(contracts.ordinal order by contracts.ordinal)
      from ingest.reviewed_public_study_contracts() as contracts
    ) is distinct from array[1, 2, 3, 4, 5, 6]::integer[]
    or (
      select array_agg(contracts.study_key order by contracts.ordinal)
      from ingest.reviewed_public_study_contracts() as contracts
    ) is distinct from array[
      'comicbook-perfect-order-us-55-v1',
      'wargamer-chaos-rising-gb-17-v1',
      'cardchill-ascended-heroes-gb-90-v1',
      'bleedingcool-phantasmal-flames-us-36-v1',
      'tcgtalk-perfect-order-sg-54-v1',
      'pokesup-abyss-eye-jp-30-v1'
    ]::text[]
    or (
      select array_agg(contracts.policy_key order by contracts.ordinal)
      from ingest.reviewed_public_study_contracts() as contracts
    ) is distinct from array[
      'public_study_comicbook_us_55',
      'public_study_wargamer_gb_17',
      'public_study_cardchill_gb_90',
      'public_study_bleedingcool_us_36',
      'public_study_tcgtalk_sg_54',
      'public_study_pokesup_jp_30'
    ]::text[]
  then
    raise exception using
      errcode = '55000',
      message = 'reviewed public-study registry is not the expected ordinal-6 definition';
  end if;

  updated_definition := replace(definition, old_suffix, new_suffix);
  if updated_definition = definition then
    raise exception using
      errcode = '55000',
      message = 'Asian coverage registry extension was not applied';
  end if;
  execute updated_definition;
end;
$migration$;

alter function ingest.reviewed_public_study_contracts() owner to postgres;
revoke all on function ingest.reviewed_public_study_contracts()
  from public, anon, authenticated, service_role;
comment on function ingest.reviewed_public_study_contracts() is
  'Owner-only immutable reviewed-study facts. Includes private historical facts and exact bounded coverage evidence; never grant this function to API or worker roles.';

-- Move all four coverage ingestion boundaries together and leave the
-- statistical ordinal-1/2 path and legacy v1 browser projection unchanged.
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
    if position('contracts.ordinal in (3, 4, 5, 6)' in source_definition) = 0
      or position('contracts.ordinal in (3, 4, 5, 6, 7, 8, 9)' in source_definition) > 0
    then
      raise exception using
        errcode = '55000',
        message = 'reviewed coverage function is missing the expected ordinal-6 predicate',
        detail = function_oid::text;
    end if;
    updated_definition := replace(
      source_definition,
      'contracts.ordinal in (3, 4, 5, 6)',
      'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9)'
    );
    if updated_definition = source_definition then
      raise exception using
        errcode = '55000',
        message = 'reviewed coverage ordinal-7/8/9 extension was not applied',
        detail = function_oid::text;
    end if;
    execute updated_definition;
  end loop;
end;
$migration$;

comment on function ingest.finalize_public_study_coverage_job_v1(
  uuid, text, bigint, text, jsonb
) is
  'Generation-fenced verifier for seven reviewed denominator-only contracts. English contracts require the exact live TCGdex catalog; explicit non-English contracts require a bounded source-native set name and official set URL. It cannot publish a numerator or inference.';

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
        'allonline-mega-dream-ex-th-10-v1'
      )
    )
  );

commit;
