-- Forward migration 100 gives Nostr its own queue capability and deploy-only
-- attestation identity.  Neither role inherits service_role or reads ledgers.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

create role pokecrack_nostr_attestor_login
  login
  noinherit
  nosuperuser
  nocreatedb
  nocreaterole
  noreplication
  nobypassrls
  connection limit 2;
grant pokecrack_nostr_attestor to pokecrack_nostr_attestor_login
  with inherit false, set true;

create role pokecrack_nostr_worker_login
  login
  noinherit
  nosuperuser
  nocreatedb
  nocreaterole
  noreplication
  nobypassrls
  connection limit 2;
grant pokecrack_nostr_worker to pokecrack_nostr_worker_login
  with inherit false, set true;

select has_function(
  'ingest', 'enqueue_due_nostr_relay_jobs_v1', array['text'],
  'the isolated Nostr capability owns its current-minute schedule'
);
select has_function(
  'ingest', 'claim_nostr_relay_jobs_v1', array['text', 'integer'],
  'the isolated Nostr capability has an exact claim wrapper'
);
select has_function(
  'ingest', 'heartbeat_nostr_relay_job_v1',
  array['uuid', 'text', 'bigint', 'integer'],
  'the isolated Nostr capability has an exact heartbeat wrapper'
);
select has_function(
  'ingest', 'fail_nostr_relay_job_v1',
  array['uuid', 'text', 'bigint', 'text', 'text', 'boolean'],
  'the isolated Nostr capability has an exact failure wrapper'
);
select has_function(
  'ingest', 'pause_nostr_relay_job_v1',
  array['uuid', 'text', 'bigint', 'timestamptz'],
  'the isolated Nostr capability has an exact pause wrapper'
);
select has_function(
  'ingest', 'upsert_nostr_worker_heartbeat_v1',
  array['text', 'text', 'jsonb'],
  'the isolated Nostr capability has an exact health wrapper'
);
select has_function(
  'ingest', 'nostr_worker_runtime_ready_v1', array[]::text[],
  'the isolated Nostr capability has a boolean-only runtime contract proof'
);
select has_function(
  'ingest', 'get_nostr_worker_policy_snapshot_v1', array[]::text[],
  'the isolated Nostr capability has a reviewed policy-only projection'
);
select has_function(
  'ingest', 'verify_nostr_release_v2', array[]::text[],
  'the release preflight uses the version-two attestation'
);

select ok(
  (select prosecdef
      and coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_catalog.pg_proc
   where oid = 'ingest.verify_nostr_release_v2()'::regprocedure),
  'the version-two attestation is SECURITY DEFINER with a fixed search_path'
);
select set_eq(
  $$select coalesce(grantees.rolname, 'public')::text
    from pg_catalog.pg_proc as procedures
    cross join lateral aclexplode(
      coalesce(procedures.proacl, acldefault('f', procedures.proowner))
    ) as grants
    left join pg_catalog.pg_roles as grantees on grantees.oid = grants.grantee
    where procedures.oid = 'ingest.verify_nostr_release_v2()'::regprocedure
      and grants.privilege_type = 'EXECUTE'$$,
  $$values ('postgres'::text), ('pokecrack_nostr_attestor')$$,
  'only postgres and the exact attestor group can execute the release proof'
);
select ok(
  not has_function_privilege(
      'service_role', 'ingest.verify_nostr_release_v2()', 'execute'
    )
    and not has_function_privilege(
      'pokecrack_nostr_worker', 'ingest.verify_nostr_release_v2()', 'execute'
    )
    and not has_function_privilege(
      'pokecrack_nostr_attestor_login',
      'ingest.verify_nostr_release_v2()', 'execute'
    ),
  'service, worker, and NOINHERIT login identities cannot call the attestation directly'
);

select ok(
  (select
    not rolsuper and not rolinherit and not rolcreaterole and not rolcreatedb
      and not rolcanlogin and not rolreplication and not rolbypassrls
      and rolconnlimit = -1
   from pg_catalog.pg_roles where rolname = 'pokecrack_nostr_worker'),
  'the Nostr worker group is exact NOLOGIN NOINHERIT least privilege'
);
select ok(
  (select
    not rolsuper and not rolinherit and not rolcreaterole and not rolcreatedb
      and rolcanlogin and not rolreplication and not rolbypassrls
      and rolconnlimit = 2
   from pg_catalog.pg_roles where rolname = 'pokecrack_nostr_worker_login')
    and (select count(*) = 1 and bool_and(
      not memberships.admin_option
        and not memberships.inherit_option
        and memberships.set_option
    )
    from pg_catalog.pg_auth_members as memberships
    join pg_catalog.pg_roles as parent on parent.oid = memberships.roleid
    join pg_catalog.pg_roles as member on member.oid = memberships.member
    where parent.rolname = 'pokecrack_nostr_worker'
      and member.rolname = 'pokecrack_nostr_worker_login'),
  'the worker login can SET exactly one non-inherited Nostr capability'
);

select ok(
  (select count(*) = 10 and bool_and(
      has_function_privilege('pokecrack_nostr_worker', signatures.signature, 'execute')
      and not has_function_privilege('service_role', signatures.signature, 'execute')
      and not has_function_privilege('anon', signatures.signature, 'execute')
      and not has_function_privilege('authenticated', signatures.signature, 'execute')
    )
   from (values
      ('ingest.enqueue_due_nostr_relay_jobs_v1(text)'::text),
      ('ingest.claim_nostr_relay_jobs_v1(text,integer)'::text),
      ('ingest.heartbeat_nostr_relay_job_v1(uuid,text,bigint,integer)'),
      ('ingest.fail_nostr_relay_job_v1(uuid,text,bigint,text,text,boolean)'),
      ('ingest.pause_nostr_relay_job_v1(uuid,text,bigint,timestamp with time zone)'),
      ('ingest.upsert_nostr_worker_heartbeat_v1(text,text,jsonb)'),
      ('ingest.nostr_worker_runtime_ready_v1()'),
      ('ingest.get_nostr_worker_policy_snapshot_v1()'),
      ('ingest.begin_nostr_relay_job(uuid,text,bigint,text)'),
      ('ingest.finalize_nostr_relay_job(uuid,text,bigint,jsonb)')
   ) as signatures(signature)),
  'exactly ten Nostr-only RPCs belong to the isolated capability, never service_role'
);
select ok(
  (select prosecdef
      and coalesce(proconfig, '{}'::text[]) @> array['search_path=pg_catalog']
   from pg_catalog.pg_proc
   where oid = 'ingest.nostr_worker_runtime_ready_v1()'::regprocedure),
  'the runtime proof is SECURITY DEFINER with a fixed search_path'
);
select set_eq(
  $$select coalesce(grantees.rolname, 'public')::text
    from pg_catalog.pg_proc as procedures
    cross join lateral aclexplode(
      coalesce(procedures.proacl, acldefault('f', procedures.proowner))
    ) as grants
    left join pg_catalog.pg_roles as grantees on grantees.oid = grants.grantee
    where procedures.oid = 'ingest.nostr_worker_runtime_ready_v1()'::regprocedure
      and grants.privilege_type = 'EXECUTE'$$,
  $$values ('postgres'::text), ('pokecrack_nostr_worker')$$,
  'only postgres and the isolated worker group can execute the runtime proof'
);
select set_eq(
  $$select coalesce(grantees.rolname, 'public')::text
    from pg_catalog.pg_proc as procedures
    cross join lateral aclexplode(
      coalesce(procedures.proacl, acldefault('f', procedures.proowner))
    ) as grants
    left join pg_catalog.pg_roles as grantees on grantees.oid = grants.grantee
    where procedures.oid =
      'ingest.get_nostr_worker_policy_snapshot_v1()'::regprocedure
      and grants.privilege_type = 'EXECUTE'$$,
  $$values ('postgres'::text), ('pokecrack_nostr_worker')$$,
  'only postgres and the isolated worker group can execute the policy projection'
);
select is(
  (select count(*) from ingest.get_nostr_worker_policy_snapshot_v1()),
  3::bigint,
  'the policy projection exposes only the three reviewed relay contracts'
);
select set_eq(
  $$select distinct jsonb_object_keys(to_jsonb(snapshot))
    from ingest.get_nostr_worker_policy_snapshot_v1() as snapshot$$,
  $$values
    ('source_key'), ('display_name'), ('source_kind'), ('domain'), ('base_url'),
    ('enabled'), ('collector_type'), ('access_mode'), ('robots_policy'),
    ('routes'), ('include_subdomains'), ('min_delay_seconds'),
    ('max_pages_per_run'), ('max_items_per_run'), ('max_concurrency'),
    ('browser_profile'), ('statistics_eligible_default'), ('retention_days'),
    ('config'), ('version'), ('expected_interval_seconds'), ('is_demo')$$,
  'the policy projection has an exact non-secret field allowlist'
);
select is(
  ingest.nostr_worker_runtime_ready_v1(), true,
  'the reviewed relay policy, gate, and checkpoint contract is runtime-ready'
);
set local role pokecrack_nostr_worker;
select set_config(
  'pokecrack_test.runtime_ready_as_worker',
  ingest.nostr_worker_runtime_ready_v1()::text,
  true
);
select set_config(
  'pokecrack_test.policy_rows_as_worker',
  (select count(*)::text from ingest.get_nostr_worker_policy_snapshot_v1()),
  true
);
select throws_ok(
  $$select count(*) from ingest.source_policies$$,
  '42501',
  'permission denied for table source_policies',
  'the isolated worker can verify the projection but cannot read its source table'
);
reset role;
select is(
  current_setting('pokecrack_test.runtime_ready_as_worker', true), 'true',
  'the isolated role can execute the boolean runtime proof'
);
select is(
  current_setting('pokecrack_test.policy_rows_as_worker', true), '3',
  'the isolated role sees exactly the three reviewed projected policies'
);
update ingest.source_policies
set expected_interval_seconds = 61
where source_key = 'nostr_relay_primal';
select is(
  ingest.nostr_worker_runtime_ready_v1(), false,
  'source-policy drift fails the runtime proof closed'
);
update ingest.source_policies
set expected_interval_seconds = 60
where source_key = 'nostr_relay_primal';
select is(
  ingest.nostr_worker_runtime_ready_v1(), true,
  'restoring the exact policy restores the runtime proof'
);
update ingest.source_policies
set config = config || '{"credential":"sentinel-must-not-project"}'::jsonb
where source_key = 'nostr_relay_primal';
select is(
  ingest.nostr_worker_runtime_ready_v1(), false,
  'an unexpected policy-config field fails the runtime proof closed'
);
select ok(
  not exists (
    select 1
    from ingest.get_nostr_worker_policy_snapshot_v1() as snapshot
    where snapshot.config ? 'credential'
  ),
  'the worker projection cannot reveal an unexpected future config field'
);
update ingest.source_policies
set config = config - 'credential'
where source_key = 'nostr_relay_primal';
select is(
  ingest.nostr_worker_runtime_ready_v1(), true,
  'removing the unexpected field restores the runtime proof'
);
select ok(
  not has_function_privilege(
      'pokecrack_nostr_worker',
      'ingest.claim_jobs_v2(text,text[],integer,integer)', 'execute'
    )
    and not has_function_privilege(
      'pokecrack_nostr_worker',
      'ingest.heartbeat_job_v2(uuid,text,bigint,integer)', 'execute'
    )
    and not has_function_privilege(
      'pokecrack_nostr_worker',
      'ingest.fail_job_v2(uuid,text,bigint,text,text,boolean)', 'execute'
    )
    and not has_function_privilege(
      'pokecrack_nostr_worker',
      'ingest.pause_job_for_budget_v2(uuid,text,bigint,timestamptz)', 'execute'
    )
    and not has_function_privilege(
      'pokecrack_nostr_worker',
      'ingest.upsert_worker_heartbeat_v1(text,text,text,jsonb)', 'execute'
    ),
  'the Nostr capability cannot call caller-controlled generic queue or health RPCs'
);

select ok(
  (select bool_and(
    not has_table_privilege('pokecrack_nostr_worker', table_name, 'select')
      and not has_table_privilege('pokecrack_nostr_worker', table_name, 'insert')
      and not has_table_privilege('pokecrack_nostr_worker', table_name, 'update')
      and not has_table_privilege('pokecrack_nostr_worker', table_name, 'delete')
      and not has_table_privilege('pokecrack_nostr_worker', table_name, 'maintain')
      and not has_table_privilege('service_role', table_name, 'select')
      and not has_table_privilege('service_role', table_name, 'insert')
      and not has_table_privilege('service_role', table_name, 'update')
      and not has_table_privilege('service_role', table_name, 'delete')
      and not has_table_privilege('service_role', table_name, 'maintain')
  ) from unnest(array[
    'ingest.nostr_relay_candidates'::text,
    'ingest.nostr_relay_observations'::text,
    'ingest.nostr_relay_checkpoints'::text
  ]) as private_tables(table_name)),
  'worker and service roles have no direct Nostr ledger capability'
);
select ok(
  not has_any_column_privilege(
    'pokecrack_nostr_worker', 'ingest.nostr_relay_candidates', 'select'
  )
    and not has_any_column_privilege(
      'pokecrack_nostr_worker', 'ingest.nostr_relay_candidates', 'insert'
    )
    and not has_any_column_privilege(
      'pokecrack_nostr_worker', 'ingest.nostr_relay_candidates', 'update'
    )
    and not has_any_column_privilege(
      'pokecrack_nostr_worker', 'ingest.nostr_relay_candidates', 'references'
    )
    and not has_any_column_privilege(
      'service_role', 'ingest.nostr_relay_candidates', 'select'
    )
    and not has_any_column_privilege(
      'service_role', 'ingest.nostr_relay_candidates', 'insert'
    )
    and not has_any_column_privilege(
      'service_role', 'ingest.nostr_relay_candidates', 'update'
    )
    and not has_any_column_privilege(
      'service_role', 'ingest.nostr_relay_candidates', 'references'
    )
    and not has_sequence_privilege(
      'pokecrack_nostr_worker',
      'ingest.nostr_relay_observations_id_seq',
      'usage'
    )
    and not has_sequence_privilege(
      'pokecrack_nostr_worker',
      'ingest.nostr_relay_observations_id_seq',
      'select'
    )
    and not has_sequence_privilege(
      'pokecrack_nostr_worker',
      'ingest.nostr_relay_observations_id_seq',
      'update'
    )
    and not has_sequence_privilege(
      'service_role',
      'ingest.nostr_relay_observations_id_seq',
      'usage'
    )
    and not has_sequence_privilege(
      'service_role',
      'ingest.nostr_relay_observations_id_seq',
      'select'
    )
    and not has_sequence_privilege(
      'service_role',
      'ingest.nostr_relay_observations_id_seq',
      'update'
    ),
  'worker and service roles have no column or identity-sequence capability'
);

select ok(
  (select count(*) = 15 and bool_and(value = 'true'::jsonb)
   from jsonb_each(ingest.verify_nostr_release_v2())),
  'the exact hosted release contract is ready with both dedicated logins'
);

create role nostr_attestor_extra_member noinherit nologin;
grant pokecrack_nostr_attestor to nostr_attestor_extra_member
  with inherit false, set true;
select is(
  ingest.verify_nostr_release_v2() -> 'attestor_role_exact',
  'false'::jsonb,
  'an unexpected attestor group member fails the release contract closed'
);
revoke pokecrack_nostr_attestor from nostr_attestor_extra_member;

alter role pokecrack_nostr_worker_login set statement_timeout = '1s';
select is(
  ingest.verify_nostr_release_v2() -> 'nostr_worker_role_exact',
  'false'::jsonb,
  'role-level configuration on the worker login fails the release contract closed'
);
alter role pokecrack_nostr_worker_login reset statement_timeout;

create table public.nostr_worker_owned_probe(id integer);
alter table public.nostr_worker_owned_probe owner to pokecrack_nostr_worker_login;
select is(
  ingest.verify_nostr_release_v2() -> 'nostr_worker_role_exact',
  'false'::jsonb,
  'worker-owned catalog objects fail the release contract closed'
);
alter table public.nostr_worker_owned_probe owner to postgres;
drop table public.nostr_worker_owned_probe;

alter default privileges for role pokecrack_nostr_worker_login
  grant select on tables to service_role;
select is(
  ingest.verify_nostr_release_v2() -> 'nostr_worker_role_exact',
  'false'::jsonb,
  'worker-owned default privileges fail the release contract closed'
);
alter default privileges for role pokecrack_nostr_worker_login
  revoke select on tables from service_role;

create role nostr_function_extra_grantee noinherit nologin;
grant execute on function ingest.claim_nostr_relay_jobs_v1(text, integer)
  to nostr_function_extra_grantee;
select is(
  ingest.verify_nostr_release_v2() -> 'nostr_worker_role_exact',
  'false'::jsonb,
  'an unexpected function ACL grantee fails the release contract closed'
);
revoke execute on function ingest.claim_nostr_relay_jobs_v1(text, integer)
  from nostr_function_extra_grantee;

grant execute on function ingest.claim_nostr_relay_jobs_v1(text, integer)
  to pokecrack_nostr_worker with grant option;
select is(
  ingest.verify_nostr_release_v2() -> 'nostr_worker_role_exact',
  'false'::jsonb,
  'worker function WITH GRANT OPTION fails the release contract closed'
);
revoke grant option for execute
  on function ingest.claim_nostr_relay_jobs_v1(text, integer)
  from pokecrack_nostr_worker;

grant execute on function ingest.verify_nostr_release_v2()
  to pokecrack_nostr_attestor with grant option;
select is(
  ingest.verify_nostr_release_v2() -> 'attestor_role_exact',
  'false'::jsonb,
  'attestor function WITH GRANT OPTION fails the release contract closed'
);
revoke grant option for execute
  on function ingest.verify_nostr_release_v2()
  from pokecrack_nostr_attestor;

alter function ingest.get_nostr_worker_policy_snapshot_v1()
  set search_path = public;
select is(
  ingest.verify_nostr_release_v2() -> 'nostr_worker_role_exact',
  'false'::jsonb,
  'worker-function search_path drift fails the release contract closed'
);
alter function ingest.get_nostr_worker_policy_snapshot_v1()
  set search_path = pg_catalog;

grant select (source_key) on ingest.source_policies to pokecrack_nostr_worker;
select is(
  ingest.verify_nostr_release_v2() -> 'nostr_worker_role_exact',
  'false'::jsonb,
  'a worker column grant on any ingest relation fails the contract closed'
);
revoke select (source_key) on ingest.source_policies from pokecrack_nostr_worker;

grant select (source_key) on ingest.source_policies to pokecrack_nostr_attestor;
select is(
  ingest.verify_nostr_release_v2() -> 'attestor_role_exact',
  'false'::jsonb,
  'an attestor column grant on any ingest relation fails the contract closed'
);
revoke select (source_key) on ingest.source_policies from pokecrack_nostr_attestor;

grant truncate on ingest.nostr_relay_candidates to service_role;
select is(
  ingest.verify_nostr_release_v2() -> 'nostr_acl_exact',
  'false'::jsonb,
  'a ledger TRUNCATE grant fails the release contract closed'
);
revoke truncate on ingest.nostr_relay_candidates from service_role;

grant select (event_id) on ingest.nostr_relay_candidates to service_role;
select is(
  ingest.verify_nostr_release_v2() -> 'nostr_acl_exact',
  'false'::jsonb,
  'a column-level ledger grant fails the release contract closed'
);
revoke select (event_id) on ingest.nostr_relay_candidates from service_role;

grant usage on sequence ingest.nostr_relay_observations_id_seq to service_role;
select is(
  ingest.verify_nostr_release_v2() -> 'nostr_acl_exact',
  'false'::jsonb,
  'an identity-sequence grant fails the release contract closed'
);
revoke usage on sequence ingest.nostr_relay_observations_id_seq from service_role;

grant select on ingest.nostr_relay_candidates to nostr_function_extra_grantee;
select is(
  ingest.verify_nostr_release_v2() -> 'nostr_acl_exact',
  'false'::jsonb,
  'an unexpected unrelated ledger grantee fails the ACL contract closed'
);
revoke select on ingest.nostr_relay_candidates from nostr_function_extra_grantee;
drop role nostr_function_extra_grantee;

select ok(
  (select count(*) = 15 and bool_and(value = 'true'::jsonb)
   from jsonb_each(ingest.verify_nostr_release_v2())),
  'the contract returns to ready after every unexpected capability is removed'
);

select set_config('pokecrack_test.nostr_job_id', '', true);
set local role pokecrack_nostr_worker;
select throws_ok(
  $$select ingest.enqueue_due_nostr_relay_jobs_v1('generic-worker')$$,
  '22023',
  'worker_id must use the dedicated Nostr collector prefix',
  'the dedicated scheduler rejects a shared worker identity'
);
select set_config(
  'pokecrack_test.nostr_due_count',
  ingest.enqueue_due_nostr_relay_jobs_v1('nostr-collector-test')::text,
  true
);
select set_config(
  'pokecrack_test.nostr_due_replay_count',
  ingest.enqueue_due_nostr_relay_jobs_v1('nostr-collector-test')::text,
  true
);
reset role;
select is(
  current_setting('pokecrack_test.nostr_due_count', true), '3',
  'the isolated scheduler creates the three exact relay jobs'
);
select is(
  current_setting('pokecrack_test.nostr_due_replay_count', true), '3',
  'replaying the same minute schedule is idempotent'
);
select is(
  (select count(*)
   from ingest.jobs as jobs
   where jobs.job_type = 'source.nostr.relay'
     and jobs.dedupe_key ~ '^schedule:nostr_(primal|nos_lol|nostr_net):'
     and jobs.available_at >= clock_timestamp() - interval '2 minutes'),
  3::bigint,
  'the isolated scheduler persists one recent job per reviewed relay'
);

set local role service_role;
select set_config(
  'pokecrack_test.nostr_job_id', jobs.id::text, true
)
from ingest.enqueue_job_v1(
  'source.nostr.relay',
  '{"relay_key":"primal"}'::jsonb,
  77,
  'nostr-role-isolation-runtime',
  clock_timestamp(),
  3
) as jobs;
select set_config(
  'pokecrack_test.generic_claim_count',
  (select count(*)::text from ingest.claim_jobs_v2(
    'generic-collector-test', array['source.nostr.relay'], 1, 600
  )),
  true
);
reset role;

select isnt(
  current_setting('pokecrack_test.nostr_job_id', true), '',
  'service_role can enqueue the reviewed scheduled work without owning its execution'
);
select is(
  current_setting('pokecrack_test.generic_claim_count', true), '0',
  'generic service_role claim cannot lease a Nostr job'
);

select set_config('pokecrack_test.nostr_claim', '{}'::text, true);
set local role pokecrack_nostr_worker;
select throws_ok(
  $$select * from ingest.claim_nostr_relay_jobs_v1('generic-worker', 600)$$,
  '22023',
  'worker_id must use the dedicated Nostr collector prefix',
  'the dedicated claim wrapper rejects a shared worker identity'
);
with claimed as materialized (
  select * from ingest.claim_nostr_relay_jobs_v1('nostr-collector-test', 600)
)
select set_config(
  'pokecrack_test.nostr_claim',
  jsonb_build_object(
    'id', claimed.id,
    'generation', claimed.lease_generation,
    'worker', claimed.locked_by
  )::text,
  true
)
from claimed;
reset role;

select is(
  current_setting('pokecrack_test.nostr_claim', true)::jsonb ->> 'id',
  current_setting('pokecrack_test.nostr_job_id', true),
  'the dedicated wrapper leases the exact queued Nostr job'
);
select is(
  current_setting('pokecrack_test.nostr_claim', true)::jsonb ->> 'worker',
  'nostr-collector-test',
  'the dedicated lease records only the Nostr collector identity'
);

set local role service_role;
select set_config(
  'pokecrack_test.generic_heartbeat_count',
  (select count(*)::text from ingest.heartbeat_job_v2(
    (current_setting('pokecrack_test.nostr_claim', true)::jsonb ->> 'id')::uuid,
    'nostr-collector-test',
    (current_setting('pokecrack_test.nostr_claim', true)::jsonb ->> 'generation')::bigint,
    600
  )),
  true
);
select set_config(
  'pokecrack_test.generic_fail_count',
  (select count(*)::text from ingest.fail_job_v2(
    (current_setting('pokecrack_test.nostr_claim', true)::jsonb ->> 'id')::uuid,
    'nostr-collector-test',
    (current_setting('pokecrack_test.nostr_claim', true)::jsonb ->> 'generation')::bigint,
    'wrong_path', 'generic worker must be inert', false
  )),
  true
);
reset role;
select is(current_setting('pokecrack_test.generic_heartbeat_count', true), '0',
  'generic service_role heartbeat is inert for a Nostr lease');
select is(current_setting('pokecrack_test.generic_fail_count', true), '0',
  'generic service_role failure is inert for a Nostr lease');

set local role pokecrack_nostr_worker;
select set_config(
  'pokecrack_test.dedicated_heartbeat_count',
  (select count(*)::text from ingest.heartbeat_nostr_relay_job_v1(
    (current_setting('pokecrack_test.nostr_claim', true)::jsonb ->> 'id')::uuid,
    'nostr-collector-test',
    (current_setting('pokecrack_test.nostr_claim', true)::jsonb ->> 'generation')::bigint,
    600
  )),
  true
);
select set_config(
  'pokecrack_test.dedicated_fail_count',
  (select count(*)::text from ingest.fail_nostr_relay_job_v1(
    (current_setting('pokecrack_test.nostr_claim', true)::jsonb ->> 'id')::uuid,
    'nostr-collector-test',
    (current_setting('pokecrack_test.nostr_claim', true)::jsonb ->> 'generation')::bigint,
    'bounded_test', 'expected test transition', false
  )),
  true
);
select set_config(
  'pokecrack_test.heartbeat_row_count',
  (select count(*)::text from ingest.upsert_nostr_worker_heartbeat_v1(
    'nostr-collector-test',
    'test-version',
    '{"command":"health","data_mode":"live","max_concurrency":1,"role_ready":true}'::jsonb
  )),
  true
);
reset role;

select is(current_setting('pokecrack_test.dedicated_heartbeat_count', true), '1',
  'the dedicated heartbeat renews its exact Nostr lease');
select is(current_setting('pokecrack_test.dedicated_fail_count', true), '1',
  'the dedicated failure wrapper performs the fenced Nostr transition');
select is(current_setting('pokecrack_test.heartbeat_row_count', true), '1',
  'the dedicated health wrapper writes one exact Nostr heartbeat');
select ok(
  (select status = 'dead'
      and locked_by is null
      and lock_expires_at is null
      and last_error_code = 'bounded_test'
   from ingest.jobs
   where id = (current_setting('pokecrack_test.nostr_job_id', true))::uuid),
  'the isolated failure leaves no live generic lease'
);
select ok(
  (select worker_type = 'nostr-collector'
      and not is_demo
      and metadata =
        '{"command":"health","data_mode":"live","max_concurrency":1,"role_ready":true}'::jsonb
   from ingest.worker_heartbeats
   where worker_id = 'nostr-collector-test'),
  'the isolated heartbeat cannot impersonate another worker type or metadata shape'
);

select * from finish();
rollback;
