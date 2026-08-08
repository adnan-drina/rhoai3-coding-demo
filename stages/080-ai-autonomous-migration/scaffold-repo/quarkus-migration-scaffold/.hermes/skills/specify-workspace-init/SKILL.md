---
name: specify-workspace-init
description: >
  Provision-time Spec Kit (AD-S) for the migration workspace: Hermes
  integration, Non-Goals override, never /speckit.implement. Run once after
  workspace start when .specify/ is missing, or when re-provisioning.
---

# Spec Kit workspace init (AD-S)

## When to use

- Fresh migration workspace with no `.specify/` under `/projects/modernized`
- After a wipe that removed `.specify/`
- **Not** on the golden scaffold source tree; **not** in `harness-refactoring/`

## Procedure

```bash
bash "${HERMES_SKILL_DIR}/scripts/init-workspace.sh" /projects/modernized
```

Idempotent via `.specify/.rhoai3-ads-provisioned`.

## What it does (AD-S)

1. Ensures `specify-cli` (`uv tool install specify-cli` if needed)
2. `specify init --here --integration hermes --force --ignore-agent-tools`
3. Copies Non-Goals override from
   `.hermes/provision/spec-kit/overrides/spec-template.md` →
   `.specify/templates/overrides/spec-template.md`
4. Writes `external_dirs` reminder under `.hermes/provision/spec-kit/`
5. Stamps `.specify/AD-S-STOP-RULE.md`

## Stop rule (non-negotiable)

After `/speckit.tasks` (optional `/speckit.analyze`) → `kanban_create()`.
**Never** `/speckit.implement`.

## Pitfalls

- Hermes binary may be absent at postStart — `--ignore-agent-tools` is required;
  skills still land under `~/.hermes/skills/`.
- Keep `$HOME/.hermes/skills` on `skills.external_dirs` when `HERMES_HOME` is
  relocated (spec-kit ignores `$HERMES_HOME` for skill install path).
