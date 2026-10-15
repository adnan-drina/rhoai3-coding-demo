---
name: rhoai-model-registry
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when changing, reviewing or debugging the Stage 030 model registry
  service: the `modelregistry` DataScienceCluster component and
  `registriesNamespace: rhoai-model-registries`, the `ModelRegistry` CR
  `demo-registry` with its operator-generated PostgreSQL, the kube-rbac-proxy
  route, registry RoleBindings for `rhods-admins` and `rhoai-developers`, or
  registry deletion and database retention
  (gitops/stages/030-private-model-serving/030-private-model-serving/model-discovery/).
  Do NOT use for registering models, versions and evaluation properties (use
  rhoai-model-registry-workflows) or catalog sources (use
  rhoai-model-catalog-sources).
---

# RHOAI Model Registry (administration)

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/030-private-model-serving/030-private-model-serving/README.md`.

## When to use

- `stages/030-private-model-serving/validate.sh` reports the registry, its database or its
  authenticated route unhealthy.
- Granting registry access to a new group or ServiceAccount.
- Considering an external database, a second registry, or deleting one.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| `modelregistry` set `Managed` with `registriesNamespace: rhoai-model-registries` by Sync hook `enable-model-discovery` into fields Stage 010 delegates | `gitops/stages/030-private-model-serving/030-private-model-serving/model-discovery/enable-job.yaml` | [Enable the model registry component][enable] |
| Registry declared in Git as `ModelRegistry` `demo-registry` (`modelregistry.opendatahub.io/v1beta1`), not created in the dashboard; wave 6, `Prune=false,Delete=false` | `gitops/stages/030-private-model-serving/030-private-model-serving/model-discovery/registry/modelregistry-demo.yaml` | [Create a model registry][create] |
| Default database (`postgres.generateDeployment: true`, `sslMode: disable`): demo only, no HA, backup or TLS | same file | [Create a model registry][create] |
| REST route disabled; only the kube-rbac-proxy route on 443, which checks the caller's token | same file | [Create a model registry][create] |
| Group access only: `rhods-admins` and `rhoai-developers` bound to the operator-created Role `registry-user-demo-registry` (wave 7) | `gitops/stages/030-private-model-serving/030-private-model-serving/model-discovery/registry/` | [Manage registry permissions][perms] |
| Namespace `rhoai-model-registries` is owned by Stage 030 and also hosts the Model Catalog, Agent Catalog source and the EvalHub catalog-insights Role | `gitops/stages/030-private-model-serving/030-private-model-serving/model-discovery/registry/namespace-rhoai-model-registries.yaml` | [Model catalog and registries][overview] |

## Procedure

1. Change manifests, commit, publish, then deploy Stage 030; `deploy.sh`
   refuses a `demo-registry` whose live spec differs from Git or whose database
   PVC and Secret it does not own:

   ```bash
   ./stages/030-private-model-serving/deploy.sh
   ./stages/030-private-model-serving/validate.sh
   ```

2. Inspect read-only, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get modelregistries.modelregistry.opendatahub.io demo-registry -n rhoai-model-registries \
     -o jsonpath='{range .status.conditions[*]}{.type}={.status} {end}{"\n"}'
   oc get deploy,pvc,route,role,rolebinding -n rhoai-model-registries
   ```

3. New access: add a RoleBinding to the operator-created Role next to the two
   existing ones; avoid `system:authenticated`.

## Pitfalls

- The 3.5 guide spells the generated Role `registry-users-<name>`; the repo
  binds `registry-user-demo-registry`, the name the operator created on this
  cluster (live check 2026-10-15). Check with `oc get role -n rhoai-model-registries` before adding a
  binding ([permissions][perms]).
- Deleting the registry does not delete its database ([Delete a model
  registry][delete]); the CR and namespace are `Prune=false,Delete=false`, so
  removal from Git also leaves them. Registry records live in that database.
- Moving to production means an external PostgreSQL (16.x) or MySQL database,
  with a CA certificate when TLS is enforced ([Create][create]); the default
  database is not supported for production.
- The registry history before Stage 030 owned it:
  `docs/OPERATIONS.md#stage-030`.

## Official documentation (RHOAI 3.5)

| Topic | Section |
|---|---|
| Catalog versus registry | [Model catalog and model registries][overview], [Model registry][registry] |
| Enable | [Enable the model registry component][enable] |
| Create, edit | [Create][create], [Edit][edit] |
| Access | [Manage model registry permissions][perms] |
| Delete | [Delete a model registry][delete] |

## Related skills

`rhoai-model-registry-workflows`, `rhoai-model-catalog-sources`,
`rhoai-dsci-dsc-configuration`, `rhoai-users-groups-access`,
`rhoai-api-tiers`.

[overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_model_registries/index#overview-of-model-registries_managing-model-registries
[registry]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_model_registries/index#model_registry
[enable]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_model_registries/index#enabling-the-model-registry-component_managing-model-registries
[create]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_model_registries/index#creating-a-model-registry_managing-model-registries
[edit]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_model_registries/index#editing-a-model-registry_managing-model-registries
[perms]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_model_registries/index#managing-model-registry-permissions_managing-model-registries
[delete]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_model_registries/index#deleting-a-model-registry_managing-model-registries
