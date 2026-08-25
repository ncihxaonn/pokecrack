begin;

-- Supabase ships these roles and the extensions schema. Keeping all application
-- objects out of public makes the browser/API boundary explicit.
create schema if not exists extensions;
create extension if not exists pgcrypto with schema extensions;

create schema if not exists catalog;
create schema if not exists ingest;
create schema if not exists analytics;

comment on schema catalog is 'Curated Pokemon TCG, geography, and retailer reference data.';
comment on schema ingest is 'Private collection, extraction, queue, health, and audit data.';
comment on schema analytics is 'Private daily aggregates and statistical signals.';
comment on schema public is 'Only browser-safe, read-only API relations belong here.';

revoke all on schema catalog from public, anon, authenticated;
revoke all on schema ingest from public, anon, authenticated;
revoke all on schema analytics from public, anon, authenticated;
revoke create on schema public from public, anon, authenticated;
grant usage on schema public to anon, authenticated, service_role;
grant usage on schema catalog, ingest, analytics to service_role;

-- New objects are private by default. Migrations grant service_role and the
-- selected public views explicitly. Direct workers may instead use a dedicated
-- PostgreSQL login granted the same private-schema rights; browser clients must
-- never receive that login or the service-role key.
alter default privileges in schema catalog revoke all on tables from public, anon, authenticated;
alter default privileges in schema ingest revoke all on tables from public, anon, authenticated;
alter default privileges in schema analytics revoke all on tables from public, anon, authenticated;
alter default privileges in schema public revoke all on tables from public, anon, authenticated;
alter default privileges in schema catalog revoke all on sequences from public, anon, authenticated;
alter default privileges in schema ingest revoke all on sequences from public, anon, authenticated;
alter default privileges in schema analytics revoke all on sequences from public, anon, authenticated;
alter default privileges in schema public revoke all on sequences from public, anon, authenticated;
alter default privileges in schema catalog revoke execute on functions from public, anon, authenticated;
alter default privileges in schema ingest revoke execute on functions from public, anon, authenticated;
alter default privileges in schema analytics revoke execute on functions from public, anon, authenticated;
alter default privileges in schema public revoke execute on functions from public, anon, authenticated;

create or replace function ingest.set_updated_at()
returns trigger
language plpgsql
set search_path = pg_catalog
as $$
begin
  new.updated_at = clock_timestamp();
  return new;
end;
$$;

revoke all on function ingest.set_updated_at() from public, anon, authenticated;
grant execute on function ingest.set_updated_at() to service_role;
comment on function ingest.set_updated_at() is 'Internal trigger helper; not an API function.';

commit;
