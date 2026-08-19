---
name: init-spec-workspace
description: When a workspace has no .specify/ — installs pinned Spec Kit, the Non-Goals override, the unique-owner tasks-template override, the destination constitution, the speckit overlay that removes implement, and the AD-S stop rule
license: Apache-2.0
compatibility: Linux seat; network to install pinned Spec Kit CLI
metadata:
  author: rhoai3-harness-team
  version: "1.4.1"
  hermes:
    tags:
    - sdd
    - m2
    category: sdd
    kind: guidance
---
# Spec Kit workspace init (AD-S)

## When to Use

- `/projects/modernized` has no `.specify/` (fresh workspace, or a wipe removed
  it) and M2 needs `/speckit-*` — provisioning must precede `/speckit-specify`,
  since the Non-Goals override is a template, not a post-edit.
- `specify` is not on PATH at postStart and the seat still owes M2 authoring.
- After `HERMES_HOME` is relocated — re-run to **assert** `skills.external_dirs`
  still lists both skills roots (relocation silently hides `/speckit-*`).
- **Not** for checking what spec-kit produced — `check-spec-readiness` lints specs,
  Kanban bodies, and partition coverage. This skill provisions only; it never
  reads spec content.
- **Not** on the golden scaffold source tree and **not** in
  `harness-refactoring/` — init refuses outside `/projects/*` when the
  ROOT is outside `/projects/*` (`FORCE_AD_S_PROVISION=1` dry-run). Golden assert: `check-specify-absent.py`.

## Procedure

```bash
bash "${HERMES_SKILL_DIR}/scripts/init-workspace.sh" /projects/modernized
# standalone re-assert (also runs inside init when HERMES_HOME is relocated)
python3 "${HERMES_SKILL_DIR}/scripts/check-external-dirs.py" /projects/modernized
```

Idempotent via `.specify/.rhoai3-ads-provisioned`. Spec Kit is pinned
(`specify-cli==0.16.1`, R-HX.1); override only via `SPECIFY_CLI_VERSION`.

## What it does (AD-S)

1. Ensures `specify-cli` (`uv tool install specify-cli` if needed)
2. `specify init --here --integration hermes --force --ignore-agent-tools`
3. Copies Non-Goals override from
   `${HERMES_SKILL_DIR}/assets/spec-template.md` →
   `.specify/templates/overrides/spec-template.md`
4. Copies unique-owner tasks override from
   `${HERMES_SKILL_DIR}/assets/tasks-template.md` →
   `.specify/templates/overrides/tasks-template.md` (one creator phase per
   dest path; Add/Verify remain amend; polish tasks that name a dest file
   Create it; source type-inventory dest twins; generated types carry spec
   + configure the dest generator)
5. Copies destination constitution from
   `${HERMES_SKILL_DIR}/assets/constitution.md` →
   `.specify/memory/constitution.md` when missing or still spec-kit
   placeholders (`[PROJECT_NAME]` / `[PRINCIPLE_1…]`)
6. Copies `stop-before-implement.overlay.yml` →
   `.specify/workflows/overlays/speckit/stop-before-implement.yml`
   (`extends: speckit`, `remove: implement`, inserts `clarify`, names M1
   evidence paths on specify args; emit pin is the tasks override, not
   mint-transcribed HTTP). Removes leftover `sdd-to-tasks.yml`.
7. Writes `external_dirs` reminder under `.specify/EXTERNAL_DIRS.note`; when `HERMES_HOME` is relocated, **ensures** `skills.external_dirs` on managed/`HERMES_HOME` `config.yaml` before assert (covers init-ai-tools skip when Hermes venv absent)
8. Stamps `.specify/AD-S-STOP-RULE.md` (includes `specify workflow run speckit`)
9. If `.git/hooks` exists, installs the LG9a pre-commit that runs the suite against `git checkout-index`

## Stop rule (non-negotiable)

After `/speckit-tasks` (optional `/speckit-analyze`) → Kanban mint.
**Never** `/speckit-implement`. Run `specify workflow run speckit`.

## Pitfalls

- Hermes binary may be absent at postStart — `--ignore-agent-tools` is required;
  skills still land under `~/.hermes/skills/`.
- When `HERMES_HOME` is relocated, **assert** (not merely remind) that
  `skills.external_dirs` lists both `<modernized>/.hermes/skills` and
  `$HOME/.hermes/skills` — `scripts/check-external-dirs.py` (also in
  `validate-contracts`).
- Stamping a second Path-A workflow YAML that has to be kept in sync with
  upstream `speckit` — use the overlay (`extends: speckit`).


## Verification

- These artifacts must exist **together** under the workspace root: `.specify/`
  (from `specify init`), `.specify/templates/overrides/spec-template.md`,
  `.specify/templates/overrides/tasks-template.md` (unique dest-path owner),
  `.specify/memory/constitution.md` (Quarkus 3.27.3.SP1 / Java 21 — not
  placeholders), `.specify/workflows/overlays/speckit/stop-before-implement.yml`,
  `.specify/AD-S-STOP-RULE.md`, and
  `.specify/EXTERNAL_DIRS.note` (workspace-only; gitignored — not under R-SK.5 skill scan).
- `.specify/.rhoai3-ads-provisioned` holds a UTC timestamp and is written
  **last**; a second run prints `already provisioned (<ts>) — skip specify init; overlays refreshed` on stderr
  (plus one JSON object on stdout with `skipped:true`) and still refreshes
  constitution / speckit overlay when the dest constitution is placeholders.
- `specify workflow resolve speckit` shows no `implement` step and no
  `review-spec` / `review-plan` gates; `clarify` is present.
- Fresh provision: stderr ends with
  `[init-spec-workspace] OK — AD-S provision complete (marker …)`; stdout is
  one JSON object `{script,ok,skipped,root,marker,provisioned_at}` (UPLIFT-2).
  Progress/`log` lines are stderr-only.
- Relocated `HERMES_HOME`: `check-external-dirs.py` must print
  `OK: external_dirs lists project + home skills (<config>)`. `assert idle`
  means `HERMES_HOME` is unset or default — it is not evidence for a relocated
  seat.
- Every failure path exits non-zero with `[init-spec-workspace] ERROR: …`
  before the marker is written (missing override asset, `specify` absent after
  install, `.specify/` not created, external_dirs assert failed).

## Hermes Spec Kit skill names

Installed under `~/.hermes/skills` as hyphenated packages (pins: `.hermes/pins.json`
`spec_kit`). Hard-invoke Hermes names, not dotted GitHub slash paths:

| Wrong (obsolete dotted) | Correct (Hermes skill) |
|-------------------------|------------------------|
| `/speckit.specify` | `/speckit-specify` |
| `/speckit.plan` | `/speckit-plan` |
| `/speckit.tasks` | `/speckit-tasks` |
| `/speckit.analyze` | `/speckit-analyze` |
| `/speckit.implement` | **FORBIDDEN** — Kanban only |
