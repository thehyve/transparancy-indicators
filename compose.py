#!/usr/bin/env python3
"""
compose.py — MAINTAINER-ONLY tool.

Dependency note: this is the one place in the pipeline that isn't stdlib-only
— it uses PyYAML (`pip install pyyaml`) to read the YAML definition files
below. localize_sql.py (the hospital-facing script) remains stdlib only;
this dependency only affects maintainers running compose.py.

Composes indicators/definitions.yaml + indicators/templates/*.tpl.{sql,sparql} +
diseases/<Disease>/*.{sql,sparql} + blocks/{sql,sparql}/*.{sql,sparql} into
plain, committed query files in dist/ in both SQL (for OMOP CDM) and SPARQL
(for RDF/OWL) formats.

Three separate things are kept apart on purpose:
  - indicators/templates/<kind>.tpl.{sql,sparql} — the query LOGIC for one
    kind of indicator (e.g. "volume"), with ${block_name} placeholders for
    whichever disease-specific CTEs/triple patterns it needs. Both SQL and
    SPARQL versions are disease-agnostic.
  - diseases/<Disease>/<block_name>.{sql,sparql} — one full, hand-written
    CTE/triple pattern per block. Exactly the same style as
    blocks/{sql,sparql}/*.{sql,sparql}, just disease-specific instead of
    shared. Not limited to a single concept or a flat OR — any query a
    maintainer wants to write is used verbatim.
  - indicators/definitions.yaml — wires templates + diseases together into
    named indicators. This is what lets e.g. THP_volume and a future
    BladderCancer_volume both reuse templates/volume.tpl.{sql,sparql} while
    each pointing at their own diseases/<Disease>/ folder.

indicators/definitions.yaml is a list, one entry per indicator to build:
    - name: THP_volume
      template: volume
      disease: THP
    - name: HHM_heroperatie
      template: unplanned_reoperation
      disease: HeadNeckMalignancy
`name` becomes dist/<name>.sql, dist/<name>.sparql, etc.

All substitution uses Python's built-in string.Template ($name / ${name}
syntax). {{ti-o:...}} and {{START_DATE}}/{{END_DATE}} tokens are left
untouched here — they are hospital-specific and get resolved later by
localize_sql.py (or equivalent SPARQL resolver, or by hand-editing).

Writes plain, committed query files to dist/ that WE review before hospitals
ever see them.

Usage (run by maintainers when blocks/templates/definitions/diseases change):
    python compose.py
"""
import logging
import re
import sys
import yaml
from pathlib import Path
from string import Template

ROOT = Path(__file__).parent
BLOCKS_SQL_DIR = ROOT / "blocks" / "sql"
BLOCKS_SPARQL_DIR = ROOT / "blocks" / "sparql"
TEMPLATES_DIR = ROOT / "indicators" / "templates"
DEFINITIONS_FILE = ROOT / "indicators" / "definitions.yaml"
DISEASES_DIR = ROOT / "diseases"
DIST_DIR = ROOT / "dist"

# File extensions for each format
FORMAT_EXTS = {"sql": ".sql", "sparql": ".sparql"}
BLOCKS_DIRS = {"sql": BLOCKS_SQL_DIR, "sparql": BLOCKS_SPARQL_DIR}

log = logging.getLogger("compose")

# ANSI color codes for terminal output (no extra dependencies)
class _Color:
    RESET = "\033[0m"
    BOLD = "\033[1m"
    DIM = "\033[2m"
    CYAN = "\033[36m"
    GREEN = "\033[32m"
    YELLOW = "\033[33m"
    BLUE = "\033[34m"


class _ColoredFormatter(logging.Formatter):
    """Custom formatter that adds ANSI color codes to log output."""

    FORMATS = {
        logging.INFO: f"{_Color.CYAN}%(message)s{_Color.RESET}",
        logging.WARNING: f"{_Color.YELLOW}⚠ %(message)s{_Color.RESET}",
    }

    def format(self, record):
        fmt = self.FORMATS.get(record.levelno, "%(message)s")
        formatter = logging.Formatter(fmt)
        return formatter.format(record)


# matches any leftover ${...} placeholder that safe_substitute couldn't
# resolve (missing block/disease file) — used to warn, not fail, since
# compose.py should stay easy to debug rather than opaquely crash.
UNRESOLVED_PLACEHOLDER = re.compile(r"\$\{(\w+)\}")


def _strip_optional_exclusion(text: str, fmt: str) -> str:
    """Remove exclusion-specific query fragments when no exclusion block exists."""
    # Remove the optional placeholder line from the WITH/parameter section.
    text = re.sub(r"^[ \t]*\$\{exclusie_concepten\},?[ \t]*\n", "", text, flags=re.MULTILINE)

    if fmt == "sql":
        # Remove condition-level exclusion filters that depend on exclusie_concepten.
        text = re.sub(
            r"\n[ \t]*WHERE NOT EXISTS \(\n(?:.*\n)*?[ \t]*INNER JOIN exclusie_concepten ec\n(?:.*\n)*?[ \t]*\)\n",
            "\n",
            text,
        )
        text = re.sub(
            r"\n[ \t]*AND NOT EXISTS \(\n(?:.*\n)*?[ \t]*INNER JOIN exclusie_concepten ec\n(?:.*\n)*?[ \t]*\)\n",
            "\n",
            text,
        )
    else:
        # Remove SPARQL exclusion filter block that depends on exclusie_concepten.
        text = re.sub(
            r"\n[ \t]*FILTER NOT EXISTS \{\n(?:.*\n)*?\$\{exclusie_concepten\}(?:.*\n)*?[ \t]*\}\n",
            "\n",
            text,
        )

    return text



def compose(config: dict, fmt: str) -> str:
    """Compose a single indicator in a specific format (sql or sparql)."""
    ext = FORMAT_EXTS[fmt]
    template_path = TEMPLATES_DIR / f"{config['template']}.tpl{ext}"
    log.info("\ttemplate: %s%s%s", _Color.BLUE, template_path.relative_to(ROOT), _Color.RESET)
    text = template_path.read_text()

    disease_dir = DISEASES_DIR / config["disease"]
    log.info("\tdisease:  %s%s%s", _Color.BLUE, disease_dir.relative_to(ROOT), _Color.RESET)

    blocks_dir = BLOCKS_DIRS[fmt]
    block_files = sorted(blocks_dir.glob(f"*{ext}")) + sorted(disease_dir.glob(f"*{ext}"))
    blocks = {block_file.stem: block_file.read_text() for block_file in block_files}
    block_names = ", ".join(f"${{{_Color.GREEN}{name}{_Color.RESET}}}" for name in blocks) or "(none)"
    log.info("\tblocks:   %s", block_names)

    # safe_substitute: only touches ${block_name}; leaves {{ti-o:...}} /
    # {{START_DATE}} / {{END_DATE}} untouched since they use different syntax.
    result = Template(text).safe_substitute(blocks)

    unresolved = sorted(set(UNRESOLVED_PLACEHOLDER.findall(result)))

    # Some diseases intentionally have no exclusion block. Keep warning,
    # and remove exclusion-specific logic from the composed query.
    if "exclusie_concepten" in unresolved:
        log.warning(
            "optional exclusion placeholder ${exclusie_concepten} is unresolved; "
            "removing exclusion logic from composed output"
        )
        result = _strip_optional_exclusion(result, fmt)
        unresolved.remove("exclusie_concepten")

    if unresolved:
        log.warning(
            "unresolved placeholder(s) left in output: %s "
            "(no matching block/disease file was found)",
            ", ".join(f"${{{name}}}" for name in unresolved),
        )

    return result

def report(definitions) -> None:
    """Print a summary of the current indicator definitions and templates.
    In a readme, there is a table with each row an indicator and each column a disease.
    The cells populate a reference to the template if it exists.
    """

    EXT = "sparql"

    # Extract all the the unique templates and diseases from the definitions
    templates = sorted(set(d["template"] for d in definitions))
    diseases = sorted(set(d["disease"] for d in definitions))

    # Print a summary table as a pretty markdown table
    with open("summary_table.md", "w") as f:

        print("\n# **Summary Table**", file=f)
        print("\nThis table summarizes the current indicator definitions and templates.\n", file=f)
        print("| Indicator | " + " | ".join([f"[{disease}](diseases/{disease})" for disease in diseases]) + " |", file=f)
        print("|----------" + "|".join(["----------"] * len(diseases) + ["----------"]) + "|", file=f)
        for template in templates:
            row = [f"[{template}](indicators/templates/{template}.tpl.{EXT})"]
            for disease in diseases:
                cell = [d["name"] for d in definitions if d["template"] == template and d["disease"] == disease]
                cell = f"[{cell[0]}](dist/{cell[0]}.{EXT})" if cell else ""
                row.append(cell)

            print("| " + " | ".join(row) + " |", file=f)
  
    return

    

def main() -> None:
    # Set up colored logging handler
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(_ColoredFormatter())
    log.addHandler(handler)
    log.setLevel(logging.INFO)

    log.info("%s%sreading definitions from %s%s", _Color.BOLD, _Color.CYAN, DEFINITIONS_FILE.relative_to(ROOT), _Color.RESET)
    definitions = yaml.safe_load(DEFINITIONS_FILE.read_text())
    indicator_names = ", ".join(f"{_Color.GREEN}{d['name']}{_Color.RESET}" for d in definitions)
    log.info("found %d indicator definition(s): %s", len(definitions), indicator_names)
    log.info("output formats: %s\n", ", ".join(_Color.BLUE + fmt + _Color.RESET for fmt in FORMAT_EXTS.keys()))

    DIST_DIR.mkdir(exist_ok=True)
    total_outputs = 0
    for config in definitions:
        log.info("%s%scomposing %s %s", _Color.BOLD, _Color.CYAN, config["name"], _Color.RESET)
        for fmt in FORMAT_EXTS.keys():
            text = compose(config, fmt)
            ext = FORMAT_EXTS[fmt]
            out_path = DIST_DIR / f"{config['name']}{ext}"
            out_path.write_text(text)
            log.info("\twrote %s%s%s\n", _Color.GREEN, out_path.relative_to(ROOT), _Color.RESET)
            total_outputs += 1

    log.info("\n%s%sdone%s — composed %d indicator(s) × %d format(s) = %d output file(s) into %s%s%s", _Color.BOLD, _Color.GREEN, _Color.RESET, len(definitions), len(FORMAT_EXTS), total_outputs, _Color.BLUE, DIST_DIR.relative_to(ROOT), _Color.RESET)

    report(definitions)

if __name__ == "__main__":
    main()



