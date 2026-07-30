---
name: stage-080-quality-advance
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Demo Environment"
description: >
  Agentic quality-advance gate for Stage 080 Track B migration runs. Use before
  M5 ship/push, before marking a story complete, before starting the next story,
  after abort, and whenever a milestone looks done. Critically reviews delivery
  substance (not only sensor GREEN), banks harness gaps, implements or HOLDs,
  and records ADVANCE/HOLD/ABORT in the active run gate file
(`docs/V9-QUALITY-GATE.md` for V9; prior runs keep their gate files). Do NOT use for
  ordinary stage deploy/validate (use validate-demo-step), GitOps review (use
  review-gitops-change), or non-080 work.
---

# Stage 080 quality-advance loop

Companion rule: `.agents/rules/stage-080-track-b.md`.

Goal: **harden the harness and keep deliveries honest**. Throughput is
secondary. This loop is agent-owned — no human GO required — but every
decision must be written down.

## When to run (mandatory)

Run this skill end-to-end before any of:

- M5 ship / `git push` of a story
- Writing `S0N,complete` (or equivalent) to the story ledger
- Starting story `N+1` or restarting outer-loop into the next story
- Declaring a task batch "done" after mechanical skips / already-complete
- Resuming after abort or polish

If a driver tick fires while a gate is open (`HOLD` without resolution),
**do not** auto-restart into ship/next story — finish or refresh the gate.

## Loop

### 1. Freeze

Stop or pause outer-loop / supervisor / driver auto-restart long enough to
inspect. Do not let O-DRV2 race a ship while reviewing.

### 2. Gather evidence (live tree)

Inspect the migration workspace (and scaffold diffs if harness changed):

| Check | What "good" looks like |
|-------|-------------------------|
| Story brief vs tasks | Tasks match brief scope; no later-story SUTs required |
| Commits since story `RUN_BASE` | Each `T-NNN` changes claimed paths; messages match substance |
| `src/main` | Expected harvest/redesign only; no fabricated later-story classes |
| `src/test` | Real assertions for owned types; **no** G-PLACE patterns |
| Sensors | task/milestone/preflight logs — note RED dimensions |
| Coverage / acceptance | Preflight coverage and acceptance contracts for this story |
| Bank | Open rows in `docs/V7-FUTURE-IMPROVEMENTS.md` that this milestone exposed |

Read commit **bodies**, not only titles. Open representative source files.

### 3. Decide

Pick exactly one verdict:

| Verdict | Meaning | Next action |
|---------|---------|-------------|
| `ADVANCE` | Delivery meets brief/acceptance honestly; sensors green or only known waived ops issues | Resume ship / next story; record gate entry |
| `HOLD` | Fixable gaps (tests, plan trim, sensor polish) | Implement fixes + bank rows; re-run this loop; do not advance |
| `ABORT` | Compromised / false-green / wrong scope | Reset to last honest commit; bank; polish before restart |

Default bias: if unsure between ADVANCE and HOLD → **HOLD**.

### 4. Bank and fix

- Append durable harness/plan/sensor gaps to the polish bank (⬜).
- Implement **open** bank rows that block honesty of the next step before
  restarting Track B (AGENTS.md).
- Do not weaken sensors to clear a RED.

### 5. Record

Append a section to the **active** run gate file (`docs/V9-QUALITY-GATE.md`
for V9; create if missing):

```markdown
## <UTC date> — <story/task id>

- **Verdict:** ADVANCE | HOLD | ABORT
- **HEAD:** `<sha> <subject>`
- **What shipped (substance):** …
- **Weak / dishonest:** …
- **Sensor/preflight:** …
- **Banked:** id — note (or none)
- **Next action:** …
```

### 6. Act on verdict

- `ADVANCE` — resume harness only for the approved next step; keep driver
  monitoring; on the next milestone, run this skill again.
- `HOLD` — keep harness down or in a non-shipping state until fixes land;
  then repeat from step 2.
- `ABORT` — reset/push honestly; implement bank; restart only after gate
  would be ADVANCE or a fresh story start with open bank cleared.

## Anti-patterns

- "T-001..T-004 already committed — skipping" ⇒ treat as **unreviewed** until
  this skill runs.
- Advancing because M5 evaluate commit message says "complete."
- Shipping model harvest with **zero** tests when the brief requires
  characterization / factory coverage will fail (V8 S02 lesson).
