# Skill naming + content convention (R-SK.10)

**Status:** Operator directive E-20260813T123906Z (Clean-Architecture uplift,
pre-v14). Extends R-SK.1/R-SK.5/R-SK.7; does not amend the R-SK.7 fixed
category set.

**Why this exists:** under official progressive disclosure, `skills_list()`
exposes only **name + description + category**. That triple is the entire
basis on which the agent decides to open a skill. A name that states a
quality rather than an action, or a description that restates the name, gives
the agent nothing to select on — it then re-derives from scratch what a skill
already knew. Naming here is an interface, not a filing label.

Official grounding: https://hermes-agent.nousresearch.com/docs/user-guide/features/skills
(§Progressive disclosure, §Creating Skills).

## Rules

**N1 — Leaf name is an imperative verb-object phrase.** Name the action the
skill performs (`validate-contracts`, `dispatch-phase`), not the quality it
embodies (`record-run-evidence`) and not its subject area alone
(`enforce-authority-boundary`). The agent is choosing an action; name it as one.

**Gerund considered, imperative chosen (E-20260813T140501Z).** Anthropic
best-practices §Naming conventions says "Consider using gerund form" and
lists action-oriented imperative (`process-pdfs`) as an **acceptable
alternative**. Gerund is not an agentskills.io spec MUST. House law is
imperative verb-object applied consistently (Architect A7). The lint
enforces spec MUSTs only; the rename table below delivers N1 consistency.

**N2 — A leaf name never repeats its category.** Under the pre-Wave-B layout,
`harness/harness-validate` declared "harness" three times (directory,
`metadata.hermes.category`, and name prefix). Category already ships in the
selection triple; the prefix only consumes signal. Enforced by lint.

**N3 — Pair skills are the sole N1 exception.** A skill carrying
transformation knowledge for a specific source→destination pair keeps the
`<source>-to-<destination>-patterns` form (per R-SK.7, "pair skills live here
by leaf name"). The pair name is the identifier and stays extensible for
future pairs. Listed in `r-sk10-name-keep.txt`.

**N4 — `description` states trigger and output, on one line.** It is the
selection signal, not a title. "Apply Spring→Quarkus migration patterns"
restates the name; a description earns its place by saying what condition
makes this the right skill and what it produces.

**N5 — The four required sections carry skill-specific content.** R-SK
requires `## When to Use`, `## Procedure`, `## Pitfalls`, `## Verification`
in that order. **House rule §K:** selection lives only under `## When to Use`
— never `## Required When`. `## Pitfalls` names silent-failure modes (not a
restatement of Procedure). Presence was once satisfiable with filler, and was:
before this uplift, `## Verification` read "Scripts under `scripts/` exit 0 on a
healthy seat." in
**13 of 13** skills, and 8 of 13 had a placeholder `## When to Use`. Identical
prose across skills is a content defect even though it passes a
section-presence check. `## Verification` must name the artifact produced and
the assertion that would catch a silent failure.

**N6 — Leaf names move only at a mint boundary.** Unchanged from R-SK.7: cards
attach skills by leaf name (`skills=[...]` / `--skill`) and bundles pin them,
so a mid-chain rename breaks live anchors. Rename between chains only.

## v14 mint-boundary rename (APPLIED — Wave B mint)

Harness packs live under `.hermes/skills/harness/` (EX-3; Wave B's
`.hermes/enforcement/` category is dissolved). Guidance leaves stay under
`.hermes/skills/<category>/`. Harness packages are path-invoked — not card
`skills[]` / bundles.

| Was | Now | Tree / reason |
|-----|-----|---------------|
| `analysis/mta-analysis` | `analysis/scan-with-mta` | guidance · N1, N2 |
| `gates/domain-gates` | `gates/check-domain-parity` | guidance · N1, N2 |
| `gates/validation-release-gates` | `gates/check-release-readiness` | guidance · N1, N2 |
| `harness/auditability-repeatability` | `enforcement/record-run-evidence` | enforcement · N1 |
| `harness/grounded-generation` | `enforcement/ground-in-harvest` | enforcement · N1 |
| `harness/harness-validate` | `enforcement/validate-contracts` | enforcement · N2 |
| `harness/phase-dispatch` | `enforcement/dispatch-phase` | enforcement · N1 |
| `harness/role-authority` (then `harness/enforce-authority-boundary`) | `enforcement/enforce-authority-boundary` | enforcement · N1; role persona retired E-144117Z |
| `sdd/sdd-readiness` | `sdd/check-spec-readiness` | guidance · N1, N2 |
| `sdd/specify-workspace-init` | `sdd/init-spec-workspace` | guidance · N1 |

**Unchanged:** `analysis/inventory-entry-points` and
`migration/derive-legacy-boot3` already satisfy N1;
`migration/spring-to-quarkus-patterns` is an N3 pair skill;
`migration/manage-quarkus-extensions` (Wave A);
`migration/bootstrap-quarkus-project` (Wave B, new guidance).

See also `references/_rename-table-applied.md` for the applied cutover note.

## Enforcement

`check-skill-conformance.py` enforces N2 mechanically and N1 by verb-lead
heuristic, with `references/r-sk10-name-keep.txt` as the Architect-justified
exception list (N3 entries live there). N4/N5 are review-enforced at the
Deputy audit gate — a landing whose `## Verification` matches another skill's
verbatim gets request-changes, not a note.
