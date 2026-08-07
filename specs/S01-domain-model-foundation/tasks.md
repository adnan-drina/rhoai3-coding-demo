# S01-domain-model-foundation Tasks

<!-- O-M3TYPED — rendered from model.tasks[]; do not treat as SoT -->
# ADR-35/40: task IDs + acceptance are harness-derived. Seat fills JUDGMENT only.

UI surface: waived (API-only).

#### S01-T-001-Bar: Bar — skeleton (fill from brief)
**Class**: rewrite
**Shape**: modify
**Port**: rename
**Role**: HARVEST
**Owns**: `src/main/java/com/demo/model/Bar.java`
**Oracle**: absent
**Assumes**:
**Findings**: (none)
**Goal**: Harvest Bar entity into com.demo.model with package rename only.
**Target design**:
- → `src/main/java/com/demo/model/Bar.java`
**Plan**: Copy from staging; pin via src/test/java/com/demo/model/BarTest.java
**Acceptance**:
- byte-fidelity vs migration/staging (LOC + serialVersionUID)
- package rename only; no behavior change
**Risk**: low

