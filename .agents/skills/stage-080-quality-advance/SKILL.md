---
name: stage-080-quality-advance
metadata:
  author: rhoai3-coding-demo
  version: 1.1.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Demo Environment"
description: >
  Agentic quality-advance gate for Stage 080 Track B. Use after every T-NNN
  task commit, after every major milestone M (M1–M5), before M5 ship/push,
  before story-complete / next story, after abort, and on escalations. Critically
  reviews delivery substance (not only sensor GREEN), banks harness gaps,
  implements or HOLDs, and records decisions in docs/V9-QUALITY-GATE.md (active
  run). Do NOT use for ordinary stage deploy/validate (use validate-demo-step)
  or GitOps review (use review-gitops-change).
---

# Stage 080 quality-advance loop

Companion rule: `.agents/rules/stage-080-track-b.md`.

Goal: **harden the harness and keep deliveries honest**. Throughput is
secondary. This loop is agent-owned — no human GO required — but every
decision must be written down.

## Cadence (mandatory)

| Gate | When | Depth |
|------|------|--------|
| **Task** | After each `T-NNN` commit (or escalation→commit) | Light substance check — see below |
| **Milestone M** | After M1 analyze, M1 profile, M2 sequence, M3 specify, M4 task-batch complete, M5 evaluate, M5 ship result | Comprehensive review |
| **Story** | Before story-complete / next story / M5 push | Full story gate (existing) |

If a driver tick fires while a gate is open (`HOLD` without resolution),
**do not** auto-restart into ship/next story — finish or refresh the gate.

### Task gate (light — every T-NNN)

Do **not** freeze the harness for every task unless HOLD/ABORT is indicated.
While the run continues, after each task commit:

1. Read commit subject + `git show --stat` (and body if non-POM).
2. Note actor path: worker / O-T6 mechan / O-ESCW noop / MiniMax escalation.
3. For **escalations**: read `/tmp/oc-T-NNN.err`, supervisor lines for
   `worker exit rc=`, `burned`, `quota`, and whether the commit was only
   “Already satisfied” — capture root cause in the gate log (or a running
   Escalations section).
4. Quick red flags → **HOLD** (stop harness):
   - Ceremonial acceptance / `status`+`ok` / `assertThat(true)` (G-OK/G-PLACE)
   - Later-story classes under `src/main`
   - Empty harvest / commit claims work that `git show` does not contain
   - Scope vs roadmap mismatch (e.g. S01 `pom.xml` growing REST endpoints)
5. Append a **one-liner** (or short bullet) under the current story section in
   `docs/V9-QUALITY-GATE.md`. Escalations get a short “why” paragraph.

### Milestone M gate (comprehensive)

**Freeze** outer-loop (and pause driver auto-restart) long enough to review.
Then run the full loop below for that M’s artifacts.

| M | Focus |
|---|--------|
| M1 | Findings/profile substance; no plan leakage |
| M2 | Roadmap/briefs vs dependency-order; S01 scope honesty |
| M3 | tasks.md vs brief/roadmap; S-CHAR / S-AC1 / no soft tasks |
| M4 | All T-NNN substance + escalation pattern; tree vs scope |
| M5 | Evaluate honesty (L-M5e); preflight; ship/factory outcome |

## Loop (comprehensive / story / HOLD)

### 1. Freeze

Stop or pause outer-loop / supervisor / driver auto-restart long enough to
inspect. Do not let O-DRV2 race a ship while reviewing.

### 2. Gather evidence (live tree)

| Check | What "good" looks like |
|-------|-------------------------|
| Story brief vs tasks | Tasks match brief scope; no later-story SUTs required |
| Commits since story `RUN_BASE` | Each `T-NNN` changes claimed paths; messages match substance |
| Escalations | Each has root cause (worker no-commit, quota, real failure) |
| `src/main` | Expected harvest/redesign only; no fabricated later-story classes |
| `src/test` | Real assertions; **no** G-PLACE patterns |
| Sensors | task/milestone/preflight logs — note RED dimensions |
| Coverage / acceptance | Preflight bar; no ceremonial status-map acceptance |
| Bank | Open rows this milestone exposed |

Read commit **bodies**, not only titles. Open representative source files.

### 3. Decide

| Verdict | Meaning | Next action |
|---------|---------|-------------|
| `ADVANCE` | Delivery meets brief/acceptance honestly | Resume; record gate entry |
| `HOLD` | Fixable gaps | Implement + bank; re-run loop; do not advance |
| `ABORT` | Compromised / false-green / wrong scope | Reset; bank; polish before restart |

Default bias: if unsure between ADVANCE and HOLD → **HOLD**.

### 4. Bank and fix

- Append durable harness/plan/sensor gaps to the polish bank (⬜).
- Implement **open** bank rows that block honesty before restarting Track B.
- Do not weaken sensors to clear a RED.

### 5. Record

Append to `docs/V9-QUALITY-GATE.md` (active run):

```markdown
## <UTC date> — <M-id or story/task id>

- **Verdict:** ADVANCE | HOLD | ABORT
- **HEAD:** `<sha> <subject>`
- **What shipped (substance):** …
- **Escalations / anomalies:** …
- **Weak / dishonest:** …
- **Sensor/preflight:** …
- **Banked:** id — note (or none)
- **Next action:** …
```

### 6. Act on verdict

- `ADVANCE` — resume only the approved next step; keep monitoring.
- `HOLD` — keep harness down until fixes land; then repeat.
- `ABORT` — reset/push honestly; implement bank; restart only when clean.

## Anti-patterns

- Task/story GREEN without reading the commit body.
- Escalation logged without reading `/tmp/oc-T-*.err` / supervisor why.
- Advancing because M5 evaluate says “complete.”
- S01 growing ceremonial acceptance endpoints (V9 S01 HOLD).
