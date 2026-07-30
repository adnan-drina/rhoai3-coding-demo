---
name: stage-080-track-b
skill-group: Demo Environment
applies-to:
  - stages/080-ai-autonomous-migration/**
  - docs/V7-FUTURE-IMPROVEMENTS.md
  - docs/V8-QUALITY-GATE.md
  - docs/V9-QUALITY-GATE.md
  - docs/V*-*.md
  - "**/quarkus-migration-scaffold/**"
  - tmp/v8-driver-loop.sh
  - tmp/V9-TASK-ANALYSIS*
  - AGENTS.md
---

# Stage 080 Track B — no compromises

**End state:** an **autonomous, swift, hardened, durable, fully functional**
migration process.

**Method:** methodical, thorough, thoughtful at every step. Skip nothing.
When an issue appears, **fix it and re-run**. Prefer **multiple partial
runs** that harden the harness over **one completed run with a broken
service**.

Mirror of AGENTS.md "Stage 080 Track B — non-negotiable mandate".

## Always-on constraints

When driving, monitoring, or changing Track B (Hermes outer-loop, supervisor,
sensors, scaffold skills, live migration workspace):

1. **Read and follow** `.agents/skills/stage-080-quality-advance/SKILL.md`
   and the AGENTS.md Track B mandate on this cadence: **detailed analysis
   after every T-NNN** (and every sensor-fix / partial autofix /
   escalation), **comprehensive check after every milestone M (M1–M5)**,
   and full gate before M5 ship / story complete / next story.
2. **Do not wait for the human to ask** for analysis. As soon as a task
   commit or RED/partial/sfix/escalation is identified, run the detailed
   task gate. Driver O-DRV3 (`tmp/v8-driver-loop.sh`) keeps CRITICAL ticks
   while `tmp/V9-TASK-ANALYSIS-PENDING.md` is uncleared — treat that as P0
   process work, equal to outer=DOWN urgency for honesty.
3. **Do not advance on green sensors alone.** Sensors catch many classes of
   failure; they miss ceremonial commits, empty harvests, placeholder tests,
   escalations-without-root-cause, and plan defects. Substance review is
   mandatory — read the diff; no assumptions.
4. **Record** detailed task notes, escalation root causes, and M/story
   ADVANCE/HOLD/ABORT decisions in the active run gate file
   (`docs/V9-QUALITY-GATE.md` for V9). No silent stage push.
5. **Bank durable defects immediately** in `docs/V7-FUTURE-IMPROVEMENTS.md`
   when analysis finds a gap. Do **not** ask whether to bank. Then
   **implement** open bank rows that block honesty (or HOLD) — do not
   accumulate backlog while a broken run continues.
6. **Prefer abort/HOLD + fix + re-run over throughput.** If delivery or
   harness honesty fails, stop; do not "fix forward" into the next story
   or nurse a compromised run for hours.
7. Human GO is **not** required for advance. The agent owns the quality loop
   and may ADVANCE only after a written review concludes the delivery is
   honest and durable enough.

## Anti-patterns (forbidden)

- Skipping detailed task analysis because the tick log says GREEN (or RED
  with only a label and no root cause).
- Waiting for the user to request analysis of a situation the agent already saw.
- Asking whether to bank an improvement — always bank; never ask.
- Leaving open polish for "after the demo" while continuing a bad run.
- Pushing a story to completion with a broken or dishonest service.
- Resuming straight into M5 ship / next story after polish without a gate entry.
- Treating "already committed / skipped" as quality evidence.
- Clearing O-DRV3 pending without a corresponding `docs/V9-QUALITY-GATE.md` entry.
