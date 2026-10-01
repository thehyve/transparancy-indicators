# Indicator Localization Architecture

This diagram shows the full flow from centrally maintained indicator logic to hospital-specific executable SQL.

```mermaid
flowchart LR
    subgraph M[Maintainers]
        O[ti-o ontology]
        T[Indicator templates]
        D[Disease concept blocks]
        B[Shared SQL blocks]
        C[compose.py]
        Q[Published canonical SQL]
    end

    subgraph H[Hospital]
        S[Concept mapping<br/>SSSOM]
        X[Structural mapping<br/>structural translation YAML]
        L[localize_sql.py<br/>plus structural pass]
        F[Final executable SQL]
        DB[(Hospital database)]
        R[Indicator result]
    end

    O --> D
    T --> C
    D --> C
    B --> C
    C --> Q

    Q --> L
    S --> L
    X --> L
    L --> F
    F --> DB
    DB --> R

    classDef maintain fill:#e8f3ff,stroke:#3b82f6,stroke-width:1px,color:#0f172a;
    classDef hospital fill:#ecfdf5,stroke:#10b981,stroke-width:1px,color:#052e16;
    classDef artifact fill:#fff7ed,stroke:#f59e0b,stroke-width:1px,color:#7c2d12;

    class O,T,D,B,C maintain;
    class S,X,L hospital;
    class Q,F,R artifact;
```

## Reading Guide

- Canonical logic is built once by maintainers.
- Concept mapping chooses which local codes represent ti-o concepts.
- Structural mapping chooses where canonical fields come from in local schema.
- Hospitals should only localize mappings, not change indicator logic.
