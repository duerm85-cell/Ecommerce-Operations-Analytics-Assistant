# Architecture

```mermaid
flowchart LR
  A[Approved public endpoint] -->|robots + rate limit| B[Collector framework]
  S[Fixed-seed synthetic generator] --> C[CSV data contract]
  B --> C
  C --> D[(MySQL 8 star schema)]
  C --> E[SQLite fallback validation]
  D --> F[SQL business queries]
  E --> G[Python four-domain analysis]
  F --> H[Power BI semantic model]
  G --> I[Reports and verified charts]
  H --> J[Four-page dashboard]
  I --> K[GitHub portfolio narrative]
  J --> K
```

The source adapter and field mapping are replaceable. Product, user and calendar dimensions surround order and advertising facts, so the same metric layer can support another marketplace or a first-party store export.

