#!/usr/bin/env python3
"""
localize_sparql_structure.py

Apply structural mappings to a canonical SPARQL query.

This complements localize_sparql.py:
  - localize_sparql.py handles concept/date localization
  - localize_sparql_structure.py handles structural predicate/class localization

Requires PyYAML.

Usage:
  python localize_sparql_structure.py \
      indicators/templates/volume.tpl.sparql \
      --structural-file mappings/sparql_structural_translation.example.yaml
"""

from __future__ import annotations

import argparse
import re
from pathlib import Path

import yaml


PREFIX_LINE_RE = re.compile(r"^PREFIX\s+(\w+):\s*<([^>]+)>", flags=re.IGNORECASE | re.MULTILINE)


def load_structural_profile(path: Path) -> dict:
    profile = yaml.safe_load(path.read_text())
    if not isinstance(profile, dict):
        raise ValueError("Structural profile must be a YAML mapping")
    return profile


def extract_existing_prefixes(query_text: str) -> set[str]:
    return {m.group(1) for m in PREFIX_LINE_RE.finditer(query_text)}


def insert_missing_prefixes(query_text: str, prefixes: dict[str, str]) -> str:
    if not prefixes:
        return query_text

    existing = extract_existing_prefixes(query_text)
    missing_lines: list[str] = []
    for prefix, iri in prefixes.items():
        if prefix not in existing:
            missing_lines.append(f"PREFIX {prefix}: <{iri}>")

    if not missing_lines:
        return query_text

    all_lines = query_text.splitlines()
    insert_at = 0
    for i, line in enumerate(all_lines):
        if line.strip().upper().startswith("PREFIX "):
            insert_at = i + 1
        else:
            if insert_at > 0:
                break

    new_lines = all_lines[:insert_at] + missing_lines + all_lines[insert_at:]
    return "\n".join(new_lines) + ("\n" if query_text.endswith("\n") else "")


def replace_terms(query_text: str, mapping: dict[str, str]) -> str:
    if not mapping:
        return query_text

    # Replace longer keys first to avoid partial collisions.
    for source in sorted(mapping.keys(), key=len, reverse=True):
        target = mapping[source]
        query_text = query_text.replace(source, target)
    return query_text


def apply_structural_mapping(query_text: str, profile: dict) -> str:
    prefixes = profile.get("prefixes", {}) or {}
    mappings = profile.get("mappings", {}) or {}
    predicate_map = mappings.get("predicates", {}) or {}
    class_map = mappings.get("classes", {}) or {}

    if not isinstance(prefixes, dict):
        raise ValueError("prefixes must be a YAML mapping")
    if not isinstance(predicate_map, dict):
        raise ValueError("mappings.predicates must be a YAML mapping")
    if not isinstance(class_map, dict):
        raise ValueError("mappings.classes must be a YAML mapping")

    result = insert_missing_prefixes(query_text, prefixes)
    result = replace_terms(result, predicate_map)
    result = replace_terms(result, class_map)
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("query_file", type=Path, help="Canonical SPARQL query file")
    parser.add_argument("--structural-file", type=Path, required=True, help="YAML structural mapping profile")
    args = parser.parse_args()

    query_text = args.query_file.read_text()
    profile = load_structural_profile(args.structural_file)
    localized = apply_structural_mapping(query_text, profile)
    print(localized)


if __name__ == "__main__":
    main()
