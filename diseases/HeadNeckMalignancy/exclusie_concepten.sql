-- Both disqualifying histology categories, OR'd together.
exclusie_concepten AS (
    SELECT concept_id
    FROM concept
    WHERE {{ti-o:CarcinomaInSitu}} OR {{ti-o:HeadNeckOtherExcludedHistology}}
)
