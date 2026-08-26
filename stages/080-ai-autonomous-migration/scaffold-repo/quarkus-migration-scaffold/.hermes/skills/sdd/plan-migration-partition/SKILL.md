---
name: plan-migration-partition
description: >
  Use at M2 PLAN — before minting Kanban children — to run specify workflow
  run speckit, read M1 attachments, author evidence/partition.json, convert
  with k4_convert.py --partition --tasks, and mint with k4_mint.py. Use when
  writing partition.json or creating the M2 card, even if the user does not
  name Spec Kit. Do not scrape write-sets from tasks.md. Do not use only to
  lint an already-written partition (check-spec-readiness).
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; pinned specify-cli; Hermes Kanban
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - sdd
    - m2
    category: sdd
    kind: guidance
---
# Plan the migration partition (M2 producer)

This skill **owns M2 end-to-end**. It is the producer
`check-spec-readiness` defers to. Pin it on the M2 card (`--skill
plan-migration-partition`). Speckit generates the **plan** (`tasks.md`);
K4 generates **cards** from the typed partition (Architect `142518ZA`).
Do not grep `tasks.md` for write-sets (`PATH_TOKEN` OBJECT).

## When to Use

- This card is **M2 PLAN**.
- `evidence/partition.json` does not exist yet, or M1 attachments changed.
- **Not** Spec Kit provision (`init-spec-workspace`).
- **Not** coverage/body lint alone (`check-spec-readiness`).
- **Not** M3 exit derivation (`derive-story-oracles`).

## Pin the M2 card

Create (or remint) M2 with this leaf first:

```bash
hermes kanban create \
  --title "M2 PLAN" \
  --assignee implementer \
  --parent "$M1_TASK_ID" \
  --skill plan-migration-partition \
  --skill check-spec-readiness \
  --workspace dir:/projects/modernized \
  --max-retries 1 \
  --max-runtime 2h
```

`init-spec-workspace` and `derive-story-oracles` are not the procedure.
Do not pin only those three.

## Procedure

Root is `/projects/modernized`. `$M1` is the parent M1 task id.

1. If `.specify/` is missing, load `init-spec-workspace` and provision.
   Then return here.
2. Read M1 attachments — **not** metadata path lists:

```bash
hermes kanban show "$M1"
# then read kanban_attachments under $HERMES_HOME/kanban/attachments/<m1-id>/
# and evidence/findings-handoff.json, entry-point-inventory.json,
# type-inventory.json, required-extensions.json
```

3. Run Spec Kit. Stop. Never `/speckit.implement`.

```bash
specify workflow run speckit
```

`tasks.md` must be non-empty under `.specify/specs/*/tasks.md`.

4. Author `evidence/partition.json` from those attachments **and** the
   plan. Schema: `references/partition-schema.md` (kept in sync with
   `.hermes/kernel/k4_schema.py` by `scripts/assert-partition-schema-sync.py`).
   Do not reverse-engineer `k4_*.py`.

   **Split rule (M2, not M3):** one service class per aggregate. Do **not**
   put the same `*Service.java` on two stories (methods in a shared
   `ClinicService` — `K4_T0_3_SERVICE`). Retire the inventory row with a
   named 1:N supersede set.

5. Story headings in `tasks.md` must match partition `story_id`s
   (`scripts/assert-m2-story-headings.py`). Still not write-set scrape.

6. Convert, then mint:

```bash
python3 .hermes/kernel/k4_convert.py \
  --partition evidence/partition.json \
  --tasks .specify/specs/*/tasks.md \
  --out evidence/partition-payloads.json
python3 .hermes/kernel/k4_mint.py \
  --payloads evidence/partition-payloads.json \
  --exec
```

`--tasks` is required for a conformant M2 complete (Operator `123401ZO`).
A hand-written partition remains a legal K4 input; it is not a complete.

7. Lint (this skill does not replace these checkers):

```bash
python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-m2-speckit-conformance.py .
python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-partition-coverage.py .
bash .hermes/skills/sdd/check-spec-readiness/scripts/check-readiness.sh --root .
python3 "${HERMES_SKILL_DIR}/scripts/assert-m2-story-headings.py" .
```

`kanban_complete` `created_cards` is the native `t_*` list from mint.
Do not `kanban daemon --force`. Do not `kanban swarm`. Do not dest-dispatch M5.

## Pitfalls

- Assembling the sequence from three other skills plus `AGENTS.md` (dest-8
  restated the protocol six times and read `k4_*.py`).
- Skipping speckit because K4 does not scrape `tasks.md` (WAVE 1 made
  `tasks.md` **binding**, not generative of cards).
- Inventing `/q/health` as a story (constitution III: if health exists, at
  `/q/health`; VII stands).
