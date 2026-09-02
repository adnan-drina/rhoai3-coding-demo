---
name: plan-migration-partition
description: >
  Use at M2 PLAN — before minting Kanban children — to follow the Hermes
  skills speckit-specify, speckit-plan, and speckit-tasks (never implement),
  read M1 attachments, author evidence/partition.json, convert with
  k4_convert.py --partition --tasks, and mint with k4_mint.py. Use when
  writing partition.json, even if the user does not name Spec Kit. Do not
  pin this leaf on the card (pin paved-road-m2). Do not run specify
  workflow run speckit: the Spec Kit
  hermes integration installs files:{} and cannot dispatch speckit-specify
  as a command. Do not PATH-lookup specify. Do not scrape write-sets from
  tasks.md. Do not use only to lint an already-written partition
  (check-spec-readiness).
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; pinned specify-cli; Hermes Kanban
metadata:
  author: rhoai3-harness-team
  version: "1.5.0"
  hermes:
    tags:
    - sdd
    - m2
    category: sdd
    kind: guidance
---
# Plan the migration partition (M2 producer)

This skill is the **M2 producer** of `evidence/partition.json`.
`check-spec-readiness` defers to it. **Do not pin this leaf on the card.**
Pin `--skill paved-road-m2`; this producer loads via `skill_view` from
`steps.json`. Speckit **skills** generate the **plan** (`tasks.md`); K4
generates **cards** from the typed partition
(Architect `142518ZA`). Do not grep `tasks.md` for write-sets
(`PATH_TOKEN` OBJECT). Do not `specify workflow run speckit`
(Architect `170540ZA`: hermes.manifest `files: {}`).

## When to Use

- This card is **M2 PLAN**.
- `evidence/partition.json` does not exist yet, or M1 attachments changed.
- **Not** Spec Kit provision (`init-spec-workspace`).
- **Not** coverage/body lint alone (`check-spec-readiness`).
- **Not** M3 exit derivation (`derive-story-oracles`).

## Card pin

Do not pin this leaf on the M2 card. Dest-init `autostart-migration.sh`
pins `--skill paved-road-m2` only. Follow this SKILL.md when `skill_view`
loads it from `steps.json`. `init-spec-workspace` and
`derive-story-oracles` are not the procedure.

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

3. Follow the Hermes speckit skills **in process**. Stop. Never
   `/speckit.implement`. Never `specify workflow run speckit` — Spec Kit
   0.16.1 `--integration hermes` writes
   `.specify/integrations/hermes.manifest.json` with `"files": {}`.
   `invoke_separator: "-"` then dispatches `speckit.specify` as the
   shell command `speckit-specify`, which does not exist
   (`Unknown skill(s): speckit-specify` on dest-9/10/12). The
   `SKILL.md` files `seed-speckit-skills.py` installs are for **this
   agent to read**, not commands a workflow runner can exec
   (Architect `170540ZA`). Derive the spec from M1 attachments
   (identity, HTTP paths, extensions) — do not invent routes.

   Load and follow, in order, the project leaves:

   - `.hermes/skills/speckit-specify/SKILL.md`
   - `.hermes/skills/speckit-plan/SKILL.md`
   - `.hermes/skills/speckit-tasks/SKILL.md`

   Do not load speckit-implement. Do not PATH-lookup `specify`. Do not
   widen `K2_ALLOW_ROOT`. Do not dest-edit dest-9 PATH or implementer
   `external_dirs`. If a named skill is missing, a named command fails,
   or a named path is absent: **stop**. Record exactly what failed.
   `kanban_block`. Do not hand-author `tasks.md`. Do not stamp
   `evidence/receipts/speckit/workflow-run.json` to satisfy a gate
   (Architect `170112ZA`: that receipt is worker-writable).

`tasks.md` must be non-empty at the Spec Kit 0.16.1 feature directory
named in `.specify/feature.json` `feature_directory` (example:
`specs/001-spring-to-quarkus/tasks.md`). Do **not** copy that file onto
`.specify/specs/` to satisfy a glob. Do **not** glob
`.specify/specs/*/tasks.md` as the M2 authority.

4. Author `evidence/partition.json` from those attachments **and** the
   plan. Schema: `references/partition-schema.md` (kept in sync with
   `.hermes/kernel/k4_schema.py` and `.hermes/kernel/k4_producers.py` by
   `scripts/assert-partition-schema-sync.py`). Pin `skills[]` from that
   page's **Valid producers** table (or omit and use `kind` → defaults).
   Do not reverse-engineer `k4_*.py`. Do not invent skill names.

   **Write-set (`K4_T0_3_SERVICE`):** the same `*Service.java` must not
   appear on two stories. One story MAY own a shared facade. Split-one-class-per-aggregate
   is petclinic architecture, not this mint refuse.

   HTTP stories must set `legacy_source` to the matching
   `entry-point-inventory.json` `file` (legacy package/path). Dest
   `files_writable` is the dest package (`com/demo`); the worker must not
   rediscover `com/example/restservice`. Missing `legacy_source` is
   `K4_LEGACY_SOURCE`. HTTP stories must also set `dest_file` to the type-inventory dest twin
   of an inventoried legacy type — **not** the new file this story creates.
   Missing `dest_file` is `K4_DEST_FILE` (dest-9 live
   partition skip is convert-refuse, not a second invented-files checker).

5. Story headings in `tasks.md` must match partition `story_id`s
   (`scripts/assert-m2-story-headings.py`). Still not write-set scrape.

6. Convert, then mint:

```bash
python3 .hermes/kernel/k4_convert.py \
  --partition evidence/partition.json \
  --tasks specs/*/tasks.md \
  --out evidence/partition-payloads.json
python3 .hermes/kernel/k4_mint.py \
  --payloads evidence/partition-payloads.json \
  --exec
```

`--tasks` is required for a conformant M2 complete (Operator `123401ZO`).
A hand-written partition remains a legal K4 input; it is not a complete.
`k4_mint.py --exec` mints the M3 stories, then one `M4 VERIFY` parented
to those M3 `t_*` (`--idempotency-key m4-verify`). Do not extend
`autostart-migration.sh` to mint M4. Do not put a verdict token in the
M4 body.

7. Lint (this skill does not replace these checkers):

```bash
python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-m2-speckit-conformance.py .
python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-partition-coverage.py .
bash .hermes/skills/sdd/check-spec-readiness/scripts/check-readiness.sh --root .
python3 "${HERMES_SKILL_DIR}/scripts/assert-m2-story-headings.py" .
```

Happy-path terminator is `kanban_request_review` (not `kanban_complete`).
`--metadata` `created_cards` is the native `t_*` list from mint. KEEP
`evidence/partition-payloads.json` and the official log also prove mint.
Empty after a mint is OBJECT. Do not `kanban daemon --force`. Do not
`kanban swarm`. Do not dest-dispatch M5.

## Pitfalls

- Assembling the sequence from three other skills plus `AGENTS.md` (dest-8
  restated the protocol six times and read `k4_*.py`).
- Skipping speckit because K4 does not scrape `tasks.md` (WAVE 1 made
  `tasks.md` **binding**, not generative of cards).
- Inventing `/q/health` as a story (constitution III: if health exists, at
  `/q/health`; VII stands).
- Prescribing `specify workflow run speckit` (Operator `165811ZO` bare
  form; Architect `170540ZA` hermes `files: {}`). Follow
  `speckit-specify` / `speckit-plan` / `speckit-tasks` as Hermes skills.
  dest-9/10/12 `Unknown skill(s): speckit-specify` is `kanban_block`,
  not a hand-authored `tasks.md` and not a stamped workflow-run receipt.
