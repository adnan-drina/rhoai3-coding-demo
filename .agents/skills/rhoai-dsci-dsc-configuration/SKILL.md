---
name: rhoai-dsci-dsc-configuration
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when reviewing or changing the OpenShift AI singletons owned by
  010-rhoai-platform: DSCInitialization default-dsci and DataScienceCluster
  default-dsc in gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/,
  component managementState values, the delegation model where Stages
  020-060 enable components through Sync hook Jobs and ignoreDifferences
  pointers (scripts/shared/stage_apps.py delegated), or a DSC/DSCI not Ready.
  Do NOT use for the operator Subscription (use rhoai-update-channels or
  rhoai-self-managed-installation), DSCI monitoring fields (use
  rhoai-observability), or the trusted CA bundle (use
  rhoai-certificate-management).
---

# RHOAI DSCInitialization and DataScienceCluster

Thin skill: repo decisions and pitfalls here, product fields in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/README.md`.

## When to use

- A change touches `rhoai-platform/dsc-init.yaml` or `rhoai-platform/datasciencecluster.yaml`.
- A stage needs a new DSC component, or a delegated component flips back.
- `default-dsc` or `default-dsci` is not Ready.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| `default-dsci` created by GitOps (operator auto-creation disabled by `DISABLE_DSC_CONFIG`); `applicationsNamespace: redhat-ods-applications`; `trustedCABundle` Managed, empty custom bundle | `rhoai-platform/dsc-init.yaml`, `rhoai-operator/subscription.yaml` | [Install and manage components by using the CLI][comp-cli] |
| DSC on `datasciencecluster.opendatahub.io/v2`; Stage 010 manages only `dashboard` and `workbenches` (`workbenchNamespace: rhods-notebooks`); every other component `Removed` in Git | `rhoai-platform/datasciencecluster.yaml` | [Install and manage components by using the CLI][comp-cli] |
| One owner for the singletons: Application `010-rhoai-platform`; later stages patch the live DSC from a `Sync` hook Job; `ignoreDifferences` plus `RespectIgnoreDifferences=true` keep the patch | `gitops/applications/010-rhoai-platform.yaml` | n/a (Argo CD behaviour, see README) |
| Delegated owners: `kueue` (020, `Unmanaged`), `kserve` and `modelregistry` (030), `aigateway` and `ogx` (040), `trustyai`, `mlflowoperator`, `aipipelines` (050), `mcplifecycleoperator` (060) | component README "Delegation model" table; `scripts/shared/stage_apps.py` | [Install and manage components by using the CLI][comp-cli]; Kueue: [Install the distributed workloads components][dw] |
| `llamastackoperator` kept `Removed` (live 3.5 CRD marks it deprecated in favour of `ogx`; the 3.5 CLI example lists `ogx` and omits it) | `rhoai-platform/datasciencecluster.yaml` | [Install and manage components by using the CLI][comp-cli] |
| No custom namespaces | `rhoai-platform/dsc-init.yaml` | [Configure custom namespaces][custom-ns] |

## Procedure

1. Decide the owner: platform-wide settings go in `dsc-init.yaml`; a new
   component goes in the owning stage's hook Job, plus its JSON pointer in the
   `010-rhoai-platform` Application `ignoreDifferences`. Never edit the live
   DSC by hand.
2. Check fields against the installed schema before committing:
   `oc explain datasciencecluster.spec.components` and
   `oc explain dscinitialization.spec`.
3. Deploy and validate:
   `./stages/010-openshift-ai-platform-foundation/deploy.sh`, then
   `./stages/010-openshift-ai-platform-foundation/validate.sh` (DSCI, DSC and
   `Auth` Ready; foundation component ownership via `stage_apps.delegated`).
4. By hand, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get dsci default-dsci -o jsonpath='{.status.phase}{"\n"}'
   oc get dsc default-dsc -o jsonpath='{.status.phase}{"\n"}{.status.installedComponents}{"\n"}'
   python3 scripts/shared/stage_apps.py delegated 010 DataScienceCluster default-dsc --group datasciencecluster.opendatahub.io
   ```

## Pitfalls

- Removing a pointer from `ignoreDifferences` restores the Git value
  (`Removed`) on the next sync and uninstalls that component. Turn the
  component off through its stage first.
- Without `RespectIgnoreDifferences=true`, a sync re-applies the Git value and
  `stage_apps.py delegated` returns nothing; Stage 020 and 030 `deploy.sh`
  then refuse to deploy.
- Kueue is `Unmanaged`, not `Managed`: the Red Hat build of Kueue Operator owns
  Kueue ([Install the distributed workloads components][dw]).
- Git values for delegated fields apply only at first creation.

## Official documentation (RHOAI 3.5)

| Topic | Section |
|---|---|
| Components, `managementState`, CLI and web console | [Install and manage components][comp], [by using the CLI][comp-cli], [by using the web console][comp-web] |
| Status update and installed components | [Update the installation status][comp-status], [View installed components][view] |
| Namespaces | [Configure custom namespaces][custom-ns] |
| Kueue and distributed workloads components | [Install the distributed workloads components][dw] |

## Related skills

`rhoai-self-managed-installation`, `rhoai-observability`, `rhoai-certificate-management`,
`rhoai-distributed-workloads`, `rhoai-api-tiers`, `rhoai-dashboard-customization`,
`ocp-gitops-operator`.

[comp]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#installing-and-managing-openshift-ai-components_component-install
[comp-cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#installing-openshift-ai-components-using-cli_component-install
[comp-web]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#installing-openshift-ai-components-using-web-console_component-install
[comp-status]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#updating-installation-status-of-openshift-ai-components-using-web-console_component-install
[view]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#viewing-installed-components_component-install
[custom-ns]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#configuring-custom-namespaces
[dw]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#installing-the-distributed-workloads-components_install
