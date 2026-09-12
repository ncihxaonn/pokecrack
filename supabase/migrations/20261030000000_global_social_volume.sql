begin;

-- Social metadata claims are publishable in the quantity-only lane, but they
-- must never enter the HTML page-check queue. The collector already retains
-- only a bounded title/text window and the Python projection stores no source
-- text, identity or media.
create or replace function ingest.claim_global_volume_candidates_v1(
  p_worker_id text,
  p_limit integer default 8
)
returns table(
  url text,
  report_group_sha256 text,
  pack_count integer,
  pack_precision text,
  country_code text,
  geography_basis text,
  set_external_id text,
  product_scope text,
  source_language text,
  state text,
  attempts integer
)
language sql
security definer
set search_path = pg_catalog
as $$
  with due as (
    select candidates.url
    from ingest.global_volume_candidates as candidates
    where p_worker_id ~ '^[a-zA-Z0-9][a-zA-Z0-9_.:-]{0,159}$'
      and p_limit between 1 and 25
      and candidates.pack_precision <> 'title_claim'
      and candidates.attempts < 3
      and (
        candidates.state = 'reported'
        or (
          candidates.state = 'checking'
          and candidates.locked_until < clock_timestamp()
        )
      )
    order by candidates.last_checked_at nulls first,
      candidates.last_seen_at, candidates.first_seen_at, candidates.url
    limit greatest(least(p_limit, 25), 0)
    for update skip locked
  ), claimed as (
    update ingest.global_volume_candidates as candidates
    set state = 'checking', attempts = candidates.attempts + 1,
        locked_by = p_worker_id, locked_until = clock_timestamp() + interval '5 minutes'
    from due
    where candidates.url = due.url
    returning candidates.*
  )
  select claimed.url, claimed.report_group_sha256, claimed.pack_count,
    claimed.pack_precision, claimed.country_code, claimed.geography_basis,
    claimed.set_external_id, claimed.product_scope, claimed.source_language,
    claimed.state, claimed.attempts
  from claimed;
$$;

alter function ingest.claim_global_volume_candidates_v1(text, integer)
  owner to postgres;
revoke all on function ingest.claim_global_volume_candidates_v1(text, integer)
  from public, anon, authenticated, service_role;
grant execute on function ingest.claim_global_volume_candidates_v1(text, integer)
  to service_role;
comment on function ingest.claim_global_volume_candidates_v1(text, integer) is
  'Claims only page-checkable public volume rows; title claims remain quantity-only metadata projections.';

commit;
