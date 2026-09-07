begin;

-- Generated with Supabase CLI on MAM as 20260907101700, then ordered after
-- the repository's existing future-dated 20261010 ledger. No schema is exposed.
-- Only the Chinese product market is claimed, never a physical opening in China.
do $migration$
declare
  definition text;
  old_suffix text := $old$      array['TCG Pokémon Uruguay  Unboxing  Booster BOX Silver Tempest + Codigos TCG Live']::text[]
    );$old$;
  new_suffix text := $new$      array['TCG Pokémon Uruguay  Unboxing  Booster BOX Silver Tempest + Codigos TCG Live']::text[]
    ),
    (
      25, 'garbage-rips-gem-vol2-cn-1-v1'::text,
      'public_study_garbage_rips_cn_1'::text,
      'garbage_rips_gem_vol2_study'::text,
      'Garbage Rips Gem Vol.2 single-pack study'::text,
      'One verified opening of a Chinese-market Gem Pack Vol.2 product. The publisher is in the United States; this is product-market coverage, not a claim of an opening in China. No normalized hit numerator or rate.'::text,
      'Garbage Rips Gem Vol.2 single-pack coverage'::text,
      'garbagerips.com'::text,
      'https://garbagerips.com/rip/only-garbage-rips-chinese-gem-pack-vol-2-eeveelutions-8jKHh-P7P7M.html'::text,
      'public-study-garbage-rips-gem-vol2-v1'::text,
      '{
  "study_key": "garbage-rips-gem-vol2-cn-1-v1",
  "canonical_url": "https://garbagerips.com/rip/only-garbage-rips-chinese-gem-pack-vol-2-eeveelutions-8jKHh-P7P7M.html",
  "collector_version": "public-study-garbage-rips-gem-vol2-v1",
  "parser_version": "garbage-rips-gem-vol2-evidence-v1",
  "country_code": "CN",
  "country_name": "China",
  "geography_basis": "product_market",
  "geography_confidence": "tier_b",
  "set_external_id": "gem-pack-vol-2",
  "set_language": "zh-CN",
  "set_name": "Pokémon宝石包VOL.2",
  "product_scope": "all",
  "pack_count": 1,
  "observed_at": "2026-02-13T13:30:09Z",
  "denominator_complete": true,
  "set_official_url": "https://www.pokemon.cn/tcg/product/15518.html",
  "robots_url": "https://garbagerips.com/robots.txt",
  "robots_checked_at": "2026-09-07",
  "terms_url": "https://garbagerips.com/privacy.html",
  "terms_checked_at": "2026-09-07",
  "terms_status": "public_site_policy_reviewed",
  "rights_scope": "minimal_noncreative_facts_no_media_or_body_reuse"
}'::jsonb,
      E'Chinese Gem Pack Vol 2 (Eeveelutions)\nOne pack. Eeveelutions.'::text,
      array['Only Garbage Rips 😬 | Chinese Gem Pack Vol 2 (Eeveelutions)']::text[]
    );$new$;
begin
  select pg_get_functiondef('ingest.reviewed_public_study_contracts()'::regprocedure)
    into definition;
  if position(old_suffix in definition) = 0
    or (select array_agg(ordinal order by ordinal)
        from ingest.reviewed_public_study_contracts())
       is distinct from array(select generate_series(1, 24))
  then
    raise exception 'Expected exact ordinal-24 reviewed-study registry';
  end if;
  execute replace(definition, old_suffix, new_suffix);
end;
$migration$;

alter function ingest.reviewed_public_study_contracts() owner to postgres;
revoke all on function ingest.reviewed_public_study_contracts()
  from public, anon, authenticated, service_role;

insert into ingest.source_policies (
  source_key, display_name, source_kind, domain, base_url, enabled,
  collector_type, access_mode, robots_policy, routes, include_subdomains,
  min_delay_seconds, max_pages_per_run, max_items_per_run, max_concurrency,
  statistics_eligible_default, retention_days, config, version,
  expected_interval_seconds, is_demo
)
select policy_key, display_name, 'public_web', domain, canonical_url, true,
  'scrapling_http', 'public', 'respect', array['scrapling_http']::text[], false,
  30, 2, 1, 1, true, 730, config, policy_version, 86400, false
from ingest.reviewed_public_study_contracts()
where ordinal = 25 and study_key = 'garbage-rips-gem-vol2-cn-1-v1';

insert into ingest.source_request_gates(source_key)
values ('public_study_garbage_rips_cn_1');

do $migration$
declare
  definition text;
  old_tail text := $old$'public_study_gringo_gameplays_silver_tempest_uy_36'$old$;
begin
  select pg_get_functiondef('ingest.reviewed_public_study_gates_ready_v1()'::regprocedure)
    into definition;
  if position('count(*) = 24' in definition) = 0
    or position(old_tail in definition) = 0 then
    raise exception 'Expected ordinal-24 gate readiness function';
  end if;
  execute replace(replace(definition, 'count(*) = 24', 'count(*) = 25'),
    old_tail, old_tail || ', ''public_study_garbage_rips_cn_1''');
end;
$migration$;

do $migration$
declare
  function_oid regprocedure;
  definition text;
  old_predicate text := 'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24)';
  new_predicate text := 'contracts.ordinal in (3, 4, 5, 6, 7, 8, 9, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25)';
begin
  foreach function_oid in array array[
    'ingest.begin_public_study_job_v2(uuid,text,bigint,text)'::regprocedure,
    'ingest.finalize_public_study_coverage_job_v1(uuid,text,bigint,text,jsonb)'::regprocedure,
    'ingest.enqueue_public_study_coverage_job_v1(text,integer,text,timestamptz,integer)'::regprocedure,
    'ingest.enqueue_scheduled_public_study_coverage_job_v1(text,timestamptz,text,integer,integer)'::regprocedure
  ] loop
    definition := pg_get_functiondef(function_oid::oid);
    if position(old_predicate in definition) = 0 then
      raise exception 'Expected ordinal-24 coverage boundary: %', function_oid;
    end if;
    execute replace(definition, old_predicate, new_predicate);
  end loop;
end;
$migration$;

-- Preserve the entire existing schedule constraint; append only the new exact
-- study key using PostgreSQL's own parsed constraint representation.
do $migration$
declare
  definition text;
  needle text := $needle$'gringo-gameplays-silver-tempest-uy-36-v1'::text$needle$;
begin
  select pg_get_constraintdef(oid) into definition
  from pg_constraint
  where conrelid = 'ingest.jobs'::regclass
    and conname = 'jobs_reviewed_coverage_schedule_allowlist_check';
  if definition is null or position(needle in definition) = 0 then
    raise exception 'Expected ordinal-24 reviewed coverage schedule constraint';
  end if;
  alter table ingest.jobs drop constraint jobs_reviewed_coverage_schedule_allowlist_check;
  execute 'alter table ingest.jobs add constraint jobs_reviewed_coverage_schedule_allowlist_check '
    || replace(definition, needle, needle || ', ''garbage-rips-gem-vol2-cn-1-v1''::text');
end;
$migration$;

-- Retain just the immutable fact excerpt, not page HTML, media, or claimed hits.
do $migration$
declare
  reviewed record;
  evidence_hash text;
begin
  select contracts.*, policies.id as policy_id into strict reviewed
  from ingest.reviewed_public_study_contracts() as contracts
  join ingest.source_policies as policies
    on policies.source_key = contracts.policy_key
    and policies.config = contracts.config
    and policies.version = contracts.policy_version
    and policies.enabled and not policies.is_demo
  where contracts.ordinal = 25 and contracts.study_key = 'garbage-rips-gem-vol2-cn-1-v1';
  evidence_hash := encode(extensions.digest(convert_to(reviewed.evidence_excerpt, 'UTF8'), 'sha256'), 'hex');
  if evidence_hash <> 'a53e1e4f4b881e8d7f8ba006764aae8b8e27323ffa1a41a138caf5c05ff1c804'
    or reviewed.config ?| array['qualifying_hit_pack_count', 'qualifying_metric', 'metric_version']
  then
    raise exception 'Chinese product-market evidence contract drifted';
  end if;
  insert into ingest.public_study_coverage_observations (
    study_key, source_policy_id, country_code, country_name, source_observed_at,
    pack_count, set_external_id, product_scope, collector_version, parser_version,
    source_policy_version, evidence_sha256, first_verified_at, last_verified_at, is_demo
  ) values (
    reviewed.study_key, reviewed.policy_id, 'CN', 'China',
    (reviewed.config ->> 'observed_at')::timestamptz, 1, 'gem-pack-vol-2', 'all',
    reviewed.policy_version, reviewed.config ->> 'parser_version',
    reviewed.policy_version, evidence_hash, statement_timestamp(), statement_timestamp(), false
  );
end;
$migration$;
commit;
