-- volume.tpl.sql — generic "treatment volume" indicator template
--
-- Disease-agnostic: counts distinct treatment procedures per location in
-- the reporting period, excluding patients with a disqualifying condition.
-- Which ti-o concepts count as inclusion/exclusion is NOT fixed here — it
-- is supplied per disease by files in diseases/<Disease>/ (e.g.
-- diseases/THP/), which is what makes this template reusable across
-- diseases (THP, and any future "volume" indicator).
--
-- Shared structural blocks (rapportagejaar, locatie) are substituted by
-- compose.py from ./blocks/sql/. The inclusie_concepten / exclusie_concepten
-- placeholders below are the same kind of block, but disease-specific —
-- compose.py substitutes them from diseases/<Disease>/inclusie_concepten.sql
-- and diseases/<Disease>/exclusie_concepten.sql, each a full, hand-written
-- CTE containing {{ti-o:...}} tokens.
--
-- Placeholders for ti-o concepts and the reporting period ARE resolved later
-- by hospital IT via localize_sql.py (or by hand, since they're plain
-- readable placeholders) — these are the {{ti-o:...}} tokens inside the
-- disease CTEs and the {{START_DATE}}/{{END_DATE}} tokens inside rapportagejaar.
--
-- All parameters are grouped at the top of the WITH clause so hospital IT
-- can see everything that needs to change in one place, without reading the
-- rest of the query logic below (which is fixed by ti-o maintainers).

WITH

-- ============================================================================
-- PARAMETERS — hospital-specific values, filled in by localize_sql.py
-- ============================================================================

${rapportagejaar},

-- #inclusie — which treatment counts toward volume (fixed per disease;
-- full CTE supplied by diseases/<Disease>/inclusie_concepten.sql)
${inclusie_concepten},

-- #exclusie — which condition disqualifies a patient (fixed per disease;
-- full CTE supplied by diseases/<Disease>/exclusie_concepten.sql)
${exclusie_concepten},

-- ============================================================================
-- QUERY LOGIC — fixed by ti-o maintainers, do not edit
-- ============================================================================

-- #behandelingen --------------------------------------------------------
behandelingen AS (
    SELECT
        po.procedure_occurrence_id,
        po.person_id,
        po.procedure_date,
        po.visit_occurrence_id
    FROM procedure_occurrence po
    INNER JOIN inclusie_concepten ic
        ON po.procedure_concept_id = ic.concept_id
    CROSS JOIN rapportagejaar rj
    WHERE po.procedure_date >= rj.jaar_start
      AND po.procedure_date <  rj.jaar_eind
),

${locatie}

-- #resultaat --------------------------------------------------------------
SELECT
    cs.care_site_name AS locatie,
    COUNT(DISTINCT bl.procedure_occurrence_id) AS aantal
FROM behandelingen_met_locatie bl
INNER JOIN care_site cs
    ON bl.care_site_id = cs.care_site_id
WHERE NOT EXISTS (
    SELECT 1
    FROM condition_occurrence co
    INNER JOIN exclusie_concepten ec
        ON co.condition_concept_id = ec.concept_id
    WHERE co.person_id = bl.person_id
)
GROUP BY cs.care_site_name
ORDER BY locatie;
