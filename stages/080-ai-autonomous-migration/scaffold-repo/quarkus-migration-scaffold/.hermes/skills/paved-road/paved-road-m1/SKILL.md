---
name: paved-road-m1
description: >
  Use at M1 ANALYZE as the kind index. Pin only --skill paved-road-m1.
  Follow steps.json in order (skill_view subskills; native
  kanban_attach.py): freeze the original source, capture build evidence,
  JDK-model inventory, optional bytecode enrichment, Spring context probe, MTA
  8.2 scan, then assemble evidence-bundle.json. Happy-path terminator is
  kanban_request_review, not kanban_complete. kanban_block for
  external/platform failures (MaaS 500, missing key, GPU) and for an
  unpinned mandatory tool. Do not pin the producer leaves on the card. Do
  not use for M2 PLAN, M3, or M4.
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; Java 21; Maven; Hermes Kanban
metadata:
  author: rhoai3-harness-team
  version: "2.0.0"
  hermes:
    tags:
    - paved-road
    - m1
    category: paved-road
    kind: guidance
---
# M1 ANALYZE paved-road (index)

This skill is the **M1 procedure index**. Ordered mandated steps live in
`steps.json`. `audit.json` is generated from that file — do not edit it
by hand. Do not copy subskill SKILL.md bodies into this file.

Pin **only** this leaf (`--skill paved-road-m1`). Subskills load via
`skill_view` from the step list. Producer of artifact `m1-analyze` is
`assemble-evidence-bundle` (`evidence/planning/evidence-bundle.json`),
the root of the planner digest chain (SAD §6).

## When to Use

- This card is **M1 ANALYZE**.
- **Not** M2 PLAN (`paved-road-m2`).
- **Not** dest-init mint (`dispatch-phase`).

## Procedure

1. Read `steps.json`. Follow that listed order:
   freeze → build → JDK-model inventory → bytecode (optional) → context probe
   → MTA → assemble → derive the scenario corpus → capture the source →
   qualify the captures → the same three again for the source's **enabled**
   security setting → handoff facts → attach.
   - `skill` — `skill_view` that leaf and follow its SKILL.md.
   - `native` — run the named script under `.hermes/kernel/`
     (`handoff_facts.py --root /projects/modernized --phase m1 --write`,
     `kanban_attach.py --task "$HERMES_KANBAN_TASK" --exec`).
2. KEEP paths on the step must exist under the workspace root.
3. A producer that records `status: unpinned` (structure extractor) or a build that
   records `outcome: failure` is **evidence**, not a defect to repair.
   A qualification verdict of `FAIL` or `INCONCLUSIVE` is the same kind of
   thing: a recorded fact about the **source**, which becomes a coverage gap
   at M4 and never a destination card. The step is red only when the gate
   could not judge at all (no corpus, no capture, a provenance that does not
   bind).
   extractor unpinned / JDK mismatch → `kanban_block` (kind `needs_input`, the pin is an
   ADR). Build failure → continue; the ledger makes it planning-only.
   The three `-enabled` steps are the same kind of thing: with no
   `security:` section in `decisions.yaml`, or with a declared credential
   this workspace does not hold, each writes its receipt with `status:
   idle` and the reason and exits 0. That is a **recorded blocker**
   (ADR-014), not a red step and not silence. The reason names the missing
   environment **variable**, never a credential.
4. `bash .hermes/skills/harness/dispatch-phase/scripts/autostart-migration.sh --root /projects/modernized --after-m1 "$HERMES_KANBAN_TASK"`
   — binds the platform-recorded pilot authorization (dest-init wrote who
   authorized this run from the DevWorkspace its creator started) to the
   bundle you just produced, and mints M2. It decides nothing: an unbound
   seal with no named authorizer, one already bound, one not recorded by the
   platform, or an unfit bundle are all refused, and admission still gates
   the plan. Mints nothing under a not-activated planner; idempotent.
   `--after-m1` validates this existing native M1; the workspace startup
   preference cannot silently skip its continuation. The reviewer checks
   the M2 task, workspace and parent edge, not just the command exit code.
5. Happy-path terminator: `kanban_request_review` (reviewer `reviewer`, with the
   summary and metadata below), then end the turn. A later nudge to finish is already satisfied by the review handoff; do not answer it with `kanban_complete` (K2 refuses it for the implementer) or `kanban_block`.
6. `kanban_block` for external/platform (MaaS 500, missing key, GPU).
7. Reviewer runs `python3 .hermes/skills/paved-road/paved-road-m1/scripts/assert-paved-road-audit.py --root /projects/modernized "$HERMES_KANBAN_TASK"`.
   Under the reviewer profile the audit also compares the current handoff
   (the latest implementer run, which must have requested review) with the
   facts recomputed from the sealed artifacts; a missing or different
   `metadata.facts` or `metadata.factual_summary` is a red audit, and the
   reviewer requests changes (another run of this card), never completes.
   The official log is `$HERMES_HOME/kanban/logs/<id>.log`. Do not pass `--log` unless that file exists; a workshop path such as `/projects/modernized/kanban/logs/` is not the official log (v9 M1 `t_e84503a8`).

## Progress and review handoff

- **Attachments.** The `kanban-attach` step attaches the KEEP evidence set to
  this card (native attachments, listed by `kanban_show` and in the worker
  context): the evidence bundle, findings handoff, inventories, required
  extensions and MTA findings. The script fixes the set and the 25 MiB cap;
  the attachment tool alone does not satisfy the audit. With `--exec` it reads
  the native records back and exits 1 unless every file is held with its
  workspace bytes; the audit reads the same records (`hermes kanban
  attachments <task> --json`). File names in `metadata.attachments` are not
  proof.
- **Milestone comments** (`kanban_comment`, at most three, factual, never one
  per command): after the MTA scan (findings count and any unpinned
  producer), after the source captures (scenarios captured and qualified, the
  enabled-mode status), and for a discovered coverage gap or blocker.
- **Review request.** `summary`: two or three sentences a person can act on —
  what the evidence establishes about the legacy application, the capture
  coverage, and the gaps M2/M4 inherit. `metadata`: `attachments` (the
  attached file names), `evidence_bundle`
  (`evidence/planning/evidence-bundle.json`), `captures` (per security mode:
  captured / qualified / idle with its reason), `m2_card` (the id
  `autostart-migration.sh --after-m1` created), `coverage_gaps`,
  `limitations`, and **verbatim** the `facts` and `factual_summary` that
  `handoff_facts.py --phase m1 --write` printed (bound to this task, this run
  and the evidence bundle). The narrative explains; it never restates a count
  differently. The facts keep four numbers apart: entry points by kind;
  read-oracle coverage (a read captured, or why not: a write needs a
  scenario, a wildcard route needs a request fixture); scenario coverage per
  security mode (only a captured scenario of that entry point whose
  qualification PASSED, in a mode bound to this bundle and corpus); and the
  entry points left unverified. A source qualification FAIL is source
  evidence, not a pass. Only a **non-HTTP** entry point needs an operator
  observation (v23 M1 called 20 HTTP gaps scheduled/messaging/lifecycle work).

## Gotchas

- Do not invent HTTP routes: paths come from the frozen source and its
  inventories.

- Silence fails. An unmatched `[exit 1]` on a mandated needle fails.
  A later clean invocation of the *same* needle clears an earlier red.
  Do not last-wins across different needles.
- `inventory-legacy-surface` precedes `scan-with-mta`: the MTA handoff
  refuses (AR-4.1) without `evidence/entry-point-inventory.json`.
- Build evidence comes first, and its warm-up runs the same
  `dependency:build-classpath` goal the offline extraction runs. An empty
  offline classpath is recorded in the build receipt's reasons and makes the
  structure partial. Do not work around it.
- The scenario corpus and its captures are bound to THIS tree's evidence
  bundle: entry-point ids change when M1 resolves more of the source. A corpus
  derived against another bundle, or a capture naming another entry point, is
  refused as a stale binding. Re-derive and re-capture; never relabel.
- `derive-legacy-boot3` is **not** an M1 step. The baseline is the
  frozen original source; a Boot 3 derivation is an execution-side
  transformation only.
- Path mention / grep / cat of a SKILL.md is not `skill_view`.
- Do not `kanban daemon --force`.

## Self-test

`python3 scripts/selftest.py` (golden only, never on a card): steps.json ↔ audit.json sync, order contract, fixture PASS/REFUSE set, and the paved-road coverage lint.
