
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

---

## E-20260813T212742Z — 2026-08-13T21:27:42Z — decide — REVIEW COMMISSION: systematic Hermes-log analysis — are our skills actually loaded, used, and helping? Measured, not impressionistic — Operator (via Deputy)

**Needs:** Review:hermes-log-effectiveness-analysis(E-20260813T212742Z) — the commission
**Done:** Deputy:author-review-commission — CLOSED
**Re:** E-20260813T201506Z, E-20260813T134203Z

**Note on mode:** two-agent mode (E-20260813T184858Z) suspended Review. This
commission **re-activates Review for this task only**. Lead remains the sole
seat actor; Review reads logs, does not touch the seat or the tree.

---

## COMMISSION — Hermes log effectiveness analysis

### Purpose

Determine whether our skills are **loaded**, **used**, and **actually reducing
the agent's work** — and produce the evidence base for cleaning up and improving
the Hermes resources. This is **R-SK.8** (reasoning-driven skill evolution)
executed systematically instead of anecdotally.

### Corpus

All Hermes kanban logs for the **v17 seat** chain (`petclinic-rest-v17-refac`),
board `default`: **M1 `t_0a8d4092` · M2a `t_7d40349d` · M2b `t_bf6a59e8`**, plus
M3-M5 tasks as they complete. Read via `hermes kanban --board default log <id>`
(and `tail`/`watch` for live). Include the **Reasoning blocks**, not only tool
calls.

### THE RULE THAT MAKES THIS USEFUL

**Every finding carries a log locus** (task id + a quoted excerpt). A count
without loci is an impression. This campaign has repeatedly been misled by
green-looking summaries — *"7 self-corrections"* with no citations is worth
nothing; *"7, here are the 7"* is actionable.

**Do not grade the agent. Grade the resources.** The question is never "did the
agent do well" — it is **"did the skill spare it work, and if not, why not."**

### Metrics — count each, cite each

**A. Load and use**
1. Which skills were **attached** per task (card `skills[]`) vs **actually
   opened** (`skill_view` / hard-invoke)? **Attached-but-never-opened = dead
   weight in the selection triple.**
2. Which **references** inside a skill were opened (`references/*.md`)? A
   reference never opened across the whole chain is a retire candidate.
3. Any skill opened that was **not attached** (agent found it itself)? That is
   evidence the attach matrix is wrong.

**B. Did the skill help — the core question**
4. **Skill-then-act**: agent opened a skill and proceeded without further
   exploration. **This is the success case — count it.**
5. **Reasoning-that-a-skill-already-answered**: agent derived, searched, or
   deliberated over something present in an attached skill. Quote both the
   reasoning **and** the skill text it duplicates. **This is the highest-value
   finding class** — it means the skill exists but failed to reach the agent
   (wrong description? buried in a reference? not attached?).
6. **Guessing** — an assertion with no citation to evidence, packet, or skill;
   an invented path/API/class later corrected or refuted. Count and quote.

**C. Rework signals**
7. **Self-correction** — agent reversed or rewrote its own prior output within a
   task. Note whether a skill would have prevented it.
8. **Retries / repeated identical tool calls** — search thrash, re-reading the
   same file, re-running a failing command unchanged.
9. **Gate refusals hit** — which gate, and did the agent respond with a **typed**
   outcome (`needs_input` / BLOCK) or improvise around it?

**D. Cost**
10. Rough turn/tool-call count per task, and the share consumed by A5/B6/C7-8
    (i.e. **work a better resource could have removed**).

### Output

`source-analysis/hermes/20260813-v17-log-effectiveness.md`:

- `## Scoreboard` — one table: per skill → attached N · opened N · references
  opened · "spared work" instances · "should have spared work" instances
- `## Top findings` — ranked, each with task id + quoted excerpt + the resource
  change it implies
- `## Skill-by-skill disposition` — **keep as-is / fix description / move
  content / retire**, with the evidence for each
- `## Reasoning the skills should have prevented` — the R-SK.8 harvest: the
  concrete text that belongs in a skill next
- `## Method + limits` — what was and was not readable

### Constraints

- **Read-only.** No seat changes, no tree edits.
- **Specimen-agnostic** in recommendations (R-SK.5 is lint-enforced).
- **Report absence honestly** — "logs unreadable for X" is a finding, not a gap
  to paper over. Three postStart failures today were undiagnosable because
  output died with the pod.
- Distinguish **v17 (current, post-refactor skills)** from any v13 comparison —
  the skill tree changed substantially today (rename, enforcement split, two new
  skills, SOUL v2).

### Why this matters now

The Operator's original concern was that workers reason their way to things a
skill should have told them. **This commission measures that directly** and
turns it into a cleanup list. It is also the first read of the **rebuilt** skill
tree under real load.

— Operator (via Deputy)

---

## E-20260813T213321Z — 2026-08-13T21:33:21Z — decide — DEPUTY AUDIT M2: **ACK** — 13 stories, all park-at-birth, v13 defects not repeated. One agreed gap: `story_id` still absent from bodies — Deputy

**Needs:** Lead:land-streaming-pin-before-m3(E-20260813T213321Z) — **HARD, the M2→M3 gap is now**; Lead:add-story-id-to-body(E-20260813T213321Z) — **HARD, one field, do it before M3 writes**
**Done:** Deputy:audit-m2-output(E-20260813T213321Z) — **ACK**
**Re:** E-20260813T210050Z, E-20260813T180236Z, E-20260813T193314Z

M2a/M2b complete. Audited by execution against the live board and the produced
artifacts.

### ACK — M2 landed well, and the v13 defects did NOT repeat

**13 M3 stories minted, every one `blocked` at birth:**
```
S-001 Build foundation: Quarkus POM/BOM      S-008 REST: Vets/Specialties/Users
S-002 Application properties + profiles      S-009 Exception handling + validation
S-003 JPA entities → Panache                 S-010 Startup + health endpoint
S-004 Spring Data repos → Panache            S-011 Test infrastructure
S-005 CDI service layer                      S-012 Dev services + cache
S-006 Security + authentication              S-013 Logging + i18n
S-007 REST: Owners/Pets/Visits
```

| v13 defect | v17 result |
|---|---|
| 9 cards **born running** (mint-gate bypass) | **all 13 `blocked` at birth** — park-at-birth holds |
| 4 cards **oversized** (s-005 FIS=23) | REST **split across two stories** (S-007/S-008) — sizing applied |
| body drift | **26 files = 13 bodies + 13 `.sha256.json`** — body-immutability wired |

Ordering respects `sdd-ordering §S.6`: foundation → config → model → repo →
service → security → rest → exceptions → startup → test → devservices →
logging. **Deputy ACKs M2.**

### THE GAP — `story_id` is still not in the body

Body keys (`evidence/bodies/m3-s-001.json`):
```
task_id · role · phase · identity · refs · files_in_scope · files_writable
exit_criteria · rules · layer · dependencies · constraints
```
**No `story_id`.** The partition↔card correspondence lives **only in the card
title** (`S-001: …`).

Better than v13 — titles now carry `S-NNN`, so a human can reconcile — but
**nothing machine-readable links body to partition**, and a title is not a
stable identifier. This is precisely the hole that made v13's *"M3 9/9 done"*
**unauditable** (E-20260813T180212Z): the mapping was never persisted and the
seat that held it is gone.

**Ask: add `story_id` to the body in `create-m3-implementer.sh`.** One field.
It converts the final completion claim from an assertion into arithmetic —
`partition ids ⊇ completed card ids`. **Do it before M3 writes**, or 13 bodies
are already committed without it and the fix becomes a migration.

### The M2→M3 gap is NOW — streaming pin

Operator ruled (E-20260813T210050Z) the streaming pin is **not banked**: it
lands **after M2, before M3 dispatches**. **That gap is open.**

Order: **verify with `hermes kanban --board default watch` first.** If it
already streams, the work is only the **factory pin** — assert the default so a
Hermes upgrade cannot silently remove it; **do not touch the live seat**. Live
Managed Scope edits mid-chain are a real risk (re-read on every worker spawn, a
malformed edit takes out every later phase).

### Neither blocks M3 on correctness

Both are **agreed items scheduled for this exact gap**. M3 is otherwise clear:
13 parked stories, bodies digest-stamped, ordering sound.

**Deputy will audit M3 per story**, watching: skills actually opened vs
attached · `spring-to-quarkus-patterns` references used (incl. the new
`exception-mapping.md` at S-009 and `observability.md` at S-010) · typed BLOCK
rather than improvisation on refusal.

— Deputy
