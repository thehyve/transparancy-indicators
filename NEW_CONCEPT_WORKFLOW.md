# Adding a new clinical concept (example: bladder cancer)

This document walks through the concrete steps to add a new clinical
concept to ti-o and make it usable in the OMOP SQL pipeline
(`compose.py` / `localize_sql.py`).

> **Note on scope:** the OMOP SQL pipeline itself does **not** need the
> OWL ontology at all. `compose.py` and `localize_sql.py` only ever read
> `blocks/sql/*.sql`, `indicators/templates/*.tpl.sql`,
> `indicators/definitions/*.yaml`, `diseases/*.yaml`, and the SSSOM
> crosswalk (`ti-o_to_omop_mapping.tsv`) — they resolve `{{ti-o:...}}`
> tokens purely by string lookup against the SSSOM `subject_id` column.
> Nothing in that pipeline queries or reasons over the `.owl.ttl` file.
>
> The OWL class still matters for other consumers of ti-o: the SPARQL/SHACL
> worked examples (`Voorbeeld */`) rely on RDF instance data being typed as
> a ti-o class (e.g. `a onto:BladderCancer`), and the OWL class is what
> gives a ti-o concept a stable, documented identity (definition, code
> system provenance) independent of any one target platform. So: **required
> for SPARQL/OWL-based indicators and for documentation purposes, not
> required for the OMOP SQL pipeline.**

## Steps

### 1. (Optional but recommended) Add the OWL class

Add a new class to `transparantie_indicatoren.owl.ttl`, following the
existing pattern used for e.g. `:AdenocarcinomaOfPancreas`: subclass of the
appropriate OGMS parent, with a label and a `skos:closeMatch` to the source
terminology.

```turtle
###  https://w3id.org/zinl/ti-o#BladderCancer
:BladderCancer rdf:type owl:Class ;
              rdfs:subClassOf obo:OGMS_0000147 ;
              rdfs:label "Blaaskanker"@nl ,
                         "Bladder cancer"@en ;
              skos:closeMatch <http://snomed.info/id/399326009> .
```

Skip this step if you only need the concept for the OMOP SQL pipeline and
don't plan to build a SPARQL/SHACL worked example for it.

### 2. Add a row to the SSSOM crosswalk

This is the step the OMOP pipeline actually depends on. Add a row to
`ti-o_to_omop_mapping.tsv` mapping the ti-o concept id to a resolvable
OMOP code:

```tsv
subject_id	subject_label	predicate_id	object_id	object_label	object_source	mapping_justification	author_id	comment
ti-o:BladderCancer	Bladder cancer	skos:exactMatch	SNOMED:399326009	Bladder cancer	SNOMED CT	Manual mapping	loesvdb	OMOP standard concept reached via SNOMED source vocabulary in the OMOP concept table
```

`subject_id` (`ti-o:BladderCancer`) is exactly the ti-o concept id you'll
reference in the disease file in the next step.

### 3. Add (or extend) a disease file

Bladder cancer volume is the *same kind* of indicator as THP volume — same
query logic, different concepts — so it reuses the existing generic
`indicators/templates/volume.tpl.sql` template. You don't need a new
template, just a new disease file naming its criteria:

```yaml
# diseases/BladderCancer.yaml
inclusie_criteria:
  - ti-o:BladderCancerResection
exclusie_criteria:
  - ti-o:BladderCancerExclusion
```

Each criterion is a YAML list of ti-o concepts, OR'd together automatically
— no SQL knowledge needed. A disease can name as many criteria as it
actually needs — see `diseases/HeadNeckMalignancy.yaml` for an example with
five (primary malignancy, resection, CIS, other excluded histology,
reoperation), used by a more complex, non-generalized indicator template.

If a criterion needs logic beyond a flat OR (e.g. `AND NOT`), write it as a
single raw SQL string instead of a list — it's used verbatim, still
containing `{{ti-o:...}}` tokens for `localize_sql.py` to resolve:

```yaml
inclusie_criteria: "{{ti-o:BladderCancerResection}} AND NOT {{ti-o:BladderCancerExclusion}}"
```

### 4. Wire the disease into an indicator definition

```yaml
# indicators/definitions/BladderCancer_volume.yaml
template: volume
disease: BladderCancer
tokens:
  inclusie_token: inclusie_criteria
  exclusie_token: exclusie_criteria
```

The `tokens` values (`inclusie_criteria`, `exclusie_criteria`) are keys into
the disease file, not `{{ti-o:...}}` tokens directly — `compose.py` resolves
them (OR-ing list items together, or using a raw string as-is) and
substitutes the result into the template.

(You'd only need a new `indicators/templates/<kind>.tpl.sql` if the new
indicator has genuinely different query logic, not just different concepts
— see the "Adding a new indicator" section in
[README_maintainers.md](README_maintainers.md) for that case.)

### 5. Build and verify

```bash
python3 compose.py
python3 localize_sql.py dist/<name>.omop.sql \
    --start-date 2023-01-01 --end-date 2024-01-01
```

Check that `{{ti-o:BladderCancer}}` resolved to the expected
`vocabulary_id`/`concept_code` WHERE fragment.

### 5. (Optional) Build out the full worked example

To match the depth of the existing `Voorbeeld volume`/`Voorbeeld Wachttijd`
examples, also add:
- example RDF data (`*_example_data.ttl`) with instances typed
  `a onto:BladderCancer`,
- SHACL shapes (`*_shapes.ttl`) constraining that data,
- a SPARQL query variant.

This is independent of the OMOP pipeline and only needed if you want a
type-based/SPARQL demonstrator for the new indicator too.
