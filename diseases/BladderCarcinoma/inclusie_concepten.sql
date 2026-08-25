inclusie_concepten AS (
    SELECT concept_id
    FROM concept
    WHERE {{ICD10:C67}}
    OR {{ZA:036250}}
    OR {{ZA:036251}}
    OR {{ZA:036252}}
    OR {{ZA:036253}}
    OR {{ZA:036256}}
    OR {{ZA:036257}}
    OR {{ZA:036258}}
)