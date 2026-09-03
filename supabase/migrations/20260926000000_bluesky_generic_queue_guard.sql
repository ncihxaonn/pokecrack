begin;

-- Bluesky owns a separate queue capability.  Keep the shared service_role
-- lifecycle available for every other job family, but make it inert for the
-- exact Bluesky job type.  Patch the reviewed function definitions in place so
-- later changes are preserved and any unexpected function-text drift aborts
-- this forward migration rather than silently replacing the function.
do $generic_isolation$
declare
  definition text;
  updated_definition text;
  old_claim_sweep constant text := $needle$  where exhausted.job_type <> 'source.nostr.relay'
    and exhausted.attempts >= exhausted.max_attempts$needle$;
  new_claim_sweep constant text := $needle$  where exhausted.job_type <> 'source.nostr.relay'
    and exhausted.job_type <> 'source.bluesky.jetstream'
    and exhausted.attempts >= exhausted.max_attempts$needle$;
  old_claimable constant text := $needle$    where j.job_type <> 'source.nostr.relay'
      and j.attempts < j.max_attempts$needle$;
  new_claimable constant text := $needle$    where j.job_type <> 'source.nostr.relay'
      and j.job_type <> 'source.bluesky.jetstream'
      and j.attempts < j.max_attempts$needle$;
  old_leased_guard constant text := $needle$  if leased_job.is_demo
    or leased_job.job_type = 'source.nostr.relay'
    or leased_job.status <> 'running'$needle$;
  new_leased_guard constant text := $needle$  if leased_job.is_demo
    or leased_job.job_type = 'source.nostr.relay'
    or leased_job.job_type = 'source.bluesky.jetstream'
    or leased_job.status <> 'running'$needle$;
  old_pause_guard constant text := $needle$  where jobs.id = p_job_id
    and jobs.job_type <> 'source.nostr.relay'
    and jobs.status = 'running'$needle$;
  new_pause_guard constant text := $needle$  where jobs.id = p_job_id
    and jobs.job_type <> 'source.nostr.relay'
    and jobs.job_type <> 'source.bluesky.jetstream'
    and jobs.status = 'running'$needle$;
begin
  select pg_get_functiondef(
    'ingest.claim_jobs_v2(text,text[],integer,integer)'::regprocedure
  ) into definition;
  if definition is null
    or length(definition) - length(replace(definition, old_claim_sweep, ''))
      <> length(old_claim_sweep)
    or length(definition) - length(replace(definition, old_claimable, ''))
      <> length(old_claimable)
    or position(new_claim_sweep in definition) <> 0
    or position(new_claimable in definition) <> 0
  then
    raise exception using
      errcode = '55000',
      message = 'claim_jobs_v2 no longer matches the reviewed Bluesky isolation points';
  end if;
  updated_definition := replace(
    replace(definition, old_claim_sweep, new_claim_sweep),
    old_claimable,
    new_claimable
  );
  if updated_definition = definition
    or position(old_claim_sweep in updated_definition) <> 0
    or position(old_claimable in updated_definition) <> 0
    or position(new_claim_sweep in updated_definition) = 0
    or position(new_claimable in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'claim_jobs_v2 Bluesky isolation did not match exactly';
  end if;
  execute updated_definition;

  select pg_get_functiondef(
    'ingest.heartbeat_job_v2(uuid,text,bigint,integer)'::regprocedure
  ) into definition;
  if definition is null
    or length(definition) - length(replace(definition, old_leased_guard, ''))
      <> length(old_leased_guard)
    or position(new_leased_guard in definition) <> 0
  then
    raise exception using
      errcode = '55000',
      message = 'heartbeat_job_v2 no longer matches the reviewed Bluesky isolation point';
  end if;
  updated_definition := replace(definition, old_leased_guard, new_leased_guard);
  if updated_definition = definition
    or position(old_leased_guard in updated_definition) <> 0
    or position(new_leased_guard in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'heartbeat_job_v2 Bluesky isolation did not match exactly';
  end if;
  execute updated_definition;

  select pg_get_functiondef(
    'ingest.fail_job_v2(uuid,text,bigint,text,text,boolean)'::regprocedure
  ) into definition;
  if definition is null
    or length(definition) - length(replace(definition, old_leased_guard, ''))
      <> length(old_leased_guard)
    or position(new_leased_guard in definition) <> 0
  then
    raise exception using
      errcode = '55000',
      message = 'fail_job_v2 no longer matches the reviewed Bluesky isolation point';
  end if;
  updated_definition := replace(definition, old_leased_guard, new_leased_guard);
  if updated_definition = definition
    or position(old_leased_guard in updated_definition) <> 0
    or position(new_leased_guard in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'fail_job_v2 Bluesky isolation did not match exactly';
  end if;
  execute updated_definition;

  select pg_get_functiondef(
    'ingest.pause_job_for_budget_v2(uuid,text,bigint,timestamptz)'::regprocedure
  ) into definition;
  if definition is null
    or length(definition) - length(replace(definition, old_pause_guard, ''))
      <> length(old_pause_guard)
    or position(new_pause_guard in definition) <> 0
  then
    raise exception using
      errcode = '55000',
      message = 'pause_job_for_budget_v2 no longer matches the reviewed Bluesky isolation point';
  end if;
  updated_definition := replace(definition, old_pause_guard, new_pause_guard);
  if updated_definition = definition
    or position(old_pause_guard in updated_definition) <> 0
    or position(new_pause_guard in updated_definition) = 0
  then
    raise exception using
      errcode = '55000',
      message = 'pause_job_for_budget_v2 Bluesky isolation did not match exactly';
  end if;
  execute updated_definition;

end;
$generic_isolation$;

-- Dynamic replacement retains the reviewed owner and SECURITY DEFINER body,
-- while these explicit owner statements make the boundary unambiguous after
-- a function is re-issued by the patch above.
alter function ingest.claim_jobs_v2(text, text[], integer, integer)
  owner to postgres;
alter function ingest.heartbeat_job_v2(uuid, text, bigint, integer)
  owner to postgres;
alter function ingest.fail_job_v2(uuid, text, bigint, text, text, boolean)
  owner to postgres;
alter function ingest.pause_job_for_budget_v2(uuid, text, bigint, timestamptz)
  owner to postgres;

commit;
