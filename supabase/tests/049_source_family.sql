create extension if not exists pgtap with schema extensions;
begin;
set local search_path=public,extensions,pg_catalog;
select no_plan();
select is((select count(*)::integer from ingest.reviewed_public_study_contracts()),32,'fixed contracts unchanged');
select is((select approved from ingest.source_family_policy_v1()),true,'source-reviewed family approved in code');
select is((select count(*)::integer from ingest.enqueue_source_family_v1(date_trunc('hour',now()))),0,'disabled family cannot enqueue');
select is((select count(*)::integer from ingest.source_family_public_rows_v1()),0,'no invented public packs');
select ok(not has_table_privilege('anon','ingest.source_family_candidates','SELECT'),'candidates private');
select ok(not has_table_privilege('service_role','ingest.source_family_admissions','INSERT'),'worker cannot directly admit');
select ok(not exists (
  select 1 from pg_class c join pg_namespace n on n.oid=c.relnamespace
  cross join unnest(array['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','MAINTAIN']) privilege
  where n.nspname='ingest' and c.relname like 'source_family_%' and c.relkind='r'
    and has_table_privilege('service_role',c.oid,privilege)
),'every family ledger denies direct worker table capabilities');
select ok(not has_function_privilege('service_role','ingest.retract_source_family_v1(text)','EXECUTE'),'worker cannot undo or issue owner retractions');
select ok(not has_function_privilege('authenticated','ingest.stage_source_family_v1(uuid,text,bigint,jsonb)','EXECUTE'),'creator reviewer cannot stage crawl verdicts');
select is((select count(*)::integer from pg_class c join pg_namespace n on n.oid=c.relnamespace
  where n.nspname='ingest' and c.relname like 'source_family_%' and c.relkind='r'
  and c.relrowsecurity and c.relforcerowsecurity),7,'all family tables force RLS');
select lives_ok($$select ingest.retract_source_family_v1('https://pokesup.com/blog/unboxing-m2/')$$,'owner can record retraction before rediscovery');
select is((select count(*)::integer from ingest.source_family_tombstones),1,'retraction retains hash tombstone');
select lives_ok($$select ingest.retract_source_family_v1('https://pokesup.com/blog/unboxing-m2/')$$,'retraction idempotent');
-- Synthetic test enablement is transaction-local and rolled back. It is not
-- production approval. Source facts below match separately probed M2/M3 pages.
delete from ingest.source_family_tombstones;
create or replace function ingest.source_family_policy_v1()
returns table(family text,version text,approved boolean,review_expires_at timestamptz)
language sql stable as $$select 'pokesup-enumerated'::text,'pokesup-enumerated-v1'::text,true,now()+interval '30 days'$$;
update ingest.source_family_control set enabled=true;
select ok(ingest.source_family_access_v1(),'review plus runtime switch and unchanged access policy enable lane');
create temporary table before_coverage as select public.get_public_study_coverage_v2() value;

create function pg_temp.proof(p_product text,p_post bigint,p_hash text,p_date text,p_ordinal integer default 1)
returns jsonb language sql as $$
 select jsonb_build_object('evidence',jsonb_build_object(
 'url','https://pokesup.com/blog/unboxing-'||p_product||(case when p_ordinal=1 then '' else '-'||p_ordinal end)||'/',
 'post_id',p_post,'product',p_product,'opening_ordinal',p_ordinal,'published_at',p_date,
 'resource_sha256',p_hash,'video_sha256s','[]'::jsonb,'resource_sha256s',(select jsonb_agg(encode(digest(
 '/assets/img/blog/unboxing-'||p_product||(case when p_ordinal=1 then '' else '-'||p_ordinal end)||'/pack_'||side||'_'||
 (case when p_product='m2' then n::text else lpad(n::text,2,'0') end)||'.jpg','sha256'),'hex') order by ord,n)
 from (values('l',1),('r',2)) s(side,ord) cross join generate_series(1,15)n),
 'labels',(select jsonb_agg(side||n||'パック' order by ord,n)
 from (values('左',1),('右',2)) s(side,ord) cross join generate_series(1,15)n)))
$$;
create function pg_temp.run_cycle(p_target text,p_result jsonb,p_finalize boolean default true)
returns uuid language plpgsql as $$
declare j uuid; target text;
begin
 update ingest.source_request_gates set acquired_at=now()-interval '10 minutes',active_until=now()-interval '1 minute'
   where source_key='public_study_pokesup_jp_30' and owner_job_id is not null;
 update ingest.source_family_candidates set checked_at=now();
 if p_target='https://pokesup.com/blog-sitemap.xml' then update ingest.source_family_clock set discovered_at=null;
 else
   update ingest.source_family_clock set discovered_at=now();
   insert into ingest.source_family_candidates(url,state,reason) values(p_target,'pending_evidence','pending_evidence')
     on conflict(url) do update set checked_at=null;
 end if;
 insert into ingest.jobs(job_type,payload,status,locked_by,locked_at,lock_expires_at,lease_generation,is_demo)
 values('source.family.cycle','{"family":"pokesup-enumerated"}','running','family-test',now(),now()+interval '5 minutes',1,false) returning id into j;
 select target_url into target from ingest.begin_source_family_v1(j,'family-test',1);
 if target is distinct from p_target then raise exception 'unexpected target %',target; end if;
 if not ingest.authorize_source_family_request_v1(j,'family-test',1,'https://pokesup.com/robots.txt') then raise exception 'robots authorization failed'; end if;
 update ingest.source_family_runs set last_request_at=now()-interval '31 seconds' where job_id=j;
 if not ingest.authorize_source_family_request_v1(j,'family-test',1,p_target) then raise exception 'page authorization failed'; end if;
 if p_target<>'https://pokesup.com/blog-sitemap.xml' then
   update ingest.source_family_runs set last_request_at=now()-interval '31 seconds' where job_id=j;
   if not ingest.authorize_source_family_request_v1(j,'family-test',1,
     'https://pokesup.com/wp-json/wp/v2/blog?slug='||split_part(p_target,'/',5)||'&_fields=id,slug,date_gmt,link') then raise exception 'metadata authorization failed'; end if;
 end if;
 perform ingest.stage_source_family_v1(j,'family-test',1,p_result);
 if p_finalize then perform ingest.finalize_source_family_v1(j,'family-test',1); end if;
 return j;
end;
$$;
create temp table proofs as
 select 'm2' product,pg_temp.proof('m2',462,'8a3917c08217118210b7681e09bad8c4c20f5436b5d60d207a4c67adbc7a1ca5','2025-09-30T10:44:54+00:00') proof
 union all select 'm3',pg_temp.proof('m3',484,'18d237b52c62560f175155f363d333074128cdf3853a769c3e8e52154542d24b','2026-01-24T08:20:48+00:00');
select lives_ok($$select pg_temp.run_cycle('https://pokesup.com/blog-sitemap.xml',
 '{"urls":["https://pokesup.com/blog/unboxing-m5/","https://pokesup.com/blog/unboxing-m5-2/","https://pokesup.com/blog/unboxing-m2/","https://pokesup.com/blog/unboxing-m3/"]}')$$,'discovery durably excludes fixed M5 and derivatives');
select is((select count(*)::integer from ingest.source_family_candidates where state='duplicate'),2,'fixed cross-ledger exclusions counted as duplicates');
select lives_ok($$select pg_temp.run_cycle('https://pokesup.com/blog/unboxing-'||product||'/',proof) from proofs$$,'real separately verified facts pass fenced admission');
select is((select sum(pack_count)::integer from ingest.source_family_public_rows_v1()),60,'two reported cohorts add exactly sixty packs');
select is((select count(distinct public_id)::integer from ingest.source_family_public_rows_v1()),2,'source identities are unique per event');
select is((select count(*)::integer from jsonb_array_elements(public.get_public_study_coverage_v3()->'sources') x
 where x->>'id' like 'pokesup_family_%'),2,'existing v3 response includes family sources');
select is((select count(*)::integer from jsonb_array_elements(public.get_public_study_coverage_v3()->'sources') x
 where x->>'id' like 'pokesup_family_%' and x->'coverage' ? 'qualifyingHitPacks'),0,'no invented numerator');
select lives_ok($$select pg_temp.run_cycle('https://pokesup.com/blog/unboxing-m2/',proof) from proofs where product='m2'$$,'repeat collection is idempotent');
select is((select sum(pack_count)::integer from ingest.source_family_public_rows_v1()),60,'no count increase on retry');
select lives_ok($$select pg_temp.run_cycle('https://pokesup.com/blog/unboxing-m2/',jsonb_set(proof,'{evidence,published_at}','"2026-09-08T10:44:54+00:00"')) from proofs where product='m2'$$,'date edits quarantine instead of refreshing old packs');
select is((select count(*)::integer from ingest.source_family_public_rows_v1()),1,'edited date removes cohort from publication');
select is((select published_at from ingest.source_family_admissions where post_id=462),'2025-09-30T10:44:54Z'::timestamptz,'original source date survives quarantine');
select lives_ok($$select pg_temp.run_cycle('https://pokesup.com/blog/unboxing-m2/',proof) from proofs where product='m2'$$,'original unchanged evidence may recover from transient quarantine');
update ingest.source_family_control set enabled=false;
select is((select count(*)::integer from ingest.source_family_public_rows_v1()),0,'runtime kill immediately hides publication');
select is((select count(*)::integer from ingest.enqueue_source_family_v1(date_trunc('hour',now()))),0,'runtime kill prevents enqueue');
update ingest.source_family_control set enabled=true;
update ingest.source_policies set enabled=false where source_key='public_study_pokesup_jp_30';
select is((select count(*)::integer from ingest.source_family_public_rows_v1()),0,'revoked source access hides publication');
update ingest.source_policies set enabled=true where source_key='public_study_pokesup_jp_30';
select lives_ok($$select ingest.retract_source_family_v1('https://pokesup.com/blog/unboxing-m2/')$$,'owner retraction');
select is((select count(*)::integer from ingest.source_family_public_rows_v1()),1,'retraction removes packs without losing identity');
select is((select count(*)::integer from ingest.source_family_admissions),2,'immutable identity records retained');
select is((select count(*)::integer from ingest.source_family_identity_keys),66,'per-resource and cohort dedupe reservations retained');

-- Exercise generation fences, mid-flight revocation and narrow leaf staging.
create temp table staged_job as select pg_temp.run_cycle('https://pokesup.com/blog/unboxing-m3/',proof,false) id from proofs where product='m3';
select is((select count(*)::integer from staged_job cross join lateral ingest.finalize_source_family_v1(id,'family-test',2)),0,'stale generation cannot finalize');
select throws_ok($$select ingest.stage_source_family_v1(id,'family-test',1,
  jsonb_set((select proof from proofs where product='m3'),'{evidence,raw_html}','"private body"')) from staged_job$$,
 'P0001','invalid family result','raw extra fields rejected before staging');
select throws_ok($$select ingest.stage_source_family_v1(id,'family-test',1,
  jsonb_set((select proof from proofs where product='m3'),'{evidence,resource_sha256s,0}',to_jsonb(repeat('a',64)))) from staged_job$$,
 'P0001','resource layout invalid','partial resource replacement rejected');
select throws_ok($$select ingest.stage_source_family_v1(id,'family-test',1,(select proof from proofs where product='m3')) from staged_job$$,
 'P0001','family result already staged or not begun','staging is single-use');
update ingest.source_family_control set enabled=false;
select is((select ingest.authorize_source_family_request_v1(id,'family-test',1,'https://pokesup.com/robots.txt') from staged_job),false,'mid-flight kill refuses network permission');
select throws_ok($$select ingest.stage_source_family_v1(id,'family-test',1,'{"quarantine":true}') from staged_job$$,
 'P0001','family lease or access lost','mid-flight kill refuses staging');
select lives_ok($$select ingest.finalize_source_family_v1(id,'family-test',1) from staged_job$$,'revoked finalizer completes without publication');
select is((select state from ingest.source_family_candidates where url='https://pokesup.com/blog/unboxing-m3/'),'pending_family','revoked result not admitted');
update ingest.source_family_control set enabled=true;
select is((select count(*)::integer from staged_job cross join lateral ingest.finalize_source_family_v1(id,'family-test',1)),0,'completed finalizer retry has no effect');
select lives_ok($$select pg_temp.run_cycle('https://pokesup.com/blog/unboxing-m3/',proof) from proofs where product='m3'$$,'reenabled policy permits re-verification');

-- Generic enqueue stays closed; only the narrow hourly producer creates this
-- typed job. Generic claim can consume it, but generic completion cannot.
create temp table scheduled as select id from ingest.enqueue_source_family_v1(date_trunc('hour',now()));
select is((select id from ingest.enqueue_source_family_v1(date_trunc('hour',now()))),(select id from scheduled),'scheduled slot dedupes');
select is((select count(*)::integer from ingest.claim_jobs_v2('claim-test',array['source.family.cycle'],1,300)),1,'generic scoped claim accepts typed family job');
select throws_ok($$select ingest.complete_job_v2(id,'claim-test',1) from scheduled$$,'22023',null,'generic completion cannot attest family collection');
select throws_ok($$select ingest.enqueue_job_v1('source.family.cycle','{"family":"pokesup-enumerated"}')$$,'22023',null,'generic producer cannot bypass family approval');
select is((select count(*)::integer from scheduled cross join lateral ingest.begin_source_family_v1(id,'wrong-worker',1)),0,'wrong worker cannot acquire request gate');

-- Future ordinal is a synthetic transport fixture, not an extra real count.
create temp table future_proof as select pg_temp.proof('m2',999,
 encode(digest((select string_agg('/assets/img/blog/unboxing-m2-2/pack_'||side||'_'||n||'.jpg',E'\n' order by ord,n)
   from (values('l',1),('r',2)) s(side,ord) cross join generate_series(1,15)n),'sha256'),'hex'),
 to_char(now()-interval '1 day','YYYY-MM-DD"T"HH24:MI:SS')||'+00:00',2) proof;
select lives_ok($$select pg_temp.run_cycle('https://pokesup.com/blog/unboxing-m2-2/',proof) from future_proof$$,'distinct numbered M2 event needs no code edit');
select is((select pack_count from ingest.source_family_admissions where post_id=999),30,'second box ordinal still counts only thirty explicit labels');
select is((select count(*)::integer from ingest.source_family_public_rows_v1()),2,'new ordinal adds one opening after first M2 retraction');

-- Synthetic video identity: different exact image layouts must not defeat a
-- shared active-video reservation. No media is fetched by these fixtures.
create temp table video_proof as select pg_temp.proof('m2',1000,
 encode(digest((select string_agg('/assets/img/blog/unboxing-m2-3/pack_'||side||'_'||n||'.jpg',E'\n' order by ord,n)
   from (values('l',1),('r',2)) s(side,ord) cross join generate_series(1,15)n),'sha256'),'hex'),
 to_char(now()-interval '1 day','YYYY-MM-DD"T"HH24:MI:SS')||'+00:00',3) proof;
update video_proof set proof=jsonb_set(proof,'{evidence,video_sha256s}',jsonb_build_array(encode(digest('youtube:fixture0001','sha256'),'hex')));
select lives_ok($$select pg_temp.run_cycle('https://pokesup.com/blog/unboxing-m2-3/',proof) from video_proof$$,'unique video plus explicit labels admitted');
select is((select pack_count from ingest.source_family_admissions where post_id=1000),30,'video reservation never adds a thirty-first pack');
update video_proof set proof=jsonb_set(pg_temp.proof('m2',1001,
 encode(digest((select string_agg('/assets/img/blog/unboxing-m2-4/pack_'||side||'_'||n||'.jpg',E'\n' order by ord,n)
   from (values('l',1),('r',2)) s(side,ord) cross join generate_series(1,15)n),'sha256'),'hex'),
 to_char(now()-interval '1 day','YYYY-MM-DD"T"HH24:MI:SS')||'+00:00',4),'{evidence,video_sha256s}',proof->'evidence'->'video_sha256s');
select lives_ok($$select pg_temp.run_cycle('https://pokesup.com/blog/unboxing-m2-4/',proof) from video_proof$$,'same active video with new images finalizes safely');
select is((select reason from ingest.source_family_candidates where url='https://pokesup.com/blog/unboxing-m2-4/'),'cohort_duplicate','video reuse blocks new cohort');
select is((select count(*)::integer from ingest.source_family_admissions where post_id=1001),0,'duplicate video contributes no admission');

-- Simulate passage beyond the public window by aging the original fixture.
update ingest.source_family_admissions set published_at=now()-interval '366 days' where post_id=484;
create temp table old_identity as select published_at from ingest.source_family_admissions where post_id=484;
select is((select count(*)::integer from ingest.source_family_public_rows_v1() where study_key='family-484'),0,'expired original cohort is hidden');
select lives_ok($$select pg_temp.run_cycle('https://pokesup.com/blog/unboxing-m3/',proof) from proofs where product='m3'$$,'reappearance with fresher source date quarantines');
select is((select published_at from ingest.source_family_admissions where post_id=484),(select published_at from old_identity),'original expired date cannot be refreshed');
select is((select count(*)::integer from ingest.source_family_public_rows_v1() where study_key='family-484'),0,'expired cohort never resurrects via edited date');
select * from finish();
rollback;
