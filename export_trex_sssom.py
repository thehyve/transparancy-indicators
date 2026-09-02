#!/usr/bin/env python3
"""Incrementally export TREX concept mappings to SSSOM TSV files.

The script queries:
  https://trex.dhd.nl/api/concept/<ID>?date=<YYYY-MM-DD>

It starts at a configurable ID (default 0), walks upward, and stops after:
    - an optional hard stop ID (`--max-id`), or
    - a configurable number of consecutive missing IDs after at least one valid
        concept (`--stop-after-consecutive-misses`).

Outputs are 5 SSSOM-style TSV files:
  - dhd_to_snomed.sssom.tsv
  - dhd_to_dbc.sssom.tsv
  - dhd_to_icd10.sssom.tsv
  - dhd_to_za.sssom.tsv
  - dhd_to_cbv_migratie.sssom.tsv

Mappings with an `endDate` before the selected `--date` are excluded.
"""

from __future__ import annotations

import argparse
import csv
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Set, Tuple


BASE_URL = "https://trex.dhd.nl/api/concept/{concept_id}?date={date}"
PREDICATE_ID = "skos:exactMatch"
DEFAULT_USER_AGENT = "curl/8.0.0"
DEFAULT_STATE_FILENAME = ".trex_processed_ids.tsv"
STATE_HEADER = [
    "subject_id",
    "active",
    "has_snomed",
    "has_dbc",
    "has_icd10",
    "has_za",
    "has_cbv",
]
HEADER = [
    "subject_id",
    "subject_label",
    "predicate_id",
    "object_id",
    "object_label",
    "object_source",
    "mapping_justification",
    "author_id",
    "comment",
]


@dataclass
class OutputTable:
    filename: str
    object_prefix: str
    object_source: str
    rows: List[List[str]] = field(default_factory=list)
    row_keys: Set[Tuple[str, ...]] = field(default_factory=set)


@dataclass
class ProcessedState:
    subject_id: str
    active: str = "unknown"
    has_snomed: str = "unknown"
    has_dbc: str = "unknown"
    has_icd10: str = "unknown"
    has_za: str = "unknown"
    has_cbv: str = "unknown"


OUTPUTS: Dict[str, OutputTable] = {
    "snomed": OutputTable(
        filename="dhd_to_snomed.sssom.tsv",
        object_prefix="SNOMED",
        object_source="SNOMED CT",
    ),
    "dbc": OutputTable(
        filename="dhd_to_dbc.sssom.tsv",
        object_prefix="DBC",
        object_source="DBC",
    ),
    "icd-10": OutputTable(
        filename="dhd_to_icd10.sssom.tsv",
        object_prefix="ICD10",
        object_source="ICD-10",
    ),
    "za": OutputTable(
        filename="dhd_to_za.sssom.tsv",
        object_prefix="ZA",
        object_source="Zorgactiviteit",
    ),
    "cbv": OutputTable(
        filename="dhd_to_cbv_migratie.sssom.tsv",
        object_prefix="CBV",
        object_source="CBV migratie",
    ),
}


def normalize_code_system(name: str) -> str:
    return name.strip().lower()


def as_dhd_curie(concept_id: int) -> str:
    return f"DHD:{concept_id:010d}"


def fetch_concept(
    concept_id: int, date: str, timeout: float, user_agent: str, debug: bool
) -> Optional[dict]:
    url = BASE_URL.format(concept_id=concept_id, date=urllib.parse.quote(date))
    request = urllib.request.Request(
        url,
        headers={
            "Accept": "application/json",
            "User-Agent": user_agent,
        },
    )
    try:
        with urllib.request.urlopen(request, timeout=timeout) as response:
            if response.status != 200:
                return None
            payload = response.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        if debug:
            print(f"HTTP {exc.code} for concept ID {concept_id}")
        return None
    except urllib.error.URLError as exc:
        raise RuntimeError(f"Network error while fetching {url}: {exc}") from exc

    try:
        data = json.loads(payload)
    except json.JSONDecodeError:
        return None

    if not isinstance(data, dict) or "id" not in data:
        return None
    return data


def add_row(
    table: OutputTable,
    subject_id: str,
    subject_label: str,
    object_code: str,
    object_label: str,
    comment: str,
) -> None:
    row = [
        subject_id,
        subject_label,
        PREDICATE_ID,
        f"{table.object_prefix}:{object_code}",
        object_label,
        table.object_source,
        "Automated mapping extraction",
        "copilot",
        comment,
    ]
    row_key = tuple(row)
    if row_key in table.row_keys:
        return
    table.rows.append(row)
    table.row_keys.add(row_key)


def load_existing_sssom_rows(path: Path) -> tuple[List[List[str]], Set[str]]:
    if not path.exists():
        return [], set()

    with path.open("r", encoding="utf-8") as handle:
        data_lines = [line for line in handle if line.strip() and not line.startswith("#")]

    if not data_lines:
        return [], set()

    reader = csv.reader(data_lines, delimiter="\t")
    header = next(reader, None)
    if header is None:
        return [], set()

    try:
        subject_idx = header.index("subject_id")
    except ValueError:
        subject_idx = 0

    rows: List[List[str]] = []
    subject_ids: Set[str] = set()
    for row in reader:
        if not row:
            continue
        rows.append(row)
        if len(row) > subject_idx and row[subject_idx].strip():
            subject_ids.add(row[subject_idx].strip())
    return rows, subject_ids


def load_processed_ids(path: Path) -> Set[str]:
    if not path.exists():
        return set()
    with path.open("r", encoding="utf-8") as handle:
        return {line.strip() for line in handle if line.strip()}


def write_processed_ids(path: Path, processed_ids: Set[str]) -> None:
    raise RuntimeError("write_processed_ids is deprecated; use write_processed_state")


def bool_to_yes_no(value: bool) -> str:
    return "yes" if value else "no"


def parse_api_date(value: object) -> Optional[dt.date]:
    if not value:
        return None
    text = str(value).strip()
    if len(text) < 10:
        return None
    try:
        return dt.date.fromisoformat(text[:10])
    except ValueError:
        return None


def is_outdated_by_end_date(end_date: object, as_of: dt.date) -> bool:
    parsed = parse_api_date(end_date)
    return bool(parsed and parsed < as_of)


def state_is_complete(st: ProcessedState) -> bool:
    return all(
        value in {"yes", "no"}
        for value in [
            st.active,
            st.has_snomed,
            st.has_dbc,
            st.has_icd10,
            st.has_za,
            st.has_cbv,
        ]
    )


def load_processed_state(path: Path) -> Dict[str, ProcessedState]:
    if not path.exists():
        return {}

    with path.open("r", encoding="utf-8") as handle:
        lines = [line.rstrip("\n") for line in handle if line.strip()]

    if not lines:
        return {}

    # Backward compatibility: legacy plain list with one subject_id per line.
    if "\t" not in lines[0] and lines[0].startswith("DHD:"):
        return {
            subject_id: ProcessedState(subject_id=subject_id)
            for subject_id in lines
            if subject_id.startswith("DHD:")
        }

    reader = csv.reader(lines, delimiter="\t")
    header = next(reader, None)
    if header is None:
        return {}

    idx = {name: pos for pos, name in enumerate(header)}
    states: Dict[str, ProcessedState] = {}
    for row in reader:
        if not row:
            continue
        subject_id = row[idx.get("subject_id", 0)].strip()
        if not subject_id:
            continue
        states[subject_id] = ProcessedState(
            subject_id=subject_id,
            active=row[idx["active"]].strip() if "active" in idx and len(row) > idx["active"] else "unknown",
            has_snomed=row[idx["has_snomed"]].strip()
            if "has_snomed" in idx and len(row) > idx["has_snomed"]
            else "unknown",
            has_dbc=row[idx["has_dbc"]].strip() if "has_dbc" in idx and len(row) > idx["has_dbc"] else "unknown",
            has_icd10=row[idx["has_icd10"]].strip()
            if "has_icd10" in idx and len(row) > idx["has_icd10"]
            else "unknown",
            has_za=row[idx["has_za"]].strip() if "has_za" in idx and len(row) > idx["has_za"] else "unknown",
            has_cbv=row[idx["has_cbv"]].strip() if "has_cbv" in idx and len(row) > idx["has_cbv"] else "unknown",
        )
    return states


def write_processed_state(path: Path, states: Dict[str, ProcessedState]) -> None:
    tmp_path = path.with_name(path.name + ".tmp")
    with tmp_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(STATE_HEADER)
        for subject_id in sorted(states):
            st = states[subject_id]
            writer.writerow(
                [
                    st.subject_id,
                    st.active,
                    st.has_snomed,
                    st.has_dbc,
                    st.has_icd10,
                    st.has_za,
                    st.has_cbv,
                ]
            )
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def iter_derivation_items(concept: dict) -> Iterable[tuple[str, dict]]:
    for derivation in concept.get("derivations", []):
        code_system = normalize_code_system(str(derivation.get("codeSystem", "")))
        for item in derivation.get("items", []):
            if isinstance(item, dict):
                yield code_system, item


def concept_flags(concept: dict, as_of: dt.date) -> Tuple[str, str, str, str, str, str]:
    has_snomed = False
    has_dbc = False
    has_icd10 = False
    has_za = False
    has_cbv = False

    snomed = concept.get("snomed") or {}
    snomed_id = str(snomed.get("id", "")).strip()
    if snomed_id and snomed_id != "0" and not is_outdated_by_end_date(concept.get("endDate"), as_of):
        has_snomed = True

    for code_system, item in iter_derivation_items(concept):
        code = str(item.get("code", "")).strip()
        if not code:
            continue
        if is_outdated_by_end_date(item.get("endDate"), as_of):
            continue
        if code_system == "dbc":
            has_dbc = True
        elif code_system == "icd-10":
            has_icd10 = True
        elif code_system == "za":
            has_za = True
        elif code_system == "cbv":
            has_cbv = True

    active = bool_to_yes_no(bool(concept.get("active", False)))
    return (
        active,
        bool_to_yes_no(has_snomed),
        bool_to_yes_no(has_dbc),
        bool_to_yes_no(has_icd10),
        bool_to_yes_no(has_za),
        bool_to_yes_no(has_cbv),
    )


def extract_rows(concept: dict, as_of: dt.date) -> None:
    concept_id = int(concept["id"])
    subject_id = as_dhd_curie(concept_id)
    subject_label = str(concept.get("description", "")).strip()

    snomed = concept.get("snomed") or {}
    snomed_id = str(snomed.get("id", "")).strip()
    snomed_label = str(snomed.get("description", "")).strip()
    if snomed_id and snomed_id != "0" and not is_outdated_by_end_date(concept.get("endDate"), as_of):
        add_row(
            OUTPUTS["snomed"],
            subject_id,
            subject_label,
            snomed_id,
            snomed_label,
            "Source: concept.snomed",
        )

    for code_system, item in iter_derivation_items(concept):
        code = str(item.get("code", "")).strip()
        label = str(item.get("description", "")).strip()
        if not code:
            continue
        if is_outdated_by_end_date(item.get("endDate"), as_of):
            continue

        comment_bits = [f"Source derivation={code_system}"]
        if "declaredSpecialism" in item:
            comment_bits.append(f"declaredSpecialism={item.get('declaredSpecialism', '')}")
        if "registeredSpecialism" in item:
            comment_bits.append(
                f"registeredSpecialism={item.get('registeredSpecialism', '')}"
            )
        if "source" in item and item.get("source"):
            comment_bits.append(f"source={item.get('source')}")
        comment = "; ".join(comment_bits)

        if code_system == "dbc":
            add_row(OUTPUTS["dbc"], subject_id, subject_label, code, label, comment)
        elif code_system == "icd-10":
            add_row(OUTPUTS["icd-10"], subject_id, subject_label, code, label, comment)
        elif code_system == "za":
            add_row(OUTPUTS["za"], subject_id, subject_label, code, label, comment)
        elif code_system == "cbv":
            add_row(
                OUTPUTS["cbv"],
                subject_id,
                subject_label,
                code,
                label,
                comment,
            )


def write_sssom(path: Path, rows: List[List[str]], mapping_set_id: str, date: str) -> None:
    tmp_path = path.with_name(path.name + ".tmp")
    with tmp_path.open("w", newline="", encoding="utf-8") as handle:
        handle.write("#curie_map:\n")
        handle.write("#  skos:    http://www.w3.org/2004/02/skos/core#\n")
        handle.write("#  DHD:     https://trex.dhd.nl/api/concept/\n")
        handle.write("#mapping_set_id: " + mapping_set_id + "\n")
        handle.write("#mapping_set_description: Automatically extracted from TREX concept API.\n")
        handle.write("#license: https://creativecommons.org/licenses/by/4.0/\n")
        handle.write("#mapping_date: " + date + "\n")
        handle.write("#creator_label:\n")
        handle.write("#  - \"GitHub Copilot\"\n")

        writer = csv.writer(handle, delimiter="\t", lineterminator="\n")
        writer.writerow(HEADER)
        writer.writerows(rows)
        handle.flush()
        os.fsync(handle.fileno())
    os.replace(tmp_path, path)


def persist_outputs_and_state(
    out_dir: Path,
    mapping_date: str,
    processed_state: Dict[str, ProcessedState],
    state_path: Path,
) -> List[str]:
    generated: List[str] = []
    for table in OUTPUTS.values():
        mapping_set_id = f"https://w3id.org/zinl/ti-o#{table.filename}"
        output_path = out_dir / table.filename
        write_sssom(output_path, table.rows, mapping_set_id, mapping_date)
        generated.append(f"{table.filename}: {len(table.rows)} rows")

    write_processed_state(state_path, processed_state)
    return generated


def parse_args(argv: List[str]) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--date", default=dt.date.today().isoformat(), help="Query date (YYYY-MM-DD)")
    parser.add_argument("--start-id", type=int, default=0, help="Start concept ID")
    parser.add_argument(
        "--output-dir",
        default=".",
        help="Directory where SSSOM TSV files will be written",
    )
    parser.add_argument(
        "--timeout",
        type=float,
        default=20.0,
        help="HTTP timeout in seconds",
    )
    parser.add_argument(
        "--max-id",
        type=int,
        default=None,
        help="Optional hard stop for concept ID",
    )
    parser.add_argument(
        "--progress-every",
        type=int,
        default=250,
        help="Progress interval used only with --verbose",
    )
    parser.add_argument(
        "--stop-after-consecutive-misses",
        type=int,
        default=10000,
        help=(
            "Stop only after this many consecutive missing IDs once at least one valid "
            "concept has been seen; set 0 to disable"
        ),
    )
    parser.add_argument(
        "--user-agent",
        default=DEFAULT_USER_AGENT,
        help="User-Agent header to send (default mimics curl)",
    )
    parser.add_argument(
        "--debug-http",
        action="store_true",
        help="Print non-200 HTTP status codes while probing IDs",
    )
    parser.add_argument(
        "--state-file",
        default=None,
        help=(
            "Optional path for processed-id state file (default: <output-dir>/"
            + DEFAULT_STATE_FILENAME
            + ")"
        ),
    )
    parser.add_argument(
        "--log-per-id",
        action="store_true",
        help=(
            "Print one line per ID with status: existing (skip), fetched-found, or fetched-missing"
        ),
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable periodic progress logs (Probing IDs / Processed through)",
    )
    parser.add_argument(
        "--write-per-id",
        action="store_true",
        help="Persist SSSOM output files and state after each fetched concept",
    )
    return parser.parse_args(argv)


def main(argv: List[str]) -> int:
    args = parse_args(argv)
    out_dir = Path(args.output_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    state_path = Path(args.state_file) if args.state_file else (out_dir / DEFAULT_STATE_FILENAME)
    as_of = dt.date.fromisoformat(args.date)

    processed_state: Dict[str, ProcessedState] = load_processed_state(state_path)
    processed_subject_ids: Set[str] = set(processed_state)
    existing_rows_total = 0
    for table in OUTPUTS.values():
        output_path = out_dir / table.filename
        existing_rows, existing_subject_ids = load_existing_sssom_rows(output_path)
        table.rows = existing_rows
        table.row_keys = {tuple(row) for row in existing_rows}
        existing_rows_total += len(existing_rows)
        for subject_id in existing_subject_ids:
            if subject_id not in processed_state:
                processed_state[subject_id] = ProcessedState(subject_id=subject_id)
            if table.object_prefix == "SNOMED":
                processed_state[subject_id].has_snomed = "yes"
            elif table.object_prefix == "DBC":
                processed_state[subject_id].has_dbc = "yes"
            elif table.object_prefix == "ICD10":
                processed_state[subject_id].has_icd10 = "yes"
            elif table.object_prefix == "ZA":
                processed_state[subject_id].has_za = "yes"
            elif table.object_prefix == "CBV":
                processed_state[subject_id].has_cbv = "yes"
            processed_subject_ids.add(subject_id)

    current_id = args.start_id
    seen_any_valid = False
    concepts_seen = 0
    skipped_ids = 0
    skipped_existing_ids = 0
    fetched_existing_for_state = 0
    consecutive_missing = 0

    if args.write_per_id:
        persist_outputs_and_state(out_dir, args.date, processed_state, state_path)

    interrupted = False
    try:
        while True:
            if args.max_id is not None and current_id > args.max_id:
                break

            subject_id = as_dhd_curie(current_id)
            existing_state = processed_state.get(subject_id)
            if subject_id in processed_subject_ids and existing_state and state_is_complete(existing_state):
                skipped_existing_ids += 1
                if args.log_per_id:
                    print(f"ID {current_id}: existing -> skipped API call")
                current_id += 1
                if (
                    args.verbose
                    and args.progress_every > 0
                    and current_id % args.progress_every == 0
                ):
                    print(
                        f"Probing IDs... now at {current_id}; "
                        f"valid={concepts_seen}, skipped_missing={skipped_ids}, "
                        f"skipped_existing={skipped_existing_ids}"
                    )
                continue

            if subject_id in processed_subject_ids and args.log_per_id:
                print(f"ID {current_id}: existing with unknown state -> fetching from API")

            concept = fetch_concept(
                current_id,
                args.date,
                args.timeout,
                args.user_agent,
                args.debug_http,
            )

            if concept is None:
                skipped_ids += 1
                consecutive_missing += 1
                if args.log_per_id:
                    print(f"ID {current_id}: fetched from API -> missing")
                if (
                    seen_any_valid
                    and args.stop_after_consecutive_misses > 0
                    and consecutive_missing >= args.stop_after_consecutive_misses
                ):
                    print(
                        "Stopping at ID "
                        f"{current_id}: reached {consecutive_missing} consecutive missing IDs."
                    )
                    break
                current_id += 1
                if (
                    args.verbose
                    and args.progress_every > 0
                    and current_id % args.progress_every == 0
                ):
                    if seen_any_valid:
                        print(
                            f"Probing IDs... now at {current_id}; "
                            f"valid={concepts_seen}, skipped={skipped_ids}, "
                            f"current_missing_run={consecutive_missing}"
                        )
                    else:
                        print(f"Probing IDs... now at {current_id} (no valid concepts yet)")
                continue

            seen_any_valid = True
            if subject_id in processed_subject_ids:
                fetched_existing_for_state += 1
            concepts_seen += 1
            consecutive_missing = 0
            extract_rows(concept, as_of)
            processed_subject_ids.add(subject_id)
            (
                active,
                has_snomed,
                has_dbc,
                has_icd10,
                has_za,
                has_cbv,
            ) = concept_flags(concept, as_of)
            processed_state[subject_id] = ProcessedState(
                subject_id=subject_id,
                active=active,
                has_snomed=has_snomed,
                has_dbc=has_dbc,
                has_icd10=has_icd10,
                has_za=has_za,
                has_cbv=has_cbv,
            )
            if args.log_per_id:
                print(f"ID {current_id}: fetched from API -> found")

            if args.write_per_id:
                persist_outputs_and_state(out_dir, args.date, processed_state, state_path)

            current_id += 1
            if args.verbose and args.progress_every > 0 and current_id % args.progress_every == 0:
                print(f"Processed through ID {current_id - 1}; valid concepts: {concepts_seen}")
    except KeyboardInterrupt:
        interrupted = True
        print("Interrupted by user; writing partial results...")

    generated: List[str] = persist_outputs_and_state(out_dir, args.date, processed_state, state_path)

    # Ensure all seen subject IDs have no/unknown defaults for missing flags.
    for subject_id in processed_subject_ids:
        if subject_id not in processed_state:
            processed_state[subject_id] = ProcessedState(subject_id=subject_id)
        st = processed_state[subject_id]
        if st.has_snomed == "unknown":
            st.has_snomed = "no"
        if st.has_dbc == "unknown":
            st.has_dbc = "no"
        if st.has_icd10 == "unknown":
            st.has_icd10 = "no"
        if st.has_za == "unknown":
            st.has_za = "no"
        if st.has_cbv == "unknown":
            st.has_cbv = "no"

    print("Done. Generated files:")
    for line in generated:
        print(f"  - {line}")

    probed_ids = max(0, current_id - args.start_id)
    print("Run statistics:")
    print(f"  - start_id: {args.start_id}")
    if args.max_id is not None:
        print(f"  - max_id: {args.max_id}")
    print(f"  - probed_ids: {probed_ids}")
    print(f"  - existing_rows_loaded: {existing_rows_total}")
    print(f"  - valid_concepts: {concepts_seen}")
    print(f"  - skipped_missing_ids: {skipped_ids}")
    print(f"  - skipped_existing_ids: {skipped_existing_ids}")
    print(f"  - fetched_existing_for_state: {fetched_existing_for_state}")
    print(f"  - state_file: {state_path}")
    print(f"  - state_entries: {len(processed_state)}")

    if concepts_seen == 0:
        print(
            "Warning: no valid concepts were found. Consider setting --start-id to the first known valid ID."
        )

    if interrupted:
        print("Partial results were saved before exit.")

    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
