-- #locatie --------------------------------------------------------------
-- Links a matched procedure/treatment to its care site.
behandelingen_met_locatie AS (
    SELECT
        b.procedure_occurrence_id,
        b.person_id,
        vo.care_site_id
    FROM behandelingen b
    INNER JOIN visit_occurrence vo
        ON b.visit_occurrence_id = vo.visit_occurrence_id
)
