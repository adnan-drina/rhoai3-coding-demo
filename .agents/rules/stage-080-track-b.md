---
name: stage-080-track-b
skill-group: Demo Environment
applies-to:
  - stages/080-ai-autonomous-migration/**
  - docs/V7-FUTURE-IMPROVEMENTS.md
  - docs/V8-QUALITY-GATE.md
  - docs/V*-*.md
  - "**/quarkus-migration-scaffold/**"
---

# Stage 080 Track B — quality over throughput

North star: a **hardened, durable** autonomous migration harness. Honest
progress beats stage count. Abort and bank beats nursing a compromised run.

## Always-on constraints

When driving, monitoring, or changing Track B (Hermes outer-loop, supervisor,
sensors, scaffold skills, live migration workspace):

1. **Read and follow** `.agents/skills/stage-080-quality-advance/SKILL.md`
   before any of: M5 ship / push, marking a story complete, starting the next
   story, or restarting the outer-loop after a milestone that looks "done."
2. **Do not advance on green sensors alone.** Sensors catch many classes of
   failure; they miss ceremonial commits, empty harvests, placeholder tests,
   and plan defects. Substance review is mandatory.
3. **Record every advance-gate decision** in `docs/V8-QUALITY-GATE.md` (or the
   active run's successor gate file) with verdict `ADVANCE` / `HOLD` /
   `ABORT`. No silent stage push.
4. **Bank durable defects** in `docs/V7-FUTURE-IMPROVEMENTS.md` (or successor)
   when the review finds a harness/plan/sensor gap — then implement open bank
   rows before the next restart (see AGENTS.md "Before each new migration run").
5. **Prefer abort/HOLD over throughput.** If delivery does not meet story
   acceptance or brief substance, stop the harness; do not "fix forward" into
   the next story.
6. Human GO is **not** required for advance. The agent owns the quality loop
   and may ADVANCE only after a written review concludes the delivery is
   honest and durable enough. Surface the decision to the user; do not wait
   idly for permission unless the user paused the run or the verdict is HOLD
   pending work the agent cannot finish alone (secrets, cluster outage).

## Anti-patterns (forbidden)

- Skipping task/story substance review because the tick log says GREEN.
- Resuming straight into M5 ship / next story after polish without a gate entry.
- Treating "already committed / skipped" as quality evidence.
- Leaving open bank items for "after the demo."
