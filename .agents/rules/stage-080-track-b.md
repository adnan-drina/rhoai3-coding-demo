---
name: stage-080-track-b
skill-group: Demo Environment
applies-to:
  - stages/080-ai-autonomous-migration/**
  - tmp/docs-archive/V7-FUTURE-IMPROVEMENTS.md
  - tmp/docs-archive/V9-QUALITY-GATE.md
  - tmp/docs-archive/V*-*.md
  - docs/V*-*.md
  - "**/quarkus-migration-scaffold/**"
  - tmp/v8-driver-loop.sh
  - tmp/V9-TASK-ANALYSIS*
  - scripts/track-b/**
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
2. **O-DRV4 chat pulse every 120s (script-proofed)** — post 2–5 lines in
   chat, then `bash tmp/v9-chat-pulse.sh <tick-ts>` with the same text
   (body + transcript fidelity). Ack-only is invalid. Driver must be
   running (`tmp/v8-driver-loop.sh` / `v9-ensure-driver.sh`); if DOWN,
   start it. Silence / fake ack is P0.
   **O-WAKE-CATCHUP / O-REVIEWDOC (script-proofed)** — every wake tick and
   every material lead action must update `tmp/KAI-WAVE4-REVIEW.md` (active
   Wave 4 shared review with Opus; Wave 1–3 docs are frozen archives). Absorb
   *all* review-doc sections after **your** last `### Implementing note`
   (not only the final heading). Wake refreshes
   `tmp/V10-REVIEW-SINCE-LAST.md` and opens
   `tmp/V10-REVIEW-CATCHUP-PENDING.md` when unabsorbed content exists; clear
   only via `bash scripts/track-b/v10-review-catchup.sh ack` after a newer
   Implementing note that passes the lead-note contract (below). Memory /
   operator reminders are not the control.
   **Lead agent = Grok** for Wave-4 petclinic Track B. Every Implementing
   note MUST:
   1. Identify the writer: `**Agent:** Grok (lead)` in the body (and prefer
      heading suffix `— Grok (lead)`).
   2. List what was reviewed/acted on from other agents:
      `**Reviewed:**` bullets and/or stable `ACK:W4-NNN` / `ACK:R-NNN` /
      `ACK:F-NN` / `ACK:O-*` tokens.
   3. State live run action taken (or "watching only") so the doc is the
      audit trail — chat pulses alone are insufficient.
   4. Close with `— Grok (lead)`.
   `v10-review-catchup.sh ack` refuses notes missing Agent/Reviewed|ACK.
   **O-DRV6 / O-DEBTFRZ** — debt RED freezes the supervisor (no next task).
   **O-DRV3/5/7 clears** — only via `scripts/track-b/v9-clear-*.sh` (see
   `scripts/track-b/README.md`). Bare SHA files do not clear.
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
   (`tmp/docs-archive/V9-QUALITY-GATE.md` for completed V9; new runs use
   `docs/V*-QUALITY-GATE.md`). No silent stage push.
6. **Bank durable defects immediately** in the active polish bank
   (`tmp/docs-archive/V7-FUTURE-IMPROVEMENTS.md` for V7–V9; new runs open a
   fresh `docs/V*-FUTURE-IMPROVEMENTS.md`)
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
12. **O-IDLEWSFP — dual idle clock.** Review / wake idle ladders that decide
    whether the *run* is stalled must key on **`workspace_fp` alone**
    (HEAD + outer/supervisor liveness + story-state / outer-loop.log).
    `harness_fp` / project dirty / monitor_fp reset an *agent-implementing*
    clock only — they must not clear `run_idle` while the specimen is stuck
    (Wave4 W4-023a: harness edits masked Sonar-401 sfix stall). Helper:
    `scripts/track-b/v10-idle-clock.sh`. **O-HARNESSFP-POD:** `harness_fp` is
    `hash(host_fp|pod_fp)` so pod harness sync is visible agent activity and
    refreshes poll `last_activity` without touching `idle_note_level`.

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
- Clearing O-DRV3 pending without a corresponding quality-gate entry
  (`tmp/docs-archive/V9-QUALITY-GATE.md` for V9).
- Hand-fixing the live app to green and moving on without durableize + re-run.
- Logging an escalation without reading Qwen/OpenCode logs for why the worker failed.
- Closing an escalation because MiniMax committed GREEN, without durableize + retest.
- Hardcoding Coolstore cart–specific identifiers into harness “durable” fixes
  that should work for the next Spring Boot → Quarkus app.
