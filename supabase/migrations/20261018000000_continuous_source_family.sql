begin;

-- Scaffold generated with CLI 2.115.0 migration new on the isolated MAM host;
-- moved forward from 20260909083554 to follow the applied 20261017000000.
-- These identifiers order the ledger; they do not schedule execution dates.
-- Production already had 20261017000000 applied on 2026-09-09. This release
-- is intended for September, within the independently reviewed 30-day window.
-- Source review: docs/CONTINUOUS_SOURCE_FAMILY.md. Runtime remains off until
-- the owner enables the separate mutable control after normal release gates.
-- Only reviewed code may change cohort rules, scope or product identities.
create function ingest.source_family_policy_v1()
returns table (family text, version text, approved boolean, review_expires_at timestamptz)
language sql stable security invoker set search_path = pg_catalog as $$
  select 'pokesup-enumerated'::text, 'pokesup-enumerated-v1'::text,
    true, '2026-10-09T00:00:00Z'::timestamptz;
$$;

create table ingest.source_family_candidates (
  url text primary key check (url ~ '^https://[a-z][a-z0-9.-]+/[a-zA-Z0-9/_-]*$' and length(url) <= 512),
  state text not null default 'pending_family' check (state in
    ('pending_family','pending_evidence','quarantined','admitted','duplicate','retracted')),
  discovered_at timestamptz not null default clock_timestamp(),
  checked_at timestamptz,
  reason text not null default 'pending_family' check (reason in
    ('pending_family','pending_evidence','invalid_evidence','fixed_duplicate','cohort_duplicate','valid','retracted'))
);
create index source_family_candidates_due on ingest.source_family_candidates (checked_at nulls first, url)
  where state not in ('duplicate','retracted');

create table ingest.source_family_admissions (
  url text primary key references ingest.source_family_candidates(url),
  policy_version text not null check (policy_version = 'pokesup-enumerated-v1'),
  post_id bigint not null unique check (post_id > 0),
  product text not null check (product ~ '^[a-z][a-z0-9]{0,15}$' and product<>'m5'),
  opening_ordinal integer not null check (opening_ordinal between 1 and 99),
  published_at timestamptz not null,
  verified_at timestamptz not null,
  resource_sha256 text not null unique check (resource_sha256 ~ '^[0-9a-f]{64}$'),
  video_sha256 text check (video_sha256 ~ '^[0-9a-f]{64}$'),
  pack_count integer not null check (pack_count = 30),
  unique(product,opening_ordinal)
);
-- Permanent hash-only reservations survive quarantine, expiry and restore.
create table ingest.source_family_identity_keys (
  identity_sha256 text primary key check (identity_sha256 ~ '^[0-9a-f]{64}$'),
  url_sha256 text not null check (url_sha256 ~ '^[0-9a-f]{64}$')
);
create index source_family_identity_url on ingest.source_family_identity_keys(url_sha256);
create table ingest.source_family_tombstones (
  url_sha256 text primary key check (url_sha256 ~ '^[0-9a-f]{64}$'),
  reason text not null check (reason in ('duplicate','retracted'))
);
create table ingest.source_family_runs (
  job_id uuid primary key references ingest.jobs(id) on delete cascade,
  generation bigint not null,
  target_url text not null,
  result jsonb check (octet_length(result::text) <= 120000),
  requests integer not null default 0 check (requests between 0 and 3),
  last_request_at timestamptz,
  created_at timestamptz not null default clock_timestamp()
);
create index source_family_runs_expiry on ingest.source_family_runs(created_at);
create table ingest.source_family_clock (
  singleton boolean primary key default true check (singleton),
  discovered_at timestamptz
);
insert into ingest.source_family_clock(singleton) values (true);
create table ingest.source_family_control (
  singleton boolean primary key default true check(singleton),
  enabled boolean not null default false,
  policy_version text not null check(policy_version='pokesup-enumerated-v1')
);
insert into ingest.source_family_control values(true,false,'pokesup-enumerated-v1');

create function ingest.source_family_access_v1()
returns boolean language sql stable security invoker set search_path=pg_catalog as $$
  select exists(select 1 from ingest.source_family_policy_v1() f
    cross join ingest.source_family_control c
    join ingest.source_policies p on p.source_key='public_study_pokesup_jp_30'
    join ingest.reviewed_public_study_contracts() fixed on fixed.policy_key=p.source_key
    where f.approved and c.enabled and c.policy_version=f.version
      and f.review_expires_at>statement_timestamp()
      and p.enabled and not p.is_demo and p.domain='pokesup.com'
      and p.base_url=fixed.canonical_url and p.version=fixed.policy_version and p.config=fixed.config
      and p.access_mode='public' and p.robots_policy='respect'
      and p.collector_type='scrapling_http' and p.routes=array['scrapling_http']::text[]
      and not p.include_subdomains and p.browser_profile is null
      and p.min_delay_seconds=30 and p.max_concurrency=1);
$$;

-- The catalog is currently English-only. These two source-native mappings
-- are the reviewed first slice; new products stay pending a separate review.
-- Discovery never creates a catalog row or guesses a translated product.
create function ingest.source_family_product_name_v1(p_product text)
returns text language sql stable security invoker set search_path=pg_catalog as $$
  select case p_product when 'm2' then 'インフェルノX' when 'm3' then 'ムニキスゼロ' end;
$$;

create function ingest.source_family_ready_v1()
returns boolean language sql stable security definer set search_path=pg_catalog as $$
  select ingest.source_family_access_v1();
$$;

create function ingest.enqueue_source_family_v1(p_slot timestamptz)
returns setof ingest.jobs language plpgsql security definer set search_path = pg_catalog as $$
declare j uuid;
begin
  if not ingest.source_family_access_v1() then return; end if;
  if p_slot is null or p_slot <> date_trunc('hour', p_slot)
      or p_slot > clock_timestamp() or p_slot < clock_timestamp() - interval '2 hours' then
    raise exception 'invalid family schedule slot';
  end if;
  perform pg_advisory_xact_lock(718180001);
  select id into j from ingest.jobs where job_type = 'source.family.cycle'
    and not is_demo and dedupe_key = 'source-family:' || extract(epoch from p_slot)::bigint;
  if j is not null then return query select * from ingest.jobs where id = j; return; end if;
  return query insert into ingest.jobs(job_type,payload,priority,dedupe_key,available_at,max_attempts,is_demo)
    values ('source.family.cycle','{"family":"pokesup-enumerated"}',12,
      'source-family:' || extract(epoch from p_slot)::bigint,p_slot,1,false) returning *;
end;
$$;

create function ingest.begin_source_family_v1(p_job uuid,p_worker text,p_generation bigint)
returns table(target_url text,product_name text) language plpgsql security definer set search_path = pg_catalog as $$
declare j ingest.jobs%rowtype; g ingest.source_request_gates%rowtype; target text;
begin
  select * into j from ingest.jobs where id=p_job for update;
  if not found or j.status <> 'running' or j.locked_by is distinct from p_worker
      or j.lease_generation is distinct from p_generation or j.lock_expires_at <= clock_timestamp()
      or j.is_demo or j.job_type <> 'source.family.cycle'
      or j.payload <> '{"family":"pokesup-enumerated"}'::jsonb then return; end if;
  if not ingest.source_family_access_v1() then return; end if;
  -- Share the existing domain request gate; do not alter its policy or bypass
  -- the exact M5 collector. Its active_until covers this bounded network run.
  select * into g from ingest.source_request_gates
    where source_key='public_study_pokesup_jp_30' for update;
  if not found or g.active_until > clock_timestamp() then return; end if;
  if exists(select 1 from ingest.source_family_runs where job_id=p_job and generation=p_generation) then
    return; -- A network acquisition is single-use per generation.
  end if;
  delete from ingest.source_family_runs where created_at < clock_timestamp()-interval '1 day';
  -- Immutable first-admission metadata survives expiry. Public filtering owns
  -- the 365-day window; edited publication dates cannot recycle old packs.
  if (select discovered_at is null or discovered_at < clock_timestamp()-interval '1 day'
      from ingest.source_family_clock) then
    target := 'https://pokesup.com/blog-sitemap.xml';
  else
    select c.url into target from ingest.source_family_candidates c
      where c.state in ('pending_family','pending_evidence','admitted','quarantined')
      and ingest.source_family_product_name_v1(substring(c.url from '/unboxing-([a-z][a-z0-9]{0,15})')) is not null
      and c.url ~ '^https://pokesup.com/blog/unboxing-[a-z][a-z0-9]{0,15}(-([2-9]|[1-9][0-9]))?/$'
      and (c.checked_at is null or c.checked_at < clock_timestamp()-interval '1 day')
      order by c.checked_at nulls first,c.url limit 1 for update skip locked;
    if target is null then target := 'https://pokesup.com/blog-sitemap.xml'; end if;
  end if;
  update ingest.source_request_gates set owner_job_id=p_job,owner_lease_generation=p_generation,
    acquired_at=clock_timestamp(),active_until=clock_timestamp()+interval '5 minutes'
    where source_key='public_study_pokesup_jp_30';
  insert into ingest.source_family_runs(job_id,generation,target_url) values(p_job,p_generation,target)
    on conflict(job_id) do update set generation=excluded.generation,target_url=excluded.target_url,
      result=null,requests=0,last_request_at=null,created_at=clock_timestamp();
  return query select target,ingest.source_family_product_name_v1(
    substring(target from '/unboxing-([a-z][a-z0-9]{0,15})'));
end;
$$;

create function ingest.authorize_source_family_request_v1(p_job uuid,p_worker text,p_generation bigint,p_url text)
returns boolean language plpgsql security definer set search_path=pg_catalog as $$
declare j ingest.jobs%rowtype; r ingest.source_family_runs%rowtype; expected text;
begin
  select * into j from ingest.jobs where id=p_job for update;
  if not found or j.status<>'running' or j.locked_by is distinct from p_worker
    or j.lease_generation is distinct from p_generation or j.lock_expires_at<=clock_timestamp()
    or j.job_type<>'source.family.cycle' or j.is_demo or not ingest.source_family_access_v1() then return false; end if;
  select * into r from ingest.source_family_runs where job_id=p_job and generation=p_generation for update;
  if not found or r.result is not null or r.requests>=3
    or r.last_request_at>clock_timestamp()-interval '30 seconds' then return false; end if;
  if not exists(select 1 from ingest.source_request_gates where source_key='public_study_pokesup_jp_30'
    and owner_job_id=p_job and owner_lease_generation=p_generation and active_until>clock_timestamp()) then return false; end if;
  expected:=case r.requests when 0 then 'https://pokesup.com/robots.txt' when 1 then r.target_url
    else 'https://pokesup.com/wp-json/wp/v2/blog?slug='||split_part(r.target_url,'/',5)||'&_fields=id,slug,date_gmt,link' end;
  if p_url is distinct from expected or (r.requests=2 and r.target_url='https://pokesup.com/blog-sitemap.xml') then return false; end if;
  update ingest.source_family_runs set requests=requests+1,last_request_at=clock_timestamp() where job_id=p_job;
  return true;
end;
$$;

create function ingest.stage_source_family_v1(p_job uuid,p_worker text,p_generation bigint,p_result jsonb)
returns void language plpgsql security definer set search_path=pg_catalog as $$
declare j ingest.jobs%rowtype; e jsonb; u text; expected jsonb; r ingest.source_family_runs%rowtype;
  paths text[]; matched_resources boolean:=false; width integer;
begin
  select * into j from ingest.jobs where id=p_job for update;
  if not found or j.status <> 'running' or j.locked_by is distinct from p_worker
    or j.lease_generation is distinct from p_generation or j.lock_expires_at <= clock_timestamp()
    or j.job_type <> 'source.family.cycle' or j.is_demo
    or not ingest.source_family_access_v1() then raise exception 'family lease or access lost'; end if;
  if p_result is null or jsonb_typeof(p_result) <> 'object' or octet_length(p_result::text)>120000
    or not (p_result = '{"quarantine":true}'::jsonb
      or (p_result ? 'urls' and p_result - 'urls' = '{}'::jsonb
          and jsonb_typeof(p_result->'urls')='array' and jsonb_array_length(p_result->'urls')<=200)
      or (p_result ? 'evidence' and p_result - 'evidence' = '{}'::jsonb
          and jsonb_typeof(p_result->'evidence')='object'
          and p_result->'evidence' ?& array['url','post_id','published_at','product','opening_ordinal','labels','resource_sha256','resource_sha256s','video_sha256s']
          and (p_result->'evidence')-array['url','post_id','published_at','product','opening_ordinal','labels','resource_sha256','resource_sha256s','video_sha256s']='{}'::jsonb)) then
    raise exception 'invalid family result'; end if;
  select * into r from ingest.source_family_runs where job_id=p_job and generation=p_generation for update;
  if not found then raise exception 'family run missing'; end if;
  if not exists(select 1 from ingest.source_request_gates where source_key='public_study_pokesup_jp_30'
    and owner_job_id=p_job and owner_lease_generation=p_generation and active_until>clock_timestamp()) then raise exception 'family gate lost'; end if;
  if p_result ? 'urls' then
    if r.target_url<>'https://pokesup.com/blog-sitemap.xml' or r.requests<>2 then raise exception 'discovery attestation missing'; end if;
    for u in select jsonb_array_elements_text(p_result->'urls') loop
      if u is null or u !~ '^https://pokesup.com/blog/unboxing-[a-z][a-z0-9]{0,15}(-([2-9]|[1-9][0-9]))?/$' then
        raise exception 'discovery URL invalid'; end if;
    end loop;
  elsif p_result ? 'evidence' then
    e:=p_result->'evidence';
    select jsonb_agg(side||n||'パック' order by ord,n) into expected
      from (values('左',1),('右',2)) s(side,ord) cross join generate_series(1,15) n;
    if r.requests<>3 or e->>'url' is distinct from r.target_url
      or jsonb_typeof(e->'url')<>'string' or jsonb_typeof(e->'product')<>'string'
      or jsonb_typeof(e->'post_id')<>'number' or jsonb_typeof(e->'opening_ordinal')<>'number'
      or e->>'post_id' !~ '^[1-9][0-9]{0,12}$' or e->>'opening_ordinal' !~ '^[1-9][0-9]?$'
      or e->>'product' !~ '^[a-z][a-z0-9]{0,15}$'
      or e->'labels'<>expected or jsonb_typeof(e->'resource_sha256')<>'string'
      or e->>'resource_sha256' !~ '^[0-9a-f]{64}$'
      or jsonb_typeof(e->'published_at')<>'string'
      or e->>'published_at' !~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}T[0-9]{2}:[0-9]{2}:[0-9]{2}\+00:00$' then
      raise exception 'family evidence leaf invalid'; end if;
    if jsonb_typeof(e->'resource_sha256s') is distinct from 'array' then raise exception 'resource array invalid'; end if;
    if jsonb_array_length(e->'resource_sha256s')<>30 then raise exception 'resource count invalid'; end if;
    if (select count(distinct x) from jsonb_array_elements_text(e->'resource_sha256s')x)<>30
      or exists(select 1 from jsonb_array_elements(e->'resource_sha256s')x
        where jsonb_typeof(x)<>'string' or (x#>>'{}') !~ '^[0-9a-f]{64}$') then raise exception 'resource identities invalid'; end if;
    foreach width in array array[1,2] loop
      select array_agg('/assets/img/blog/'||split_part(r.target_url,'/',5)||'/pack_'||side||'_'||
        (case when width=1 then n::text else lpad(n::text,2,'0') end)||'.jpg' order by ord,n)
        into paths from (values('l',1),('r',2)) s(side,ord) cross join generate_series(1,15)n;
      if e->>'resource_sha256'=encode(extensions.digest(array_to_string(paths,E'\n'),'sha256'),'hex')
        and e->'resource_sha256s'=(select jsonb_agg(encode(extensions.digest(p,'sha256'),'hex') order by ord)
          from unnest(paths) with ordinality x(p,ord)) then matched_resources:=true; end if;
    end loop;
    if not matched_resources then raise exception 'resource layout invalid'; end if;
    if jsonb_typeof(e->'video_sha256s') is distinct from 'array' then raise exception 'video array invalid'; end if;
    if jsonb_array_length(e->'video_sha256s')>1 or exists(
      select 1 from jsonb_array_elements(e->'video_sha256s')x
      where jsonb_typeof(x)<>'string' or (x#>>'{}') !~ '^[0-9a-f]{64}$') then raise exception 'video identity invalid'; end if;
  end if;
  update ingest.source_family_runs set result=p_result where job_id=p_job and generation=p_generation and result is null;
  if not found then raise exception 'family result already staged or not begun'; end if;
end;
$$;

create function ingest.finalize_source_family_v1(p_job uuid,p_worker text,p_generation bigint)
returns setof ingest.jobs language plpgsql security definer set search_path=pg_catalog as $$
declare j ingest.jobs%rowtype; r ingest.source_family_runs%rowtype; u text; e jsonb;
  why text; expected jsonb; published timestamptz; product_id text; policy_ok boolean;
  ordinal_id integer; keys text[]; key_hash text; url_hash text;
begin
  select * into j from ingest.jobs where id=p_job for update;
  if not found or j.locked_by is distinct from p_worker or j.lease_generation is distinct from p_generation
    or j.status <> 'running' or j.lock_expires_at <= clock_timestamp()
    or j.job_type <> 'source.family.cycle' or j.is_demo then return; end if;
  select * into r from ingest.source_family_runs where job_id=p_job and generation=p_generation for update;
  if not found or r.result is null then raise exception 'family result missing'; end if;
  perform 1 from ingest.source_request_gates where source_key='public_study_pokesup_jp_30'
    and owner_job_id=p_job and owner_lease_generation=p_generation and active_until>clock_timestamp() for update;
  if not found then return; end if;
  policy_ok:=ingest.source_family_access_v1();
  perform pg_advisory_xact_lock(718180001);
  if r.target_url='https://pokesup.com/blog-sitemap.xml' then
    if policy_ok and r.requests=2 and r.result ? 'urls' then
      for u in select jsonb_array_elements_text(r.result->'urls') loop
        if u !~ '^https://pokesup.com/blog/unboxing-[a-z][a-z0-9]{0,15}(-([2-9]|[1-9][0-9]))?/$' then
          raise exception 'family discovery URL outside scope'; end if;
        insert into ingest.source_family_candidates(url,state,reason) values(u,'pending_evidence','pending_evidence')
          on conflict(url) do nothing;
        if ingest.source_family_product_name_v1(substring(u from '/unboxing-([a-z][a-z0-9]{0,15})')) is null then
          update ingest.source_family_candidates set state='pending_family',reason='pending_family'
            where url=u and state='pending_evidence';
        end if;
        if exists(select 1 from ingest.reviewed_public_study_contracts() c where c.canonical_url=u)
          or u ~ '^https://pokesup.com/blog/unboxing-m5(-[0-9]+)?/$' then
          update ingest.source_family_candidates set state='duplicate',reason='fixed_duplicate' where url=u;
          insert into ingest.source_family_tombstones values(encode(extensions.digest(u,'sha256'),'hex'),'duplicate') on conflict do nothing;
        end if;
      end loop;
      update ingest.source_family_clock set discovered_at=clock_timestamp();
    end if;
  else
    u:=r.target_url; e:=r.result->'evidence'; why:='invalid_evidence';
    -- Retractions are permanent until separately reviewed code changes the
    -- tombstone. A later successful fetch cannot resurrect an opening.
    if exists(select 1 from ingest.source_family_tombstones where url_sha256=encode(extensions.digest(u,'sha256'),'hex')) then
      why:='retracted';
    elsif not coalesce(policy_ok,false) then why:='pending_family';
    elsif exists(select 1 from ingest.reviewed_public_study_contracts() c
      where c.canonical_url=u or (c.domain='pokesup.com' and lower(c.config->>'set_external_id')=e->>'product')
      or e->'video_sha256s' ? encode(extensions.digest('youtube:'||substring(c.canonical_url
        from 'youtube[.]com/watch[?]v=([A-Za-z0-9_-]{11})'),'sha256'),'hex')) then
      why:='fixed_duplicate';
    elsif e is not null and r.requests=3 then
      select jsonb_agg(side || n || 'パック' order by ord,n) into expected
        from (values('左',1),('右',2)) s(side,ord) cross join generate_series(1,15) n;
      begin
        published:=(e->>'published_at')::timestamptz; product_id:=e->>'product';
        ordinal_id:=case when e->>'opening_ordinal' ~ '^[1-9][0-9]?$' then (e->>'opening_ordinal')::integer end;
        if e->>'url'=u and ingest.source_family_product_name_v1(product_id) is not null and ordinal_id is not null
          and u='https://pokesup.com/blog/unboxing-'||product_id||(case when ordinal_id=1 then '' else '-'||ordinal_id end)||'/'
          and e->'labels'=expected and e->>'post_id' ~ '^[1-9][0-9]{0,12}$'
          and e->>'resource_sha256' ~ '^[0-9a-f]{64}$'
          and published>clock_timestamp()-interval '365 days' and published<=clock_timestamp() then
          url_hash:=encode(extensions.digest(u,'sha256'),'hex');
          select array_agg(encode(extensions.digest(k,'sha256'),'hex')) into keys from unnest(array[
            'pokesup:post:'||(e->>'post_id'), 'pokesup:cohort:'||product_id||':'||ordinal_id,
            'pokesup:resources:'||(e->>'resource_sha256')] || array(
              select 'pokesup:resource:'||x from jsonb_array_elements_text(e->'resource_sha256s')x) || array(
              select 'pokesup:video:'||x from jsonb_array_elements_text(e->'video_sha256s')x)) k;
          if exists(select 1 from ingest.source_family_admissions a where a.url=u and
            (a.published_at<>published or a.post_id<>(e->>'post_id')::bigint
              or a.product<>product_id or a.opening_ordinal<>ordinal_id or a.resource_sha256<>e->>'resource_sha256'
              or a.video_sha256 is distinct from (e->'video_sha256s'->>0))) then
            why:='invalid_evidence';
          elsif exists(select 1 from ingest.source_family_identity_keys k where k.identity_sha256=any(keys) and k.url_sha256<>url_hash) then
            why:='cohort_duplicate';
          else why:='valid'; end if;
        end if;
      exception when invalid_datetime_format or datetime_field_overflow then why:='invalid_evidence'; end;
    end if;
    -- Replace/quarantine and count publication are one transaction. No model
    -- verdict, numerator, creator-reviewer identity or pack-count input exists.
    if why='valid' then
      insert into ingest.source_family_admissions values(u,'pokesup-enumerated-v1',
        (e->>'post_id')::bigint,product_id,ordinal_id,published,clock_timestamp(),e->>'resource_sha256',e->'video_sha256s'->>0,jsonb_array_length(e->'labels'))
        on conflict(url) do update set verified_at=excluded.verified_at;
      foreach key_hash in array keys loop
        insert into ingest.source_family_identity_keys values(key_hash,url_hash) on conflict do nothing;
      end loop;
    end if;
    update ingest.source_family_candidates set checked_at=clock_timestamp(),reason=why,
      state=case why when 'valid' then 'admitted' when 'pending_family' then 'pending_family'
        when 'fixed_duplicate' then 'duplicate' when 'cohort_duplicate' then 'duplicate'
        when 'retracted' then 'retracted' else 'quarantined' end where url=u;
  end if;
  delete from ingest.source_family_runs where job_id=p_job;
  -- Preserve cooldown ownership until active_until: the fixed collector checks
  -- this same gate. Never null it early after a rapid failure.
  return query update ingest.jobs set status='completed',locked_by=null,locked_at=null,
    lock_expires_at=null,completed_at=clock_timestamp(),updated_at=clock_timestamp()
    where id=p_job returning *;
end;
$$;

-- Owner-only retraction, separate from worker permissions and creator review.
create function ingest.retract_source_family_v1(p_url text)
returns void language plpgsql security invoker set search_path=pg_catalog as $$
begin
  perform pg_advisory_xact_lock(718180001);
  insert into ingest.source_family_tombstones values(encode(extensions.digest(p_url,'sha256'),'hex'),'retracted')
    on conflict(url_sha256) do update set reason='retracted';
  update ingest.source_family_candidates set state='retracted',reason='retracted' where url=p_url;
end;
$$;

-- Fail-closed public facts. The private family relation is consumed by the
-- existing coverage projection; no new browser endpoint or UI field is needed.
create function ingest.source_family_public_rows_v1()
returns table(ordinal integer,study_key text,public_id text,public_name text,public_note text,
  domain text,publisher_identity text,canonical_url text,country_code text,country_name text,attribution_basis text,
  set_language text,configured_set_name text,source_observed_at timestamptz,pack_count integer,
  set_external_id text,product_scope text,last_verified_at timestamptz)
language sql stable security invoker set search_path=pg_catalog as $$
  select 1000,'family-'||a.post_id,'pokesup_family_'||a.post_id,'PokeSup enumerated opening '||a.post_id,
    'Explicit pack enumeration; Japan product market, not a physical opening location.',
    'pokesup.com','pokesup.com',a.url,'JP','Japan','product_market','ja',
    ingest.source_family_product_name_v1(a.product),
    a.published_at,a.pack_count,upper(a.product),'booster_box',a.verified_at
  from ingest.source_family_admissions a join ingest.source_family_candidates c using(url)
  cross join ingest.source_family_policy_v1() p
  where ingest.source_family_access_v1() and a.policy_version=p.version
    and ingest.source_family_product_name_v1(a.product) is not null
    and c.state='admitted' and a.published_at>statement_timestamp()-interval '365 days'
    and a.published_at<=statement_timestamp() and a.verified_at>statement_timestamp()-interval '48 hours'
    and not exists(select 1 from ingest.source_family_tombstones t
      where t.url_sha256=encode(extensions.digest(a.url,'sha256'),'hex'))
    and not exists(select 1 from ingest.reviewed_public_study_contracts() fixed
      where fixed.canonical_url=a.url or (fixed.domain='pokesup.com' and lower(fixed.config->>'set_external_id')=a.product)
      or a.video_sha256=encode(extensions.digest('youtube:'||substring(fixed.canonical_url
        from 'youtube[.]com/watch[?]v=([A-Za-z0-9_-]{11})'),'sha256'),'hex'));
$$;

-- Guarded insertion into the latest v2 projection preserves every fixed row,
-- statistical numerator and old gate. Family rows have no numerator fields.
do $projection$
declare definition text; anchor text := E'\n),\ndata_version_rows as (';
begin
  select pg_get_functiondef('public.get_public_study_coverage_v2()'::regprocedure) into definition;
  if position(anchor in definition)=0 then raise exception 'coverage projection boundary drift'; end if;
  definition:=replace(definition,anchor,E'\n union all select * from ingest.source_family_public_rows_v1()'||anchor);
  if position('''sources'', sources.value' in definition)=0 then raise exception 'coverage source boundary drift'; end if;
  definition:=replace(definition,'''sources'', sources.value',
    $sources$'sources', sources.value || coalesce((select jsonb_agg(jsonb_build_object(
      'id',f.public_id,'name',f.public_name,'kind','community','access','public','status','operational',
      'lastCollectedAt',f.last_verified_at,'url',f.canonical_url,'note',f.public_note,
      'coverage',jsonb_build_object('packsObserved',f.pack_count,'countriesObserved',1,'completeOpenings',1)))
      from ingest.source_family_public_rows_v1() f),'[]'::jsonb)$sources$);
  -- One source identity per event keeps exact counts addressable without
  -- asserting multiple independent publishers; country counts still use domain.
  execute definition;
end;
$projection$;

-- Generic completion cannot attest successful collection for this typed lane.
-- Generic claim already supports bounded job_type filters; enqueue stays narrow.
alter table ingest.jobs add constraint jobs_source_family_payload_check check (
  job_type<>'source.family.cycle' or (not is_demo and payload='{"family":"pokesup-enumerated"}'::jsonb)
);
do $completion$
declare d text; anchor text:='if leased_job.is_demo or leased_job.job_type in (';
begin
  select pg_get_functiondef('ingest.complete_job_v2(uuid,text,bigint)'::regprocedure) into d;
  if position(anchor in d)=0 then raise exception 'generic completion boundary drift'; end if;
  execute replace(d,anchor,anchor||E'\n    ''source.family.cycle'',');
end;
$completion$;

-- Source-agnostic maintenance expires abandoned minimal staging even when
-- this family is disabled. Keep all existing cleanup calls and lease checks.
do $cleanup$
declare d text; anchor text:='  completion_time := clock_timestamp();';
begin
  select pg_get_functiondef('ingest.finalize_cleanup_job(uuid,text,bigint)'::regprocedure) into d;
  if position(anchor in d)=0 then raise exception 'cleanup boundary drift'; end if;
  execute replace(d,anchor,$prune$
  with expired as (
    select runs.job_id from ingest.source_family_runs as runs
      where runs.created_at < lease_checked_at-interval '1 day'
      order by runs.created_at limit 1000 for update skip locked
  ) delete from ingest.source_family_runs r using expired e where r.job_id=e.job_id;
$prune$||anchor);
end;
$cleanup$;

do $permissions$
declare t text; f regprocedure;
begin
  foreach t in array array['source_family_candidates','source_family_admissions','source_family_tombstones','source_family_runs','source_family_clock','source_family_control','source_family_identity_keys'] loop
    execute format('alter table ingest.%I enable row level security',t);
    execute format('alter table ingest.%I force row level security',t);
    execute format('revoke all on ingest.%I from public,anon,authenticated,service_role',t);
  end loop;
  for f in select p.oid::regprocedure from pg_proc p join pg_namespace n on n.oid=p.pronamespace
    where n.nspname='ingest' and (p.proname like '%source_family%') loop
    execute format('alter function %s owner to postgres',f);
    execute format('revoke all on function %s from public,anon,authenticated,service_role',f);
  end loop;
end;
$permissions$;
grant execute on function ingest.enqueue_source_family_v1(timestamptz),
  ingest.source_family_ready_v1(),
  ingest.authorize_source_family_request_v1(uuid,text,bigint,text),
  ingest.begin_source_family_v1(uuid,text,bigint),ingest.stage_source_family_v1(uuid,text,bigint,jsonb),
  ingest.finalize_source_family_v1(uuid,text,bigint) to service_role;

commit;
