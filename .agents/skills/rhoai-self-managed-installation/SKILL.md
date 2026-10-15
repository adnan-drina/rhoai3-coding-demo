---
name: rhoai-self-managed-installation
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when reviewing or changing how Stage 010 installs Red Hat OpenShift AI
  Self-Managed: the 010-rhoai-operator Application (Namespace
  redhat-ods-operator, OperatorGroup rhods-operator-group, Subscription
  rhods-operator), the hand-off to 010-rhoai-platform, deploy ordering in
  stages/010-openshift-ai-platform-foundation/deploy.sh, platform
  prerequisites (OpenShift version, cluster-admin, no Open Data Hub), and
  post-install verification. Do NOT use for channel choice (use
  rhoai-update-channels), DSCI/DSC fields (use rhoai-dsci-dsc-configuration),
  or uninstall (use rhoai-uninstallation).
---

# RHOAI Self-Managed installation

Thin skill: repo decisions and pitfalls here, product procedure in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-operator/README.md`.

## When to use

- A change touches `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-operator/`
  or `gitops/applications/010-rhoai-operator.yaml`.
- Stage 010 deploy stops before the `rhods-operator` CSV succeeds.
- A fresh cluster is being prepared for Stage 010.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| CLI install method in GitOps: Namespace `redhat-ods-operator`, OperatorGroup with no `targetNamespaces`, Subscription `rhods-operator` from `redhat-operators` | `010-rhoai-operator/namespace.yaml`, `operator-group.yaml`, `subscription.yaml` | [Install the Operator by using the CLI][op-cli] |
| Operator lifecycle in its own Application (`010-rhoai-operator`); DSCI, DSC, `Auth` and dashboard config in `010-rhoai-platform`, so a channel change never re-syncs the DSC | `gitops/applications/010-rhoai-operator.yaml`, `gitops/applications/010-rhoai-platform.yaml` | [Install and manage components][comp] |
| `DISABLE_DSC_CONFIG=true` in the Subscription `config.env`, so GitOps creates `default-dsci` (upstream Open Data Hub setting, not in the 3.5 guide) | `010-rhoai-operator/subscription.yaml` | not documented in the 3.5 install guide (recorded as a deviation in the README) |
| Predefined namespaces (`redhat-ods-operator`, `redhat-ods-applications`, `rhods-notebooks`); no custom namespaces | `010-rhoai-platform/dsc-init.yaml`, `datasciencecluster.yaml` | [Configure custom namespaces][custom-ns] |
| Catalog and install gated by the operator policy: channel `stable-3.5`, minimum `3.5.1` | `scripts/platform/check-operator-policy.py` (called by `deploy.sh` and `validate.sh`) | [Update channels][channels] |
| Platform runs OCP 4.22; the install guide lists a narrower range, the supported-configurations matrix includes 4.22 | `docs/PLATFORM_BASELINE.md` | [Platform requirements][platform-req] |

## Procedure

1. Change the operator objects in Git only. Keep the channel and minimum in
   `check-operator-policy.py` in step with the doc map
   (`python3 scripts/shared/check-doc-links.py --family rhoai`).
2. Deploy and validate through the stage scripts:
   `./stages/010-openshift-ai-platform-foundation/deploy.sh`, then
   `./stages/010-openshift-ai-platform-foundation/setup-access.sh` and
   `./stages/010-openshift-ai-platform-foundation/validate.sh`.
   `deploy.sh` runs the policy check before applying and waits up to 1800 s
   for the CSV afterwards.
3. By hand, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get subscription rhods-operator -n redhat-ods-operator \
     -o jsonpath='{.spec.channel} {.status.installedCSV}{"\n"}'
   oc get csv -n redhat-ods-operator -l operators.coreos.com/rhods-operator.redhat-ods-operator
   oc get dsc default-dsc -o jsonpath='{.status.installedComponents}{"\n"}'
   ```

## Pitfalls

- `deploy.sh` applies all deploy-order Applications in one batch; ordering
  against `010-rhoai-platform` comes from Argo CD retry and
  `SkipDryRunOnMissingResource`, not from a script wait.
- Removing `DISABLE_DSC_CONFIG` lets the operator create its own DSCI that
  GitOps must then adopt. Keep it while `010-rhoai-platform` owns the DSCI.
- The guide requires cluster-admin, forbids `kubeadmin`, and forbids Open Data
  Hub on the same cluster ([Platform requirements][platform-req]).
- CSV stuck or vanished: `docs/TROUBLESHOOTING.md#operator-csv-not-succeeded`,
  `docs/TROUBLESHOOTING.md#operator-subscription-claims-a-csv-that-no-longer-exists`.

## Official documentation (RHOAI 3.5)

| Topic | Section |
|---|---|
| Architecture | [Architecture of OpenShift AI Self-Managed][arch] |
| Requirements | [Requirements][req], [Platform requirements][platform-req], [Component requirements][comp-req] |
| Custom namespaces (not used) | [Configure custom namespaces][custom-ns] |
| Operator install | [Install the Operator][op], [by using the CLI][op-cli], [by using the web console][op-web] |
| Components and status | [Install and manage components][comp], [View installed components][view] |
| Dashboard access | [Access the dashboard][dash] |
| Install troubleshooting | [Troubleshooting reference: Installation][troubleshoot] |

## Related skills

`rhoai-update-channels`, `rhoai-dsci-dsc-configuration`, `rhoai-users-groups-access`,
`rhoai-observability`, `rhoai-installation-troubleshooting`, `rhoai-uninstallation`,
`ocp-gitops-operator`.

[arch]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#architecture-of-openshift-ai-self-managed_install
[channels]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#understanding-update-channels_install
[req]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#requirements-for-openshift-ai-self-managed_install
[platform-req]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#platform_requirements
[comp-req]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#component_requirements
[custom-ns]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#configuring-custom-namespaces
[op]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#installing-the-openshift-ai-operator_operator-install
[op-cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#installing-openshift-ai-operator-using-cli_operator-install
[op-web]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#installing-openshift-ai-operator-using-web-console_operator-install
[comp]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#installing-and-managing-openshift-ai-components_component-install
[view]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#viewing-installed-components_component-install
[dash]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#accessing-the-dashboard_install
[troubleshoot]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/installing_and_uninstalling_openshift_ai_self-managed/index#troubleshooting-common-installation-problems_install
