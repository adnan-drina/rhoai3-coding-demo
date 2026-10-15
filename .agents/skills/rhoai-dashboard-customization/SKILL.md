---
name: rhoai-dashboard-customization
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when reviewing or changing the OdhDashboardConfig odh-dashboard-config
  in redhat-ods-applications (gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/odhdashboardconfig.yaml):
  spec.dashboardConfig feature flags, which stage owns a flag through the
  010-rhoai-platform ignoreDifferences delegation, preview-feature flags, or a
  dashboard menu that is missing or reverted. Do NOT use for application
  tiles and notebookController (use rhoai-dashboard-applications), access
  groups (use rhoai-users-groups-access), project-scoped resources (use
  rhoai-project-scoped-resources), or usage data collection (use
  rhoai-telemetry-admin-settings).
---

# RHOAI dashboard customization

Thin skill: repo decisions and pitfalls here, option names and defaults in the
linked OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/README.md`
("Delegation model", "OdhDashboardConfig").

## When to use

- A change touches `odhdashboardconfig.yaml` or a stage Job that patches
  `odh-dashboard-config`.
- A dashboard menu or feature is missing, or flips back after a sync.
- A new stage needs its own dashboard flag.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| One `OdhDashboardConfig` (`opendatahub.io/v1alpha`) `odh-dashboard-config` in `redhat-ods-applications`, owned by `010-rhoai-platform`, sync-wave 4 | `gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/odhdashboardconfig.yaml` | [Edit the dashboard configuration][edit] |
| Stage 010 non-default values: `connectionTest: true` (Technology Preview), `disableKueue: false` (Developer Preview), `disableModelCatalog`/`disableModelRegistry: true`, `modelAsService: false`; defaults written down for `observabilityDashboard`, `disableTracking` and several feature flags | same file; README "OdhDashboardConfig" table | [Dashboard configuration options][options] |
| Later stages own their flags: the Application lists each one as a JSON pointer in `ignoreDifferences` with `RespectIgnoreDifferences=true`, and the owning stage's Sync-hook Job patches it | `gitops/applications/010-rhoai-platform.yaml` | — (repo GitOps rule) |
| Owners: Stage 030 (`agentsCatalog`, `disableModelCatalog`, `disableModelRegistry`, `toolCalling`, `mcpCatalog`, `mcpRegistry`); Stage 040 (`genAiStudio`, `modelAsService`, `vLLMDeploymentOnMaaS` and the other Gen AI flags, `/spec/genAiStudioConfig`); Stage 050 (`disableLMEval`, `globalProjectPrompts`, `/spec/globalMLflowNamespaces`); Stage 060 (`agentOps`) | `gitops/stages/030-private-model-serving/private-model-serving/model-discovery/enable-job.yaml`, `gitops/stages/040-governed-models-as-a-service/maas-platform/jobs/enable-maas-job.yaml`, `gitops/stages/050-model-evaluation/mlflow/dsc-enablement/enable-job.yaml`, `gitops/stages/060-agent-runtime-and-agentops/agent-console/enable-job.yaml` | [Dashboard configuration options][options], [Global prompt registry namespaces][prompts] |
| Delegated fields keep a Git value only for first creation; after that the owning stage wins | `gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/README.md` | — |

## Procedure

1. Pick the owner. A Stage 010 flag changes in `odhdashboardconfig.yaml`. A
   flag for a later stage goes in that stage's enable Job (declared in its
   `demo.rhoai.io/writes-delegated` annotation), and its pointer goes into the
   `010-rhoai-platform` `ignoreDifferences` list. Static check:
   `python3 scripts/shared/stage_apps.py check-delegations` (also run by
   `./scripts/platform/validate-stage-flow.sh`).
2. Look up the option name, default and support status in [Dashboard
   configuration options][options]; record any preview status in the owning
   component README ("Alignment with official guidance").
3. Deploy and validate the owning stage, for example
   `./stages/010-openshift-ai-platform-foundation/validate.sh` (checks
   `observabilityDashboard`) or the later stage's `validate.sh`.
4. Read-only check, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications \
     -o jsonpath='{.spec.dashboardConfig}{"\n"}'
   python3 scripts/shared/stage_apps.py delegated 010 OdhDashboardConfig \
     odh-dashboard-config redhat-ods-applications --group opendatahub.io
   ```

## Pitfalls

- A flag patched live without a delegated pointer is reverted by self-heal.
  Removing a pointer makes Argo CD restore the Git value on the next sync.
- `disable*` options hide a feature when `true`; the others enable it. Check
  each name in the options table before setting it.
- A visible menu does not mean the component works; the DSC component must be
  `Managed` too (see `rhoai-dsci-dsc-configuration`).
- `disableHardwareProfiles` and `groupsConfig` are no longer used in 3.5
  ([Dashboard configuration options][options]).

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Chapter | [Customize the dashboard][chapter] |
| Edit the CR | [Edit the dashboard configuration][edit] |
| Options, defaults, preview status | [Dashboard configuration options][options] |
| Global prompt namespaces | [Configure global prompt registry namespaces][prompts] |

## Related skills

`rhoai-dashboard-applications`, `rhoai-dsci-dsc-configuration`,
`rhoai-users-groups-access`, `rhoai-telemetry-admin-settings`,
`rhoai-project-scoped-resources`, `review-gitops-change`.

[chapter]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#customizing-the-dashboard
[edit]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#editing-the-dashboard-configuration_dashboard
[prompts]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#configuring-global-prompt-registry-namespaces_dashboard
[options]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#ref-dashboard-configuration-options_dashboard
