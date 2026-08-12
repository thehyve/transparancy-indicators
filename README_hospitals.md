# Running a ti-o indicator query — for hospital IT

> **Status: proposal / proof of concept.** This workflow is still being
> discussed with stakeholders and may change.

This guide explains how to take a published indicator query and run it
against your own OMOP database, using your own reporting period and your
own local coding, without needing to understand the underlying ti-o
ontology or SSSOM mapping format in detail.

## What you get from us

For each indicator (e.g. `THP_volume`), we publish one file:

```
dist/THP_volume.omop.sql
```

This is a plain SQL query. It contains two kinds of placeholders that you
fill in before running it:

| Placeholder | What it means |
|---|---|
| `{{START_DATE}}` / `{{END_DATE}}` | The reporting period you want to compute the indicator for. |
| `{{ti-o:...}}` (e.g. `{{ti-o:THP}}`) | A clinical concept used for inclusion/exclusion. Resolved to the matching code in your local vocabulary. |

Every placeholder is marked in the file with a `<== EDIT HERE` comment, so
it's clear exactly what needs to change and nothing else does.

## Option A — fill it in yourself, no tools needed

Open `dist/THP_volume.omop.sql` in any text editor and:
1. Replace `{{START_DATE}}` / `{{END_DATE}}` with your reporting period.
2. Replace each `{{ti-o:...}}` token with the matching filter for your own
   database, e.g.:
   ```sql
   (vocabulary_id = 'SNOMED' AND concept_code = '52734007')
   ```
   Look up the default mapping we provide in `ti-o_to_omop_mapping.tsv`
   (search for the `ti-o:` concept name), or use your own internal code if
   your systems don't use that vocabulary.
3. Run the resulting SQL directly against your OMOP database. Nothing needs
   to be installed — no views, no extra tables.

## Option B — use our script

If you have Python available, run:

```bash
python localize_sql.py dist/THP_volume.omop.sql \
    --start-date 2023-01-01 --end-date 2024-01-01
```

This fills in the reporting period and resolves every `{{ti-o:...}}` token
using our default crosswalk (`ti-o_to_omop_mapping.tsv`), and prints the
final, ready-to-run SQL.

### Using your own code mapping

If your hospital uses a different code/vocabulary for one of the ti-o
concepts (e.g. your internal system doesn't use SNOMED for total hip
replacement), copy `ti-o_to_omop_mapping.tsv`, edit the relevant row(s), and
point the script at your copy:

```bash
python localize_sql.py dist/THP_volume.omop.sql \
    --start-date 2023-01-01 --end-date 2024-01-01 \
    --sssom-file our_own_mapping.tsv
```

You can only change *which code* a concept resolves to — not which
concepts are included/excluded, since that logic is fixed centrally to keep
the indicator comparable across hospitals.

## What you never need to do

- No database views, tables, or schema changes on your side.
- No templating engine or build tooling — the published file is plain SQL.
- No need to understand the ti-o ontology internals — just the two kinds of
  placeholders above.

## Questions / contributing a code mapping

If a ti-o concept doesn't yet have a mapping for your code system, you're
welcome to propose one by submitting a row to `ti-o_to_omop_mapping.tsv`
(or your own local crosswalk file, if you'd rather not share it) — see the
maintainers for the current contribution process.
