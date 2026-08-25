begin;

create table catalog.sets (
  id uuid primary key default gen_random_uuid(),
  external_source text not null,
  external_id text not null,
  name text not null,
  slug text not null unique,
  set_code text,
  language text not null default 'en',
  release_date date,
  series_name text,
  rarity_taxonomy jsonb not null default '{}'::jsonb,
  metadata jsonb not null default '{}'::jsonb,
  is_active boolean not null default true,
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint sets_external_source_check check (external_source ~ '^[a-z][a-z0-9_.-]{0,79}$'),
  constraint sets_external_id_check check (btrim(external_id) <> '' and char_length(external_id) <= 160),
  constraint sets_name_check check (btrim(name) <> '' and char_length(name) <= 160),
  constraint sets_slug_check check (slug ~ '^[a-z0-9][a-z0-9-]{0,158}[a-z0-9]$' or slug ~ '^[a-z0-9]$'),
  constraint sets_set_code_check check (set_code is null or (btrim(set_code) <> '' and char_length(set_code) <= 40)),
  constraint sets_language_check check (language = 'en'),
  constraint sets_series_name_check check (series_name is null or char_length(series_name) <= 120),
  constraint sets_rarity_taxonomy_check check (jsonb_typeof(rarity_taxonomy) = 'object'),
  constraint sets_metadata_check check (jsonb_typeof(metadata) = 'object'),
  constraint sets_external_identity_unique unique (external_source, external_id, language)
);
create index sets_release_date_idx on catalog.sets (release_date desc) where release_date is not null;
create index sets_code_idx on catalog.sets (lower(set_code)) where set_code is not null;

create table catalog.products (
  id uuid primary key default gen_random_uuid(),
  set_id uuid references catalog.sets(id) on update cascade on delete restrict,
  name text not null,
  slug text not null unique,
  product_type text not null,
  language text not null default 'en',
  sku text,
  upc text,
  ean text,
  declared_pack_count integer,
  metadata jsonb not null default '{}'::jsonb,
  is_active boolean not null default true,
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint products_name_check check (btrim(name) <> '' and char_length(name) <= 160),
  constraint products_slug_check check (slug ~ '^[a-z0-9][a-z0-9-]{0,158}[a-z0-9]$' or slug ~ '^[a-z0-9]$'),
  constraint products_type_check check (product_type in ('booster_box', 'etb', 'booster_bundle')),
  constraint products_language_check check (language = 'en'),
  constraint products_sku_check check (sku is null or (btrim(sku) <> '' and char_length(sku) <= 80)),
  constraint products_upc_check check (upc is null or upc ~ '^[0-9]{12}$'),
  constraint products_ean_check check (ean is null or ean ~ '^[0-9]{13}$'),
  constraint products_declared_pack_count_check check (declared_pack_count is null or declared_pack_count between 0 and 10000),
  constraint products_metadata_check check (jsonb_typeof(metadata) = 'object')
);
create unique index products_sku_uidx on catalog.products (lower(sku)) where sku is not null;
create unique index products_upc_uidx on catalog.products (upc) where upc is not null;
create unique index products_ean_uidx on catalog.products (ean) where ean is not null;
create index products_set_id_idx on catalog.products (set_id) where set_id is not null;

create table catalog.cards (
  id uuid primary key default gen_random_uuid(),
  external_source text not null,
  external_id text not null,
  set_id uuid not null references catalog.sets(id) on update cascade on delete restrict,
  name text not null,
  collector_number text,
  rarity text,
  language text not null default 'en',
  metadata jsonb not null default '{}'::jsonb,
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint cards_external_source_check check (external_source ~ '^[a-z][a-z0-9_.-]{0,79}$'),
  constraint cards_external_id_check check (btrim(external_id) <> '' and char_length(external_id) <= 160),
  constraint cards_name_check check (btrim(name) <> '' and char_length(name) <= 160),
  constraint cards_collector_number_check check (collector_number is null or (btrim(collector_number) <> '' and char_length(collector_number) <= 40)),
  constraint cards_rarity_check check (rarity is null or rarity ~ '^[a-z][a-z0-9_]{0,63}$'),
  constraint cards_language_check check (language = 'en'),
  constraint cards_metadata_check check (jsonb_typeof(metadata) = 'object'),
  constraint cards_external_identity_unique unique (external_source, external_id, language)
);
create unique index cards_collector_uidx on catalog.cards (set_id, lower(collector_number), language) where set_id is not null and collector_number is not null;
create index cards_set_rarity_idx on catalog.cards (set_id, rarity) where set_id is not null;
create index cards_name_idx on catalog.cards (lower(name));

create table catalog.regions (
  id uuid primary key default gen_random_uuid(),
  country_code text not null,
  state_code text,
  city text,
  name text not null,
  slug text not null unique,
  region_type text not null,
  parent_id uuid references catalog.regions(id) on update cascade on delete restrict,
  latitude numeric(9,6),
  longitude numeric(9,6),
  metadata jsonb not null default '{}'::jsonb,
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint regions_country_code_check check (country_code = 'AU'),
  constraint regions_state_code_check check (state_code is null or state_code ~ '^[A-Z]{2,3}$'),
  constraint regions_city_check check (city is null or char_length(city) <= 100),
  constraint regions_name_check check (btrim(name) <> '' and char_length(name) <= 160),
  constraint regions_slug_check check (slug ~ '^[a-z0-9][a-z0-9-]{0,158}[a-z0-9]$' or slug ~ '^[a-z0-9]$'),
  constraint regions_type_check check (region_type in ('country', 'state', 'city', 'metro')),
  constraint regions_parent_check check (parent_id is null or parent_id <> id),
  constraint regions_latitude_check check (latitude is null or latitude between -90 and 90),
  constraint regions_longitude_check check (longitude is null or longitude between -180 and 180),
  constraint regions_coordinates_pair_check check ((latitude is null) = (longitude is null)),
  constraint regions_metadata_check check (jsonb_typeof(metadata) = 'object')
);
create unique index regions_geography_uidx on catalog.regions (country_code, coalesce(state_code, ''), coalesce(lower(city), ''), region_type);
create index regions_parent_idx on catalog.regions (parent_id) where parent_id is not null;

create table catalog.retailers (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  slug text not null unique,
  country_code text,
  website_domain text,
  metadata jsonb not null default '{}'::jsonb,
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint retailers_name_check check (btrim(name) <> '' and char_length(name) <= 160),
  constraint retailers_slug_check check (slug ~ '^[a-z0-9][a-z0-9-]{0,158}[a-z0-9]$' or slug ~ '^[a-z0-9]$'),
  constraint retailers_country_code_check check (country_code is null or country_code ~ '^[A-Z]{2}$'),
  constraint retailers_domain_check check (website_domain is null or (website_domain = lower(website_domain) and website_domain ~ '^[a-z0-9.-]+$' and char_length(website_domain) <= 253)),
  constraint retailers_metadata_check check (jsonb_typeof(metadata) = 'object')
);
create unique index retailers_domain_uidx on catalog.retailers (lower(website_domain)) where website_domain is not null;

create table catalog.stores (
  id uuid primary key default gen_random_uuid(),
  retailer_id uuid not null references catalog.retailers(id) on update cascade on delete restrict,
  region_id uuid references catalog.regions(id) on update cascade on delete restrict,
  name text not null,
  slug text not null unique,
  public_address text,
  latitude numeric(9,6),
  longitude numeric(9,6),
  metadata jsonb not null default '{}'::jsonb,
  is_demo boolean not null default false,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint stores_name_check check (btrim(name) <> '' and char_length(name) <= 160),
  constraint stores_slug_check check (slug ~ '^[a-z0-9][a-z0-9-]{0,158}[a-z0-9]$' or slug ~ '^[a-z0-9]$'),
  constraint stores_public_address_check check (public_address is null or char_length(public_address) <= 500),
  constraint stores_latitude_check check (latitude is null or latitude between -90 and 90),
  constraint stores_longitude_check check (longitude is null or longitude between -180 and 180),
  constraint stores_coordinates_pair_check check ((latitude is null) = (longitude is null)),
  constraint stores_metadata_check check (jsonb_typeof(metadata) = 'object')
);
create index stores_retailer_idx on catalog.stores (retailer_id);
create index stores_region_idx on catalog.stores (region_id) where region_id is not null;

create trigger sets_set_updated_at before update on catalog.sets for each row execute function ingest.set_updated_at();
create trigger products_set_updated_at before update on catalog.products for each row execute function ingest.set_updated_at();
create trigger cards_set_updated_at before update on catalog.cards for each row execute function ingest.set_updated_at();
create trigger regions_set_updated_at before update on catalog.regions for each row execute function ingest.set_updated_at();
create trigger retailers_set_updated_at before update on catalog.retailers for each row execute function ingest.set_updated_at();
create trigger stores_set_updated_at before update on catalog.stores for each row execute function ingest.set_updated_at();

alter table catalog.sets enable row level security;
alter table catalog.products enable row level security;
alter table catalog.cards enable row level security;
alter table catalog.regions enable row level security;
alter table catalog.retailers enable row level security;
alter table catalog.stores enable row level security;
alter table catalog.sets force row level security;
alter table catalog.products force row level security;
alter table catalog.cards force row level security;
alter table catalog.regions force row level security;
alter table catalog.retailers force row level security;
alter table catalog.stores force row level security;

create policy sets_service_role_all on catalog.sets for all to service_role using (true) with check (true);
create policy products_service_role_all on catalog.products for all to service_role using (true) with check (true);
create policy cards_service_role_all on catalog.cards for all to service_role using (true) with check (true);
create policy regions_service_role_all on catalog.regions for all to service_role using (true) with check (true);
create policy retailers_service_role_all on catalog.retailers for all to service_role using (true) with check (true);
create policy stores_service_role_all on catalog.stores for all to service_role using (true) with check (true);

revoke all on all tables in schema catalog from public, anon, authenticated;
grant select, insert, update, delete on all tables in schema catalog to service_role;

comment on table catalog.regions is 'Coarse public geography only; never household/person location data.';
comment on column catalog.stores.public_address is 'Public business address only; household addresses are prohibited.';
comment on column catalog.sets.is_demo is 'True only for visibly synthetic fixture catalog data.';

commit;
