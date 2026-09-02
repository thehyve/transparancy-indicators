# How To Run TREX SSSOM Export

This script fetches DHD concepts from TREX and writes 5 SSSOM files.
It DHD concepts to:
* SNOMED
* DBC
* ICD10
* ZA (ZORGACTIVITEIT)
* CBV MIGRATIE

To fetch the data, it uses the following API:
`https://trex.dhd.nl/api/concept/{concept_id}?date={date}`


## 1) Go to the project folder
```bash
cd ./your/repo/destination/transparancy-indicators
```

## 2) Run the exporter (recommended)
```bash
python export_trex_sssom.py --date 2026-08-18 --start-id 0 --output-dir dist/trex
```

Output files:
- `dhd_to_snomed.sssom.tsv`
- `dhd_to_dbc.sssom.tsv`
- `dhd_to_icd10.sssom.tsv`
- `dhd_to_za.sssom.tsv`
- `dhd_to_cbv_migratie.sssom.tsv`

## Useful options

Verbose progress:
```bash
python export_trex_sssom.py --date 2026-08-18 --start-id 0 --output-dir dist/trex --verbose
```

Per-ID decision logging (existing vs fetched):
```bash
python export_trex_sssom.py --date 2026-08-18 --start-id 0 --output-dir dist/trex --log-per-id
```

Limit range for testing:
```bash
python export_trex_sssom.py --date 2026-08-18 --start-id 50000 --max-id 50100 --output-dir dist/trex-test
```

## Resume behavior

The script reuses existing output rows and a state file:
- `dist/trex/.trex_processed_ids.tsv`

So reruns skip already processed IDs and avoid unnecessary API calls.


# Example
An example output is found below. Now it is possible to match the SNOMED code to the DBC, ZA and other systems using DHD. The snomed code is not always available (i.e. TOTAL HIP PROTESE - DHD:0000065910), so some manual mapping should still be done.

## DHD --> ZA

| subject_id | subject_label | predicate_id | object_id | object_label |
| --- | --- | --- | --- | --- |
| DHD:0000065910 | TOTAL HIP PROTHESE | skos:exactMatch | ZA:190305 | Totale heup. |

## DHD --> cbv migratie

| subject_id | subject_label | predicate_id | object_id | object_label |
| --- | --- | --- | --- | --- |
| DHD:0000065910 | TOTAL HIP PROTHESE | skos:exactMatch | CBV:685304 | TOTAL HIP PROTHESE |

## DHD --> SNOMED

| subject_id | subject_label | predicate_id | object_id | object_label |
| --- | --- | --- | --- | --- |
| DHD:0000035929 | urotheelcelcarcinoom van blaas | skos:exactMatch | SNOMED:255109008 | Transitional cell carcinoma of urinary bladder (disorder) |

## DHD --> ICD10

| subject_id | subject_label | predicate_id | object_id | object_label |
| --- | --- | --- | --- | --- |
| DHD:0000035929 | urotheelcelcarcinoom van blaas | skos:exactMatch | ICD10:C67.9 | Maligne neoplasma van blaas, niet gespecificeerd |
| DHD:0000035929 | urotheelcelcarcinoom van blaas | skos:exactMatch | ICD10:C67.9 | Maligne neoplasma van blaas, niet gespecificeerd |
| DHD:0000035929 | urotheelcelcarcinoom van blaas | skos:exactMatch | ICD10:C23 | Maligne neoplasma van galblaas |

## DHD --> DBC

| subject_id | subject_label | predicate_id | object_id | object_label |
| --- | --- | --- | --- | --- |
| DHD:0000035929 | urotheelcelcarcinoom van blaas | skos:exactMatch | DBC:030 | Blaastumor |
| DHD:0000035929 | urotheelcelcarcinoom van blaas | skos:exactMatch | DBC:30 | Blaastumor |
| DHD:0000035929 | urotheelcelcarcinoom van blaas | skos:exactMatch | DBC:02 | Neoplasmata |
| DHD:0000035929 | urotheelcelcarcinoom van blaas | skos:exactMatch | DBC:833 | Maligniteit urinewegen |
