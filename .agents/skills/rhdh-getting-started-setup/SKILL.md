---
name: rhdh-getting-started-setup
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when reviewing how this demo walks the Developer Hub 1.10 first-instance
  checklist: Operator install, external services, custom configuration
  (app-config, dynamic plugins, Secrets) provisioned through Git and a Sync
  hook, the Backstage CR, RHBK (Keycloak platform realm) authentication with
  guest login disabled, and RBAC from a CSV file instead of the Web UI. Start
  here for an overview of the 070-rhdh component. Do NOT use for detailed
  install (use rhdh-install-ocp), authentication or authorization changes (use
  rhdh-authentication, rhdh-authorization), or day-1 portal navigation (use
  rhdh-getting-started-navigate).
---

# RHDH getting started: setup

Thin skill: how this repo maps onto the product's first-instance checklist.
Detailed record: `gitops/stages/070-advanced-app-platform/070-rhdh/README.md`;
day-2 notes: `docs/OPERATIONS.md#stage-070--developer-hub-rhdh-component`.

## When to use

- First look at the `070-rhdh` component, or a review against the product's
  production checklist.
- Deciding which specialised `rhdh-*` skill owns a change.

## Repo decisions (checklist order)

| Decision (checklist step) | Where in Git | Official section |
|---|---|---|
| Install the Operator: `rhdh` Subscription, `fast-1.10`, Manual approval, `startingCSV: rhdh-operator.v1.10.5`, own allow-listing approval hook | `gitops/stages/070-advanced-app-platform/070-rhdh/rhdh-operator/` | [Install the Operator][install] |
| External services: Operator-managed local PostgreSQL (Deviation: demo); GitLab mirror and tokens from `070-gitlab`; Keycloak from Stage 010 | `070-rhdh/README.md` ("Depends on") | [Prepare external services][external] |
| Provision custom configuration: ConfigMaps `app-config-rhdh`, `dynamic-plugins-rhdh`, `rhdh-rbac-policies`; Secret `rhdh-secrets` filled by `job-configure-rhdh` | `070-rhdh/rhdh-instance/`, `070-rhdh/jobs/configure-rhdh.yaml` | [Provision custom configuration][provision] |
| Authentication: OIDC to Keycloak realm `platform`, client `rhdh`, `auth.environment: production` (no guest), resolver `preferredUsernameMatchingUserEntityName`; Users `ai-admin`, `ai-developer` are static catalog entities (Deviation: no RHBK user import) | `070-rhdh/rhdh-instance/app-config-configmap.yaml`, `070-rhdh/catalog/all.yaml` | [Enable authentication with RHBK][rhbk], [Disable guest login][guest], [Import users from RHBK][import] |
| Run with the Operator: `Backstage` `developer-hub`, wave 18, `maxSurge: 0`, `NODE_EXTRA_CA_CERTS` | `070-rhdh/rhdh-instance/backstage.yaml` | [Run with your custom configuration][run] |
| RBAC: CSV policy file in Git, `ai-admin` as policy admin; the Web UI is not the source of truth | `070-rhdh/rhdh-instance/rbac-policy.yaml` | [RBAC in the Web UI][rbac-ui] |

## Procedure

1. Deploy and validate through the stage scripts after the OpenShift safety
   guard in `AGENTS.md` (`070-rhdh` is deploy-order 8, last):

   ```bash
   ./stages/070-advanced-app-platform/deploy.sh
   ./stages/070-advanced-app-platform/validate.sh
   ```

2. Read-only checks:

   ```bash
   oc get subscription rhdh -n rhdh-operator -o jsonpath='{.status.installedCSV}{"\n"}'
   oc get backstage developer-hub -n rhdh; oc get pods -n rhdh
   ```

## Pitfalls

- Roles created in the Web UI are not in Git and are lost or contradicted by
  the CSV file; change `rbac-policy.yaml` instead (`rhdh-authorization`).
- A fresh database with two backends racing migrations leaves the portal at
  0/1 ready; `maxSurge: 0` exists for that (`backstage.yaml` comment).
- OIDC sign-in 504 after a cluster resume:
  `docs/TROUBLESHOOTING.md#red-hat-developer-hub-oidc-sign-in-fails-with-504-gateway-timeout`.
- The GitHub and Microsoft Azure sign-in paths of the guide are not used.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Production checklist | [Checklist][checklist] |
| Install and external services | [Install the Operator][install], [Prepare external services][external] |
| Configuration and run | [Provision custom configuration][provision], [Run with the Operator][run] |
| Authentication | [Understand authentication and provisioning][authn], [Disable guest login][guest], [Share a secret with RHBK][rhbk-secret], [Enable RHBK][rhbk] |
| RBAC | [RBAC in the Web UI][rbac-ui] |

## Related skills

`rhdh-install-ocp`, `rhdh-configure`, `rhdh-authentication`,
`rhdh-authorization`, `rhdh-dynamic-plugins-install`,
`rhdh-getting-started-navigate`, `rhdh-upgrade`.

[checklist]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/setting_up_and_configuring_your_first_red_hat_developer_hub_instance/index#checklist-to-run-your-first-rhdh-instance-in-production_setting-up-and-configuring-your-first-red-hat-developer-hub-instance
[install]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/setting_up_and_configuring_your_first_red_hat_developer_hub_instance/index#install-the-rhdh-operator_setting-up-and-configuring-your-first-red-hat-developer-hub-instance
[external]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/setting_up_and_configuring_your_first_red_hat_developer_hub_instance/index#prepare-your-external-services_setting-up-and-configuring-your-first-red-hat-developer-hub-instance
[provision]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/setting_up_and_configuring_your_first_red_hat_developer_hub_instance/index#provision-your-custom-rhdh-configuration_setting-up-and-configuring-your-first-red-hat-developer-hub-instance
[authn]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/setting_up_and_configuring_your_first_red_hat_developer_hub_instance/index#understand-authentication-and-user-provisioning_enable-authentication-in-rhdh-with-mandatory-steps-only
[guest]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/setting_up_and_configuring_your_first_red_hat_developer_hub_instance/index#disable-the-guest-login_enable-or-disable-authentication-with-the-guest-user
[rhbk-secret]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/setting_up_and_configuring_your_first_red_hat_developer_hub_instance/index#share-a-secret-with-rhbk_enable-authentication-in-rhdh-with-mandatory-steps-only
[import]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/setting_up_and_configuring_your_first_red_hat_developer_hub_instance/index#import-users-and-groups-from-rhbk_enable-authentication-in-rhdh-with-mandatory-steps-only
[rhbk]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/setting_up_and_configuring_your_first_red_hat_developer_hub_instance/index#enable-authentication-with-rhbk_enable-authentication-in-rhdh-with-mandatory-steps-only
[run]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/setting_up_and_configuring_your_first_red_hat_developer_hub_instance/index#use-the-rhdh-operator-to-run-rhdh-with-your-custom-configuration_enable-authentication-in-rhdh-with-mandatory-steps-only
[rbac-ui]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/setting_up_and_configuring_your_first_red_hat_developer_hub_instance/index#manage-role-based-access-controls-rbac-using-the-rhdh-web-ui_enable-authentication-in-rhdh-with-mandatory-steps-only
