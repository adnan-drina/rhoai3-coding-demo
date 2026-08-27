---
name: plan-migration-partition
description: >
  Use at M2 PLAN — before minting Kanban children — to run
  specify-from-project.sh --root /projects/modernized workflow run speckit
  -i spec="<description derived from M1 evidence>", read M1 attachments,
  author evidence/partition.json, convert with k4_convert.py --partition
  --tasks, and mint with k4_mint.py. Use when writing partition.json or
  creating the M2 card, even if the user does not name Spec Kit. Do not
  PATH-lookup specify (dest-9 uv specify shadows the dest-init shim). Do
  not run the bare form (Required input spec). Do not scrape write-sets
  from tasks.md. Do not use only to lint an already-written partition
  (check-spec-readiness).
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; pinned specify-cli; Hermes Kanban
metadata:
  author: rhoai3-harness-team
  version: "1.3.1"
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

3. Run Spec Kit with the required `spec` input. Stop. Never
   `/speckit.implement`. Never the bare form (Operator `165811ZO`:
   `Required input 'spec' not provided`, exit 1). Derive the description
   from M1 attachments (identity, HTTP paths, extensions) — do not invent
   routes.

```bash
bash .hermes/skills/sdd/init-spec-workspace/scripts/specify-from-project.sh \
  --root /projects/modernized \
  workflow run speckit \
  -i spec="<description derived from M1 evidence>"
```

Do **not** PATH-lookup `specify`. dest-9 `command -v specify` was
`/home/user/.local/bin/specify` (uv), which shadowed dest-init
`/projects/.platform/hermes/bin/specify` (the shim). Project leaf
`.hermes/skills/speckit-specify/SKILL.md` was PRESENT; user-home leaf was
ABSENT. `-i spec=` is necessary and not sufficient without the helper.
Unknown `speckit-specify` is `kanban_block`, not hand-author `tasks.md`.
Do not dest-edit dest-9 PATH or implementer `external_dirs`.
Do **not** prefer dest-init `/projects/.platform/hermes/bin/specify`: dest-init
writes the **same helper wrapper** there (Architect `131720ZA`: 1744
concurrent helpers). Skip dest helper wrappers (this script,
`${ROOT}/.hermes/bin`, `*/.platform/hermes/bin`, `/etc/hermes/bin`) and refuse
any candidate whose file contains `specify-from-project.sh`. dest-10 M2
`t_c705fc91` still saw `Unknown skill(s): speckit-specify` on uv — that
remaining miss is not a reason to prefer the wrapper. Do not widen
`K2_ALLOW_ROOT`.

`tasks.md` must be non-empty under `.specify/specs/*/tasks.md`.

4. Author `evidence/partition.json` from those attachments **and** the
   plan. Schema: `references/partition-schema.md` (kept in sync with
   `.hermes/kernel/k4_schema.py` by `scripts/assert-partition-schema-sync.py`).
   Do not reverse-engineer `k4_*.py`.

   **Write-set (`K4_T0_3_SERVICE`):** the same `*Service.java` must not
   appear on two stories. One story MAY own a shared facade. Split-one-class-per-aggregate
   is petclinic architecture, not this mint refuse.

   HTTP stories must set `legacy_source` to the matching
   `entry-point-inventory.json` `file` (legacy package/path). Dest
   `files_writable` is the dest package (`com/demo`); the worker must not
   rediscover `com/example/restservice`. Missing `legacy_source` is
   `K4_LEGACY_SOURCE`. HTTP stories must also set `dest_file` to the
   inventory dest twin. Missing `dest_file` is `K4_DEST_FILE` (dest-9 live
   partition skip is convert-refuse, not a second invented-files checker).

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
- Prescribing PATH `specify workflow run speckit` (Operator `165811ZO` bare
  form; dest-9 uv specify shadows the dest-init shim). Call
  `specify-from-project.sh --root`. dest-9 `-i spec=` still
  `speckit-specify` unknown is `kanban_block`, not a hand-authored
  `tasks.md`. dest-10: do not skip `.platform/hermes/bin` in the helper
  skip-list (uv then cannot see Hermes skills).
