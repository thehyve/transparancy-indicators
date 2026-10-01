# HOWTO SPARQL Structural Mapping

Use this when a hospital graph does not use the same predicates/classes as the canonical ti-o SPARQL templates.

## Why two mapping layers?

- Concept mapping (SSSOM): ti-o concepts -> local concepts/codes.
- Structural mapping (YAML): canonical predicates/classes -> local graph structure.

Example:
- Canonical: `obo:RO_0000057`
- Local graph: `zkh:participant`

## Files

- Template: [mappings/sparql_structural_translation.template.yaml](mappings/sparql_structural_translation.template.yaml)
- Example: [mappings/sparql_structural_translation.example.yaml](mappings/sparql_structural_translation.example.yaml)
- Rewriter: [localize_sparql_structure.py](localize_sparql_structure.py)

## Workflow

1. Compose canonical query (maintainer step).
2. Apply concept/date localization with [localize_sparql.py](localize_sparql.py).
3. Apply structural localization with [localize_sparql_structure.py](localize_sparql_structure.py).
4. Execute localized query against hospital RDF graph.

## Example command

```bash
python localize_sparql.py dist/THP_volume.sparql \
  --start-date 2023-01-01 --end-date 2024-01-01 \
  --sssom-file ti-o_to_aandoening_mapping.tsv \
  > /tmp/THP_volume.concepts.sparql

python localize_sparql_structure.py /tmp/THP_volume.concepts.sparql \
  --structural-file mappings/sparql_structural_translation.example.yaml \
  > /tmp/THP_volume.localized.sparql
```

## Notes

- The structural script does text-based CURIE replacement.
- Keep canonical query logic unchanged; only map concepts/structure.
- If needed, include path mappings (for example time path -> one local predicate).
