---
name: ocp-devspaces-install
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_devspaces
  docs-version: "3.30"
  skill-group: "OpenShift Platform"
description: >
  Use when reviewing or changing how this demo installs or upgrades Red Hat
  OpenShift Dev Spaces 3.30 through Argo CD: the devspaces Subscription in
  openshift-devspaces (Manual approval, startingCSV devspacesoperator.v3.30.2),
  the InstallPlan approver that also admits devworkspace-operator.v0.43.0, the
  webhook-wait hook before the CheCluster, install verification, and
  z-stream upgrades. Do NOT use for CheCluster field choices (use
  ocp-devspaces-admin), devfiles and workspace usage (use
  ocp-devspaces-user-guide), release content (use
  ocp-devspaces-release-notes), or day-2 workspace operations (use
  manage-devspaces).
---

# Dev Spaces install

Thin skill: repo decisions and pitfalls here, product procedure in the linked
Dev Spaces 3.30 topics. Detailed record:
`gitops/stages/070-advanced-app-platform/devspaces/README.md`.

## When to use

- A change touches `devspaces/subscription.yaml`, `operatorgroup.yaml`,
  `approve-installplan.yaml` or `wait-for-operator-webhook.yaml`.
- `070-devspaces` stalls before the CheCluster, or a Dev Spaces z-stream is
  reviewed.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| GitOps install: Subscription, `CheCluster` (`org.eclipse.che/v2`) and Kustomization in Git, reconciled by Argo CD Application `070-devspaces` | `gitops/stages/070-advanced-app-platform/devspaces/kustomization.yaml` | [Deploy using GitOps and Argo CD][gitops] |
| Subscription `devspaces` in `openshift-devspaces` with an empty-spec (AllNamespaces) OperatorGroup; the guide places it in `openshift-operators` (recorded Gap) | `devspaces/subscription.yaml`, `devspaces/operatorgroup.yaml` | [Deploy using GitOps and Argo CD][gitops] |
| Channel `stable`, `installPlanApproval: Manual`, `startingCSV: devspacesoperator.v3.30.2` | `devspaces/subscription.yaml` | [Update approval strategy][approval] |
| Approver hook allowlist `devworkspace-operator.v0.43.0`, `devspacesoperator.v3.30.2`; Role limited to this namespace's InstallPlans and Subscription `devspaces` | `devspaces/approve-installplan.yaml` | [How the upgrade works][upgrade] |
| Webhook-wait hook (wave 9) holds the CheCluster (wave 10) until operator endpoints answer admission | `devspaces/wait-for-operator-webhook.yaml` | [How the installation works][overview] |
| Namespaces from `070-namespaces`; Argo CD ignores Subscription `startingCSV` and OperatorGroup `olm.providedAPIs` | `gitops/stages/070-advanced-app-platform/namespaces/`, `gitops/argocd/app-of-apps/070-advanced-app-platform/devspaces.yaml` | — |

## Procedure

1. A z-stream update changes `startingCSV`, the approver allowlist and the
   validator expectation in one commit; check the matching DWO version in
   the release notes (`ocp-devspaces-release-notes`).
2. Deploy and validate after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   ./stages/070-advanced-app-platform/deploy.sh
   ./stages/070-advanced-app-platform/validate.sh
   ```

3. Read-only checks:

   ```bash
   oc get subscription devspaces -n openshift-devspaces -o jsonpath='{.status.installedCSV}{"\n"}'
   oc get csv -n openshift-devspaces
   oc get checluster devspaces -n openshift-devspaces -o jsonpath='{.status.chePhase} {.status.cheVersion}{"\n"}'
   ```

## Pitfalls

- OLM creates a second Subscription for DWO (`devworkspace-operator-fast-…`,
  channel `fast`) in `openshift-devspaces`; it rides the same InstallPlan, so
  an unlisted DWO CSV stops the approver.
- A duplicate DWO after a cluster upgrade has a product repair procedure:
  [Fix a duplicate DWO][dwo].
- Applying the CheCluster before the webhook answers fails admission; keep
  the wait hook wave below the CheCluster wave.
- Workspace start failures after install:
  `docs/TROUBLESHOOTING.md#red-hat-openshift-dev-spaces-workspace-does-not-start`.

## Official documentation (Dev Spaces 3.30)

| Topic | Section |
|---|---|
| Plan | [Supported platforms][platforms], [Size your cluster][sizing] |
| Install | [How installation works][overview], [GitOps and Argo CD][gitops], [CLI][cli], [Verify][verify], [Dashboard URL][fqdn] |
| Not used | [GitOps air-gapped][airgap], [External IdP][oidc], [Uninstall][uninstall] |
| Upgrade | [How upgrades work][upgrade], [Approval strategy][approval], [Pre-upgrade checklist][checklist], [Verify upgrade][verifyup], [Duplicate DWO][dwo] |

## Related skills

`ocp-devspaces-admin`, `ocp-devspaces-release-notes`, `ocp-devspaces-about`,
`manage-devspaces`, `ocp-gitops-operator`.

[gitops]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/install-proc_deploying_devspaces_using_gitops
[overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/install-con_installation_overview
[cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/install-proc_installing_dev_spaces_using_cli
[verify]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/install-proc_verifying_the_installation
[fqdn]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/install-proc_finding_the_fqdn
[airgap]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/install-proc_deploying_devspaces_using_gitops_in_a_restricted_environment
[oidc]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/install-proc_installing_dev_spaces_on_openshift_with_keycloak_as_oidc
[uninstall]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/install-proc_uninstalling_dev_spaces
[platforms]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/plan-supported_platforms_ref
[sizing]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/plan-proc_calculating_resource_requirements
[upgrade]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/upgrade-con_upgrade_overview
[approval]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/upgrade-proc_specifying_update_approval_strategy
[checklist]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/upgrade-ref_pre_upgrade_checklist
[verifyup]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/upgrade-proc_verify_upgrade_completed
[dwo]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/upgrade-proc_repairing_devworkspace_operator
