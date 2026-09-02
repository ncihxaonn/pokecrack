-- The authorized-opening reviewer boundary is deliberately private. This
-- suite exercises its four RPCs under their runtime roles and proves that an
-- accepted opening remains an immutable, retractable audit fact rather than a
-- browser-readable dashboard record.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select has_table(
  'ingest',
  'authorized_opening_submissions',
  'private authorized-opening submission queue exists'
);
select has_table(
  'ingest',
  'authorized_opening_review_events',
  'private immutable reviewer event ledger exists'
);
select has_table(
  'ingest',
  'authorized_opening_observations',
  'private immutable accepted-observation ledger exists'
);
select has_table(
  'ingest',
  'authorized_opening_retractions',
  'private immutable retraction ledger exists'
);

select ok(
  exists (
    select 1
    from pg_roles as roles
    where roles.rolname = 'pokecrack_authorized_opening_reviewer'
      and not roles.rolsuper
      and not roles.rolcanlogin
      and not roles.rolinherit
      and not roles.rolcreatedb
      and not roles.rolcreaterole
      and not roles.rolreplication
      and not roles.rolbypassrls
      and roles.rolconnlimit = -1
      and roles.rolconfig is null
  ),
  'reviewer capability is a no-login, no-inherit, non-escalating database role'
);

select ok(
  (select count(*) = 4
   from pg_class as relations
   join pg_namespace as schemas on schemas.oid = relations.relnamespace
   where schemas.nspname = 'ingest'
     and relations.relkind in ('r', 'p')
     and relations.relname in (
       'authorized_opening_submissions',
       'authorized_opening_review_events',
       'authorized_opening_observations',
       'authorized_opening_retractions'
     ))
  and (select bool_and(relations.relrowsecurity and relations.relforcerowsecurity)
       from pg_class as relations
       join pg_namespace as schemas on schemas.oid = relations.relnamespace
       where schemas.nspname = 'ingest'
         and relations.relname in (
           'authorized_opening_submissions',
           'authorized_opening_review_events',
           'authorized_opening_observations',
           'authorized_opening_retractions'
         ))
  and (select count(*) = 4
       from pg_policies as policies
       where policies.schemaname = 'ingest'
         and policies.tablename in (
           'authorized_opening_submissions',
           'authorized_opening_review_events',
           'authorized_opening_observations',
           'authorized_opening_retractions'
         )
         and policies.roles = array['service_role']::name[]
         and policies.cmd = 'SELECT')
  and not exists (
    select 1
    from pg_class as relations
    join pg_namespace as schemas on schemas.oid = relations.relnamespace
    where schemas.nspname = 'ingest'
      and relations.relname in (
        'authorized_opening_submissions',
        'authorized_opening_review_events',
        'authorized_opening_observations',
        'authorized_opening_retractions'
      )
      and (
        has_table_privilege('anon', relations.oid, 'select')
        or has_table_privilege('authenticated', relations.oid, 'select')
        or has_table_privilege(
          'pokecrack_authorized_opening_reviewer', relations.oid, 'select'
        )
        or has_table_privilege(
          'pokecrack_authorized_opening_reviewer', relations.oid, 'insert'
        )
        or has_table_privilege(
          'pokecrack_authorized_opening_reviewer', relations.oid, 'update'
        )
        or has_table_privilege(
          'pokecrack_authorized_opening_reviewer', relations.oid, 'delete'
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
    where schemas.nspname = 'ingest'
      and relations.relname in (
        'authorized_opening_submissions',
        'authorized_opening_review_events',
        'authorized_opening_observations',
        'authorized_opening_retractions'
      )
      and grants.grantee = 0
  ),
  'reviewer ledgers force RLS and never grant direct browser, reviewer, or PUBLIC table access'
);

select ok(
  (select bool_and(
      has_table_privilege('service_role', relations.oid, 'select')
      and not has_table_privilege('service_role', relations.oid, 'insert')
      and not has_table_privilege('service_role', relations.oid, 'update')
      and not has_table_privilege('service_role', relations.oid, 'delete')
      and not has_table_privilege('service_role', relations.oid, 'truncate')
      and not has_table_privilege('service_role', relations.oid, 'references')
      and not has_table_privilege('service_role', relations.oid, 'trigger')
      and not has_table_privilege('service_role', relations.oid, 'maintain')
    )
   from pg_class as relations
   join pg_namespace as schemas on schemas.oid = relations.relnamespace
   where schemas.nspname = 'ingest'
     and relations.relname in (
       'authorized_opening_submissions',
       'authorized_opening_review_events',
       'authorized_opening_observations',
       'authorized_opening_retractions'
     )),
  'service_role can only read reviewer ledgers and must use the typed submit RPC to write'
);

select ok(
  has_function_privilege(
    'service_role', 'ingest.submit_authorized_opening_v1(jsonb)'::regprocedure, 'execute'
  )
  and not has_function_privilege(
    'anon', 'ingest.submit_authorized_opening_v1(jsonb)'::regprocedure, 'execute'
  )
  and not has_function_privilege(
    'authenticated', 'ingest.submit_authorized_opening_v1(jsonb)'::regprocedure, 'execute'
  )
  and not has_function_privilege(
    'pokecrack_authorized_opening_reviewer',
    'ingest.submit_authorized_opening_v1(jsonb)'::regprocedure,
    'execute'
  ),
  'submit RPC is callable only by service_role'
);

select ok(
  (select bool_and(
      has_function_privilege(
        'pokecrack_authorized_opening_reviewer', functions.oid, 'execute'
      )
      and not has_function_privilege('service_role', functions.oid, 'execute')
      and not has_function_privilege('anon', functions.oid, 'execute')
      and not has_function_privilege('authenticated', functions.oid, 'execute')
    )
   from unnest(array[
     'ingest.list_authorized_opening_reviews_v1(text,integer)'::regprocedure,
     'ingest.review_authorized_opening_v1(uuid,bigint,text,text,text)'::regprocedure,
     'ingest.retract_authorized_opening_v1(uuid,text,text)'::regprocedure
   ]) as functions(oid)),
  'list, review, and retract RPCs are callable only by the dedicated reviewer role'
);

select ok(
  (select count(*) = 4 and bool_and(
      functions.proowner = 'postgres'::regrole
      and functions.prosecdef
      and coalesce(functions.proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
    )
   from pg_proc as functions
   where functions.oid = any(array[
     'ingest.submit_authorized_opening_v1(jsonb)'::regprocedure,
     'ingest.list_authorized_opening_reviews_v1(text,integer)'::regprocedure,
     'ingest.review_authorized_opening_v1(uuid,bigint,text,text,text)'::regprocedure,
     'ingest.retract_authorized_opening_v1(uuid,text,text)'::regprocedure
   ])),
  'all reviewer-boundary RPCs are postgres-owned SECURITY DEFINER functions with a fixed search path'
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
  'pgtap-authorized-opening-perfect-order',
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

set local role service_role;
select throws_ok(
  $sql$
    select *
    from ingest.submit_authorized_opening_v1(
      jsonb_build_object(
        'schemaVersion', '1.0.0',
        'submissionKey', 'pgtap-authorized-opening-invalid',
        'discoveryPlatform', 'direct',
        'discoveryCandidateSha256', null,
        'sourceIdentitySha256', repeat('0', 64),
        'authorizationReferenceSha256', repeat('1', 64),
        'evidenceSha256', repeat('2', 64),
        'provenanceDedupeSha256', repeat('3', 64),
        'countryCode', 'US',
        'countryName', 'United States',
        'geographyBasis', 'opening_location',
        'geographyConfidence', 'tier_a',
        'language', 'en',
        'tcgdexSetId', 'me03',
        'productScope', 'all',
        'observedAt', '2026-04-01T00:00:00Z',
        'packCount', 36,
        'qualifyingHitPackCount', 1,
        'denominatorComplete', true,
        'statisticsEligible', true,
        'unexpected', true
      )
    )
  $sql$,
  '22023',
  'authorized opening payload must match the exact bounded v1 contract',
  'service-role submit rejects an extra payload field before touching the queue'
);

select set_config(
  'pokecrack.authorized_opening_submission_id',
  (
    select submission_id::text
    from ingest.submit_authorized_opening_v1(
      jsonb_build_object(
        'schemaVersion', '1.0.0',
        'submissionKey', 'pgtap-authorized-opening-1',
        'discoveryPlatform', 'direct',
        'discoveryCandidateSha256', null,
        'sourceIdentitySha256', repeat('a', 64),
        'authorizationReferenceSha256', repeat('b', 64),
        'evidenceSha256', repeat('c', 64),
        'provenanceDedupeSha256', repeat('d', 64),
        'countryCode', 'US',
        'countryName', 'United States',
        'geographyBasis', 'opening_location',
        'geographyConfidence', 'tier_a',
        'language', 'en',
        'tcgdexSetId', 'me03',
        'productScope', 'all',
        'observedAt', '2026-04-01T00:00:00Z',
        'packCount', 36,
        'qualifyingHitPackCount', 1,
        'denominatorComplete', true,
        'statisticsEligible', true
      )
    )
  ),
  true
);
select is(
  (
    select submission_id::text
    from ingest.submit_authorized_opening_v1(
      jsonb_build_object(
        'schemaVersion', '1.0.0',
        'submissionKey', 'pgtap-authorized-opening-1',
        'discoveryPlatform', 'direct',
        'discoveryCandidateSha256', null,
        'sourceIdentitySha256', repeat('a', 64),
        'authorizationReferenceSha256', repeat('b', 64),
        'evidenceSha256', repeat('c', 64),
        'provenanceDedupeSha256', repeat('d', 64),
        'countryCode', 'US',
        'countryName', 'United States',
        'geographyBasis', 'opening_location',
        'geographyConfidence', 'tier_a',
        'language', 'en',
        'tcgdexSetId', 'me03',
        'productScope', 'all',
        'observedAt', '2026-04-01T00:00:00Z',
        'packCount', 36,
        'qualifyingHitPackCount', 1,
        'denominatorComplete', true,
        'statisticsEligible', true
      )
    )
  ),
  current_setting('pokecrack.authorized_opening_submission_id'),
  'identical service-role submission replay returns the original immutable queue row'
);
select throws_ok(
  $sql$
    insert into ingest.authorized_opening_submissions (submission_key)
    values ('pgtap-direct-write-must-fail')
  $sql$,
  '42501',
  'permission denied for table authorized_opening_submissions',
  'service_role cannot directly write the reviewer queue'
);
reset role;
grant pokecrack_authorized_opening_reviewer to current_user
  with inherit false, set true;

select ok(
  exists (
    select 1
    from ingest.authorized_opening_submissions as submissions
    where submissions.id = current_setting('pokecrack.authorized_opening_submission_id')::uuid
      and submissions.state = 'queued'
      and submissions.revision = 1
      and submissions.country_code = 'US'
      and submissions.country_name = 'United States'
      and submissions.pack_count = 36
      and submissions.qualifying_hit_pack_count = 1
  )
  and (select count(*) = 1
       from ingest.authorized_opening_review_events as events
       where events.submission_id = current_setting('pokecrack.authorized_opening_submission_id')::uuid
         and events.from_state is null
         and events.to_state = 'queued'
         and events.reason_code = 'submitted'),
  'submit atomically persists exactly one queued submission and its immutable creation event'
);

set local role pokecrack_authorized_opening_reviewer;
select is(
  (
    select count(*)::integer
    from ingest.list_authorized_opening_reviews_v1('queued', 10)
  ),
  1,
  'reviewer can list the bounded queued-review projection'
);
select doesnt_match(
  (
    select coalesce(jsonb_agg(to_jsonb(rows))::text, '[]')
    from ingest.list_authorized_opening_reviews_v1('queued', 10) as rows
  ),
  '(?i)(submission_key|sha256|evidence|authorization|source_identity|provenance)',
  'reviewer list projection never returns opaque identity, authorization, evidence, or dedupe references'
);
select throws_ok(
  $sql$select * from ingest.authorized_opening_submissions$sql$,
  '42501',
  'permission denied for table authorized_opening_submissions',
  'reviewer cannot bypass the bounded list RPC with a direct ledger read'
);

select set_config(
  'pokecrack.authorized_opening_in_review_revision',
  (
    select revision::text
    from ingest.review_authorized_opening_v1(
      current_setting('pokecrack.authorized_opening_submission_id')::uuid,
      1,
      'in_review',
      repeat('e', 64),
      'review_started'
    )
  ),
  true
);
select is(
  current_setting('pokecrack.authorized_opening_in_review_revision'),
  '2',
  'reviewer moves a queued submission to in_review through the revision-fenced RPC'
);

select set_config(
  'pokecrack.authorized_opening_observation_id',
  (
    select accepted_observation_id::text
    from ingest.review_authorized_opening_v1(
      current_setting('pokecrack.authorized_opening_submission_id')::uuid,
      2,
      'accepted_statistics',
      repeat('f', 64),
      'evidence_verified'
    )
  ),
  true
);
select ok(
  nullif(current_setting('pokecrack.authorized_opening_observation_id'), '') is not null,
  'accepted-statistics review atomically creates an immutable accepted observation'
);
select throws_ok(
  $sql$
    select *
    from ingest.review_authorized_opening_v1(
      current_setting('pokecrack.authorized_opening_submission_id')::uuid,
      2,
      'rejected',
      repeat('0', 64),
      'reviewer_rejected'
    )
  $sql$,
  '40001',
  'authorized opening review revision is stale',
  'reviewer cannot overwrite an accepted decision with a stale revision'
);
reset role;

select ok(
  exists (
    select 1
    from ingest.authorized_opening_submissions as submissions
    where submissions.id = current_setting('pokecrack.authorized_opening_submission_id')::uuid
      and submissions.state = 'accepted_statistics'
      and submissions.revision = 3
  )
  and exists (
    select 1
    from ingest.authorized_opening_observations as observations
    where observations.id = current_setting('pokecrack.authorized_opening_observation_id')::uuid
      and observations.submission_id = current_setting('pokecrack.authorized_opening_submission_id')::uuid
      and observations.statistics_eligible
      and observations.pack_count = 36
      and observations.qualifying_hit_pack_count = 1
  )
  and (select count(*) = 3
       from ingest.authorized_opening_review_events as events
       where events.submission_id = current_setting('pokecrack.authorized_opening_submission_id')::uuid),
  'acceptance preserves the review history and writes one private statistics-eligible observation'
);
select throws_ok(
  $sql$
    update ingest.authorized_opening_observations
    set pack_count = 35
    where id = current_setting('pokecrack.authorized_opening_observation_id')::uuid
  $sql$,
  '55000',
  'authorized opening audit and observation rows are immutable',
  'accepted observations remain immutable even for the database owner'
);

set local role pokecrack_authorized_opening_reviewer;
select set_config(
  'pokecrack.authorized_opening_retracted_at',
  (
    select retracted_at::text
    from ingest.retract_authorized_opening_v1(
      current_setting('pokecrack.authorized_opening_observation_id')::uuid,
      repeat('1', 64),
      'authorization_revoked'
    )
  ),
  true
);
select is(
  (
    select retracted_at::text
    from ingest.retract_authorized_opening_v1(
      current_setting('pokecrack.authorized_opening_observation_id')::uuid,
      repeat('1', 64),
      'authorization_revoked'
    )
  ),
  current_setting('pokecrack.authorized_opening_retracted_at'),
  'identical reviewer retraction replay is idempotent and preserves its original audit timestamp'
);
reset role;
revoke pokecrack_authorized_opening_reviewer from current_user;

select ok(
  (select count(*) = 1
   from ingest.authorized_opening_retractions as retractions
   where retractions.accepted_observation_id
       = current_setting('pokecrack.authorized_opening_observation_id')::uuid
     and retractions.reason_code = 'authorization_revoked')
  and exists (
    select 1
    from ingest.authorized_opening_observations as observations
    where observations.id = current_setting('pokecrack.authorized_opening_observation_id')::uuid
  ),
  'retraction appends one private takedown fact without deleting the immutable accepted observation'
);

select finish();
rollback;
