---
name: check-spec-readiness
description: Before kanban_create or M3 dispatch — lints SDD specs and story bodies, refuses with typed BODY_* codes
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; reads migration/ specs and bodies
metadata:
  author: rhoai3-harness-team
  version: "1.2.0"
  hermes:
    tags:
    - sdd
    - m2
    category: sdd
    kind: guidance
---
## When to Use

- Before `kanban_create()` and before dispatching any M3 body — the phase-attach
  matrix pins this skill to every phase M1–M5.
- After authoring or amending a `evidence/bodies/*.json` — validate that one
  body with `--body <path>` at create time, not only the whole corpus.
- At M2a exit — prove the partition is VALID as a whole (endpoint coverage, no
  write overlap), which per-body lint cannot show.
- When a body's `exit_criteria`, `files_in_scope`, or `operand_count` changed —
  these are the fields the gates refuse on.
- **Not** for creating `.specify/` or installing `specify-cli` — that is
  `init-spec-workspace`. This skill reads artifacts and writes only receipts
  and stamps you explicitly ask for.


# SDD readiness (pattern-steals + §S.6)

## Procedure

```bash
bash "${HERMES_SKILL_DIR}/scripts/check-readiness.sh"
# W2 §6.1 typed body vocabulary
python3 "${HERMES_SKILL_DIR}/scripts/check-kanban-body.py" /projects/modernized
# AD-H §16.9 / AR-4.4 — surgical write sets + endpoint exits
python3 "${HERMES_SKILL_DIR}/scripts/check-surgical-scopes.py" /projects/modernized
# AR-2.3–2.7 — semantic product exits for REST/persistence stories
python3 "${HERMES_SKILL_DIR}/scripts/check-semantic-exits.py" /projects/modernized
# Architect E-104925Z / E-110403Z — measured operand_count (phase-name REJECT)
python3 "${HERMES_SKILL_DIR}/scripts/check-operand-count.py" /projects/modernized
# M2a exit — partition VALID as a whole (writes a tri-state receipt)
python3 "${HERMES_SKILL_DIR}/scripts/check-partition-coverage.py" /projects/modernized \
  --write-receipt evidence/receipts/partition-coverage/latest.json
```

`check-readiness.sh` already runs `check-ordering.py` (§S.6) and
`check-kanban-body.py` — run the body lint standalone only to scope it with
`--body`. Idle (pass) when no SDD / body artifacts exist yet.

## Contracts

- `governance/contracts/pattern-steals.md`
- `governance/contracts/sdd-ordering.md` (AD-S §S.6)
- `governance/contracts/surgical-scopes.md` (AR-4.4)
- `governance/contracts/semantic-exits.md` (AR-2.3–2.7)
- `governance/contracts/story-sizing.md` (operand_count)
- `governance/schemas/mta-exception.md`
- `governance/schemas/kanban-body.md` (W2 §6.1)

## Available scripts

- `scripts/check-readiness.sh` — corpus SDD readiness + ordering + body lint
- `scripts/check-kanban-body.py` — W2 §6.1 typed body vocabulary (`--body` optional)
- `scripts/check-ordering.py` — §S.6 story/spec ordering
- `scripts/check-surgical-scopes.py` — AR-4.4 write-set / exit surgery
- `scripts/check-semantic-exits.py` — AR-2.3–2.7 product exit semantics
- `scripts/check-operand-count.py` — measured operand_count / wall-fit
- `scripts/check-partition-coverage.py` — M2a partition VALID receipt
- `scripts/check-interface-closure.py` — interface closure Class-A gate
- `scripts/check-findings-handoff.py` — findings handoff schema (also under mta)
- `scripts/check-persistence-bom.py` — R-M3.5 persistence BOM in pom.xml
- `scripts/check-compile-deps-preflight.py` — R-M3.7 wraps persistence BOM
- `scripts/check-jdbc-deps-preflight.py` — R-M3.11 JDBC deps preflight
- `scripts/assert-dependency-closure.py` — Class-A dependency closure
- `scripts/assert-mint-constraints-complete.py` — mint constraints complete
- `scripts/assert-constraints-preserved.py` — constraints survive amend
- `scripts/assert-quarantine-tombstones.py` — quarantine tombstone presence
- `scripts/assert-dest-inventory-hardinvoke.py` — dest inventory hard-invoke
- `scripts/register-quarantine-tombstone.py` — mutate: register tombstone
- `scripts/stamp-body-dependencies.py` — mutate: `--write` body deps stamp
- `scripts/stamp-destination-inventory.py` — mutate: `--write` dest inventory
- `scripts/specimen_agnostic.py` — library helper (not an agent entry point)

## Verification

- `check-readiness.sh` ends `OK: SDD readiness passed (N artifact(s) checked)`;
  each violation prints `FAIL: <relpath>: …` first. **Silent-failure catch:**
  `readiness lint idle` (N=0) while specs/bodies exist means the artifacts are
  not under the scanned roots — unproven, not passed.
- `check-kanban-body.py` prints `OK: Kanban body §6.1 checks passed (N body(ies);
  corpus|single-body)`. Failures are typed and stable: `BODY_SCHEMA`,
  `BODY_REF_UNKNOWN`, `BODY_REF_SHA256`, `BODY_REF_DIGEST`, `BODY_REF_MISSING`,
  `BODY_INLINE`, `BODY_SCOPE`, `BODY_SCOPE_DEST`, `BODY_EXIT`, `BODY_IDENTITY`,
  `BODY_G2`, `BODY_SIZE`. `BODY_REF_DIGEST` is the drift catch — a ref file
  changed after the body was minted.
- `check-surgical-scopes.py` → `OK: AR-4.4 surgical scopes (N M3 body(ies))`; it
  refuses an empty destination write set, one path owned by two bodies without
  `sequence_after`, and exit criteria drawn only from the compile-only set.
- `check-operand-count.py` → `OK: … operand_class=… operand_count=R measured=M
  max=…`; `R` must equal the measured write set, so a scope edit that forgets
  the count is refused rather than silently resized.
- `check-partition-coverage.py --write-receipt` leaves
  `evidence/receipts/partition-coverage/latest.json`
  (`schema: rhoai3.partition-coverage/v1`) with `verdict`, `gaps[]`,
  `http_endpoint_count`. Only `VALID` exits 0 — `INCONCLUSIVE` (no story files
  found) is not a pass.
- Exit condition for the gate: every command above exits 0 **and** reports a
  non-zero artifact/body count. All-idle output on a populated workspace is a
  path defect to fix before dispatch.
