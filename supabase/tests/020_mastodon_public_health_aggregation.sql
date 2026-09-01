-- Regression coverage for the non-multiplying Mastodon public health tuple.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select has_function(
  'public',
  'get_public_social_discovery_v3',
  array[]::text[],
  'the fixed public social v3 projection exists'
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
     'public.get_public_social_discovery_v3()'::regprocedure),
  'public social v3 remains owner-controlled, stable, parallel safe, and fixed-search-path'
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
      'public.get_public_social_discovery_v3()'::regprocedure
      and acl.privilege_type = 'EXECUTE'
      and not acl.is_grantable
  $$,
  $$values ('postgres'::text), ('anon'), ('authenticated')$$,
  'only postgres and browser roles can execute public social v3'
);
select is(
  (select min_delay_seconds
   from ingest.source_policies
   where source_key = 'mastodon_social'),
  2::numeric,
  'the fixed public health contract retains the two-second Mastodon delay'
);
select is(
  (select count(*)::integer
   from ingest.mastodon_public_hashtag_checkpoints as checkpoints
   join ingest.source_policies as policies
     on policies.id = checkpoints.source_policy_id
   where policies.source_key = 'mastodon_social'
     and not checkpoints.is_demo),
  7,
  'the fixture has all seven reviewed per-tag checkpoints'
);

update ingest.mastodon_public_hashtag_checkpoints as checkpoints
set last_collected_at = statement_timestamp() - interval '1 minute',
    incomplete = false,
    updated_at = statement_timestamp()
from ingest.source_policies as policies
where policies.id = checkpoints.source_policy_id
  and policies.source_key = 'mastodon_social'
  and not checkpoints.is_demo;

set local role anon;
select set_config(
  'pokecrack.mastodon_health_payload',
  public.get_public_social_discovery_v3()::text,
  true
);
reset role;

select is(
  current_setting('pokecrack.mastodon_health_payload')::jsonb ->> 'schemaVersion',
  '3.0.0',
  'the fixed projection preserves the public schema version'
);
select is(
  (
    select array_agg(source.value ->> 'id' order by source.ordinality)
    from jsonb_array_elements(
      current_setting('pokecrack.mastodon_health_payload')::jsonb -> 'sources'
    ) with ordinality as source(value, ordinality)
  ),
  array['bluesky_jetstream', 'nostr_multi_relay', 'mastodon_public_hashtag']::text[],
  'the fixed projection preserves Bluesky, Nostr, then Mastodon source order'
);
select set_eq(
  $$
    select jsonb_object_keys(
      current_setting('pokecrack.mastodon_health_payload')::jsonb
        #> '{sources,2}'
    )
  $$,
  $$values
    ('id'::text), ('name'), ('kind'), ('access'), ('status'),
    ('lastCollectedAt'), ('url'), ('note')$$,
  'the Mastodon source retains only the safe public eight-key projection'
);
select is(
  current_setting('pokecrack.mastodon_health_payload')::jsonb
    #>> '{sources,2,status}',
  'operational',
  'seven fresh checkpoints with one valid enabled policy are operational'
);
select is(
  current_setting('pokecrack.mastodon_health_payload')::jsonb
    #>> '{sources,2,note}',
  '7 of 7 reviewed mastodon.social public hashtag activity-only feeds collected recently; 0 retained activity-only rows. Coverage may be incomplete and is never opening evidence, a denominator, or rate evidence.',
  'the operational tuple reports all seven fresh feeds without exposing private rows'
);
select ok(
  current_setting('pokecrack.mastodon_health_payload')::jsonb
    #>> '{sources,2,lastCollectedAt}' is not null,
  'the operational tuple preserves the public collection timestamp'
);
select doesnt_match(
  current_setting('pokecrack.mastodon_health_payload'),
  '(?i)(api/v[0-9]|"(instance_url|endpoint|status_id|sha256|hash|tag_key|cursor|rate_limit|error|raw|profile|handle|media|location|source_policy|gate|payload)"[[:space:]]*:)',
  'the fixed tuple still redacts endpoint, identity, cursor, policy, and raw fields'
);

update ingest.mastodon_public_hashtag_checkpoints as checkpoints
set incomplete = true,
    updated_at = statement_timestamp()
from ingest.source_policies as policies
where policies.id = checkpoints.source_policy_id
  and policies.source_key = 'mastodon_social'
  and checkpoints.tag_key = 'pokemontcg'
  and not checkpoints.is_demo;

select is(
  public.get_public_social_discovery_v3() #>> '{sources,2,status}',
  'delayed',
  'a fresh but incomplete checkpoint is not reported as operational'
);
select is(
  public.get_public_social_discovery_v3() #>> '{sources,2,note}',
  '6 of 7 reviewed mastodon.social public hashtag activity-only feeds collected recently; 0 retained activity-only rows. Coverage may be incomplete and is never opening evidence, a denominator, or rate evidence.',
  'an incomplete checkpoint is excluded from the recent feed count'
);

update ingest.mastodon_public_hashtag_checkpoints as checkpoints
set incomplete = false,
    updated_at = statement_timestamp()
from ingest.source_policies as policies
where policies.id = checkpoints.source_policy_id
  and policies.source_key = 'mastodon_social'
  and checkpoints.tag_key = 'pokemontcg'
  and not checkpoints.is_demo;

select is(
  public.get_public_social_discovery_v3() #>> '{sources,2,status}',
  'operational',
  'completing the seventh fresh checkpoint restores operational health'
);

update ingest.source_policies
set min_delay_seconds = 3,
    updated_at = statement_timestamp()
where source_key = 'mastodon_social';

set local role authenticated;
select set_config(
  'pokecrack.mastodon_drift_payload',
  public.get_public_social_discovery_v3()::text,
  true
);
reset role;

select is(
  current_setting('pokecrack.mastodon_drift_payload')::jsonb
    #>> '{sources,2,status}',
  'attention',
  'a drift from the reviewed two-second policy remains attention'
);

update ingest.source_policies
set min_delay_seconds = 2,
    updated_at = statement_timestamp()
where source_key = 'mastodon_social';

select is(
  public.get_public_social_discovery_v3() #>> '{sources,2,status}',
  'operational',
  'restoring the exact policy contract restores operational health'
);

select * from finish();
rollback;
