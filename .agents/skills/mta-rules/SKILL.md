---
name: mta-rules
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: mta
  docs-version: "8.3"
  skill-group: "Application Modernization"
description: >
  Use when writing or reviewing custom MTA 8.3 YAML rules in this demo: the
  Stage 130 canary ruleset (rhoai3-canary-00001), konveyor.io/target labels
  that must match the analysis targets, builtin and java provider conditions,
  rule categories and effort, and how a custom ruleset is passed with --rules.
  Do NOT use for running the CLI or reading receipts (use mta-cli), Hub UI
  analysis (use mta-ui), or AI-assisted fixes (use mta-lightspeed).
---

# MTA rules

Thin skill: repo decisions and pitfalls here, rule syntax in the linked MTA
8.3 rules guide. The only custom ruleset in the repo is the Stage 130 canary.

## When to use

- A change to
  `stages/130-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes/planning/mta-rules/`.
- A run blocks with `CANARY_MISSING`, or analysis targets change.
- Someone proposes a project-specific migration rule.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Canary rule `rhoai3-canary-00001`: `category: optional`, `effort: 0`, `builtin.filecontent` on `*.java`; proves the custom ruleset was in the effective selection | `.../.hermes/planning/mta-rules/rhoai3-canary.yaml` | [Rule metadata][meta], [Categories][categories], [builtin provider][builtin] |
| Canary carries one `konveyor.io/target=` label per analysis target (quarkus, jakarta-ee9, cloud-readiness, openjdk21) so any target selection loads it | same file; `analysis.targets`, `custom_rules`, `canary_rule_id` in `gitops/stages/070-advanced-app-platform/070-rhdh/templates/app-migration/skeleton/migration.yaml` | [Rule labels][labels], [Reserved labels][reserved] |
| Canary incidents are not migration obligations: the planner filters `analysis.canary_rule_id` and records `mta.canary.fired` | `.../.hermes/skills/analysis/scan-with-mta/scripts/assert-mta-canary.py` | — |
| Ruleset passed with `--rules <dir>` and never with `--source` | `.../scan-with-mta/scripts/mta-analyze-legacy.sh` | [Custom ruleset][ruleset] |

## Procedure

1. Write a rule in the canary's file layout (YAML list of rules); copy the
   structure from the repo file, the syntax from [YAML rule structure][syntax].
2. Give every rule the target labels the run selects; a rule without a
   matching `konveyor.io/target` label is silently not selected.
3. Run the scaffold tests and a rehearsal, not an ad hoc analysis:

   ```bash
   python3 stages/130-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/analysis/scan-with-mta/scripts/scan-with-mta.test.py
   ./stages/130-ai-autonomous-migration/validate.sh
   ```

## Pitfalls

- Wrong target label, missing `--rules`, or a kantra fallback without custom
  rules all end in `CANARY_MISSING` (comment in `rhoai3-canary.yaml`).
- A canary that matches nothing passes vacuously elsewhere; keep it on a
  pattern every Java application has (`.agents/rules/ensure-cli-capability.md`
  states presence is not capability).
- Wildcard-import annotation incidents can be missed by the Java provider
  (MTA-6530 in the 8.3.0 [known issues][known]); do not rely on such a rule as
  a gate.

## Official documentation (MTA 8.3)

| Topic | Section |
|---|---|
| Basics | [The MTA rules][about], [How MTA analyzes][how], [YAML rule structure][syntax] |
| Metadata | [Structure][meta], [Labels][labels], [Reserved labels][reserved], [Categories][categories] |
| Providers | [How providers work][providers], [Rule condition][cond], [builtin][builtin], [Java][java] |
| Java conditions | [Locations][locations], [Annotation inspection][annotations] |
| Logic | [AND][and], [OR][or], [Chaining][chaining], [Custom variables][vars] |
| Actions | [Tag][tag], [Message][message] |
| Authoring | [Create a YAML rule][create], [Custom ruleset][ruleset] |

## Related skills

`mta-cli`, `mta-ui`, `mta-release-notes`.

[about]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index#about-rules_rules-introduction
[how]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index#how_mta_performs_an_analysis
[syntax]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index#yaml-rule-structure-syntax_rules-introduction
[meta]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index#yaml-rule-metadata-structure_rule-yaml-metadata
[labels]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index#yaml-rule-labels_rule-yaml-metadata
[reserved]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index#reserved-label_rule-yaml-metadata
[categories]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index#yaml-rule-categories_rule-yaml-metadata
[providers]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index#external-providers_rules-prov-cond
[cond]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index#yaml-provider-conditions_rules-prov-cond
[builtin]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index#yaml-builtin-provider_rules-prov-cond
[java]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index#yaml-java-provider_rules-prov-cond
[locations]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index#yaml-java-locations_java-conditions-capabilities
[annotations]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index#yaml-annotation-inspection_java-conditions-capabilities
[and]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index#yaml-and-condition_logical-chaining-custom-variables
[or]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index#yaml-or-condition_logical-chaining-custom-variables
[chaining]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index#yaml-chaining-condition-variables_logical-chaining-custom-variables
[vars]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index#yaml-custom-variables_logical-chaining-custom-variables
[tag]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index#yaml-tag-actions_rule-yaml-actions
[message]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index#yaml-message-actions_rule-yaml-actions
[create]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index#create-first-yaml-rule_creating-rule
[ruleset]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_rules_for_an_mta_analysis/index#yaml-rulesets_rule-rulesets
[known]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/release_notes/index#known-issues-8-3-0_mta-8-3-0
