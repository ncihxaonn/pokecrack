create extension if not exists pgtap with schema extensions;
begin;
set local search_path=public,extensions,pg_catalog;
select no_plan();
select is((select count(*)::integer from ingest.reviewed_public_study_contracts()),33,'all reviewed contracts remain present');
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
 (case when p_product in ('m2','sv8') then n::text else lpad(n::text,2,'0') end)||'.jpg','sha256'),'hex') order by ord,n)
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

-- Evidence age alone no longer hides a recently verified historical report.
update ingest.source_family_admissions set published_at=now()-interval '366 days' where post_id=484;
create temp table old_identity as select published_at from ingest.source_family_admissions where post_id=484;
select is((select count(*)::integer from ingest.source_family_public_rows_v1() where study_key='family-484'),1,'historical original cohort remains visible');
select lives_ok($$select pg_temp.run_cycle('https://pokesup.com/blog/unboxing-m3/',proof) from proofs where product='m3'$$,'reappearance with fresher source date quarantines');
select is((select published_at from ingest.source_family_admissions where post_id=484),(select published_at from old_identity),'original historical date cannot be refreshed');
select is((select count(*)::integer from ingest.source_family_public_rows_v1() where study_key='family-484'),0,'historical cohort never resurrects via edited date');

-- Three historical source reports: transaction-local replay is test evidence,
-- not proof that production has collected or admitted these reported packs.
select is(ingest.source_family_product_name_v1('sv8'),'超電ブレイカー','reviewed source-native SV8 identity');
select is(ingest.source_family_product_name_v1('sv7'),null::text,'unreviewed product still unmapped');
create temp table historical_proofs as
 select n,pg_temp.proof('sv8',post_id,resource_hash,published,n) proof
 from (values
   (1,120::bigint,'994f0da10b5a7cfb1b31e384b24bd17f1efd0b305213e2847aec9f8df012245a','2024-10-18T16:10:30+00:00'),
   (2,124::bigint,'84c9dadf7bf719fd2a5e9fe905d61a83befa62b3b47d6391fa080dbb924c2384','2024-11-08T13:24:46+00:00'),
   (3,126::bigint,'154670373d7750d027600856d2a798fc324d531416e47c387dd06ea2bf304d84','2024-11-12T09:52:32+00:00')
 ) reports(n,post_id,resource_hash,published);
select lives_ok($$select pg_temp.run_cycle(proof->'evidence'->>'url',proof) from historical_proofs$$,'three historical SV8 reports pass actual fenced SQL admission');
select is((select sum(pack_count)::integer from ingest.source_family_public_rows_v1() where set_external_id='SV8'),90,'three historical cohorts add exactly ninety packs');
select lives_ok($$select pg_temp.run_cycle(proof->'evidence'->>'url',proof) from historical_proofs$$,'historical re-verification is idempotent');
select is((select sum(pack_count)::integer from ingest.source_family_public_rows_v1() where set_external_id='SV8'),90,'historical retries add zero packs');
select is((select count(*)::integer from jsonb_array_elements(public.get_public_study_coverage_v3()->'sources') x
 where x->>'id' in ('pokesup_family_120','pokesup_family_124','pokesup_family_126')),3,'v3 publishes all historical events within its existing period');
select is((select count(*)::integer from jsonb_array_elements(public.get_public_study_coverage_v3()->'sources') x
 where x->>'id' in ('pokesup_family_120','pokesup_family_124','pokesup_family_126')
 and x->'coverage' ? 'qualifyingHitPacks'),0,'historical reports have no invented numerator');
select throws_ok($$select pg_temp.run_cycle(proof->'evidence'->>'url',
 jsonb_set(proof,'{evidence,labels,0}','"左2パック"')) from historical_proofs where n=1$$,
 'P0001','family evidence leaf invalid','normalization does not weaken database enumeration');
update ingest.source_family_admissions set verified_at=now()-interval '49 hours' where product='sv8';
select is((select count(*)::integer from ingest.source_family_public_rows_v1() where set_external_id='SV8'),0,'historical evidence still needs recent verification');
select lives_ok($$select pg_temp.run_cycle(proof->'evidence'->>'url',proof) from historical_proofs$$,'fresh source verification restores historical visibility');
select is((select sum(pack_count)::integer from ingest.source_family_public_rows_v1() where set_external_id='SV8'),90,'freshness recovery preserves ninety-pack denominator');
update ingest.source_family_control set enabled=false;
select is((select count(*)::integer from ingest.source_family_public_rows_v1()),0,'runtime kill still hides historical and recent families');
update ingest.source_family_control set enabled=true;
update ingest.source_policies set enabled=false where source_key='public_study_pokesup_jp_30';
select is((select count(*)::integer from ingest.source_family_public_rows_v1()),0,'source access revocation still hides every family');
update ingest.source_policies set enabled=true where source_key='public_study_pokesup_jp_30';
create or replace function ingest.source_family_policy_v1()
returns table(family text,version text,approved boolean,review_expires_at timestamptz)
language sql stable as $$select 'pokesup-enumerated'::text,'pokesup-enumerated-v1'::text,true,now()-interval '1 second'$$;
select is((select count(*)::integer from ingest.source_family_public_rows_v1()),0,'expired source review cannot be confused with allowed historical evidence');

-- Variable layouts: restore the test-local review only. Fixtures use the
-- independently observed counts/hashes, not box multipliers or live admissions.
create or replace function ingest.source_family_policy_v1()
returns table(family text,version text,approved boolean,review_expires_at timestamptz)
language sql stable as $$select 'pokesup-enumerated'::text,'pokesup-enumerated-v1'::text,true,now()+interval '30 days'$$;
select is(ingest.source_family_pack_count_v1('sv11b'),20,'Black Bolt enumeration has twenty packs');
select is(ingest.source_family_pack_count_v1('sv8a'),10,'Terastal enumeration has ten packs');
select is(ingest.source_family_pack_count_v1('sv9a'),30,'ten explicit three-pack ranges cover thirty packs');
select is(ingest.source_family_pack_count_v1('sv7'),null::integer,'unknown products have no assumed box count');
select is(ingest.source_family_expected_labels_v1('sv7'),null::jsonb,'unknown products have no synthetic labels');
select ok(not has_function_privilege('service_role','ingest.enqueue_pokesup_variable_layout_backfill_v1()','EXECUTE'),'worker cannot initiate owner catch-up');

create temp table variable_reports(product text,post_id bigint,ordinal integer,packs integer,resources integer,hash text,published text);
insert into variable_reports values
 ('sv11b',387,1,20,20,'a8da05c22685cc76a3b8c401dc9b7f1b19af4d7e3d4cdbcfd38ea123b790940f','2025-06-06T17:31:36+00:00'),
 ('sv11w',389,1,20,20,'67140f3bf30d7e3e1ac95fda2c24508763fc8b1c168dde32048a1c18493306c4','2025-06-10T03:04:06+00:00'),
 ('sv2a',190,1,20,20,'8d35f6c9e437672db8d4d4a6937361e4999f8c04bc8c93906d6360f363a00705','2024-12-01T17:06:13+00:00'),
 ('sv8a',192,1,10,10,'16bad74523c81b6ad659ea0a01d5751b84fcb5858e2d9a1563aee6dfff32aad9','2024-12-26T15:34:32+00:00'),
 ('sv9',217,1,30,30,'4069cf384299905ce0ff936ec80788323873cac1760cce505598393162d3a2d6','2025-01-24T00:05:43+00:00'),
 ('sv9',221,2,30,30,'2eab648b6864fc41a429124ebddccab68ba90970444f645c3e678cf7189ccc1d','2025-01-26T09:42:07+00:00'),
 ('sv9a',273,1,30,10,'1666e125ce7a6d0475759c1489cce375d528deb44c0ec64d8143ec5b2d589681','2025-03-16T09:27:42+00:00');
create temp table variable_proofs as
select r.*,jsonb_build_object('evidence',jsonb_build_object(
 'url','https://pokesup.com/blog/'||slug||'/', 'post_id',post_id,'product',product,
 'opening_ordinal',ordinal,'published_at',published,'resource_sha256',hash,
 'video_sha256s','[]'::jsonb,
 'labels',case when product='sv8a' then (select jsonb_agg(n||'パック' order by n) from generate_series(1,10)n)
   else (select jsonb_agg(side||n||'パック' order by ord,n) from (values('左',1),('右',2))s(side,ord)
     cross join generate_series(1,packs/2)n) end,
 'resource_sha256s',(select jsonb_agg(encode(digest(path,'sha256'),'hex') order by pos)
   from (select '/assets/img/blog/'||slug||'/pack_'||
      case when product='sv8a' then n::text
        else (case when n<=resources/2 then 'l_' else 'r_' end)||((n-1)%(resources/2)+1)::text end
      ||'.jpg' as path,n as pos from generate_series(1,resources)n)p)
 ))proof
from variable_reports r cross join lateral (select 'unboxing-'||product||case when ordinal=1 then '' else '-'||ordinal end slug)s;
select lives_ok($$select pg_temp.run_cycle(proof->'evidence'->>'url',proof) from variable_proofs$$,'all seven real-shaped layouts pass fenced SQL validation');
select is((select sum(pack_count)::integer from ingest.source_family_public_rows_v1()
 where set_external_id in ('SV11B','SV11W','SV2A','SV8A','SV9','SV9A')),160,'seven independent reports total exactly 160 enumerated packs');
select lives_ok($$select pg_temp.run_cycle(proof->'evidence'->>'url',proof) from variable_proofs$$,'variable layouts reverify without new counts');
select is((select sum(pack_count)::integer from ingest.source_family_public_rows_v1()
 where set_external_id in ('SV11B','SV11W','SV2A','SV8A','SV9','SV9A')),160,'retries preserve the 160-pack denominator');
select throws_ok($$select pg_temp.run_cycle(proof->'evidence'->>'url',
 jsonb_set(proof,'{evidence,labels,0}','"左2パック"')) from variable_proofs where product='sv11b'$$,
 'P0001','family evidence leaf invalid','variable layouts still reject duplicate pack positions');
select throws_ok($$select pg_temp.run_cycle(proof->'evidence'->>'url',
 jsonb_set(proof,'{evidence,resource_sha256s}',(proof->'evidence'->'resource_sha256s')-0))
 from variable_proofs where product='sv9a'$$,'P0001','resource count invalid','grouped labels do not allow missing resource identity');
update ingest.source_family_admissions set pack_count=30 where product='sv11b';
select is((select count(*)::integer from ingest.source_family_public_rows_v1() where set_external_id='SV11B'),0,'mismatched persisted counts cannot appear in public projection');
update ingest.source_family_admissions set pack_count=20 where product='sv11b';
select is((select count(*)::integer from jsonb_array_elements(public.get_public_study_coverage_v3()->'sources')x
 where x->>'id' in ('pokesup_family_387','pokesup_family_389','pokesup_family_190','pokesup_family_192','pokesup_family_217','pokesup_family_221','pokesup_family_273')
 and x->'coverage' ? 'qualifyingHitPacks'),0,'variable layouts never invent hit numerators');
select * from finish();
rollback;
