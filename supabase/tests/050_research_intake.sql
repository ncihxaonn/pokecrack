create extension if not exists pgtap with schema extensions;
begin;
set local search_path=public,extensions,pg_catalog;
select no_plan();

select ok(not has_table_privilege('anon','ingest.research_intake_references','SELECT'),'references never exposed to anonymous clients');
select ok(not has_table_privilege('authenticated','ingest.research_intake_references','SELECT'),'references never exposed to signed-in clients');
select ok(not has_function_privilege('anon','ingest.import_research_intake_v1(jsonb)','EXECUTE'),'anonymous cannot import');
select ok(not has_function_privilege('authenticated','ingest.import_research_intake_v1(jsonb)','EXECUTE'),'signed-in browser cannot import');
select ok(has_function_privilege('service_role','ingest.import_research_intake_v1(jsonb)','EXECUTE'),'existing collector can call only the narrow importer');
select ok(not exists(
  select 1 from pg_class c join pg_namespace n on n.oid=c.relnamespace
  cross join unnest(array['SELECT','INSERT','UPDATE','DELETE','TRUNCATE','REFERENCES','TRIGGER','MAINTAIN']) privilege
  where n.nspname='ingest' and c.relname in ('research_intake_references','research_intake_control')
    and has_table_privilege('service_role',c.oid,privilege)
),'no direct collector table capabilities or activation privilege');
select is((select count(*)::integer from pg_class c join pg_namespace n on n.oid=c.relnamespace
  where n.nspname='ingest' and c.relname in ('research_intake_references','research_intake_control')
    and c.relrowsecurity and c.relforcerowsecurity),2,'both private relations force RLS');
select is((select count(*)::integer from pg_policies where schemaname='ingest'
  and tablename in ('research_intake_references','research_intake_control')),0,'no permissive policies');
select is((select enabled from ingest.research_intake_control),false,'intake defaults off');

create function pg_temp.manifest(p_url text,p_conflicting boolean default false,p_hash text default repeat('a',64))
returns jsonb language sql as $$
  select jsonb_build_object('schema_version','research-intake-v1','snapshot_sha256',p_hash,
    'references',jsonb_build_array(jsonb_build_object('url',p_url,
      'report_group_sha256',repeat('b',64),'conflicting',p_conflicting)));
$$;
select is(ingest.import_research_intake_v1(pg_temp.manifest('https://example.com/study'))->>'status','paused','disabled intake is a pause');
select is((select count(*)::integer from ingest.research_intake_references),0,'pause writes nothing');
update ingest.research_intake_control set enabled=true;
select is((ingest.import_research_intake_v1(pg_temp.manifest('https://example.com/study'))->>'references_inserted')::integer,1,'unknown source enters private queue');
select is((select count(*)::integer from ingest.source_family_candidates),0,'unknown source never enters fetch queue');
create temporary table first_reference as select * from ingest.research_intake_references;
select is((ingest.import_research_intake_v1(pg_temp.manifest('https://example.com/study'))->>'references_inserted')::integer,0,'replay cannot duplicate a reference');
select is((select first_seen_at from ingest.research_intake_references),(select first_seen_at from first_reference),'first discovery time is immutable');
select is((select last_seen_at from ingest.research_intake_references),(select last_seen_at from first_reference),'identical snapshot is an idempotent no-op');
select lives_ok($$select ingest.import_research_intake_v1(pg_temp.manifest('https://example.com/study',true,repeat('c',64)))$$,'conflicting research is retained');
select is((select conflicting from ingest.research_intake_references),true,'conflicting report remains flagged');
select lives_ok($$select ingest.import_research_intake_v1(pg_temp.manifest('https://example.com/study',false,repeat('d',64)))$$,'later nonconflicting report does not erase conflict');
select is((select conflicting from ingest.research_intake_references),true,'worker cannot clear conflict flag');

-- Only transaction-local synthetic approval; production owner controls stay unchanged.
create or replace function ingest.source_family_policy_v1()
returns table(family text,version text,approved boolean,review_expires_at timestamptz)
language sql stable as $$select 'pokesup-enumerated'::text,'pokesup-enumerated-v1'::text,true,now()+interval '30 days'$$;
select is((ingest.import_research_intake_v1(pg_temp.manifest('https://pokesup.com/blog/unboxing-m2-2'))->>'family_queued')::integer,0,'family runtime pause is respected');
update ingest.source_family_control set enabled=true;
select ok(ingest.source_family_access_v1(),'synthetic family test has existing reviewed access');
select is((ingest.import_research_intake_v1(pg_temp.manifest('https://pokesup.com/blog/unboxing-m2-2'))->>'family_queued')::integer,1,'approved exact family route enters independent evidence queue');
select is((select state from ingest.source_family_candidates where url='https://pokesup.com/blog/unboxing-m2-2/'),'pending_evidence','a reference is not an admission');
select is((ingest.import_research_intake_v1(pg_temp.manifest('https://pokesup.com/blog/unboxing-m2-2'))->>'family_queued')::integer,0,'repeat cannot requeue existing event');
select is((ingest.import_research_intake_v1(pg_temp.manifest('https://pokesup.com/blog/unboxing-m5'))->>'family_queued')::integer,0,'existing fixed contract cannot double count');
select is((ingest.import_research_intake_v1(pg_temp.manifest('https://pokesup.com/blog/unboxing-sv8'))->>'family_queued')::integer,1,'reviewed historical SV8 enters independent evidence queue');
select is((select state from ingest.source_family_candidates where url='https://pokesup.com/blog/unboxing-sv8/'),'pending_evidence','historical reference is not a pack admission');
select is((ingest.import_research_intake_v1(pg_temp.manifest('https://pokesup.com/blog/unboxing-sv7'))->>'family_queued')::integer,0,'other unreviewed products cannot be fetched');
select is((ingest.import_research_intake_v1(pg_temp.manifest('https://pokesup.com/blog/unboxing-sv8-2',true))->>'family_queued')::integer,0,'conflicting historical reference cannot enter fetch queue');
select is((ingest.import_research_intake_v1(pg_temp.manifest('https://pokesup.com/blog/unboxing-m3-2',true))->>'family_queued')::integer,0,'conflicting reference does not queue a new event');
select lives_ok($$select ingest.retract_source_family_v1('https://pokesup.com/blog/unboxing-m2-3/')$$,'owner can tombstone an event before discovery');
select is((ingest.import_research_intake_v1(pg_temp.manifest('https://pokesup.com/blog/unboxing-m2-3'))->>'family_queued')::integer,0,'intake cannot resurrect owner-retracted event');
select is((select count(*)::integer from ingest.source_family_admissions),0,'intake imports zero pack observations');
select is((select count(*)::integer from ingest.source_family_public_rows_v1()),0,'intake adds zero public packs');

select throws_ok($$select ingest.import_research_intake_v1(pg_temp.manifest('http://example.com/a'))$$,'22023',null,'HTTP reference rejected');
select throws_ok($$select ingest.import_research_intake_v1(pg_temp.manifest('https://127.0.0.1/a'))$$,'22023',null,'IP literal rejected');
select throws_ok($$select ingest.import_research_intake_v1(pg_temp.manifest('https://user:secret@example.com/a'))$$,'22023',null,'credentials rejected');
select throws_ok($$select ingest.import_research_intake_v1(pg_temp.manifest('https://example.com/a?secret=x'))$$,'22023',null,'query strings rejected');
select throws_ok($$select ingest.import_research_intake_v1(pg_temp.manifest('https://example.com/a#fragment'))$$,'22023',null,'fragment rejected');
select throws_ok($$select ingest.import_research_intake_v1(pg_temp.manifest('https://example.internal/a'))$$,'22023',null,'internal hostname rejected');
select throws_ok($$select ingest.import_research_intake_v1(pg_temp.manifest('https://example.com:443/a'))$$,'22023',null,'port rejected');
select throws_ok($$select ingest.import_research_intake_v1(pg_temp.manifest('https://EXAMPLE.com/a'))$$,'22023',null,'noncanonical host rejected');
select throws_ok($$select ingest.import_research_intake_v1(pg_temp.manifest('https://example.com/a/'))$$,'22023',null,'noncanonical trailing slash rejected');
select throws_ok($$select ingest.import_research_intake_v1(pg_temp.manifest('https://example.com/a')||'{"approved":true}'::jsonb)$$,'22023',null,'self-approval field rejected');
select throws_ok($$select ingest.import_research_intake_v1(jsonb_set(pg_temp.manifest('https://example.com/a'),'{schema_version}','null'))$$,'22023',null,'null schema rejected');
select throws_ok($$select ingest.import_research_intake_v1(jsonb_set(pg_temp.manifest('https://example.com/a'),'{references,0,packs}','1000'))$$,'22023',null,'reported pack count rejected');
select throws_ok($$select ingest.import_research_intake_v1(jsonb_set(pg_temp.manifest('https://example.com/a'),'{references,0,conflicting}','null'))$$,'22023',null,'null conflict state rejected');
select throws_ok($$select ingest.import_research_intake_v1(jsonb_set(pg_temp.manifest('https://example.com/a'),'{references}',
  jsonb_build_array(pg_temp.manifest('https://example.com/a')->'references'->0,pg_temp.manifest('https://example.com/a')->'references'->0)))$$,'22023',null,'duplicate URL rejected');
select throws_ok($$select ingest.import_research_intake_v1(jsonb_set(pg_temp.manifest('https://example.com/a'),'{references}',
  jsonb_build_array(pg_temp.manifest('https://example.com/z')->'references'->0,pg_temp.manifest('https://example.com/a')->'references'->0)))$$,'22023',null,'unsorted manifest rejected');
select lives_ok($$select ingest.import_research_intake_v1(pg_temp.manifest('https://example.com/開封'))$$,'non-Latin public reference path retained without fetching');

set local role service_role;
select throws_ok($$select * from ingest.research_intake_references$$,'42501',null,'actual worker cannot read private references directly');
select throws_ok($$update ingest.research_intake_control set enabled=true$$,'42501',null,'actual worker cannot enable intake');
select lives_ok($$select ingest.import_research_intake_v1(jsonb_build_object(
  'schema_version','research-intake-v1','snapshot_sha256',repeat('a',64),'references','[]'::jsonb))$$,'actual worker can import bounded empty manifest');
reset role;

-- Capacity failure is explicit and atomic; no truncation of old references.
insert into ingest.research_intake_references(url,report_group_sha256,snapshot_sha256)
select 'https://example.com/capacity-'||n,repeat('a',64),repeat('b',64)
from generate_series(1,10000-(select count(*)::integer from ingest.research_intake_references)) n;
select is((select count(*)::integer from ingest.research_intake_references),10000,'private queue has fixed capacity');
select throws_ok($$select ingest.import_research_intake_v1(pg_temp.manifest('https://example.com/overflow'))$$,'54000',null,'capacity cannot silently evict or expand');
select is((select count(*)::integer from ingest.research_intake_references),10000,'failed overflow writes no row');
select * from finish();
rollback;
