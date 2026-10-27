---
name: ocp-devspaces-install
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_devspaces
  docs-version: "3.31"
  skill-group: "OpenShift Platform"
description: >
  Use when reviewing or changing how this demo installs or upgrades Red Hat
  OpenShift Dev Spaces 3.31 through Argo CD: the devspaces Subscription in
  openshift-operators (Automatic, stable, policy minimum 3.31.0), the
  webhook-wait hook before the CheCluster, install verification, and
  z-stream upgrades. Do NOT use for CheCluster field choices (use
  ocp-devspaces-admin), devfiles and workspace usage (use
  ocp-devspaces-user-guide), release content (use
  ocp-devspaces-release-notes), or day-2 workspace operations (use
  manage-devspaces).
---

# Dev Spaces install

Thin skill: repo decisions and pitfalls here, product procedure in the linked
Dev Spaces 3.31 topics. Detailed record:
`gitops/stages/070-advanced-app-platform/070-devspaces/README.md`.

## When to use

- A change touches `070-devspaces/subscription.yaml` or
  `wait-for-operator-webhook.yaml`, or the `devspaces` entries in
  `check_operator_policy` in `scripts/lib.sh`.
- `070-devspaces` stalls before the CheCluster, or a Dev Spaces z-stream is
  reviewed.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| GitOps install: Subscription, `CheCluster` (`org.eclipse.che/v2`) and Kustomization in Git, reconciled by Argo CD Application `070-devspaces` | `gitops/stages/070-advanced-app-platform/070-devspaces/kustomization.yaml` | [Deploy using GitOps and Argo CD][gitops] |
| Subscription `devspaces` in `openshift-operators` (AllNamespaces), as the guide shows; OLM adds the DevWorkspace operator there | `070-devspaces/subscription.yaml` | [Deploy using GitOps and Argo CD][gitops] |
| Channel `stable`, `installPlanApproval: Automatic`; the operator policy refuses another channel or a version outside 3.31 (minimum 3.31.0) | `070-devspaces/subscription.yaml`, `check_operator_policy` in `scripts/lib.sh` | [Update approval strategy][approval], [How the upgrade works][upgrade] |
| Webhook-wait hook (wave 9) holds the CheCluster (wave 10) until operator endpoints answer admission | `070-devspaces/wait-for-operator-webhook.yaml` | [How the installation works][overview] |
| Namespaces from `070-namespaces`; no OperatorGroup or Subscription ignore rules | `gitops/stages/070-advanced-app-platform/070-namespaces/`, `gitops/applications/070-devspaces.yaml` | — |

## Procedure

1. Automatic approval takes z-streams on `stable`. A minor update (3.32)
   changes the policy `minimum`/`channels` entries, the map's `docs_version`
   and the validator expectation in one commit; check the matching DWO version
   in the release notes (`ocp-devspaces-release-notes`).
2. Deploy and validate after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   ./stages/070-advanced-app-platform/deploy.sh
   ./stages/070-advanced-app-platform/validate.sh
   ```

3. Read-only checks:

   ```bash
   oc get subscription devspaces -n openshift-operators -o jsonpath='{.status.installedCSV}{"\n"}'
   oc get csv -n openshift-operators | grep -E 'devspaces|devworkspace'
   oc get checluster devspaces -n openshift-devspaces -o jsonpath='{.status.chePhase} {.status.cheVersion}{"\n"}'
   ```

## Pitfalls

- OLM creates a second Subscription for DWO (`devworkspace-operator-fast-…`,
  channel `fast`) in `openshift-operators`; it is not in Git.
- All Subscriptions in `openshift-operators` resolve together; a Manual one
  there would hold the others' updates, so every one is Automatic.
- A duplicate DWO after a cluster upgrade has a product repair procedure:
  [Fix a duplicate DWO][dwo].
- Applying the CheCluster before the webhook answers fails admission; keep
  the wait hook wave below the CheCluster wave.
- Workspace start failures after install:
  `docs/TROUBLESHOOTING.md#red-hat-openshift-dev-spaces-workspace-does-not-start`.

## Official documentation (Dev Spaces 3.31)

| Topic | Section |
|---|---|
| Plan | [Supported platforms][platforms], [Size your cluster][sizing] |
| Install | [How installation works][overview], [GitOps and Argo CD][gitops], [CLI][cli], [Verify][verify], [Dashboard URL][fqdn] |
| Not used | [GitOps air-gapped][airgap], [External IdP][oidc], [Uninstall][uninstall] |
| Upgrade | [How upgrades work][upgrade], [Approval strategy][approval], [Pre-upgrade checklist][checklist], [Verify upgrade][verifyup], [Duplicate DWO][dwo] |

## Related skills

`ocp-devspaces-admin`, `ocp-devspaces-release-notes`, `ocp-devspaces-about`,
`manage-devspaces`, `ocp-gitops-operator`.

[gitops]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/install-proc_deploying_devspaces_using_gitops
[overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/install-con_installation_overview
[cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/install-proc_installing_dev_spaces_using_cli
[verify]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/install-proc_verifying_the_installation
[fqdn]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/install-proc_finding_the_fqdn
[airgap]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/install-proc_deploying_devspaces_using_gitops_in_a_restricted_environment
[oidc]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/install-proc_installing_dev_spaces_on_openshift_with_keycloak_as_oidc
[uninstall]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/install-proc_uninstalling_dev_spaces
[platforms]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/plan-supported_platforms_ref
[sizing]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/plan-proc_calculating_resource_requirements
[upgrade]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/upgrade-con_upgrade_overview
[approval]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/upgrade-proc_specifying_update_approval_strategy
[checklist]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/upgrade-ref_pre_upgrade_checklist
[verifyup]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/upgrade-proc_verify_upgrade_completed
[dwo]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.31/upgrade-proc_repairing_devworkspace_operator
