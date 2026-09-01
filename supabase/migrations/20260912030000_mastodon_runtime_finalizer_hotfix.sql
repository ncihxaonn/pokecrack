-- Migration: 20260912030000_mastodon_runtime_finalizer_hotfix
-- mastodon.social can return an expired X-RateLimit-Reset while the remaining
-- budget is still positive.  That timestamp is informational and is never
-- used for a cooldown; only an exhausted budget requires a future reset.
-- Also keep the aggregate candidate tag union replay-safe across independently
-- scheduled tag jobs while preserving immutable per-tag observations.
begin;

do $migration$
declare
  function_oid regprocedure :=
    'ingest.finalize_mastodon_public_hashtag_job(uuid,text,bigint,jsonb)'::regprocedure;
  definition text;
  updated_definition text;
  old_rate_guard text := $old_rate$    or result_rate_limit_reset_at < completion_time - interval '5 minutes'
    or (
      result_rate_limit_remaining = 0
      and (
        result_rate_limit_reset_at is null
        or result_rate_limit_reset_at <= completion_time
      )
    )$old_rate$;
  new_rate_guard text := $new_rate$    or (
      result_rate_limit_remaining = 0
      and (
        result_rate_limit_reset_at is null
        or result_rate_limit_reset_at <= completion_time
      )
    )$new_rate$;
  old_candidate_guard text := $old_candidate$        or existing_candidate.is_demo is not false
        or (
          result_tag_key = any(existing_candidate.matched_tags)
          and existing_candidate.matched_tags <> candidate_tags
        )$old_candidate$;
  new_candidate_guard text := $new_candidate$        or existing_candidate.is_demo is not false$new_candidate$;
begin
  select pg_get_functiondef(function_oid) into strict definition;

  if (
    char_length(definition) - char_length(replace(definition, old_rate_guard, ''))
  ) / char_length(old_rate_guard) <> 1 then
    raise exception using
      errcode = '55000',
      message = 'Mastodon finalizer rate guard no longer matches the reviewed extension point';
  end if;
  if (
    char_length(definition) - char_length(replace(definition, old_candidate_guard, ''))
  ) / char_length(old_candidate_guard) <> 1 then
    raise exception using
      errcode = '55000',
      message = 'Mastodon finalizer candidate replay guard no longer matches the reviewed extension point';
  end if;

  updated_definition := replace(definition, old_rate_guard, new_rate_guard);
  updated_definition := replace(
    updated_definition,
    old_candidate_guard,
    new_candidate_guard
  );

  if updated_definition = definition
    or position(old_rate_guard in updated_definition) <> 0
    or position(old_candidate_guard in updated_definition) <> 0
    or position(new_rate_guard in updated_definition) = 0
    or position(new_candidate_guard in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'Mastodon finalizer hotfix replacement failed closed';
  end if;

  execute updated_definition;
end;
$migration$;

alter function ingest.finalize_mastodon_public_hashtag_job(uuid, text, bigint, jsonb)
  owner to postgres;
revoke all on function ingest.finalize_mastodon_public_hashtag_job(uuid, text, bigint, jsonb)
  from public, anon, authenticated, service_role;
grant execute on function ingest.finalize_mastodon_public_hashtag_job(uuid, text, bigint, jsonb)
  to service_role;
comment on function ingest.finalize_mastodon_public_hashtag_job(uuid, text, bigint, jsonb) is
  'Fenced exact Mastodon activity finalizer. Positive remaining budgets tolerate provider-stale reset hints; exhausted budgets still require a future reset. Aggregate candidate tags merge canonically while immutable per-tag observations remain replay-checked.';

commit;
