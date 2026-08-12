#!/usr/bin/env python3
"""
localize_sparql.py — HOSPITAL-FACING tool (stdlib only, no dependencies).

Scope: SPARQL indicators only (dist/*.omop.sparql).

Fills in a generated dist/<indicator>.omop.sparql file with:
  - the reporting period ({{START_DATE}} / {{END_DATE}})
  - concept URIs (ti-o:... URIs), resolved via a SSSOM crosswalk file

By default, ti-o: URIs are resolved using our shipped ti-o_to_omop_mapping.tsv.
Hospitals using different local vocabulary/coding for a ti-o concept can
copy that file, edit the `object_id` for the relevant row(s), and pass their
own copy via --sssom-file. The indicator's set of ti-o concepts itself
(inclusion/exclusion definitions) cannot be changed this way — only which
local code(s) they resolve to.

The SSSOM mapping translates ti-o concepts to (vocabulary, code) pairs, which
are then formatted as URIs (e.g., SNOMED:52734007 → <http://snomed.info/id/52734007>,
OMOP:4225446 → <http://example.org/omop#4225446>, etc.). These URIs are
substituted into the SPARQL query's VALUES clauses, replacing the original
ti-o: URIs.

If a hospital prefers to localize by hand, the plain ti-o:... URIs can be
find/replaced in a text editor.

Usage:
    python localize_sparql.py dist/THP_volume.omop.sparql \\
        --start-date 2023-01-01 --end-date 2024-01-01 \\
        [--sssom-file ti-o_to_omop_mapping.tsv]
        [--execute graph.ttl]  # Optional: execute query against an RDF file
"""
import argparse
import csv
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).parent
DEFAULT_SSSOM_FILE = ROOT / "ti-o_to_omop_mapping.tsv"

# Matches {{ti-o:...}} placeholders, same as localize_sparql.py
TI_O_TOKEN_RE = re.compile(r"\{\{(ti-o:[^}]+)\}\}")

# URI prefixes for different vocabularies (hospital can customize these)
VOCABULARY_PREFIXES = {
    "SNOMED": "http://snomed.info/id/",
    "OMOP": "http://example.org/omop#",
    "ICD9": "http://purl.bioontology.org/ontology/ICD9/",
    "ICD10": "http://purl.bioontology.org/ontology/ICD10/",
    "LOINC": "http://loinc.org/rdf#",
}


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


def concept_to_uri(vocabulary_id: str, concept_code: str) -> str:
    """Convert (vocabulary, code) to a URI reference for SPARQL."""
    prefix = VOCABULARY_PREFIXES.get(vocabulary_id, "http://example.org/")
    return f"<{prefix}{concept_code}>"


# Vocabulary values used as placeholders in the shipped SSSOM file for
# concepts that haven't been verified/mapped yet (see NEW_CONCEPT_WORKFLOW.md)
PLACEHOLDER_VOCABULARIES = {"TODO"}


def resolve_ti_o_token(
    ti_o_concept: str,
    mapping: dict[str, list[tuple[str, str]]],
    unresolved: list[str],
) -> str:
    """Resolve a ti-o concept to a SPARQL VALUES list of URIs.

    If found in SSSOM, returns mapped URIs (e.g., <http://snomed.info/id/52734007>).
    If not found (or only a TODO:VERIFY placeholder row), falls back to the bare
    ti-o URI (e.g., ti-o:HipFracture) so the query remains syntactically valid
    and can execute (even if it finds no results) — but the concept is recorded
    in `unresolved` so a warning can be printed.
    """
    # Skip documentation placeholders like ti-o:... (with ellipsis)
    if ti_o_concept == "ti-o:...":
        return f"{{{{{ti_o_concept}}}}}"  # Return unchanged

    codes = mapping.get(ti_o_concept)
    real_codes = [(vocab, code) for vocab, code in (codes or []) if vocab not in PLACEHOLDER_VOCABULARIES]
    if real_codes:
        # Mapping found: convert to target vocabulary URIs
        uris = [concept_to_uri(vocab, code) for vocab, code in real_codes]
        return " ".join(uris)
    else:
        # No mapping at all, or only a TODO:VERIFY placeholder row: fall back
        # to the ti-o URI itself (valid SPARQL; won't match data unless the
        # hospital's graph itself uses ti-o URIs).
        unresolved.append(ti_o_concept)
        return ti_o_concept


def localize_sparql(sparql_text: str, start_date: str, end_date: str, sssom_path: Path) -> tuple[str, list[str]]:
    """Substitute {{ti-o:...}} tokens and date placeholders in SPARQL text."""
    mapping = load_sssom(sssom_path)
    unresolved: list[str] = []

    def replace_token(match: re.Match) -> str:
        ti_o_concept = match.group(1)  # e.g., "ti-o:THP"
        return resolve_ti_o_token(ti_o_concept, mapping, unresolved)

    sparql_text = TI_O_TOKEN_RE.sub(replace_token, sparql_text)
    sparql_text = sparql_text.replace("{{START_DATE}}", start_date)
    sparql_text = sparql_text.replace("{{END_DATE}}", end_date)
    return sparql_text, unresolved


def execute_sparql(sparql_text: str, graph_file: Path) -> None:
    """Execute SPARQL query against an RDF graph (requires rdflib)."""
    try:
        from rdflib import Graph
    except ImportError:
        raise ImportError(
            "rdflib is required to execute SPARQL queries. "
            "Install it with: pip install rdflib"
        )

    g = Graph()
    g.parse(graph_file, format="turtle")
    print(f"# Loaded RDF graph from {graph_file} ({len(g)} triples)\n", file=sys.stderr)

    results = g.query(sparql_text)
    print(results.serialize(format="csv"))


def main() -> None:
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("query_file", type=Path, help="Path to a dist/<indicator>.omop.sparql file")
    parser.add_argument("--start-date", required=True, help="Reporting period start, e.g. 2023-01-01")
    parser.add_argument("--end-date", required=True, help="Reporting period end, e.g. 2024-01-01")
    parser.add_argument(
        "--sssom-file",
        type=Path,
        default=DEFAULT_SSSOM_FILE,
        help="SSSOM crosswalk file (default: our shipped ti-o_to_omop_mapping.tsv)",
    )
    parser.add_argument(
        "--execute",
        type=Path,
        help="Optional: execute query against an RDF graph (Turtle file)",
    )
    args = parser.parse_args()

    sparql_text = args.query_file.read_text()
    result, unresolved = localize_sparql(sparql_text, args.start_date, args.end_date, args.sssom_file)

    if args.execute:
        execute_sparql(result, args.execute)
    else:
        print(result)

    if unresolved:
        unique = sorted(set(unresolved))
        print(
            "\n" + "=" * 70 +
            "\nWARNING: the following ti-o concept(s) could NOT be mapped and were"
            "\nleft as bare ti-o: URIs in the SPARQL above (query is still valid but"
            "\nwill match nothing unless your data itself uses ti-o URIs):\n" +
            "\n".join(f"  - {concept}" for concept in unique) +
            "\n\nAdd a real row (vocabulary_id:code) for each of these to your SSSOM"
            "\nfile (--sssom-file) to get correct results."
            "\n" + "=" * 70,
            file=sys.stderr,
        )


if __name__ == "__main__":
    main()
