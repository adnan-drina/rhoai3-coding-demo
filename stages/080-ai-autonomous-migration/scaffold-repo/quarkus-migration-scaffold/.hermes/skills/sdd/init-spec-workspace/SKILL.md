---
name: init-spec-workspace
description: When a workspace has no .specify/ — installs pinned Spec Kit, the Non-Goals override and the AD-S stop rule
license: Apache-2.0
compatibility: Linux seat; network to install pinned Spec Kit CLI
metadata:
  author: rhoai3-harness-team
  version: "1.2.0"
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
4. Writes `external_dirs` reminder beside this skill; when `HERMES_HOME` is relocated, **ensures** `skills.external_dirs` on managed/`HERMES_HOME` `config.yaml` before assert (covers init-ai-tools skip when Hermes venv absent)
5. Stamps `.specify/AD-S-STOP-RULE.md`

## Stop rule (non-negotiable)

After `/speckit-tasks` (optional `/speckit-analyze`) → `kanban_create()`.
**Never** `/speckit-implement`.

## Pitfalls

- Hermes binary may be absent at postStart — `--ignore-agent-tools` is required;
  skills still land under `~/.hermes/skills/`.
- When `HERMES_HOME` is relocated, **assert** (not merely remind) that
  `skills.external_dirs` lists both `<modernized>/.hermes/skills` and
  `$HOME/.hermes/skills` — `scripts/check-external-dirs.py` (also in
  `validate-contracts`).


## Verification

- Four artifacts must exist **together** under the workspace root: `.specify/`
  (from `specify init`), `.specify/templates/overrides/spec-template.md`,
  `.specify/AD-S-STOP-RULE.md`, and
  `.hermes/skills/sdd/init-spec-workspace/EXTERNAL_DIRS.note`.
- `.specify/.rhoai3-ads-provisioned` holds a UTC timestamp and is written
  **last**; a second run prints `already provisioned (<ts>) — skip` on stderr
  (plus one JSON object on stdout with `skipped:true`) and exits 0.
  **Silent-failure catch:** marker present but the Non-Goals override missing
  means a partial or hand-made init — delete the marker and re-run, because the
  marker alone suppresses all later provisioning.
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
