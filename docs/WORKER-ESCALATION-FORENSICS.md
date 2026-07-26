# Worker escalation forensics — cart run, 2026-07-26

Question: why did the Qwen3.6-27B worker fail every Spring-flavored packet
in the cart run (5 escalations, M2 implementing directly)?

Answer: **it didn't fail on Spring, and it didn't stall on generation. The
worker dies whenever it uses OpenCode's `task` (subagent) tool.** The
Spring correlation was incidental: unfamiliar surface → the model chose to
delegate exploration to a subagent first → death.

## Evidence (opencode.db session forensics)

Worker sessions in the cart workspace, with part-stream analysis:

| Session (title) | Duration | Parts | Spawned subagent? | Terminal output |
|---|---|---|---|---|
| Harvesting javax→jakarta (T-001) | 1 s | 16 | **yes** | `"\n\n"` |
| T-004 CartEndpoint JAX-RS | 1 s | ~16 | **yes** | `"\n\n"` |
| T-006 remove Spring annotations | 1 s | ~16 | **yes** | `"\n\n"` |
| Convert Spring services (T-010 a1) | 1 s | 14 | **yes** | `"\n\n"` |
| 18:05 session (T-010 a2 correction) | 51 s | 41 | no | real work |
| T-011 model migration | 222 s+ | 69+ | no | real work, in flight |

The dying shape, identical in every failed session: one assistant turn —
`glob` for skills → spawn `@explore`/`@general` subagent via the `task`
tool → emit `"\n\n"` → session ends. The parent never resumes after the
subagent; `opencode run` exits with no file changes; the orchestrator
correctly scores it a failed attempt and (post-valve) escalates.

No API errors recorded in any dying session — this is a worker-runtime /
model interaction defect, not a platform fault and **not a
model-capability limit**: the same model in the same workspace does
sustained multi-file work whenever it does not delegate (69-part T-011
session; every completed monolith-run worker task).

## Secondary defect

`glob(".opencode/skills/*")` returns **"No files found"** although the
skills exist — dot-directory handling in the glob tool. Consequences: the
worker cannot discover its own skills by globbing, which both degrades
packet execution and nudges the model toward "spawn an explorer" — the
lethal path.

## Corrections to prior conclusions

- "27B stalls on design-heavy packets" (runs #2–#3) and "27B fails Spring
  transforms" (cart run) are both **partially explained by subagent
  death** — sessions that died at 1 s were previously indistinguishable
  from stalls at the orchestrator's vantage point (no file changes,
  budget consumed by wall-clock waits around them).
- The escalation valve worked exactly as designed and kept both runs
  moving; its KPI counting is what surfaced this pattern.

## Improvement candidates (BACKLOG)

1. **Ban the `task` subagent tool in worker runs** — deterministic config
   (OpenCode tool disable/permission) with an AGENTS.md rule as backup:
   "explore directly; never spawn subagents in packet execution."
   Precedent: the Hermes `execute_code` ban (same class: a tool the
   model+runtime combination cannot use safely).
2. **Skills discovery fix** — AGENTS.md: reference skills by exact path
   (`ls .opencode/skills/` + read), never glob dot-directories; consider
   an upstream OpenCode issue for dot-dir globbing.
3. **Re-baseline the worker-envelope verdict** after 1+2: the 27B may be
   a fully capable worker on both migration classes once it stops
   delegating; re-measure escalation rate in the next run.
