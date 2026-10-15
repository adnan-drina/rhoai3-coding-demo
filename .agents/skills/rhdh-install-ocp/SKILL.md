---
name: rhdh-install-ocp
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when reviewing or changing how this demo installs Red Hat Developer Hub
  1.10 on OpenShift: the rhdh-operator OperatorGroup and Subscription
  (fast-1.10, Manual approval, startingCSV), the reviewed-CSV approve-installplan
  hook, the Backstage CR developer-hub in namespace rhdh, sync-wave order of the
  070-rhdh Application, and install verification. Do NOT use for z-stream
  upgrades (use rhdh-upgrade), app-config or Backstage CR fields beyond install
  (use rhdh-configure), plugins (use rhdh-dynamic-plugins-configure), or other
  platforms (rhdh-install-aks, rhdh-install-eks, rhdh-install-gke,
  rhdh-install-osd-gcp, rhdh-install-airgapped).
---

# Developer Hub install on OpenShift

Thin skill: repo decisions and pitfalls here, product procedure in the linked
Developer Hub 1.10 sections. Detailed record:
`gitops/stages/070-advanced-app-platform/070-rhdh/README.md`.

## When to use

- A change touches `gitops/stages/070-advanced-app-platform/070-rhdh/rhdh-operator/`
  or `070-rhdh/rhdh-instance/backstage.yaml`.
- Stage 070 stops before the portal answers (operator CSV, Backstage CR, Route).

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Operator path, not the Helm chart (Helm is not used) | `070-rhdh/rhdh-operator/`, `070-rhdh/rhdh-instance/backstage.yaml` | [Installation methods][methods] |
| Namespace `rhdh-operator`, OperatorGroup without target namespaces (all-namespaces mode; a specific namespace is not supported) | `070-rhdh/rhdh-operator/operatorgroup.yaml` | [Install the Operator][install-op] |
| Subscription `rhdh`: channel `fast-1.10` (z-streams only), `installPlanApproval: Manual`, `startingCSV: rhdh-operator.v1.10.5`, `redhat-operators` | `070-rhdh/rhdh-operator/subscription.yaml` | [Install the Operator][install-op] |
| Sync hook `approve-installplan` approves only InstallPlans whose CSVs are all on its allowlist, then waits for the CSV; its Role reaches only `rhdh-operator` InstallPlans and Subscription `rhdh` | `070-rhdh/rhdh-operator/approve-installplan.yaml` | — (repo control) |
| Instance is the `Backstage` CR `developer-hub` in `rhdh` (wave 18), configured only through ConfigMaps, Secrets and the CR | `070-rhdh/rhdh-instance/` | [Provision custom configuration][provision], [Run with custom configuration][run-op] |
| Namespaces `rhdh-operator` and `rhdh` come from `070-namespaces`; `070-rhdh` is deploy-order 8 (last) of Stage 070 | `gitops/stages/070-advanced-app-platform/070-namespaces/`, `gitops/applications/070-rhdh.yaml` | — |

Paths are relative to `gitops/stages/070-advanced-app-platform/` unless absolute.

## Procedure

1. Change the Subscription, allowlist and validator together: a new CSV is a
   reviewed change in `subscription.yaml`, `approve-installplan.yaml` and
   `stages/070-advanced-app-platform/validate.sh` (it expects exactly
   `rhdh-operator.v1.10.5`). Keep the map pin consistent
   (`python3 scripts/shared/check-doc-links.py --family rhdh`).
2. Deploy and validate through the stage scripts after the OpenShift safety
   guard in `AGENTS.md`:

   ```bash
   ./stages/070-advanced-app-platform/deploy.sh
   ./stages/070-advanced-app-platform/validate.sh
   ./stages/070-advanced-app-platform/validate.sh --static
   ```

3. Read-only checks:

   ```bash
   oc get subscription rhdh -n rhdh-operator -o jsonpath='{.status.installedCSV}{"\n"}'
   oc get csv -n rhdh-operator
   oc get backstage developer-hub -n rhdh; oc get pods,route -n rhdh
   ```

## Pitfalls

- With Manual approval nothing installs until the hook approves; a CSV not on
  the allowlist leaves the InstallPlan pending by design. Never approve a
  foreign InstallPlan by hand.
- Argo CD ignores Subscription `startingCSV` and OperatorGroup
  `olm.providedAPIs` (`ignoreDifferences` in the Application); drift there is
  not a reason to resync.
- Operator-owned objects (Deployment `backstage-developer-hub`, StatefulSet
  `backstage-psql-developer-hub`, Route, default app-config) are not in Git;
  do not add them.
- OutOfSync while healthy:
  `docs/TROUBLESHOOTING.md#red-hat-developer-hub-is-healthy-but-stage-070-is-outofsync`.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Installation methods | [Installation methods][methods] |
| Operator install | [Install with the Operator][op], [Install the Operator][install-op] |
| Custom configuration | [Provision custom configuration][provision], [Run with custom configuration][run-op] |
| Helm chart (not used) | [Install with the Helm chart][helm] |
| Operator vs Helm, sizing | [Compare deployment methods][compare], [Sizing][sizing] |

## Related skills

`rhdh-upgrade`, `rhdh-configure`, `rhdh-release-notes`, `rhdh-about`,
`rhdh-dynamic-plugins-configure`.

[methods]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_on_openshift_container_platform/index#rhdh-installation-methods-on-ocp_installing-rhdh-on-ocp
[op]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_on_openshift_container_platform/index#install-rhdh-on-ocp-with-the-operator_installing-rhdh-on-ocp
[install-op]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_on_openshift_container_platform/index#install-the-rhdh-operator_install-rhdh-on-ocp-with-the-operator
[provision]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_on_openshift_container_platform/index#provision-your-custom-rhdh-configuration_install-rhdh-on-ocp-with-the-operator
[run-op]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_on_openshift_container_platform/index#use-the-rhdh-operator-to-run-rhdh-with-your-custom-configuration_install-rhdh-on-ocp-with-the-operator
[helm]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_on_openshift_container_platform/index#install-rhdh-on-ocp-with-the-helm-chart_installing-rhdh-on-ocp
[compare]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/about_red_hat_developer_hub/index#compare-the-helm-chart-and-operator-to-choose-the-optimal-deployment-method_about-rhdh
[sizing]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/about_red_hat_developer_hub/index#sizing-requirements-for-rhdh_about-rhdh
