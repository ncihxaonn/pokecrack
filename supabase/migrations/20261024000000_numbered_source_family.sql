begin;

-- Migration numbers order the ledger, not deployment dates. Production already
-- applied 20261023000000 on 2026-09-10; this successor is intended for the same
-- September release window. The reviewed access expiry remains 2026-10-10.

-- Publisher-level candidate acquisition; no per-article migration is required.
-- Disabled until worker routing, public unknown-location projection and the
-- backup/restore contract have passed the normal release gates.
create table ingest.numbered_family_control (
  singleton boolean primary key default true check(singleton),
  enabled boolean not null default false,
  policy_version text not null check(policy_version='kozaru-numbered-v1'),
  discovered_at timestamptz,
  active_until timestamptz not null default '-infinity',
  owner_job_id uuid references ingest.jobs(id) on delete set null,
  owner_generation bigint,
  last_request_at timestamptz
);
insert into ingest.numbered_family_control(singleton,policy_version)
  values(true,'kozaru-numbered-v1');

create table ingest.numbered_family_candidates (
  url text primary key check(url ~ '^https://www[.]kozaru02[.]com/entry/[a-z0-9-]{1,120}$'),
  state text not null default 'pending' check(state in
    ('pending','admitted','quarantined','duplicate','retracted')),
  discovered_at timestamptz not null default clock_timestamp(),
  checked_at timestamptz
);
create index numbered_family_candidates_due on ingest.numbered_family_candidates(checked_at nulls first,url)
  where state not in ('duplicate','retracted');

create table ingest.numbered_family_admissions (
  url text primary key references ingest.numbered_family_candidates(url),
  policy_version text not null check(policy_version='kozaru-numbered-v1'),
  published_at timestamptz not null,
  verified_at timestamptz not null,
  pack_count integer not null check(pack_count=10),
  evidence_sha256 text not null check(evidence_sha256 ~ '^[0-9a-f]{64}$'),
  resource_sha256s text[] not null check(array_ndims(resource_sha256s)=1
    and cardinality(resource_sha256s)=10
    and array_to_string(resource_sha256s,',') ~ '^[0-9a-f]{64}(,[0-9a-f]{64}){9}$')
);
-- Permanent reservations survive quarantine and retraction. Only numbered-image
-- identities participate, never common product photos or author attributes.
create table ingest.numbered_family_identity_keys (
  resource_sha256 text primary key check(resource_sha256 ~ '^[0-9a-f]{64}$'),
  url_sha256 text not null check(url_sha256 ~ '^[0-9a-f]{64}$')
);
create index numbered_family_identity_url on ingest.numbered_family_identity_keys(url_sha256);
create table ingest.numbered_family_runs (
  job_id uuid primary key references ingest.jobs(id) on delete cascade,
  generation bigint not null,
  target_url text not null,
  requests integer not null default 0 check(requests between 0 and 2),
  result jsonb check(octet_length(result::text)<=120000),
  created_at timestamptz not null default clock_timestamp()
);
create index numbered_family_runs_expiry on ingest.numbered_family_runs(created_at);

create function ingest.numbered_family_access_v1()
returns boolean language sql stable security invoker set search_path=pg_catalog as $$
  select exists(select 1 from ingest.numbered_family_control
    where enabled and policy_version='kozaru-numbered-v1'
      and statement_timestamp()<'2026-10-10T00:00:00Z'::timestamptz);
$$;
create function ingest.numbered_family_ready_v1()
returns boolean language sql stable security definer set search_path=pg_catalog as $$
  select ingest.numbered_family_access_v1();
$$;

alter table ingest.jobs drop constraint jobs_source_family_payload_check;
alter table ingest.jobs add constraint jobs_source_family_payload_check check(
  job_type<>'source.family.cycle' or (not is_demo and payload in
    ('{"family":"pokesup-enumerated"}'::jsonb,'{"family":"kozaru-numbered"}'::jsonb))
);

create function ingest.enqueue_numbered_family_v1(p_slot timestamptz)
returns setof ingest.jobs language plpgsql security definer set search_path=pg_catalog as $$
declare j uuid;
begin
  if not ingest.numbered_family_access_v1() then return; end if;
  if p_slot is null or p_slot<>date_bin(interval '5 minutes',p_slot,'2000-01-01T00:00:00Z'::timestamptz)
    or p_slot>clock_timestamp() or p_slot<clock_timestamp()-interval '2 hours' then
    raise exception 'invalid numbered family slot'; end if;
  perform pg_advisory_xact_lock(718240001);
  -- One outstanding cycle per publisher. Deferred jobs must not accumulate a
  -- new duplicate every scheduler tick or bypass a domain-wide cooldown.
  if exists(select 1 from ingest.jobs where job_type='source.family.cycle'
    and payload='{"family":"kozaru-numbered"}'::jsonb and status in ('pending','running')) then return; end if;
  if exists(select 1 from ingest.numbered_family_control where active_until>clock_timestamp()) then return; end if;
  if not exists(select 1 from ingest.numbered_family_control
      where discovered_at is null or discovered_at<clock_timestamp()-interval '1 day')
    and not exists(select 1 from ingest.numbered_family_candidates where state not in ('duplicate','retracted')
      and (checked_at is null or checked_at<clock_timestamp()-interval '1 day')) then return; end if;
  select id into j from ingest.jobs where job_type='source.family.cycle' and not is_demo
    and dedupe_key='numbered-family:'||extract(epoch from p_slot)::bigint;
  if j is null then
    insert into ingest.jobs(job_type,payload,priority,dedupe_key,max_attempts,is_demo)
      values('source.family.cycle','{"family":"kozaru-numbered"}',10,
        'numbered-family:'||extract(epoch from p_slot)::bigint,1,false) returning id into j;
  end if;
  return query select * from ingest.jobs where id=j;
end;
$$;

create function ingest.begin_numbered_family_v1(p_job uuid,p_worker text,p_generation bigint)
returns table(target_url text) language plpgsql security definer set search_path=pg_catalog as $$
declare j ingest.jobs%rowtype; c ingest.numbered_family_control%rowtype; target text;
begin
  select * into j from ingest.jobs where id=p_job for update;
  if not found or j.status<>'running' or j.is_demo or j.locked_by is distinct from p_worker
    or j.lease_generation is distinct from p_generation or j.lock_expires_at<=clock_timestamp()
    or j.job_type<>'source.family.cycle' or j.payload<>'{"family":"kozaru-numbered"}'::jsonb then return; end if;
  select * into c from ingest.numbered_family_control where singleton for update;
  if not found or not ingest.numbered_family_access_v1() or c.active_until>clock_timestamp() then return; end if;
  if exists(select 1 from ingest.numbered_family_runs where job_id=p_job and generation=p_generation) then return; end if;
  if c.discovered_at is null or c.discovered_at<clock_timestamp()-interval '1 day' then
    target:='https://www.kozaru02.com/feed';
  else
    select n.url into target from ingest.numbered_family_candidates n
      where n.state not in ('duplicate','retracted')
        and (n.checked_at is null or n.checked_at<clock_timestamp()-interval '1 day')
      order by n.checked_at nulls first,n.url limit 1 for update skip locked;
    if target is null then return; end if;
  end if;
  delete from ingest.numbered_family_runs where created_at<clock_timestamp()-interval '1 day';
  update ingest.numbered_family_control set owner_job_id=p_job,owner_generation=p_generation,
    active_until=clock_timestamp()+interval '5 minutes' where singleton;
  insert into ingest.numbered_family_runs(job_id,generation,target_url) values(p_job,p_generation,target)
    on conflict(job_id) do update set generation=excluded.generation,target_url=excluded.target_url,
      requests=0,result=null,created_at=clock_timestamp();
  return query select target;
end;
$$;

create function ingest.authorize_numbered_family_request_v1(p_job uuid,p_worker text,p_generation bigint,p_url text)
returns boolean language plpgsql security definer set search_path=pg_catalog as $$
declare j ingest.jobs%rowtype; r ingest.numbered_family_runs%rowtype; c ingest.numbered_family_control%rowtype;
begin
  select * into j from ingest.jobs where id=p_job for update;
  if not found or j.status<>'running' or j.is_demo or j.locked_by is distinct from p_worker
    or j.lease_generation is distinct from p_generation or j.lock_expires_at<=clock_timestamp()
    or j.job_type<>'source.family.cycle' or j.payload<>'{"family":"kozaru-numbered"}'::jsonb then return false; end if;
  select * into c from ingest.numbered_family_control where singleton for update;
  if not ingest.numbered_family_access_v1() or c.owner_job_id is distinct from p_job
    or c.owner_generation is distinct from p_generation or c.active_until<=clock_timestamp() then return false; end if;
  select * into r from ingest.numbered_family_runs where job_id=p_job and generation=p_generation for update;
  if not found or r.requests>=2 or r.result is not null
    or c.last_request_at>clock_timestamp()-interval '30 seconds' then return false; end if;
  if p_url is distinct from (case when r.requests=0 then 'https://www.kozaru02.com/robots.txt' else r.target_url end) then return false; end if;
  update ingest.numbered_family_runs set requests=requests+1 where job_id=p_job;
  update ingest.numbered_family_control set last_request_at=clock_timestamp() where singleton;
  return true;
end;
$$;

-- Preserve server backoff across OTHER queued jobs as well as this job's retry.
create function ingest.defer_numbered_family_v1(p_job uuid,p_worker text,p_generation bigint,p_until timestamptz)
returns boolean language plpgsql security definer set search_path=pg_catalog as $$
declare j ingest.jobs%rowtype;
begin
  select * into j from ingest.jobs where id=p_job for update;
  if not found or j.status<>'running' or j.is_demo or j.locked_by is distinct from p_worker
    or j.lease_generation is distinct from p_generation or j.lock_expires_at<=clock_timestamp()
    or j.job_type<>'source.family.cycle' or j.payload<>'{"family":"kozaru-numbered"}'::jsonb
    or p_until is null or p_until<=clock_timestamp() or not isfinite(p_until) then return false; end if;
  update ingest.numbered_family_control set active_until=greatest(active_until,p_until)
    where singleton and owner_job_id=p_job and owner_generation=p_generation;
  return found;
end;
$$;

create function ingest.stage_numbered_family_v1(p_job uuid,p_worker text,p_generation bigint,p_result jsonb)
returns void language plpgsql security definer set search_path=pg_catalog as $$
declare j ingest.jobs%rowtype; r ingest.numbered_family_runs%rowtype; e jsonb; u jsonb; published timestamptz;
begin
  select * into j from ingest.jobs where id=p_job for update;
  if not found or j.status<>'running' or j.is_demo or j.locked_by is distinct from p_worker
    or j.lease_generation is distinct from p_generation or j.lock_expires_at<=clock_timestamp()
    or j.job_type<>'source.family.cycle' or j.payload<>'{"family":"kozaru-numbered"}'::jsonb
    or not ingest.numbered_family_access_v1() then raise exception 'numbered family lease or access lost'; end if;
  perform 1 from ingest.numbered_family_control where singleton and owner_job_id=p_job
    and owner_generation=p_generation and active_until>clock_timestamp() for update;
  if not found then raise exception 'numbered family gate lost'; end if;
  select * into r from ingest.numbered_family_runs where job_id=p_job and generation=p_generation for update;
  if not found or r.result is not null then raise exception 'numbered family run missing or already staged'; end if;
  if p_result is null or jsonb_typeof(p_result)<>'object' or octet_length(p_result::text)>120000 then
    raise exception 'invalid numbered result'; end if;
  if p_result='{"quarantine":true}'::jsonb then
    if r.requests<1 then raise exception 'numbered access attempt missing'; end if;
  elsif p_result ? 'urls' and p_result-'urls'='{}'::jsonb then
    if r.target_url<>'https://www.kozaru02.com/feed' or r.requests<>2
      or jsonb_typeof(p_result->'urls') is distinct from 'array' then raise exception 'invalid numbered discovery'; end if;
    if jsonb_array_length(p_result->'urls')>200 then raise exception 'numbered discovery limit'; end if;
    for u in select jsonb_array_elements(p_result->'urls') loop
      if jsonb_typeof(u)<>'string' or u#>>'{}' !~ '^https://www[.]kozaru02[.]com/entry/[a-z0-9-]{1,120}$' then
        raise exception 'numbered discovery scope'; end if;
    end loop;
  elsif p_result ? 'evidence' and p_result-'evidence'='{}'::jsonb then
    e:=p_result->'evidence';
    if jsonb_typeof(e) is distinct from 'object' or r.requests<>2
      or r.target_url='https://www.kozaru02.com/feed'
      or not e ?& array['canonical_url','published_at','product_label','pack_count','evidence_sha256',
        'resource_sha256s','opening_country','opened_at','statistics_eligible']
      or e-array['canonical_url','published_at','product_label','pack_count','evidence_sha256',
        'resource_sha256s','opening_country','opened_at','statistics_eligible']<>'{}'::jsonb then
      raise exception 'numbered evidence shape'; end if;
    if e->'canonical_url' is distinct from to_jsonb(r.target_url)
      or e->'product_label' is distinct from '"MEGAドリームex"'::jsonb
      or e->'pack_count' is distinct from '10'::jsonb
      or e->'opening_country' is distinct from 'null'::jsonb or e->'opened_at' is distinct from 'null'::jsonb
      or e->'statistics_eligible' is distinct from 'false'::jsonb
      or jsonb_typeof(e->'evidence_sha256')<>'string' or e->>'evidence_sha256' !~ '^[0-9a-f]{64}$'
      or jsonb_typeof(e->'published_at')<>'string'
      or e->>'published_at' !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}(\.[0-9]{1,6})?\+00:00$'
      or jsonb_typeof(e->'resource_sha256s') is distinct from 'array' then raise exception 'numbered evidence leaf'; end if;
    if jsonb_array_length(e->'resource_sha256s')<>10
      or (select count(distinct x) from jsonb_array_elements_text(e->'resource_sha256s')x)<>10
      or exists(select 1 from jsonb_array_elements(e->'resource_sha256s')x
        where jsonb_typeof(x)<>'string' or x#>>'{}' !~ '^[0-9a-f]{64}$') then raise exception 'numbered resource identities'; end if;
    published:=(e->>'published_at')::timestamptz;
    if published<'2020-05-17T00:00:00Z'::timestamptz or published>clock_timestamp() then raise exception 'numbered publication range'; end if;
  else raise exception 'invalid numbered result shape'; end if;
  update ingest.numbered_family_runs set result=p_result where job_id=p_job and generation=p_generation;
end;
$$;

create function ingest.finalize_numbered_family_v1(p_job uuid,p_worker text,p_generation bigint)
returns setof ingest.jobs language plpgsql security definer set search_path=pg_catalog as $$
declare j ingest.jobs%rowtype; r ingest.numbered_family_runs%rowtype; e jsonb; u text; h text;
  url_hash text; resources text[]; prior ingest.numbered_family_admissions%rowtype; outcome text;
begin
  select * into j from ingest.jobs where id=p_job for update;
  if not found or j.status<>'running' or j.is_demo or j.locked_by is distinct from p_worker
    or j.lease_generation is distinct from p_generation or j.lock_expires_at<=clock_timestamp()
    or j.job_type<>'source.family.cycle' or j.payload<>'{"family":"kozaru-numbered"}'::jsonb then return; end if;
  perform 1 from ingest.numbered_family_control where singleton and owner_job_id=p_job
    and owner_generation=p_generation and active_until>clock_timestamp() for update;
  if not found or not ingest.numbered_family_access_v1() then return; end if;
  select * into r from ingest.numbered_family_runs where job_id=p_job and generation=p_generation for update;
  if not found or r.result is null then raise exception 'numbered result missing'; end if;
  if r.target_url='https://www.kozaru02.com/feed' then
    if r.result ? 'urls' then
      for u in select distinct jsonb_array_elements_text(r.result->'urls') loop
        if (select count(*) from ingest.numbered_family_candidates)>=10000 then exit; end if;
        insert into ingest.numbered_family_candidates(url) values(u) on conflict do nothing;
      end loop;
    end if;
    -- Both successful and quarantined feed checks consume the daily discovery
    -- slot. A permanent denial or malformed feed must not retry every cycle.
    update ingest.numbered_family_control set discovered_at=clock_timestamp() where singleton;
  else
    u:=r.target_url; e:=r.result->'evidence'; outcome:='quarantined';
    perform 1 from ingest.numbered_family_candidates where url=u and state not in ('duplicate','retracted') for update;
    if found and e is not null then
      url_hash:=encode(extensions.digest(u,'sha256'),'hex');
      select array_agg(x order by ord) into resources
        from jsonb_array_elements_text(e->'resource_sha256s') with ordinality a(x,ord);
      select * into prior from ingest.numbered_family_admissions where url=u;
      if found and (prior.published_at<>(e->>'published_at')::timestamptz
        or prior.evidence_sha256<>e->>'evidence_sha256' or prior.resource_sha256s<>resources) then
        outcome:='quarantined';
      elsif exists(select 1 from ingest.numbered_family_identity_keys
        where resource_sha256=any(resources) and url_sha256<>url_hash) then outcome:='duplicate';
      else
        outcome:='admitted';
        insert into ingest.numbered_family_admissions values(u,'kozaru-numbered-v1',
          (e->>'published_at')::timestamptz,clock_timestamp(),10,e->>'evidence_sha256',resources)
          on conflict(url) do update set verified_at=excluded.verified_at;
      end if;
      if outcome in ('admitted','duplicate') then
        -- Preserve novel identities in a valid partial repost too. Otherwise
        -- a later repost can evade dedup by retaining only that novel subset.
        -- Existing ownership is immutable; no duplicate adds a public cohort.
        foreach h in array resources loop
          insert into ingest.numbered_family_identity_keys values(h,url_hash) on conflict do nothing;
        end loop;
      end if;
    end if;
    update ingest.numbered_family_candidates set state=outcome,checked_at=clock_timestamp()
      where url=u and state not in ('duplicate','retracted');
  end if;
  delete from ingest.numbered_family_runs where job_id=p_job;
  return query update ingest.jobs set status='completed',locked_by=null,locked_at=null,
    lock_expires_at=null,completed_at=clock_timestamp(),updated_at=clock_timestamp()
    where id=p_job returning *;
end;
$$;

create function ingest.retract_numbered_family_v1(p_url text)
returns void language plpgsql security invoker set search_path=pg_catalog as $$
begin
  perform 1 from ingest.numbered_family_control where singleton for update;
  insert into ingest.numbered_family_candidates(url,state) values(p_url,'retracted')
    on conflict(url) do update set state='retracted';
end;
$$;

-- Expire abandoned minimal staging even when publisher collection is disabled.
do $cleanup$
declare d text; anchor text:='  completion_time := clock_timestamp();';
begin
  select pg_get_functiondef('ingest.finalize_cleanup_job(uuid,text,bigint)'::regprocedure) into d;
  if position(anchor in d)=0 then raise exception 'numbered cleanup boundary drift'; end if;
  execute replace(d,anchor,$prune$
  with expired as (
    select runs.job_id from ingest.numbered_family_runs runs where runs.created_at<lease_checked_at-interval '1 day'
      order by runs.created_at limit 1000 for update skip locked
  ) delete from ingest.numbered_family_runs r using expired e where r.job_id=e.job_id;
$prune$||anchor);
end;
$cleanup$;

do $permissions$
declare t text; f regprocedure;
begin
  foreach t in array array['numbered_family_control','numbered_family_candidates',
    'numbered_family_admissions','numbered_family_identity_keys','numbered_family_runs'] loop
    execute format('alter table ingest.%I enable row level security',t);
    execute format('alter table ingest.%I force row level security',t);
    execute format('revoke all on ingest.%I from public,anon,authenticated,service_role',t);
  end loop;
  for f in select p.oid::regprocedure from pg_proc p join pg_namespace n on n.oid=p.pronamespace
    where n.nspname='ingest' and p.proname like '%numbered_family%' loop
    execute format('alter function %s owner to postgres',f);
    execute format('revoke all on function %s from public,anon,authenticated,service_role',f);
  end loop;
end;
$permissions$;
grant execute on function ingest.numbered_family_ready_v1(),ingest.enqueue_numbered_family_v1(timestamptz),
  ingest.begin_numbered_family_v1(uuid,text,bigint),ingest.authorize_numbered_family_request_v1(uuid,text,bigint,text),
  ingest.defer_numbered_family_v1(uuid,text,bigint,timestamptz),ingest.stage_numbered_family_v1(uuid,text,bigint,jsonb),
  ingest.finalize_numbered_family_v1(uuid,text,bigint) to service_role;

commit;
