# ADR-32 — Harness-driven PROFILE decide loop (`O-PROFSEATARCH`)

**Status:** Accepted — implementing (operator GO 2026-08-05 wipe)  
**Date:** 2026-08-05  
**Supersedes (scheduling):** MiniMax N=20 mchat batch seats (`O-PROF1OF79STOP` containment)  
**Keeps:** ADR-26 projection, ADR-29 typed SoT, ADR-31 anchor SELECT, O-DECISIONWRITEDROP upsert

## Context

`O-PROF1OF79STOP` sliced PROFILE into repeated Hermes/MiniMax sessions of
`--limit 20` undecided units. That contained rate-limit and megapatch failure
modes, but it is **seat scheduling**, not a PROFILE architecture: each seat
re-ingests a fat DERIVED FACTS prompt, exits at the batch boundary
(`hermes_rc=0`), and outer starts another mchat. Operator dissent (W5-072):
that is a plaster.

With ADR-26/29/31 + upsert, the remaining per-unit work is small:
**SELECT one projected anchor + HARVEST|REDESIGN + rationale → upsert.**


## Why batch seats do not fix MiniMax quota

MiniMax MaaS limits are **hourly** (and related burst/429 behavior), not
per-Hermes-session. Splitting PROFILE into N=20 mchats does **not** increase
available quota — it often **increases** spend (repeated fat DERIVED FACTS
prompts + session overhead) while still concentrating the same classify work
into the same hour. Live proof 2026-08-05T14:38Z: containment run hit
`O-PROF1OF79STOP` MiniMax rate-limit mid-batches and `fail_run` stopped at
41/79 credited — batching did not save the stage.

The durable fix is **spend MiniMax less** (harness loop + Qwen classify), not
more MiniMax seats.

## Decision

Replace multi-seat MiniMax batching with a **harness-owned decide loop** that
runs until the typed-decision coverage floor (or undecided empty):

```
emit/refresh profile skeleton + §§1–6  # optional: one prose seat (model TBD)
profile_roles.init
while undecided profile-units and credited < floor:
    unit ← next undecided (stable order from model)
    anchors ← ADR-31 projection (cap small)
    (role, rationale, evidence) ← classify(unit, anchors)   # tiny call
    profile_roles.upsert(...); refuse non-members
    every K units or end: profile_close + rubric snapshot
commit when floor met (or STOP_AFTER_M1 hold)
```

### Classify backends (pluggable)

| Mode | When | How |
|------|------|-----|
| `opencode-qwen` | **Happy path** (operator 2026-08-05) | OpenCode returns JSON judgment; harness upserts (`O-PROFCLASSIFYVAL`) |
| `hermes-orch` | Escape / judgment fail | **Per-unit** after primary retries (`O-PROFCLASCESC`); also run-level `--backend` |
| `dry-run` / fixture | Instruments | Deterministic stub |

Env:

- `PROFILE_DECIDE_ENGINE=harness-loop` (default) vs `batch-mchat` (legacy containment)
- `PROFILE_CLASSIFY_BACKEND=opencode-qwen|hermes-orch`
- `PROFILE_CLASSIFY_ESCALATE_BACKEND=hermes-orch` (default for opencode; `none` to disable)
- `PROFILE_CLASSIFY_MAX_UNITS=1` (default; hard cap ≤3 aligned with upsert)

### What stays one LLM seat

- Architecture-profile **§§1–6** prose (intent, contracts) may remain a single
  orchestrator or worker seat.
- **§7 is never authored** — still rendered from `model.units[].decision`.

### What goes away

- Outer `m1-profile-batch-N/6` MiniMax mchats as the primary decide path
- Asking one chat to "finish the listed 20 then exit" as the unit of progress

## Consequences

- Wall-clock and quota track **unit count**, not **number of Hermes sessions**
- Qwen trial (W4-466) becomes the natural first backend: task is SELECT+enum
- MiniMax reserved for §§1–6 and classify backstop, not the happy path
- `O-PROF1OF79STOP` rate-limit refuse-a2 remains useful as a guard if any
  mchat path is still used; batch-of-20 ceases to be the architecture

## Validation (next wipe)

1. Instruments: harness loop walks fixture undecided → upsert → coverage
2. Live `STOP_AFTER_M1` with `PROFILE_CLASSIFY_BACKEND=opencode-qwen`
3. Compare to MiniMax containment tip: `evidence_miss`, HARVEST/REDESIGN split
   (`O-PROFHARVESTBIAS`), wall-clock, drops
4. Dual ACCEPT before M2

## Non-goals

- Softening ADR-31 membership
- Wholesale `profile-decisions.json` rewrite
- Mid-seat sync while a containment run is live
