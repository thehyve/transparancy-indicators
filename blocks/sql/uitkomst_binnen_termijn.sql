-- #uitkomsten: generic "outcome within a time window after a reference
-- event" shape, reused across indicator templates (e.g. unplanned
-- reoperation, mortality, recurrence). Expects `behandelingen`
-- (person_id, procedure_date), `uitkomst_concepten` (concept_id) and
-- `uitkomst_parameters` (termijn_dagen) to already be defined by the
-- template — which ti-o concept counts as the uitkomst and how long the
-- termijn is are fixed per indicator TEMPLATE, not disease- or
-- hospital-specific.
uitkomsten AS (
    SELECT DISTINCT
        b.procedure_occurrence_id
    FROM behandelingen b
    CROSS JOIN uitkomst_parameters up
    INNER JOIN procedure_occurrence uitkomst
        ON uitkomst.person_id = b.person_id
       AND uitkomst.procedure_date > b.procedure_date
       AND uitkomst.procedure_date <= b.procedure_date + (up.termijn_dagen * INTERVAL '1' DAY)
    INNER JOIN uitkomst_concepten uc
        ON uitkomst.procedure_concept_id = uc.concept_id
)
