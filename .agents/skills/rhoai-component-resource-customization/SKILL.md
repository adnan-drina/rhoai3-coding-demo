---
name: rhoai-component-resource-customization
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when someone wants to change CPU or memory requests or limits of an
  OpenShift AI component Deployment in redhat-ods-applications (for example
  rhods-dashboard, kserve-controller-manager, odh-model-controller), or meets
  the opendatahub.io/managed annotation on such a Deployment. Do NOT use for
  model-server or workbench sizing (use rhoai-hardware-profiles), Kueue quotas
  (use rhoai-kueue-workload-management), or the opendatahub.io/managed label
  on Secrets and the MaaS Gateway (see .agents/rules/env.md and
  rhoai-maas-governance).
---

# RHOAI component resource customization

Thin skill. Not deployed in this demo: no component Deployment in
`redhat-ods-applications` is patched; all run with the operator's default
resources. Product behavior is in the linked OpenShift AI 3.5 sections.

## When to use

- A component pod is OOMKilled or throttled and a resource bump is proposed.
- A Deployment shows `opendatahub.io/managed: true` and its edits are reverted.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Operator-owned Deployments are not in Git and are not patched; the DSC only sets `managementState` per component | `gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/datasciencecluster.yaml` | [Customize component deployment resources][overview] |
| `opendatahub.io/managed: "false"` appears only on the MaaS Gateway objects, for a different MaaS requirement; it is not a component-resource setting | `gitops/stages/040-governed-models-as-a-service/gateway-governance/gateway/gateway.yaml` | see `rhoai-maas-governance` |

## If a customization is needed

1. Confirm the Deployment and container names live (read-only, after the
   OpenShift safety guard in `AGENTS.md`):

   ```bash
   oc get deploy -n redhat-ods-applications
   oc get deploy <name> -n redhat-ods-applications \
     -o jsonpath='{.metadata.annotations}{"\n"}{.spec.template.spec.containers[*].resources}{"\n"}'
   ```

2. Change only `resources` of the named container, following
   [Customize component resources][customize]. Do not make an Argo CD
   Application own the whole Deployment; record the change and the reason in
   `docs/OPERATIONS.md` (or in a narrow GitOps patch with its own README entry).
3. Re-check after the next operator reconcile that the values stayed.

## Pitfalls

- The annotation `opendatahub.io/managed: true` disables customization and
  restores defaults ([Disable component resource customization][disable]).
  Do not add it unless that is the intent.
- Re-enabling customization means deleting the Deployment so the operator
  recreates it ([Re-enable component resource customization][reenable]); that
  restarts the component. Ask first.
- The documented Deployment list may not match every 3.5 component this demo
  enables (AIGateway, OGX, MLflow); check the live names.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Chapter | [Customize component deployment resources][chapter] |
| Overview and Deployment names | [Overview][overview] |
| Procedures | [Customize][customize], [Disable][disable], [Re-enable][reenable] |

## Related skills

`rhoai-dsci-dsc-configuration`, `rhoai-hardware-profiles`,
`rhoai-troubleshoot`, `rhoai-installation-troubleshooting`.

[chapter]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#customizing-component-deployment-resources_resource-mgmt
[overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#overview-of-component-resource-customization_resource-mgmt
[customize]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#customizing-component-resources_resource-mgmt
[disable]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#disabling-component-resource-customization_resource-mgmt
[reenable]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#reenabling-component-resource-customization_resource-mgmt
