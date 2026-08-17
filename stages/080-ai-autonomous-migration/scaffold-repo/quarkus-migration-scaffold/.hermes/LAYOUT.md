# Hermes taxonomy homes (AD-H §7)

**Rule:** classify first; kind determines home. Do not add top-level `scripts/`
for new procedures.

| Kind | Home | Examples here |
|------|------|----------------|
| Standing convention | `AGENTS.md` | Java 21, native Quarkus, task-id correlation |
| Identity | authored `.hermes/SOUL.md`; loaded `$HERMES_HOME/SOUL.md` | factory places + sha256-verifies (AD-H §14) |
| Procedural knowledge + tool invocation | `.hermes/skills/<category>/<name>/` | `scan-with-mta`, `derive-legacy-boot3`, `init-spec-workspace` |
| Deterministic **enforcement** (path-invoke) | `.hermes/skills/harness/<name>/` | `validate-contracts`, `dispatch-phase`, `enforce-authority-boundary` |
| Deterministic **domain** gate | `.hermes/skills/gates/check-domain-parity/` | G-1..G-4 vocabulary names below |
| Scaffold lint | `.hermes/skills/harness/validate-contracts/scripts/check-no-hermes-context-override.sh` | no `.hermes.md` override |
| SDD readiness checks | `.hermes/skills/sdd/check-spec-readiness/` | Non-Goals, Q-*, §S.6 |
| Entry-point inventory | `.hermes/skills/analysis/inventory-entry-points/` | W2 §11.3 scanner |
| Harness meta-validate | `.hermes/skills/harness/validate-contracts/` | specimen-free suite |
| Provision assets (not runtime) | `.hermes/provision/` | Spec Kit Non-Goals override template |
| Phase / run data | `evidence/` | findings, inventory JSON, fixtures, acks; MTA raw report is `evidence/mta/` (SR-8) |
| Task authority contract | `.hermes/skills/harness/enforce-authority-boundary/references/task-authority.md` | AD-H §16 — task-type obligations, privilege, human checkpoints |
| Grounded generation contract | `.hermes/skills/harness/ground-in-harvest/` | AD-H §17 — consult order, citation, anti-invention (no `governance/` folder) |
| Validation / release contract | `AGENTS.md (doctrine; was validation-release-gates)` | AD-H §18 — phase gates, regression, failure routing |
| Validation / release skill | `.hermes/skills/gates/check-release-readiness/` | matrix lint + verdict routing |
| Auditability contract | `.hermes/skills/harness/record-run-evidence/` | AD-H §19 — provenance, digests, early metric (no `governance/` folder) |
| Provenance schema | `.hermes/skills/harness/record-run-evidence/` | Kanban metadata fields (retired `governance/schemas/generation-provenance.md`) |
| Kanban body schema | `.hermes/skills/sdd/check-spec-readiness/` | W2 §6.1 typed refs + failure codes (retired `governance/schemas/kanban-body.md`) |
| SDD stack (workspace only) | `.specify/` + `specs/` | AD-S — never commit `.specify/` in golden |
| Task state | Hermes Kanban | not parallel CSV/ledgers |

## Domain gate vocabulary (binding)

| ID | Directory / script stem | Meaning |
|----|-------------------------|---------|
| G-1 | `g1-characterization` | characterization substance / mutation (volume via PIT 1.25.5 dry-run) |
| G-2 | `g2-harvest-fidelity` | obligation conservation vs harvest |
| G-3 | `g3-findings-delta` | MTA findings closure |
| G-4 | `g4-runtime-parity` | observed runtime parity |

Admission fixture trees: `.hermes/skills/gates/check-release-readiness/fixtures/admission/<stem>/`.

## How to invoke

Prefer skill paths (Hermes sets `HERMES_SKILL_DIR` when a skill is loaded):

```bash
bash "${HERMES_SKILL_DIR}/scripts/<script>"
```

From a shell without a loaded skill:

```bash
bash .hermes/skills/harness/validate-contracts/scripts/validate.sh
bash .hermes/skills/gates/check-domain-parity/scripts/run-admission.sh
```

## Skill / enforcement index

Guidance (card-attachable) and enforcement (path-invoke only):

| Leaf | Kind | Purpose |
|------|------|---------|
| `derive-legacy-boot3` | guidance | Boot 2→3 derivation + manifest check |
| `scan-with-mta` | guidance | `mta-cli` analyze + findings normalize/schema |
| `init-spec-workspace` | guidance | AD-S Spec Kit provision |
| `inventory-entry-points` | guidance | Entry-point scanner |
| `check-spec-readiness` | guidance | Pattern-steals + §S.6 lints |
| `check-domain-parity` | guidance | G-1..G-4 + admission fixtures |
| `check-release-readiness` | guidance | AD-H §18 phase matrix + routing |
| `spring-to-quarkus-patterns` | guidance | IMPLEMENT mapping cards |
| `manage-quarkus-extensions` | guidance | Extension add/rm (RH BOM) |
| `bootstrap-quarkus-project` | guidance | Destination Quarkus create (CLI\|Maven) |
| `dispatch-phase` | enforcement | Kanban create+dispatch; `--parent`/`link` is the phase DAG (BV19-3); named seat assignees |
| `validate-contracts` | enforcement | Specimen-free harness suite |
| `enforce-authority-boundary` | enforcement | Acks + write fence + write-set hook; EX-5 overlay lint |
| `ground-in-harvest` | enforcement | Citation lint + invent-without-locus refuse |
| `record-run-evidence` | enforcement | Provenance lint + scoped compile gate |
| *(platform)* `harness-skill-authoring` | — | CS-9 / R-SK land-time lint — not golden (R-SK.9) |
