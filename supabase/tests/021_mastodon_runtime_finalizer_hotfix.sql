-- Regression coverage for provider-stale positive-budget reset hints and
-- aggregate candidate tag-union replay.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog;
select no_plan();

select ok(
  (select procedures.proowner::regrole::text = 'postgres'
      and procedures.prosecdef
      and procedures.provolatile = 'v'
      and procedures.proparallel = 'u'
      and coalesce(procedures.proconfig, '{}'::text[])
        @> array['search_path=pg_catalog']
   from pg_proc as procedures
   where procedures.oid =
     'ingest.finalize_mastodon_public_hashtag_job(uuid,text,bigint,jsonb)'::regprocedure),
  'the hotfixed Mastodon finalizer remains owner-controlled and fixed-search-path'
);
select set_eq(
  $$
    select grantees.rolname
    from pg_proc as procedures
    cross join lateral aclexplode(
      coalesce(procedures.proacl, acldefault('f', procedures.proowner))
    ) as acl
    join pg_roles as grantees on grantees.oid = acl.grantee
    where procedures.oid =
      'ingest.finalize_mastodon_public_hashtag_job(uuid,text,bigint,jsonb)'::regprocedure
      and acl.privilege_type = 'EXECUTE'
      and not acl.is_grantable
  $$,
  $$values ('postgres'::text), ('service_role')$$,
  'only postgres and service_role execute the hotfixed finalizer'
);
select ok(
  position(
    $needle$result_rate_limit_reset_at < completion_time - interval '5 minutes'$needle$
    in pg_get_functiondef(
      'ingest.finalize_mastodon_public_hashtag_job(uuid,text,bigint,jsonb)'::regprocedure
    )
  ) = 0,
  'positive remaining budgets no longer reject a provider-stale reset hint'
);
select ok(
  position(
    $needle$existing_candidate.matched_tags <> candidate_tags$needle$
    in pg_get_functiondef(
      'ingest.finalize_mastodon_public_hashtag_job(uuid,text,bigint,jsonb)'::regprocedure
    )
  ) = 0
  and position(
    $needle$existing_observation.matched_tags <> candidate_tags$needle$
    in pg_get_functiondef(
      'ingest.finalize_mastodon_public_hashtag_job(uuid,text,bigint,jsonb)'::regprocedure
    )
  ) > 0,
  'aggregate tag unions are replay-safe while per-tag observations stay immutable'
);

create function pg_temp.mastodon_hotfix_hash(status_id text)
returns text
language sql
immutable
as $$
  select encode(extensions.digest(
    convert_to('mastodon_social' || E'\n' || status_id, 'UTF8'), 'sha256'
  ), 'hex');
$$;

update ingest.source_request_gates
set active_until = null,
    owner_job_id = null,
    owner_lease_generation = null,
    acquired_at = null
where source_key = 'mastodon_social';
update ingest.mastodon_rate_cooldowns
set cooldown_until = clock_timestamp() - interval '1 second',
    updated_at = clock_timestamp()
where instance_key = 'mastodon_social';
update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '10 seconds',
    updated_at = clock_timestamp()
where source_key = 'mastodon_social';

insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'a7030000-0000-4000-8000-000000000001',
  'source.mastodon.public_hashtag',
  '{"instance_key":"mastodon_social","tag_key":"pokemontcg"}'::jsonb,
  'running', 1, clock_timestamp(), clock_timestamp() + interval '10 minutes',
  'mastodon-hotfix-worker-a1', 1, false
);
select ok(
  (select acquired and start_status_id is null
   from ingest.begin_mastodon_public_hashtag_job(
     'a7030000-0000-4000-8000-000000000001',
     'mastodon-hotfix-worker-a1', 1, 'mastodon_social', 'pokemontcg'
   )),
  'the positive-budget stale-reset fixture acquires its first tag checkpoint'
);
select lives_ok(
  $sql$select * from ingest.finalize_mastodon_public_hashtag_job(
    'a7030000-0000-4000-8000-000000000001',
    'mastodon-hotfix-worker-a1', 1,
    jsonb_build_object(
      'version', '1.0.0', 'instance_key', 'mastodon_social',
      'tag_key', 'pokemontcg', 'start_status_id', null,
      'end_status_id', 'hotfix-a', 'incomplete', false,
      'requests_made', 1, 'statuses_seen', 1, 'bytes_seen', 128,
      'candidates', jsonb_build_array(jsonb_build_object(
        'status_id', 'hotfix-shared',
        'status_key_sha256', pg_temp.mastodon_hotfix_hash('hotfix-shared'),
        'published_at', '2026-01-01T00:00:00Z',
        'matched_tags', jsonb_build_array('pokemontcg'),
        'activity_only', true, 'statistics_eligible', false
      )),
      'rate_limit_limit', 300, 'rate_limit_remaining', 299,
      'rate_limit_reset_at', to_char(
        clock_timestamp() at time zone 'UTC' - interval '2 hours',
        'YYYY-MM-DD"T"HH24:MI:SS"Z"'
      )
    )
  )$sql$,
  'a stale reset hint is accepted while the provider reports positive remaining budget'
);
select ok(
  (select status = 'completed'
   from ingest.jobs where id = 'a7030000-0000-4000-8000-000000000001')
  and (select last_status_id = 'hotfix-a'
       from ingest.mastodon_public_hashtag_checkpoints
       where tag_key = 'pokemontcg'),
  'positive-budget finalization advances the opaque checkpoint atomically'
);

update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '10 seconds',
    updated_at = clock_timestamp()
where source_key = 'mastodon_social';
insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'a7030000-0000-4000-8000-000000000002',
  'source.mastodon.public_hashtag',
  '{"instance_key":"mastodon_social","tag_key":"pokemoncards"}'::jsonb,
  'running', 1, clock_timestamp(), clock_timestamp() + interval '10 minutes',
  'mastodon-hotfix-worker-b', 1, false
);
select ok(
  (select acquired and start_status_id is null
   from ingest.begin_mastodon_public_hashtag_job(
     'a7030000-0000-4000-8000-000000000002',
     'mastodon-hotfix-worker-b', 1, 'mastodon_social', 'pokemoncards'
   )),
  'the second tag acquires its independent nullable checkpoint'
);
select lives_ok(
  $sql$select * from ingest.finalize_mastodon_public_hashtag_job(
    'a7030000-0000-4000-8000-000000000002',
    'mastodon-hotfix-worker-b', 1,
    jsonb_build_object(
      'version', '1.0.0', 'instance_key', 'mastodon_social',
      'tag_key', 'pokemoncards', 'start_status_id', null,
      'end_status_id', 'hotfix-b', 'incomplete', false,
      'requests_made', 1, 'statuses_seen', 1, 'bytes_seen', 128,
      'candidates', jsonb_build_array(jsonb_build_object(
        'status_id', 'hotfix-shared',
        'status_key_sha256', pg_temp.mastodon_hotfix_hash('hotfix-shared'),
        'published_at', '2026-01-01T00:00:00Z',
        'matched_tags', jsonb_build_array('pokemoncards'),
        'activity_only', true, 'statistics_eligible', false
      )),
      'rate_limit_limit', null, 'rate_limit_remaining', null,
      'rate_limit_reset_at', null
    )
  )$sql$,
  'a second tag merges the same activity identity into the aggregate candidate'
);
select is(
  (select matched_tags
   from ingest.mastodon_public_hashtag_candidates
   where status_key_sha256 = pg_temp.mastodon_hotfix_hash('hotfix-shared')),
  array['pokemontcg', 'pokemoncards']::text[],
  'the shared candidate retains the canonical union of independently observed tags'
);

update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '10 seconds',
    updated_at = clock_timestamp()
where source_key = 'mastodon_social';
insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'a7030000-0000-4000-8000-000000000003',
  'source.mastodon.public_hashtag',
  '{"instance_key":"mastodon_social","tag_key":"pokemontcg"}'::jsonb,
  'running', 1, clock_timestamp(), clock_timestamp() + interval '10 minutes',
  'mastodon-hotfix-worker-a2', 1, false
);
select ok(
  (select acquired and start_status_id = 'hotfix-a'
   from ingest.begin_mastodon_public_hashtag_job(
     'a7030000-0000-4000-8000-000000000003',
     'mastodon-hotfix-worker-a2', 1, 'mastodon_social', 'pokemontcg'
   )),
  'the first tag replay starts from its exact opaque checkpoint'
);
select lives_ok(
  $sql$select * from ingest.finalize_mastodon_public_hashtag_job(
    'a7030000-0000-4000-8000-000000000003',
    'mastodon-hotfix-worker-a2', 1,
    jsonb_build_object(
      'version', '1.0.0', 'instance_key', 'mastodon_social',
      'tag_key', 'pokemontcg', 'start_status_id', 'hotfix-a',
      'end_status_id', 'hotfix-a-next', 'incomplete', false,
      'requests_made', 1, 'statuses_seen', 1, 'bytes_seen', 128,
      'candidates', jsonb_build_array(jsonb_build_object(
        'status_id', 'hotfix-shared',
        'status_key_sha256', pg_temp.mastodon_hotfix_hash('hotfix-shared'),
        'published_at', '2026-01-01T00:00:00Z',
        'matched_tags', jsonb_build_array('pokemontcg'),
        'activity_only', true, 'statistics_eligible', false
      )),
      'rate_limit_limit', null, 'rate_limit_remaining', null,
      'rate_limit_reset_at', null
    )
  )$sql$,
  'a per-tag replay remains valid after the aggregate candidate gained another tag'
);
select ok(
  (select matched_tags = array['pokemontcg', 'pokemoncards']::text[]
   from ingest.mastodon_public_hashtag_candidates
   where status_key_sha256 = pg_temp.mastodon_hotfix_hash('hotfix-shared'))
  and (select count(*) = 2
       from ingest.mastodon_public_hashtag_observations
       where status_key_sha256 = pg_temp.mastodon_hotfix_hash('hotfix-shared')),
  'aggregate replay preserves the union and does not duplicate immutable observations'
);

update ingest.source_policies
set last_attempt_at = clock_timestamp() - interval '10 seconds',
    updated_at = clock_timestamp()
where source_key = 'mastodon_social';
insert into ingest.jobs (
  id, job_type, payload, status, attempts, locked_at, lock_expires_at,
  locked_by, lease_generation, is_demo
) values (
  'a7030000-0000-4000-8000-000000000004',
  'source.mastodon.public_hashtag',
  '{"instance_key":"mastodon_social","tag_key":"pokemon_card_zh_hans"}'::jsonb,
  'running', 1, clock_timestamp(), clock_timestamp() + interval '10 minutes',
  'mastodon-hotfix-worker-exhausted', 1, false
);
select ok(
  (select acquired
   from ingest.begin_mastodon_public_hashtag_job(
     'a7030000-0000-4000-8000-000000000004',
     'mastodon-hotfix-worker-exhausted', 1,
     'mastodon_social', 'pokemon_card_zh_hans'
   )),
  'the exhausted-budget negative fixture acquires its independent checkpoint'
);
select throws_ok(
  $sql$select * from ingest.finalize_mastodon_public_hashtag_job(
    'a7030000-0000-4000-8000-000000000004',
    'mastodon-hotfix-worker-exhausted', 1,
    jsonb_build_object(
      'version', '1.0.0', 'instance_key', 'mastodon_social',
      'tag_key', 'pokemon_card_zh_hans', 'start_status_id', null,
      'end_status_id', null, 'incomplete', true,
      'requests_made', 1, 'statuses_seen', 0, 'bytes_seen', 64,
      'candidates', '[]'::jsonb,
      'rate_limit_limit', 300, 'rate_limit_remaining', 0,
      'rate_limit_reset_at', to_char(
        clock_timestamp() at time zone 'UTC' - interval '2 hours',
        'YYYY-MM-DD"T"HH24:MI:SS"Z"'
      )
    )
  )$sql$,
  '22023',
  'Mastodon result exceeds the fixed page, status, byte, or rate bounds',
  'an exhausted budget still rejects a stale reset timestamp'
);
select ok(
  (select status = 'running'
   from ingest.jobs where id = 'a7030000-0000-4000-8000-000000000004')
  and (select last_status_id is null
       from ingest.mastodon_public_hashtag_checkpoints
       where tag_key = 'pokemon_card_zh_hans'),
  'exhausted-budget rejection leaves the fenced lease and checkpoint unchanged'
);

select * from finish();
rollback;
