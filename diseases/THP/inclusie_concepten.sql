inclusie_concepten AS (
    SELECT concept_id
    FROM concept
    WHERE {{ti-o:THP}}
    OR {{DHD:0000071917}}
)