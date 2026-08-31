begin;

-- Human authorization is a separate privilege from collection. The role is
-- deliberately NOLOGIN: deployment must provision a dedicated login and make
-- it a member. Generic service_role workers can submit, but cannot review.
do $role$
declare
  reviewer_role_is_safe boolean;
begin
  if not exists (
    select 1 from pg_catalog.pg_roles
    where rolname = 'pokecrack_authorized_opening_reviewer'
  ) then
    create role pokecrack_authorized_opening_reviewer
      nosuperuser nologin noinherit nocreatedb nocreaterole noreplication nobypassrls;
  end if;

  -- The migration connection is intentionally a non-superuser in local and
  -- hosted Supabase.  Re-applying ALTER ROLE here would require superuser
  -- authority when a pre-provisioned role is marked SUPERUSER.  Creation above
  -- establishes the exact least-privilege defaults; an existing role must
  -- already match them or the migration fails closed for the operator to fix.
  select (
    not rolsuper
    and not rolcanlogin
    and not rolinherit
    and not rolcreatedb
    and not rolcreaterole
    and not rolreplication
    and not rolbypassrls
  )
  into reviewer_role_is_safe
  from pg_catalog.pg_roles
  where rolname = 'pokecrack_authorized_opening_reviewer';

  if not coalesce(reviewer_role_is_safe, false) then
    raise exception
      'pokecrack_authorized_opening_reviewer must be pre-provisioned as NOLOGIN, NOINHERIT, NOSUPERUSER, NOCREATEDB, NOCREATEROLE, NOREPLICATION, NOBYPASSRLS'
      using errcode = '42501';
  end if;
end;
$role$;

-- Keep the country code and display name in one database-owned catalogue. The
-- worker mirrors this exact 249-row contract, but the database remains the
-- authority at the RPC boundary so callers cannot smuggle a renamed country.
alter table catalog.iso_alpha2_codes
  add column country_name text;

update catalog.iso_alpha2_codes as codes
set country_name = canonical.country_name
from (
  values
    ('AD', 'Andorra'),
    ('AE', 'United Arab Emirates'),
    ('AF', 'Afghanistan'),
    ('AG', 'Antigua & Barbuda'),
    ('AI', 'Anguilla'),
    ('AL', 'Albania'),
    ('AM', 'Armenia'),
    ('AO', 'Angola'),
    ('AQ', 'Antarctica'),
    ('AR', 'Argentina'),
    ('AS', 'American Samoa'),
    ('AT', 'Austria'),
    ('AU', 'Australia'),
    ('AW', 'Aruba'),
    ('AX', 'Åland Islands'),
    ('AZ', 'Azerbaijan'),
    ('BA', 'Bosnia & Herzegovina'),
    ('BB', 'Barbados'),
    ('BD', 'Bangladesh'),
    ('BE', 'Belgium'),
    ('BF', 'Burkina Faso'),
    ('BG', 'Bulgaria'),
    ('BH', 'Bahrain'),
    ('BI', 'Burundi'),
    ('BJ', 'Benin'),
    ('BL', 'St. Barthélemy'),
    ('BM', 'Bermuda'),
    ('BN', 'Brunei'),
    ('BO', 'Bolivia'),
    ('BQ', 'Caribbean Netherlands'),
    ('BR', 'Brazil'),
    ('BS', 'Bahamas'),
    ('BT', 'Bhutan'),
    ('BV', 'Bouvet Island'),
    ('BW', 'Botswana'),
    ('BY', 'Belarus'),
    ('BZ', 'Belize'),
    ('CA', 'Canada'),
    ('CC', 'Cocos (Keeling) Islands'),
    ('CD', 'Congo - Kinshasa'),
    ('CF', 'Central African Republic'),
    ('CG', 'Congo - Brazzaville'),
    ('CH', 'Switzerland'),
    ('CI', 'Côte d’Ivoire'),
    ('CK', 'Cook Islands'),
    ('CL', 'Chile'),
    ('CM', 'Cameroon'),
    ('CN', 'China'),
    ('CO', 'Colombia'),
    ('CR', 'Costa Rica'),
    ('CU', 'Cuba'),
    ('CV', 'Cape Verde'),
    ('CW', 'Curaçao'),
    ('CX', 'Christmas Island'),
    ('CY', 'Cyprus'),
    ('CZ', 'Czechia'),
    ('DE', 'Germany'),
    ('DJ', 'Djibouti'),
    ('DK', 'Denmark'),
    ('DM', 'Dominica'),
    ('DO', 'Dominican Republic'),
    ('DZ', 'Algeria'),
    ('EC', 'Ecuador'),
    ('EE', 'Estonia'),
    ('EG', 'Egypt'),
    ('EH', 'Western Sahara'),
    ('ER', 'Eritrea'),
    ('ES', 'Spain'),
    ('ET', 'Ethiopia'),
    ('FI', 'Finland'),
    ('FJ', 'Fiji'),
    ('FK', 'Falkland Islands'),
    ('FM', 'Micronesia'),
    ('FO', 'Faroe Islands'),
    ('FR', 'France'),
    ('GA', 'Gabon'),
    ('GB', 'United Kingdom'),
    ('GD', 'Grenada'),
    ('GE', 'Georgia'),
    ('GF', 'French Guiana'),
    ('GG', 'Guernsey'),
    ('GH', 'Ghana'),
    ('GI', 'Gibraltar'),
    ('GL', 'Greenland'),
    ('GM', 'Gambia'),
    ('GN', 'Guinea'),
    ('GP', 'Guadeloupe'),
    ('GQ', 'Equatorial Guinea'),
    ('GR', 'Greece'),
    ('GS', 'South Georgia & South Sandwich Islands'),
    ('GT', 'Guatemala'),
    ('GU', 'Guam'),
    ('GW', 'Guinea-Bissau'),
    ('GY', 'Guyana'),
    ('HK', 'Hong Kong SAR China'),
    ('HM', 'Heard & McDonald Islands'),
    ('HN', 'Honduras'),
    ('HR', 'Croatia'),
    ('HT', 'Haiti'),
    ('HU', 'Hungary'),
    ('ID', 'Indonesia'),
    ('IE', 'Ireland'),
    ('IL', 'Israel'),
    ('IM', 'Isle of Man'),
    ('IN', 'India'),
    ('IO', 'British Indian Ocean Territory'),
    ('IQ', 'Iraq'),
    ('IR', 'Iran'),
    ('IS', 'Iceland'),
    ('IT', 'Italy'),
    ('JE', 'Jersey'),
    ('JM', 'Jamaica'),
    ('JO', 'Jordan'),
    ('JP', 'Japan'),
    ('KE', 'Kenya'),
    ('KG', 'Kyrgyzstan'),
    ('KH', 'Cambodia'),
    ('KI', 'Kiribati'),
    ('KM', 'Comoros'),
    ('KN', 'St. Kitts & Nevis'),
    ('KP', 'North Korea'),
    ('KR', 'South Korea'),
    ('KW', 'Kuwait'),
    ('KY', 'Cayman Islands'),
    ('KZ', 'Kazakhstan'),
    ('LA', 'Laos'),
    ('LB', 'Lebanon'),
    ('LC', 'St. Lucia'),
    ('LI', 'Liechtenstein'),
    ('LK', 'Sri Lanka'),
    ('LR', 'Liberia'),
    ('LS', 'Lesotho'),
    ('LT', 'Lithuania'),
    ('LU', 'Luxembourg'),
    ('LV', 'Latvia'),
    ('LY', 'Libya'),
    ('MA', 'Morocco'),
    ('MC', 'Monaco'),
    ('MD', 'Moldova'),
    ('ME', 'Montenegro'),
    ('MF', 'St. Martin'),
    ('MG', 'Madagascar'),
    ('MH', 'Marshall Islands'),
    ('MK', 'North Macedonia'),
    ('ML', 'Mali'),
    ('MM', 'Myanmar (Burma)'),
    ('MN', 'Mongolia'),
    ('MO', 'Macao SAR China'),
    ('MP', 'Northern Mariana Islands'),
    ('MQ', 'Martinique'),
    ('MR', 'Mauritania'),
    ('MS', 'Montserrat'),
    ('MT', 'Malta'),
    ('MU', 'Mauritius'),
    ('MV', 'Maldives'),
    ('MW', 'Malawi'),
    ('MX', 'Mexico'),
    ('MY', 'Malaysia'),
    ('MZ', 'Mozambique'),
    ('NA', 'Namibia'),
    ('NC', 'New Caledonia'),
    ('NE', 'Niger'),
    ('NF', 'Norfolk Island'),
    ('NG', 'Nigeria'),
    ('NI', 'Nicaragua'),
    ('NL', 'Netherlands'),
    ('NO', 'Norway'),
    ('NP', 'Nepal'),
    ('NR', 'Nauru'),
    ('NU', 'Niue'),
    ('NZ', 'New Zealand'),
    ('OM', 'Oman'),
    ('PA', 'Panama'),
    ('PE', 'Peru'),
    ('PF', 'French Polynesia'),
    ('PG', 'Papua New Guinea'),
    ('PH', 'Philippines'),
    ('PK', 'Pakistan'),
    ('PL', 'Poland'),
    ('PM', 'St. Pierre & Miquelon'),
    ('PN', 'Pitcairn Islands'),
    ('PR', 'Puerto Rico'),
    ('PS', 'Palestinian Territories'),
    ('PT', 'Portugal'),
    ('PW', 'Palau'),
    ('PY', 'Paraguay'),
    ('QA', 'Qatar'),
    ('RE', 'Réunion'),
    ('RO', 'Romania'),
    ('RS', 'Serbia'),
    ('RU', 'Russia'),
    ('RW', 'Rwanda'),
    ('SA', 'Saudi Arabia'),
    ('SB', 'Solomon Islands'),
    ('SC', 'Seychelles'),
    ('SD', 'Sudan'),
    ('SE', 'Sweden'),
    ('SG', 'Singapore'),
    ('SH', 'St. Helena'),
    ('SI', 'Slovenia'),
    ('SJ', 'Svalbard & Jan Mayen'),
    ('SK', 'Slovakia'),
    ('SL', 'Sierra Leone'),
    ('SM', 'San Marino'),
    ('SN', 'Senegal'),
    ('SO', 'Somalia'),
    ('SR', 'Suriname'),
    ('SS', 'South Sudan'),
    ('ST', 'São Tomé & Príncipe'),
    ('SV', 'El Salvador'),
    ('SX', 'Sint Maarten'),
    ('SY', 'Syria'),
    ('SZ', 'Eswatini'),
    ('TC', 'Turks & Caicos Islands'),
    ('TD', 'Chad'),
    ('TF', 'French Southern Territories'),
    ('TG', 'Togo'),
    ('TH', 'Thailand'),
    ('TJ', 'Tajikistan'),
    ('TK', 'Tokelau'),
    ('TL', 'Timor-Leste'),
    ('TM', 'Turkmenistan'),
    ('TN', 'Tunisia'),
    ('TO', 'Tonga'),
    ('TR', 'Türkiye'),
    ('TT', 'Trinidad & Tobago'),
    ('TV', 'Tuvalu'),
    ('TW', 'Taiwan'),
    ('TZ', 'Tanzania'),
    ('UA', 'Ukraine'),
    ('UG', 'Uganda'),
    ('UM', 'U.S. Outlying Islands'),
    ('US', 'United States'),
    ('UY', 'Uruguay'),
    ('UZ', 'Uzbekistan'),
    ('VA', 'Vatican City'),
    ('VC', 'St. Vincent & Grenadines'),
    ('VE', 'Venezuela'),
    ('VG', 'British Virgin Islands'),
    ('VI', 'U.S. Virgin Islands'),
    ('VN', 'Vietnam'),
    ('VU', 'Vanuatu'),
    ('WF', 'Wallis & Futuna'),
    ('WS', 'Samoa'),
    ('YE', 'Yemen'),
    ('YT', 'Mayotte'),
    ('ZA', 'South Africa'),
    ('ZM', 'Zambia'),
    ('ZW', 'Zimbabwe')
) as canonical(code, country_name)
where codes.code = canonical.code;

do $iso$
begin
  if (select count(*) from catalog.iso_alpha2_codes) <> 249
    or (select count(*) from catalog.iso_alpha2_codes where country_name is null) <> 0
    or (select count(distinct country_name) from catalog.iso_alpha2_codes) <> 249
  then
    raise exception using
      errcode = '23514',
      message = 'trusted ISO alpha-2 code/name catalogue must contain exactly 249 rows';
  end if;
end;
$iso$;

alter table catalog.iso_alpha2_codes
  alter column country_name set not null;
alter table catalog.iso_alpha2_codes
  add constraint iso_alpha2_codes_country_name_check check (
    char_length(country_name) between 1 and 160
    and country_name = btrim(country_name)
    and country_name = normalize(country_name, NFKC)
    and country_name !~ '[[:cntrl:]]'
  );
create unique index iso_alpha2_codes_country_name_uidx
  on catalog.iso_alpha2_codes (country_name);

create table ingest.authorized_opening_submissions (
  id uuid primary key default gen_random_uuid(),
  submission_key text not null unique,
  discovery_platform text,
  discovery_candidate_sha256 text,
  source_identity_sha256 text not null,
  authorization_reference_sha256 text not null,
  evidence_sha256 text not null,
  provenance_dedupe_sha256 text not null,
  country_code text not null
    references catalog.iso_alpha2_codes(code)
    on update restrict on delete restrict,
  country_name text not null,
  geography_basis text not null,
  geography_confidence text not null,
  language text not null,
  tcgdex_set_id text not null,
  product_scope text not null,
  observed_at timestamptz not null,
  pack_count integer not null,
  qualifying_hit_pack_count integer not null,
  denominator_complete boolean not null,
  statistics_eligible_requested boolean not null,
  state text not null default 'queued',
  revision bigint not null default 1,
  created_at timestamptz not null default statement_timestamp(),
  updated_at timestamptz not null default statement_timestamp(),
  expires_at timestamptz not null default (statement_timestamp() + interval '30 days'),
  constraint authorized_opening_submission_key_check check (
    submission_key ~ '^[a-z0-9][a-z0-9._:-]{0,159}$'
    and submission_key = btrim(submission_key)
    and submission_key = normalize(submission_key, NFKC)
    and submission_key !~ '[[:cntrl:]]'
  ),
  constraint authorized_opening_discovery_check check (
    discovery_platform is null
    or discovery_platform in ('youtube', 'bluesky', 'nostr', 'direct')
  ),
  constraint authorized_opening_candidate_check check (
    discovery_candidate_sha256 is null
    or (
      discovery_platform is not null
      and
      discovery_candidate_sha256 ~ '^[0-9a-f]{64}$'
      and discovery_platform in ('youtube', 'bluesky', 'nostr')
    )
  ),
  constraint authorized_opening_private_hashes_check check (
    source_identity_sha256 ~ '^[0-9a-f]{64}$'
    and authorization_reference_sha256 ~ '^[0-9a-f]{64}$'
    and evidence_sha256 ~ '^[0-9a-f]{64}$'
    and provenance_dedupe_sha256 ~ '^[0-9a-f]{64}$'
  ),
  constraint authorized_opening_country_name_check check (
    btrim(country_name) <> ''
    and char_length(country_name) <= 160
    and country_name = btrim(country_name)
    and country_name = normalize(country_name, NFKC)
    and country_name !~ '[[:cntrl:]]'
  ),
  constraint authorized_opening_geography_check check (
    geography_basis in (
      'opening_location',
      'publisher_country',
      'author_public_residence',
      'self_reported_country'
    )
    and geography_confidence in ('tier_a', 'tier_b')
  ),
  constraint authorized_opening_language_check check (
    char_length(language) <= 35
    and language = normalize(language, NFKC)
    and language !~ '[[:cntrl:]]'
    and language ~ '^[a-z]{2,3}(-[A-Z][a-z]{3})?(-([A-Z]{2}|[0-9]{3}))?$'
  ),
  constraint authorized_opening_set_check check (
    tcgdex_set_id = btrim(tcgdex_set_id)
    and tcgdex_set_id = normalize(tcgdex_set_id, NFKC)
    and tcgdex_set_id !~ '[[:cntrl:]]'
    and tcgdex_set_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$'
  ),
  constraint authorized_opening_product_check check (
    product_scope in ('all', 'booster_box', 'etb', 'booster_bundle')
  ),
  constraint authorized_opening_counts_check check (
    pack_count between 1 and 100000
    and qualifying_hit_pack_count between 0 and pack_count
    and denominator_complete
  ),
  constraint authorized_opening_state_check check (
    state in (
      'queued', 'in_review', 'accepted_statistics',
      'accepted_activity_only', 'duplicate', 'rejected', 'expired'
    )
  ),
  constraint authorized_opening_revision_check check (revision >= 1),
  constraint authorized_opening_time_check check (
    observed_at >= '2000-01-01 00:00:00+00'::timestamptz
    and updated_at >= created_at
    and expires_at > created_at
    and expires_at <= created_at + interval '31 days'
  )
);

create index authorized_opening_submissions_queue_idx
  on ingest.authorized_opening_submissions (state, created_at, id);
create index authorized_opening_submissions_expiry_idx
  on ingest.authorized_opening_submissions (expires_at)
  where state in ('queued', 'in_review');
create unique index authorized_opening_submissions_provenance_uidx
  on ingest.authorized_opening_submissions (provenance_dedupe_sha256);
create unique index authorized_opening_submissions_evidence_uidx
  on ingest.authorized_opening_submissions (evidence_sha256);
create unique index authorized_opening_submissions_candidate_uidx
  on ingest.authorized_opening_submissions (discovery_candidate_sha256)
  where discovery_candidate_sha256 is not null;

create table ingest.authorized_opening_review_events (
  id uuid primary key default gen_random_uuid(),
  submission_id uuid not null
    references ingest.authorized_opening_submissions(id)
    on update restrict on delete restrict,
  revision bigint not null,
  from_state text,
  to_state text not null,
  reviewer_reference_sha256 text,
  reason_code text not null,
  reviewed_at timestamptz not null default statement_timestamp(),
  unique (submission_id, revision),
  constraint authorized_opening_event_revision_check check (revision >= 1),
  constraint authorized_opening_event_states_check check (
    (from_state is null and to_state = 'queued')
    or (
      from_state is not null
      and from_state = 'queued'
      and to_state = 'in_review'
    )
    or (
      from_state is not null
      and
      from_state in ('queued', 'in_review')
      and to_state = 'expired'
    )
    or (
      from_state is not null
      and
      from_state = 'in_review'
      and to_state in (
        'accepted_statistics', 'accepted_activity_only', 'duplicate',
        'rejected', 'expired'
      )
    )
  ),
  constraint authorized_opening_event_reviewer_check check (
    (to_state = 'queued' and reviewer_reference_sha256 is null)
    or (
      to_state <> 'queued'
      and reviewer_reference_sha256 is not null
      and reviewer_reference_sha256 ~ '^[0-9a-f]{64}$'
    )
  ),
  constraint authorized_opening_event_reason_check check (
    (to_state = 'queued' and reason_code = 'submitted')
    or (to_state = 'in_review' and reason_code = 'review_started')
    or (to_state = 'accepted_statistics' and reason_code = 'evidence_verified')
    or (to_state = 'accepted_activity_only' and reason_code = 'activity_only')
    or (
      to_state = 'duplicate'
      and reason_code in ('duplicate_provenance', 'duplicate_source')
    )
    or (
      to_state = 'rejected'
      and reason_code in (
        'authorization_invalid', 'evidence_incomplete',
        'geography_unverified', 'denominator_incomplete',
        'reviewer_rejected'
      )
    )
    or (to_state = 'expired' and reason_code = 'policy_expired')
  )
);

create index authorized_opening_review_events_submission_idx
  on ingest.authorized_opening_review_events (
    submission_id, revision desc, reviewed_at desc
  );

create table ingest.authorized_opening_observations (
  id uuid primary key default gen_random_uuid(),
  submission_id uuid not null unique
    references ingest.authorized_opening_submissions(id)
    on update restrict on delete restrict,
  submission_key text not null unique,
  discovery_platform text,
  discovery_candidate_sha256 text,
  source_identity_sha256 text not null,
  authorization_reference_sha256 text not null,
  evidence_sha256 text not null unique,
  provenance_dedupe_sha256 text not null unique,
  country_code text not null
    references catalog.iso_alpha2_codes(code)
    on update restrict on delete restrict,
  country_name text not null,
  geography_basis text not null,
  geography_confidence text not null,
  language text not null,
  tcgdex_set_id text not null,
  product_scope text not null,
  observed_at timestamptz not null,
  pack_count integer not null,
  qualifying_hit_pack_count integer not null,
  denominator_complete boolean not null,
  statistics_eligible boolean not null,
  methodology_version text not null default 'authorized-opening-v1',
  accepted_at timestamptz not null default statement_timestamp(),
  constraint authorized_opening_observation_discovery_check check (
    discovery_platform is null
    or discovery_platform in ('youtube', 'bluesky', 'nostr', 'direct')
  ),
  constraint authorized_opening_observation_candidate_check check (
    discovery_candidate_sha256 is null
    or (
      discovery_platform is not null
      and
      discovery_candidate_sha256 ~ '^[0-9a-f]{64}$'
      and discovery_platform in ('youtube', 'bluesky', 'nostr')
    )
  ),
  constraint authorized_opening_observation_hashes_check check (
    source_identity_sha256 ~ '^[0-9a-f]{64}$'
    and authorization_reference_sha256 ~ '^[0-9a-f]{64}$'
    and evidence_sha256 ~ '^[0-9a-f]{64}$'
    and provenance_dedupe_sha256 ~ '^[0-9a-f]{64}$'
  ),
  constraint authorized_opening_observation_country_name_check check (
    btrim(country_name) <> ''
    and char_length(country_name) <= 160
    and country_name = btrim(country_name)
    and country_name = normalize(country_name, NFKC)
    and country_name !~ '[[:cntrl:]]'
  ),
  constraint authorized_opening_observation_geography_check check (
    geography_basis in (
      'opening_location', 'publisher_country',
      'author_public_residence', 'self_reported_country'
    )
    and geography_confidence in ('tier_a', 'tier_b')
  ),
  constraint authorized_opening_observation_language_check check (
    char_length(language) <= 35
    and language = normalize(language, NFKC)
    and language !~ '[[:cntrl:]]'
    and language ~ '^[a-z]{2,3}(-[A-Z][a-z]{3})?(-([A-Z]{2}|[0-9]{3}))?$'
  ),
  constraint authorized_opening_observation_set_check check (
    tcgdex_set_id = btrim(tcgdex_set_id)
    and tcgdex_set_id = normalize(tcgdex_set_id, NFKC)
    and tcgdex_set_id !~ '[[:cntrl:]]'
    and tcgdex_set_id ~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$'
  ),
  constraint authorized_opening_observation_product_check check (
    product_scope in ('all', 'booster_box', 'etb', 'booster_bundle')
  ),
  constraint authorized_opening_observation_counts_check check (
    pack_count between 1 and 100000
    and qualifying_hit_pack_count between 0 and pack_count
    and denominator_complete
    and statistics_eligible
  ),
  constraint authorized_opening_observation_time_check check (
    observed_at >= '2000-01-01 00:00:00+00'::timestamptz
    and accepted_at >= observed_at - interval '1 day'
    and accepted_at <= statement_timestamp() + interval '1 day'
  ),
  constraint authorized_opening_observation_method_check check (
    methodology_version = 'authorized-opening-v1'
  )
);

create index authorized_opening_observations_country_idx
  on ingest.authorized_opening_observations (
    country_code, observed_at desc, source_identity_sha256
  );
create index authorized_opening_observations_set_idx
  on ingest.authorized_opening_observations (
    tcgdex_set_id, observed_at desc, source_identity_sha256
  );
create unique index authorized_opening_observations_candidate_uidx
  on ingest.authorized_opening_observations (discovery_candidate_sha256)
  where discovery_candidate_sha256 is not null;
create unique index authorized_opening_observations_source_fact_uidx
  on ingest.authorized_opening_observations (
    source_identity_sha256,
    country_code,
    tcgdex_set_id,
    product_scope,
    observed_at,
    pack_count,
    qualifying_hit_pack_count
  );

create table ingest.authorized_opening_retractions (
  id uuid primary key default gen_random_uuid(),
  accepted_observation_id uuid not null
    references ingest.authorized_opening_observations(id)
    on update restrict on delete restrict,
  reviewer_reference_sha256 text not null,
  reason_code text not null,
  retracted_at timestamptz not null default statement_timestamp(),
  constraint authorized_opening_retraction_observation_uidx
    unique (accepted_observation_id),
  constraint authorized_opening_retraction_reviewer_check check (
    reviewer_reference_sha256 ~ '^[0-9a-f]{64}$'
  ),
  constraint authorized_opening_retraction_reason_check check (
    reason_code in (
      'authorization_revoked', 'evidence_corrected',
      'privacy_request', 'policy_takedown'
    )
  )
);

alter table ingest.authorized_opening_submissions enable row level security;
alter table ingest.authorized_opening_submissions force row level security;
alter table ingest.authorized_opening_review_events enable row level security;
alter table ingest.authorized_opening_review_events force row level security;
alter table ingest.authorized_opening_observations enable row level security;
alter table ingest.authorized_opening_observations force row level security;
alter table ingest.authorized_opening_retractions enable row level security;
alter table ingest.authorized_opening_retractions force row level security;

create policy authorized_opening_submissions_service_role_select
  on ingest.authorized_opening_submissions
  for select to service_role using (true);
create policy authorized_opening_review_events_service_role_select
  on ingest.authorized_opening_review_events
  for select to service_role using (true);
create policy authorized_opening_observations_service_role_select
  on ingest.authorized_opening_observations
  for select to service_role using (true);
create policy authorized_opening_retractions_service_role_select
  on ingest.authorized_opening_retractions
  for select to service_role using (true);

revoke all on table ingest.authorized_opening_submissions
  from public, anon, authenticated, service_role,
    pokecrack_authorized_opening_reviewer;
revoke all on table ingest.authorized_opening_review_events
  from public, anon, authenticated, service_role,
    pokecrack_authorized_opening_reviewer;
revoke all on table ingest.authorized_opening_observations
  from public, anon, authenticated, service_role,
    pokecrack_authorized_opening_reviewer;
revoke all on table ingest.authorized_opening_retractions
  from public, anon, authenticated, service_role,
    pokecrack_authorized_opening_reviewer;
grant select on table ingest.authorized_opening_submissions to service_role;
grant select on table ingest.authorized_opening_review_events to service_role;
grant select on table ingest.authorized_opening_observations to service_role;
grant select on table ingest.authorized_opening_retractions to service_role;

comment on table ingest.authorized_opening_submissions is
  'Private authorization-review queue. It accepts bounded facts and opaque fingerprints only; raw URLs, text, author identity and media are prohibited.';
comment on column ingest.authorized_opening_submissions.source_identity_sha256 is
  'Owner-produced opaque HMAC-SHA256 reference; never a plain hash of a low-entropy identity.';
comment on column ingest.authorized_opening_submissions.authorization_reference_sha256 is
  'Owner-produced opaque HMAC-SHA256 authorization reference; raw authorization text or URL is prohibited.';
comment on column ingest.authorized_opening_submissions.provenance_dedupe_sha256 is
  'Owner-produced opaque HMAC-SHA256 canonical-opening fingerprint used only for private deduplication.';
comment on table ingest.authorized_opening_review_events is
  'Append-only revision-fenced review audit. Direct mutation is denied to runtime roles.';
comment on table ingest.authorized_opening_observations is
  'Immutable accepted-statistics ledger. Public RPCs expose only aggregate counts and never its numerator or fingerprints.';
comment on column ingest.authorized_opening_observations.source_identity_sha256 is
  'Owner-produced opaque HMAC-SHA256 source reference; raw identities are prohibited.';
comment on column ingest.authorized_opening_observations.authorization_reference_sha256 is
  'Owner-produced opaque HMAC-SHA256 authorization reference; raw authorization material is prohibited.';
comment on column ingest.authorized_opening_observations.provenance_dedupe_sha256 is
  'Owner-produced opaque HMAC-SHA256 canonical-opening fingerprint.';
comment on column ingest.authorized_opening_retractions.reviewer_reference_sha256 is
  'Owner-produced opaque HMAC-SHA256 reviewer reference; raw reviewer identity is prohibited.';
comment on table ingest.authorized_opening_retractions is
  'Append-only reviewer takedown ledger. Public projections exclude matching immutable observations without deleting audit history.';

create or replace function ingest.reject_authorized_opening_immutable_mutation_v1()
returns trigger
language plpgsql
security definer
set search_path = pg_catalog
as $$
begin
  raise exception using
    errcode = '55000',
    message = 'authorized opening audit and observation rows are immutable';
end;
$$;

alter function ingest.reject_authorized_opening_immutable_mutation_v1()
  owner to postgres;
revoke all on function ingest.reject_authorized_opening_immutable_mutation_v1()
  from public, anon, authenticated, service_role,
    pokecrack_authorized_opening_reviewer;

create trigger authorized_opening_review_events_immutable
before update or delete on ingest.authorized_opening_review_events
for each row execute function ingest.reject_authorized_opening_immutable_mutation_v1();
create trigger authorized_opening_observations_immutable
before update or delete on ingest.authorized_opening_observations
for each row execute function ingest.reject_authorized_opening_immutable_mutation_v1();
create trigger authorized_opening_retractions_immutable
before update or delete on ingest.authorized_opening_retractions
for each row execute function ingest.reject_authorized_opening_immutable_mutation_v1();

-- Remaining SECURITY DEFINER RPCs and v4 projection are defined below.

create or replace function ingest.submit_authorized_opening_v1(
  payload jsonb
)
returns table(
  submission_id uuid,
  revision bigint,
  state text
)
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $submit$
<<submit_block>>
declare
  expected_keys constant text[] := array[
    'schemaVersion', 'submissionKey', 'discoveryPlatform',
    'discoveryCandidateSha256', 'sourceIdentitySha256',
    'authorizationReferenceSha256', 'evidenceSha256',
    'provenanceDedupeSha256', 'countryCode', 'countryName',
    'geographyBasis', 'geographyConfidence', 'language', 'tcgdexSetId',
    'productScope', 'observedAt', 'packCount', 'qualifyingHitPackCount',
    'denominatorComplete', 'statisticsEligible'
  ];
  submission_key text;
  discovery_platform text;
  discovery_candidate_sha256 text;
  source_identity_sha256 text;
  authorization_reference_sha256 text;
  evidence_sha256 text;
  provenance_dedupe_sha256 text;
  country_code text;
  payload_country_name text;
  canonical_country_name text;
  geography_basis text;
  geography_confidence text;
  language text;
  tcgdex_set_id text;
  product_scope text;
  observed_at timestamptz;
  pack_count integer;
  qualifying_hit_pack_count integer;
  denominator_complete boolean;
  statistics_eligible boolean;
  tcgdex_set_id_row uuid;
  submitted_at timestamptz := clock_timestamp();
  inserted_row ingest.authorized_opening_submissions%rowtype;
  existing_row ingest.authorized_opening_submissions%rowtype;
begin
  if payload is null
    or jsonb_typeof(payload) is distinct from 'object'
    or octet_length(payload::text) > 16384
    or not (payload ?& expected_keys)
    or payload - expected_keys <> '{}'::jsonb
  then
    raise exception using
      errcode = '22023',
      message = 'authorized opening payload must match the exact bounded v1 contract';
  end if;

  if jsonb_typeof(payload -> 'schemaVersion') is distinct from 'string'
    or payload ->> 'schemaVersion' <> '1.0.0'
    or jsonb_typeof(payload -> 'submissionKey') is distinct from 'string'
    or jsonb_typeof(payload -> 'discoveryPlatform') not in ('string', 'null')
    or jsonb_typeof(payload -> 'discoveryCandidateSha256') not in ('string', 'null')
    or jsonb_typeof(payload -> 'sourceIdentitySha256') is distinct from 'string'
    or jsonb_typeof(payload -> 'authorizationReferenceSha256') is distinct from 'string'
    or jsonb_typeof(payload -> 'evidenceSha256') is distinct from 'string'
    or jsonb_typeof(payload -> 'provenanceDedupeSha256') is distinct from 'string'
    or jsonb_typeof(payload -> 'countryCode') is distinct from 'string'
    or jsonb_typeof(payload -> 'countryName') is distinct from 'string'
    or jsonb_typeof(payload -> 'geographyBasis') is distinct from 'string'
    or jsonb_typeof(payload -> 'geographyConfidence') is distinct from 'string'
    or jsonb_typeof(payload -> 'language') is distinct from 'string'
    or jsonb_typeof(payload -> 'tcgdexSetId') is distinct from 'string'
    or jsonb_typeof(payload -> 'productScope') is distinct from 'string'
    or jsonb_typeof(payload -> 'observedAt') is distinct from 'string'
    or jsonb_typeof(payload -> 'packCount') is distinct from 'number'
    or jsonb_typeof(payload -> 'qualifyingHitPackCount') is distinct from 'number'
    or jsonb_typeof(payload -> 'denominatorComplete') is distinct from 'boolean'
    or jsonb_typeof(payload -> 'statisticsEligible') is distinct from 'boolean'
  then
    raise exception using
      errcode = '22023',
      message = 'authorized opening payload fields have invalid JSON types';
  end if;

  submission_key := payload ->> 'submissionKey';
  discovery_platform := payload ->> 'discoveryPlatform';
  discovery_candidate_sha256 := payload ->> 'discoveryCandidateSha256';
  source_identity_sha256 := payload ->> 'sourceIdentitySha256';
  authorization_reference_sha256 := payload ->> 'authorizationReferenceSha256';
  evidence_sha256 := payload ->> 'evidenceSha256';
  provenance_dedupe_sha256 := payload ->> 'provenanceDedupeSha256';
  country_code := payload ->> 'countryCode';
  payload_country_name := payload ->> 'countryName';
  geography_basis := payload ->> 'geographyBasis';
  geography_confidence := payload ->> 'geographyConfidence';
  language := payload ->> 'language';
  tcgdex_set_id := payload ->> 'tcgdexSetId';
  product_scope := payload ->> 'productScope';
  denominator_complete := (payload ->> 'denominatorComplete')::boolean;
  statistics_eligible := (payload ->> 'statisticsEligible')::boolean;

  if submission_key is null
    or char_length(submission_key) not between 1 and 160
    or submission_key <> btrim(submission_key)
    or submission_key <> normalize(submission_key, NFKC)
    or submission_key ~ '[[:cntrl:]]'
    or submission_key !~ '^[a-z0-9][a-z0-9._:-]{0,159}$'
  then
    raise exception using errcode = '22023', message = 'submissionKey is not canonical';
  end if;

  if discovery_platform is not null
    and discovery_platform not in ('youtube', 'bluesky', 'nostr', 'direct')
  then
    raise exception using errcode = '22023', message = 'discoveryPlatform is not allowed';
  end if;
  if discovery_candidate_sha256 is not null
    and (
      discovery_candidate_sha256 !~ '^[0-9a-f]{64}$'
      or discovery_platform not in ('youtube', 'bluesky', 'nostr')
    )
  then
    raise exception using
      errcode = '22023',
      message = 'discoveryCandidateSha256 requires a supported social platform';
  end if;
  if source_identity_sha256 !~ '^[0-9a-f]{64}$'
    or authorization_reference_sha256 !~ '^[0-9a-f]{64}$'
    or evidence_sha256 !~ '^[0-9a-f]{64}$'
    or provenance_dedupe_sha256 !~ '^[0-9a-f]{64}$'
  then
    raise exception using errcode = '22023', message = 'opaque references must be lowercase SHA-256';
  end if;

  select codes.country_name
  into canonical_country_name
  from catalog.iso_alpha2_codes as codes
  where codes.code = country_code;
  if not found
    or payload_country_name is distinct from canonical_country_name
  then
    raise exception using
      errcode = '22023',
      message = 'countryCode and countryName must match the trusted ISO catalogue';
  end if;

  if geography_basis not in (
      'opening_location', 'publisher_country',
      'author_public_residence', 'self_reported_country'
    )
    or geography_confidence not in ('tier_a', 'tier_b')
  then
    raise exception using errcode = '22023', message = 'geography fields are not allowed';
  end if;
  if language !~ '^[a-z]{2,3}(-[A-Z][a-z]{3})?(-([A-Z]{2}|[0-9]{3}))?$'
    or language <> normalize(language, NFKC)
    or language <> btrim(language)
    or language ~ '[[:cntrl:]]'
  then
    raise exception using errcode = '22023', message = 'language is not canonical';
  end if;
  if tcgdex_set_id is null
    or char_length(tcgdex_set_id) not between 1 and 160
    or tcgdex_set_id <> btrim(tcgdex_set_id)
    or tcgdex_set_id <> normalize(tcgdex_set_id, NFKC)
    or tcgdex_set_id ~ '[[:cntrl:]]'
    or tcgdex_set_id !~ '^[A-Za-z0-9][A-Za-z0-9._-]{0,159}$'
  then
    raise exception using errcode = '22023', message = 'tcgdexSetId is not canonical';
  end if;
  if product_scope not in ('all', 'booster_box', 'etb', 'booster_bundle') then
    raise exception using errcode = '22023', message = 'productScope is not allowed';
  end if;

  if (payload ->> 'observedAt') !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}Z$' then
    raise exception using errcode = '22023', message = 'observedAt must use UTC seconds';
  end if;
  begin
    observed_at := (payload ->> 'observedAt')::timestamptz;
  exception when others then
    raise exception using errcode = '22023', message = 'observedAt is not a valid timestamp';
  end;
  if observed_at < '2000-01-01 00:00:00+00'::timestamptz
    or observed_at > submitted_at + interval '24 hours'
  then
    raise exception using errcode = '22023', message = 'observedAt is outside the approved range';
  end if;

  if (payload ->> 'packCount') !~ '^(0|[1-9][0-9]{0,5})$'
    or (payload ->> 'qualifyingHitPackCount') !~ '^(0|[1-9][0-9]{0,5})$'
  then
    raise exception using errcode = '22023', message = 'opening counts must be canonical integers';
  end if;
  pack_count := (payload ->> 'packCount')::integer;
  qualifying_hit_pack_count := (payload ->> 'qualifyingHitPackCount')::integer;
  if pack_count not between 1 and 100000
    or qualifying_hit_pack_count not between 0 and pack_count
    or not denominator_complete
  then
    raise exception using
      errcode = '22023',
      message = 'opening counts must describe one complete bounded denominator';
  end if;

  -- The external id is checked against both the live catalog and its current
  -- browser-safe projection. This rejects demo, inactive, stale, and unknown
  -- TCGdex identities before they enter the review queue.
  select sets.id
  into tcgdex_set_id_row
  from catalog.sets as sets
  join public.tcgdex_set_index as set_index
    on set_index.set_id = sets.id
   and set_index.language = 'en'
   and set_index.is_current
   and not set_index.is_demo
  where sets.external_source = 'tcgdex'
    and sets.external_id = tcgdex_set_id
    and sets.language = 'en'
    and sets.is_active
    and not sets.is_demo
  limit 1;
  if not found or tcgdex_set_id_row is null then
    raise exception using
      errcode = '22023',
      message = 'tcgdexSetId must identify a current live non-demo TCGdex set';
  end if;

  -- ON CONFLICT DO NOTHING is deliberate: it waits for a concurrent writer,
  -- then lets us return the existing exact row for an idempotent retry while
  -- still rejecting a changed payload or a competing provenance fingerprint.
  insert into ingest.authorized_opening_submissions (
    submission_key,
    discovery_platform,
    discovery_candidate_sha256,
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
    revision,
    created_at,
    updated_at,
    expires_at
  ) values (
    submission_key,
    discovery_platform,
    discovery_candidate_sha256,
    source_identity_sha256,
    authorization_reference_sha256,
    evidence_sha256,
    provenance_dedupe_sha256,
    country_code,
    canonical_country_name,
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
    'queued',
    1,
    submitted_at,
    submitted_at,
    submitted_at + interval '30 days'
  )
  on conflict do nothing
  returning * into inserted_row;

  if not found then
    select submissions.*
    into existing_row
    from ingest.authorized_opening_submissions as submissions
    where submissions.submission_key = submit_block.submission_key
    for update;

    if found then
      if existing_row.discovery_platform is distinct from discovery_platform
        or existing_row.discovery_candidate_sha256 is distinct from discovery_candidate_sha256
        or existing_row.source_identity_sha256 is distinct from source_identity_sha256
        or existing_row.authorization_reference_sha256 is distinct from authorization_reference_sha256
        or existing_row.evidence_sha256 is distinct from evidence_sha256
        or existing_row.provenance_dedupe_sha256 is distinct from provenance_dedupe_sha256
        or existing_row.country_code is distinct from country_code
        or existing_row.country_name is distinct from canonical_country_name
        or existing_row.geography_basis is distinct from geography_basis
        or existing_row.geography_confidence is distinct from geography_confidence
        or existing_row.language is distinct from language
        or existing_row.tcgdex_set_id is distinct from tcgdex_set_id
        or existing_row.product_scope is distinct from product_scope
        or existing_row.observed_at is distinct from observed_at
        or existing_row.pack_count is distinct from pack_count
        or existing_row.qualifying_hit_pack_count is distinct from qualifying_hit_pack_count
        or existing_row.denominator_complete is distinct from denominator_complete
        or existing_row.statistics_eligible_requested is distinct from statistics_eligible
      then
        raise exception using
          errcode = '23505',
          message = 'submissionKey already belongs to a different authorized opening payload';
      end if;

      return query select existing_row.id, existing_row.revision, existing_row.state;
      return;
    end if;

    if exists (
      select 1 from ingest.authorized_opening_submissions as submissions
      where submissions.provenance_dedupe_sha256 = submit_block.provenance_dedupe_sha256
    ) then
      raise exception using
        errcode = '23505',
        message = 'provenanceDedupeSha256 is already assigned to another submission';
    end if;
    if exists (
      select 1 from ingest.authorized_opening_submissions as submissions
      where submissions.evidence_sha256 = submit_block.evidence_sha256
    ) then
      raise exception using
        errcode = '23505',
        message = 'evidenceSha256 is already assigned to another submission';
    end if;
    if discovery_candidate_sha256 is not null and exists (
      select 1 from ingest.authorized_opening_submissions as submissions
      where submissions.discovery_candidate_sha256 = submit_block.discovery_candidate_sha256
    ) then
      raise exception using
        errcode = '23505',
        message = 'discoveryCandidateSha256 is already assigned to another submission';
    end if;
    raise exception using
      errcode = '40001',
      message = 'authorized opening submission was concurrently changed';
  end if;

  insert into ingest.authorized_opening_review_events (
    submission_id,
    revision,
    from_state,
    to_state,
    reviewer_reference_sha256,
    reason_code,
    reviewed_at
  ) values (
    inserted_row.id,
    inserted_row.revision,
    null,
    'queued',
    null,
    'submitted',
    submitted_at
  );

  return query select inserted_row.id, inserted_row.revision, inserted_row.state;
end;
$submit$;

alter function ingest.submit_authorized_opening_v1(jsonb) owner to postgres;
revoke all on function ingest.submit_authorized_opening_v1(jsonb)
  from public, anon, authenticated, service_role,
    pokecrack_authorized_opening_reviewer;
grant execute on function ingest.submit_authorized_opening_v1(jsonb)
  to service_role;
comment on function ingest.submit_authorized_opening_v1(jsonb) is
  'Strict service-role-only insertion and idempotent replay gate for owner-authorized opening evidence.';

create or replace function ingest.list_authorized_opening_reviews_v1(
  requested_state text,
  requested_limit integer
)
returns table(
  submission_id uuid,
  revision bigint,
  state text,
  discovery_platform text,
  country_code text,
  geography_basis text,
  geography_confidence text,
  language text,
  tcgdex_set_id text,
  product_scope text,
  observed_at timestamptz,
  pack_count integer,
  qualifying_hit_pack_count integer,
  denominator_complete boolean,
  statistics_eligible_requested boolean,
  created_at timestamptz,
  updated_at timestamptz,
  expires_at timestamptz
)
language plpgsql
security definer
stable
parallel restricted
set search_path = pg_catalog
as $list$
begin
  if requested_state is null
    or requested_state <> btrim(requested_state)
    or requested_state not in (
      'all', 'queued', 'in_review', 'accepted_statistics',
      'accepted_activity_only', 'duplicate', 'rejected', 'expired'
    )
  then
    raise exception using errcode = '22023', message = 'state filter is not allowed';
  end if;
  if requested_limit is null or requested_limit not between 1 and 100 then
    raise exception using errcode = '22023', message = 'limit must be between 1 and 100';
  end if;

  return query
  select
    submissions.id,
    submissions.revision,
    submissions.state,
    submissions.discovery_platform,
    submissions.country_code,
    submissions.geography_basis,
    submissions.geography_confidence,
    submissions.language,
    submissions.tcgdex_set_id,
    submissions.product_scope,
    submissions.observed_at,
    submissions.pack_count,
    submissions.qualifying_hit_pack_count,
    submissions.denominator_complete,
    submissions.statistics_eligible_requested,
    submissions.created_at,
    submissions.updated_at,
    submissions.expires_at
  from ingest.authorized_opening_submissions as submissions
  where requested_state = 'all'
    or submissions.state = requested_state
  order by submissions.created_at, submissions.id
  limit requested_limit;
end;
$list$;

alter function ingest.list_authorized_opening_reviews_v1(text, integer)
  owner to postgres;
revoke all on function ingest.list_authorized_opening_reviews_v1(text, integer)
  from public, anon, authenticated, service_role;
grant execute on function ingest.list_authorized_opening_reviews_v1(text, integer)
  to pokecrack_authorized_opening_reviewer;
comment on function ingest.list_authorized_opening_reviews_v1(text, integer) is
  'Reviewer-only bounded queue projection; opaque references and submission keys never leave the database.';

create or replace function ingest.review_authorized_opening_v1(
  requested_submission_id uuid,
  expected_revision bigint,
  target_state text,
  reviewer_reference_sha256 text,
  reason_code text
)
returns table(
  submission_id uuid,
  revision bigint,
  state text,
  accepted_observation_id uuid
)
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $review$
declare
  current_row ingest.authorized_opening_submissions%rowtype;
  changed_row ingest.authorized_opening_submissions%rowtype;
  review_time timestamptz := clock_timestamp();
  duplicate_reason text;
  live_set_id uuid;
  observation_id uuid;
begin
  if requested_submission_id is null
    or expected_revision is null
    or expected_revision < 1
    or target_state is null
    or target_state not in (
      'in_review', 'accepted_statistics', 'accepted_activity_only',
      'duplicate', 'rejected', 'expired'
    )
    or reviewer_reference_sha256 is null
    or reviewer_reference_sha256 !~ '^[0-9a-f]{64}$'
    or reason_code is null
    or reason_code <> btrim(reason_code)
    or char_length(reason_code) not between 1 and 64
    or reason_code <> normalize(reason_code, NFKC)
    or reason_code ~ '[[:cntrl:]]'
  then
    raise exception using errcode = '22023', message = 'review request is not canonical';
  end if;

  if (target_state = 'in_review' and reason_code <> 'review_started')
    or (target_state = 'accepted_statistics' and reason_code <> 'evidence_verified')
    or (target_state = 'accepted_activity_only' and reason_code <> 'activity_only')
    or (target_state = 'duplicate' and reason_code not in ('duplicate_provenance', 'duplicate_source'))
    or (target_state = 'rejected' and reason_code not in (
      'authorization_invalid', 'evidence_incomplete',
      'geography_unverified', 'denominator_incomplete', 'reviewer_rejected'
    ))
    or (target_state = 'expired' and reason_code <> 'policy_expired')
  then
    raise exception using errcode = '22023', message = 'review state and reason are not an allowed pair';
  end if;

  select submissions.*
  into current_row
  from ingest.authorized_opening_submissions as submissions
  where submissions.id = requested_submission_id
  for update;
  if not found then
    raise exception using errcode = 'P0002', message = 'authorized opening submission does not exist';
  end if;
  if current_row.revision <> expected_revision then
    raise exception using
      errcode = '40001',
      message = 'authorized opening review revision is stale';
  end if;

  -- Expiry is database-clock based and fenced by the same row lock. A review
  -- arriving after the queue deadline can only produce the immutable expired
  -- event, never an accepted observation.
  if current_row.state in ('queued', 'in_review')
    and current_row.expires_at <= review_time
    and target_state <> 'expired'
  then
    target_state := 'expired';
    reason_code := 'policy_expired';
  end if;

  if (current_row.state = 'queued' and target_state not in ('in_review', 'expired'))
    or (current_row.state = 'in_review' and target_state not in (
      'accepted_statistics', 'accepted_activity_only', 'duplicate', 'rejected', 'expired'
    ))
    or current_row.state not in ('queued', 'in_review')
  then
    raise exception using
      errcode = '55000',
      message = 'authorized opening submission is not in a reviewable state';
  end if;

  if target_state = 'accepted_statistics' then
    if not current_row.statistics_eligible_requested
      or not current_row.denominator_complete
    then
      raise exception using
        errcode = '22023',
        message = 'statistics acceptance requires an eligible complete denominator';
    end if;

    select sets.id
    into live_set_id
    from catalog.sets as sets
    join public.tcgdex_set_index as set_index
      on set_index.set_id = sets.id
     and set_index.language = 'en'
     and set_index.is_current
     and not set_index.is_demo
    where sets.external_source = 'tcgdex'
      and sets.external_id = current_row.tcgdex_set_id
      and sets.language = 'en'
      and sets.is_active
      and not sets.is_demo
    limit 1;
    if not found or live_set_id is null then
      raise exception using
        errcode = '55000',
        message = 'statistics acceptance requires a current live non-demo TCGdex set';
    end if;

    begin
      insert into ingest.authorized_opening_observations (
        submission_id,
        submission_key,
        discovery_platform,
        discovery_candidate_sha256,
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
      ) values (
        current_row.id,
        current_row.submission_key,
        current_row.discovery_platform,
        current_row.discovery_candidate_sha256,
        current_row.source_identity_sha256,
        current_row.authorization_reference_sha256,
        current_row.evidence_sha256,
        current_row.provenance_dedupe_sha256,
        current_row.country_code,
        current_row.country_name,
        current_row.geography_basis,
        current_row.geography_confidence,
        current_row.language,
        current_row.tcgdex_set_id,
        current_row.product_scope,
        current_row.observed_at,
        current_row.pack_count,
        current_row.qualifying_hit_pack_count,
        current_row.denominator_complete,
        true,
        'authorized-opening-v1',
        review_time
      ) returning id into observation_id;
    exception when unique_violation then
      if exists (
        select 1 from ingest.authorized_opening_observations as observations
        where observations.provenance_dedupe_sha256 = current_row.provenance_dedupe_sha256
      ) then
        duplicate_reason := 'duplicate_provenance';
      elsif exists (
        select 1 from ingest.authorized_opening_observations as observations
        where observations.evidence_sha256 = current_row.evidence_sha256
          or observations.discovery_candidate_sha256 is not distinct from current_row.discovery_candidate_sha256
             and current_row.discovery_candidate_sha256 is not null
          or (
            observations.source_identity_sha256 = current_row.source_identity_sha256
            and observations.country_code = current_row.country_code
            and observations.tcgdex_set_id = current_row.tcgdex_set_id
            and observations.product_scope = current_row.product_scope
            and observations.observed_at = current_row.observed_at
            and observations.pack_count = current_row.pack_count
            and observations.qualifying_hit_pack_count = current_row.qualifying_hit_pack_count
          )
      ) then
        duplicate_reason := 'duplicate_source';
      else
        raise;
      end if;
      target_state := 'duplicate';
      reason_code := duplicate_reason;
    end;
  end if;

  update ingest.authorized_opening_submissions as submissions
  set state = target_state,
      revision = submissions.revision + 1,
      updated_at = review_time
  where submissions.id = current_row.id
    and submissions.revision = expected_revision
    and submissions.state = current_row.state
  returning * into changed_row;
  if not found then
    raise exception using errcode = '40001', message = 'authorized opening review lost its row fence';
  end if;

  insert into ingest.authorized_opening_review_events (
    submission_id,
    revision,
    from_state,
    to_state,
    reviewer_reference_sha256,
    reason_code,
    reviewed_at
  ) values (
    changed_row.id,
    changed_row.revision,
    current_row.state,
    changed_row.state,
    reviewer_reference_sha256,
    reason_code,
    review_time
  );

  return query select changed_row.id, changed_row.revision, changed_row.state, observation_id;
end;
$review$;

alter function ingest.review_authorized_opening_v1(uuid, bigint, text, text, text)
  owner to postgres;
revoke all on function ingest.review_authorized_opening_v1(uuid, bigint, text, text, text)
  from public, anon, authenticated, service_role;
grant execute on function ingest.review_authorized_opening_v1(uuid, bigint, text, text, text)
  to pokecrack_authorized_opening_reviewer;
comment on function ingest.review_authorized_opening_v1(uuid, bigint, text, text, text) is
  'Reviewer-only row-lock and revision-fenced decision path that atomically appends immutable accepted observations.';

create or replace function ingest.retract_authorized_opening_v1(
  requested_observation_id uuid,
  reviewer_reference_sha256 text,
  requested_reason_code text
)
returns table(
  accepted_observation_id uuid,
  reason_code text,
  retracted_at timestamptz
)
language plpgsql
security definer
volatile
parallel unsafe
set search_path = pg_catalog
as $retract$
declare
  existing_observation ingest.authorized_opening_observations%rowtype;
  inserted_retraction ingest.authorized_opening_retractions%rowtype;
  existing_retraction ingest.authorized_opening_retractions%rowtype;
  retraction_time timestamptz := clock_timestamp();
begin
  if requested_observation_id is null
    or reviewer_reference_sha256 is null
    or reviewer_reference_sha256 !~ '^[0-9a-f]{64}$'
    or requested_reason_code is null
    or requested_reason_code <> btrim(requested_reason_code)
    or requested_reason_code <> normalize(requested_reason_code, NFKC)
    or requested_reason_code ~ '[[:cntrl:]]'
    or requested_reason_code not in (
      'authorization_revoked', 'evidence_corrected',
      'privacy_request', 'policy_takedown'
    )
  then
    raise exception using errcode = '22023', message = 'retraction request is not canonical';
  end if;

  select observations.*
  into existing_observation
  from ingest.authorized_opening_observations as observations
  where observations.id = requested_observation_id
  for update;
  if not found then
    raise exception using errcode = 'P0002', message = 'accepted authorized observation does not exist';
  end if;

  insert into ingest.authorized_opening_retractions (
    accepted_observation_id,
    reviewer_reference_sha256,
    reason_code,
    retracted_at
  ) values (
    existing_observation.id,
    reviewer_reference_sha256,
    requested_reason_code,
    retraction_time
  )
  on conflict on constraint authorized_opening_retraction_observation_uidx do nothing
  returning * into inserted_retraction;

  if found then
    return query select
      inserted_retraction.accepted_observation_id,
      inserted_retraction.reason_code,
      inserted_retraction.retracted_at;
    return;
  end if;

  select retractions.*
  into existing_retraction
  from ingest.authorized_opening_retractions as retractions
  where retractions.accepted_observation_id = existing_observation.id
  for update;
  if not found then
    raise exception using errcode = '40001', message = 'authorized opening retraction was concurrently changed';
  end if;
  if existing_retraction.reason_code <> requested_reason_code then
    raise exception using
      errcode = '23505',
      message = 'accepted authorized observation already has a different retraction';
  end if;

  return query select
    existing_retraction.accepted_observation_id,
    existing_retraction.reason_code,
    existing_retraction.retracted_at;
end;
$retract$;

alter function ingest.retract_authorized_opening_v1(uuid, text, text)
  owner to postgres;
revoke all on function ingest.retract_authorized_opening_v1(uuid, text, text)
  from public, anon, authenticated, service_role;
grant execute on function ingest.retract_authorized_opening_v1(uuid, text, text)
  to pokecrack_authorized_opening_reviewer;
comment on function ingest.retract_authorized_opening_v1(uuid, text, text) is
  'Reviewer-only append-only retraction ledger; public projections filter retracted observations without deleting history.';

create or replace function public.get_public_dashboard_snapshot_v4()
returns jsonb
language sql
stable
security definer
parallel restricted
set search_path = pg_catalog
as $dashboard$
with base_snapshot as materialized (
  select public.get_public_dashboard_snapshot_v3() as value
),
selected_period as (
  select
    (statement_timestamp() at time zone 'UTC')::date - 364 as period_start,
    (statement_timestamp() at time zone 'UTC')::date as period_end
),
authorized_rows as (
  -- The unique provenance index already prevents duplicates. DISTINCT ON is
  -- an additional fail-closed guard for repaired/imported legacy rows.
  select distinct on (observations.provenance_dedupe_sha256)
    observations.country_code,
    observations.observed_at,
    observations.accepted_at,
    observations.pack_count,
    observations.source_identity_sha256,
    observations.tcgdex_set_id
  from ingest.authorized_opening_observations as observations
  join catalog.iso_alpha2_codes as countries
    on countries.code = observations.country_code
  join catalog.sets as sets
    on sets.external_source = 'tcgdex'
   and sets.external_id = observations.tcgdex_set_id
   and sets.language = 'en'
   and sets.is_active
   and not sets.is_demo
  join public.tcgdex_set_index as set_index
    on set_index.set_id = sets.id
   and set_index.language = 'en'
   and set_index.is_current
   and not set_index.is_demo
  where observations.statistics_eligible
    and (observations.observed_at at time zone 'UTC')::date
      between (select period_start from selected_period)
      and (select period_end from selected_period)
    and not exists (
      select 1
      from ingest.authorized_opening_retractions as retractions
      where retractions.accepted_observation_id = observations.id
    )
  order by observations.provenance_dedupe_sha256, observations.accepted_at desc, observations.id desc
),
authorized_country_metrics as (
  select
    rows.country_code,
    countries.country_name,
    period.period_start,
    period.period_end,
    sum(rows.pack_count)::bigint as observed_packs,
    count(*)::bigint as complete_openings,
    count(distinct rows.source_identity_sha256)::integer as independent_sources,
    max(rows.accepted_at) as updated_at
  from authorized_rows as rows
  join catalog.iso_alpha2_codes as countries
    on countries.code = rows.country_code
  cross join selected_period as period
  group by rows.country_code, countries.country_name, period.period_start, period.period_end
),
authorized_map_rows as (
  select
    metrics.country_code,
    jsonb_build_object(
      'countryCode', metrics.country_code,
      'countryName', metrics.country_name,
      'periodStart', metrics.period_start,
      'periodEnd', metrics.period_end,
      'setScope', 'all',
      'productScope', 'all',
      'metricKey', 'qualifying_hit_pack_rate',
      'metricVersion', 'authorized-opening-v1',
      'packsObserved', metrics.observed_packs,
      'openings', metrics.complete_openings,
      'independentSources', metrics.independent_sources,
      'baselineRate', null,
      'hitRate', null,
      'posteriorMean', null,
      'credibleInterval', null,
      'deltaFromBaseline', null,
      'state', case
        when metrics.observed_packs < 30 or metrics.independent_sources < 3
          then 'insufficient'
        else 'pending'
      end,
      'sampleNote', case
        when metrics.observed_packs < 30 or metrics.independent_sources < 3
          then format(
            'Rate withheld: %s observed packs across %s independent source%s. Publication requires at least 30 packs and three sources.',
            metrics.observed_packs,
            metrics.independent_sources,
            case when metrics.independent_sources = 1 then '' else 's' end
          )
        else 'The evidence threshold is met, but the reviewed baseline and interval publisher has not completed; all inference fields remain withheld.'
      end,
      'methodologyVersion', 'authorized-opening-v1',
      'updatedAt', metrics.updated_at
    ) as item
  from authorized_country_metrics as metrics
),
base_map_rows as (
  select
    cells.item ->> 'countryCode' as country_code,
    cells.item,
    3 as priority
  from base_snapshot as base
  cross join lateral jsonb_array_elements(
    coalesce(base.value -> 'mapCells', '[]'::jsonb)
  ) as cells(item)
  where cells.item ->> 'countryCode' is not null
),
selected_map_rows as (
  select distinct on (candidates.country_code)
    candidates.country_code,
    candidates.item
  from (
    select base.country_code, base.item, base.priority from base_map_rows as base
    union all
    select authorized.country_code, authorized.item, 2
    from authorized_map_rows as authorized
  ) as candidates
  order by candidates.country_code, candidates.priority desc
),
public_map_snapshot as (
  select
    coalesce(
      jsonb_agg(rows.item order by rows.item ->> 'countryName', rows.country_code),
      '[]'::jsonb
    ) as value,
    count(*)::integer as country_count,
    count(*) filter (where rows.item -> 'hitRate' <> 'null'::jsonb)::integer
      as published_rate_count,
    coalesce(sum((rows.item ->> 'packsObserved')::bigint), 0)::bigint
      as observed_packs,
    coalesce(sum((rows.item ->> 'openings')::bigint), 0)::bigint
      as complete_openings,
    coalesce(sum((rows.item ->> 'independentSources')::bigint), 0)::bigint
      as source_country_contributions,
    max((rows.item ->> 'updatedAt')::timestamptz) as as_of,
    case
      when count(distinct rows.item ->> 'methodologyVersion') = 1
        then min(rows.item ->> 'methodologyVersion')
      else null
    end as methodology_version
  from selected_map_rows as rows
),
authorized_set_metrics as (
  select
    sets.slug,
    sets.name,
    sets.series_name,
    sets.release_date,
    sum(rows.pack_count)::bigint as observed_packs,
    count(*)::bigint as complete_openings,
    count(distinct rows.source_identity_sha256)::integer as independent_sources,
    max(rows.accepted_at) as updated_at
  from authorized_rows as rows
  join catalog.sets as sets
    on sets.external_source = 'tcgdex'
   and sets.external_id = rows.tcgdex_set_id
   and sets.language = 'en'
   and sets.is_active
   and not sets.is_demo
   and sets.series_name is not null
   and sets.release_date is not null
  group by sets.slug, sets.name, sets.series_name, sets.release_date
  order by sets.release_date desc nulls last, sets.name, sets.slug
  limit 100
),
base_set_rows as (
  select
    sets.item ->> 'slug' as slug,
    sets.item,
    2 as priority
  from base_snapshot as base
  cross join lateral jsonb_array_elements(
    coalesce(base.value -> 'sets', '[]'::jsonb)
  ) as sets(item)
  where sets.item ->> 'slug' is not null
),
authorized_set_rows as (
  select
    metrics.slug,
    jsonb_build_object(
      'slug', metrics.slug,
      'name', metrics.name,
      'series', metrics.series_name,
      'releaseDate', metrics.release_date,
      'signal', case
        when metrics.observed_packs < 30 or metrics.independent_sources < 3
          then 'Rate withheld; the publication threshold is not met.'
        else 'Publication pending; the reviewed baseline and interval are not available yet.'
      end,
      'packsObserved', metrics.observed_packs,
      'openings', metrics.complete_openings,
      'independentSources', metrics.independent_sources,
      'baselineRate', null,
      'hitRate', null,
      'posteriorMean', null,
      'credibleInterval', null,
      'deltaFromBaseline', null,
      'state', case
        when metrics.observed_packs < 30 or metrics.independent_sources < 3
          then 'insufficient'
        else 'pending'
      end,
      'sampleNote', case
        when metrics.observed_packs < 30 or metrics.independent_sources < 3
          then format(
            'Rate withheld: %s observed packs across %s independent source%s. Publication requires at least 30 packs and three sources.',
            metrics.observed_packs,
            metrics.independent_sources,
            case when metrics.independent_sources = 1 then '' else 's' end
          )
        else 'The evidence threshold is met, but the reviewed baseline and interval publisher has not completed; all inference fields remain withheld.'
      end,
      'updatedAt', metrics.updated_at
    ) as item,
    1 as priority
  from authorized_set_metrics as metrics
),
selected_set_rows as (
  select distinct on (candidates.slug)
    candidates.slug,
    candidates.item
  from (
    select base.slug, base.item, base.priority from base_set_rows as base
    union all
    select authorized.slug, authorized.item, authorized.priority
    from authorized_set_rows as authorized
  ) as candidates
  order by candidates.slug, candidates.priority desc
),
public_sets_snapshot as (
  select coalesce(
    jsonb_agg(rows.item order by rows.item ->> 'releaseDate' desc nulls last, rows.item ->> 'name', rows.slug),
    '[]'::jsonb
  ) as value,
  count(*)::integer as row_count
  from selected_set_rows as rows
),
public_regions_snapshot as (
  select coalesce(
    jsonb_agg(
      jsonb_build_object(
        'slug', lower(rows.item ->> 'countryCode'),
        'name', rows.item ->> 'countryName',
        'countryCode', rows.item ->> 'countryCode',
        'coverage', format(
          '%s observed packs from %s independent source%s in the current global period.',
          rows.item ->> 'packsObserved',
          rows.item ->> 'independentSources',
          case when (rows.item ->> 'independentSources')::integer = 1 then '' else 's' end
        ),
        'packsObserved', rows.item -> 'packsObserved',
        'openings', rows.item -> 'openings',
        'independentSources', rows.item -> 'independentSources',
        'baselineRate', rows.item -> 'baselineRate',
        'hitRate', rows.item -> 'hitRate',
        'posteriorMean', rows.item -> 'posteriorMean',
        'credibleInterval', rows.item -> 'credibleInterval',
        'deltaFromBaseline', rows.item -> 'deltaFromBaseline',
        'state', rows.item ->> 'state',
        'sampleNote', rows.item ->> 'sampleNote',
        'updatedAt', rows.item ->> 'updatedAt'
      ) order by rows.item ->> 'countryName', rows.country_code
    ),
    '[]'::jsonb
  ) as value
  from selected_map_rows as rows
),
snapshot as (
  select
    jsonb_set(
      jsonb_set(
        jsonb_set(
          jsonb_set(
            jsonb_set(
              base.value,
              '{schemaVersion}',
              -- v4 is a server-side source addition; it deliberately keeps
              -- the public dashboard wire schema stable for existing clients.
              '"2.0.0"'::jsonb,
              true
            ),
            '{generatedAt}',
            to_jsonb(statement_timestamp()),
            true
          ),
          '{summary}',
          jsonb_build_object(
            'observedPacks', map.observed_packs,
            'completeOpenings', map.complete_openings,
            'aiValidatedSources', 0,
            'trackedSets', sets.row_count,
            'trackedRegions', map.country_count,
            'batchSightings', 0,
            'baselineHitRate', null,
            'globalCoverage', case
              when map.country_count = 0
                then 'No verified current-period country observations are published yet.'
              else format(
                '%s countries have verified observations in the current global period; %s publish a rate.',
                map.country_count,
                map.published_rate_count
              )
            end,
            'methodologyVersion', coalesce(map.methodology_version, 'global-observation-v1')
          ),
          true
        ),
        '{observations}',
        jsonb_build_object(
          'status', case
            when map.country_count = 0 then 'empty'
            when map.published_rate_count = 0 then 'collecting'
            else 'published'
          end,
          'period', case
            when map.country_count = 0 then null
            else jsonb_build_object(
              'start', period.period_start,
              'end', period.period_end
            )
          end,
          'observedPacks', map.observed_packs,
          'completeOpenings', map.complete_openings,
          'independentSources', null,
          'sourceCountryContributions', map.source_country_contributions,
          'countriesObserved', map.country_count,
          'countriesWithPublishedRate', map.published_rate_count,
          'asOf', map.as_of,
          'methodologyVersion', map.methodology_version,
          'minimumPacks', 30,
          'minimumSources', 3,
          'watchMinimumPacks', 200,
          'metricKey', 'qualifying_hit_pack_rate'
        ),
        true
      ),
      '{mapCells}',
      map.value,
      true
    ) as value
  from base_snapshot as base
  cross join selected_period as period
  cross join public_map_snapshot as map
  cross join public_sets_snapshot as sets
)
select
  jsonb_set(
    jsonb_set(
      jsonb_set(snapshot.value, '{sets}', sets.value, true),
      '{regions}', regions.value, true
    ),
    '{mapCells}',
    snapshot.value -> 'mapCells',
    true
  )
from snapshot
cross join public_sets_snapshot as sets
cross join public_regions_snapshot as regions;
$dashboard$;

alter function public.get_public_dashboard_snapshot_v4() owner to postgres;
revoke all on function public.get_public_dashboard_snapshot_v4()
  from public, anon, authenticated, service_role;
grant execute on function public.get_public_dashboard_snapshot_v4()
  to anon, authenticated;
comment on function public.get_public_dashboard_snapshot_v4() is
  'Counts-only public dashboard snapshot that adds non-retracted authorized observations while withholding every private identifier, numerator, reviewer field, rate, and inference value.';

-- The reviewer role can reach only its three SECURITY DEFINER entry points.
-- It deliberately has no table privileges, no submit privilege, and no login.
grant usage on schema ingest to pokecrack_authorized_opening_reviewer;

commit;
