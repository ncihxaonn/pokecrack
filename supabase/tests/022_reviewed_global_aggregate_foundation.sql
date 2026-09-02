-- Private foundation for the later fenced reviewed-global publisher.  This
-- suite intentionally proves that no public rate path exists yet.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select has_table(
  'analytics',
  'reviewed_global_aggregate_baselines',
  'private immutable baseline contracts exist'
);
select has_table(
  'analytics',
  'reviewed_global_aggregate_audit',
  'private immutable aggregate audit records exist'
);
select has_column(
  'analytics', 'reviewed_global_aggregate_audit', 'qualifying_hit_pack_count',
  'the numerator is retained only in the private audit ledger'
);
select has_column(
  'analytics', 'reviewed_global_aggregate_audit', 'source_domain_set_sha256',
  'the audit stores a hashed independent-domain set instead of public source identities'
);
select has_column(
  'analytics', 'reviewed_global_aggregate_audit', 'cohort_fingerprint_sha256',
  'the audit stores a deterministic cohort fingerprint'
);
select has_column(
  'analytics', 'reviewed_global_aggregate_audit', 'withhold_reason',
  'withheld results retain a private explicit reason'
);

select ok(
  (select relations.relrowsecurity and relations.relforcerowsecurity
   from pg_class as relations
   join pg_namespace as schemas on schemas.oid = relations.relnamespace
   where schemas.nspname = 'analytics'
     and relations.relname = 'reviewed_global_aggregate_baselines'),
  'baseline contracts use FORCE RLS'
);
select ok(
  (select relations.relrowsecurity and relations.relforcerowsecurity
   from pg_class as relations
   join pg_namespace as schemas on schemas.oid = relations.relnamespace
   where schemas.nspname = 'analytics'
     and relations.relname = 'reviewed_global_aggregate_audit'),
  'aggregate audit records use FORCE RLS'
);
select is(
  (select count(*)::integer
   from pg_policies
   where schemaname = 'analytics'
     and tablename in (
       'reviewed_global_aggregate_baselines',
       'reviewed_global_aggregate_audit'
     )),
  0,
  'no browser or service-role policy can read the private aggregate foundation'
);
select ok(
  not exists (
    select 1
    from pg_class as relations
    join pg_namespace as schemas on schemas.oid = relations.relnamespace
    cross join unnest(array['service_role', 'anon', 'authenticated'])
      as application_roles(role_name)
    cross join unnest(array[
      'select', 'insert', 'update', 'delete', 'truncate', 'references',
      'trigger', 'maintain'
    ]) as table_privileges(privilege_name)
    where schemas.nspname = 'analytics'
      and relations.relname in (
        'reviewed_global_aggregate_baselines',
        'reviewed_global_aggregate_audit'
      )
      and has_table_privilege(
        application_roles.role_name,
        relations.oid,
        table_privileges.privilege_name
      )
  ),
  'no application role has any direct private baseline or numerator-ledger table capability'
);
select ok(
  exists (
    select 1
    from pg_trigger as triggers
    join pg_class as relations on relations.oid = triggers.tgrelid
    join pg_namespace as schemas on schemas.oid = relations.relnamespace
    where schemas.nspname = 'analytics'
      and relations.relname = 'reviewed_global_aggregate_baselines'
      and triggers.tgname = 'reviewed_global_aggregate_baselines_immutable'
      and not triggers.tgisinternal
  )
  and exists (
    select 1
    from pg_trigger as triggers
    join pg_class as relations on relations.oid = triggers.tgrelid
    join pg_namespace as schemas on schemas.oid = relations.relnamespace
    where schemas.nspname = 'analytics'
      and relations.relname = 'reviewed_global_aggregate_audit'
      and triggers.tgname = 'reviewed_global_aggregate_audit_immutable'
      and not triggers.tgisinternal
  ),
  'both private ledgers reject update/delete mutations'
);

select is(
  (select count(*)::integer
   from pg_trigger as triggers
   join pg_class as relations on relations.oid = triggers.tgrelid
   join pg_namespace as schemas on schemas.oid = relations.relnamespace
   where schemas.nspname = 'analytics'
     and relations.relname in (
       'reviewed_global_aggregate_baselines',
       'reviewed_global_aggregate_audit'
     )
     and triggers.tgname in (
       'reviewed_global_aggregate_baselines_immutable',
       'reviewed_global_aggregate_audit_immutable'
     )
     and not triggers.tgisinternal
     and triggers.tgfoid =
       'analytics.reject_reviewed_global_aggregate_mutation_v1()'::regprocedure
     and (triggers.tgtype::integer & 1) <> 0
     and (triggers.tgtype::integer & 2) <> 0
     and (triggers.tgtype::integer & 8) <> 0
     and (triggers.tgtype::integer & 16) <> 0),
  2,
  'both immutable triggers are owner-bound BEFORE row triggers for update and delete'
);

select ok(
  (select pg_get_constraintdef(constraints.oid) ilike '%publication_state%'
      and pg_get_constraintdef(constraints.oid) ilike '%withheld%'
      and pg_get_constraintdef(constraints.oid) ilike '%withhold_reason is not null%'
      and pg_get_constraintdef(constraints.oid) not ilike '%calculated%'
   from pg_constraint as constraints
   where constraints.conrelid = to_regclass('analytics.reviewed_global_aggregate_audit')
     and constraints.conname = 'reviewed_global_aggregate_audit_state_check'),
  'the foundation permits only explicitly reasoned withheld audit rows'
);

select ok(
  not has_function_privilege(
    'service_role',
    'analytics.reject_reviewed_global_aggregate_mutation_v1()'::regprocedure,
    'execute'
  )
  and not has_function_privilege(
    'anon',
    'analytics.reject_reviewed_global_aggregate_mutation_v1()'::regprocedure,
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'analytics.reject_reviewed_global_aggregate_mutation_v1()'::regprocedure,
    'execute'
  ),
  'the private immutability trigger helper is not directly executable by application roles'
);

select lives_ok(
  $sql$
    insert into analytics.reviewed_global_aggregate_baselines (
      baseline_id,
      baseline_version,
      metric_key,
      metric_version,
      set_external_id,
      language,
      product_scope,
      baseline_rate,
      provenance_sha256,
      contract_sha256,
      valid_from
    ) values (
      'pgtap-global-baseline-v1',
      'pgtap-v1',
      'qualifying_hit_pack_rate',
      'pgtap-v1',
      'pgtap-set',
      'en',
      'all',
      0.05::numeric,
      repeat('a', 64),
      repeat('b', 64),
      date '2026-01-01'
    )
  $sql$,
  'the owner-side test fixture can seed one valid private baseline contract'
);
select lives_ok(
  $sql$
    insert into analytics.reviewed_global_aggregate_audit (
      aggregate_key,
      country_code,
      period_start,
      period_end,
      language,
      set_scope,
      product_scope,
      metric_key,
      metric_version,
      methodology_version,
      publication_contract_version,
      calculation_implementation_version,
      source_domain_set_sha256,
      cohort_fingerprint_sha256,
      independent_source_count,
      complete_openings,
      observed_packs,
      qualifying_hit_pack_count,
      publication_state,
      withhold_reason,
      build_sha
    ) values (
      'pgtap-global-audit-us-v1',
      'US',
      date '2025-09-03',
      date '2026-09-02',
      'en',
      'all',
      'all',
      'qualifying_hit_pack_rate',
      'pgtap-v1',
      'pgtap-v1',
      'pgtap-v1',
      'pgtap-v1',
      repeat('c', 64),
      repeat('d', 64),
      1,
      1,
      1,
      0,
      'withheld',
      'insufficient_sample',
      'abcdef0'
    )
  $sql$,
  'the owner-side test fixture can seed one valid explicitly withheld private audit row'
);
select throws_ok(
  $$
    update analytics.reviewed_global_aggregate_baselines
    set baseline_rate = 0.06::numeric
    where baseline_id = 'pgtap-global-baseline-v1'
  $$,
  '55000',
  'reviewed global aggregate records are immutable',
  'the baseline contract trigger rejects owner-side updates'
);
select throws_ok(
  $$
    delete from analytics.reviewed_global_aggregate_audit
    where aggregate_key = 'pgtap-global-audit-us-v1'
  $$,
  '55000',
  'reviewed global aggregate records are immutable',
  'the aggregate audit trigger rejects owner-side deletes'
);

select has_function(
  'analytics',
  'reviewed_global_beta_parameters_v1',
  array['bigint', 'bigint', 'numeric', 'numeric'],
  'the exact posterior-parameter helper exists'
);
select ok(
  (select procedures.proowner::regrole::text = 'postgres'
      and not procedures.prosecdef
      and procedures.provolatile = 'i'
      and procedures.proparallel = 's'
      and coalesce(procedures.proconfig, '{}'::text[])
        @> array['search_path=pg_catalog']
   from pg_proc as procedures
   where procedures.oid =
     'analytics.reviewed_global_beta_parameters_v1(bigint,bigint,numeric,numeric)'::regprocedure),
  'the posterior helper is postgres-owned, immutable, invoker-safe, and fixed-search-path'
);
select ok(
  not has_function_privilege(
    'service_role',
    'analytics.reviewed_global_beta_parameters_v1(bigint,bigint,numeric,numeric)'::regprocedure,
    'execute'
  )
  and not has_function_privilege(
    'anon',
    'analytics.reviewed_global_beta_parameters_v1(bigint,bigint,numeric,numeric)'::regprocedure,
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'analytics.reviewed_global_beta_parameters_v1(bigint,bigint,numeric,numeric)'::regprocedure,
    'execute'
  ),
  'only a future owner-controlled publisher can call the private posterior helper'
);
select is(
  (select alpha
   from analytics.reviewed_global_beta_parameters_v1(1, 10, 0.1::numeric, 50::numeric)),
  6::numeric,
  'posterior alpha exactly matches the documented Beta prior plus hits'
);
select is(
  (select beta
   from analytics.reviewed_global_beta_parameters_v1(1, 10, 0.1::numeric, 50::numeric)),
  54::numeric,
  'posterior beta exactly matches the documented Beta prior plus non-hits'
);
select is(
  (select posterior_mean
   from analytics.reviewed_global_beta_parameters_v1(1, 10, 0.1::numeric, 50::numeric)),
  0.1::numeric,
  'posterior mean uses exact documented arithmetic'
);
select throws_ok(
  $$select * from analytics.reviewed_global_beta_parameters_v1(11, 10, 0.1::numeric, 50::numeric)$$,
  '22023',
  'hits must satisfy 0 <= hits <= packs',
  'invalid numerator/denominator inputs fail closed'
);
select throws_ok(
  $$select * from analytics.reviewed_global_beta_parameters_v1(0, 0, 0.1::numeric, 50::numeric)$$,
  '22023',
  'hits must satisfy 0 <= hits <= packs',
  'zero-pack inputs fail closed rather than manufacturing a publication cohort'
);
select throws_ok(
  $$select * from analytics.reviewed_global_beta_parameters_v1(1, 10, 1::numeric, 50::numeric)$$,
  '22023',
  'baseline rate must be strictly between zero and one',
  'invalid baselines fail closed'
);
select throws_ok(
  $$select * from analytics.reviewed_global_beta_parameters_v1(1, 10, 'NaN'::numeric, 50::numeric)$$,
  '22023',
  'baseline rate must be strictly between zero and one',
  'non-finite baselines fail closed'
);
select throws_ok(
  $$select * from analytics.reviewed_global_beta_parameters_v1(1, 10, 0.1::numeric, 'Infinity'::numeric)$$,
  '22023',
  'prior strength must be positive',
  'non-finite prior strengths fail closed'
);

select ok(
  not exists (
    select 1
    from pg_proc as procedures
    join pg_namespace as schemas on schemas.oid = procedures.pronamespace
    where schemas.nspname = 'analytics'
      and procedures.proname like 'reviewed_global_%'
      and pg_get_functiondef(procedures.oid) ilike '%country_period_map_cells%'
  ),
  'foundation functions cannot mutate or query the browser map'
);

select * from finish();
rollback;
