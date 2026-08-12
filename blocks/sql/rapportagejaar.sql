-- #rapportagejaar --------------------------------------------------------
-- Reporting period filter. The start/end date placeholders are left as
-- plain tokens by compose.py — hospital IT fills them in via
-- localize_sql.py or by editing the two literal dates directly.
rapportagejaar AS (
    SELECT
        DATE '{{START_DATE}}' AS jaar_start,   -- <== EDIT HERE (or run localize_sql.py)
        DATE '{{END_DATE}}'   AS jaar_eind     -- <== EDIT HERE (or run localize_sql.py)
)
