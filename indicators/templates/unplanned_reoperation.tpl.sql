-- unplanned_reoperation.tpl.sql — generic "unplanned reoperation after
-- primary resection" indicator template
--
-- Disease-agnostic: percentage of patients with a primary condition who
-- underwent a resection procedure in the reporting period, who then had an
-- unplanned reoperation for a complication within 30 days — excluding
-- patients with a disqualifying condition (e.g. carcinoma in situ or other
-- excluded histology). Which ti-o concepts fill each role is NOT fixed
-- here — it is supplied per disease by a definition file in
-- indicators/definitions/ (e.g. HHM_heroperatie.yaml), which is what makes
-- this template reusable across diseases (originally modelled after
-- DHNA-gids indicator 3 for head and neck malignancy, but not specific to
-- it).
--
--   Teller  = # patients with an unplanned reoperation for a complication
--             within 30 days after the resection
--   Noemer  = # patients with a resection of the primary condition in the
--             reporting period
--
-- Shared structural blocks (rapportagejaar, locatie) are substituted by
-- compose.py from ./blocks/sql/. The inclusie_concepten / resectie_concepten
-- / exclusie_concepten placeholders below are the same kind of block, but
-- disease-specific — compose.py substitutes them from
-- diseases/<Disease>/inclusie_concepten.sql, resectie_concepten.sql and
-- exclusie_concepten.sql, each a full, hand-written CTE containing
-- {{ti-o:...}} tokens. inclusie_concepten defines the primary condition
-- (patient-level inclusion criterion); resectie_concepten defines which
-- procedure counts as "the" resection for this disease — a disease-
-- definition detail rather than a patient inclusion/exclusion criterion,
-- so it's kept in its own file.
--
-- What counts as an "unplanned reoperation for complication" is NOT
-- disease-specific — it defines this indicator itself — so that CTE is
-- fixed here in the template rather than supplied per disease.
--
-- Placeholders for ti-o concepts and the reporting period ARE resolved
-- later by hospital IT via localize_sql.py (or by hand, since they're
-- plain readable placeholders) — these are the {{ti-o:...}} tokens inside
-- the disease CTEs and the {{START_DATE}}/{{END_DATE}} tokens inside
-- rapportagejaar.
--
-- NOT covered by this query (out of scope for the raw OMOP pipeline, see
-- NEW_CONCEPT_WORKFLOW.md and README_hospitals.md):
--   * Casemix correctie (leeftijd, geslacht, comorbiditeiten, roken,
--     tumorlocatie, cTNM, etc.) — toegepast in een latere/analytische stap.
--   * "Tweede primaire aandoening" exclusieregels (eerder/synchroon/na
--     CIS/recidief) — dit vergt longitudinale registratielogica die verder
--     gaat dan een concept-lookup; te implementeren op basis van de lokale
--     (tumor)registratie i.p.v. via een ti-o concept-token.

WITH

-- ============================================================================
-- PARAMETERS — hospital-specific values, filled in by localize_sql.py
-- ============================================================================

${rapportagejaar},

-- #inclusie: conditie — primaire aandoening (fixed per disease; full CTE
-- supplied by diseases/<Disease>/inclusie_concepten.sql)

-- == EDIT HERE (or run localize_sql.py) ==
${inclusie_concepten},

-- #resectie: procedure — welke procedure telt als resectie van de
-- primaire aandoening; onderdeel van de ziektedefinitie, geen
-- patiënt-inclusie/exclusiecriterium (fixed per disease; full CTE
-- supplied by diseases/<Disease>/resectie_concepten.sql)

-- == EDIT HERE (or run localize_sql.py) ==
${resectie_concepten}, 

-- #exclusie: conditie — disqualificerende (sub)diagnoses (fixed per
-- disease; full CTE supplied by diseases/<Disease>/exclusie_concepten.sql)

-- == EDIT HERE (or run localize_sql.py) ==
${exclusie_concepten}, 

-- #teller: procedure — ongeplande heroperatie i.v.m. complicatie(s), en
-- de termijn waarbinnen die telt. This defines the indicator itself (not
-- disease-specific), so it's fixed here rather than supplied per disease.
uitkomst_concepten AS (
    SELECT concept_id
    FROM concept
    WHERE {{ti-o:UnplannedReoperationForComplication}}   -- <== EDIT HERE (or run localize_sql.py)
),

uitkomst_parameters AS (
    SELECT 30 AS termijn_dagen
),

-- ============================================================================
-- QUERY LOGIC — fixed by ti-o maintainers, do not edit
-- ============================================================================

-- #primaire_aandoening --------------------------------------------------
primaire_aandoening AS (
    SELECT
        co.person_id,
        co.condition_start_date
    FROM condition_occurrence co
    INNER JOIN inclusie_concepten ic
        ON co.condition_concept_id = ic.concept_id
),

-- #behandelingen (noemer: resecties in de verslagperiode) ----------------
behandelingen AS (
    SELECT
        po.procedure_occurrence_id,
        po.person_id,
        po.procedure_date,
        po.visit_occurrence_id
    FROM procedure_occurrence po
    INNER JOIN resectie_concepten rc
        ON po.procedure_concept_id = rc.concept_id
    INNER JOIN primaire_aandoening pa
        ON pa.person_id = po.person_id
       AND pa.condition_start_date <= po.procedure_date
    CROSS JOIN rapportagejaar rj
    WHERE po.procedure_date >= rj.jaar_start
      AND po.procedure_date <  rj.jaar_eind
      AND NOT EXISTS (
          SELECT 1
          FROM condition_occurrence co_excl
          INNER JOIN exclusie_concepten ec
              ON co_excl.condition_concept_id = ec.concept_id
          WHERE co_excl.person_id = po.person_id
      )
),

${locatie},

-- #uitkomst_binnen_termijn (teller: uitkomst binnen N dagen) — shared
-- building block; see blocks/sql/uitkomst_binnen_termijn.sql. Expects
-- uitkomst_concepten / uitkomst_parameters (defined above, fixed for THIS
-- indicator) and behandelingen (defined above) to already exist.
${uitkomst_binnen_termijn}


-- #resultaat --------------------------------------------------------------
SELECT
    cs.care_site_name AS locatie,
    COUNT(DISTINCT u.procedure_occurrence_id) AS teller_heroperaties,
    COUNT(DISTINCT bl.procedure_occurrence_id) AS noemer_resecties,
    ROUND(
        100.0 * COUNT(DISTINCT u.procedure_occurrence_id)
        / NULLIF(COUNT(DISTINCT bl.procedure_occurrence_id), 0),
    1) AS percentage_heroperaties
FROM behandelingen_met_locatie bl
INNER JOIN care_site cs
    ON bl.care_site_id = cs.care_site_id
LEFT JOIN uitkomsten u
    ON u.procedure_occurrence_id = bl.procedure_occurrence_id
GROUP BY cs.care_site_name
ORDER BY locatie;
