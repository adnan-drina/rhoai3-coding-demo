---
name: build-worklist
description: >
  Use at M2 PLAN after bootstrap-destination to produce the only plan:
  evidence/planning/worklist.json. Runs the mechanical verifier over the
  bootstrapped destination (JDK compiler diagnostics, surefire, MTA
  rescan), turns every tool finding into a file-clustered, fixed-order
  work-list item, records the baseline measure, and commits the baseline.
  No model, no ownership map, no DAG. Refuses without the bootstrap
  receipt. Do not use inside an M3 card (advance.py rebuilds the list
  there).
license: Apache-2.0
compatibility: Linux seat; JDK 21 (javac); Maven offline; Python 3.11+
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - planning
    - m2
    category: planning
    kind: guidance
    paths:
      reads: ["/projects/modernized", "/projects/modernized/evidence/planning/evidence-bundle.json"]
      writes: ["/projects/modernized/evidence/planning/worklist.json", "/projects/modernized/verification"]
---
# Build the work list (M2 producer of the plan)

The work list is recomputed by tools and never by a model:

| Source | Items | Kind |
|---|---|---|
| MTA rescan of the destination (or the frozen-source obligations before the first rescan) | mandatory incidents, one per incident, content-addressed | build / config / incident |
| JDK compiler diagnostics (`JdkDiagnostics.java`) | every ERROR | compile (or build when the pom is unresolvable) |
| surefire reports | every failing test | test |
| parity verdicts (M4) | every FAIL | parity |

Items cluster by file. Order: build → config → compile (leaf types first,
from the JDK model) → incident → test → parity. The head cluster is the
next card. The measure is `(mandatory incidents, compile errors, failing
tests, parity mismatches)`; the loop accepts a step only on a strict
lexicographic decrease with no new mandatory incident.

## Procedure

```bash
bash "${HERMES_SKILL_DIR}/scripts/build-worklist.sh" --root /projects/modernized
```

Runs `fix-until-green/scripts/run-verify.sh` (the real tools) and then
`advance.py --baseline` (commits the bootstrapped tree as step 0 and
re-seals admission). A measure that is not fully known is admission
BLOCK `MEASURE_UNKNOWN`.

## Verification

- `evidence/planning/worklist.json` validates against
  `.hermes/planning/schemas/worklist.schema.json`; `measure.known` is true.
- `verification/loop/steps.json` has the baseline step with a commit.
- `.hermes/lib/planner/worklist.test.py` proves ordering, clustering,
  the measure and the progress rule; `fix-until-green.test.py` proves the
  chain on the http specimen.

## Scripts

- `scripts/build-worklist.sh` — verifier + baseline
- `scripts/rehearse-legacy.sh` — isolated rehearsal without dispatch (`--legacy <checkout> --root <fresh dir>`): M1 producers → bootstrap → first verification → work-list head; SAD v3 §9 exit 5
