-- The hardening migration is intentionally forward-only.  This suite checks
-- the exact SECURITY DEFINER path, exercises the submitter through SET ROLE,
-- and installs hostile temporary functions to prove that an operator call
-- never resolves an unqualified built-in from pg_temp.
create extension if not exists pgtap with schema extensions;

begin;
set local search_path = public, extensions, pg_catalog, pg_temp;
select no_plan();

select ok(
  (select count(*) = 4 and bool_and(
      functions.proowner = 'postgres'::regrole
      and functions.prosecdef
      and functions.proconfig = array['search_path=pg_catalog, pg_temp']::text[]
    )
   from pg_catalog.pg_proc as functions
   where functions.oid = any(array[
     'ingest.submit_authorized_opening_v1(jsonb)'::regprocedure,
     'ingest.list_authorized_opening_reviews_v1(text,integer)'::regprocedure,
     'ingest.review_authorized_opening_v1(uuid,bigint,text,text,text)'::regprocedure,
     'ingest.retract_authorized_opening_v1(uuid,text,text)'::regprocedure
   ])),
  'all four authorized-opening RPCs are postgres-owned SECURITY DEFINER functions with the exact pg_catalog, pg_temp path'
);

select ok(
  (select functions.proowner = 'postgres'::regrole
      and functions.prosecdef
      and functions.proconfig = array['search_path=pg_catalog, pg_temp']::text[]
   from pg_catalog.pg_proc as functions
   where functions.oid = 'ingest.submit_authorized_opening_direct_v1(jsonb)'::regprocedure),
  'the submitter wrapper is postgres-owned SECURITY DEFINER with the same exact search path'
);

select ok(
  has_function_privilege(
    'service_role',
    'ingest.submit_authorized_opening_v1(jsonb)'::regprocedure,
    'execute'
  )
  and not has_function_privilege(
    'pokecrack_authorized_opening_submitter',
    'ingest.submit_authorized_opening_v1(jsonb)'::regprocedure,
    'execute'
  )
  and has_function_privilege(
    'pokecrack_authorized_opening_submitter',
    'ingest.submit_authorized_opening_direct_v1(jsonb)'::regprocedure,
    'execute'
  )
  and not has_function_privilege(
    'service_role',
    'ingest.submit_authorized_opening_direct_v1(jsonb)'::regprocedure,
    'execute'
  )
  and not has_function_privilege(
    'pokecrack_authorized_opening_reviewer',
    'ingest.submit_authorized_opening_direct_v1(jsonb)'::regprocedure,
    'execute'
  ),
  'the submitter capability reaches only the direct wrapper while service_role retains the historical submit RPC'
);

-- Give the test session the same SET-only capability as the dedicated login;
-- all calls below run under the actual role rather than an owner shortcut.
grant pokecrack_authorized_opening_submitter to current_user
  with inherit false, set true;
grant pokecrack_authorized_opening_reviewer to current_user
  with inherit false, set true;

-- Deliberately put pg_temp first for the caller.  Every function below must
-- still resolve the pg_catalog built-in because its own fixed path wins.
create or replace function pg_temp.clock_timestamp()
returns timestamptz
language plpgsql
as $shadow_clock$
begin
  raise exception using errcode = 'P0001', message = 'shadow function was called';
end;
$shadow_clock$;
create or replace function pg_temp.jsonb_typeof(jsonb)
returns text
language plpgsql
as $shadow_jsonb_typeof$
begin
  raise exception using errcode = 'P0001', message = 'shadow function was called';
end;
$shadow_jsonb_typeof$;
create or replace function pg_temp.btrim(text)
returns text
language plpgsql
as $shadow_btrim$
begin
  raise exception using errcode = 'P0001', message = 'shadow function was called';
end;
$shadow_btrim$;
create or replace function pg_temp.normalize(text, text)
returns text
language plpgsql
as $shadow_normalize$
begin
  raise exception using errcode = 'P0001', message = 'shadow function was called';
end;
$shadow_normalize$;
create or replace function pg_temp.octet_length(text)
returns integer
language plpgsql
as $shadow_octet_length$
begin
  raise exception using errcode = 'P0001', message = 'shadow function was called';
end;
$shadow_octet_length$;

set local search_path = pg_temp, public, extensions, pg_catalog;

select set_config('pokecrack.authorized_opening_hardening_submit_state', '', true);
set local role service_role;
do $service_submit_shadow$
begin
  begin
    perform 1 from ingest.submit_authorized_opening_v1('{}'::jsonb);
    perform set_config(
      'pokecrack.authorized_opening_hardening_submit_state', 'unexpected', true
    );
  exception when others then
    perform set_config(
      'pokecrack.authorized_opening_hardening_submit_state', sqlstate, true
    );
  end;
end;
$service_submit_shadow$;
reset role;

select set_config('pokecrack.authorized_opening_hardening_list_state', '', true);
set local role pokecrack_authorized_opening_reviewer;
do $review_list_shadow$
begin
  begin
    perform 1 from ingest.list_authorized_opening_reviews_v1('not-a-state', 10);
    perform set_config(
      'pokecrack.authorized_opening_hardening_list_state', 'unexpected', true
    );
  exception when others then
    perform set_config(
      'pokecrack.authorized_opening_hardening_list_state', sqlstate, true
    );
  end;
end;
$review_list_shadow$;
reset role;

select set_config('pokecrack.authorized_opening_hardening_review_state', '', true);
set local role pokecrack_authorized_opening_reviewer;
do $review_decision_shadow$
begin
  begin
    perform 1 from ingest.review_authorized_opening_v1(
      '00000000-0000-0000-0000-000000000001'::uuid,
      1,
      'in_review',
      repeat('a', 64),
      'not-a-valid-reason'
    );
    perform set_config(
      'pokecrack.authorized_opening_hardening_review_state', 'unexpected', true
    );
  exception when others then
    perform set_config(
      'pokecrack.authorized_opening_hardening_review_state', sqlstate, true
    );
  end;
end;
$review_decision_shadow$;
reset role;

select set_config('pokecrack.authorized_opening_hardening_retract_state', '', true);
set local role pokecrack_authorized_opening_reviewer;
do $retract_shadow$
begin
  begin
    perform 1 from ingest.retract_authorized_opening_v1(
      '00000000-0000-0000-0000-000000000001'::uuid,
      repeat('b', 64),
      'not-a-valid-reason'
    );
    perform set_config(
      'pokecrack.authorized_opening_hardening_retract_state', 'unexpected', true
    );
  exception when others then
    perform set_config(
      'pokecrack.authorized_opening_hardening_retract_state', sqlstate, true
    );
  end;
end;
$retract_shadow$;
reset role;

select is(
  current_setting('pokecrack.authorized_opening_hardening_submit_state'),
  '22023',
  'service-role submit validation resolves built-ins from pg_catalog'
);
select is(
  current_setting('pokecrack.authorized_opening_hardening_list_state'),
  '22023',
  'review list validation resolves built-ins from pg_catalog'
);
select is(
  current_setting('pokecrack.authorized_opening_hardening_review_state'),
  '22023',
  'review decision validation resolves built-ins from pg_catalog'
);
select is(
  current_setting('pokecrack.authorized_opening_hardening_retract_state'),
  '22023',
  'retraction validation resolves built-ins from pg_catalog'
);

select set_config('pokecrack.authorized_opening_direct_social_state', '', true);
set local role pokecrack_authorized_opening_submitter;
do $direct_social_rejection$
begin
  begin
    perform 1
    from ingest.submit_authorized_opening_direct_v1(
      jsonb_build_object(
        'discoveryPlatform', 'youtube',
        'discoveryCandidateSha256', repeat('c', 64)
      )
    );
    perform set_config(
      'pokecrack.authorized_opening_direct_social_state', 'unexpected', true
    );
  exception when others then
    perform set_config(
      'pokecrack.authorized_opening_direct_social_state', sqlstate, true
    );
  end;
end;
$direct_social_rejection$;

select set_config('pokecrack.authorized_opening_core_bypass_state', '', true);
do $core_bypass_rejection$
begin
  begin
    perform 1
    from ingest.submit_authorized_opening_v1(
      jsonb_build_object(
        'discoveryPlatform', 'youtube',
        'discoveryCandidateSha256', repeat('d', 64)
      )
    );
    perform set_config(
      'pokecrack.authorized_opening_core_bypass_state', 'unexpected', true
    );
  exception when others then
    perform set_config(
      'pokecrack.authorized_opening_core_bypass_state', sqlstate, true
    );
  end;
end;
$core_bypass_rejection$;
reset role;

select is(
  current_setting('pokecrack.authorized_opening_direct_social_state'),
  '22023',
  'SET ROLE submitter rejects a social candidate at the database wrapper boundary'
);
select is(
  current_setting('pokecrack.authorized_opening_core_bypass_state'),
  '42501',
  'SET ROLE submitter cannot bypass the direct-only wrapper through the historical RPC'
);

select * from finish();
rollback;
