---
name: rhoai-architecture-overview
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when writing or reviewing an architecture narrative or a namespace layout
  that involves OpenShift AI in this repo: the management layer (rhods-operator
  in redhat-ods-operator; the DSCInitialization default-dsci, DataScienceCluster
  default-dsc and Auth CR owned by 010-rhoai-platform), the product namespaces
  (redhat-ods-applications, rhods-notebooks, redhat-ods-monitoring), and where
  demo workloads live instead (demo-sandbox, internal-models, evaluated-models,
  external-models, Stage 070 namespaces). Do NOT use for DSC/DSCI fields (use
  rhoai-dsci-dsc-configuration), operator install or channels (use
  rhoai-self-managed-installation, rhoai-update-channels), or the Stage 130
  solution architecture (read stages/130-ai-autonomous-migration/SOLUTION-ARCHITECTURE.md).
---

# RHOAI Architecture Overview

Thin skill: how this repo maps onto the OpenShift AI architecture, with product
behavior in the linked OpenShift AI 3.5 sections. Detailed records:
`gitops/stages/010-openshift-ai-platform-foundation/rhoai-operator/README.md`
and `gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/README.md`.

## When to use

- `README.md`, a stage README or a slide describes what OpenShift AI provides
  and what the demo adds.
- A new component needs a namespace and you must decide whether it may go into
  an OpenShift AI namespace.
- Someone asks which Argo CD Application owns an OpenShift AI singleton.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Management layer: one OLM Subscription `rhods-operator` in `redhat-ods-operator` (Application `010-rhoai-operator`), separate from platform configuration | `gitops/stages/010-openshift-ai-platform-foundation/rhoai-operator/` | [Architecture][arch]; [Install the Operator by CLI][op-cli] |
| Predefined projects, no custom namespaces: `applicationsNamespace: redhat-ods-applications`, `workbenchNamespace: rhods-notebooks` | `rhoai-platform/dsc-init.yaml`, `rhoai-platform/datasciencecluster.yaml` | [Architecture][arch]; [Configure custom namespaces][custom-ns] |
| Service layer switched per component on the shared `default-dsc`; Stage 010 keeps only Dashboard and Workbenches Managed, later stages enable theirs through delegated fields | `rhoai-platform/datasciencecluster.yaml`; delegation table in `rhoai-platform/README.md` | [Install components by CLI][comp-cli] |
| DSCI, DSC, `Auth` and `odh-dashboard-config` are cluster singletons with one owner (`010-rhoai-platform`) | `gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/` | [Install and manage components][comp] |
| Native observability stack in `redhat-ods-monitoring`; the namespace is created in Git before the DSCI | `rhoai-platform/monitoring-namespace.yaml`, `rhoai-platform/dsc-init.yaml` | [Enable the observability stack][obs] |
| Demo workloads stay out of OpenShift AI namespaces: dashboard projects `demo-sandbox`, `internal-models`, `evaluated-models` (label `opendatahub.io/dashboard: "true"`), plus `external-models`, `evalhub`, `rhoai-model-registries` | `gitops/stages/010-openshift-ai-platform-foundation/access/namespace-demo-sandbox.yaml`, `gitops/stages/040-governed-models-as-a-service/local-models/namespace.yaml`, `gitops/stages/050-model-evaluation/model-qualification/namespace.yaml` | [Architecture][arch] (no ISV applications in OpenShift AI namespaces) |
| Developer tools (Dev Spaces, Developer Hub, GitLab, MTA, SonarQube) get their own namespaces in Stage 070 | `gitops/stages/070-advanced-app-platform/namespaces/namespaces.yaml` | [Architecture][arch] |
| Generated per-component CRs (`*.components.platform.opendatahub.io`) stay out of Git; enablement Jobs only read them for readiness | `gitops/stages/050-model-evaluation/mlflow/dsc-enablement/enable-job.yaml` | [View installed components][view] |

Workshop architecture lives in `README.md` and the stage list in `AGENTS.md`
(Demo stages). Stage 130 keeps its own solution architecture in
`stages/130-ai-autonomous-migration/SOLUTION-ARCHITECTURE.md`.

## Procedure

1. Map every capability a narrative claims to a DSC component or to a demo
   component under `gitops/stages/<stage>/`. Label demo glue (Jobs,
   provisioners, MCP servers, databases) as demo-owned.
2. Put a new workload in a stage-owned namespace; add
   `opendatahub.io/dashboard: "true"` only when it must appear as a project in
   the OpenShift AI dashboard.
3. Validate structure statically: `./scripts/platform/validate-stage-flow.sh`.
4. Live check, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get dsci default-dsci -o jsonpath='{.spec.applicationsNamespace}{"\n"}'
   oc get ns -l opendatahub.io/dashboard=true
   ./stages/010-openshift-ai-platform-foundation/validate.sh
   ```

## Pitfalls

- The operator does not create the default DSCI here (`DISABLE_DSC_CONFIG=true`
  in `rhoai-operator/subscription.yaml`); a missing DSCI points to
  `010-rhoai-platform`, not to the operator.
- `rhods-admins` is created by the operator from the `Auth` CR; its membership
  comes from `stages/010-openshift-ai-platform-foundation/setup-access.sh`, not Git.
- `llamastackoperator` stays `Removed`; the 3.5 generative AI service layer here
  is `ogx` (enabled by Stage 040). Do not describe Llama Stack as deployed.
- Do not count catalog entries or dashboard tiles as deployed components
  (`docs/OPERATIONS.md`, Ownership and stage boundaries).

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Service and management layers, default projects | [Architecture of OpenShift AI Self-Managed][arch] |
| Requirements | [Requirements for OpenShift AI Self-Managed][req] |
| Custom namespaces (not used) | [Configure custom namespaces][custom-ns] |
| Operator and components | [Install the Operator by CLI][op-cli], [Install and manage components][comp], [View installed components][view] |
| Observability stack | [Enable the observability stack][obs] |

## Related skills

`rhoai-self-managed-installation`, `rhoai-dsci-dsc-configuration`,
`rhoai-platform-planning`, `rhoai-users-groups-access`, `rhoai-observability`,
`project-demo-stage-authoring`.

[arch]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#architecture-of-openshift-ai-self-managed_install
[req]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#requirements-for-openshift-ai-self-managed_install
[custom-ns]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#configuring-custom-namespaces
[op-cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#installing-openshift-ai-operator-using-cli_operator-install
[comp]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#installing-and-managing-openshift-ai-components_component-install
[comp-cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#installing-openshift-ai-components-using-cli_component-install
[view]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#viewing-installed-components_component-install
[obs]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#enabling-the-observability-stack_managing-rhoai
