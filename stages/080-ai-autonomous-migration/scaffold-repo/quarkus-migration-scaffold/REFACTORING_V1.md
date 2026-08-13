
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
