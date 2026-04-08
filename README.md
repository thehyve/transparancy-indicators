# Transparantie-indicatoren – Semantisch model (PoC)

> **Proof of concept** voor het uitdrukken van ZINL-transparantie-indicatoren als Linked Data, met behulp van een gedeelde OWL-ontologie, SHACL-validatieshapes en SPARQL-queries.

---

## Inhoud

```
transparancy-indicators/
├── transparantie_indicatoren.owl.ttl   # Kernontologie (OWL/Turtle)
├── Voorbeeld volume/
│   ├── THP_shapes.ttl              # SHACL-shapes voor Totale Heup Procedure
│   ├── THP_example_data.ttl        # Voorbeelddata (3 patiënten, incl. exclusiegeval)
│   └── THP_volume_2023.sparql      # SPARQL-query: volumetelling per locatie
├── Voorbeeld PROM/
│   ├── indicator_4c_data_leesbaar.ttl   # Voorbeelddata indicator 4c (EQ-5D heup)
│   ├── indicator_4c_leesbaar.sparql     # SPARQL-query: verschilscore EQ-5D
│   ├── PROM ontologie en data.drawio    # Diagram (bewerkbaar)
│   └── PROM ontologie en data.png       # Diagram (afbeelding)
└── Voorbeeld Mortaliteit/
    ├── birth_death_shapes.ttl           # SHACL-shapes voor geboortemoment en overlijdensmoment
    ├── birth_death_example_data.ttl     # Voorbeelddata (2 patiënten: met en zonder overlijdensdatum)
    └── geboorte_overlijden ontologie en data.png  # Diagram (afbeelding)
```

---

## Achtergrond

Zorginstituut Nederland (ZINL) publiceert transparantie-indicatoren die zorgaanbieders rapporteren als kwaliteitsmaat. Dit project verkent of die indicatoren machine-leesbaar en interoperabel gemaakt kunnen worden via:

- een gedeelde **domeinontologie** gebaseerd op bewezen OBO-standaarden (BFO, OGMS, IAO, RO),
- **SHACL-shapes** om te valideren of zorgdata aan de definitie van een indicator voldoet,
- **SPARQL-queries** om de teller en noemer van een indicator te berekenen.

Het doel is dat ziekenhuissystemen data in een afgesproken semantisch formaat aanleveren, waarna de indicatorberekening volledig automatisch en transparant kan verlopen.

---

## Ontologie

De kernontologie (`transparantie_indicatoren.owl.ttl`) heeft namespace `https://w3id.org/zinl/ti-o#` en importeert:

| Ontologie | Doel |
|-----------|------|
| [BFO](http://purl.obolibrary.org/obo/bfo.owl) | Bovenliggende categorieën (processen, continuanten, tijdsperioden) |
| [OGMS](http://purl.obolibrary.org/obo/ogms.owl) | Klinische begrippen (ziekte, aandoening, disorder) |
| [IAO](http://purl.obolibrary.org/obo/iao.owl) | Informatie-entiteiten, identifiers (CRID) |
| [RO](http://purl.obolibrary.org/obo/ro.owl) | Relaties (has participant, inheres in, …) |
| [W3C Time](https://www.w3.org/TR/owl-time/) | Temporele modellering |

Codesystemen (SNOMED CT, ICD-10, Zorgactiviteitcodes) worden gerepresenteerd als named individuals van het type `ti-o:CodeSystem`. Codes zelf zijn `IAO:CRID`-instances die via `IAO:denotes` gekoppeld zijn aan de klinische entiteit.

Toevoegingen voor het mortaliteitspatroon:

| Klasse / Property | Type | Beschrijving |
|-------------------|------|-------------|
| `:BirthInstant` | `owl:Class` | Temporeel moment van geboorte; subklasse van `BFO:zero-dimensional temporal region` |
| `:BirthProcess` | `owl:Class` | Biologisch geboorteproces; eindigt op het `BirthInstant` |
| `:DeathInstant` | `owl:Class` | Temporeel moment van overlijden; subklasse van `BFO:zero-dimensional temporal region` |
| `:hasBirthDate` | `owl:ObjectProperty` | Koppelt een menselijk organisme aan zijn `BirthInstant` |
| `:hasDeathDate` | `owl:ObjectProperty` | Koppelt een menselijk organisme aan zijn `DeathInstant` (optioneel) |

---

## Voorbeelden

### 1 · Volume-indicator – Totale Heupprothese (THP)

**Wat wordt gemeten:** het aantal primaire totale heupprothese-ingrepen per zorglocatie in een rapportagejaar, exclusief ingrepen bij patiënten met een heupfractuur.

| Bestand | Beschrijving |
|---------|-------------|
| `THP_shapes.ttl` | SHACL-shapes die afdwingen dat elke THP-procedure gekoppeld is aan een patiënt, prothese, aandoening (SNOMED CT), tijdsinterval en zorglocatie |
| `THP_example_data.ttl` | Drie voorbeeldpatiënten: coxartrose (inclusie), avasculaire necrose (inclusie), heupfractuur (exclusie) |
| `THP_volume_2023.sparql` | Telt `DISTINCT` procedures per locatie voor 2023; filtert op ZA-code en sluit heupfractuur-SNOMED-codes uit via `FILTER NOT EXISTS` |

De query is parameteriseerbaar via `VALUES`-blokken: vervang de ZA-code en exclusiecodes om de query voor een andere indicator te hergebruiken.

### 2 · PROM-indicator 4c – EQ-5D verschilscore heup (3 maanden postoperatief)

**Wat wordt gemeten:** de gemiddelde verandering in EQ-5D indexscore tussen de preoperatieve en de 3-maands postoperatieve meting, bij patiënten met coxartrose (ICD-10 M16) die een primaire totale heupprothese (ZA 035461) hebben ondergaan.

| Bestand | Beschrijving |
|---------|-------------|
| `indicator_4c_data_leesbaar.ttl` | Twee patiënten: patiënt A heeft zowel pre- als postoperatieve meting (telt mee); patiënt B heeft alleen een preoperatieve meting (valt uit) |
| `indicator_4c_leesbaar.sparql` | Selecteert patiënten met complete PROM-cyclus en berekent `?score_post - ?score_pre`; temporele filters: ≤ 30 dagen voor OK, 60–120 dagen na OK |

> **Let op:** de tijdrekenkundige expressies (`xsd:duration`-arithmetic) worden ondersteund door productie-triplestores (Apache Jena Fuseki, GraphDB, Virtuoso) maar niet door `rdflib`.

### 3 · Mortaliteit – geboortemoment en overlijdensmoment

**Wat wordt gemodelleerd:** hoe geboorte- en overlijdensdata van een patiënt semantisch correct worden vastgelegd, rekening houdend met variabele kalendernauwkeurigheid (datum, tijdstip, of alleen een jaar).

De ontologie introduceert twee nieuwe klassen (`BirthInstant`, `DeathInstant`) als subklassen van `BFO:zero-dimensional temporal region`, en twee bijbehorende properties (`hasBirthDate`, `hasDeathDate`). Door `time:inXSDDate`, `time:inXSDDateTime` of `time:inXSDgYear` te gebruiken is de granulariteit van de datumwaarde flexibel.

| Bestand | Beschrijving |
|---------|-------------|
| `birth_death_shapes.ttl` | SHACL-shapes: elk menselijk organisme (`NCBITAXON:9606`) moet precies één `BirthInstant` hebben en mag maximaal één `DeathInstant` hebben; elk moment moet één kalenderwaarde dragen |
| `birth_death_example_data.ttl` | Twee patiënten: Maria de Vries (geboortedatum én overlijdensdatum bekend) en Jan Bakker (alleen geboortedatum – nog in leven of overlijden niet geregistreerd) |

> **Ontwerpkeuze:** `BirthInstant` en `DeathInstant` zijn bewust *niet* gelijkgesteld aan `time:Instant`, zodat de ontologie geen commitment maakt aan de relatie tussen BFO en W3C Time. Een bridge-axioma kan beide gelijkstellen indien gewenst.

---

## Gebruik

### Vereisten

- Een SPARQL 1.1-compatibele triplestore (bijv. [Apache Jena Fuseki](https://jena.apache.org/documentation/fuseki2/), [GraphDB](https://graphdb.ontotext.com/), of [Oxigraph](https://github.com/oxigraph/oxigraph))
- Voor SHACL-validatie: [pySHACL](https://github.com/RDFLib/pySHACL) of een triplestore met ingebouwde SHACL-engine

### SHACL-validatie uitvoeren (voorbeeld met pySHACL)

```bash
pip install pyshacl

pyshacl \
  -i rdfs \
  -im \
  -s "Voorbeeld volume/THP_shapes.ttl" \
  -d "Voorbeeld volume/THP_example_data.ttl" \
  --ont-graph transparantie_indicatoren.owl \
  -f table

```

### SPARQL-query uitvoeren (voorbeeld met Fuseki)

```bash
# Laad data in Fuseki (na opstarten met ./fuseki-server --mem /ds)
curl -X POST http://localhost:3030/ds/data \
  --data-binary @"Voorbeeld volume/THP_example_data.ttl" \
  -H "Content-Type: text/turtle"

# Voer query uit
curl -X POST http://localhost:3030/ds/query \
  --data-urlencode query@"Voorbeeld volume/THP_volume_2023.sparql" \
  -H "Accept: application/sparql-results+json"
```

---

## Ontwerpkeuzes

- **CRID-patroon voor identifiers:** entiteiten worden niet direct voorzien van een code-literal, maar via een `IAO:CRID`-node die deel is van een `CodeSystem`. Dit maakt queries over meerdere codesystemen eenduidig en vermijdt verwarring bij hergebruik van codes.
- **Parameteriseerbare queries:** behandelingscodes en exclusiecodes staan in `VALUES`-blokken bovenaan de query, zodat de logica herbruikbaar is voor andere indicatoren.

---

## Licentie

*Nog te bepalen – dit is een intern proof-of-concept van ZINL.*
