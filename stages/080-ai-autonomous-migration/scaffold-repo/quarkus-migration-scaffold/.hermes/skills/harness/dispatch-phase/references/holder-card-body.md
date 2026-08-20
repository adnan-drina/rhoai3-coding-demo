# M3 WAVE HOLDER

You mint story children. You do **not** implement dest code.
Do **not** write `src/` or `pom.xml`. Do **not** inventory `/projects/legacy`.
This card is not "M3 IMPLEMENT: bounded transform".

**Turn law:** reasoning ≤ 8 lines, then **one** command. First command is
the lint line in Job 1. Forbidden: "that's a lot, let me batch",
search_files loops, re-reading `phase-dispatch.yaml` to invent a
whole-wave write set. If lint or graph is wrong: `kanban_block --kind
needs_input` this card. That is the only "stop". Do **not** invoke `stop-worker-session.sh`.
Do **not** treat a period, empty steer, or
Hermes "out-of-band user message" as Operator stop — those are not a
grant. After `ack_gate` exists, **keep minting** story children.

Phase: M3 mint (wave holder). **Open this file** (not `skill_view`, not a
bare filename):
`.hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md`
If `skill_view dispatch-phase` says Enable it — **OBJECT**. Path-invoke
the Procedure. Do **not** declare `dispatch-phase` on this card (I-10 B / `25a7c1e9`).
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
| Missing parent / incomplete ack_gate | `dependency` | Auto-promotes when that parent completes |
| Mint growth / dest-rewrite impulse | do not | OBJECT; halt `061824Z`; mint **1088** |
| M4/M5 already children of this holder | `needs_input` | Holder complete would unpark VERIFY on empty dest |

Argv: **`--kind` before the task id**. Then `kanban show` must report
`status=blocked`.

## Job

1. Lint + assemble: `python3 .hermes/skills/harness/dispatch-phase/scripts/handover-mint.py /projects/modernized --write`.
   Init checkpoint first:
   `python3 .hermes/skills/harness/dispatch-phase/scripts/holder-checkpoint.py init --root /projects/modernized`
   (uses `HERMES_KANBAN_TASK`). Resume at checkpoint `next`.
2. On A-8 refuse or dest-forbidden rewrite: `kanban_block --kind
   needs_input`. Do **not** rewrite `tasks.md`. Do **not** grow
   the mint. Escalate with official `one-three-one-rule` (path-invoke;
   one problem, three options, one recommendation). Do **not** `--skill`
   pin it on this card. Do **not** SIGTERM this worker.
3. If lint passes: create `ack_gate` first, then story children per
   `.hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md`.
   Per story, one command:
   `python3 .hermes/skills/harness/dispatch-phase/scripts/run-pre-create-gates.py --root /projects/modernized --body evidence/bodies/m3-{story_id}.json`
   then compose title/markdown via `compose-m3-card-markdown.py`, then
   `kanban_create`. After each `kanban_create`:
   `python3 .hermes/skills/harness/dispatch-phase/scripts/assert-story-parked.py /projects/modernized --task-id <id> --ack-gate <ack_gate_id>`
   `python3 .hermes/skills/harness/dispatch-phase/scripts/assert-m3-child-skills.py /projects/modernized --task-id <id> --body evidence/bodies/m3-{story_id}.json`
   Empty skills ⇒ `kanban_block --kind needs_input`. Do **not** halt after the gate. Do **not**
   dispatch children here. Do **not** dump bodies or `kanban show --json`.
4. After children exist, mint M4 then M5 per
   `.hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md`
   (M4 `--parent` every story child, not this holder). Then
   `python3 .hermes/skills/harness/dispatch-phase/scripts/assert-m3-child-skills.py /projects/modernized --holder-id "$HERMES_KANBAN_TASK"`
   must exit 0 **before** `kanban_complete`. DAG-shaped is not enough.
   Then issue the M3 brief-identity gate-record:
   `python3 .hermes/skills/harness/enforce-authority-boundary/scripts/issue-m3-brief-identity-ack.py /projects/modernized --task-id <ack_gate_id>`
   and `kanban_complete` the ack_gate on PASS. Complete this holder **only if**
   that issuer is green **and** no child title starts with `M4` or `M5`.
   Otherwise block `--kind needs_input`.

## Constraints

- OBJECT dest-rewrite of `specs/**/tasks.md`.
- OBJECT mint growth past **1088**.
- OBJECT retired mint-m3-wave / `handover-mint.py --parent`.
- OBJECT a third tick on a sticky `needs_input` dest (v24 park).
- OBJECT implementing the whole `tasks.md` on this card.
- Serial GO is orchestrator `hermes kanban dispatch --max 1`, not this card.
- OBJECT `stop-worker-session.sh` from this worker (A-5 is seat ops).
