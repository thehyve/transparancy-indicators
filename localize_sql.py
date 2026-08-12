#!/usr/bin/env python3
"""
localize_sql.py — HOSPITAL-FACING tool (stdlib only, no dependencies).

Scope: OMOP SQL indicators only (dist/*.omop.sql). SPARQL indicators use a
separate, existing mechanism (see Voorbeeld volume/volume.ipynb, which
substitutes its patientCohortQueryDeel fragment directly via Python
f-strings) and are not processed by this script.

Fills in a generated dist/<indicator>.omop.sql file with:
  - the reporting period ({{START_DATE}} / {{END_DATE}})
  - concept filters ({{ti-o:...}} tokens), resolved via a SSSOM crosswalk file

By default, concepts are resolved using our shipped ti-o_to_omop_mapping.tsv.
Hospitals using a different local vocabulary/coding for a ti-o concept can
copy that file, edit the `object_id` for the relevant row(s), and pass their
own copy via --sssom-file. The indicator's set of ti-o concepts itself
(inclusion/exclusion definitions) cannot be changed this way — only which
local code(s) they resolve to.

If a hospital prefers not to run Python at all, the same result can be
achieved by manually find/replacing the plain {{...}} tokens in the dist
file with a text editor.

Usage:
    python localize_sql.py dist/THP_volume.omop.sql \
        --start-date 2023-01-01 --end-date 2024-01-01 \
        [--sssom-file ti-o_to_omop_mapping.tsv]
"""
import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
DEFAULT_SSSOM_FILE = ROOT / "ti-o_to_omop_mapping.tsv"

TI_O_TOKEN_RE = re.compile(r"\{\{(ti-o:[^}]+)\}\}")

# Vocabulary values used as placeholders in the shipped SSSOM file for
# concepts that haven't been verified/mapped yet (see NEW_CONCEPT_WORKFLOW.md)
PLACEHOLDER_VOCABULARIES = {"TODO"}


def load_sssom(sssom_path: Path) -> dict[str, list[tuple[str, str]]]:
    """Returns {subject_id: [(vocabulary_id, concept_code), ...]}."""
    mapping: dict[str, list[tuple[str, str]]] = defaultdict(list)
    with sssom_path.open(newline="") as f:
        reader = csv.DictReader(f, delimiter="\t")
        for row in reader:
            subject_id = row["subject_id"].strip()
            object_id = row["object_id"].strip()  # e.g. "SNOMED:52734007"
            vocabulary_id, _, concept_code = object_id.partition(":")
            if not concept_code:
                raise ValueError(
                    f"Malformed object_id '{object_id}' for {subject_id}; "
                    f"expected '<vocabulary>:<code>'"
                )
            mapping[subject_id].append((vocabulary_id, concept_code))
    return mapping


def resolve_ti_o_token(
    ti_o_concept: str,
    mapping: dict[str, list[tuple[str, str]]],
    unresolved: list[str],
) -> str:
    # Skip documentation placeholders like ti-o:... (with ellipsis)
    if ti_o_concept == "ti-o:...":
        return f"{{{{{ti_o_concept}}}}}"  # Return unchanged

    codes = mapping.get(ti_o_concept)
    real_codes = [(vocab, code) for vocab, code in (codes or []) if vocab not in PLACEHOLDER_VOCABULARIES]
    if real_codes:
        clauses = [
            f"(vocabulary_id = '{vocab}' AND concept_code = '{code}')"
            for vocab, code in real_codes
        ]
        return " OR ".join(clauses)
    else:
        # No mapping at all, or only a TODO:VERIFY placeholder row: fall back
        # to a clause using the ti-o concept itself as vocabulary/code. This
        # keeps the SQL syntactically valid and will match rows if the
        # hospital's own concept table already uses 'ti-o' as vocabulary_id
        # (e.g. they loaded ti-o concepts directly, or happen to use the same
        # code under a different name) — otherwise it simply matches nothing.
        unresolved.append(ti_o_concept)
        concept_name = ti_o_concept.removeprefix("ti-o:")
        return f"(vocabulary_id = 'ti-o' AND concept_code = '{concept_name}')"


def localize(sql_text: str, start_date: str, end_date: str, sssom_path: Path) -> tuple[str, list[str]]:
    mapping = load_sssom(sssom_path)
    unresolved: list[str] = []

    def replace_token(match: re.Match) -> str:
        return resolve_ti_o_token(match.group(1), mapping, unresolved)

    sql_text = TI_O_TOKEN_RE.sub(replace_token, sql_text)
    sql_text = sql_text.replace("{{START_DATE}}", start_date)
    sql_text = sql_text.replace("{{END_DATE}}", end_date)
    return sql_text, unresolved


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("query_file", type=Path, help="Path to a dist/<indicator>.omop.sql file")
    parser.add_argument("--start-date", required=True, help="Reporting period start, e.g. 2023-01-01")
    parser.add_argument("--end-date", required=True, help="Reporting period end, e.g. 2024-01-01")
    parser.add_argument("--sssom-file", type=Path, default=DEFAULT_SSSOM_FILE,
                         help="SSSOM crosswalk file (default: our shipped ti-o_to_omop_mapping.tsv)")
    args = parser.parse_args()

    sql_text = args.query_file.read_text()
    result, unresolved = localize(sql_text, args.start_date, args.end_date, args.sssom_file)
    print(result)

    if unresolved:
        unique = sorted(set(unresolved))
        print(
            "\n" + "=" * 70 +
            "\nWARNING: the following ti-o concept(s) could NOT be mapped and were"
            "\nsubstituted as (vocabulary_id = 'ti-o' AND concept_code = '...') in the"
            "\nSQL above. This is valid SQL but will match nothing unless your concept"
            "\ntable itself uses 'ti-o' as vocabulary_id:\n" +
            "\n".join(f"  - {concept}" for concept in unique) +
            "\n\nAdd a real row (vocabulary_id:code) for each of these to your SSSOM"
            "\nfile (--sssom-file) to get correct results."
            "\n" + "=" * 70,
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
