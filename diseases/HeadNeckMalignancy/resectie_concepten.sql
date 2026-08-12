resectie_concepten AS (
    SELECT concept_id
    FROM concept
    WHERE {{ti-o:HeadNeckResection}}
)
