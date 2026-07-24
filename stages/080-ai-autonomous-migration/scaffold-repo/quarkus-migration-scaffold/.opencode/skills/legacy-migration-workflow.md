---
name: legacy-migration-workflow
description: How to migrate the legacy project into this Quarkus scaffold — analysis-grounded, read-only source, gated output
---

# Legacy Migration Workflow

## Ground rules

1. `/projects/legacy` is **read-only reference material**. Read any file;
   never edit, create, delete, commit, or push there. If a change seems
   needed in the legacy tree, it is not — the change belongs in
   `/projects/modernized` as part of the migration.
2. The **MTA analysis is the checklist**. Findings enumerate what must
   change and why. A migration step that is not traceable to a finding or
   to observed legacy behavior needs justification in the spec.
3. Behavior over structure: capture what the legacy service *does*
   (endpoints, contracts, data shapes, side effects) in the spec, then
   build Quarkus-native — do not transliterate legacy class-by-class.

## Working order

1. Read the MTA analysis results. The normalized contract copy is
   `migration/mta-findings.json` in this repository (the harness writes it;
   see `migration/README.md`). If it does not exist yet, fall back to the
   extension output — each run is saved as machine-readable JSON at
   `/projects/legacy/.vscode/mta-core/analysis_<timestamp>.json`; use the
   newest file. Structure (both copies): a list of rulesets; each ruleset's
   `violations` map is keyed by rule id, with `description`, `category` and
   an `incidents` list (`uri`, `lineNumber`, `message`, `codeSnip`). If no
   analysis exists at either path, ask the user to run the analysis first.
2. Extract the legacy service's observable behavior: REST endpoints and
   verbs, request/response shapes, persistence entities, seed data,
   external calls. Cite file paths from `/projects/legacy` as evidence.
3. Write the spec (`/speckit.specify`) from findings + behavior — never
   from a mental model of "typical" apps.
4. Plan (`/speckit.plan`): map each mandatory finding to its Quarkus-native
   equivalent. Prefer deterministic transforms (OpenRewrite recipes) for
   mechanical changes — dependency swaps, annotation replacement, import
   rewrites; reserve model inference for design judgment.
5. Implement in `/projects/modernized` in small increments; `mvn -q test`
   after each.

## Definition of done

- Every mandatory MTA finding resolved or explicitly waived in the spec.
- Legacy behavior reproduced and covered by tests in the modernized
  project.
- `migration.yaml` untouched (provenance) and the README API table current.
