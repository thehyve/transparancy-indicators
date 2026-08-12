inclusie_concepten AS (
    SELECT concept_id
    FROM concept
    WHERE {{ti-o:HeadNeckOralCavity}}
       OR {{ti-o:HeadNeckOropharynx}}
       OR {{ti-o:HeadNeckNasopharynx}}
       OR {{ti-o:HeadNeckHypopharynx}}
       OR {{ti-o:HeadNeckLarynx}}
       OR {{ti-o:HeadNeckNasalCavityAndSinuses}}
       OR {{ti-o:HeadNeckSalivaryGlands}}
       OR {{ti-o:HeadNeckLymphNodeMetastases}}
)
