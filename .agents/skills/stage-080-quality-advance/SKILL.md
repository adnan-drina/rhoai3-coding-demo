---
name: stage-080-quality-advance
metadata:
  author: rhoai3-coding-demo
  version: 1.2.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Demo Environment"
description: >
  Agentic quality-advance gate for Stage 080 Track B. Use after every T-NNN
  task commit (detailed analysis — not a one-liner), after every major
  milestone M (M1–M5), before M5 ship/push, before story-complete / next
  story, after abort, and on escalations. Critically reviews delivery
  substance (not only sensor GREEN), banks harness gaps, implements or HOLDs,
  and records decisions in docs/V9-QUALITY-GATE.md (active run). Driver
  O-DRV3 nags via tmp/V9-TASK-ANALYSIS-PENDING.md until the task gate is
  written and cleared. Do NOT use for ordinary stage deploy/validate (use
  validate-demo-step) or GitOps review (use review-gitops-change).
---

# Stage 080 quality-advance loop

Companion rule: `.agents/rules/stage-080-track-b.md`.

Goal: an **autonomous, swift, hardened, durable, fully functional**
migration process. No compromises, assumptions, or cutting corners.
Prefer fix + re-run (multiple partial runs that harden the harness) over
one completed run with a broken service. Throughput is secondary. This
loop is agent-owned — no human GO required — but every decision must be
written down. See AGENTS.md "Stage 080 Track B — non-negotiable mandate".

**Process mandate:** when a task lands or a RED/partial/sfix/escalation
appears, run the **Task gate (detailed)** immediately — do **not** wait for
the human to ask, and do **not** defer depth until a later milestone. The
driver (`tmp/v8-driver-loop.sh`, O-DRV3) will keep emitting CRITICAL ticks
while `tmp/V9-TASK-ANALYSIS-PENDING.md` exists.

## Cadence (mandatory)

| Gate | When | Depth |
|------|------|--------|
| **Task** | After each `T-NNN` commit, `T-NNN sensor fix`, or escalation→commit | **Detailed** — see below (not a one-liner) |
| **Milestone M** | After M1 analyze, M1 profile, M2 sequence, M3 specify, M4 task-batch complete, M5 evaluate, M5 ship result | Comprehensive review |
| **Story** | Before story-complete / next story / M5 push | Full story gate (existing) |

If a driver tick fires while a gate is open (`HOLD` without resolution, or
O-DRV3 pending uncleared), **finish the analysis / HOLD first** — do not
silent-advance into ship/next story.

### Task gate (detailed — every T-NNN)

Do **not** freeze the harness for every clean task unless HOLD/ABORT is
indicated. Do **always** gather evidence and write a real gate note while
the run continues.

**Trigger immediately** (same tick you notice them — no waiting for ask):

- New `T-NNN:` / `T-NNN sensor fix:` commit
- `SENSOR RED`, style-autofix partial, sensor-fix dispatch
- Escalation / quota / O-ESCW / debt / FAIL lines

**Evidence pack (minimum):**

1. `git show --stat` + full diff (or representative hunks) for the commit(s).
2. Actor path: worker / O-T6 mechan / O-ESCW noop / MiniMax escalation /
   deterministic style-autofix / sfix.
3. For RED / partial / sfix / escalation: supervisor slice + dimension logs
   (`/tmp/sensor-task.log`, `/tmp/sensor-milestone.log`, `/tmp/sensor-sonar.log`,
   `/tmp/sonar-violations.txt`, `/tmp/oc-T-NNN.err`, `/tmp/style-autofix.log`).
4. Remaining violations, root cause, and harness smells (e.g. `git add -A`
   sweeping `migration/staging` or `.hermes/`, cross-task Sonar bleed,
   comment that should clear S1186 but does not, false-green risk).
5. **Bank every durable gap immediately** as a ⬜ row in
   `docs/V7-FUTURE-IMPROVEMENTS.md`. Do **not** ask the human whether to
   bank — append in the same analysis pass (main run goal).

**HOLD immediately** (stop harness) on:

- Ceremonial acceptance / `status`+`ok` / `assertThat(true)` (G-OK/G-PLACE)
- Later-story classes under `src/main`
- Empty harvest / commit claims work that `git show` does not contain
- Scope vs roadmap mismatch (e.g. S01 `pom.xml` growing REST endpoints)

**Record** a detailed bullet block under the current story in
`docs/V9-QUALITY-GATE.md` (not just a table one-liner). Escalations and
sensor-fix paths get an explicit “why” paragraph.

**Clear O-DRV3 pending** only after the gate entry exists:

```bash
# after writing docs/V9-QUALITY-GATE.md
git -C /projects/modernized rev-parse HEAD > tmp/V9-TASK-ANALYSIS.sha   # via oc or local mirror of HEAD
rm -f tmp/V9-TASK-ANALYSIS-PENDING.md
```

(Use the workspace HEAD SHA you actually reviewed.)

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

- Append durable harness/plan/sensor/process gaps to the polish bank (⬜)
  in the same pass — never ask “should I bank this?”
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

- Waiting for the human to request analysis that the tick already surfaced.
- Asking whether to bank an improvement — always bank; never ask.
- Task/story GREEN without reading the commit body / sensor logs.
- One-liner gate notes for RED / partial autofix / escalation (depth required).
- Escalation logged without reading `/tmp/oc-T-*.err` / supervisor why.
- Advancing because M5 evaluate says “complete.”
- S01 growing ceremonial acceptance endpoints (V9 S01 HOLD).
- Leaving `tmp/V9-TASK-ANALYSIS-PENDING.md` uncleared after a real review.
