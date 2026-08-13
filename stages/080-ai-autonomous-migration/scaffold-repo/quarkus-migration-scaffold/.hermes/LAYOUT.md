# Hermes taxonomy homes (AD-H §7)

**Rule:** classify first; kind determines home. Do not add top-level `scripts/`
for new procedures.

| Kind | Home | Examples here |
|------|------|----------------|
| Standing convention | `AGENTS.md` | Java 21, native Quarkus, task-id correlation |
| Identity | `.hermes/SOUL.md` | faithfulness, stop-on-bad-input |
| Procedural knowledge + tool invocation | `.hermes/skills/<name>/` | `mta-analysis`, `derive-legacy-boot3`, `specify-workspace-init` |
| Deterministic **domain** gate | `.hermes/skills/gates/domain-gates/` | G-1..G-4 vocabulary names below |
| Scaffold lint | `.hermes/skills/harness/harness-validate/scripts/check-no-hermes-context-override.sh` | no `.hermes.md` override |
| SDD readiness checks | `.hermes/skills/sdd/sdd-readiness/` | Non-Goals, Q-*, §S.6 |
| Entry-point inventory | `.hermes/skills/analysis/inventory-entry-points/` | W2 §11.3 scanner |
| Harness meta-validate | `.hermes/skills/harness/harness-validate/` | specimen-free suite |
| Provision assets (not runtime) | `.hermes/provision/` | Spec Kit Non-Goals override template |
| Phase / run data | `migration/` | findings, inventory JSON, fixtures, contracts, schemas, acks |
| Task authority contract | `migration/contracts/task-authority.md` | AD-H §16 — task-type obligations, privilege, human checkpoints |
| Grounded generation contract | `migration/contracts/grounded-generation.md` | AD-H §17 — consult order, citation, anti-invention |
| Validation / release contract | `migration/contracts/validation-release-gates.md` | AD-H §18 — phase gates, regression, failure routing |
| Validation / release skill | `.hermes/skills/gates/validation-release-gates/` | matrix lint + verdict routing |
| Auditability contract | `migration/contracts/auditability-repeatability.md` | AD-H §19 — provenance, digests, early metric |
| Provenance schema | `migration/schemas/generation-provenance.md` | Kanban metadata fields |
| Kanban body schema | `migration/schemas/kanban-body.md` | W2 §6.1 typed refs + failure codes |
| SDD stack (workspace only) | `.specify/` + `specs/` | AD-S — never commit `.specify/` in golden |
| Task state | Hermes Kanban | not parallel CSV/ledgers |

## Domain gate vocabulary (binding)

| ID | Directory / script stem | Meaning |
|----|-------------------------|---------|
| G-1 | `g1-characterization` | characterization substance / mutation (volume via PIT 1.25.5 dry-run) |
| G-2 | `g2-harvest-fidelity` | obligation conservation vs harvest |
| G-3 | `g3-findings-delta` | MTA findings closure |
| G-4 | `g4-runtime-parity` | observed runtime parity |

Admission fixture trees: `migration/fixtures/admission/<stem>/`.

## How to invoke

Prefer skill paths (Hermes sets `HERMES_SKILL_DIR` when a skill is loaded):

```bash
bash "${HERMES_SKILL_DIR}/scripts/<script>"
```

From a shell without a loaded skill:

```bash
bash .hermes/skills/harness/harness-validate/scripts/validate.sh
bash .hermes/skills/gates/domain-gates/scripts/run-admission.sh
```

## Skill index

| Skill | Purpose |
|-------|---------|
| `derive-legacy-boot3` | Boot 2→3 derivation + manifest check |
| `phase-dispatch` | Hermes Kanban create+dispatch for M1–M5 from `phase-dispatch.yaml` |
| `mta-analysis` | `mta-cli` analyze + findings normalize/schema (inside M1/M5 worker) |
| `specify-workspace-init` | AD-S Spec Kit provision |
| `inventory-entry-points` | Entry-point scanner |
| `sdd-readiness` | Pattern-steals + §S.6 lints |
| `domain-gates` | G-1..G-4 + admission fixtures (parser/fixture only until live prove) |
| `harness-validate` | One entrypoint for the above (+ context-override lint) |
| *(platform)* `harness-skill-authoring` | CS-9 / R-SK land-time lint — not golden (R-SK.9) |
| `enforce-authority-boundary` | AD-H §16 acks + write fence; phase `skills[]` in `phase-dispatch.yaml` |
| `grounded-generation` | AD-H §17 citation lint + invent-without-locus refuse |
| `spring-to-quarkus-patterns` | IMPLEMENT mapping cards (REST / DI / persistence); quarkusio-first |
| `validation-release-gates` | AD-H §18 phase matrix + INCONCLUSIVE-never-ship routing |
| `auditability-repeatability` | AD-H §19 provenance lint + `reconstruct-from-commit` (fail closed) |
