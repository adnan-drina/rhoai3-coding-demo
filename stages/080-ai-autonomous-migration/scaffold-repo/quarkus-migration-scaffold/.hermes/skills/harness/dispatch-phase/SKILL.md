---
name: dispatch-phase
description: Creates and dispatches an M1-M5 Kanban card with declared skills, budget and park-at-birth. Use when starting any migration phase, when splitting M3 into child stories, or when a card must be minted with its skills and exit criteria already attached.
license: Apache-2.0
compatibility: Linux seat; Hermes CLI on PATH for kanban create/dispatch
metadata:
  author: rhoai3-harness-team
  version: "1.4.1"
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
- After **M2 PLAN** Done — mint M3 children via **`mint-m3-wave.sh`** (AD-016/GR2
  orchestrator-owned mint). Always uses `create-m3-implementer.sh` under the hood;
  bare `hermes kanban create` attaches **zero** skills.
- Seeding the next phase after an ack is granted (`--parent <prior task id>`).
- Replacing a forbidden detached `mta-analyze-legacy.sh` / derive shell under
  PPID 1 — that path yields `tasks=0` and cannot stamp
  `orchestration=hermes_native`.
- **M2a/M2b are refused** (GR2). Dispatch **M2**, then `mint-m3-wave.sh`.

## Standing rule

**Hermes owns orchestration for M1–M5.** Domain scripts (`mta-analyze-legacy.sh`,
`derive-legacy-boot3.sh`, …) run **inside** a Kanban worker that loaded the
declared skills — they are not the demo control plane.

**EX-4 seat assignees** are named Hermes profiles (`analyzer` / `planner` /
`implementer` / `validator`), created with `--description` for kanban routing.
Never `--assignee default`. Pillar heads stay Cursor — do not create them as
Hermes profiles and do not touch `.wake/`. Catalog:
`references/assignee-profiles.json`. Unknown names silent-fail in the
dispatcher; mint/dispatch fail-closed via `hermes profile show`.

**BV19-3:** the Kanban `--parent` / `link` graph is the phase DAG. M1 is the
only root (no `--parent`). M2 / M3 / M4 / M5 / factory and M3 mint **must**
pass `--parent`. After live create, dispatch and create-m3 read
`hermes kanban show --json` via `read-link-graph.py --expect-parent`.
`evidence/derived/phase-*-task-id.txt` is a Review pointer, not the DAG.
Do not derive phase identity from card titles. Official: dispatcher promotes
`todo→ready` when all parents are `done`; CLI is `hermes kanban link`.

**L7:** `block_loop_detected` is not a hold by itself — Hermes may leave the
card `blocked`, which promote lifts. `park-on-block-loop.py` runs before
daemon start and sets those cards to `triage`. `--self-test` proves promote
does not claim a loop-broken card.

## Procedure

```bash
export HERMES_HOME="${HERMES_HOME:-/projects/modernized/.hermes/home}"
export HERMES_MANAGED_DIR="${HERMES_MANAGED_DIR:-/projects/.platform/hermes}"
cd /projects/modernized

# Ensure watch is already running in another pane (demo Act D).
bash "${HERMES_SKILL_DIR}/scripts/dispatch-phase.sh" M1
# later:
bash "${HERMES_SKILL_DIR}/scripts/dispatch-phase.sh" M2 --parent <m1_task_id>
# after M2 Done:
bash "${HERMES_SKILL_DIR}/scripts/mint-m3-wave.sh" --parent <m2_task_id>
```

`--dry-run` prints the exact `hermes kanban create` argv without creating.
`--idempotency-key KEY` overrides the default `migration-<phase>-v1`.
From a shell without the skill loaded:

```bash
bash .hermes/skills/harness/dispatch-phase/scripts/dispatch-phase.sh M1
```

M3 children take the dedicated create path (`--parent` is **required**):

```bash
bash .hermes/skills/harness/dispatch-phase/scripts/mint-m3-wave.sh \
  --parent <m2_task_id>
# or per-story:
bash "${HERMES_SKILL_DIR}/scripts/create-m3-implementer.sh" \
  --title "M3 IMPLEMENT: <story>" \
  --body-json evidence/bodies/m3-s-010.json \
  --parent <m2_task_id>
```

### What dispatch-phase.sh does

1. Runs the pre-create gate chain, dying on the first refusal: tip sync,
   quarantine tombstones, `check-phase-attach-matrix.py`,
   `check-phase-body-script-refs.py`, `check-phase-input-manifest.py`,
   `check-decision-complete-cards.py`, and — for M2 only —
   `check-specify-preseed.py` (provision owns `specify init`; agents verify
   or BLOCK).
2. Reads `.hermes/phase-dispatch.yaml` for `role`, `skills[]`,
   `max_runtime_seconds` for the phase.
3. R-HX.5: does **not** copy Managed Scope `config.yaml` / `.env` into
   `HERMES_HOME` (DB/logs only). Pins `HERMES_MANAGED_DIR` and refuses a
   mismatched export; writes `skills.external_dirs` into `HERMES_HOME/config.yaml`
   so tip skills resolve.
4. Ensures a standalone `hermes kanban daemon --force` (Dev Spaces has no gateway).
5. `hermes kanban create` with `--workspace dir:/projects/modernized`, one
   `--skill` per declared skill, `--max-runtime`, and the idempotency key;
   records the id under `evidence/derived/` (pointer only — the DAG is the
   parent/child link graph).
6. Ticks `hermes kanban dispatch --max 1`. **The M3 create path does not** —
   cards are born `--initial-status blocked` and unpark only after M2 ledger
   PASS + brief-identity ack + serial GO (Deputy `E-20260811T131900Z`).

### What create-m3-implementer.sh / mint-m3-wave.sh add

`mint-m3-wave.sh` walks `evidence/briefs/partition.json`, invokes
`create-m3-implementer.sh` per story, then runs
`assert-m2b-created-cards-claim.sh` (F8a/F8b receipt).

`create-m3-implementer.sh` stamps the body digest (AR-4.3), runs the body-scoped
create gates, builds the markdown card from the typed body **by reference**,
forces park-at-birth, appends to `evidence/derived/created-cards-<parent>.json`,
emits an unsigned ack-request, then cross-asserts card digest ↔ live sidecar.

### M1 body contract (evidence-analyst)

The created M1 task instructs the worker to, in order:

1. `derive-legacy-boot3` (manifest check / derive if missing)
2. `inventory-entry-points` → `evidence/entry-point-inventory.json` (before handoff emit)
3. `scan-with-mta` → `mta-analyze-legacy.sh` (writable clone + `MTA_RUN_CWD`; emits findings-handoff)
4. Validate findings + handoff — **do not** grant stage-advance acks (Operator writes `m1-findings.ack.yaml` per AR-1.1)

## Pitfalls

- Do **not** start M1 by `nohup …/mta-analyze-legacy.sh &`.
- Do **not** omit `--workspace dir:/projects/modernized` (scratch default is wrong).
- Do **not** dispatch M3 children from the M2 worker — use `mint-m3-wave.sh`.
- Do **not** `--parent` a `done` card when minting park-at-birth children
  (`PARENT_DONE`). Hermes auto-promotes those children (HKN-2); create-time
  `blocked` is not durable. Mint under a still-open wave holder.
- Start `hermes kanban watch` **before** dispatch for the demo audience.
  Companion pane: `hermes kanban tail <task_id>` or `hermes kanban log <task_id>`
  (native CLI — do **not** revive `kanban-track.sh`; W6 REMOVE 2026-08-13).
- Do **not** `--assignee default` — that is the EX-4 identity hole. Unknown
  profile names silent-fail in the dispatcher.
- Do **not** omit `--parent` on M2–M5 / factory (BV19-3). A card with no parent
  link is an unrooted DAG node — recreate via these scripts with `--parent`.
- Do **not** treat `phase-*-task-id.txt` as the DAG, and do not derive phase
  from the card title.

## Available scripts

- `scripts/dispatch-phase.sh` — create a phase seed card from `phase-dispatch.yaml`
- `scripts/mint-m3-wave.sh` — orchestrator-owned M3 mint from partition (GR2/AD-016)
- `scripts/create-m3-implementer.sh` — M3 child with required skills + park-at-birth
- `scripts/read-link-graph.py` — BV19-3 parse `kanban show --json` parents/children
- `scripts/read-phase-dispatch.py` — LG7 JSON phase seed (no eval of parser output)
- `scripts/check-link-graph.py` — BV19-3 lint: `--parent` required except M1
- `scripts/resolve-seat-assignee.py` — EX-4 phase → named seat profile
- `scripts/check-seat-assignee-profiles.py` — EX-4 catalog + no-default lint
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
  to confirm skills, `max_runtime`, and `--assignee <named-profile>` before a
  live create. M3 dry-run must show `--assignee implementer`, never `default`.
