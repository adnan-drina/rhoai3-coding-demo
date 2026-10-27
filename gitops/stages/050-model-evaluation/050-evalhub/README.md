# EvalHub evaluation service (`050-evalhub`)

This Application runs EvalHub, the OpenShift AI evaluation service managed by the TrustyAI operator, in its own `evalhub`
namespace with a project-owned PostgreSQL database. It registers the built-in and custom providers and collections,
enables the EvalHub MCP server for coding agents, and grants the programmatic and catalog principals. The
`ai-curated-prompts` global prompt workspace belongs to `010-mlflow`. Platform administrators, the qualification pipeline, the Stage 050 helpers
and MCP clients submit evaluations through it; the dashboard's **Evaluations** pages and the model catalog's **Safety and
security insights** tab read from it.

| | |
|---|---|
| Argo CD Application | `050-evalhub` ([manifest](../../../applications/050-evalhub.yaml)) |
| Deployed by | [`stages/050-model-evaluation/deploy.sh`](../../../../stages/050-model-evaluation/deploy.sh) (deploy-order 3), followed by [`stages/050-model-evaluation/deploy.sh`](../../../../stages/050-model-evaluation/deploy.sh) for the database Secret and MLflow address |
| Validated by | [`validate.sh`](../../../../stages/050-model-evaluation/validate.sh), [`stages/050-model-evaluation/validate.sh`](../../../../stages/050-model-evaluation/validate.sh) (database, EvalHub `Ready`, multi-tenant PostgreSQL, MLflow wiring, service RBAC) and [`stages/050-model-evaluation/validate.sh`](../../../../stages/050-model-evaluation/validate.sh) (authenticated API discovery) |
| Sync | Automated, `prune` and `selfHeal`. Server-Side Diff by annotation; `RespectIgnoreDifferences=true`, `SkipDryRunOnMissingResource=true`. |
| Depends on | `010-mlflow` (MLflow, dashboard `globalMLflowNamespaces`); `050-model-qualification` `evaluation-enablement/` (TrustyAI component, dashboard `disableLMEval: false`); `050-model-qualification` (namespace `evaluated-models`, Role `evalhub-evaluator`); `050-evaluation-content` (ConfigMaps for the custom providers and collections the CR lists); `030-private-model-serving` (namespace `rhoai-model-registries`). |
| Used by | `050-model-qualification` (pipeline steps call EvalHub), `050-evaluation-content` (SWE-bench grading runs through EvalHub), `050-oci-export`, the RHOAI dashboard, MCP clients. |

## Why

OpenShift AI 3.5 deploys EvalHub with an `EvalHub` custom resource reconciled by the TrustyAI operator, in a dedicated
namespace rather than `redhat-ods-applications`, with a PostgreSQL database whose Secret holds a `db-url` key [1]. Tenants
are labelled namespaces (here `evaluated-models`) and access is checked against virtual resources in the tenant [1]. The
MCP server lets AI coding agents discover providers and submit evaluations [1]. The product does not provide a database
operator, so this component runs one pinned Red Hat PostgreSQL 16 StatefulSet.

The `ai-curated-prompts` global MLflow prompt workspace, which the dashboard lists through `globalMLflowNamespaces`, is
declared by `010-mlflow` (`prompts/`); MLflow watches the `opendatahub.io/global-mlflow-workspace` label [2][3].

## What

### Service and database (component root)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Namespace | `evalhub` | cluster | Wave 0, `Prune=false,Delete=false`. Dedicated service namespace (not a tenant). |
| ServiceAccount, Role, RoleBinding | `evalhub-credentials-ready` | `evalhub` | Wave 10. `get` on Secret `evalhub-db-credentials` only. |
| Job | `evalhub-credentials-ready` | `evalhub` | `Sync` hook, wave 11, `BeforeHookCreation,HookSucceeded`, 600 s deadline. Waits until `stages/050-model-evaluation/deploy.sh` has created the database Secret. |
| PersistentVolumeClaim | `evalhub-postgresql` | `evalhub` | Wave 12, `Prune=false,Delete=false`. 10 Gi `gp3-csi`. |
| Service | `evalhub-postgresql` | `evalhub` | Wave 12. Port 5432. |
| StatefulSet | `evalhub-postgresql` | `evalhub` | Wave 12. One replica, `rhel9/postgresql-16` pinned by digest, no service-account token, `RuntimeDefault` seccomp, all capabilities dropped. |
| NetworkPolicy | `evalhub-postgresql` | `evalhub` | Wave 12. Ingress to 5432 only from the EvalHub API pods (`app=eval-hub, instance=evalhub, component=api`). |
| ServiceAccount | `evalhub-mcp-client` | `evalhub` | Wave 29. Identity the MCP server uses to call the EvalHub API. |
| Secret (`kubernetes.io/service-account-token`) | `evalhub-mcp-client-token` | `evalhub` | Wave 29. Token for `spec.mcp.authSecret`; filled by Kubernetes. |
| RoleBinding | `evalhub-mcp-client-access` | `evaluated-models` | Wave 29. `evalhub-evaluator` for `evalhub-mcp-client`. |
| EvalHub | `evalhub` | `evalhub` | Wave 30, `Prune=false,Delete=false`. One replica, `tenancy: multi`, PostgreSQL, 12 providers, 18 collections, MCP server, MLflow URI from a ConfigMap. |
| RoleBinding | `evalhub-mcp-access` | `evalhub` | Wave 31. Operator Role `evalhub-service-access-role` (`evalhubs/proxy`) for `evaluated-models/evalhub-automation`, so it passes the MCP kube-rbac-proxy. |

### `tenant/`

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServiceAccount | `evalhub-automation` | `evaluated-models` | Wave 12. ServiceAccount principal for the SDK, CLI, CI and MCP clients; tokens are issued with `oc create token`. |
| RoleBinding | `evalhub-automation-access` | `evaluated-models` | Wave 12. `evalhub-evaluator` for that ServiceAccount. |
| Role | `evalhub-catalog-insights` | `rhoai-model-registries` | Wave 12. `get` on virtual resource `evaluations.trustyai.opendatahub.io` only. |
| RoleBinding | `demo-evalhub-catalog-insights` | `rhoai-model-registries` | Wave 12. That Role for `rhods-admins` and `rhoai-developers`, so the catalog's safety-insights tab passes the Eval Hub BFF's tenant check. The namespace is not a tenant. |

### `prompts/` (moved)

Moved on 2026-10-14 to the MLflow component (`prompts/`), now `010-mlflow`: `ai-curated-prompts` is an MLflow global workspace, enabled by the MLflow hook.

### Objects not in Git

| Object | Created by |
|---|---|
| Secret `evalhub-db-credentials` (`database-user`, `database-password`, `database-name`, `db-url`) | `stages/050-model-evaluation/deploy.sh`, once, with a random password |
| ConfigMap `evalhub-mlflow-connection` (`tracking-uri`) | `stages/050-model-evaluation/deploy.sh` after MLflow is `Available` |
| Deployments `evalhub`, `evalhub-mcp`; Services `evalhub`, `evalhub-mcp`, `evalhub-metrics`; Route `evalhub-mcp` (re-encrypt); Role `evalhub-service-access-role`; ConfigMap `evalhub-service-ca` | TrustyAI operator, owned by the `EvalHub` CR |
| Built-in provider ConfigMaps `trustyai-service-operator-evalhub-provider-*` in `redhat-ods-applications` | TrustyAI operator |
| Tenant objects in `evaluated-models` (`evalhub-evalhub-job`, `evalhub-discovery`, `evalhub-service-ca`) | TrustyAI operator |
| Evaluation jobs, results, MLflow runs | EvalHub at run time |

## How

**Ordering.** Namespace (0); credential wait (10, 11); database (12); MCP identity (29); EvalHub
(30); MCP access (31) [5]. `deploy.sh` applies the Application first and then runs `stages/050-model-evaluation/deploy.sh`, which creates
the database Secret the wave-11 hook is waiting for, then publishes the MLflow URI. `deploy.sh` waits for
`status.ready: True` on the `EvalHub` CR.

**EvalHub CR fields.**

| Field | Value | Reason |
|---|---|---|
| `database` | `type: postgresql`, `secret: evalhub-db-credentials` | Documented database configuration; the Secret carries `db-url` [1] |
| `tenancy` | `multi` | Tenancy by labelled namespaces [1]; the validator requires it |
| `providers` | nine built-in (`deepeval`, `garak`, `garak-kfp`, `guidellm`, `ibm-clear`, `inspect`, `lighteval`, `lm-evaluation-harness`, `ragas`) plus `swebench`, `inspect-coding` | A provider ConfigMap is used only once its id is listed in `spec.providers` [1]; the two custom ones come from `050-evaluation-content` |
| `collections` | nine built-in plus four `agentic-coding-*` | Same rule for collections in `spec.collections` [1] |
| `mcp` | `enabled: true`, `transport: http`, `authSecret: evalhub-mcp-client-token`, env `EVALHUB_TENANT=evaluated-models` | MCP server for remote clients [1]. The guide's procedure sets `port: 3001` and exposes the Service with `oc expose`; the 3.5.1 CRD has no port field and the operator creates the re-encrypt Route itself. Without `authSecret` the MCP server's calls return 401, and 3.5.1 does not forward the client's `x-tenant` header, so the tenant is pinned. |
| `env.MLFLOW_TRACKING_URI` | from ConfigMap `evalhub-mlflow-connection` | The MLflow HTTPS address is known only after MLflow is `Available` [1] |

**Collection and provider id length.** EvalHub 1.0 validates ids (36 characters or fewer) at start-up; one invalid id stops
the new pod from starting while the old pod keeps serving.

**Database transport.** The `db-url` written by `stages/050-model-evaluation/deploy.sh` uses `sslmode=disable`; the NetworkPolicy limits the
port to the EvalHub API pods.

**Access.** The catalog-insights Role grants a single verb on a virtual resource in the catalog namespace; the dashboard's
Eval Hub BFF performs a SubjectAccessReview for it before returning pre-computed safety data [1]. The automation
ServiceAccount has the same tenant Role as administrators. The MCP client token is a long-lived ServiceAccount token
Secret; rotate it by deleting the Secret and syncing.

**Secrets.** No value in Git. The database Secret is generated by `stages/050-model-evaluation/deploy.sh`; the MCP token is filled by
Kubernetes.

## Validation

`stages/050-model-evaluation/validate.sh` checks: the EvalHub PostgreSQL StatefulSet current and ready, its Bound `gp3-csi` PVC and Secret
keys; the `EvalHub` CR `Ready` with `tenancy: multi`, PostgreSQL and default connection pool; one current operator-owned
`evalhub` Deployment; `MLFLOW_TRACKING_URI` from `evalhub-mlflow-connection` equal to the MLflow address; the database
Secret mount; the MLflow CA, projected token (at most one hour) and workspace `evalhub`, with TLS verification on; the
EvalHub ServiceAccount may write MLflow experiments in `evalhub` and create Jobs in `evaluated-models`; the curated prompt
namespace label and dashboard settings. `stages/050-model-evaluation/validate.sh` performs authenticated, read-only API discovery.

By hand:

```bash
oc get evalhub evalhub -n evalhub -o jsonpath='{.status.phase} {.status.ready}{"\n"}'
oc get deploy,route -n evalhub
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Install method | `EvalHub` CR reconciled by the TrustyAI operator [1] | Same; TrustyAI enabled by `050-model-qualification` (`evaluation-enablement/`) | Aligned |
| Namespace | Dedicated namespace, not `redhat-ods-applications` [1] | `evalhub` | Aligned |
| Database | PostgreSQL Secret with `db-url` [1] | Same; single instance, plaintext in-namespace | Deviation (justified: demo; no HA, backup or TLS) |
| Multi-tenancy and roles | Tenant label; Role on virtual resources per tenant [1] | One tenant; documented Role bound to admins, automation and MCP identities | Aligned |
| Custom providers and collections | ConfigMaps with type/name labels, ids listed in the CR [1] | Listed in the CR; ConfigMaps in `050-evaluation-content` | Aligned |
| MCP server | `spec.mcp` `enabled`, `transport: http`, `port`; manual Route; client token from `oc create token` [1] | No `port` (absent from the 3.5.1 CRD); operator Route; `authSecret` added | Deviation (justified: 3.5.1 CRD differs from the procedure) |
| MLflow tracking | Running MLflow and tracking URI [1] | URI from a runtime ConfigMap, TLS verified with the service CA | Aligned |
| Dashboard pages | `disableLMEval` defaults to `true` [3] | Set to `false` by `050-model-qualification` (`evaluation-enablement/`) | Aligned |
| Global prompt workspace | Namespace label `opendatahub.io/global-mlflow-workspace` [2]; `globalProjectPrompts` Technology Preview [3] | Namespace and dashboard field both in `010-mlflow` | Aligned (Technology Preview) |
| Argo CD | Server-Side Diff by annotation [6]; `Prune=false,Delete=false` for retained data [4] | PVC, namespaces and CR retained; StatefulSet, Service and NetworkPolicy not | Gap (inconsistent with `010-mlflow`; see findings) |

## References

1. Evaluating AI systems (2.3 Deploy EvalHub with the TrustyAI Operator, 2.7 EvalHub multi-tenancy, 2.20 Configure MLflow experiment tracking for evaluation jobs, 2.22 Add a custom provider by using a ConfigMap, 2.23 Add a collection by using a ConfigMap, 2.29 Grant access to EvalHub, 2.30 EvalHub roles, 4.3 Deploy the EvalHub MCP server), Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index
2. Working with MLflow (global prompt registry namespaces), Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_mlflow/index
3. Customizing the dashboard (dashboard feature configuration options), Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_resources/customizing-the-dashboard
4. Sync options, Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/
5. Sync phases and waves, Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
6. Diff strategies (Server-Side Diff), Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/diff-strategies/
