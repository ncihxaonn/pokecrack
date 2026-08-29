-- Exact reviewed public-study ingestion, fencing, and rate-withholding contract.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select has_table(
  'ingest', 'public_study_observations',
  'the private reviewed-study ledger exists'
);
select ok(
  (select relrowsecurity and relforcerowsecurity
   from pg_class
   where oid = 'ingest.public_study_observations'::regclass),
  'the reviewed-study ledger forces RLS'
);
select is(
  (select count(*)::integer
   from pg_policies
   where schemaname = 'ingest'
     and tablename = 'public_study_observations'
     and cmd = 'SELECT'
     and 'service_role' = any(roles)),
  1,
  'the ledger has one service-role read policy'
);
select ok(
  has_table_privilege(
    'service_role', 'ingest.public_study_observations', 'select'
  )
  and not has_table_privilege(
    'service_role', 'ingest.public_study_observations', 'insert'
  )
  and not has_table_privilege(
    'service_role', 'ingest.public_study_observations', 'update'
  )
  and not has_table_privilege(
    'service_role', 'ingest.public_study_observations', 'delete'
  ),
  'service_role can inspect but never mutate the ledger directly'
);
select ok(
  not has_table_privilege(
    'anon', 'ingest.public_study_observations', 'select'
  )
  and not has_table_privilege(
    'authenticated', 'ingest.public_study_observations', 'select'
  ),
  'browser roles cannot inspect the private ledger'
);

select has_function(
  'ingest', 'begin_public_study_job',
  array['uuid', 'text', 'bigint'],
  'the fenced public-study preflight exists'
);
select has_function(
  'ingest', 'finalize_public_study_job',
  array['uuid', 'text', 'bigint', 'jsonb'],
  'the fenced public-study finalizer exists'
);
select ok(
  (select bool_and(procedures.prosecdef)
   from pg_proc as procedures
   where procedures.oid = any(array[
     'ingest.begin_public_study_job(uuid,text,bigint)'::regprocedure,
     'ingest.finalize_public_study_job(uuid,text,bigint,jsonb)'::regprocedure
   ])),
  'both public-study RPCs are SECURITY DEFINER'
);
select ok(
  (select bool_and(
      coalesce(procedures.proconfig, '{}'::text[])
        @> array['search_path=pg_catalog']
    )
   from pg_proc as procedures
   where procedures.oid = any(array[
     'ingest.begin_public_study_job(uuid,text,bigint)'::regprocedure,
     'ingest.finalize_public_study_job(uuid,text,bigint,jsonb)'::regprocedure
   ])),
  'both public-study RPCs fix search_path to pg_catalog'
);
select ok(
  (select bool_and(
      has_function_privilege('service_role', procedures.oid, 'execute')
      and not has_function_privilege('anon', procedures.oid, 'execute')
      and not has_function_privilege(
        'authenticated', procedures.oid, 'execute'
      )
    )
   from pg_proc as procedures
   where procedures.oid = any(array[
     'ingest.begin_public_study_job(uuid,text,bigint)'::regprocedure,
     'ingest.finalize_public_study_job(uuid,text,bigint,jsonb)'::regprocedure
   ])),
  'only service_role can execute the public-study write RPCs'
);

select is(
  (select count(*)::integer
   from ingest.source_policies
   where source_key in (
     'public_study_comicbook_us_55',
     'public_study_wargamer_gb_17'
   )
     and enabled
     and not is_demo
     and source_kind = 'public_web'
     and collector_type = 'scrapling_http'
     and access_mode = 'public'
     and robots_policy = 'respect'
     and routes = array['scrapling_http']::text[]
     and not include_subdomains
     and min_delay_seconds = 30
     and max_pages_per_run = 2
     and max_items_per_run = 1
     and max_concurrency = 1
     and browser_profile is null
     and statistics_eligible_default
     and retention_days = 730
     and expected_interval_seconds = 86400),
  2,
  'exactly two live reviewed public-study policies are enabled'
);
select ok(
  (select config = '{
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
    }'::jsonb
   from ingest.source_policies
   where source_key = 'public_study_comicbook_us_55'),
  'the US study facts are immutable database policy data'
);
select ok(
  (select config = '{
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
    }'::jsonb
   from ingest.source_policies
   where source_key = 'public_study_wargamer_gb_17'),
  'the GB study facts are immutable database policy data'
);
select is(
  (select count(*)::integer
   from ingest.source_request_gates
   where source_key in (
     'public_study_comicbook_us_55',
     'public_study_wargamer_gb_17'
   )
     and owner_job_id is null
     and owner_lease_generation is null
     and acquired_at is null
     and active_until is null),
  2,
  'both reviewed sources start with idle durable request gates'
);

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
    'tcgdex', 'me03', 'Perfect Order', 'public-study-perfect-order',
    'en', '2026-03-27', 'Mega Evolution', '{}'::jsonb, '{}'::jsonb,
    true, false
  ),
  (
    'tcgdex', 'me04', 'Chaos Rising', 'public-study-chaos-rising',
    'en', '2026-05-15', 'Mega Evolution', '{}'::jsonb, '{}'::jsonb,
    true, false
  )
on conflict (external_source, external_id, language, is_demo) do update set
  is_active = true,
  updated_at = excluded.updated_at;

select throws_ok(
  $sql$select * from ingest.enqueue_job_v1(
    'source.public_study.opening',
    '{"study_key":"not-reviewed"}'::jsonb
  )$sql$,
  '22023',
  'public-study jobs require one exact approved study_key',
  'direct enqueue rejects an unreviewed study key'
);
select throws_ok(
  $sql$select * from ingest.enqueue_scheduled_job_v1(
    'wrong-schedule-name',
    date_trunc('minute', clock_timestamp()),
    'source.public_study.opening',
    '{"study_key":"comicbook-perfect-order-us-55-v1"}'::jsonb
  )$sql$,
  '22023',
  'public-study schedule_name must match its exact study_key',
  'scheduled enqueue binds the name to its exact reviewed study'
);

set local role service_role;
do $public_study_ingestion$
declare
  comic_job_id uuid;
  comic_generation bigint;
  wargamer_job_id uuid;
  wargamer_generation bigint;
  acquired_value boolean;
  bad_hash_state text;
  comic_excerpt constant text := E'In total, I opened 55 boosters from the upcoming Perfect Order lineup.\n1 Special Illustration Rare';
  wargamer_excerpt constant text := E'after opening the 17 Pokémon Chaos Rising packs Wargamer was sent ahead of release, my opinion remains positive on those fronts.\nmissing out on any SIR mega hits.';
begin
  select jobs.id
  into comic_job_id
  from ingest.enqueue_job_v1(
    'source.public_study.opening',
    '{"study_key":"comicbook-perfect-order-us-55-v1"}'::jsonb,
    30,
    'pgtap:public-study:comic:first'
  ) as jobs;
  select jobs.id, jobs.lease_generation
  into comic_job_id, comic_generation
  from ingest.claim_jobs_v2(
    'pgtap-public-study-comic',
    array['source.public_study.opening'],
    1,
    600
  ) as jobs;
  select begun.acquired
  into acquired_value
  from ingest.begin_public_study_job(
    comic_job_id,
    'pgtap-public-study-comic',
    comic_generation
  ) as begun;
  if acquired_value is distinct from true then
    raise exception 'ComicBook preflight was not acquired';
  end if;

  begin
    perform ingest.finalize_public_study_job(
      comic_job_id,
      'pgtap-public-study-comic',
      comic_generation,
      jsonb_build_object(
        'version', 1,
        'study_key', 'comicbook-perfect-order-us-55-v1',
        'source_url', 'https://comicbook.com/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates',
        'title', 'I Opened 55 Packs from Pokemon TCG Perfect Order — Pull Rates',
        'evidence_excerpt', comic_excerpt,
        'evidence_sha256', repeat('0', 64),
        'collector_version', 'public-study-comicbook-perfect-order-v1',
        'parser_version', 'comicbook-perfect-order-evidence-v1',
        'source_policy_version', 'public-study-comicbook-perfect-order-v1'
      )
    );
    bad_hash_state := 'allowed';
  exception when others then
    bad_hash_state := sqlstate;
  end;
  perform set_config('pokecrack.public_study_bad_hash_state', bad_hash_state, true);

  perform ingest.finalize_public_study_job(
    comic_job_id,
    'pgtap-public-study-comic',
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
    'pgtap:public-study:wargamer:first'
  ) as jobs;
  select jobs.id, jobs.lease_generation
  into wargamer_job_id, wargamer_generation
  from ingest.claim_jobs_v2(
    'pgtap-public-study-wargamer',
    array['source.public_study.opening'],
    1,
    600
  ) as jobs;
  select begun.acquired
  into acquired_value
  from ingest.begin_public_study_job(
    wargamer_job_id,
    'pgtap-public-study-wargamer',
    wargamer_generation
  ) as begun;
  if acquired_value is distinct from true then
    raise exception 'Wargamer preflight was not acquired';
  end if;
  perform ingest.finalize_public_study_job(
    wargamer_job_id,
    'pgtap-public-study-wargamer',
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

select is(
  current_setting('pokecrack.public_study_bad_hash_state'),
  '22023',
  'the finalizer rejects a SHA-256 that does not hash the exact evidence'
);
select is(
  (select count(*)::integer from ingest.public_study_observations),
  2,
  'two reviewed studies create exactly two immutable ledger rows'
);
select is(
  (select sum(pack_count)::bigint from ingest.public_study_observations),
  72::bigint,
  'the private ledger records 72 reviewed packs'
);
select is(
  (select sum(qualifying_hit_pack_count)::bigint
   from ingest.public_study_observations),
  1::bigint,
  'the qualifying numerator remains private and equals one pack'
);
select is(
  (select count(*)::integer
   from ingest.source_items
   where platform = 'public-study' and not is_demo),
  2,
  'two bounded evidence-only source items are persisted'
);
select is(
  (select count(*)::integer
   from ingest.extraction_runs as runs
   join ingest.public_study_observations as observations
     on observations.extraction_run_id = runs.id),
  2,
  'two deterministic extraction audit rows are persisted'
);
select is(
  (select count(*)::integer
   from ingest.openings as openings
   join ingest.public_study_observations as observations
     on observations.opening_id = openings.id
   where openings.complete_opening
     and openings.eligible_for_statistics
     and openings.validation_status = 'accepted'
     and openings.public_status = 'verified'
     and not openings.is_demo),
  2,
  'two complete verified opening denominators are persisted'
);
select is(
  (select count(*)::integer
   from ingest.opening_hits as hits
   join ingest.public_study_observations as observations
     on observations.opening_id = hits.opening_id),
  0,
  'aggregate studies never fabricate card-level opening hits'
);
select is(
  (select count(*)::integer
   from ingest.source_request_gates
   where source_key in (
     'public_study_comicbook_us_55',
     'public_study_wargamer_gb_17'
   )
     and owner_job_id is null
     and owner_lease_generation is null
     and acquired_at is null
     and active_until is null),
  2,
  'both request gates are released after atomic completion'
);
select is(
  (select count(*)::integer
   from public.country_period_map_cells
   where country_code in ('US', 'GB')
     and period_end = (statement_timestamp() at time zone 'UTC')::date
     and signal_status = 'Insufficient sample'
     and num_nonnulls(
       observed_rate,
       posterior_mean,
       baseline_rate,
       credible_interval_low,
       credible_interval_high,
       delta_from_baseline
     ) = 0
     and not is_demo),
  2,
  'both country cells withhold every rate and inference field'
);
select ok(
  (select bool_and(
      (country_code = 'US' and observed_packs = 55)
      or (country_code = 'GB' and observed_packs = 17)
    )
   from public.country_period_map_cells
   where country_code in ('US', 'GB')
     and period_end = (statement_timestamp() at time zone 'UTC')::date
     and complete_openings = 1
     and independent_source_count = 1
     and not is_demo),
  'country cells expose only reviewed denominators and source counts'
);

set local role anon;
select set_config(
  'pokecrack.public_study_snapshot',
  public.get_public_dashboard_snapshot_v2()::text,
  true
);
reset role;
select is(
  (current_setting('pokecrack.public_study_snapshot')::jsonb
    #>> '{observations,observedPacks}')::integer,
  72,
  'the anonymous dashboard reports 72 observed packs'
);
select is(
  (current_setting('pokecrack.public_study_snapshot')::jsonb
    #>> '{observations,countriesObserved}')::integer,
  2,
  'the anonymous dashboard reports two observed countries'
);
select is(
  (current_setting('pokecrack.public_study_snapshot')::jsonb
    #>> '{observations,countriesWithPublishedRate}')::integer,
  0,
  'the anonymous dashboard publishes no country rate from one-source samples'
);
select is(
  jsonb_array_length(
    current_setting('pokecrack.public_study_snapshot')::jsonb -> 'mapCells'
  ),
  2,
  'the anonymous dashboard exposes two collecting map cells'
);

-- Re-verify one study through a fresh fenced job. The immutable identities
-- must be reused rather than duplicated. Simulate cleanup after a long outage:
-- a fresh exact verification must restore the bounded excerpt and renew every
-- linked retention deadline instead of becoming permanently unverifiable.
update ingest.source_items
set text_excerpt = null,
    expires_at = greatest(discovered_at + interval '1 second', clock_timestamp())
where id = (
  select opening.source_item_id
  from ingest.public_study_observations as opening
  where opening.study_key = 'comicbook-perfect-order-us-55-v1'
);
update ingest.extraction_runs
set expires_at = greatest(started_at + interval '1 second', clock_timestamp())
where id = (
  select opening.extraction_run_id
  from ingest.public_study_observations as opening
  where opening.study_key = 'comicbook-perfect-order-us-55-v1'
);
update ingest.openings
set expires_at = greatest(observed_at + interval '1 second', clock_timestamp())
where id = (
  select opening.opening_id
  from ingest.public_study_observations as opening
  where opening.study_key = 'comicbook-perfect-order-us-55-v1'
);
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '31 seconds'
where source_key = 'public_study_comicbook_us_55';
set local role service_role;
do $public_study_idempotency$
declare
  job_id_value uuid;
  generation_value bigint;
  acquired_value boolean;
  excerpt_value constant text := E'In total, I opened 55 boosters from the upcoming Perfect Order lineup.\n1 Special Illustration Rare';
begin
  select jobs.id
  into job_id_value
  from ingest.enqueue_job_v1(
    'source.public_study.opening',
    '{"study_key":"comicbook-perfect-order-us-55-v1"}'::jsonb,
    20,
    'pgtap:public-study:comic:verify'
  ) as jobs;
  select jobs.id, jobs.lease_generation
  into job_id_value, generation_value
  from ingest.claim_jobs_v2(
    'pgtap-public-study-verify',
    array['source.public_study.opening'],
    1,
    600
  ) as jobs;
  select begun.acquired
  into acquired_value
  from ingest.begin_public_study_job(
    job_id_value,
    'pgtap-public-study-verify',
    generation_value
  ) as begun;
  if acquired_value is distinct from true then
    raise exception 'idempotent preflight was not acquired';
  end if;
  perform ingest.finalize_public_study_job(
    job_id_value,
    'pgtap-public-study-verify',
    generation_value,
    jsonb_build_object(
      'version', 1,
      'study_key', 'comicbook-perfect-order-us-55-v1',
      'source_url', 'https://comicbook.com/gaming/feature/pokemon-tcg-perfect-order-pull-rates-ex-illustration-rares-estimates',
      'title', 'I Opened 55 Packs from Pokemon TCG Perfect Order — Pull Rates',
      'evidence_excerpt', excerpt_value,
      'evidence_sha256',
        'a48e4b6d54243254a8c5a951161238679ecc7d053676b48555022e582428818d',
      'collector_version', 'public-study-comicbook-perfect-order-v1',
      'parser_version', 'comicbook-perfect-order-evidence-v1',
      'source_policy_version', 'public-study-comicbook-perfect-order-v1'
    )
  );
end;
$public_study_idempotency$;
reset role;
select is(
  (select count(*)::integer from ingest.public_study_observations),
  2,
  're-verification does not duplicate ledger identities'
);
select is(
  (select count(*)::integer
   from ingest.source_items
   where platform = 'public-study' and not is_demo),
  2,
  're-verification does not duplicate source identities'
);
select ok(
  (select last_verified_at >= first_verified_at
   from ingest.public_study_observations
   where study_key = 'comicbook-perfect-order-us-55-v1'),
  're-verification advances the ledger verification timestamp'
);
select ok(
  (select source_items.text_excerpt =
      E'In total, I opened 55 boosters from the upcoming Perfect Order lineup.\n1 Special Illustration Rare'
      and source_items.expires_at > clock_timestamp() + interval '729 days'
      and runs.expires_at > clock_timestamp() + interval '729 days'
      and openings.expires_at > clock_timestamp() + interval '729 days'
   from ingest.public_study_observations as observations
   join ingest.source_items as source_items
     on source_items.id = observations.source_item_id
   join ingest.extraction_runs as runs
     on runs.id = observations.extraction_run_id
   join ingest.openings as openings
     on openings.id = observations.opening_id
   where observations.study_key = 'comicbook-perfect-order-us-55-v1'),
  'fresh exact evidence restores the excerpt and renews linked retention'
);

-- A reclaimed lease must make every generation-1 call inert. The current
-- generation still owns the gate and generic completion remains forbidden.
set local role service_role;
do $public_study_stale_setup$
declare
  job_id_value uuid;
  generation_value bigint;
begin
  select jobs.id
  into job_id_value
  from ingest.enqueue_job_v1(
    'source.public_study.opening',
    '{"study_key":"wargamer-chaos-rising-gb-17-v1"}'::jsonb,
    10,
    'pgtap:public-study:wargamer:stale'
  ) as jobs;
  select jobs.id, jobs.lease_generation
  into job_id_value, generation_value
  from ingest.claim_jobs_v2(
    'pgtap-public-study-old',
    array['source.public_study.opening'],
    1,
    1
  ) as jobs;
  perform set_config('pokecrack.public_study_stale_job', job_id_value::text, true);
  perform set_config(
    'pokecrack.public_study_stale_generation', generation_value::text, true
  );
end;
$public_study_stale_setup$;
reset role;
update ingest.jobs
set lock_expires_at = clock_timestamp() - interval '1 second'
where id = current_setting('pokecrack.public_study_stale_job')::uuid;
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '31 seconds'
where source_key = 'public_study_wargamer_gb_17';
set local role service_role;
do $public_study_stale_assertions$
declare
  job_id_value uuid := current_setting('pokecrack.public_study_stale_job')::uuid;
  stale_generation bigint :=
    current_setting('pokecrack.public_study_stale_generation')::bigint;
  current_generation bigint;
  stale_begin_count integer;
  stale_finalize_count integer;
  acquired_value boolean;
  generic_state text;
begin
  select jobs.id, jobs.lease_generation
  into job_id_value, current_generation
  from ingest.claim_jobs_v2(
    'pgtap-public-study-new',
    array['source.public_study.opening'],
    1,
    600
  ) as jobs;
  select count(*)::integer
  into stale_begin_count
  from ingest.begin_public_study_job(
    job_id_value,
    'pgtap-public-study-old',
    stale_generation
  );
  select count(*)::integer
  into stale_finalize_count
  from ingest.finalize_public_study_job(
    job_id_value,
    'pgtap-public-study-old',
    stale_generation,
    null
  );
  select begun.acquired
  into acquired_value
  from ingest.begin_public_study_job(
    job_id_value,
    'pgtap-public-study-new',
    current_generation
  ) as begun;
  begin
    perform ingest.complete_job_v2(
      job_id_value,
      'pgtap-public-study-new',
      current_generation
    );
    generic_state := 'allowed';
  exception when others then
    generic_state := sqlstate;
  end;
  perform ingest.fail_job_v2(
    job_id_value,
    'pgtap-public-study-new',
    current_generation,
    'pgtap_complete',
    'expected test cleanup',
    false
  );
  perform set_config(
    'pokecrack.public_study_stale_begin_count', stale_begin_count::text, true
  );
  perform set_config(
    'pokecrack.public_study_stale_finalize_count',
    stale_finalize_count::text,
    true
  );
  perform set_config(
    'pokecrack.public_study_current_acquired',
    coalesce(acquired_value, false)::text,
    true
  );
  perform set_config(
    'pokecrack.public_study_generic_state', generic_state, true
  );
end;
$public_study_stale_assertions$;
reset role;
select is(
  current_setting('pokecrack.public_study_stale_begin_count'),
  '0',
  'a stale generation cannot acquire the public-study request gate'
);
select is(
  current_setting('pokecrack.public_study_stale_finalize_count'),
  '0',
  'a stale generation cannot finalize or mutate public-study data'
);
select is(
  current_setting('pokecrack.public_study_current_acquired'),
  'true',
  'the reclaimed current generation can acquire its request gate'
);
select is(
  current_setting('pokecrack.public_study_generic_state'),
  '22023',
  'generic completion cannot bypass the dedicated public-study finalizer'
);
select is(
  (select count(*)::integer from ingest.public_study_observations),
  2,
  'stale and failed retry paths cannot add observations'
);

select lives_ok(
  $sql$select * from ingest.enqueue_scheduled_job_v1(
    'public_study_comicbook-perfect-order-us-55-v1',
    date_trunc('minute', clock_timestamp()),
    'source.public_study.opening',
    '{"study_key":"comicbook-perfect-order-us-55-v1"}'::jsonb,
    5,
    3
  )$sql$,
  'the exact daily scheduler identity is accepted'
);

insert into public.country_period_map_cells (
  country_code,
  country_name,
  period_start,
  period_end,
  language,
  set_scope,
  product_scope,
  metric_key,
  metric_version,
  observed_packs,
  complete_openings,
  independent_source_count,
  signal_status,
  methodology_version,
  updated_at,
  is_demo
) values (
  'CA',
  'Canada',
  (statement_timestamp() at time zone 'UTC')::date - 365,
  (statement_timestamp() at time zone 'UTC')::date - 1,
  'en',
  'all',
  'all',
  'qualifying_hit_pack_rate',
  'global-sir-v1',
  1,
  1,
  1,
  'Insufficient sample',
  'public-study-global-sir-v1',
  clock_timestamp(),
  false
);
set local role anon;
select set_config(
  'pokecrack.public_study_stale_visible',
  (
    select count(*)::integer
    from public.country_period_map_cells
    where country_code = 'CA'
  )::text,
  true
);
reset role;
select is(
  current_setting('pokecrack.public_study_stale_visible'),
  '0',
  'browser RLS hides historical rolling cells while retaining them for audit'
);

select * from finish();
rollback;
