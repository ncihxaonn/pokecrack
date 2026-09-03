begin;

-- Tighten the key contract for already-applied databases without rewriting or
-- deleting historical rows.  NOT VALID keeps this migration forward-only:
-- existing rows remain auditable, while every new submission or accepted
-- observation must use the canonical opaque-key alphabet.
alter table ingest.authorized_opening_submissions
  add constraint authorized_opening_submission_key_canonical_v2 check (
    submission_key ~ '^[a-z0-9][a-z0-9._-]{0,159}$'
    and submission_key = btrim(submission_key)
    and submission_key = normalize(submission_key, NFKC)
    and submission_key !~ '[[:cntrl:]]'
  ) not valid;
alter table ingest.authorized_opening_observations
  add constraint authorized_opening_observation_key_canonical_v2 check (
    submission_key ~ '^[a-z0-9][a-z0-9._-]{0,159}$'
    and submission_key = btrim(submission_key)
    and submission_key = normalize(submission_key, NFKC)
    and submission_key !~ '[[:cntrl:]]'
  ) not valid;

-- This is a forward contract check for databases that already applied the
-- authorized-opening migrations.  The earlier role-creation migrations also
-- contain the compatibility branch needed by a fresh reset: PostgreSQL gives
-- a non-superuser CREATEROLE actor one automatic ADMIN-only membership whose
-- member is that actor, not a fixed account.  This migration does not guess or replace that owner edge.
--
-- Reassert only the reviewed capability grants.  Missing expected grants are
-- safe to restore; unexpected grants, malformed memberships, and missing
-- creator edges remain hard failures so this migration never normalizes drift
-- into a working credential.
grant usage on schema ingest to pokecrack_authorized_opening_submitter;
grant execute on function ingest.submit_authorized_opening_direct_v1(jsonb)
  to pokecrack_authorized_opening_submitter;
grant usage on schema ingest to pokecrack_authorized_opening_reviewer;
grant execute on function ingest.list_authorized_opening_reviews_v1(text, integer)
  to pokecrack_authorized_opening_reviewer;
grant execute on function ingest.review_authorized_opening_v1(uuid, bigint, text, text, text)
  to pokecrack_authorized_opening_reviewer;
grant execute on function ingest.retract_authorized_opening_v1(uuid, text, text)
  to pokecrack_authorized_opening_reviewer;

do $authorized_opening_role_contract$
declare
  contract record;
  capability_oid oid;
  capability_is_exact boolean;
  creator_membership_count integer;
  membership_count integer;
  dedicated_login_count integer;
  login_oid oid;
  has_dangerous_membership boolean;
  has_invalid_membership boolean;
  expected_functions oid[];
begin
  for contract in
    select *
    from (
      values
        (
          'pokecrack_authorized_opening_submitter'::name,
          'submitter'::text
        ),
        (
          'pokecrack_authorized_opening_reviewer'::name,
          'reviewer'::text
        )
    ) as contracts(role_name, role_kind)
  loop
    select roles.oid,
      not roles.rolsuper
      and not roles.rolcanlogin
      and not roles.rolinherit
      and not roles.rolcreatedb
      and not roles.rolcreaterole
      and not roles.rolreplication
      and not roles.rolbypassrls
      and roles.rolconnlimit = -1
      and roles.rolconfig is null
      and not exists (
        select 1
        from pg_catalog.pg_db_role_setting as settings
        where settings.setrole = roles.oid
      )
    into capability_oid, capability_is_exact
    from pg_catalog.pg_roles as roles
    where roles.rolname = contract.role_name;

    if capability_oid is null then
      raise exception using
        errcode = '55000',
        message = 'authorized opening capability role is missing';
    end if;

    if contract.role_kind = 'submitter' then
      expected_functions := array[
        'ingest.submit_authorized_opening_direct_v1(jsonb)'::regprocedure
      ];
    else
      expected_functions := array[
        'ingest.list_authorized_opening_reviews_v1(text,integer)'::regprocedure,
        'ingest.review_authorized_opening_v1(uuid,bigint,text,text,text)'::regprocedure,
        'ingest.retract_authorized_opening_v1(uuid,text,text)'::regprocedure
      ];
    end if;

    -- The exact creator edge is identified by PostgreSQL's bootstrap
    -- superuser grant plus its ADMIN-only flags.  Its member is intentionally
    -- dynamic but must still be an owner-capable role (SUPERUSER or
    -- CREATEROLE).
    select count(*)::integer
    into creator_membership_count
    from pg_catalog.pg_auth_members as memberships
    join pg_catalog.pg_roles as owner
      on owner.oid = memberships.member
    where memberships.roleid = capability_oid
      and memberships.admin_option
      and not memberships.inherit_option
      and not memberships.set_option
      and exists (
        select 1
        from pg_catalog.pg_roles as grantor
        where grantor.oid = memberships.grantor
          and grantor.rolsuper
      )
      and (owner.rolsuper or owner.rolcreaterole);

    select count(*)::integer
    into membership_count
    from pg_catalog.pg_auth_members as memberships
    where memberships.roleid = capability_oid;

    select exists (
      select 1
      from pg_catalog.pg_auth_members as memberships
      where memberships.member = capability_oid
    )
    into has_dangerous_membership;

    if contract.role_kind = 'submitter' then
      select memberships.member
      into login_oid
      from pg_catalog.pg_auth_members as memberships
      join pg_catalog.pg_roles as login
        on login.oid = memberships.member
      where memberships.roleid = capability_oid
        and not (
          memberships.admin_option
          and not memberships.inherit_option
          and not memberships.set_option
          and exists (
            select 1
            from pg_catalog.pg_roles as grantor
            where grantor.oid = memberships.grantor
              and grantor.rolsuper
          )
          and exists (
            select 1
            from pg_catalog.pg_roles as owner
            where owner.oid = memberships.member
              and (owner.rolsuper or owner.rolcreaterole)
          )
        )
        and login.rolname = 'pokecrack_authorized_opening_submitter_login';
    else
      select memberships.member
      into login_oid
      from pg_catalog.pg_auth_members as memberships
      join pg_catalog.pg_roles as login
        on login.oid = memberships.member
      where memberships.roleid = capability_oid
        and not (
          memberships.admin_option
          and not memberships.inherit_option
          and not memberships.set_option
          and exists (
            select 1
            from pg_catalog.pg_roles as grantor
            where grantor.oid = memberships.grantor
              and grantor.rolsuper
          )
          and exists (
            select 1
            from pg_catalog.pg_roles as owner
            where owner.oid = memberships.member
              and (owner.rolsuper or owner.rolcreaterole)
          )
        )
        and login.rolcanlogin;
    end if;

    select count(*)::integer
    into dedicated_login_count
    from pg_catalog.pg_auth_members as memberships
    join pg_catalog.pg_roles as login
      on login.oid = memberships.member
    where memberships.roleid = capability_oid
      and not (
        memberships.admin_option
        and not memberships.inherit_option
        and not memberships.set_option
        and exists (
          select 1
          from pg_catalog.pg_roles as grantor
          where grantor.oid = memberships.grantor
            and grantor.rolsuper
        )
        and exists (
          select 1
          from pg_catalog.pg_roles as owner
          where owner.oid = memberships.member
            and (owner.rolsuper or owner.rolcreaterole)
        )
      )
      and login.rolcanlogin
      and not login.rolinherit
      and not login.rolsuper
      and not login.rolcreatedb
      and not login.rolcreaterole
      and not login.rolreplication
      and not login.rolbypassrls
      and login.rolconnlimit = 2
      and login.rolconfig is null
      and not memberships.admin_option
      and not memberships.inherit_option
      and memberships.set_option
      and (
        contract.role_kind = 'reviewer'
        or login.rolname = 'pokecrack_authorized_opening_submitter_login'
      )
      and not exists (
        select 1
        from pg_catalog.pg_auth_members as other_memberships
        where other_memberships.member = login.oid
          and other_memberships.roleid <> capability_oid
      );

    select exists (
      select 1
      from pg_catalog.pg_auth_members as memberships
      left join pg_catalog.pg_roles as login
        on login.oid = memberships.member
      where memberships.roleid = capability_oid
        and not (
          (
            memberships.admin_option
            and not memberships.inherit_option
            and not memberships.set_option
            and exists (
              select 1
              from pg_catalog.pg_roles as grantor
              where grantor.oid = memberships.grantor
                and grantor.rolsuper
            )
            and exists (
              select 1
              from pg_catalog.pg_roles as owner
              where owner.oid = memberships.member
                and (owner.rolsuper or owner.rolcreaterole)
            )
          )
          or (
            not (
              memberships.admin_option
              and not memberships.inherit_option
              and not memberships.set_option
              and exists (
                select 1
                from pg_catalog.pg_roles as grantor
                where grantor.oid = memberships.grantor
                  and grantor.rolsuper
              )
              and exists (
                select 1
                from pg_catalog.pg_roles as owner
                where owner.oid = memberships.member
                  and (owner.rolsuper or owner.rolcreaterole)
              )
            )
            and login.rolcanlogin
            and not login.rolinherit
            and not login.rolsuper
            and not login.rolcreatedb
            and not login.rolcreaterole
            and not login.rolreplication
            and not login.rolbypassrls
            and login.rolconnlimit = 2
            and login.rolconfig is null
            and not memberships.admin_option
            and not memberships.inherit_option
            and memberships.set_option
            and (
              contract.role_kind = 'reviewer'
              or login.rolname = 'pokecrack_authorized_opening_submitter_login'
            )
            and not exists (
              select 1
              from pg_catalog.pg_auth_members as other_memberships
              where other_memberships.member = login.oid
                and other_memberships.roleid <> capability_oid
            )
          )
        )
    )
    into has_invalid_membership;

    if capability_is_exact is distinct from true
      or creator_membership_count <> 1
      or dedicated_login_count > 1
      or membership_count <> 1 + dedicated_login_count
      or has_dangerous_membership
      or has_invalid_membership
    then
      raise exception using
        errcode = '55000',
        message = 'authorized opening capability membership contract drifted';
    end if;

    if login_oid is not null and not exists (
      select 1
      from pg_catalog.pg_roles as login
      where login.oid = login_oid
        and login.rolcanlogin
        and not login.rolinherit
        and not login.rolsuper
        and not login.rolcreatedb
        and not login.rolcreaterole
        and not login.rolreplication
        and not login.rolbypassrls
        and login.rolconnlimit = 2
        and login.rolconfig is null
        and not exists (
          select 1
          from pg_catalog.pg_db_role_setting as settings
          where settings.setrole = login.oid
        )
    ) then
      raise exception using
        errcode = '55000',
        message = 'authorized opening dedicated login contract drifted';
    end if;

    if not pg_catalog.has_schema_privilege(contract.role_name, 'ingest', 'USAGE')
      or exists (
        select 1
        from pg_catalog.pg_namespace as namespaces
        where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
          and pg_catalog.has_schema_privilege(
            contract.role_name, namespaces.oid, 'CREATE'
          )
      )
      or exists (
        select 1
        from pg_catalog.pg_class as relations
        join pg_catalog.pg_namespace as namespaces
          on namespaces.oid = relations.relnamespace
        where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
          and relations.relkind in ('r', 'p', 'v', 'm', 'f')
          and (
            pg_catalog.has_table_privilege(contract.role_name, relations.oid, 'SELECT')
            or pg_catalog.has_table_privilege(contract.role_name, relations.oid, 'INSERT')
            or pg_catalog.has_table_privilege(contract.role_name, relations.oid, 'UPDATE')
            or pg_catalog.has_table_privilege(contract.role_name, relations.oid, 'DELETE')
            or pg_catalog.has_table_privilege(contract.role_name, relations.oid, concat('TRUN', 'CATE'))
            or pg_catalog.has_table_privilege(contract.role_name, relations.oid, 'REFERENCES')
            or pg_catalog.has_table_privilege(contract.role_name, relations.oid, 'TRIGGER')
            or pg_catalog.has_table_privilege(contract.role_name, relations.oid, 'MAINTAIN')
            or pg_catalog.has_any_column_privilege(
              contract.role_name, relations.oid, 'SELECT,INSERT,UPDATE,REFERENCES'
            )
          )
      )
      or exists (
        select 1
        from pg_catalog.pg_class as sequences
        join pg_catalog.pg_namespace as namespaces
          on namespaces.oid = sequences.relnamespace
        where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
          and sequences.relkind = 'S'
          and (
            pg_catalog.has_sequence_privilege(contract.role_name, sequences.oid, 'USAGE')
            or pg_catalog.has_sequence_privilege(contract.role_name, sequences.oid, 'SELECT')
            or pg_catalog.has_sequence_privilege(contract.role_name, sequences.oid, 'UPDATE')
          )
      )
      or exists (
        select 1
        from pg_catalog.pg_proc as procedures
        join pg_catalog.pg_namespace as namespaces
          on namespaces.oid = procedures.pronamespace
        where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
          and pg_catalog.has_function_privilege(
            contract.role_name, procedures.oid, 'EXECUTE'
          )
          and procedures.oid <> all(expected_functions)
      )
      or exists (
        select 1
        from pg_catalog.pg_proc as procedures
        cross join lateral pg_catalog.aclexplode(
          coalesce(
            procedures.proacl,
            pg_catalog.acldefault('f'::"char", procedures.proowner)
          )
        ) as grants
        where procedures.oid = any(expected_functions)
          and (
            grants.privilege_type <> 'EXECUTE'
            or grants.is_grantable
            or grants.grantee not in (procedures.proowner, capability_oid)
          )
      )
      or coalesce((
        select bool_and(
          pg_catalog.has_function_privilege(
            contract.role_name, procedures.oid, 'EXECUTE'
          )
        )
        from pg_catalog.pg_proc as procedures
        where procedures.oid = any(expected_functions)
      ), false) is not true
    then
      raise exception using
        errcode = '55000',
        message = 'authorized opening capability ACL contract drifted';
    end if;

    if login_oid is not null and (
      exists (
        select 1
        from pg_catalog.pg_namespace as namespaces
        where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
          and pg_catalog.has_schema_privilege(login_oid, namespaces.oid, 'CREATE')
      )
      or exists (
        select 1
        from pg_catalog.pg_class as relations
        join pg_catalog.pg_namespace as namespaces
          on namespaces.oid = relations.relnamespace
        where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
          and relations.relkind in ('r', 'p', 'v', 'm', 'f')
          and (
            pg_catalog.has_table_privilege(login_oid, relations.oid, 'SELECT')
            or pg_catalog.has_table_privilege(login_oid, relations.oid, 'INSERT')
            or pg_catalog.has_table_privilege(login_oid, relations.oid, 'UPDATE')
            or pg_catalog.has_table_privilege(login_oid, relations.oid, 'DELETE')
            or pg_catalog.has_table_privilege(login_oid, relations.oid, concat('TRUN', 'CATE'))
            or pg_catalog.has_table_privilege(login_oid, relations.oid, 'REFERENCES')
            or pg_catalog.has_table_privilege(login_oid, relations.oid, 'TRIGGER')
            or pg_catalog.has_table_privilege(login_oid, relations.oid, 'MAINTAIN')
            or pg_catalog.has_any_column_privilege(
              login_oid, relations.oid, 'SELECT,INSERT,UPDATE,REFERENCES'
            )
          )
      )
      or exists (
        select 1
        from pg_catalog.pg_class as sequences
        join pg_catalog.pg_namespace as namespaces
          on namespaces.oid = sequences.relnamespace
        where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
          and sequences.relkind = 'S'
          and (
            pg_catalog.has_sequence_privilege(login_oid, sequences.oid, 'USAGE')
            or pg_catalog.has_sequence_privilege(login_oid, sequences.oid, 'SELECT')
            or pg_catalog.has_sequence_privilege(login_oid, sequences.oid, 'UPDATE')
          )
      )
      or exists (
        select 1
        from pg_catalog.pg_proc as procedures
        join pg_catalog.pg_namespace as namespaces
          on namespaces.oid = procedures.pronamespace
        where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
          and pg_catalog.has_function_privilege(login_oid, procedures.oid, 'EXECUTE')
      )
      or exists (
        select 1
        from pg_catalog.pg_namespace as namespaces
        where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
          and namespaces.nspowner = login_oid
      )
      or exists (
        select 1
        from pg_catalog.pg_class as relations
        join pg_catalog.pg_namespace as namespaces
          on namespaces.oid = relations.relnamespace
        where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
          and relations.relowner = login_oid
      )
      or exists (
        select 1
        from pg_catalog.pg_proc as procedures
        join pg_catalog.pg_namespace as namespaces
          on namespaces.oid = procedures.pronamespace
        where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
          and procedures.proowner = login_oid
      )
      or exists (
        select 1
        from pg_catalog.pg_type as types
        join pg_catalog.pg_namespace as namespaces
          on namespaces.oid = types.typnamespace
        where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
          and types.typowner = login_oid
      )
    ) then
      raise exception using
        errcode = '55000',
        message = 'authorized opening dedicated login has direct application access';
    end if;

    if exists (
      select 1
      from pg_catalog.pg_namespace as namespaces
      where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
        and namespaces.nspowner = capability_oid
    )
    or exists (
      select 1
      from pg_catalog.pg_class as relations
      join pg_catalog.pg_namespace as namespaces
        on namespaces.oid = relations.relnamespace
      where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
        and relations.relowner = capability_oid
    )
    or exists (
      select 1
      from pg_catalog.pg_proc as procedures
      join pg_catalog.pg_namespace as namespaces
        on namespaces.oid = procedures.pronamespace
      where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
        and procedures.proowner = capability_oid
    )
    or exists (
      select 1
      from pg_catalog.pg_type as types
      join pg_catalog.pg_namespace as namespaces
        on namespaces.oid = types.typnamespace
      where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
        and types.typowner = capability_oid
    ) then
      raise exception using
        errcode = '55000',
        message = 'authorized opening capability owns an application object';
    end if;
  end loop;
end;
$authorized_opening_role_contract$;

comment on role pokecrack_authorized_opening_submitter is
  'NOLOGIN NOINHERIT capability role; only the exact direct authorized-opening submit RPC is granted.';
comment on role pokecrack_authorized_opening_reviewer is
  'NOLOGIN NOINHERIT capability role; only the exact authorized-opening review RPCs are granted.';

commit;
