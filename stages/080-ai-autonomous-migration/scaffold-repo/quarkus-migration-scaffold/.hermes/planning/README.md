# Planning contracts (`.hermes/planning/`)

One authoritative home for every contract the fix-until-green loop
(SAD v3) reads. Admission seals all of them; a change after admission
invalidates the receipt.

| File | Role |
|---|---|
| `schemas/evidence-bundle.schema.json` | M1 evidence bundle (source manifest, structure, entry points, MTA obligations, producer receipts) |
| `schemas/worklist.schema.json` | the only plan: tool-computed items, file clusters, fixed order, measure |
| `schemas/admission-receipt.schema.json` | receipt v2: seals (bundle, work list, bootstrap, decisions, contracts, pins), blocks, activation, measure |
| `schemas/decisions.schema.json` | `decisions.yaml` v2: destination platform, attempt threshold, ADR-retired items |
| `schemas/producer-receipt.schema.json` | every producer receipt (freeze, build, jdk-model, mta, bootstrap) |
| `schemas/structure.schema.json` | JDK-model structural claims |
| `catalogs/compat-mapping.json` | deterministic bootstrap for the Spring-compatibility path (starters → extensions, drivers, property keys, main class); every row a documented Quarkus mapping |
| `catalogs/entry-points.json` | annotation → entry-point kind catalog (HTTP, scheduled, messaging, …) for the source oracles |
| `catalogs/destination-platforms.json` | platform ids (`decisions.destination_platform.id`) → BOM pin key, compat mapping |
| `catalogs/framework-generated.json` | generated-source markers |
| `catalogs/cross-cutting.json` | cross-cutting annotation/supertype catalog (retained for the entry-point derivation) |
| `mta-rules/ruleset.yaml`, `mta-rules/rhoai3-canary.yaml` | custom rules + the canary that proves the effective ruleset |
| `decisions.example.yaml` | fail-closed template for the project-root `decisions.yaml` |

Nothing here is written by a worker. A missing decision is an admission
`BLOCK` and the loop refuses to mint; nothing is inferred.
