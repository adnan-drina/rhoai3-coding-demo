# ADR-48 — Run state is migration data (REV-1)

**Status:** accepted (Grok lead + Opus W4-783; operator GO 2026-08-07)  
**Applies:** Stage 080 Track B harness run machinery  
**Related:** ADR-42 (gate ≠ scheduler), ADR-47 (one owner per model field), O-LIFECYCLEREOPEN, O-ADVANCETIPSHA, O-NULLACTIONREOPEN, O-DEBTTREE  
**Supersedes as policy:** `--force` ADVANCE→READY reopen; tip-as-restore-target; LLM escalation prose as completion writer

## Problem

ADR-47 required every field in `migration/model.json` to have exactly one owning phase. That rule was never applied to **run state** — `state`, `tip_sha`, debt rows, reopen records — which is written by multiple independent mechanisms and has gained authority over the working tree (W4-776…783).

Symptom class (not the defect list): *two or more writers, one fact, no reconciliation.*

## Decision — four rules

### (a) `tip_sha` is an observation, never an authority

- Records *what was produced* (attribution).
- Must never be a restore / reconcile target for Owns paths.
- Consumer asserts (`char_surface`, …) judge **working-tree / HEAD content**, or return `UNKNOWN` — they do not evaluate a stale tip blob as if it were the present.
- Harness paths that `git checkout <tip_sha> -- <owns>` to “keep the ledger tip” are forbidden (F-tip-not-authority).

### (b) Task state has exactly one writer; every change is a transition

- Ledger writer: `task_lifecycle.py` only.
- **Typed REOPEN:** `ADVANCE → READY` is a first-class edge requiring `reason ∈ REOPEN_REASONS` and incrementing `reopen_gen`.
- `--force` remains emergency-only and must not be the designed reopen path.
- Prior tip remains in `tip_sha` / `tip_history` as observation; completion is invalid while `state ≠ ADVANCE`.

`REOPEN_REASONS` (closed enum):

| reason | when |
|--------|------|
| `consumer_assert` | M4 consumer refuse (e.g. refuse-char) invalidated ADVANCE |
| `phase_rewind` | M4→M3 phase rewind |
| `replan_orphan` | M3 replan orphaned tip binding |
| `operator` | explicit operator reopen |

### (c) Debt is a projection / incident journal, not a parallel authority — **landed (O-DEBTADVANCE)**

- `state ∈ {ADVANCE} ∧ unresolved freeze-worthy debt` is **unrepresentable**: `task_lifecycle.py` refuses ADVANCE when `debt.md` has `## {tid} — (task|milestone|sonar|seat-budget) RED`; `completion_authority` rejects completion claims in that case.
- Freeze-worthy `record_debt` demotes via typed **ADVANCE→DEBT** (`lifecycle_debt`); tip_sha stays observation.
- `migration/debt.md` remains an append-only incident journal (module `debt_journal.py`) — not a second SoT for “must redo.”
- Full migration of debt into `model.json` is sequenced later (not required to close F-advance-debt).

### (d) Unresolvable task → `BLOCKED`; scheduler continues — **landed (O-BLOCKSCHED)**

- ADR-42: gate ≠ scheduler. A task that cannot proceed reports `BLOCKED` (with `blocked_on` / reason); the outer loop schedules other work.
- Seat exhaustion / `O-ESCNOCOMMIT` (no tip) → `lifecycle_blocked` + continue; **not** `/tmp/debt-freeze` kill.
- Sensor RED (`task|milestone|sonar|seat-budget`) still freezes via O-DEBTFRZ (honesty gate ≠ unresolvable).
- M4 end with any BLOCKED → `supervisor-done=tasks-blocked`; outer continues to next story; run end writes `outer-partial: tasks-blocked=…`.
- Loop exit must write a terminal marker distinct from crash (`/tmp/outer-loop-done` with typed reason). EXIT trap writes `outer-crashed:` when the marker is absent. Silence without marker is a defect.

## Completion authority (amendment #4)

LLM escalation prose (`/tmp/escalation-noaction-*.txt`) is a **request**, never a writer of task outcome.

Seat end-state is a typed verdict from harness probes:

| verdict | source |
|---------|--------|
| `DISPATCH` | must run (default) |
| `SKIP_ALREADY` | only `already-complete.py` exit 0 |
| `ADVANCE_OK` | ledger `ADVANCE` + tip observation + verify dims (+ kind-specific consumer assert) |
| `REJECT_COMPLETION_CLAIM` | prose claims “already complete” while `state ≠ ADVANCE` |

Module: `completion_authority.py` (SoT). `nullaction_reopen.py` becomes a thin adapter over that verdict (fence until prose paths are fully demoted).

## Falsifiers

- **F-tip-not-authority:** no harness happy path restores Owns from ledger `tip_sha`.
- **F-reopen-typed:** `ADVANCE → READY` without `reason ∈ REOPEN_REASONS` refuses; `--force` not required for reopen.
- **F-prose-not-writer:** already-complete-shaped null_action while `state ≠ ADVANCE` is rejected; supervisor continues the seat.
- **F-blocked-not-kill:** (d) — exhausted/escnocommit must not touch `/tmp/debt-freeze`; must `lifecycle_blocked` + continue; outer EXIT always leaves typed `/tmp/outer-loop-done`.
- **F-advance-debt:** (c) — ADVANCE while freeze-worthy `debt.md` RED for the same tid refuses; ADVANCE→DEBT is the demotion edge.

## Sequence

1. Suite baseline (`instruments.sh`) while run HOLD.  
2. Land (a)+(b)+completion authority.  
3. Land (d) scheduler/terminal marker — **done (O-BLOCKSCHED)**.  
4. Land (c) debt projection / ADVANCE∥debt unrepresentable — **done (O-DEBTADVANCE)**.

## Out of scope (named)

- `characterizes` edge retarget (interface vs impl) — specimen graph decision; separate bank.  
- Loop-repeat tree-object refuse (W4-780) — complementary commit gate; must not become a parallel “must redo” channel.  
- Widening phrase regexes on null_action — retired as policy by completion authority.

## Review bar

Patches that only detect force-reopen wording, or restore tips to match `tip_sha`, are **partial solutions** and must Verdict HOLD against this ADR.
