begin;

-- Scaffold: CLI 2.115.0 migration new country_research_intake on isolated MAM
-- produced 20260909124316. Ordered after the already-applied 20261018000000;
-- these versions order schema dependencies, not future execution dates.
-- Research references are private proposals. No reported packs, hit counts,
-- country claims, page bodies, media or credentials enter this relation.
create function ingest.research_reference_url_valid_v1(p_url text)
returns boolean language sql immutable security invoker set search_path=pg_catalog as $$
  select p_url is not null and char_length(p_url) between 10 and 1000
    and p_url ~ '^https://([a-z0-9-]+[.])+[a-z]{2,63}/[^[:space:]<>?#]*$'
    and position(chr(92) in p_url)=0 and position(chr(96) in p_url)=0
    and split_part(p_url,'/',3) !~ '[.](local|internal|localhost|invalid)$'
    and (right(p_url,1)<>'/' or p_url ~ '^https://[^/]+/$');
$$;

create table ingest.research_intake_references (
  url text primary key check(ingest.research_reference_url_valid_v1(url)),
  report_group_sha256 text not null check(report_group_sha256 ~ '^[0-9a-f]{64}$'),
  conflicting boolean not null default false,
  first_seen_at timestamptz not null default clock_timestamp(),
  last_seen_at timestamptz not null default clock_timestamp(),
  snapshot_sha256 text not null check(snapshot_sha256 ~ '^[0-9a-f]{64}$'),
  check(last_seen_at>=first_seen_at)
);
create table ingest.research_intake_control (
  singleton boolean primary key default true check(singleton),
  enabled boolean not null default false
);
insert into ingest.research_intake_control(singleton) values(true);

-- Only this validated mutation is granted to the existing collector role.
-- SECURITY DEFINER is the private write boundary, not a browser/user endpoint.
-- The owner alone controls activation. No arbitrary SQL or HTTP is accepted.
create function ingest.import_research_intake_v1(p_manifest jsonb)
returns jsonb language plpgsql security definer set search_path=pg_catalog as $$
declare
  item jsonb; u text; previous_url text; manifest_hash text; received integer;
  enabled_value boolean; row_total integer; new_total integer; conflict_total integer;
  inserted_total integer:=0; queued_total integer:=0;
begin
  if p_manifest is null or jsonb_typeof(p_manifest)<>'object'
      or octet_length(p_manifest::text)>2097152
      or not p_manifest ?& array['schema_version','snapshot_sha256','references']
      or p_manifest-array['schema_version','snapshot_sha256','references']<>'{}'::jsonb
      or p_manifest->>'schema_version' is distinct from 'research-intake-v1'
      or jsonb_typeof(p_manifest->'snapshot_sha256')<>'string'
      or (p_manifest->>'snapshot_sha256') !~ '^[0-9a-f]{64}$'
      or jsonb_typeof(p_manifest->'references')<>'array' then
    raise exception using errcode='22023',message='invalid research intake manifest';
  end if;
  manifest_hash:=p_manifest->>'snapshot_sha256';
  received:=jsonb_array_length(p_manifest->'references');
  if received>10000 then
    raise exception using errcode='22023',message='research intake capacity';
  end if;
  for item in select value from jsonb_array_elements(p_manifest->'references') loop
    if jsonb_typeof(item)<>'object' or not item ?& array['url','report_group_sha256','conflicting']
        or item-array['url','report_group_sha256','conflicting']<>'{}'::jsonb
        or jsonb_typeof(item->'url')<>'string'
        or not ingest.research_reference_url_valid_v1(item->>'url')
        or jsonb_typeof(item->'report_group_sha256')<>'string'
        or (item->>'report_group_sha256') !~ '^[0-9a-f]{64}$'
        or jsonb_typeof(item->'conflicting')<>'boolean' then
      raise exception using errcode='22023',message='invalid research intake reference';
    end if;
    u:=item->>'url';
    if previous_url is not null and previous_url collate "C">=u collate "C" then
      raise exception using errcode='22023',message='duplicate or unsorted research references';
    end if;
    previous_url:=u;
  end loop;

  -- Short database-only transaction; network acquisition occurs later, through
  -- the existing family job/request gates. Serialize complete manifest imports.
  perform pg_advisory_xact_lock(718190001);
  select enabled into enabled_value from ingest.research_intake_control where singleton for update;
  if not found then
    raise exception using errcode='55000',message='research intake control unavailable';
  end if;
  select count(*)::integer,count(*) filter(where conflicting)::integer
    into row_total,conflict_total from ingest.research_intake_references;
  if enabled_value then
    select count(*)::integer into new_total
      from jsonb_array_elements(p_manifest->'references') p
      where not exists(select 1 from ingest.research_intake_references r where r.url=p->>'url');
    if row_total+new_total>10000 then
      raise exception using errcode='54000',message='research intake queue requires review';
    end if;
    with inserted as (
      insert into ingest.research_intake_references(url,report_group_sha256,conflicting,snapshot_sha256)
      select p.url,p.report_group_sha256,p.conflicting,manifest_hash
      from jsonb_to_recordset(p_manifest->'references')
        as p(url text,report_group_sha256 text,conflicting boolean)
      on conflict(url) do nothing returning 1
    ) select count(*)::integer into inserted_total from inserted;
    update ingest.research_intake_references r set
      report_group_sha256=p.report_group_sha256,
      conflicting=r.conflicting or p.conflicting,
      last_seen_at=clock_timestamp(),snapshot_sha256=manifest_hash
    from jsonb_to_recordset(p_manifest->'references')
      as p(url text,report_group_sha256 text,conflicting boolean)
    where r.url=p.url and (r.snapshot_sha256<>manifest_hash or r.report_group_sha256<>p.report_group_sha256
      or (p.conflicting and not r.conflicting));

    -- An exact, already-reviewed family route can join its existing evidence
    -- queue. Appending the canonical slash is specific to this reviewed family;
    -- no generic host/path rewriting, redirects or unknown-product fetches.
    if ingest.source_family_access_v1() then
      with proposed as (
        select r.url||'/' as url,
          (regexp_match(r.url,'^https://pokesup[.]com/blog/unboxing-([a-z][a-z0-9]{0,15})(?:-([2-9]|[1-9][0-9]))?$'))[1] as product
        from ingest.research_intake_references r
        join jsonb_to_recordset(p_manifest->'references') as p(url text) on p.url=r.url
        where not r.conflicting
      ), inserted as (
        insert into ingest.source_family_candidates(url,state,reason)
        select p.url,'pending_evidence','pending_evidence' from proposed p
        where ingest.source_family_product_name_v1(p.product) is not null
          and not exists(select 1 from ingest.source_family_tombstones t
            where t.url_sha256=encode(extensions.digest(p.url,'sha256'),'hex'))
          and not exists(select 1 from ingest.reviewed_public_study_contracts() f
            where f.canonical_url=p.url or (f.domain='pokesup.com'
              and lower(f.config->>'set_external_id')=p.product))
        on conflict(url) do nothing returning 1
      ) select count(*)::integer into queued_total from inserted;
    end if;
    select count(*)::integer,count(*) filter(where conflicting)::integer
      into row_total,conflict_total from ingest.research_intake_references;
  end if;
  return jsonb_build_object('status',case when enabled_value then 'accepted' else 'paused' end,
    'snapshot_sha256',manifest_hash,'references_received',received,
    'references_inserted',inserted_total,'reference_count',row_total,
    'conflicting_count',conflict_total,'family_queued',queued_total);
end;
$$;

alter table ingest.research_intake_references enable row level security;
alter table ingest.research_intake_references force row level security;
alter table ingest.research_intake_control enable row level security;
alter table ingest.research_intake_control force row level security;
revoke all on ingest.research_intake_references,ingest.research_intake_control
  from public,anon,authenticated,service_role;
alter function ingest.research_reference_url_valid_v1(text) owner to postgres;
alter function ingest.import_research_intake_v1(jsonb) owner to postgres;
revoke all on function ingest.research_reference_url_valid_v1(text),
  ingest.import_research_intake_v1(jsonb) from public,anon,authenticated,service_role;
grant execute on function ingest.import_research_intake_v1(jsonb) to service_role;

commit;
