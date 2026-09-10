begin;

-- Search references discover candidates, never pack counts. Reuse the existing
-- validated importer and preserve its signature, privileges and paused state.
do $migration$
declare
  definition text;
  anchor text := $anchor$    select count(*)::integer,count(*) filter(where conflicting)::integer
      into row_total,conflict_total from ingest.research_intake_references;
$anchor$;
  addition text := $addition$    -- Serialize capacity with feed finalization, using the same control row.
    perform 1 from ingest.numbered_family_control where singleton for update;
    if ingest.numbered_family_access_v1() then
      with proposed as (
        select r.url
        from ingest.research_intake_references r
        join jsonb_to_recordset(p_manifest->'references') as p(url text) on p.url=r.url
        where not r.conflicting
          and r.url ~ '^https://www[.]kozaru02[.]com/entry/[a-z0-9-]{1,120}$'
          and not exists(select 1 from ingest.numbered_family_candidates c where c.url=r.url)
          and not exists(select 1 from ingest.reviewed_public_study_contracts() f where f.canonical_url=r.url)
        order by r.url collate "C"
        limit greatest(0,10000-(select count(*) from ingest.numbered_family_candidates))
      ), inserted as (
        insert into ingest.numbered_family_candidates(url)
        select url from proposed
        on conflict(url) do nothing returning 1
      ) select queued_total+count(*)::integer into queued_total from inserted;
    end if;
$addition$;
begin
  definition := pg_get_functiondef('ingest.import_research_intake_v1(jsonb)'::regprocedure);
  if (length(definition)-length(replace(definition,anchor,'')))/length(anchor)<>1 then
    raise exception 'research intake routing anchor changed';
  end if;
  execute replace(definition,anchor,addition||anchor);
end;
$migration$;

commit;
