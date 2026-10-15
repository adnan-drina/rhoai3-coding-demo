---
name: ocp-pipelines-install-config
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_pipelines
  docs-version: "1.24"
  skill-group: "OpenShift Platform"
description: >
  Use when reviewing or changing how this demo installs and configures Red Hat
  OpenShift Pipelines: the openshift-pipelines-operator-rh Subscription on
  pipelines-1.24, the operator-owned TektonConfig singleton and the Sync-hook
  patches for the pruner, coschedule and createRbacResource, the
  config-triggers-core-interceptors workaround, and upgrade checks. Do NOT use
  for pipeline and trigger authoring (use ocp-pipelines-cicd), build security
  and SCCs (use ocp-pipelines-security), resource tuning (use
  ocp-pipelines-performance), or RHOAI data science pipelines (use
  rhoai-ai-pipelines).
---

# OpenShift Pipelines install and configuration

Thin skill: repo decisions and pitfalls here, product procedure in the linked
OpenShift Pipelines 1.24 sections. Detailed record:
`gitops/stages/070-advanced-app-platform/pipelines/README.md`.

## When to use

- A change touches `gitops/stages/070-advanced-app-platform/pipelines/operators/`
  or `.../pipelines/build/` (TektonConfig hooks, Triggers settings).
- The Pipelines channel moves, or `TektonConfig` is not Ready after an update.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Subscription `openshift-pipelines-operator-rh` in `openshift-operators`, channel `pipelines-1.24`, Automatic; `startingCSV` v1.24.0 is an install floor (1.24.1 runs live) | `pipelines/operators/pipelines-subscription.yaml` | [Install by using the CLI][install-cli] |
| Automatic approval because `openshift-operators` is shared (RHTAS too); Dev Spaces, RHDH and MTA use Manual approval with their own approver hooks | same; `stages/070-advanced-app-platform/validate.sh` (minor check) | [Install by using the CLI][install-cli] |
| `TektonConfig` `config` is operator-owned: Sync-hook Jobs patch single fields, never declare the CR | `pipelines/operators/configure-tekton-pruner.yaml`, `pipelines/build/tektonconfig-affinity.yaml` | [Customizing TektonConfig][tektonconfig] |
| Pruner: PipelineRuns only, keep 10, hourly (product default keep 100, daily at 08:00) | `pipelines/operators/configure-tekton-pruner.yaml` | [Configuring the pruner][pruner] |
| `createRbacResource=false`: no per-namespace `pipeline` SA grants or `pipelines-scc-rolebinding`; one named SA gets one SCC | `pipelines/build/tektonconfig-affinity.yaml`, `pipelines/operators/image-builder-scc.yaml` | [Disabling automatic RBAC creation][rbac], [RBAC and Trusted CA flags][rbac-flags] |
| `spec.pipeline.coschedule: pipelineruns` so one run can bind the source PVC and the `maven-cache` PVC | `pipelines/build/tektonconfig-affinity.yaml` | not in the 1.24 Red Hat guides (verified live on the operator; upstream Tekton field) |
| `config-triggers-core-interceptors` applied from Git (upstream default) after a 1.22.6 update shipped without it | `pipelines/build/tekton-triggers-core-config.yaml` | operator-owned operand; see Pitfalls |

## Procedure

1. Change Subscriptions and hooks in Git only; keep the channel equal to the
   doc map pin (`python3 scripts/shared/check-doc-links.py --family ocp_pipelines`).
2. Deploy and validate through the stage scripts:
   `./stages/070-advanced-app-platform/deploy.sh`, then
   `./stages/070-advanced-app-platform/validate.sh` (checks
   `openshift-pipelines-operator-rh stays on selected minor` and `TektonConfig ready`).
3. Read-only, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get subscription openshift-pipelines-operator-rh -n openshift-operators \
     -o custom-columns=CHANNEL:.spec.channel,CSV:.status.installedCSV
   oc get tektonconfig config -o jsonpath='{.spec.pruner}{"\n"}{.spec.pipeline.coschedule}{"\n"}{.spec.params}{"\n"}'
   oc get deploy -n openshift-pipelines
   ```

4. For a minor upgrade follow `route_update_rules.when_upgrading_product` in
   `.agents/references/red-hat-doc-map.yaml` and read the removed and
   deprecated features in the [release notes][relnotes] before moving the channel.

## Pitfalls

- An operator update can drop an operand ConfigMap: Triggers crash-loops and
  webhooks never start provisioning
  (`docs/TROUBLESHOOTING.md#pipelines-1226-template-publishes-but-provisioning-never-starts`).
  On 1.24.1 the ConfigMap is owned by the operator's `TektonInstallerSet`
  again; the Git copy is a recorded Gap. Remove it only after the checks in
  the manifest comment pass.
- Declaring `TektonConfig` in Git fights the operator; patch fields from a hook.
- With `createRbacResource=false` new namespaces get no `pipeline` SA: each
  project's ServiceAccounts come from `pipelines/project-pipeline/serviceaccounts.yaml`.
- `startingCSV` is ignored after install (`ignoreDifferences`); the validator
  enforces the minor, not the patch.

## Official documentation (OpenShift Pipelines 1.24)

| Topic | Section |
|---|---|
| Install (console, CLI, restricted network) | [Web console][install-console], [CLI][install-cli], [Restricted environment][install-restricted] |
| TektonConfig fields | [Customizing TektonConfig][tektonconfig], [Modifiable fields][fields], [HA mode][ha] |
| RBAC and SCC defaults | [Disabling automatic RBAC creation][rbac], [RBAC and Trusted CA flags][rbac-flags] |
| Pruning | [Automatic pruning][pruning], [Configuring the pruner][pruner], [Event-driven pruner][event-pruner] |
| Triggers and resolvers | [Disabling Triggers][triggers-off], [Configuring resolvers][resolvers] |
| Uninstall | [Uninstalling OpenShift Pipelines][uninstall] |
| Version status | [Release notes][relnotes] |

## Related skills

`ocp-pipelines-cicd`, `ocp-pipelines-security`, `ocp-pipelines-performance`,
`ocp-pipelines-release-notes`, `ocp-gitops-operator`.

[install-console]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index#op-installing-pipelines-operator-in-web-console_installing-pipelines
[install-cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index#op-installing-pipelines-operator-using-the-cli_installing-pipelines
[install-restricted]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index#op-pipelines-operator-in-restricted-environment_installing-pipelines
[tektonconfig]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index#customizing-configurations-in-the-tektonconfig-cr
[fields]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index#op-modifiable-fields-with-default-values_customizing-configurations-in-the-tektonconfig-cr
[ha]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index#op-ha-mode-options_customizing-configurations-in-the-tektonconfig-cr
[rbac]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index#op-disabling-automatic-creation-of-rbac-resources_customizing-configurations-in-the-tektonconfig-cr
[rbac-flags]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index#op-configuration-rbac-trusted-ca-flags.adoc_customizing-configurations-in-the-tektonconfig-cr
[pruning]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index#op-automatic-pruning-taskrun-pipelinerun_customizing-configurations-in-the-tektonconfig-cr
[pruner]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index#default-pruner-configuration_customizing-configurations-in-the-tektonconfig-cr
[event-pruner]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index#event-pruner-configuration_customizing-configurations-in-the-tektonconfig-cr
[triggers-off]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index#op-disabling-pipeline-triggers_customizing-configurations-in-the-tektonconfig-cr
[resolvers]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index#op-configuring-pipeline-resolvers_customizing-configurations-in-the-tektonconfig-cr
[uninstall]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index#uninstalling-pipelines
[relnotes]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/release_notes/index#op-release-notes-1-24
