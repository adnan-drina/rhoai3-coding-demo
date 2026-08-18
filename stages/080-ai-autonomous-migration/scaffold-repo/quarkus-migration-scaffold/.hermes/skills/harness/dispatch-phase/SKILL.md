---
name: dispatch-phase
description: Creates and dispatches an M1-M5 Kanban card with declared skills, budget and park-at-birth. Use when starting any migration phase, after speckit.tasks when a Hermes wave-holder session must lint+assemble+stamp then kanban_create parked M3 children with an ack_gate parent, or when a card must be minted with skills already attached. Do not run mint-m3-wave.sh from Cursor.
license: Apache-2.0
compatibility: Linux seat; Hermes CLI on PATH for kanban create/dispatch
metadata:
  author: rhoai3-harness-team
  version: "1.5.2"
  hermes:
    tags:
    - harness
    - orchestration
    category: harness
    kind: enforcement
---
# Phase dispatch (Hermes Kanban)

## When to Use

- Starting **any** M-phase, especially **M1 ANALYZE** (derive + MTA + inventory).
- After **speckit.tasks** — the **wave-holder Hermes session** loads this
  skill and follows `references/mint-m3-hermes.md` (`kanban_create` +
  ack_gate). Lint is `handover-mint.py --write` (no `--parent`).
  Bare `kanban create` attaches **zero** skills.
- Seeding the next phase after an ack is granted (`--parent <prior task id>`).
- Replacing a forbidden detached `mta-analyze-legacy.sh` / derive shell under
  PPID 1 — that path yields `tasks=0` and cannot stamp
  `orchestration=hermes_native`.
- **M2a/M2b are refused** (GR2). Dispatch **M2**; M3 children are minted
  by the holder session, not `mint-m3-wave.sh`.

## Standing rule

**Hermes owns orchestration for M1–M5.** Domain scripts (`mta-analyze-legacy.sh`,
`derive-legacy-boot3.sh`, …) run **inside** a Kanban worker that loaded the
declared skills — they are not the demo control plane.

**C-2(a) single-persona.** Cards use Hermes profile `default` (R-V14.10).
Named analyzer/planner/implementer/validator profiles are retired. Pillar
heads stay Cursor — do not create them as Hermes profiles and do not touch
`.wake/`. Catalog: `references/assignee-profiles.json`. Mint/dispatch
fail-closed via `hermes profile show default`.

**BV19-3:** the Kanban `--parent` / `link` graph is the phase DAG. M1 is the
only root (no `--parent`). M2 / M3 / M4 / M5 / factory and M3 mint **must**
pass `--parent`. After live create, dispatch and create-m3 read
`hermes kanban show --json` via `read-link-graph.py --expect-parent`.
`evidence/derived/phase-*-task-id.txt` is a Review pointer, not the DAG.
Do not derive phase identity from card titles. Official: dispatcher promotes
`todo→ready` when all parents are `done`; CLI is `hermes kanban link`.

**L7:** at Hermes v0.20.2 a second same-kind re-block hits native
`BLOCK_RECURRENCE_LIMIT` and the card goes `triage`. Promote will not
reclaim it. Do not reimplement that hold in dispatch.

**Seat pin:** `.hermes/pins.json` `hermes_agent.version` **v0.20.4**
(binary-local `--help` + `VALID_INITIAL_STATUSES`; omit `--initial-status`
yields `ready`). Live dispatch runs `scripts/assert-seat-hermes-pin.py`.

## Fail-closed kind map (Architect `E-20260818T094316Z` / `094840Z`)

Dest-forbidden rewrite and A-8 planning refuse are **not** parent waits.
`dependency` self-clears (`dependency_wait` → `promoted`) and does **not**
count toward `BLOCK_RECURRENCE_LIMIT` (Research `7af1f14f`). Wrong kind on
a planning defect cycles the holder. Do **not** restore `park-on-block-loop.py`.

| Refusal class | `hermes kanban block --kind` | Why |
|---|---|---|
| A-8 refuse (`endpoints_multi` / `endpoints_uncovered` / lint exit 1) | `needs_input` | Defect is in `tasks.md`; holder must not dest-rewrite |
| Dest-forbidden rewrite (`tasks.md` outside write-set) | `needs_input` | Same — OBJECT dest-rewrite |
| Missing parent / unsigned ack_gate | `dependency` | Auto-promotes when that parent completes |
| Mint growth / dest-rewrite impulse | do not | OBJECT; halt `061824Z`; mint **1088** |

Argv order: **`--kind` before the task id** (`204830Z` silent no-op if reversed).
Then `kanban show` must report `status=blocked`.

## Holder card (I-10 B — Architect `25a7c1e9`)

Create the M3 wave holder **before** the holder session mints children.
Pin official `one-three-one-rule` (escalations). Do **not** pin `dispatch-phase` — path-invoke `references/mint-m3-hermes.md`. Keep the five names in `skills.disabled`. Do **not** pin `check-spec-readiness` on the holder until story bodies exist (v22 `skill_view` 0 / unused pin).

```bash
python3 .hermes/skills/harness/dispatch-phase/scripts/assert-skills-not-disabled.py \
  /projects/modernized --skill one-three-one-rule
hermes kanban create --assignee default --workspace dir:/projects/modernized \
  --skill one-three-one-rule \
  --parent <m2_task_id> \
  --body-file .hermes/skills/harness/dispatch-phase/references/holder-card-body.md \
  "M3 WAVE HOLDER"
```

Holder body is `references/holder-card-body.md` (fail-closed kind map in
the card, not only this skill). Mint procedure: `references/mint-m3-hermes.md`.

## Procedure

```bash
export HERMES_HOME="${HERMES_HOME:-/projects/modernized/.hermes/home}"
export HERMES_MANAGED_DIR="${HERMES_MANAGED_DIR:-/projects/.platform/hermes}"
cd /projects/modernized

# Ensure watch is already running in another pane (demo Act D).
bash "${HERMES_SKILL_DIR}/scripts/dispatch-phase.sh" M1
# later:
bash "${HERMES_SKILL_DIR}/scripts/dispatch-phase.sh" M2 --parent <m1_task_id>
# after M2 Done: the M3 wave-holder worker follows references/mint-m3-hermes.md
# (lint + kanban_create + ack_gate). Do not bash mint-m3-wave.sh.
```

`--dry-run` prints the exact `hermes kanban create` argv without creating.
`--idempotency-key KEY` overrides the default `migration-<phase>-v1`.
From a shell without the skill loaded:

```bash
bash .hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh M1
```

### Serial GO (one in-flight)

Create parks (`DISPATCH_MAX=0`). Spawn is native `hermes kanban dispatch --max 1`
— not `chat -q`, not `kanban daemon --force`. Argv, official log path, and M3
`--parent` create: `references/native-dispatch.md`.

### What dispatch-phase.sh does

1. Runs the pre-create gate chain, dying on the first refusal: tip sync,
   quarantine tombstones, `check-phase-attach-matrix.py`,
   `check-phase-body-script-refs.py`, `check-phase-input-manifest.py`,
   `check-decision-complete-cards.py`, `assert-skills-not-disabled.py` (B3),
   and — for M2 only —
   `check-specify-preseed.py` (provision owns `specify init`; agents verify
   or BLOCK).
2. Reads `.hermes/phase-dispatch.yaml` for `role`, `skills[]`,
   `max_runtime_seconds` for the phase.
3. R-HX.5: does **not** copy Managed Scope `config.yaml` / `.env` into
   `HERMES_HOME` (DB/logs only). Pins `HERMES_MANAGED_DIR` and refuses a
   mismatched export; writes `skills.external_dirs` into `HERMES_HOME/config.yaml`
   so tip skills resolve.
4. Daemon/dispatcher stay **off** unless `DISPATCH_START_DAEMON=1` /
   `DISPATCH_MAX>0` (Architect `E-20260816T185414Z`: `--force` is a restart
   trigger, not a dispatch side-effect).
5. `hermes kanban create` (`dir:/projects/modernized`, skills, budget,
   idempotency key); id under `evidence/derived/` (pointer, not the DAG).
   M2 stamps dest write-set **cache** `evidence/runtime/write-sets/<id>.json`
   = `.specify/` + `specs/` (AD-013; fence is spawn-env, not that file).
6. M3 children are **not** created by this script. The holder session
   follows `references/mint-m3-hermes.md`.

### What mint-m3-hermes.md adds

`handover-mint.py --write` (no `--parent`) is lint+assemble. The holder
creates **ack_gate first** (no holder parent; sticky-block with `--kind`
before the id; assert `status=blocked`), then one parked child per
story with parents `[holder, ack_gate]`, then `kanban_complete`s itself.
Pre-create gates that lived in `create-m3-implementer.sh` run via
`execute_code` (list in `references/mint-m3-hermes.md`). Story card
markdown must carry typed-body path, AR-4.3 digest + `--expect` REFUSE,
standing pointer, Constraints, and **full** attach-script skills
(`035010Z`). Grant = complete the blocked gate card, not a YAML file.
Do not parent the gate on the holder (`173800Z`).

### M1 body contract (evidence-analyst)

The created M1 task instructs the worker to, in order:

1. `derive-legacy-boot3` (manifest check / derive if missing)
2. `inventory-entry-points` → `evidence/entry-point-inventory.json` (before handoff emit)
3. `scan-with-mta` → `mta-analyze-legacy.sh` (writable clone + `MTA_RUN_CWD`; emits findings-handoff)
4. Validate findings + handoff — **do not** grant stage-advance acks (Operator writes `m1-findings.ack.yaml` per AR-1.1). M1 ACK GATE complete is the **verifier card** in `references/m1-verifier.md` (`scripts/check-m1-verifier.py`, refuse-on-nonzero). This worker does not complete the gate.

### M2 body contract (planner)

Job order (inventory before specify; `@Path` emit): `references/m2-planner.md`.

## Pitfalls

- Do **not** start M1 by `nohup …/mta-analyze-legacy.sh &`.
- Do **not** omit `--workspace dir:/projects/modernized` (scratch default is wrong).
- Do **not** dispatch M3 children from the M2 worker — the **holder**
  session mints via `references/mint-m3-hermes.md`.
- Do **not** run `mint-m3-wave.sh` / `create-m3-implementer.sh` from
  Cursor or ask the demo user to (`165300Z`).
- Do **not** `--parent` a `done` card when minting park-at-birth children
  (`PARENT_DONE`). Hermes auto-promotes those children (HKN-2); create-time
  `blocked` is not durable. The incomplete **ack_gate** parent holds them.
- Start `hermes kanban watch` **before** dispatch for the demo audience.
  Companion pane: `hermes kanban tail <task_id>` or `hermes kanban log <task_id>`
  (native CLI — do **not** revive `kanban-track.sh`; W6 REMOVE 2026-08-13).
- Do **not** omit `--parent` on M2–M5 / factory (BV19-3). A card with no parent
  link is an unrooted DAG node — recreate via these scripts with `--parent`.
- Do **not** treat `phase-*-task-id.txt` as the DAG, and do not derive phase
  from the card title.

## Available scripts

- `scripts/dispatch-phase.sh` — create a phase seed card from `phase-dispatch.yaml`
- `scripts/check-m1-verifier.py` / `references/m1-verifier.md` — M1 verifier (refuse-on-nonzero)
- `scripts/assert-seat-hermes-pin.py` — seat Hermes vs `.hermes/pins.json` (`v0.20.4`)
- `scripts/handover-mint.py` — tasks.md phases → receipt + bodies (A-4/A-5/A-8); lint only (`--write`, no `--parent`)
- `references/mint-m3-hermes.md` — Hermes holder mint: gates + `kanban_create` + ack_gate
- `scripts/read-link-graph.py` — BV19-3 parse `kanban show --json` parents/children
- `scripts/read-phase-dispatch.py` — LG7 JSON phase seed (no eval of parser output)
- `scripts/check-link-graph.py` — BV19-3 lint: `--parent` required except M1
- `scripts/resolve-seat-assignee.py` — C-2(a) phase → `default`
- `scripts/check-seat-assignee-profiles.py` — C-2(a) catalog + GitOps skip lint
- `scripts/m3-attach-skills.py` — B-16 attach from `identity.operand_skills`
- `scripts/mint-remediation-card.py` — C-3(a) REFUSE → remediation receipt
- `scripts/check-phase-attach-matrix.py` — skills[] vs attach-matrix law
- `scripts/check-create-path-tip-sync.py` — BLOCKING R0/R3 create-path tip sync
- `scripts/check-phase-input-manifest.py` — phase input manifest present
- `scripts/check-phase-body-script-refs.py` — body refs to scripts resolve
- `scripts/check-specify-preseed.py` — Spec Kit preseed gate
- `scripts/check-completion-na-reject.py` — refuse N/A completion abuse
- `scripts/check-created-cards-claim.py` — created-cards claim coherence
- `scripts/check-decision-complete-cards.py` — decision→complete card checks
- `scripts/assert-bundle-skills-exist.py` — CS-7 bundle skill exists-assert

## Verification

- `evidence/derived/phase-<PHASE>-task-id.txt` contains the new task id
  (Review pointer). The DAG is `hermes kanban show --json` `parents` /
  `children`. The script dies if `kanban create` returned no id, so an
  absent or stale file means no card was created.
- **Silent-failure catch (BV19-3):** a non-M1 create without a parent link
  is a fail-closed refuse (`BV19-3: --parent REQUIRED`). A live card whose
  `parents` list omits the `--parent` id is the same refuse after create.
- Stdout ends with `OK: <PHASE> → <task_id> (Hermes-native)` and prints
  `REVIEW_ADHERE_OBSERVE=<task_id>`;
  `evidence/derived/review-adhere-observe-needed.yaml` carries the same id.
- **Silent-failure catch:** the card must actually carry the declared skills.
  `hermes kanban show <task_id>` listing zero skills means the bare-create
  path was used — refuse the run and recreate via these scripts.
- M3 only: `PARK_AT_BIRTH=<task_id> status=blocked` (or `triage`). Any of
  `ready` / `todo` / `running` after create is a fail-closed die — a
  dispatchable M3 mint races M2.
- M3 only: `CREATED_CARDS_CLAIM=<path>` names a
  `evidence/derived/created-cards-<parent>.json` containing the new id, and
  `ACK_REQUEST=<path>` names an unsigned `ack-request-<story>.yaml` whose
  body digest matches the sidecar.
- `--dry-run` exits 0 and prints the argv without touching the board — use it
  to confirm skills, `max_runtime`, and `--assignee default` before a
  live create. M3 dry-run must show `--assignee default`.
