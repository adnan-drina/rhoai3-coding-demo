
---

## E-20260813T211435Z — 2026-08-13T21:14:35Z — decide — M2 SIMPLIFICATION DESIGN: it is bloated for four identifiable reasons, three of them fixable — Operator (via Deputy)

**Needs:** Operator:rule-m2-simplification(E-20260813T211435Z) — DESIGN; Lead:none-yet (v14 design, NOT mid-chain)
**Done:** Deputy:design-m2-simplification — CLOSED
**Re:** E-20260813T144954Z, E-20260813T201506Z

Operator: *"make it cleaner and simpler — currently feels bloated and chaotic."*
Agreed. Deputy names **why**, then proposes cuts. **Not to be actioned
mid-chain** — M2b is running.

### The measured bloat

| Surface | Now |
|---|---|
| Pre-dispatch gates | **6**, on *every* phase |
| `check-spec-readiness` scripts | **21**, spanning **4+ concerns**, **9 attach points** |
| M2 phases | **2** (M2a/M2b) — a *context-budget* workaround, not a domain boundary |
| Skills on M2a | 3 — one attached for **path resolution**, not need |

### Cause 1 — one skill is four skills (already ratified, not yet done)

`check-spec-readiness` fuses **body legality** (`check-kanban-body` + 12 typed
`BODY_*` codes, ordering, semantic-exits, surgical-scopes, operand-count),
**partition coverage**, **Class A closure asserts** (dependency/interface/mint
constraints), **mutating stampers**, **quarantine lifecycle**, and **three
dependency preflights**.

Research called this "fused along *everything the SDD lifecycle needs*, not one
concern" — the least defensible axis. **R-SK.14 already ratifies the split**:
guidance keeps `check-readiness.sh` + `check-kanban-body.py`; the Class A
asserts and stampers move to `.hermes/enforcement/`. **Do it — the ruling
exists, the work does not.**

### Cause 2 — gates are universal when their meaning is phase-specific

All **6** pre-dispatch gates fire for **M1, M2a, M2b, M3, M4, M5** alike. But:
`check-s008-resurrection-order` is about **M3 partition ordering**;
`assert-quarantine-tombstones` matters where quarantine can resurrect;
`check-phase-input-manifest` is *already* phase-parameterised.

**Proposal: declare gates per-phase in `phase-dispatch.yaml`** alongside
`skills[]`, instead of a hardcoded chain in `dispatch-phase.sh`. Same
protection, applied where it means something, and the chain becomes **data, not
script** — which is also what AD-016 wants when `dispatch-phase` shrinks to
templates.

### Cause 3 — a skill is attached to fix a path bug

M2a attaches `scan-with-mta` **not because the agent needs it**, but so
`check-findings-handoff.py` resolves via `skill_view` (comment in
`phase-dispatch.yaml`). That script is the **broken sibling shim** Research
found — it belongs to `scan-with-mta` outright and its local copy resolved a
dead path for weeks.

**Fix the shim, drop the attachment.** M2a then carries **2** skills, both
genuinely used. **An attachment that exists to satisfy a resolver is not a
skill — it is a workaround wearing a skill's clothes.**

### Cause 4 — the M2a/M2b split is a symptom, and should be re-tested (not removed yet)

The split exists because one worker could not hold partition **and** SDD emit
**and** create-m3 within the turn budget (R-AB.2). **That was a real problem and
the split solved it.**

But causes 1-3 all *reduce what M2 loads*. **Deputy does not propose merging
now** — it would trade a clean cut for a context risk we have measured before.
**Re-test after 1-3 land**: if M2 fits in one phase, merge; if not, keep the
split and stop treating it as debt.

### What "simpler" looks like after this

- **M2a:** 2 skills · phase-scoped gates · partition + briefs
- **M2b:** 2 skills · phase-scoped gates · SDD emit + create-m3
- **`check-spec-readiness`:** ~6 guidance scripts an agent reads; the rest
  enforcement the harness runs
- **gate chain:** declared in `phase-dispatch.yaml`, not hardcoded

**Deputy's honest note:** none of this is new capability — it is removing
workarounds that were each individually reasonable. The bloat is **accreted
mitigation**, exactly like the incident-named fixtures and the R1-R8 register.
That is the harness's characteristic failure mode, and it is worth naming as
such.

### Sequencing

**v14 design work. Do not touch mid-chain.** Cause 1 is already ratified and can
ride the enforcement-tree completion; causes 2-3 need an Operator ruling; cause
4 is a measurement after the others.

— Operator (via Deputy)

---

## E-20260813T211843Z — 2026-08-13T21:18:43Z — decide — OPERATOR: remove the M2a/M2b split. Deputy proposes removing it by MOVING THE MINT OUT, not by merging two workloads into one worker — Operator (via Deputy)

**Needs:** Operator:choose-m2-removal-path(E-20260813T211843Z) — DESIGN; Lead:none-yet (v14)
**Done:** Deputy:design-m2-split-removal — CLOSED
**Re:** E-20260813T211435Z, AD-016

**Operator: remove the M2a/M2b split.** Deputy had proposed re-testing after
other cuts (E-20260813T211435Z). **The Operator's instinct is better** — but the
*method* matters, and a naive merge would re-create the problem the split was
invented for.

### Why the split exists — read the reason precisely

`phase-dispatch.yaml` calls it a **"turn-volume cut"** (R-AB.2), not a context
overflow. That distinction decides everything:

- **Context problem** → reducing loaded skills fixes it → merge is safe.
- **Turn-volume problem** → the *work* is too big for one worker
  (`max_runtime_seconds: 3600`, tool-loop guardrail) → **reducing skills does
  not help**, because partition + SDD emit + minting **13 story cards** is still
  the same amount of work.

It is the second. **So a straight merge trades an ugly phase boundary for a
worker that may not finish** — and M2 is the phase that mints every M3 card, so
a timeout there is expensive.

### The clean removal — take the MINT out of the worker

M2b does two unlike things: **emit SDD artifacts** (spec/plan/tasks) and **mint
the M3 children** (create-m3). Only the first is agent work.

**Minting is orchestration**, and this harness already has a ruling heading that
way: **AD-016 orchestrator-owned mint** — `kanban_create` belongs to the
orchestrator toolset, with `dispatch-phase` shrinking to templates.

**Therefore:**

| Today | Proposed |
|---|---|
| **M2a** partition + briefs | **M2 PLAN** — partition, briefs, SDD emit (one worker, one phase) |
| **M2b** SDD emit **+ create-m3** | mint moves to the **orchestrator**, driven by the partition artifact |

**The split disappears because the second half stops being a worker phase at
all** — not because two workloads were crammed together. M2 rejoins M1/M3/M4/M5
as a single phase, and the M-stage model becomes uniform again.

### Why this is better than merging

1. **Turn volume genuinely drops** — the worker no longer mints 13 cards; it
   produces one partition + briefs + SDD artifacts.
2. **It composes with the cuts already ratified** — skill split (R-SK.14),
   phase-scoped gates, dropping the `scan-with-mta` shim attachment.
3. **It aligns with AD-016** instead of fighting it. `dispatch-phase` is already
   the v14 retirement target and already sits in `.hermes/enforcement/`.
4. **Deterministic minting** — cards created by the orchestrator from a
   validated partition are reproducible; cards created by an LLM mid-session are
   the mint-gate-bypass class we hit in v13 (9 cards born running, 4 oversized).
5. **It makes the story-id persistence trivial** — the orchestrator holds the
   partition and writes the id into every card body, which is the fix that makes
   an "N/N done" claim auditable.

### The honest risk

The orchestrator must then own **story sizing / FIS** and the
`assert-mint-constraints-complete` checks that today run inside the worker's
skill. That is a **transfer of responsibility, not a deletion** — and it must be
designed, not assumed. This is the single reason Deputy would not do it
mid-chain.

### Operator's choice

- **(A) Move the mint out** (Deputy recommends) — split removed, uniform
  M-stages, aligned with AD-016, deterministic minting.
- **(B) Straight merge** — simplest to describe, but re-creates the turn-volume
  problem the split solved, in the phase that mints every downstream card.

**v14 design work. M2b is running — do not touch the live chain.**

— Operator (via Deputy)
