---
name: assemble-evidence-bundle
description: >
  Use as the last M1 ANALYZE producer step, after scan-with-mta, to
  assemble evidence-bundle.json — the first of the five sealed planner
  artifacts — from the frozen manifest, producer receipts, JDK-model
  structure, optional bytecode, context probe, MTA findings, catalogs,
  and migration.yaml. Records facts and provenance only; derives entry
  points, injection bindings, divergences, and obligations mechanically.
  Do not use to plan or to edit any producer output.
license: Apache-2.0
compatibility: Linux seat; Python 3.11+
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - analysis
    - m1
    category: analysis
    kind: guidance
    paths:
      reads: ["/projects/modernized/evidence", "/projects/modernized/.hermes/planning", "/projects/modernized/decisions.yaml", "/projects/modernized/migration.yaml"]
      writes: ["/projects/modernized/evidence/planning/evidence-bundle.json"]
---
# Assemble the evidence bundle (M1 producer of `m1-analyze`)

Owns `evidence/planning/evidence-bundle.json`
(`rhoai3.evidence-bundle/v1`, schema in `.hermes/planning/schemas/`).
Its digest is the root of the planner chain (SAD §6):

```text
evidence-bundle → worklist → admission-receipt
```

## When to Use

- Final producer step of `paved-road-m1`, after every other producer has
  written its receipt. Missing receipts are recorded as `status: missing`
  in `producers`, not invented.
- Whenever a producer re-ran (the bundle digest must change with its
  inputs).

## Procedure

```bash
python3 "${HERMES_SKILL_DIR}/scripts/assemble-evidence-bundle.py" --root /projects/modernized
```

The assembler (`planner.evidence.assemble`):

1. Classifies every frozen file (production, test, resource, build,
   generated, integration, other) from the catalogs.
2. Derives entry points from JDK-model claims + `catalogs/entry-points.json`
   (HTTP, messaging, scheduled, batch, event, lifecycle).
3. Derives injection candidates and resolves bindings per declared
   environment against the context probe (`RESOLVED` / `AMBIGUOUS` /
   `UNRESOLVED`), honouring only ADR-backed `binding_overrides`.
4. Reconciles JDK-model (source) and jQAssistant (bytecode) claims deterministically
   (`STRUCTURAL_DIVERGENCE` vs `NOTE`).
5. Normalizes MTA incidents into stable obligation ids and records the
   canary outcome.
6. Writes canonical JSON. Hostnames, timestamps, and tool-internal ids
   live only under `observations` and are stripped from the digest.

## Verification

- Exit 0 prints the bundle digest; the file validates against
  `evidence-bundle.schema.json` (`admit-migration-plan` re-validates).
- Two runs on unchanged inputs are byte-identical.
- `scripts/assemble-evidence-bundle.test.py` proves determinism, shuffle
  invariance, and that a missing freeze manifest refuses.

## Scripts

- `scripts/assemble-evidence-bundle.py` — the producer
- `scripts/assemble-evidence-bundle.test.py` — selftest
