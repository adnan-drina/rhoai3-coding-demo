# M3 WAVE HOLDER

Phase: M3 mint (wave holder). Path-invoke
`.hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md`.
Do **not** declare `dispatch-phase` on this card (I-10 B / `25a7c1e9`).
Pinned skill: official `one-three-one-rule` only.
Do **not** attach `check-spec-readiness` until story bodies exist.

Workspace: `dir:/projects/modernized`.
Lint is `handover-mint.py --write` only — **no** `--parent`, **no**
`--ensure-wave-holder`. Halt `061824Z`. Mint **1088**.

## Fail-closed kind map (Architect `E-20260818T094316Z` / `094840Z`)

Dest-forbidden rewrite and A-8 planning refuse are **not** parent waits.
`dependency` self-clears (`dependency_wait` → `promoted`) and does **not**
count toward `BLOCK_RECURRENCE_LIMIT`. Wrong kind on a planning defect
cycles this card. Do **not** restore `park-on-block-loop.py`.

| Refusal class | `hermes kanban block --kind` | Why |
|---|---|---|
| A-8 refuse (`endpoints_multi` / `endpoints_uncovered` / lint exit 1) | `needs_input` | Defect is in `tasks.md`; do not dest-rewrite |
| Dest-forbidden rewrite (`tasks.md` outside write-set) | `needs_input` | OBJECT dest-rewrite |
| Missing parent / unsigned ack_gate | `dependency` | Auto-promotes when that parent completes |
| Mint growth / dest-rewrite impulse | do not | OBJECT; halt `061824Z`; mint **1088** |

Argv: **`--kind` before the task id**. Then `kanban show` must report
`status=blocked`.

## Job

1. Lint + assemble: `python3 .hermes/skills/harness/dispatch-phase/scripts/handover-mint.py /projects/modernized --write`.
2. On A-8 refuse or dest-forbidden rewrite: stop. Block this card
   `--kind needs_input`. Do **not** rewrite `tasks.md`. Do **not** grow
   the mint. Escalate with official `one-three-one-rule` (one problem,
   three options, one recommendation).
3. If lint passes: create `ack_gate` first, then story children per
   `mint-m3-hermes.md`. Do **not** dispatch children here.
4. After children exist (or a typed `needs_input` block is recorded),
   `kanban_complete` this holder. The gate stays blocked.

## Constraints

- OBJECT dest-rewrite of `specs/**/tasks.md`.
- OBJECT mint growth past **1088**.
- OBJECT `mint-m3-wave.sh` / `handover-mint.py --parent`.
- OBJECT a third tick on a sticky `needs_input` dest (v24 park).
- Serial GO is orchestrator `hermes kanban dispatch --max 1`, not this card.
