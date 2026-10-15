---
name: rhoai-release-and-support-posture
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when a README, slide, component Alignment table or PR in this repo says
  "supported", "GA", "Technology Preview", "Developer Preview", "deprecated",
  "removed" or "EUS" about an OpenShift AI 3.5 feature; when reviewing the
  release notes (new features, known issues, support removals) before a z-stream
  or minor upgrade of the stable-3.5 Subscription; or when labelling a demo
  feature such as MaaS, external models, the MCP Lifecycle Operator, AgentOps or
  Kueue dashboard support. Do NOT use for Subscription channel mechanics (use
  rhoai-update-channels), API version stability (use rhoai-api-tiers), supported
  OCP versions and hardware (use rhoai-platform-planning), or component
  configuration (use the component rhoai-* skill).
---

# RHOAI Release And Support Posture

Thin skill: how this repo labels feature maturity, with the posture itself in
the linked OpenShift AI 3.5 release notes and the Customer Portal lifecycle
page. Each component README records its own posture in its "Alignment with
official guidance" table.

## When to use

- A sentence claims a feature is supported, GA or production-ready.
- A component enables a Technology Preview (TP) or Developer Preview (DP)
  feature, or keeps a deprecated component.
- Before moving the operator to a new 3.5 z-stream or to another minor.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| The demo follows `stable-3.5` with `Automatic` approval, bounded by a minimum installed version `3.5.1` | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-operator/subscription.yaml`, `scripts/platform/check-operator-policy.py` | [Lifecycle][lifecycle]; see `rhoai-update-channels` |
| TP and DP features may be shown, labelled as such where they are used; posture lives in the component README Alignment table, not in this skill | component READMEs under `gitops/stages/` | [Technology Preview features][tp], [Developer Preview features][dp] |
| Dashboard flags that enable preview UI: `connectionTest` (TP), `disableKueue: false` (DP), `modelAsService` (TP, Stage 040) | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/README.md` (OdhDashboardConfig) | [3.5 GA TP features][tp35] |
| MaaS and external models are labelled TP | `gitops/stages/040-governed-models-as-a-service/040-local-models/README.md` | [3.5 GA TP features][tp35] |
| Stage 060 MCP Lifecycle Operator is labelled TP; the MCP Catalog and AgentOps view DP | `stages/060-agent-runtime-and-agentops/README.md` | [3.5 GA TP features][tp35], [3.5 GA DP features][dp35] |
| Deprecated `llamastackoperator` stays `Removed`; OGX is used instead | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/datasciencecluster.yaml` | [Deprecated][deprecated] |
| AutoRAG and AutoML are out of scope | `docs/OPERATIONS.md` (Ownership and stage boundaries) | [Product features][features] |
| Product doc version is pinned to the Subscription channel; upgrades change pin, map and skills together | `.agents/references/red-hat-doc-map.yaml`, `docs/PLATFORM_BASELINE.md` | [Release notes overview][overview] |

## Procedure

1. Find the feature in the TP and DP sections of the release notes; note the
   release section (3.5 GA, EA2, EA1) that lists it. Features first listed in
   3.4 sections can since have moved to GA; read the newest mention.
2. Check [Support removals][removals] for deprecated or removed items the repo
   uses (`git grep` the component name under `gitops/`).
3. Write the label in the component README Alignment table (status column) and,
   for user-facing steps, in the stage README. Keep failure details out of
   READMEs (`docs/TROUBLESHOOTING.md`).
4. Before an upgrade, read [Known issues][known] for the target release and
   record any that affect a stage in `BACKLOG.md` or the component README.
5. Confirm the installed release after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get subscription rhods-operator -n redhat-ods-operator \
     -o jsonpath='{.spec.channel} {.status.installedCSV}{"\n"}'
   python3 scripts/shared/check-doc-links.py --versions
   ```

## Pitfalls

- TP status is per feature, not per component: MLflow is GA while some MLflow
  features (for example prompt management) are listed as TP. Check the exact
  feature.
- Early Access (EA) builds have no support; do not run them in this demo.
- The lifecycle page is a Customer Portal article without a version in its URL;
  quote the date you read it. The 3.5 dates were not published when last read.
- A dashboard tile or catalog entry is not evidence that a feature is GA or
  installed.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Overview and new features | [Overview][overview], [New features and enhancements][new] |
| Technology Preview | [Technology Preview features][tp], [3.5 GA TP features][tp35] |
| Developer Preview | [Developer Preview features][dp], [3.5 GA DP features][dp35] |
| Deprecated and removed | [Support removals][removals], [Deprecated][deprecated], [Removed functionality][removed] |
| Known and resolved issues | [Known issues][known], [Issues discovered at 3.5 GA][known35], [Resolved issues][resolved] |
| Product features | [Product features][features] |
| Lifecycle phases (Full Support, Maintenance, EUS, EA) | [Self-Managed life cycle][lifecycle] (Customer Portal) |

## Related skills

`rhoai-update-channels`, `rhoai-api-tiers`, `rhoai-platform-planning`,
`review-doc-alignment`, `update-demo-docs`.

[overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/release_notes/index#overview-of-openshift-ai_relnotes
[new]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/release_notes/index#new-features-and-enhancements_relnotes
[tp]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/release_notes/index#technology-preview-features_relnotes
[tp35]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/release_notes/index#three_5_ga_technology_preview_features
[dp]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/release_notes/index#developer-preview-features_relnotes
[dp35]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/release_notes/index#three_5_ga_developer_preview_features
[removals]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/release_notes/index#support-removals_relnotes
[deprecated]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/release_notes/index#deprecated
[removed]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/release_notes/index#removed_functionality
[known]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/release_notes/index#known-issues_relnotes
[known35]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/release_notes/index#issues_discovered_at_version_3_5_ga
[resolved]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/release_notes/index#resolved-issues_relnotes
[features]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/release_notes/index#product-features_relnotes
[lifecycle]: https://access.redhat.com/support/policy/updates/rhoai-sm/lifecycle
