# M3 WAVE HOLDER

You mint story children. You do **not** implement dest code.
Do **not** write `src/` or `pom.xml`. Do **not** inventory `/projects/legacy`.
This card is not "M3 IMPLEMENT: bounded transform".

**Turn law:** reasoning ≤ 8 lines, then **one** command. First command is
the lint line in Job 1. Forbidden: "that's a lot, let me batch",
search_files loops, re-reading `phase-dispatch.yaml` to invent a
whole-wave write set. If lint or graph is wrong: block this turn, stop.

Phase: M3 mint (wave holder). Path-invoke
`.hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md`.
Do **not** declare `dispatch-phase` on this card (I-10 B / `25a7c1e9`).
Do **not** pin `one-three-one-rule` (I-11; path-invoke on escalation).
Do **not** attach `check-spec-readiness` until story bodies exist.

Workspace: `dir:/projects/modernized`.
Lint is `handover-mint.py --write` only — **no** `--parent`, **no**
`--ensure-wave-holder`. Halt `061824Z`. Mint **1088**.

## Files Writable

- evidence/bodies/
- evidence/briefs/
- evidence/derived/

## Fail-closed kind map (Architect `E-20260818T094316Z` / `094840Z`)

Dest-forbidden rewrite and A-8 planning refuse are **not** parent waits.
`dependency` self-clears (`dependency_wait` → `promoted`) and does **not**
count toward `BLOCK_RECURRENCE_LIMIT`. Wrong kind on a planning defect
cycles this card. Do **not** restore park-on-block-loop.

| Refusal class | `hermes kanban block --kind` | Why |
|---|---|---|
| A-8 refuse (`endpoints_multi` / `endpoints_uncovered` / lint exit 1) | `needs_input` | Defect is in `tasks.md`; do not dest-rewrite |
| Dest-forbidden rewrite (`tasks.md` outside write-set) | `needs_input` | OBJECT dest-rewrite |
| Missing parent / unsigned ack_gate | `dependency` | Auto-promotes when that parent completes |
| Mint growth / dest-rewrite impulse | do not | OBJECT; halt `061824Z`; mint **1088** |
| M4/M5 already children of this holder | `needs_input` | Holder complete would unpark VERIFY on empty dest |

Argv: **`--kind` before the task id**. Then `kanban show` must report
`status=blocked`.

## Job

1. Lint + assemble: `python3 .hermes/skills/harness/dispatch-phase/scripts/handover-mint.py /projects/modernized --write`.
2. On A-8 refuse or dest-forbidden rewrite: stop. Block this card
   `--kind needs_input`. Do **not** rewrite `tasks.md`. Do **not** grow
   the mint. Escalate with official `one-three-one-rule` (path-invoke;
   one problem, three options, one recommendation). Do **not** `--skill`
   pin it on this card.
3. If lint passes: create `ack_gate` first, then story children per
   `mint-m3-hermes.md`. Do **not** dispatch children here.
4. After children exist (or a typed `needs_input` block is recorded),
   `kanban_complete` this holder **only if** no child title starts with
   `M4` or `M5`. Otherwise block `--kind needs_input` (graph defect).
   The gate stays blocked.

## Constraints

- OBJECT dest-rewrite of `specs/**/tasks.md`.
- OBJECT mint growth past **1088**.
- OBJECT retired mint-m3-wave / `handover-mint.py --parent`.
- OBJECT a third tick on a sticky `needs_input` dest (v24 park).
- OBJECT implementing the whole `tasks.md` on this card.
- Serial GO is orchestrator `hermes kanban dispatch --max 1`, not this card.
