-- The aggregate-cohort bridge is private and deliberately does not publish a
-- map cell. These tests prove that owner admission + a declared domain, not a
-- reviewer acceptance or social discovery record, controls aggregate input.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select has_table(
  'analytics',
  'reviewed_global_aggregate_independent_sources',
  'private independent-source registry exists'
);
select has_table(
  'analytics',
  'reviewed_global_aggregate_authorized_source_bindings',
  'private authorized source-binding registry exists'
);
select has_table(
  'analytics',
  'reviewed_global_aggregate_input_admissions',
  'private cross-ledger admission registry exists'
);
select has_function(
  'analytics',
  'reviewed_global_aggregate_cohort_v1',
  array['date', 'date', 'timestamp with time zone'],
  'owner-only aggregate cohort resolver exists'
);

select ok(
  (select count(*) = 3 and bool_and(relrowsecurity and relforcerowsecurity)
   from pg_class as relations
   join pg_namespace as schemas on schemas.oid = relations.relnamespace
   where schemas.nspname = 'analytics'
     and relations.relname in (
       'reviewed_global_aggregate_independent_sources',
       'reviewed_global_aggregate_authorized_source_bindings',
       'reviewed_global_aggregate_input_admissions'
     ))
  and not exists (
    select 1
    from pg_class as relations
    join pg_namespace as schemas on schemas.oid = relations.relnamespace
    where schemas.nspname = 'analytics'
      and relations.relname in (
        'reviewed_global_aggregate_independent_sources',
        'reviewed_global_aggregate_authorized_source_bindings',
        'reviewed_global_aggregate_input_admissions'
      )
      and (
        has_table_privilege('anon', relations.oid, 'select')
        or has_table_privilege('authenticated', relations.oid, 'select')
        or has_table_privilege('service_role', relations.oid, 'select')
        or has_table_privilege(
          'pokecrack_authorized_opening_reviewer', relations.oid, 'select'
        )
        or has_table_privilege('service_role', relations.oid, 'insert')
        or has_table_privilege(
          'pokecrack_authorized_opening_reviewer', relations.oid, 'insert'
        )
      )
  )
  and not exists (
    select 1
    from pg_class as relations
    join pg_namespace as schemas on schemas.oid = relations.relnamespace
    cross join lateral pg_catalog.aclexplode(
      coalesce(relations.relacl, pg_catalog.acldefault('r'::"char", relations.relowner))
    ) as grants
    where schemas.nspname = 'analytics'
      and relations.relname in (
        'reviewed_global_aggregate_independent_sources',
        'reviewed_global_aggregate_authorized_source_bindings',
        'reviewed_global_aggregate_input_admissions'
      )
      and grants.grantee = 0
  ),
  'bridge tables force RLS and grant no browser, service, reviewer, or PUBLIC access'
);

select ok(
  (select proowner = 'postgres'::regrole
     and prosecdef
     and coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_proc
   where oid = 'analytics.reviewed_global_aggregate_cohort_v1(date,date,timestamptz)'::regprocedure)
  and not has_function_privilege(
    'public',
    'analytics.reviewed_global_aggregate_cohort_v1(date,date,timestamptz)'::regprocedure,
    'execute'
  )
  and not has_function_privilege(
    'anon',
    'analytics.reviewed_global_aggregate_cohort_v1(date,date,timestamptz)'::regprocedure,
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'analytics.reviewed_global_aggregate_cohort_v1(date,date,timestamptz)'::regprocedure,
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'analytics.reviewed_global_aggregate_cohort_v1(date,date,timestamptz)'::regprocedure,
    'execute'
  )
  and not has_function_privilege(
    'pokecrack_authorized_opening_reviewer',
    'analytics.reviewed_global_aggregate_cohort_v1(date,date,timestamptz)'::regprocedure,
    'execute'
  ),
  'cohort resolver is postgres-owned SECURITY DEFINER and callable by no application role'
);

select ok(
  (select count(*) = 5
   from analytics.reviewed_global_aggregate_independent_sources
   where (source_key, canonical_domain) in (
     ('public-study-comicbook-v1', 'comicbook.com'),
     ('public-study-wargamer-v1', 'www.wargamer.com'),
     ('public-study-cardchill-v1', 'cardchill.com'),
     ('public-study-bleedingcool-v1', 'bleedingcool.com'),
     ('public-study-tcgtalk-v1', 'tcgtalk.com')
   ))
  and (select count(*) = 5
       from analytics.reviewed_global_aggregate_independent_sources),
  'owner migration declares every current reviewed-public-study host as an explicit source identity'
);

select ok(
  position('source_identity_sha256' in pg_get_function_result(
    'analytics.reviewed_global_aggregate_cohort_v1(date,date,timestamptz)'::regprocedure
  )) = 0
  and position('authorization_reference_sha256' in pg_get_function_result(
    'analytics.reviewed_global_aggregate_cohort_v1(date,date,timestamptz)'::regprocedure
  )) = 0
  and position('evidence_sha256' in pg_get_function_result(
    'analytics.reviewed_global_aggregate_cohort_v1(date,date,timestamptz)'::regprocedure
  )) = 0
  and position('canonical_opening_fingerprint' in pg_get_function_result(
    'analytics.reviewed_global_aggregate_cohort_v1(date,date,timestamptz)'::regprocedure
  )) = 0
  and position('ingest.bluesky' in pg_get_functiondef(
    'analytics.reviewed_global_aggregate_cohort_v1(date,date,timestamptz)'::regprocedure
  )) = 0
  and position('ingest.nostr' in pg_get_functiondef(
    'analytics.reviewed_global_aggregate_cohort_v1(date,date,timestamptz)'::regprocedure
  )) = 0
  and position('ingest.mastodon' in pg_get_functiondef(
    'analytics.reviewed_global_aggregate_cohort_v1(date,date,timestamptz)'::regprocedure
  )) = 0
  and position('ingest.youtube' in pg_get_functiondef(
    'analytics.reviewed_global_aggregate_cohort_v1(date,date,timestamptz)'::regprocedure
  )) = 0,
  'cohort result redacts opaque identity/evidence fields and function never joins social discovery'
);

insert into catalog.sets (
  external_source,
  external_id,
  name,
  slug,
  language,
  release_date,
  series_name,
  is_active,
  is_demo
) values (
  'tcgdex',
  'me03',
  'Perfect Order',
  'pgtap-authorized-cohort-perfect-order',
  'en',
  '2026-03-27',
  'Mega Evolution',
  true,
  false
)
on conflict on constraint sets_external_identity_unique do update
set name = excluded.name,
    slug = excluded.slug,
    release_date = excluded.release_date,
    series_name = excluded.series_name,
    is_active = true,
    is_demo = false,
    updated_at = clock_timestamp();

insert into analytics.reviewed_global_aggregate_independent_sources (
  source_key,
  canonical_domain,
  domain_contract_version,
  domain_contract_sha256
) values
  ('pgtap-authorized-source-one', 'partner-one.example', 'pgtap-domain-v1', repeat('1', 64)),
  ('pgtap-authorized-source-two', 'partner-two.example', 'pgtap-domain-v1', repeat('2', 64));

insert into analytics.reviewed_global_aggregate_authorized_source_bindings (
  binding_key,
  source_identity_sha256,
  authorization_reference_sha256,
  independent_source_key,
  authorization_contract_version,
  authorization_contract_sha256,
  valid_from
) values
  ('pgtap-binding-one', repeat('a', 64), repeat('b', 64),
   'pgtap-authorized-source-one', 'pgtap-authorization-v1', repeat('3', 64),
   clock_timestamp() - interval '3 hours'),
  ('pgtap-binding-one-second', repeat('c', 64), repeat('d', 64),
   'pgtap-authorized-source-one', 'pgtap-authorization-v1', repeat('4', 64),
   clock_timestamp() - interval '3 hours'),
  ('pgtap-binding-two', repeat('e', 64), repeat('f', 64),
   'pgtap-authorized-source-two', 'pgtap-authorization-v1', repeat('5', 64),
   clock_timestamp() - interval '3 hours'),
  ('pgtap-binding-fingerprint', repeat('b', 64), repeat('a', 64),
   'pgtap-authorized-source-one', 'pgtap-authorization-v1', repeat('6', 64),
   clock_timestamp() - interval '3 hours');

insert into ingest.authorized_opening_submissions (
  submission_key,
  discovery_platform,
  source_identity_sha256,
  authorization_reference_sha256,
  evidence_sha256,
  provenance_dedupe_sha256,
  country_code,
  country_name,
  geography_basis,
  geography_confidence,
  language,
  tcgdex_set_id,
  product_scope,
  observed_at,
  pack_count,
  qualifying_hit_pack_count,
  denominator_complete,
  statistics_eligible_requested,
  state,
  revision
) values
  ('pgtap-cohort-accepted-one', 'direct', repeat('a', 64), repeat('b', 64),
   repeat('6', 64), repeat('7', 64), 'US', 'United States', 'opening_location',
   'tier_a', 'en', 'me03', 'all', clock_timestamp() - interval '1 day', 36, 1,
   true, true, 'accepted_statistics', 3),
  ('pgtap-cohort-accepted-two', 'direct', repeat('c', 64), repeat('d', 64),
   repeat('8', 64), repeat('9', 64), 'US', 'United States', 'opening_location',
   'tier_a', 'en', 'me03', 'all', clock_timestamp() - interval '1 day', 36, 1,
   true, true, 'accepted_statistics', 3),
  ('pgtap-cohort-accepted-three', 'direct', repeat('e', 64), repeat('f', 64),
   repeat('0', 64), repeat('1', 64), 'US', 'United States', 'opening_location',
   'tier_a', 'en', 'me03', 'all', clock_timestamp() - interval '1 day', 36, 1,
   true, true, 'accepted_statistics', 3),
  ('pgtap-cohort-unadmitted', 'direct', repeat('7', 64), repeat('8', 64),
   repeat('2', 64), repeat('3', 64), 'US', 'United States', 'opening_location',
   'tier_a', 'en', 'me03', 'all', clock_timestamp() - interval '1 day', 36, 1,
   true, true, 'accepted_statistics', 3),
  ('pgtap-cohort-mismatched-fingerprint', 'direct', repeat('b', 64), repeat('a', 64),
   repeat('4', 64), repeat('c', 64), 'US', 'United States', 'opening_location',
   'tier_a', 'en', 'me03', 'etb', clock_timestamp() - interval '1 day', 36, 1,
   true, true, 'accepted_statistics', 3);

insert into ingest.authorized_opening_observations (
  submission_id,
  submission_key,
  discovery_platform,
  source_identity_sha256,
  authorization_reference_sha256,
  evidence_sha256,
  provenance_dedupe_sha256,
  country_code,
  country_name,
  geography_basis,
  geography_confidence,
  language,
  tcgdex_set_id,
  product_scope,
  observed_at,
  pack_count,
  qualifying_hit_pack_count,
  denominator_complete,
  statistics_eligible,
  methodology_version,
  accepted_at
)
select
  submissions.id,
  submissions.submission_key,
  submissions.discovery_platform,
  submissions.source_identity_sha256,
  submissions.authorization_reference_sha256,
  submissions.evidence_sha256,
  submissions.provenance_dedupe_sha256,
  submissions.country_code,
  submissions.country_name,
  submissions.geography_basis,
  submissions.geography_confidence,
  submissions.language,
  submissions.tcgdex_set_id,
  submissions.product_scope,
  submissions.observed_at,
  submissions.pack_count,
  submissions.qualifying_hit_pack_count,
  submissions.denominator_complete,
  true,
  'authorized-opening-v1',
  clock_timestamp() - interval '1 hour'
from ingest.authorized_opening_submissions as submissions
where submissions.submission_key in (
  'pgtap-cohort-accepted-one',
  'pgtap-cohort-accepted-two',
  'pgtap-cohort-accepted-three',
  'pgtap-cohort-unadmitted',
  'pgtap-cohort-mismatched-fingerprint'
);

insert into analytics.reviewed_global_aggregate_input_admissions (
  admission_key,
  input_kind,
  accepted_observation_id,
  binding_key,
  canonical_opening_fingerprint_sha256,
  admission_contract_version,
  admission_contract_sha256,
  admitted_at
)
select
  values_to_insert.admission_key,
  'authorized_opening',
  observations.id,
  values_to_insert.binding_key,
  values_to_insert.fingerprint,
  'pgtap-admission-v1',
  values_to_insert.contract_hash,
  clock_timestamp() - interval '30 minutes'
from (
  values
    ('pgtap-admission-one', 'pgtap-cohort-accepted-one', 'pgtap-binding-one', repeat('7', 64), repeat('5', 64)),
    ('pgtap-admission-two', 'pgtap-cohort-accepted-two', 'pgtap-binding-one-second', repeat('9', 64), repeat('7', 64)),
    ('pgtap-admission-three', 'pgtap-cohort-accepted-three', 'pgtap-binding-two', repeat('1', 64), repeat('9', 64)),
    ('pgtap-admission-wrong-binding', 'pgtap-cohort-unadmitted', 'pgtap-binding-one', repeat('3', 64), repeat('1', 64)),
    ('pgtap-admission-mismatched-fingerprint', 'pgtap-cohort-mismatched-fingerprint', 'pgtap-binding-fingerprint', repeat('d', 64), repeat('2', 64))
) as values_to_insert(admission_key, submission_key, binding_key, fingerprint, contract_hash)
join ingest.authorized_opening_observations as observations
  on observations.submission_key = values_to_insert.submission_key;

select is(
  (select count(*)::bigint
   from analytics.reviewed_global_aggregate_cohort_v1(
     (statement_timestamp() at time zone 'UTC')::date - 364,
     (statement_timestamp() at time zone 'UTC')::date,
     statement_timestamp()
   ) as cohort
   where cohort.input_kind = 'authorized_opening'),
  3::bigint,
  'only owner-admitted observations with matching opaque binding fields enter the authorized cohort'
);
select is(
  (select count(distinct cohort.independent_source_key)::bigint
   from analytics.reviewed_global_aggregate_cohort_v1(
     (statement_timestamp() at time zone 'UTC')::date - 364,
     (statement_timestamp() at time zone 'UTC')::date,
     statement_timestamp()
   ) as cohort
   where cohort.input_kind = 'authorized_opening'),
  2::bigint,
  'two accepted observations bound to one declared source count as one independent source'
);
select ok(
  not exists (
    select 1
    from analytics.reviewed_global_aggregate_cohort_v1(
      (statement_timestamp() at time zone 'UTC')::date - 364,
      (statement_timestamp() at time zone 'UTC')::date,
      statement_timestamp()
    ) as cohort
    where cohort.input_id = (
      select observations.id::text
      from ingest.authorized_opening_observations as observations
      where observations.submission_key = 'pgtap-cohort-unadmitted'
    )
  ),
  'a matching admission with the wrong HMAC binding fails closed'
);
select ok(
  not exists (
    select 1
    from analytics.reviewed_global_aggregate_cohort_v1(
      (statement_timestamp() at time zone 'UTC')::date - 364,
      (statement_timestamp() at time zone 'UTC')::date,
      statement_timestamp()
    ) as cohort
    where cohort.input_id = (
      select observations.id::text
      from ingest.authorized_opening_observations as observations
      where observations.submission_key = 'pgtap-cohort-mismatched-fingerprint'
    )
  ),
  'an admission fingerprint must equal the immutable authorized provenance fingerprint'
);

select throws_ok(
  $sql$
    insert into analytics.reviewed_global_aggregate_input_admissions (
      admission_key,
      input_kind,
      public_study_key,
      canonical_opening_fingerprint_sha256,
      admission_contract_version,
      admission_contract_sha256
    ) values (
      'pgtap-cross-ledger-collision',
      'public_study',
      'pgtap-public-study-key',
      repeat('7', 64),
      'pgtap-admission-v1',
      repeat('a', 64)
    )
  $sql$,
  '23505',
  null,
  'one canonical fingerprint cannot be admitted through two aggregate input paths'
);
select throws_ok(
  $sql$
    update analytics.reviewed_global_aggregate_authorized_source_bindings
    set independent_source_key = 'pgtap-authorized-source-two'
    where binding_key = 'pgtap-binding-one'
  $sql$,
  '55000',
  'reviewed global aggregate records are immutable',
  'owner-reviewed bindings are immutable once admitted'
);
select throws_ok(
  $sql$
    select *
    from analytics.reviewed_global_aggregate_cohort_v1(
      current_date - 365,
      current_date,
      statement_timestamp()
    )
  $sql$,
  '22023',
  'aggregate cohort window must be a nonfuture UTC period of at most 365 days',
  'resolver rejects an overlong cohort window'
);

insert into ingest.authorized_opening_retractions (
  accepted_observation_id,
  reviewer_reference_sha256,
  reason_code,
  retracted_at
)
select
  observations.id,
  repeat('b', 64),
  'authorization_revoked',
  clock_timestamp()
from ingest.authorized_opening_observations as observations
where observations.submission_key = 'pgtap-cohort-accepted-three';

select is(
  (select count(*)::bigint
   from analytics.reviewed_global_aggregate_cohort_v1(
     (statement_timestamp() at time zone 'UTC')::date - 364,
     (statement_timestamp() at time zone 'UTC')::date,
     (
       select retractions.retracted_at - interval '1 microsecond'
       from ingest.authorized_opening_retractions as retractions
       join ingest.authorized_opening_observations as observations
         on observations.id = retractions.accepted_observation_id
       where observations.submission_key = 'pgtap-cohort-accepted-three'
     )
   ) as cohort
   where cohort.input_kind = 'authorized_opening'),
  3::bigint,
  'as-of resolver reproduces the pre-retraction cohort without mutating its audit facts'
);
select is(
  (select count(*)::bigint
   from analytics.reviewed_global_aggregate_cohort_v1(
     (statement_timestamp() at time zone 'UTC')::date - 364,
     (statement_timestamp() at time zone 'UTC')::date,
     statement_timestamp()
   ) as cohort
   where cohort.input_kind = 'authorized_opening'),
  2::bigint,
  'post-retraction cohort excludes the immutable accepted observation'
);
select ok(
  exists (
    select 1
    from ingest.authorized_opening_observations as observations
    where observations.submission_key = 'pgtap-cohort-accepted-three'
  )
  and exists (
    select 1
    from ingest.authorized_opening_retractions as retractions
    join ingest.authorized_opening_observations as observations
      on observations.id = retractions.accepted_observation_id
    where observations.submission_key = 'pgtap-cohort-accepted-three'
  ),
  'retraction leaves immutable accepted evidence intact for historical reproduction'
);

insert into analytics.reviewed_global_aggregate_authorized_source_bindings (
  binding_key,
  source_identity_sha256,
  authorization_reference_sha256,
  independent_source_key,
  authorization_contract_version,
  authorization_contract_sha256,
  valid_from
) values (
  'pgtap-binding-ambiguous', repeat('a', 64), repeat('e', 64),
  'pgtap-authorized-source-two', 'pgtap-authorization-v1', repeat('f', 64),
  clock_timestamp() - interval '3 hours'
);

select is(
  (select count(*)::bigint
   from analytics.reviewed_global_aggregate_cohort_v1(
     (statement_timestamp() at time zone 'UTC')::date - 364,
     (statement_timestamp() at time zone 'UTC')::date,
     statement_timestamp()
   ) as cohort
   where cohort.input_kind = 'authorized_opening'),
  1::bigint,
  'an identity bound to conflicting independent sources fails closed instead of inflating source diversity'
);
select ok(
  not exists (
    select 1
    from analytics.reviewed_global_aggregate_cohort_v1(
      (statement_timestamp() at time zone 'UTC')::date - 364,
      (statement_timestamp() at time zone 'UTC')::date,
      statement_timestamp()
    ) as cohort
    where cohort.input_id = (
      select observations.id::text
      from ingest.authorized_opening_observations as observations
      where observations.submission_key = 'pgtap-cohort-accepted-one'
    )
  ),
  'ambiguous identity bindings exclude every affected authorized observation'
);

select finish();
rollback;
