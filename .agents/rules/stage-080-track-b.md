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

**Temporary manual → durable → re-run:** hand edits in the live app tree
are OK only to confirm an assumption. After validation, **implement the
same fix in harness/skills/sensors** (bank ⬜ → ✅) and **re-run** so the
process applies it without the hand edit. Probe-only fixes that never
land in the harness are forbidden.

Mirror of AGENTS.md "Stage 080 Track B — non-negotiable mandate".

## Always-on constraints

When driving, monitoring, or changing Track B (Hermes outer-loop, supervisor,
sensors, scaffold skills, live migration workspace):

1. **Read and follow** `.agents/skills/stage-080-quality-advance/SKILL.md`
   and the AGENTS.md Track B mandate on this cadence: **detailed analysis
   after every T-NNN** (and every sensor-fix / partial autofix /
   escalation), **comprehensive check after every milestone M (M1–M5)**,
   and full gate before M5 ship / story complete / next story.
2. **O-DRV4 chat pulse every 120s** — post 2–5 lines in chat, then ack
   `tmp/V9-CHAT-PULSE.ack` and clear `tmp/V9-CHAT-PULSE-PENDING.md`. The
   driver makes every tick CRITICAL for this. Silence / overdue ack is P0.
3. **Do not wait for the human to ask** for analysis. As soon as a task
   commit or RED/partial/sfix/escalation is identified, run the detailed
   task gate. Driver O-DRV3 keeps CRITICAL ticks while
   `tmp/V9-TASK-ANALYSIS-PENDING.md` is uncleared — treat that as P0
   process work, equal to outer=DOWN urgency for honesty.
4. **Do not advance on green sensors alone.** Sensors catch many classes of
   failure; they miss ceremonial commits, empty harvests, placeholder tests,
   escalations-without-root-cause, and plan defects. **Judging AI-generated
   code quality and AI action quality is crucial** on every O-DRV3/O-DRV5
   gate — read the diff and the actor path; no assumptions.
5. **Record** detailed task notes, escalation root causes, and M/story
   ADVANCE/HOLD/ABORT decisions in the active run gate file
   (`docs/V9-QUALITY-GATE.md` for V9). No silent stage push.
6. **Bank durable defects immediately** in `docs/V7-FUTURE-IMPROVEMENTS.md`
   when analysis finds a gap. Do **not** ask whether to bank. Then
   **implement** open bank rows that block honesty (or HOLD) — do not
   accumulate backlog while a broken run continues.
7. **Prefer abort/HOLD + fix + re-run over throughput.** If delivery or
   harness honesty fails, stop; do not "fix forward" into the next story
   or nurse a compromised run for hours.
8. Human GO is **not** required for advance. The agent owns the quality loop
   and may ADVANCE only after a written review concludes the delivery is
   honest and durable enough.
9. **Temporary manual → durable → re-run.** Probe with a hand fix if needed;
   once validated, durableize in harness/skills and re-run for proof. Do not
   close a bank row on a one-off app edit alone.
10. **MiniMax-over-Qwen escalations.** Every time MiniMax takes over from
    Qwen/OpenCode (including sfix MiniMax ownership), capture it, read
    Qwen logs (`/tmp/oc-T-*.err` / `.json`) for root cause, durableize the
    fix in harness/skills, and retest so that failure class does not
    escalate again. “MiniMax fixed it GREEN” is not closure.
11. **Migration-general durable fixes.** Harness/skill/sensor/plan-lint
    changes must generalize to **any** Spring Boot → Quarkus migration on
    this method. Parameterize via `migration.yaml` / briefs / findings.
    Coolstore cart names, packages, item ids, and endpoints belong in story
    artifacts or explicit test fixtures — never as the only shape a “durable”
    fix understands.

## Anti-patterns (forbidden)

- Going silent between driver ticks / leaving `tmp/V9-CHAT-PULSE.ack` stale.
- Skipping detailed task analysis because the tick log says GREEN (or RED
  with only a label and no root cause).
- Waiting for the user to request analysis of a situation the agent already saw.
- Asking whether to bank an improvement — always bank; never ask.
- Leaving open polish for "after the demo" while continuing a bad run.
- Pushing a story to completion with a broken or dishonest service.
- Resuming straight into M5 ship / next story after polish without a gate entry.
- Treating "already committed / skipped" as quality evidence.
- Clearing O-DRV3 pending without a corresponding `docs/V9-QUALITY-GATE.md` entry.
- Hand-fixing the live app to green and moving on without durableize + re-run.
- Logging an escalation without reading Qwen/OpenCode logs for why the worker failed.
- Closing an escalation because MiniMax committed GREEN, without durableize + retest.
- Hardcoding Coolstore cart–specific identifiers into harness “durable” fixes
  that should work for the next Spring Boot → Quarkus app.
