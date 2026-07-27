# Harness audit: division of labor, obsolete code, remaining improvements

Written 2026-07-27, immediately after cart run #2 shipped. Every number
below is measured from that run's artifacts (`/tmp/supervisor-metrics.csv`,
`/tmp/supervisor-events.csv`, `opencode.db`, the cart repo's commit
ledger `9c18fcd..HEAD`), not estimated.

## 1. Who does the migration work?

The concern examined: *has supervisor.sh taken on so much that Hermes is
losing its value?* The measured answer is no — the supervisor authored
none of the migration; but the audit did find judgment **text** leaking
into the supervisor, and a real ceiling on what Hermes is allowed to
learn. Both are addressed below.

### Time (run wall clock 21:47 → 05:50, ~8.1 h)

| Actor | Time | Share |
|---|---|---|
| Hermes orchestrator sessions (M2) | 45 sessions, 6.5 h | ~81% of wall clock |
| OpenCode worker sessions (27B) | 18 sessions, 51 min | inside orchestrator sessions |
| Supervisor script execution | seconds per transition; it *waits* the rest | <1% |
| Operator interventions | the balance (~1.5 h incl. analysis) | — |

### Commits in the shipped repo (53 total)

| Author class | Commits | Content |
|---|---|---|
| Model sessions (Hermes ± worker) | **37** | The plan (3 Phase B commits), all 29 task commits, 3 autonomous sensor-fix commits, Phase D, Build fix r1 |
| Operator | 10 | Mostly boundary completions: commit-step-only closures of green session work (3), the T-008 pom repair, package-identity consolidation, T-027 fabrication reversal, ship surface |
| Supervisor script | 4 | Phase A file copy, one checkpoint, two run reports |
| Harness meta (operator, non-app) | 2 | in-run harness syncs |

Every line of migrated production code, every mapping decision, the
spec, the plan, and 1,153 of the ~1,400 test lines are model-authored.
The supervisor's own commits contain zero domain content.

### What supervisor.sh actually is (line audit, ~510 lines)

| Block | ~Lines | Nature |
|---|---|---|
| Phase E ship mechanics (push, pipeline watch, triage, evidence export, acceptance curls) | 150 | process |
| Session lifecycle (dispatch, timeout, metrics, failure classification) | 70 | process |
| Loop control + resume (committed ledger, task iteration) | 80 | process |
| Prompts passed to Hermes | 60 | **contract + some leaked judgment (see §3)** |
| Post-commit verification dispatch, milestone cadence | 50 | process |
| Phase A file mechanics, reporting, helpers | 100 | process |

It never chooses a mapping, never edits code, never rewrites the plan.
Failure *classification* (quota vs stall vs no-commit; build vs gate vs
deploy) is deterministic triage — pattern matching on logs and task
names, the automatable part of what the operator was doing by hand in
runs #1–2.

### Verdict on the concern

The supervisor did not take migration work FROM Hermes — runs #1–3 show
the same work being done by the *operator* (manual retries, manual gate
diagnosis, manual ship). The supervisor mechanized the operator's
process labor, not the model's judgment labor. The evidence that Hermes
gained rather than lost: run #2 under the strictest supervisor produced
the first style-clean factory arrival, the first honest failing-metric
self-report (T-028), and the first shipped migration — because closed
feedback loops let model judgment land instead of drowning in process
noise. 33 of 45 sessions succeeded on attempt 1; the supervisor's
classification saved 4+ sessions from being burned by platform faults.

## 2. The real Hermes-value ceiling (recommendation)

Hermes only ever sees ONE session at a time; the cross-run learning —
retros, harness diffs, rule authoring — is done by the operator. That is
the actual sense in which "Hermes loses value": it executes but does not
learn. If we want to move up a level, the next experiment is a
**Phase F retro session**: after ship, the supervisor hands Hermes the
run report, events CSV, and skill files, and asks for proposed diffs to
EXECUTION/PLANNING/MAPPINGS (operator-reviewed before merge). That moves
the improvement loop itself into the agent — the highest-value seat we
have not yet given it. Low risk: it is a read-and-propose session.

## 3. Judgment leakage found (and the cleanup rule)

Three places where advice text (judgment) lives in the process layer;
all should move to the skill so the layering principle stays true:

1. Gate evidence (`gate_violations` coverage block) embeds test-writing
   rules ("mock external boundaries only…"). Evidence files should carry
   DATA; the rules belong in SHIPPING.md/EXECUTION.md, which fix
   sessions already read. (Introduced by the operator during run #2 —
   worked, but sets a bad precedent.)
2. The acceptance-failure evidence advises the design ("add a minimal
   index page…"). Same treatment: state the failing contract, point at
   SHIPPING.md.
3. The Phase B prompt embeds format mandates (heading form, id padding)
   that the lint already enforces deterministically — redundant text
   that drifts (it still says '### T-NNN' while both parsers accept
   depth 2–6). Prompts should carry scope + commit contract; format
   law lives in the lint.

Rule going forward: **supervisor text = scope, contract, evidence
pointers. All "how to do it well" text = skill files.**

## 4. Obsolete / defective code found by the audit

| Finding | Class | Status |
|---|---|---|
| `MAX_FACTORY_ROUNDS=4` declared, used nowhere (superseded by per-class `MAX_PER_CLASS`) | obsolete | removed |
| Task-id grep `#{3,6}` vs lint `#{2,6}` — a `## T-001:` plan passes lint then FATALs the task loop | latent run-killer | fixed + parity test (suite case 12) |
| "task sensor is RED" log line hardcoded `task` even when the milestone sensor fired | log accuracy | fixed |
| Sonar violation-export python exists 3× (sensors inloop, sensors full, supervisor gate_violations) | duplication | open — consolidate into one `sonar-report.py` helper next touch |
| `RUN_CONTRACT` worker-model line is sent to sessions that never dispatch workers (fix sessions) | harmless noise | leave |
| Phase A kantra fallback path — unexercised in all five runs (IDE analysis always present) | untested path | leave (correctly FATALs when both sources missing), noted |
| `boot_check` hardcodes `/q/health` — correct only while root-path stays default | coupling | guarded by the PLANNING root-path rule; acceptable |

## 5. Standing improvement queue (post-audit)

1. Phase F retro session (§2) — the Hermes-value experiment.
2. Consolidate the sonar-export python into one helper (§4).
3. Move the three leaked advice texts into SHIPPING.md (§3).
4. Worker-seat utilization: 18 worker sessions / 51 min in an 8 h run —
   the 27B seat is cheap and now reliable (subagent ban held: zero
   1-second deaths this run). EXECUTION.md could push more mechanical
   packet classes to the worker; economics, not correctness.
