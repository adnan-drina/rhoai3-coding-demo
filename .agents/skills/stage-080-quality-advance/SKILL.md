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
  and records decisions in the active quality gate (V9 archived:
  tmp/docs-archive/V9-QUALITY-GATE.md). Driver
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
driver (`tmp/v8-driver-loop.sh`) emits CRITICAL every tick for **O-DRV4
chat pulses** (`tmp/V9-CHAT-PULSE-PENDING.md` → ack
`tmp/V9-CHAT-PULSE.ack`) and keeps CRITICAL for **O-DRV3** while
`tmp/V9-TASK-ANALYSIS-PENDING.md` exists. Chat pulse first, then analysis.
Never go idle between ticks.

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
- Outer/supervisor lines: `MiniMax` / `escalation` / `worker incomplete`

**Evidence pack (minimum) — AI code + AI action quality are crucial:**

1. `git show --stat` + full diff (or representative hunks) — **read the
   generated code**, not only the commit title.
2. **AI-generated code quality:** matches task goal/acceptance and legacy
   intent; harvest/rename fidelity; real assertions (no G-PLACE); no
   ceremonial stubs; packages/APIs honest; no security-sensitive junk.
3. **AI action quality:** actor path (worker / O-T6 mechan / O-ESCW /
   MiniMax escalation / style-autofix / sfix) — was this the right action,
   or a false green / wrong-title / wasted seat?
4. For RED / partial / sfix / escalation: supervisor slice + dimension logs
   (`/tmp/sensor-task.log`, `/tmp/sensor-milestone.log`, `/tmp/sensor-sonar.log`,
   `/tmp/sonar-violations.txt`, `/tmp/oc-T-NNN.err`, `/tmp/style-autofix.log`).
5. Remaining violations, root cause, harness smells, and **process
   performance** (retry thrash, quota burn, silent ticks).
6. **Bank every durable gap immediately** as a ⬜ row in
   `tmp/docs-archive/V7-FUTURE-IMPROVEMENTS.md`. Do **not** ask the human whether to
   bank — append in the same analysis pass (main run goal).

### Escalation gate (MiniMax over Qwen — every takeover)

When MiniMax/Hermes takes over from Qwen/OpenCode, the task gate **must**
include this loop (same temporary→durable→re-run spirit):

1. **Capture** — dedicated gate bullets: task id, when escalation fired,
   whether MiniMax wrote the winning commit.
2. **Qwen root cause** — read `/tmp/oc-T-NNN.err` and `/tmp/oc-T-NNN.json`
   (or OpenCode session output), plus supervisor lines *before* escalation
   (worker rc, O-T6/O-T6b/O-T6d/O-ESCW/already-complete decisions, dirty
   paths). State the concrete cause in one paragraph.
3. **MiniMax action review** — what it changed; necessary vs false path.
4. **Durableize** — bank ⬜ and implement harness/skill/worker guidance so
   that cause does not force MiniMax again.
5. **Retest** — re-run / resume proving the worker path completes without
   MiniMax for that failure class when the durable fix is in place.

Do **not** clear O-DRV3 for an escalation commit until steps 1–3 are written
and step 4 is banked (or implemented). Step 5 may be the next resume; note
it explicitly as owed if deferred past HOLD.

**HOLD immediately** (stop harness) on:

- Ceremonial acceptance / `status`+`ok` / `assertThat(true)` (G-OK/G-PLACE)
- Later-story classes under `src/main`
- Empty harvest / commit claims work that `git show` does not contain
- Scope vs roadmap mismatch (e.g. S01 `pom.xml` growing REST endpoints)

**Record** a detailed bullet block under the current story in
`tmp/docs-archive/V9-QUALITY-GATE.md` (not just a table one-liner). Escalations and
sensor-fix paths get an explicit “why” paragraph.

**Clear O-DRV3 pending** only via the clear script (bare SHA write is invalid):

```bash
# after writing a detailed tmp/docs-archive/V9-QUALITY-GATE.md section for this SHA
bash scripts/track-b/v9-capture-diff.sh --oc <full-sha>
bash scripts/track-b/v9-clear-task-analysis.sh <full-sha>
# Escalations first:
# bash scripts/track-b/v9-clear-escalation.sh T-NNN --qwen-cause '...' --bank-id O-XXX --retest '...'
```

O-DRV5: `bash scripts/track-b/v9-clear-m-analysis.sh <sha>` (requires
`**Verdict:** ADVANCE|HOLD|ABORT`). See `scripts/track-b/README.md`.

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
| **AI-generated code** | Correct, faithful, tested, maintainable — not merely compiling |
| **AI actions** | Right actor/path; no false already-complete / wrong mechan / scope cheat |
| Escalations | Each has root cause (worker no-commit, quota, real failure) |
| `src/main` | Expected harvest/redesign only; no fabricated later-story classes |
| `src/test` | Real assertions; **no** G-PLACE patterns |
| Sensors | task/milestone/preflight logs — note RED dimensions (insufficient alone) |
| Coverage / acceptance | Preflight bar; no ceremonial status-map acceptance |
| Process performance | No silent ticks, no wasted MiniMax, no thrash loops left unbanked |
| Bank | Open rows this milestone exposed |

Read commit **bodies**, not only titles. Open representative source files.
Sensor GREEN without AI code/action judgment is an incomplete gate.

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
- **Temporary manual → durable → re-run:** a hand edit in the live tree may
  probe a hypothesis. After it validates, implement the same capability in
  harness/skills/sensors (mark bank ✅) and **re-run** so the process owns
  the fix. Do not mark a gap closed because the agent patched `src/` once.
- **Migration-general only:** durableize against **patterns** (preserve
  tokens, missing Target `.java`, rewrite-before-infer, cheap sonar sfix,
  worker no-commit, etc.) parameterized by `migration.yaml` / briefs /
  findings. Reject bank ✅ if the fix only understands Coolstore cart
  classes, packages, item ids, or endpoints. Put specimen-specific examples
  in instruments/fixtures or story artifacts.

### 5. Record

Append to `tmp/docs-archive/V9-QUALITY-GATE.md` (active run):

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
- Hand-fixing the app to clear Sonar/sensors and advancing without
  durableize + re-run proof (north-star violation).
- “Escalation → MiniMax GREEN” without Qwen-log root cause, durable fix,
  and retest plan/proof.
- Coolstore-only harness patches presented as durable (next Spring Boot →
  Quarkus app would not inherit the behavior).
