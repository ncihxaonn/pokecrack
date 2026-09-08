begin;

-- Supabase CLI 2.115.0 generated 20260908123613 on MAM; ordered after
-- the already-applied 20261015 ledger. Do not edit that applied migration.
-- Body evidence and the report title are separate identity checks.
do $migration$
declare
  definition text;
  unaffected jsonb;
  old_fragment text := $old$array['1パック', 'VSTARユニバース', '全部で10枚']::text[]$old$;
  new_fragment text := $new$array['タイ語版ポケモンカードをタイのドンキホーテで買って開封してみる。']::text[]$new$;
begin
  if (select title_fragments from ingest.reviewed_public_study_contracts()
      where ordinal = 29 and study_key = 'bokunotebook-vstar-universe-th-1-v1')
      is distinct from array['1パック', 'VSTARユニバース', '全部で10枚']::text[] then
    raise exception 'Expected exact Bokunotebook title-contract correction';
  end if;
  select jsonb_agg(to_jsonb(contracts) order by ordinal) into unaffected
    from ingest.reviewed_public_study_contracts() as contracts where ordinal <> 29;
  select pg_get_functiondef('ingest.reviewed_public_study_contracts()'::regprocedure)
    into definition;
  if (length(definition) - length(replace(definition, old_fragment, '')))
      <> length(old_fragment) then
    raise exception 'Expected exactly one old title fragment';
  end if;
  execute replace(definition, old_fragment, new_fragment);
  if unaffected is distinct from (
    select jsonb_agg(to_jsonb(contracts) order by ordinal)
    from ingest.reviewed_public_study_contracts() as contracts where ordinal <> 29
  ) then
    raise exception 'Unrelated reviewed source contracts changed';
  end if;
end;
$migration$;

alter function ingest.reviewed_public_study_contracts() owner to postgres;
revoke all on function ingest.reviewed_public_study_contracts()
  from public, anon, authenticated, service_role;

commit;
