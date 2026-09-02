-- Regression coverage for the strict public global social activity pulse.
-- The fixture exercises only aggregate counts; the assertion surface rejects
-- any accidental return of provider identity or evidence-shaped fields.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select has_function(
  'public',
  'get_public_social_discovery_v4',
  array[]::text[],
  'the strict public social v4 pulse projection exists'
);
select ok(
  (select procedures.proowner::regrole::text = 'postgres'
      and procedures.prosecdef
      and procedures.provolatile = 's'
      and procedures.proparallel = 's'
      and coalesce(procedures.proconfig, '{}'::text[])
        @> array['search_path=pg_catalog']
   from pg_proc as procedures
   where procedures.oid =
     'public.get_public_social_discovery_v4()'::regprocedure),
  'public social v4 remains owner-controlled, stable, parallel safe, and fixed-search-path'
);
select set_eq(
  $$
    select grantee::regrole::text
    from pg_proc as procedures
    cross join lateral aclexplode(
      coalesce(procedures.proacl, acldefault('f', procedures.proowner))
    ) as acl
    join pg_roles as grantees on grantees.oid = acl.grantee
    where procedures.oid =
      'public.get_public_social_discovery_v4()'::regprocedure
      and acl.privilege_type = 'EXECUTE'
      and not acl.is_grantable
  $$,
  $$values ('postgres'::text), ('anon'), ('authenticated')$$,
  'only postgres and browser roles can execute public social v4'
);

select is(
  (
    select policies.config ->> 'stream_window_seconds'
    from ingest.source_policies as policies
    where policies.source_key = 'bluesky_jetstream'
      and not policies.is_demo
    limit 1
  ),
  '10',
  'the v4 fixture uses the current ten-second Bluesky runtime bounds'
);

update ingest.bluesky_jetstream_checkpoints as checkpoints
set last_collected_at = statement_timestamp() - interval '1 minute',
    updated_at = statement_timestamp()
from ingest.source_policies as policies
where policies.id = checkpoints.source_policy_id
  and policies.source_key = 'bluesky_jetstream'
  and not checkpoints.is_demo;
update ingest.nostr_relay_checkpoints as checkpoints
set last_checkpoint = statement_timestamp() - interval '1 minute',
    updated_at = statement_timestamp()
where not checkpoints.is_demo;
update ingest.mastodon_public_hashtag_checkpoints as checkpoints
set last_collected_at = statement_timestamp() - interval '1 minute',
    incomplete = false,
    updated_at = statement_timestamp()
from ingest.source_policies as policies
where policies.id = checkpoints.source_policy_id
  and policies.source_key = 'mastodon_social'
  and not checkpoints.is_demo;

insert into ingest.bluesky_jetstream_candidates (
  at_uri,
  public_url,
  text_excerpt,
  record_sha256,
  published_at,
  source_policy_id,
  source_policy_version,
  collector_version,
  first_seen_at,
  last_seen_at,
  last_cursor,
  expires_at,
  is_demo,
  created_at,
  updated_at
)
select
  'at://did:plc:pulsev4/app.bsky.feed.post/pulsev4',
  'https://bsky.app/profile/did:plc:pulsev4/post/pulsev4',
  null,
  repeat('a', 64),
  statement_timestamp() - interval '2 hours',
  policies.id,
  'bluesky-jetstream-v1',
  'test-pulse-v4',
  statement_timestamp() - interval '2 hours',
  statement_timestamp() - interval '2 hours',
  1,
  statement_timestamp() - interval '2 hours' + interval '30 days',
  false,
  statement_timestamp(),
  statement_timestamp()
from ingest.source_policies as policies
where policies.source_key = 'bluesky_jetstream';

insert into ingest.nostr_relay_candidates (
  event_id,
  source_policy_id,
  relay_key,
  author_sha256,
  content_sha256,
  matched_tags,
  published_at,
  first_seen_at,
  last_seen_at,
  expires_at,
  activity_only,
  statistics_eligible,
  is_demo,
  created_at,
  updated_at
)
select
  repeat('b', 64),
  policies.id,
  'primal',
  repeat('c', 64),
  repeat('d', 64),
  array['pokemontcg']::text[],
  statement_timestamp() - interval '2 hours',
  statement_timestamp() - interval '2 hours',
  statement_timestamp() - interval '2 hours',
  statement_timestamp() - interval '2 hours' + interval '30 days',
  true,
  false,
  false,
  statement_timestamp(),
  statement_timestamp()
from ingest.source_policies as policies
where policies.source_key = 'nostr_relay_primal';

insert into ingest.mastodon_public_hashtag_candidates (
  source_policy_id,
  status_key_sha256,
  matched_tags,
  published_at,
  first_seen_at,
  last_seen_at,
  expires_at,
  activity_only,
  statistics_eligible,
  is_demo,
  created_at,
  updated_at
)
select
  policies.id,
  repeat('e', 64),
  array['pokemontcg']::text[],
  statement_timestamp() - interval '2 hours',
  statement_timestamp() - interval '2 hours',
  statement_timestamp() - interval '2 hours',
  statement_timestamp() - interval '2 hours' + interval '30 days',
  true,
  false,
  false,
  statement_timestamp(),
  statement_timestamp()
from ingest.source_policies as policies
where policies.source_key = 'mastodon_social';

set local role anon;
select set_config(
  'pokecrack.social_activity_pulse_v4_payload',
  public.get_public_social_discovery_v4()::text,
  true
);
reset role;

select is(
  current_setting('pokecrack.social_activity_pulse_v4_payload')::jsonb ->> 'schemaVersion',
  '4.0.0',
  'the pulse uses the exact v4 schema version'
);
select is(
  jsonb_array_length(
    current_setting('pokecrack.social_activity_pulse_v4_payload')::jsonb -> 'sources'
  ),
  3,
  'the pulse exposes exactly three fixed social platforms'
);
select ok(
  (extract(epoch from (
    (current_setting('pokecrack.social_activity_pulse_v4_payload')::jsonb #>> '{window,end}')::timestamptz
    - (current_setting('pokecrack.social_activity_pulse_v4_payload')::jsonb #>> '{window,start}')::timestamptz
  )) = 86400),
  'the pulse window covers exactly 24 hours'
);
select ok(
  (current_setting('pokecrack.social_activity_pulse_v4_payload')::jsonb ->> 'activityOnly')::boolean
    and (current_setting('pokecrack.social_activity_pulse_v4_payload')::jsonb ->> 'nonEvidence')::boolean,
  'the top-level pulse is explicitly activity-only and non-evidence'
);
select set_eq(
  $$
    select jsonb_object_keys(
      current_setting('pokecrack.social_activity_pulse_v4_payload')::jsonb
    )
  $$,
  $$values
    ('schemaVersion'::text), ('window'), ('activityOnly'), ('nonEvidence'), ('sources')$$,
  'the top-level pulse exposes only version, window, scope, and sources'
);
select is(
  (
    select array_agg(source.value ->> 'id' order by source.ordinality)
    from jsonb_array_elements(
      current_setting('pokecrack.social_activity_pulse_v4_payload')::jsonb -> 'sources'
    ) with ordinality as source(value, ordinality)
  ),
  array['bluesky_jetstream', 'nostr_multi_relay', 'mastodon_public_hashtag']::text[],
  'the pulse preserves Bluesky, Nostr, then Mastodon order'
);

select set_eq(
  $$
    select jsonb_object_keys(
      current_setting('pokecrack.social_activity_pulse_v4_payload')::jsonb
        #> '{sources,0}'
    )
  $$,
  $$values
    ('id'::text), ('name'), ('kind'), ('access'), ('status'), ('freshness'),
    ('lastCollectedAt'), ('newCandidates24h'), ('retainedCandidates'),
    ('activityOnly'), ('statisticsEligible')$$,
  'each source exposes only the strict aggregate activity fields'
);
select ok(
  (select bool_and(
      source.value ->> 'kind' = 'social'
      and source.value ->> 'access' = 'public'
      and (source.value ->> 'activityOnly')::boolean
      and not (source.value ->> 'statisticsEligible')::boolean
      and (source.value ->> 'newCandidates24h')::integer >= 0
      and (source.value ->> 'retainedCandidates')::integer >= 0
   )
   from jsonb_array_elements(
     current_setting('pokecrack.social_activity_pulse_v4_payload')::jsonb -> 'sources'
   ) as source(value)),
  'all source rows are public activity-only bounded counts'
);
select is(
  current_setting('pokecrack.social_activity_pulse_v4_payload')::jsonb
    #>> '{sources,0,newCandidates24h}',
  '1',
  'the Bluesky 24-hour discovery count is exposed as an aggregate only'
);
select is(
  current_setting('pokecrack.social_activity_pulse_v4_payload')::jsonb
    #>> '{sources,0,retainedCandidates}',
  '1',
  'the Bluesky retained count is exposed as an aggregate only'
);
select is(
  current_setting('pokecrack.social_activity_pulse_v4_payload')::jsonb
    #>> '{sources,1,newCandidates24h}',
  '1',
  'the Nostr 24-hour discovery count is exposed as an aggregate only'
);
select is(
  current_setting('pokecrack.social_activity_pulse_v4_payload')::jsonb
    #>> '{sources,2,newCandidates24h}',
  '1',
  'the Mastodon 24-hour discovery count is exposed as an aggregate only'
);
select is(
  current_setting('pokecrack.social_activity_pulse_v4_payload')::jsonb
    #>> '{sources,0,status}',
  'operational',
  'the fresh Bluesky checkpoint reports operational health'
);
select is(
  current_setting('pokecrack.social_activity_pulse_v4_payload')::jsonb
    #>> '{sources,1,status}',
  'operational',
  'all fresh Nostr checkpoints report operational health'
);
select is(
  current_setting('pokecrack.social_activity_pulse_v4_payload')::jsonb
    #>> '{sources,2,status}',
  'operational',
  'all fresh Mastodon checkpoints report operational health'
);

-- A missing policy must still produce the fixed source tuple and must not
-- preserve a count from the private candidate ledger.
update ingest.source_policies
set source_key = 'bluesky_jetstream_missing_fixture',
    base_url = 'https://example.invalid/bluesky-jetstream-missing-fixture'
where source_key = 'bluesky_jetstream';
set local role anon;
select set_config(
  'pokecrack.social_activity_pulse_v4_missing_policy',
  public.get_public_social_discovery_v4()::text,
  true
);
reset role;
update ingest.source_policies
set source_key = 'bluesky_jetstream',
    base_url = 'wss://jetstream.us-west.bsky.network/xrpc/network.bsky.jetstream.subscribeEvents'
where source_key = 'bluesky_jetstream_missing_fixture';

select is(
  jsonb_array_length(
    current_setting('pokecrack.social_activity_pulse_v4_missing_policy')::jsonb -> 'sources'
  ),
  3,
  'a missing Bluesky policy still emits all three fixed source rows'
);
select is(
  current_setting('pokecrack.social_activity_pulse_v4_missing_policy')::jsonb
    #>> '{sources,0,status}',
  'attention',
  'a missing Bluesky policy reports attention'
);
select is(
  current_setting('pokecrack.social_activity_pulse_v4_missing_policy')::jsonb
    #>> '{sources,0,newCandidates24h}',
  '0',
  'a missing Bluesky policy suppresses its 24-hour count'
);
select is(
  current_setting('pokecrack.social_activity_pulse_v4_missing_policy')::jsonb
    #>> '{sources,0,retainedCandidates}',
  '0',
  'a missing Bluesky policy suppresses its retained count'
);

-- A registered but contract-invalid policy must not expose stale activity.
update ingest.source_policies
set display_name = 'Nostr relay relay.primal.net discovery (invalid fixture)'
where source_key = 'nostr_relay_primal';
set local role anon;
select set_config(
  'pokecrack.social_activity_pulse_v4_invalid_policy',
  public.get_public_social_discovery_v4()::text,
  true
);
reset role;
update ingest.source_policies
set display_name = 'Nostr relay relay.primal.net discovery'
where source_key = 'nostr_relay_primal';

select is(
  current_setting('pokecrack.social_activity_pulse_v4_invalid_policy')::jsonb
    #>> '{sources,1,status}',
  'attention',
  'an invalid Nostr contract reports attention'
);
select is(
  current_setting('pokecrack.social_activity_pulse_v4_invalid_policy')::jsonb
    #>> '{sources,1,newCandidates24h}',
  '0',
  'an invalid Nostr contract suppresses its 24-hour count'
);
select is(
  current_setting('pokecrack.social_activity_pulse_v4_invalid_policy')::jsonb
    #>> '{sources,1,retainedCandidates}',
  '0',
  'an invalid Nostr contract suppresses its retained count'
);

-- A disabled policy is paused and its old candidate rows are not reported.
update ingest.source_policies
set enabled = false
where source_key = 'mastodon_social';
set local role anon;
select set_config(
  'pokecrack.social_activity_pulse_v4_disabled_policy',
  public.get_public_social_discovery_v4()::text,
  true
);
reset role;
update ingest.source_policies
set enabled = true
where source_key = 'mastodon_social';

select is(
  current_setting('pokecrack.social_activity_pulse_v4_disabled_policy')::jsonb
    #>> '{sources,2,status}',
  'paused',
  'a disabled Mastodon policy reports paused'
);
select is(
  current_setting('pokecrack.social_activity_pulse_v4_disabled_policy')::jsonb
    #>> '{sources,2,newCandidates24h}',
  '0',
  'a disabled Mastodon policy suppresses its 24-hour count'
);
select is(
  current_setting('pokecrack.social_activity_pulse_v4_disabled_policy')::jsonb
    #>> '{sources,2,retainedCandidates}',
  '0',
  'a disabled Mastodon policy suppresses its retained count'
);

select doesnt_match(
  current_setting('pokecrack.social_activity_pulse_v4_payload'),
  '(?i)"(text|url|uri|event_id|status_id|sha256|hash|author|tag|cursor|raw_payload|profile|handle|media|country|pack|rate|endpoint|policy|gate|payload)"[[:space:]]*:',
  'the v4 payload never exposes text, endpoints, identities, hashes, tags, cursors, policy, rate, or raw fields'
);

select * from finish();
rollback;
