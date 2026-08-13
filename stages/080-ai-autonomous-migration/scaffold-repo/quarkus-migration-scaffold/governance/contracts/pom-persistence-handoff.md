# Cross-story POM / dependency_wait handoff (R-M3.5–8)

**Status:** binding proving-min
**Basis:** AD-H §6.5 · `20260810-m3-s002-harness-review.md`

## Bindings

| ID | Rule |
|----|------|
| **R-M3.5** | Scaffold / S-001-class foundations **MUST** leave `quarkus-hibernate-orm` + `quarkus-hibernate-validator` in `pom.xml` (JDBC when a story needs a live datasource) **or** split a persistence-BOM story with pom writable. `grep -q quarkus` alone is **not** a sufficient `quarkus_pom` exit. |
| **R-M3.6** | On typed `dependency_wait`, **do not** auto-promote / soft-requeue until a named actor fixes the upstream dep **or** the body gains typed pom write authority. Stamp `Needs: steward:fix-upstream-pom…` (peer of AD-010 §3d). Use `apply-dependency-wait-hold.py`. |
| **R-M3.7** | Model / JPA Job step 0: run `check-compile-deps-preflight.py` **before** first entity write; fail → typed `dependency_wait` (no N-file sunk cost). |
| **R-M3.8** | After typed `dependency_wait`, **forbid** re-litigating `files_writable` in Reasoning — wait for human steward or escalate. Do not OOS-edit `pom.xml`. |

**Reject:** blanket pom write on every story · skill pile · MiniMax.

## Commands

```bash
# R-M3.5 substrate / S-001 exit helper
python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-persistence-bom.py .

# R-M3.7 before first model write
python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-compile-deps-preflight.py .

# R-M3.6 when dependency_wait fires (dispatcher)
python3 .hermes/skills/gates/check-release-readiness/scripts/apply-dependency-wait-hold.py \
 . --task-id t_xxx --stamp --block
```

Stamp: `evidence/verdicts/dependency-wait-hold-<task_id>.json`
(`rhoai3.dependency-wait-hold/v1`).
