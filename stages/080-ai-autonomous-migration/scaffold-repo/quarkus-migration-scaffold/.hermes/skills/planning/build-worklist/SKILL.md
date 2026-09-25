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

Under `decisions.loop.unit_formation: v1` a coordinated repair clusters as
one **unit** instead of per file: a diagnostic family, a declaration and its
direct implementers and callers, a package nothing outside names, or a
property and its consumers. What decides those is the compiler's own model,
never a package name: each type row's declaration walk (`type_refs`: the
declared types its supertypes, type-parameter bounds, field types and member
signatures name, through generic arguments, array components, wildcard and
type-variable bounds, intersections and enclosing types), plus a declared
member's `type_refs` and resolved `calls`, the supertypes and the imports.

The walk is bounded and says whether it finished: `type_refs_complete` is
false, with `type_refs_incomplete` naming where and why, when a part is
unresolved, unsupported or over the depth/node bound. A reference found is
evidence even on an incomplete row; an absence is evidence only on a complete
one. So a package is a **leaf** only when every type inside and outside it is
named, its walk is complete, every outside type is fully resolved, and no
failed file of the source root is missing from the model. "Isolated" means no
recorded inbound declaration reference in `src/main/java` — not unreachable,
unused or safe to delete: framework callbacks, reflection, configuration and
body-only references are outside the walk. When the evidence is short, the
leaf rule steps aside and the family, declaration and per-file rules take the
same obligations; nothing is dropped and nothing becomes writable because a
reference was found. The same completeness bounds the retirement check: an
incomplete walk cannot prove a retired symbol gone, though the independent
parse proof still can.

A unit is bounded at 20 files, 160 sites and 8 symbols. A union narrows by
dropping whole families, lowest cardinality first, and each dropped
obligation stays in the work list as its own item; a declaration closure
never drops its callers, because a caller is bound to the declaration the
unit changes. Anything still over the bound is `UNIT_OVERSIZE`, an admission
block, not a chunk. Where the rule can enumerate a fragment parent that no
implementer answers, the seal also records the **implementation obligation**:
the new type and file the naming contract fixes for it, which is what lets
`amend-scope.py` authorize that path before it exists.

## Procedure

```bash
bash /projects/modernized/.hermes/skills/planning/build-worklist/scripts/build-worklist.sh --root /projects/modernized
```

Runs `fix-until-green/scripts/run-verify.sh` (the real tools) and then
`advance.py --baseline` (commits the bootstrapped tree as step 0 and
re-seals admission). A measure that is not fully known is admission
BLOCK `MEASURE_UNKNOWN`.

Run once in the foreground with terminal `timeout: 600`. The wrapper
prints `WORKLIST_PHASE` for verification and baseline. On nonzero exit,
report the failing phase and read that invocation's output plus
`verification/build/run.json` if present. Correct one identified invocation
error and retry once; if the same failure remains, block with its exact
error and phase. Do not background the command, guess alternative paths,
repeat Maven separately, or write the missing receipt yourself. Compiler
diagnostics are measurements; a failed verifier process is a tool failure.

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
