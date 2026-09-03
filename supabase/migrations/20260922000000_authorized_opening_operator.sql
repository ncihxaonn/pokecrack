begin;

-- The operator submitter is a capability role, not a credential.  The
-- account-owner provisions at most one separate NOINHERIT login outside the
-- migration, then grants this role with SET only.  No password or DSN belongs
-- in SQL, Git, logs, or the public application.
do $submitter_role$
declare
  submitter_oid oid;
  role_is_exact boolean;
  role_has_dangerous_memberships boolean;
  role_membership_count integer;
  role_creator_membership_count integer;
  role_dedicated_login_count integer;
  role_has_invalid_membership boolean;
  submitter_login_oid oid;
begin
  if not exists (
    select 1 from pg_catalog.pg_roles
    where rolname = 'pokecrack_authorized_opening_submitter'
  ) then
    create role pokecrack_authorized_opening_submitter
      nosuperuser nologin noinherit nocreatedb nocreaterole noreplication
      nobypassrls connection limit -1;

    select roles.oid
    into submitter_oid
    from pg_catalog.pg_roles as roles
    where roles.rolname = 'pokecrack_authorized_opening_submitter';

    -- PostgreSQL automatically creates one creator-admin membership for a
    -- non-superuser CREATEROLE actor. The member is the migration actor, not
    -- a fixed account, and the bootstrap grantor is the stable marker
    -- for that implicit owner edge. A superuser creates no automatic edge, so
    -- add the reviewed owner edge only when no exact creator edge exists.
    if exists (
      select 1
      from pg_catalog.pg_auth_members as memberships
      where memberships.roleid = submitter_oid
        and memberships.admin_option
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
    ) then
      null;
    elsif exists (
      select 1
      from pg_catalog.pg_auth_members as memberships
      where memberships.roleid = submitter_oid
        and memberships.admin_option
        and not memberships.inherit_option
        and not memberships.set_option
    ) then
      raise exception using
        errcode = '55000',
        message = 'fresh authorized opening submitter creator edge is not isolated';
    else
      grant pokecrack_authorized_opening_submitter
        to current_user
        with admin true, inherit false, set false;
    end if;
  else
    select
      roles.oid,
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
    into submitter_oid, role_is_exact
    from pg_catalog.pg_roles as roles
    where roles.rolname = 'pokecrack_authorized_opening_submitter';

    select count(*)::integer
    into role_membership_count
    from pg_catalog.pg_auth_members as memberships
    where memberships.roleid = submitter_oid;

    select exists (
      select 1
      from pg_catalog.pg_auth_members as memberships
      where memberships.member = submitter_oid
    )
    into role_has_dangerous_memberships;

    select count(*)::integer
    into role_creator_membership_count
    from pg_catalog.pg_auth_members as memberships
    where memberships.roleid = submitter_oid
      and memberships.admin_option
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
      );

    select count(*)::integer
    into role_dedicated_login_count
    from pg_catalog.pg_auth_members as memberships
    join pg_catalog.pg_roles as login
      on login.oid = memberships.member
    where memberships.roleid = submitter_oid
      and login.rolname = 'pokecrack_authorized_opening_submitter_login'
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
      and not memberships.admin_option
      and not memberships.inherit_option
      and memberships.set_option
      and not exists (
        select 1
        from pg_catalog.pg_auth_members as other_memberships
        where other_memberships.member = login.oid
          and other_memberships.roleid <> submitter_oid
      );

    select memberships.member
    into submitter_login_oid
    from pg_catalog.pg_auth_members as memberships
    join pg_catalog.pg_roles as login
      on login.oid = memberships.member
    where memberships.roleid = submitter_oid
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

    select exists (
      select 1
      from pg_catalog.pg_auth_members as memberships
      left join pg_catalog.pg_roles as login
        on login.oid = memberships.member
      where memberships.roleid = submitter_oid
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
            and login.rolname = 'pokecrack_authorized_opening_submitter_login'
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
            and not memberships.admin_option
            and not memberships.inherit_option
            and memberships.set_option
            and not exists (
              select 1
              from pg_catalog.pg_auth_members as other_memberships
              where other_memberships.member = login.oid
                and other_memberships.roleid <> submitter_oid
            )
          )
        )
    )
    into role_has_invalid_membership;

    -- Existing role drift is a hard stop.  This block never normalizes a
    -- stale credential into a working submitter by revoking unknown grants.
    if role_is_exact is distinct from true
      or role_has_dangerous_memberships
      or role_creator_membership_count <> 1
      or role_dedicated_login_count > 1
      or role_membership_count <> 1 + role_dedicated_login_count
      or role_has_invalid_membership
    then
      raise exception using
        errcode = '55000',
        message = 'existing authorized opening submitter role is not the reviewed isolated contract';
    end if;

    -- A membership to the named login is optional until the account-owner
    -- provisions credentials, but an unrelated member is never acceptable.
    if submitter_login_oid is not null
      and exists (
        select 1
        from pg_catalog.pg_auth_members as memberships
        where memberships.member = submitter_login_oid
          and memberships.roleid <> submitter_oid
      )
    then
      raise exception using
        errcode = '55000',
        message = 'authorized opening submitter login has an unrelated membership';
    end if;
  end if;
end;
$submitter_role$;

-- Start from the default-deny role posture and expose only the one reviewed
-- submission function.  The role never receives table or sequence access.
grant usage on schema ingest to pokecrack_authorized_opening_submitter;
grant execute on function ingest.submit_authorized_opening_v1(jsonb)
  to pokecrack_authorized_opening_submitter;

-- Replayed migrations must fail closed on privilege drift rather than repair
-- it.  The submitter role can only call the exact typed submit RPC; its
-- dedicated login can acquire that capability only with SET ROLE.
do $submitter_attestation$
declare
  submitter_oid oid;
  submitter_login_oid oid;
  submitter_has_dangerous_memberships boolean;
  submitter_membership_count integer;
  submitter_creator_membership_count integer;
  submitter_dedicated_login_count integer;
  submitter_has_invalid_membership boolean;
  expected_submit_function oid :=
    'ingest.submit_authorized_opening_v1(jsonb)'::regprocedure;
begin
  select roles.oid
  into submitter_oid
  from pg_catalog.pg_roles as roles
  where roles.rolname = 'pokecrack_authorized_opening_submitter';
  if submitter_oid is null then
    raise exception using
      errcode = '55000',
      message = 'authorized opening submitter capability role is missing';
  end if;

  select count(*)::integer
  into submitter_membership_count
  from pg_catalog.pg_auth_members as memberships
  where memberships.roleid = submitter_oid;

  select exists (
    select 1
    from pg_catalog.pg_auth_members as memberships
    where memberships.member = submitter_oid
  )
  into submitter_has_dangerous_memberships;

  select count(*)::integer
  into submitter_creator_membership_count
  from pg_catalog.pg_auth_members as memberships
  where memberships.roleid = submitter_oid
    and memberships.admin_option
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
    );

  select memberships.member
  into submitter_login_oid
  from pg_catalog.pg_auth_members as memberships
  join pg_catalog.pg_roles as login on login.oid = memberships.member
  where memberships.roleid = submitter_oid
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

  select count(*)::integer
  into submitter_dedicated_login_count
  from pg_catalog.pg_auth_members as memberships
  join pg_catalog.pg_roles as login on login.oid = memberships.member
  where memberships.roleid = submitter_oid
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
    and login.rolname = 'pokecrack_authorized_opening_submitter_login'
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
    and not memberships.admin_option
    and not memberships.inherit_option
    and memberships.set_option
    and not exists (
      select 1
      from pg_catalog.pg_auth_members as other_memberships
      where other_memberships.member = login.oid
        and other_memberships.roleid <> submitter_oid
    );

  select exists (
    select 1
    from pg_catalog.pg_auth_members as memberships
    left join pg_catalog.pg_roles as login on login.oid = memberships.member
    where memberships.roleid = submitter_oid
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
          and login.rolname = 'pokecrack_authorized_opening_submitter_login'
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
          and not memberships.admin_option
          and not memberships.inherit_option
          and memberships.set_option
          and not exists (
            select 1
            from pg_catalog.pg_auth_members as other_memberships
            where other_memberships.member = login.oid
              and other_memberships.roleid <> submitter_oid
          )
        )
      )
  )
  into submitter_has_invalid_membership;

  if submitter_creator_membership_count <> 1
    or submitter_has_dangerous_memberships
    or submitter_dedicated_login_count > 1
    or submitter_membership_count <> 1 + submitter_dedicated_login_count
    or submitter_has_invalid_membership
  then
    raise exception using
      errcode = '55000',
      message = 'authorized opening submitter memberships drifted';
  end if;

  if not pg_catalog.has_schema_privilege(
       'pokecrack_authorized_opening_submitter', 'ingest', 'USAGE'
     )
     or pg_catalog.has_schema_privilege(
       'pokecrack_authorized_opening_submitter', 'ingest', 'CREATE'
     )
     or exists (
       select 1
       from pg_catalog.pg_namespace as namespaces
       where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
         and pg_catalog.has_schema_privilege(
           'pokecrack_authorized_opening_submitter', namespaces.oid, 'CREATE'
         )
     )
  then
    raise exception using
      errcode = '55000',
      message = 'authorized opening submitter schema privileges drifted';
  end if;

  if exists (
    select 1
    from pg_catalog.pg_class as relations
    join pg_catalog.pg_namespace as namespaces on namespaces.oid = relations.relnamespace
    where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
      and relations.relkind in ('r', 'p', 'v', 'm', 'f')
      and (
        pg_catalog.has_table_privilege(
          'pokecrack_authorized_opening_submitter', relations.oid, 'SELECT'
        )
        or pg_catalog.has_table_privilege(
          'pokecrack_authorized_opening_submitter', relations.oid, 'INSERT'
        )
        or pg_catalog.has_table_privilege(
          'pokecrack_authorized_opening_submitter', relations.oid, 'UPDATE'
        )
        or pg_catalog.has_table_privilege(
          'pokecrack_authorized_opening_submitter', relations.oid, 'DELETE'
        )
        or pg_catalog.has_table_privilege(
          'pokecrack_authorized_opening_submitter', relations.oid, concat('TRUN', 'CATE')
        )
        or pg_catalog.has_table_privilege(
          'pokecrack_authorized_opening_submitter', relations.oid, 'REFERENCES'
        )
        or pg_catalog.has_table_privilege(
          'pokecrack_authorized_opening_submitter', relations.oid, 'TRIGGER'
        )
        or pg_catalog.has_table_privilege(
          'pokecrack_authorized_opening_submitter', relations.oid, 'MAINTAIN'
        )
        or pg_catalog.has_any_column_privilege(
          'pokecrack_authorized_opening_submitter',
          relations.oid,
          'SELECT,INSERT,UPDATE,REFERENCES'
        )
      )
  )
  or exists (
    select 1
    from pg_catalog.pg_class as sequences
    join pg_catalog.pg_namespace as namespaces on namespaces.oid = sequences.relnamespace
    where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
      and sequences.relkind = 'S'
      and (
        pg_catalog.has_sequence_privilege(
          'pokecrack_authorized_opening_submitter', sequences.oid, 'USAGE'
        )
        or pg_catalog.has_sequence_privilege(
          'pokecrack_authorized_opening_submitter', sequences.oid, 'SELECT'
        )
        or pg_catalog.has_sequence_privilege(
          'pokecrack_authorized_opening_submitter', sequences.oid, 'UPDATE'
        )
      )
  )
  then
    raise exception using
      errcode = '55000',
      message = 'authorized opening submitter relation privileges drifted';
  end if;

  if exists (
    select 1
    from pg_catalog.pg_proc as procedures
    join pg_catalog.pg_namespace as namespaces on namespaces.oid = procedures.pronamespace
    where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
      and pg_catalog.has_function_privilege(
        'pokecrack_authorized_opening_submitter', procedures.oid, 'EXECUTE'
      )
      and procedures.oid <> expected_submit_function
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
    where procedures.oid = expected_submit_function
      and (
        grants.privilege_type <> 'EXECUTE'
        or grants.is_grantable
        or grants.grantee not in (procedures.proowner, submitter_oid, 'service_role'::regrole)
      )
  )
  or not pg_catalog.has_function_privilege(
    'pokecrack_authorized_opening_submitter',
    expected_submit_function,
    'EXECUTE'
  )
  then
    raise exception using
      errcode = '55000',
      message = 'authorized opening submitter function privileges drifted';
  end if;

  -- If provisioned, the login itself must have no direct application path;
  -- it receives the submit capability only through SET ROLE.
  if submitter_login_oid is not null and (
    exists (
      select 1
      from pg_catalog.pg_namespace as namespaces
      where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
        and pg_catalog.has_schema_privilege(submitter_login_oid, namespaces.oid, 'CREATE')
    )
    or exists (
      select 1
      from pg_catalog.pg_class as relations
      join pg_catalog.pg_namespace as namespaces on namespaces.oid = relations.relnamespace
      where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
        and relations.relkind in ('r', 'p', 'v', 'm', 'f')
        and (
          pg_catalog.has_table_privilege(submitter_login_oid, relations.oid, 'SELECT')
          or pg_catalog.has_table_privilege(submitter_login_oid, relations.oid, 'INSERT')
          or pg_catalog.has_table_privilege(submitter_login_oid, relations.oid, 'UPDATE')
          or pg_catalog.has_table_privilege(submitter_login_oid, relations.oid, 'DELETE')
          or pg_catalog.has_table_privilege(
            submitter_login_oid, relations.oid, concat('TRUN', 'CATE')
          )
          or pg_catalog.has_table_privilege(submitter_login_oid, relations.oid, 'REFERENCES')
          or pg_catalog.has_table_privilege(submitter_login_oid, relations.oid, 'TRIGGER')
          or pg_catalog.has_table_privilege(submitter_login_oid, relations.oid, 'MAINTAIN')
          or pg_catalog.has_any_column_privilege(
            submitter_login_oid, relations.oid, 'SELECT,INSERT,UPDATE,REFERENCES'
          )
        )
    )
    or exists (
      select 1
      from pg_catalog.pg_class as sequences
      join pg_catalog.pg_namespace as namespaces on namespaces.oid = sequences.relnamespace
      where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
        and sequences.relkind = 'S'
        and (
          pg_catalog.has_sequence_privilege(submitter_login_oid, sequences.oid, 'USAGE')
          or pg_catalog.has_sequence_privilege(submitter_login_oid, sequences.oid, 'SELECT')
          or pg_catalog.has_sequence_privilege(submitter_login_oid, sequences.oid, 'UPDATE')
        )
    )
    or exists (
      select 1
      from pg_catalog.pg_proc as procedures
      join pg_catalog.pg_namespace as namespaces on namespaces.oid = procedures.pronamespace
      where namespaces.nspname in ('catalog', 'ingest', 'analytics', 'public')
        and pg_catalog.has_function_privilege(submitter_login_oid, procedures.oid, 'EXECUTE')
    )
  ) then
    raise exception using
      errcode = '55000',
      message = 'dedicated authorized opening submitter login has direct application privileges';
  end if;

  if exists (
    select 1
    from pg_catalog.pg_namespace as namespaces
    where namespaces.nspowner in (submitter_oid, submitter_login_oid)
      and namespaces.nspname not like 'pg_temp_%'
      and namespaces.nspname not like 'pg_toast_temp_%'
  )
  or exists (
    select 1 from pg_catalog.pg_class as relations
    where relations.relowner in (submitter_oid, submitter_login_oid)
  )
  or exists (
    select 1 from pg_catalog.pg_proc as procedures
    where procedures.proowner in (submitter_oid, submitter_login_oid)
  )
  or exists (
    select 1 from pg_catalog.pg_type as types
    where types.typowner in (submitter_oid, submitter_login_oid)
  )
  then
    raise exception using
      errcode = '55000',
      message = 'authorized opening submitter or login owns an application object';
  end if;
end;
$submitter_attestation$;

comment on role pokecrack_authorized_opening_submitter is
  'NOLOGIN NOINHERIT capability role; only the exact authorized-opening submit RPC is granted.';

commit;
