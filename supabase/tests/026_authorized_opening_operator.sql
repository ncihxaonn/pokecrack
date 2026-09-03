-- The local operator path must use a separate submitter capability.  This
-- suite proves that the capability can submit only through the reviewed RPC
-- and cannot read or mutate private ledgers or enter reviewer functions.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select ok(
  exists (
    select 1
    from pg_roles as roles
    where roles.rolname = 'pokecrack_authorized_opening_submitter'
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
  'submitter capability is a no-login, no-inherit, non-escalating database role'
);

select ok(
  has_schema_privilege(
    'pokecrack_authorized_opening_submitter', 'ingest', 'usage'
  )
  and not has_schema_privilege(
    'pokecrack_authorized_opening_submitter', 'ingest', 'create'
  )
  and not exists (
    select 1
    from pg_class as relations
    join pg_namespace as schemas on schemas.oid = relations.relnamespace
    where schemas.nspname in ('catalog', 'ingest', 'analytics', 'public')
      and relations.relkind in ('r', 'p', 'v', 'm', 'f')
      and (
        has_table_privilege(
          'pokecrack_authorized_opening_submitter', relations.oid, 'select'
        )
        or has_table_privilege(
          'pokecrack_authorized_opening_submitter', relations.oid, 'insert'
        )
        or has_table_privilege(
          'pokecrack_authorized_opening_submitter', relations.oid, 'update'
        )
        or has_table_privilege(
          'pokecrack_authorized_opening_submitter', relations.oid, 'delete'
        )
        or has_table_privilege(
          'pokecrack_authorized_opening_submitter', relations.oid, 'truncate'
        )
        or has_table_privilege(
          'pokecrack_authorized_opening_submitter', relations.oid, 'references'
        )
        or has_table_privilege(
          'pokecrack_authorized_opening_submitter', relations.oid, 'trigger'
        )
        or has_table_privilege(
          'pokecrack_authorized_opening_submitter', relations.oid, 'maintain'
        )
        or has_any_column_privilege(
          'pokecrack_authorized_opening_submitter',
          relations.oid,
          'select,insert,update,references'
        )
      )
  )
  and not exists (
    select 1
    from pg_class as sequences
    join pg_namespace as schemas on schemas.oid = sequences.relnamespace
    where schemas.nspname in ('catalog', 'ingest', 'analytics', 'public')
      and sequences.relkind = 'S'
      and (
        has_sequence_privilege(
          'pokecrack_authorized_opening_submitter', sequences.oid, 'usage'
        )
        or has_sequence_privilege(
          'pokecrack_authorized_opening_submitter', sequences.oid, 'select'
        )
        or has_sequence_privilege(
          'pokecrack_authorized_opening_submitter', sequences.oid, 'update'
        )
      )
  ),
  'submitter capability has no direct application relation or sequence access'
);

select ok(
  has_function_privilege(
    'pokecrack_authorized_opening_submitter',
    'ingest.submit_authorized_opening_direct_v1(jsonb)'::regprocedure,
    'execute'
  )
  and not has_function_privilege(
    'pokecrack_authorized_opening_submitter',
    'ingest.submit_authorized_opening_v1(jsonb)'::regprocedure,
    'execute'
  )
  and not has_function_privilege(
    'pokecrack_authorized_opening_submitter',
    'ingest.list_authorized_opening_reviews_v1(text,integer)'::regprocedure,
    'execute'
  )
  and not has_function_privilege(
    'pokecrack_authorized_opening_submitter',
    'ingest.review_authorized_opening_v1(uuid,bigint,text,text,text)'::regprocedure,
    'execute'
  )
  and not has_function_privilege(
    'pokecrack_authorized_opening_submitter',
    'ingest.retract_authorized_opening_v1(uuid,text,text)'::regprocedure,
    'execute'
  )
  and not has_function_privilege(
    'anon',
    'ingest.submit_authorized_opening_v1(jsonb)'::regprocedure,
    'execute'
  )
  and not has_function_privilege(
    'authenticated',
    'ingest.submit_authorized_opening_v1(jsonb)'::regprocedure,
    'execute'
  ),
  'submitter capability can execute only the direct-only submit RPC, never the historical or reviewer RPCs'
);

select ok(
  (select count(*) = 1
   from pg_auth_members as memberships
   join pg_roles as owner on owner.oid = memberships.member
   join pg_roles as grantor on grantor.oid = memberships.grantor
   where memberships.roleid = 'pokecrack_authorized_opening_submitter'::regrole
     and memberships.admin_option
     and not memberships.inherit_option
     and not memberships.set_option
     and grantor.rolsuper
     and (owner.rolsuper or owner.rolcreaterole)),
  'submitter capability retains one owner-only creator membership edge'
);

select ok(
  position('insert into' in lower(pg_get_functiondef(
    'ingest.submit_authorized_opening_v1(jsonb)'::regprocedure
  ))) > 0
  and position('authorized_opening_submissions' in lower(pg_get_functiondef(
    'ingest.submit_authorized_opening_v1(jsonb)'::regprocedure
  ))) > 0
  and exists (
    select 1
    from pg_proc as procedures
    where procedures.oid = any(array[
      'ingest.submit_authorized_opening_v1(jsonb)'::regprocedure,
      'ingest.list_authorized_opening_reviews_v1(text,integer)'::regprocedure,
      'ingest.review_authorized_opening_v1(uuid,bigint,text,text,text)'::regprocedure,
      'ingest.retract_authorized_opening_v1(uuid,text,text)'::regprocedure
    ])
    group by true
    having count(*) = 4 and bool_and(procedures.prosecdef)
  ),
  'operator uses the existing security-definer submit/reviewer functions and no direct table writer'
);

select * from finish();
rollback;
