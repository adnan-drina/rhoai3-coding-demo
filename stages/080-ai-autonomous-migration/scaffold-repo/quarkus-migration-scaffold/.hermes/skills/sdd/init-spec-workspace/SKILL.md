---
name: init-spec-workspace
description: When a workspace has no .specify/ — installs pinned Spec Kit, the Non-Goals override, the unique-owner tasks-template override, the destination constitution, the speckit overlay that removes implement, the AD-S stop rule, copies speckit-specify into the project skills root plus sdd/, and installs a PATH shim so a worker-shell specify workflow run speckit finds speckit-specify when HOME is the profile (does not add user-root external_dirs)
license: Apache-2.0
compatibility: Linux seat; network to install pinned Spec Kit CLI
metadata:
  author: rhoai3-harness-team
  version: "1.4.9"
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
2. `HOME=<project> specify init --here --integration hermes --force --ignore-agent-tools` (spec-kit 0.16.1 looks at Path.home()/.hermes/skills)
2b. Copies `speckit-specify` (and plan/tasks/analyze, never implement) from
    specify-init's Hermes skill install into
    `<modernized>/.hermes/skills/` **and** `<modernized>/.hermes/skills/sdd/`
    so implementer `skills list` names `speckit-specify`. Does **not** add
    user-root `external_dirs`.
2c. Installs PATH name `specify` (`<modernized>/.hermes/bin/specify`; dest-init
    also writes `HERMES_MANAGED_DIR/bin/specify`) so a worker shell
    `specify workflow run speckit` resolves `speckit-specify` when HOME is
    the profile. Control: `assert-specify-run-from-worker-home.py`.
3. Copies Non-Goals override from
   `${HERMES_SKILL_DIR}/assets/spec-template.md` →
   `.specify/templates/overrides/spec-template.md`
4. Copies unique-owner tasks override from
   `${HERMES_SKILL_DIR}/assets/tasks-template.md` →
   `.specify/templates/overrides/tasks-template.md` (one creator phase per
   live dest path unless a named non-empty successor set supersedes that
   path; HTTP entry-point rows stay exactly one owner; Add/Verify remain
   amend; polish tasks that name a dest file Create it; source type-inventory
   dest twins; generated types carry spec + configure the dest generator)
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

After `/speckit-tasks` (optional `/speckit-analyze`) → K4 convert →
`.hermes/kernel/k4_mint.py` (`hermes kanban create`). **Never**
`/speckit-implement`. Invoke `specify-from-project.sh --root` (do not
PATH-lookup `specify`; dest-9 uv specify shadows the dest-init shim).
Bare form exits 1 (`Required input 'spec'`). Do not rely on workers
prefixing `HOME=/projects/modernized`.
M2 PLAN consumes M1 KEEP evidence via parent `kanban_attachments` plus
`evidence/findings-handoff.json` — not from metadata path lists.

## Pitfalls

- Hermes binary may be absent at postStart — `--ignore-agent-tools` is required;
  skills still land under `~/.hermes/skills/`. `seed-speckit-skills.py` then
  copies `speckit-specify` into the project skills root and `sdd/` tree
  (Architect `125450Z`). dest-init + `install-specify-shim.sh` put `specify`
  on PATH so a worker shell without `HOME=` still hits the project skills
  root. Do **not** add `/home/user/.hermes/skills`
  to the implementer profile.
- When `HERMES_HOME` is relocated, **assert** (not merely remind) that
  `skills.external_dirs` lists both `<modernized>/.hermes/skills` and
  dest-user `/home/user/.hermes/skills` — `scripts/check-external-dirs.py`.
  dest-init (GitOps maas-api-key-provisioning.yaml) is the actor that lists
  that path. Listed extra paths that do not exist fail closed naming the
  path (Hermes otherwise silent-skips). Worker `$HOME` is profile-relative,
  not that slot. Architect
  `105906ZA`: dest-init’s dest-user path is the contract, not worker
  `Path.home()`. Do not `kanban_complete` around exit 1; typed
  `kanban_block`.
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
- After provision, `<modernized>/.hermes/skills/speckit-specify/SKILL.md`
  **and** `<modernized>/.hermes/skills/sdd/speckit-specify/SKILL.md`
  exist. `assert-specify-skills-root.py` refuses a nested-only copy.
  `assert-specify-run-from-worker-home.py` PASSes when `HOME` is a profile
  dir with 0 speckit skills and bare `specify workflow run speckit` still
  finds `speckit-specify`. Implementer `skills list` names it without a
  user-root `external_dirs` grant.
- dest-init (GitOps) must smoke helper-by-path
  `specify workflow run speckit -i spec=dest-init-smoke` via `SPECIFY_REAL`
  and assert **four** overlay skills (`speckit-specify`, `speckit-clarify`,
  `speckit-plan`, `speckit-tasks`) plus `hermes kanban ls`, and must **run**
  `specify init --here --integration hermes --force --ignore-agent-tools`
  plus `mvn test` on **fresh** trees (`dest-init-fresh-smoke` /
  `dest-init-mvn-smoke`) — not dest-9 `/projects/modernized`
  (`assert-dest-init-smokes-mandated-tools.py`). One-skill specify is not
  the workflow. Shim-only dest-init REFUSE. Do not dest-apply onto dest-9.
- Relocated `HERMES_HOME`: `check-external-dirs.py` must print
  `OK: external_dirs lists project + home skills (<config>)`. A listed
  extra path that does not exist fails closed **naming the path**.
  `assert idle` means `HERMES_HOME` is unset or default — it is not
  evidence for a relocated seat.
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
