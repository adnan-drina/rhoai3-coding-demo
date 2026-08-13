# Hermes taxonomy homes (AD-H §7)

**Rule:** classify first; kind determines home. Do not add top-level `scripts/`
for new procedures.

| Kind | Home | Examples here |
|------|------|----------------|
| Standing convention | `AGENTS.md` | Java 21, native Quarkus, task-id correlation |
| Identity | authored `.hermes/SOUL.md`; loaded `$HERMES_HOME/SOUL.md` | factory places + sha256-verifies (AD-H §14) |
| Procedural knowledge + tool invocation | `.hermes/skills/<category>/<name>/` | `scan-with-mta`, `derive-legacy-boot3`, `init-spec-workspace` |
| Deterministic **enforcement** (path-invoke) | `.hermes/enforcement/<name>/` | `validate-contracts`, `dispatch-phase`, `enforce-authority-boundary` |
| Deterministic **domain** gate | `.hermes/skills/gates/check-domain-parity/` | G-1..G-4 vocabulary names below |
| Scaffold lint | `.hermes/enforcement/validate-contracts/scripts/check-no-hermes-context-override.sh` | no `.hermes.md` override |
| SDD readiness checks | `.hermes/skills/sdd/check-spec-readiness/` | Non-Goals, Q-*, §S.6 |
| Entry-point inventory | `.hermes/skills/analysis/inventory-entry-points/` | W2 §11.3 scanner |
| Harness meta-validate | `.hermes/enforcement/validate-contracts/` | specimen-free suite |
| Provision assets (not runtime) | `.hermes/provision/` | Spec Kit Non-Goals override template |
| Phase / run data | `migration/` | findings, inventory JSON, fixtures, contracts, schemas, acks |
| Task authority contract | `governance/contracts/task-authority.md` | AD-H §16 — task-type obligations, privilege, human checkpoints |
| Grounded generation contract | `governance/contracts/grounded-generation.md` | AD-H §17 — consult order, citation, anti-invention |
| Validation / release contract | `governance/contracts/validation-release-gates.md` | AD-H §18 — phase gates, regression, failure routing |
| Validation / release skill | `.hermes/skills/gates/check-release-readiness/` | matrix lint + verdict routing |
| Auditability contract | `governance/contracts/auditability-repeatability.md` | AD-H §19 — provenance, digests, early metric |
| Provenance schema | `governance/schemas/generation-provenance.md` | Kanban metadata fields |
| Kanban body schema | `governance/schemas/kanban-body.md` | W2 §6.1 typed refs + failure codes |
| SDD stack (workspace only) | `.specify/` + `specs/` | AD-S — never commit `.specify/` in golden |
| Task state | Hermes Kanban | not parallel CSV/ledgers |

## Domain gate vocabulary (binding)

| ID | Directory / script stem | Meaning |
|----|-------------------------|---------|
| G-1 | `g1-characterization` | characterization substance / mutation (volume via PIT 1.25.5 dry-run) |
| G-2 | `g2-harvest-fidelity` | obligation conservation vs harvest |
| G-3 | `g3-findings-delta` | MTA findings closure |
| G-4 | `g4-runtime-parity` | observed runtime parity |

Admission fixture trees: `governance/fixtures/admission/<stem>/`.

## How to invoke

Prefer skill paths (Hermes sets `HERMES_SKILL_DIR` when a skill is loaded):

```bash
bash "${HERMES_SKILL_DIR}/scripts/<script>"
```

From a shell without a loaded skill:

```bash
bash .hermes/enforcement/validate-contracts/scripts/validate.sh
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
| `dispatch-phase` | enforcement | Kanban create+dispatch from `phase-dispatch.yaml` |
| `validate-contracts` | enforcement | Specimen-free harness suite |
| `enforce-authority-boundary` | enforcement | Acks + write fence + untrusted |
| `ground-in-harvest` | enforcement | Citation lint + invent-without-locus refuse |
| `record-run-evidence` | enforcement | Provenance lint + reconstruct |
| *(platform)* `harness-skill-authoring` | — | CS-9 / R-SK land-time lint — not golden (R-SK.9) |
