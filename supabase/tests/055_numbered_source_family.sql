create extension if not exists pgtap with schema extensions;
begin;
set local search_path=public,extensions,pg_catalog;
select no_plan();
select is(ingest.numbered_family_ready_v1(),false,'numbered collection defaults off');
select is((select count(*)::integer from ingest.enqueue_numbered_family_v1(now())),0,'disabled lane cannot enqueue');
set local role service_role;
select is(ingest.numbered_family_ready_v1(),false,'worker can call the fenced readiness RPC');
reset role;
select is((select count(*)::integer from pg_class c join pg_namespace n on n.oid=c.relnamespace
  where n.nspname='ingest' and c.relname like 'numbered_family_%' and c.relkind='r'
    and c.relrowsecurity and c.relforcerowsecurity),5,'all five ledgers force RLS');
select ok(not has_table_privilege('service_role','ingest.numbered_family_admissions','INSERT'),'worker cannot directly admit');
select ok(not has_table_privilege('anon','ingest.numbered_family_candidates','SELECT'),'candidates not public');
select ok(not exists(select 1 from pg_class c join pg_namespace n on n.oid=c.relnamespace
  cross join unnest(array['anon','authenticated','service_role']) r(role_name)
  cross join unnest(array['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','MAINTAIN']) p(privilege)
  where n.nspname='ingest' and c.relname like 'numbered_family_%' and c.relkind='r'
    and has_table_privilege(r.role_name,c.oid,p.privilege)),
  'every numbered-family table denies all direct browser and worker capabilities');
select is((select count(*)::integer from pg_policies where schemaname='ingest' and tablename like 'numbered_family_%'),0,
  'no row policies grant alternate access');
select ok(not has_function_privilege('service_role','ingest.retract_numbered_family_v1(text)','EXECUTE'),'retraction owner-only');
select ok(not has_function_privilege('authenticated','ingest.stage_numbered_family_v1(uuid,text,bigint,jsonb)','EXECUTE'),'browser cannot stage facts');
select lives_ok($$select ingest.retract_numbered_family_v1('https://www.kozaru02.com/entry/removed')$$,'owner may retract before discovery');
select is((select state from ingest.numbered_family_candidates where url='https://www.kozaru02.com/entry/removed'),'retracted','pre-discovery retraction retained');

-- Synthetic test enablement is rolled back. Keep tests independent of calendar
-- expiry without relaxing the deployed policy's reviewed expiration.
create or replace function ingest.numbered_family_access_v1()
returns boolean language sql stable security invoker set search_path=pg_catalog as $$
  select exists(select 1 from ingest.numbered_family_control where enabled and policy_version='kozaru-numbered-v1');
$$;
update ingest.numbered_family_control set enabled=true;
create temp table scheduled_job as select id from ingest.enqueue_numbered_family_v1(
  date_bin(interval '5 minutes',now(),'2000-01-01T00:00:00Z'::timestamptz));
select is((select count(*)::integer from scheduled_job),1,'enabled due publisher enqueues one cycle');
select is((select count(*)::integer from ingest.enqueue_numbered_family_v1(
  date_bin(interval '5 minutes',now(),'2000-01-01T00:00:00Z'::timestamptz))),0,'repeat scheduling cannot accumulate pending jobs');
update ingest.jobs set status='cancelled',completed_at=clock_timestamp() where id in (select id from scheduled_job);
create function pg_temp.proof(p_url text,p_seed text default 'first') returns jsonb language sql as $$
  select jsonb_build_object('evidence',jsonb_build_object(
    'canonical_url',p_url,'published_at','2026-01-10T08:11:34+00:00','product_label','MEGAドリームex',
    'pack_count',10,'evidence_sha256',encode(digest(p_seed,'sha256'),'hex'),
    'resource_sha256s',(select jsonb_agg(encode(digest(p_seed||n,'sha256'),'hex') order by n) from generate_series(1,10)n),
    'opening_country',null,'opened_at',null,'statistics_eligible',false));
$$;
create function pg_temp.acquire(p_target text) returns uuid language plpgsql as $$
declare j uuid; target text;
begin
  update ingest.numbered_family_control set active_until=now()-interval '1 minute',last_request_at=now()-interval '1 minute';
  update ingest.numbered_family_candidates set checked_at=now();
  if p_target='https://www.kozaru02.com/feed' then update ingest.numbered_family_control set discovered_at=null;
  else
    update ingest.numbered_family_control set discovered_at=now();
    insert into ingest.numbered_family_candidates(url) values(p_target) on conflict(url) do update set checked_at=null;
  end if;
  insert into ingest.jobs(job_type,payload,status,locked_by,locked_at,lock_expires_at,lease_generation,is_demo)
    values('source.family.cycle','{"family":"kozaru-numbered"}','running','numbered-test',now(),now()+interval '5 minutes',1,false)
    returning id into j;
  select target_url into target from ingest.begin_numbered_family_v1(j,'numbered-test',1);
  if target is distinct from p_target then raise exception 'wrong target'; end if;
  if not ingest.authorize_numbered_family_request_v1(j,'numbered-test',1,'https://www.kozaru02.com/robots.txt') then raise exception 'robots denied'; end if;
  update ingest.numbered_family_control set last_request_at=now()-interval '31 seconds';
  if not ingest.authorize_numbered_family_request_v1(j,'numbered-test',1,p_target) then raise exception 'target denied'; end if;
  return j;
end;
$$;
create function pg_temp.cycle(p_target text,p_result jsonb) returns uuid language plpgsql as $$
declare j uuid;
begin
  j:=pg_temp.acquire(p_target);
  perform ingest.stage_numbered_family_v1(j,'numbered-test',1,p_result);
  perform ingest.finalize_numbered_family_v1(j,'numbered-test',1);
  return j;
end;
$$;

select lives_ok($$select pg_temp.cycle('https://www.kozaru02.com/feed',
  '{"urls":["https://www.kozaru02.com/entry/a","https://www.kozaru02.com/entry/a","https://www.kozaru02.com/entry/removed"]}')$$,'feed candidates enqueue automatically');
select is((select count(*)::integer from ingest.numbered_family_candidates),2,'feed deduplicates URLs');
select is((select state from ingest.numbered_family_candidates where url like '%/removed'),'retracted','discovery cannot undo retraction');
select lives_ok($$select pg_temp.cycle('https://www.kozaru02.com/entry/a',pg_temp.proof('https://www.kozaru02.com/entry/a'))$$,'fenced evidence admitted');
select is((select sum(pack_count)::integer from ingest.numbered_family_admissions),10,'exactly ten packs admitted');
select is((select count(*)::integer from ingest.numbered_family_identity_keys),10,'ten permanent resource reservations');
select lives_ok($$select pg_temp.cycle('https://www.kozaru02.com/entry/a',pg_temp.proof('https://www.kozaru02.com/entry/a'))$$,'repeat refresh succeeds');
select is((select sum(pack_count)::integer from ingest.numbered_family_admissions),10,'repeat does not add packs');
select lives_ok($$select pg_temp.cycle('https://www.kozaru02.com/entry/repost',pg_temp.proof('https://www.kozaru02.com/entry/repost'))$$,'repost handled transactionally');
select is((select state from ingest.numbered_family_candidates where url like '%/repost'),'duplicate','resource reuse marks duplicate');
select is((select count(*)::integer from ingest.numbered_family_admissions),1,'repost adds no admission');
select lives_ok($$select pg_temp.cycle('https://www.kozaru02.com/entry/a',pg_temp.proof('https://www.kozaru02.com/entry/a','changed'))$$,'changed immutable cohort quarantined');
select is((select state from ingest.numbered_family_candidates where url like '%/a'),'quarantined','same URL cannot become a new opening');
select is((select count(*)::integer from ingest.numbered_family_identity_keys),10,'old identities survive quarantine');

create temp table staged_job as select pg_temp.acquire('https://www.kozaru02.com/entry/b') id;
select throws_ok($$select ingest.stage_numbered_family_v1(id,'wrong-worker',1,pg_temp.proof('https://www.kozaru02.com/entry/b')) from staged_job$$,
  'P0001','numbered family lease or access lost','wrong worker cannot stage');
select throws_ok($$select ingest.stage_numbered_family_v1(id,'numbered-test',2,pg_temp.proof('https://www.kozaru02.com/entry/b')) from staged_job$$,
  'P0001','numbered family lease or access lost','stale generation cannot stage');
select throws_ok($$select ingest.stage_numbered_family_v1(id,'numbered-test',1,
  jsonb_set(pg_temp.proof('https://www.kozaru02.com/entry/b'),'{evidence,opening_country}','"JP"')) from staged_job$$,
  'P0001','numbered evidence leaf','country cannot be invented');
select throws_ok($$select ingest.stage_numbered_family_v1(id,'numbered-test',1,
  jsonb_set(pg_temp.proof('https://www.kozaru02.com/entry/b'),'{evidence,pack_count}','1000')) from staged_job$$,
  'P0001','numbered evidence leaf','count cannot be inflated');
select throws_ok($$select ingest.stage_numbered_family_v1(id,'numbered-test',1,
  pg_temp.proof('https://www.kozaru02.com/entry/b')||'{"body":"private text"}'::jsonb) from staged_job$$,
  'P0001','invalid numbered result shape','raw content cannot enter staging');
select lives_ok($$select ingest.stage_numbered_family_v1(id,'numbered-test',1,pg_temp.proof('https://www.kozaru02.com/entry/b','second')) from staged_job$$,'valid result stages');
select throws_ok($$select ingest.stage_numbered_family_v1(id,'numbered-test',1,pg_temp.proof('https://www.kozaru02.com/entry/b','second')) from staged_job$$,
  'P0001','numbered family run missing or already staged','staging is single-use');
update ingest.numbered_family_control set enabled=false;
select is((select count(*)::integer from staged_job j cross join lateral ingest.finalize_numbered_family_v1(j.id,'numbered-test',1)),0,'revocation prevents finalization');
update ingest.numbered_family_control set enabled=true;
select lives_ok($$select ingest.finalize_numbered_family_v1(id,'numbered-test',1) from staged_job$$,'valid finalization resumes');
select is((select count(*)::integer from ingest.numbered_family_admissions),2,'independent resources add second cohort');
select lives_ok($$select ingest.retract_numbered_family_v1('https://www.kozaru02.com/entry/b')$$,'owner retracts admitted cohort');
select is((select count(*)::integer from ingest.numbered_family_identity_keys),20,'retraction preserves reservations');

select lives_ok($$select pg_temp.cycle('https://www.kozaru02.com/entry/bridge',
  jsonb_set(pg_temp.proof('https://www.kozaru02.com/entry/bridge','bridge'),'{evidence,resource_sha256s,0}',
    pg_temp.proof('https://www.kozaru02.com/entry/a')#>'{evidence,resource_sha256s,0}'))$$,'partial repost retained as duplicate evidence');
select is((select state from ingest.numbered_family_candidates where url like '%/bridge'),'duplicate','partial overlap is not a new cohort');
select is((select count(*)::integer from ingest.numbered_family_identity_keys),29,'novel hashes in duplicate reports are reserved');
select lives_ok($$select pg_temp.cycle('https://www.kozaru02.com/entry/chain',
  jsonb_set(pg_temp.proof('https://www.kozaru02.com/entry/chain','chain'),'{evidence,resource_sha256s,0}',
    pg_temp.proof('https://www.kozaru02.com/entry/bridge','bridge')#>'{evidence,resource_sha256s,1}'))$$,'chained partial repost processed');
select is((select state from ingest.numbered_family_candidates where url like '%/chain'),'duplicate','novel subset cannot evade duplicate history');
select is((select count(*)::integer from ingest.numbered_family_admissions),2,'transitive reposts add no cohorts');
select is((select url_sha256 from ingest.numbered_family_identity_keys where resource_sha256=encode(digest('first1','sha256'),'hex')),
  encode(digest('https://www.kozaru02.com/entry/a','sha256'),'hex'),'original resource owner is preserved');

select lives_ok($$select pg_temp.cycle('https://www.kozaru02.com/feed','{"quarantine":true}')$$,'failed feed finalizes without losing its check time');
select ok((select discovered_at>=now() from ingest.numbered_family_control),'failed feed consumes daily discovery slot');
update ingest.numbered_family_control set active_until=now()-interval '1 minute';
select is((select count(*)::integer from ingest.enqueue_numbered_family_v1(
  date_bin(interval '5 minutes',now(),'2000-01-01T00:00:00Z'::timestamptz))),0,'feed failure does not enqueue again after ownership cooldown');

create temp table backoff_job as select pg_temp.acquire('https://www.kozaru02.com/feed') id;
select ok((select ingest.defer_numbered_family_v1(id,'numbered-test',1,now()+interval '2 hours') from backoff_job),'backoff stored while lease valid');
select ok((select active_until>=now()+interval '2 hours' from ingest.numbered_family_control),'backoff applies to domain');
select ok(not (select ingest.defer_numbered_family_v1(id,'numbered-test',2,now()+interval '4 hours') from backoff_job),'stale lease cannot extend cooldown');
select is((select count(*)::integer from ingest.enqueue_numbered_family_v1(
  date_bin(interval '5 minutes',now(),'2000-01-01T00:00:00Z'::timestamptz))),0,'outstanding cycle prevents queue accumulation');
select is((select count(*)::integer from backoff_job j cross join lateral ingest.begin_numbered_family_v1(j.id,'numbered-test',1)),0,'active cooldown prevents reacquisition');
select * from finish();
rollback;
