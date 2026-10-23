---
name: rhdh-upgrade
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when moving this demo's Red Hat Developer Hub to another 1.10 z-stream
  or a later minor: changing the rhdh Subscription channel and startingCSV,
  the approve-installplan allowlist and the Stage 070 validator, checking the
  release notes, and verifying the portal after the Operator upgrade. Do NOT
  use for the first installation (use rhdh-install-ocp), configuration changes
  (use rhdh-configure), or Helm chart upgrades (not used in this repo).
---

# Developer Hub upgrade

Thin skill: repo decisions and pitfalls here, product procedure in the linked
Developer Hub 1.10 sections. Detailed record:
`gitops/stages/070-advanced-app-platform/070-rhdh/README.md` (How: Installation).

## When to use

- A new RHDH z-stream (1.10.x) or minor is to be adopted.
- The installed CSV differs from `rhdh-operator.v1.10.6` or an InstallPlan
  stays pending in `rhdh-operator`.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Upgrades are reviewed Git changes, never console approvals: Subscription `installPlanApproval: Manual` with an exact `startingCSV` | `gitops/stages/070-advanced-app-platform/070-rhdh/rhdh-operator/subscription.yaml` | [Upgrade the Operator][op] |
| Channel `fast-1.10` delivers z-streams only; a minor upgrade changes the channel (`fast` would follow every version) | same file | [Install the Operator][channel] |
| The `approve-installplan` hook approves a plan only if every CSV is on its allowlist and waits for that CSV | `gitops/stages/070-advanced-app-platform/070-rhdh/rhdh-operator/approve-installplan.yaml` | — (repo control) |
| The validator expects exactly the allow-listed CSV | `stages/070-advanced-app-platform/validate.sh` | — |
| Helm chart upgrade paths (including 1.8 to 1.10 values migration) do not apply | — | [Helm upgrade][helm], [1.8 to 1.10 with Helm][helm18] |

## Procedure

1. Read the release notes of the target version (fixed issues per z-stream,
   deprecated and removed features); check that every OCI plugin digest in
   `070-rhdh/rhdh-instance/dynamic-plugins-configmap.yaml` has a build for it.
2. In one change: `startingCSV` (and the channel for a minor), the allowlist
   in `approve-installplan.yaml`, the expected CSV in
   `stages/070-advanced-app-platform/validate.sh`, the version text in the
   component README and `stages/070-advanced-app-platform/README.md`, and the
   map pin (`python3 .agents/tools/check-doc-links.py --family rhdh`).
3. After the OpenShift safety guard in `AGENTS.md`, sync and validate:

   ```bash
   ./stages/070-advanced-app-platform/deploy.sh
   ./stages/070-advanced-app-platform/validate.sh
   oc get installplan -n rhdh-operator
   oc get subscription rhdh -n rhdh-operator -o jsonpath='{.status.installedCSV}{"\n"}'
   ```

## Pitfalls

- Argo CD ignores `startingCSV` after installation, so editing it alone does
  not move an installed operator; the allowlisted InstallPlan does.
- A fresh database migration after an upgrade can race two backend pods; the
  Backstage CR keeps `maxSurge: 0` for that reason (see `rhdh-configure`).
- OCI plugin packages are pinned by digest; an RHDH upgrade does not update
  them (see `rhdh-dynamic-plugins-install`).
- Stale catalog after a re-stamp:
  `docs/TROUBLESHOOTING.md#rhdh-template-entity-returns-200-then-404-after-a-catalog-re-stamp`.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Operator upgrade | [Upgrade the Operator][op] |
| Channels | [Install the Operator][channel] |
| Helm (not used) | [Helm upgrade][helm], [1.8 to 1.10 with Helm][helm18] |
| What changed | [Fixed issues][fixed], [Deprecated][deprecated], [Removed][removed] |

## Related skills

`rhdh-install-ocp`, `rhdh-release-notes`, `rhdh-dynamic-plugins-install`,
`rhdh-configure`.

[op]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/upgrading_red_hat_developer_hub/index#upgrade-the-rhdh-operator_upgrade-rhdh
[helm]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/upgrading_red_hat_developer_hub/index#upgrade-the-rhdh-helm-chart_upgrade-rhdh
[helm18]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/upgrading_red_hat_developer_hub/index#upgrade-rhdh-from-1-8-to-using-the-helm-chart_upgrade-rhdh
[channel]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_red_hat_developer_hub_on_openshift_container_platform/index#install-the-rhdh-operator_install-rhdh-on-ocp-with-the-operator
[fixed]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/red_hat_developer_hub_release_notes/index#fixed-issues
[deprecated]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/red_hat_developer_hub_release_notes/index#deprecated-features
[removed]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/red_hat_developer_hub_release_notes/index#removed-features
