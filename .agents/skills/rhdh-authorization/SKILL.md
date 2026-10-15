---
name: rhdh-authorization
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhdh
  docs-version: "1.10"
  skill-group: "Developer Hub"
description: >
  Use when changing or reviewing who may do what in this demo's Red Hat
  Developer Hub: the RBAC plugin, policy administrator ai-admin, the
  rbac-policies.csv file in ConfigMap rhdh-rbac-policies mounted through
  extraFiles, role:default/developer for ai-developer (catalog read, template
  use, task create/read, Kubernetes read; catalog writes denied),
  pluginsWithPermission, and RBAC-related validation tests. Do NOT use for
  sign-in or user identity (use rhdh-authentication), Kubernetes RBAC of the
  plugin ServiceAccount (use rhdh-dynamic-plugins-configure), or installation.
---

# Developer Hub authorization

Thin skill: repo decisions and pitfalls here, product behavior in the linked
Developer Hub 1.10 sections. Detailed record:
`gitops/stages/070-advanced-app-platform/070-rhdh/README.md` (How: Authorization).

## When to use

- A change touches `070-rhdh/rhdh-instance/rbac-policy.yaml` or the `permission`
  block of `app-config-rhdh`.
- A persona can see or do more or less than expected in the portal.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| RBAC plugin enabled (`backstage-community-plugin-rbac`), `permission.enabled: true` | `070-rhdh/rhdh-instance/dynamic-plugins-configmap.yaml`, `app-config-configmap.yaml` | [Enable RBAC][enable] |
| Policy administrator `user:default/ai-admin` in `permission.rbac.admin.users` | `070-rhdh/rhdh-instance/app-config-configmap.yaml` | [Enable RBAC][enable] |
| Policies come only from a CSV file in Git (`policies-csv-file: /opt/app-root/src/rbac/rbac-policies.csv`), mounted from ConfigMap `rhdh-rbac-policies` by `extraFiles`; no Web UI or REST edits | `070-rhdh/rhdh-instance/rbac-policy.yaml`, `backstage.yaml` | [Choose the policy source][source], [External files with the Operator][files-op] |
| `ai-developer` gets `role:default/developer`: catalog entity read, location read, template read, action use, task create/read, Kubernetes clusters and resources read; catalog location create, entity create and delete denied | `070-rhdh/rhdh-instance/rbac-policy.yaml` | [Catalog][perm-catalog], [Scaffolder][perm-scaffolder], [Kubernetes][perm-k8s] permissions |
| `pluginsWithPermission: [catalog, scaffolder, permission, kubernetes]` | `070-rhdh/rhdh-instance/app-config-configmap.yaml` | [Enable RBAC][enable] |
| Only the platform catalog may add templates; developers cannot register locations (enforced by the deny rows and catalog rules) | same files, `070-rhdh/catalog/all.yaml` | [Design policy rules][design] |

Paths are under `gitops/stages/070-advanced-app-platform/`.

## Procedure

1. Edit `rbac-policies.csv` in Git; keep default-deny (grant only what a
   persona needs) and add an explicit deny for catalog writes.
2. A new plugin with its own permissions needs its ID in
   `pluginsWithPermission` and rows from the [permission reference][perms].
3. Validate:

   ```bash
   ./stages/070-advanced-app-platform/validate.sh --static   # security-boundaries.test.py RBAC tests
   ./stages/070-advanced-app-platform/validate.sh
   oc get configmap rhdh-rbac-policies -n rhdh -o jsonpath='{.data.rbac-policies\.csv}'
   ```

## Pitfalls

- Tekton, Topology and Argo CD have their own permission sets
  ([Tekton][perm-tekton], [Topology][perm-topology], [Argo CD][perm-argocd]);
  the repo lists only `kubernetes` of these in `pluginsWithPermission`. Read
  the reference and add CSV rows before listing another plugin, or its views
  can disappear for `ai-developer`.
- `ai-admin` is a policy administrator by config; giving it a CSV role as
  well is unnecessary.
- The tests `test_only_admins_register_and_discovery_does_not_ingest_templates`
  and `test_developer_can_view_delivery_without_proxy_or_catalog_writes` in
  `stages/070-advanced-app-platform/tests/security-boundaries.test.py` encode
  this policy; update them with any intentional change.

## Official documentation (Developer Hub 1.10)

| Topic | Section |
|---|---|
| Concepts | [RBAC in Developer Hub][rbac] |
| Enablement | [Enable RBAC][enable] |
| Policy source and design | [Choose the policy source][source], [Design policy rules][design] |
| External files | [External files][files], [With the Operator][files-op] |
| Permission reference | [Reference][perms], [Catalog][perm-catalog], [Scaffolder][perm-scaffolder], [Kubernetes][perm-k8s] |
| Not used | [Web UI][webui], [REST API][rest], [Conditional policies][cond] |

## Related skills

`rhdh-authentication`, `rhdh-configure`, `rhdh-dynamic-plugins-configure`.

[rbac]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authorization_in_red_hat_developer_hub/index#role-based-access-control-in-rhdh_authorization-in-rhdh
[enable]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authorization_in_red_hat_developer_hub/index#enable-and-give-access-to-the-role-based-access-control-rbac-feature_authorization-in-rhdh
[source]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authorization_in_red_hat_developer_hub/index#determine-permission-policy-and-role-configuration-source_authorization-in-rhdh
[design]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authorization_in_red_hat_developer_hub/index#design-your-policy-rules_authorization-in-rhdh
[files]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authorization_in_red_hat_developer_hub/index#manage-authorizations-by-using-external-files_authorization-in-rhdh
[files-op]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authorization_in_red_hat_developer_hub/index#define-authorizations-in-external-files-by-using-the-operator_manage-authorizations-by-using-external-files
[perms]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authorization_in_red_hat_developer_hub/index#permission-policies-reference_authorization-in-rhdh
[perm-catalog]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authorization_in_red_hat_developer_hub/index#catalog-permissions_permission-policies-reference
[perm-scaffolder]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authorization_in_red_hat_developer_hub/index#scaffolder-permissions_permission-policies-reference
[perm-k8s]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authorization_in_red_hat_developer_hub/index#kubernetes-permissions_permission-policies-reference
[perm-topology]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authorization_in_red_hat_developer_hub/index#topology-permissions_permission-policies-reference
[perm-tekton]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authorization_in_red_hat_developer_hub/index#tekton-permissions_permission-policies-reference
[perm-argocd]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authorization_in_red_hat_developer_hub/index#argocd-permissions_permission-policies-reference
[webui]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authorization_in_red_hat_developer_hub/index#manage-role-based-access-controls-rbac-using-the-rhdh-web-ui_authorization-in-rhdh
[rest]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authorization_in_red_hat_developer_hub/index#manage-authorizations-by-using-the-rest-api_authorization-in-rhdh
[cond]: https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authorization_in_red_hat_developer_hub/index#conditional-policies-in-rhdh_authorization-in-rhdh
