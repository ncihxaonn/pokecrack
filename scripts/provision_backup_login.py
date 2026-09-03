#!/usr/bin/env python3
"""Provision the least-privilege login used by the managed backup script.

The command is intended for the protected, one-shot GitHub workflow.  It
accepts the owner-scoped Supabase token and the generated password only from
the process environment, sends the fixed SQL through the Supabase Management
API, and never prints the password, DSN, or API response.
"""

from __future__ import annotations

import argparse
import os
import re
import sys

try:
    from run_supabase_migrations import MigrationRunnerError, SupabaseManagementAPI
except ModuleNotFoundError:  # pragma: no cover - exercised when imported as a package
    from scripts.run_supabase_migrations import MigrationRunnerError, SupabaseManagementAPI


PROJECT_REF = re.compile(r"^[a-z0-9]{20}$")
BACKUP_PASSWORD = re.compile(r"^[A-Za-z0-9._~-]{32,128}$")
BACKUP_LOGIN = "pokecrack_backup_login"


def build_provision_sql(password: str) -> str:
    """Return the fixed transactional role/grant contract.

    The login has direct read grants because ``pg_dump`` intentionally stays
    on the login role.  The request gate is the only direct table exception:
    it receives PostgreSQL 17 ``MAINTAIN`` but no row-read privilege.  The
    service-role membership is non-inherited and SET-capable solely for the
    backup script's independent retention preflights.
    """

    if BACKUP_PASSWORD.fullmatch(password) is None:
        raise MigrationRunnerError("backup password must be an opaque 32-128 character value")

    return f"""begin;
do $$
begin
  if current_setting('server_version_num')::integer < 170000 then
    raise exception using
      errcode = '0A000',
      message = 'PokeCrack backup login requires PostgreSQL 17 or newer';
  end if;
  if to_regclass('ingest.source_request_gates') is null then
    raise exception using
      errcode = '42P01',
      message = 'PokeCrack request-gate migration is not present';
  end if;
  if not exists (select 1 from pg_catalog.pg_roles where rolname = 'service_role') then
    raise exception using
      errcode = '42704',
      message = 'Supabase service_role is not present';
  end if;
  if exists (
    select 1 from pg_catalog.pg_roles where rolname = '{BACKUP_LOGIN}'
  ) then
    raise exception using
      errcode = '42710',
      message = 'PokeCrack backup login already exists; refusing implicit rotation';
  end if;
end;
$$;

create role {BACKUP_LOGIN}
  login password '{password}'
  nosuperuser nocreatedb nocreaterole noinherit noreplication nobypassrls
  connection limit 2;

grant connect on database postgres to {BACKUP_LOGIN};
grant usage on schema catalog, ingest, analytics, public, supabase_migrations
  to {BACKUP_LOGIN};
grant select on all tables in schema catalog, ingest, analytics, public,
  supabase_migrations to {BACKUP_LOGIN};
grant select on all sequences in schema catalog, ingest, analytics, public,
  supabase_migrations to {BACKUP_LOGIN};

-- The gate's rows must remain opaque to the backup login.  MAINTAIN is the
-- PostgreSQL 17 schema-lock capability needed by pg_dump with gate data
-- excluded; it does not grant SELECT or row mutation.
revoke all on table ingest.source_request_gates from {BACKUP_LOGIN};
grant maintain on table ingest.source_request_gates to {BACKUP_LOGIN};

-- The preflight switches only this real login connection into service_role.
grant service_role to {BACKUP_LOGIN} with inherit false, set true;
revoke all on table ingest.source_request_gates from service_role;
grant maintain on table ingest.source_request_gates to service_role;

-- Migrations are applied by postgres.  Keep future application tables and
-- sequences dumpable without granting the login ownership or DDL authority.
alter default privileges for role postgres
  in schema catalog, ingest, analytics, public, supabase_migrations
  grant select on tables to {BACKUP_LOGIN};
alter default privileges for role postgres
  in schema catalog, ingest, analytics, public, supabase_migrations
  grant select on sequences to {BACKUP_LOGIN};

commit;
"""


def run(arguments: argparse.Namespace) -> int:
    project_ref = arguments.project_ref or os.environ.get("SUPABASE_PROJECT_REF", "")
    token = os.environ.get("SUPABASE_ACCESS_TOKEN", "")
    password = os.environ.get("SUPABASE_BACKUP_DB_PASSWORD", "")

    if PROJECT_REF.fullmatch(project_ref) is None:
        raise MigrationRunnerError("SUPABASE_PROJECT_REF must be a canonical project reference")
    if not token:
        raise MigrationRunnerError("SUPABASE_ACCESS_TOKEN is required")

    api = SupabaseManagementAPI(token=token, project_ref=project_ref)
    api.verify_project()
    api.query(build_provision_sql(password))
    print(f"Provisioned {BACKUP_LOGIN} through the Supabase Management API.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--project-ref",
        help="optional assertion matching SUPABASE_PROJECT_REF (never a credential)",
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    try:
        return run(build_parser().parse_args(argv))
    except MigrationRunnerError as error:
        print(f"backup login provisioning: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
