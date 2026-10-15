# MaaS database (`040-maas-database`)

This Application runs the PostgreSQL database that OpenShift AI Models-as-a-Service (MaaS) uses for API key lifecycle data. It also creates the `models-as-a-service` tenant namespace. Both are data, so neither is pruned or deleted with the Application. The MaaS API (`maas-api` in `redhat-ai-gateway-infra`) is the only consumer. It reads the connection string from a runtime Secret that `stages/040-governed-models-as-a-service/deploy.sh` creates.

| | |
|---|---|
| Argo CD Application | `040-maas-database` ([manifest](../../../applications/040-maas-database.yaml)) |
| Deployed by | `stages/040-governed-models-as-a-service/deploy.sh` (deploy-order 2); credentials from `stages/040-governed-models-as-a-service/deploy.sh`, which `deploy.sh` calls |
| Validated by | `stages/040-governed-models-as-a-service/validate.sh` → `stages/040-governed-models-as-a-service/validate.sh` ("Current durable MaaS PostgreSQL and runtime credential presence"); `preflight.sh` (retained-data and ownership checks before deploy) |
| Sync | Automated, `prune: true`, `selfHeal: true`; `CreateNamespace`, `SkipDryRunOnMissingResource`, `ServerSideDiff`, `RespectIgnoreDifferences` [6]; compare-option `ServerSideDiff=true` [5]; `ignoreDifferences` on `/data` of two runtime Secrets |
| Depends on | Stage 010 (OpenShift AI with `aigateway` delegated, which creates `redhat-ai-gateway-infra`); the `gp3-csi` StorageClass |
| Used by | `maas-api` (via `maas-db-config`); `040-maas-platform` (RoleBindings in `models-as-a-service`); the MaaS controller (tenant resources in `models-as-a-service`) |

## Why

The MaaS guide requires a PostgreSQL 14 or later instance for API key lifecycle management. OpenShift AI does not provide one [1]. The demo runs a single in-cluster PostgreSQL 16 from the Red Hat RHEL 9 image, which keeps the platform self-contained.

The database is a separate Application because its lifecycle differs: it holds state that must survive any change to gateway, model or access configuration. Its namespaces and StatefulSet carry `Prune=false,Delete=false`, so Argo CD keeps them when it prunes or when someone deletes the Application [6].

The `models-as-a-service` namespace sits here for the same reason. It is the MaaS tenant namespace, where the native controller keeps tenant configuration and subscriptions, and it must not disappear with a policy change.

## What

### Namespaces and database (top level)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Namespace | `models-as-a-service` | (cluster) | MaaS tenant namespace. Labels `maas-gateway-access=true`, `opendatahub.io/dashboard=true`, `demo.rhoai.io/maas-route-access=true`, `kueue.openshift.io/managed=true`, Pod Security `restricted` audit/warn. Wave 1, `Prune=false,Delete=false` |
| Namespace | `models-as-a-service-db` | (cluster) | Database namespace, Pod Security `restricted` audit/warn. Wave 1, `Prune=false,Delete=false` |
| NetworkPolicy | `maas-postgres` | `models-as-a-service-db` | Ingress to PostgreSQL TCP 5432 only from `redhat-ai-gateway-infra` (wave 7) |
| Service | `maas-postgres` | `models-as-a-service-db` | ClusterIP on 5432 (wave 8) |
| StatefulSet | `maas-postgres` | `models-as-a-service-db` | One replica, `registry.redhat.io/rhel9/postgresql-16` pinned by digest, credentials from `envFrom` Secret `maas-postgres-credentials`, `pg_isready` probes, 100m/256Mi requests, 500m/1Gi limits, 5Gi `gp3-csi` RWO volume claim template. Wave 8, `Prune=false,Delete=false` |

### `jobs/`: credential barrier

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServiceAccount | `wait-maas-db-credentials` | `models-as-a-service-db` | Job identity (wave 6) |
| Role | `wait-maas-db-credentials` | `models-as-a-service-db` | `get` on Secret `maas-postgres-credentials` only (wave 6) |
| RoleBinding | `wait-maas-db-credentials` | `models-as-a-service-db` | Binds the Role to the ServiceAccount (wave 6) |
| Job | `wait-maas-db-credentials` | `models-as-a-service-db` | `Sync` hook, wave 7, delete policy `BeforeHookCreation,HookSucceeded`. Polls up to 10 minutes for the credential Secret's metadata. Fails the sync if the Secret never appears, so the StatefulSet (wave 8) never starts without credentials |

### Objects not in Git

| Object | Owner |
|---|---|
| Secret `maas-postgres-credentials` (`POSTGRESQL_USER`, `POSTGRESQL_PASSWORD`, `POSTGRESQL_DATABASE`) in `models-as-a-service-db` | `stages/040-governed-models-as-a-service/deploy.sh`, label `app.kubernetes.io/managed-by=stage040-runtime`, no Argo CD tracking |
| Secret `maas-db-config` (`DB_CONNECTION_URL`) in `redhat-ai-gateway-infra` | `stages/040-governed-models-as-a-service/deploy.sh`, same label |
| PVC `data-maas-postgres-0` | StatefulSet controller (volume claim template) |
| Namespace `redhat-ai-gateway-infra` | OpenShift AI AIGateway controller |

## How

- **Ordering.** Namespaces (wave 1), barrier RBAC (wave 6), barrier Job and NetworkPolicy (wave 7), Service and StatefulSet (wave 8). `deploy.sh` applies the Application first and then runs `stages/040-governed-models-as-a-service/deploy.sh`, so the barrier Job, a `Sync` hook that runs inside wave 7 [3], waits for the script. If `preflight.sh` reports a clean cluster, `deploy.sh` passes `--fresh-database`.
- **Credentials.** `stages/040-governed-models-as-a-service/deploy.sh` never rotates an existing password. On a fresh install it generates a random 48-hex-character password for user and database `maas` and creates `maas-postgres-credentials`. It then waits for `redhat-ai-gateway-infra` and creates `maas-db-config` with `postgresql://maas:<password>@maas-postgres.models-as-a-service-db.svc.cluster.local:5432/maas?sslmode=disable`. Both Secrets are created through standard input and contain no values from Git. If storage or a StatefulSet exists without credentials, the script refuses to continue: restore the original Secret instead. If an existing `maas-db-config` differs from the URI that the credentials imply, it also refuses. The MaaS guide names the Secret, namespace and key [1].
- **Transport.** The connection string uses `sslmode=disable`. The guide's example uses `sslmode=require` [1]. The demo limits plaintext to in-cluster traffic and constrains it with the `maas-postgres` NetworkPolicy. The pod has no other policy selecting it, so this policy alone defines its ingress [2].
- **`ignoreDifferences`.** The Application ignores `/data` on `maas-postgres-credentials` and `maas-db-config`. Neither Secret is rendered from Git, so these entries [4] only matter if Argo CD ever tracks them. `preflight.sh` accepts the Secrets only when they are untracked or tracked by a Stage 040 component.
- **Tenant namespace label.** The kustomization's `replacements` set `app.kubernetes.io/part-of=modelsasservice` on `models-as-a-service`, which is the value the native AITenant controller writes, so Argo CD and the controller do not fight over it. The other `part-of` labels in the component stay `rhoai3-coding-demo`.
- **Storage.** 5Gi `gp3-csi` (AWS EBS CSI). `preflight.sh` checks that the StorageClass exists with provisioner `ebs.csi.aws.com` and that any retained PVC is `data-maas-postgres-0`, Bound and owned by the StatefulSet.
- **Cluster-specific values.** None in Git.

## Validation

`stages/040-governed-models-as-a-service/validate.sh` requires the StatefulSet to be available, PVC `data-maas-postgres-0` to be Bound on `gp3-csi`, and both runtime Secrets to have their keys. It reads key names only. `preflight.sh` checks retained database state and ownership before every deploy.

By hand:

```bash
oc get statefulset,pvc,svc,networkpolicy -n models-as-a-service-db
oc get secret maas-postgres-credentials -n models-as-a-service-db -o jsonpath='{.metadata.labels.app\.kubernetes\.io/managed-by}{"\n"}'
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Database engine | Customer-provided PostgreSQL 14 or later [1] | PostgreSQL 16, `rhel9/postgresql-16`, pinned by digest | Aligned |
| Connection Secret | `maas-db-config` with key `DB_CONNECTION_URL` in the infrastructure namespace (default `redhat-ai-gateway-infra`) [1] | Created by `stages/040-governed-models-as-a-service/deploy.sh` in `redhat-ai-gateway-infra` | Aligned |
| Connection TLS | The example connection string uses `sslmode=require` [1] | `sslmode=disable`, with ingress restricted by NetworkPolicy | Deviation (justified: in-cluster demo database without a server certificate; plaintext stays in the pod network and the policy admits only two namespaces) |
| Secrets outside Git | Secrets are not stored in the manifests [1] | Runtime Secrets only. Git holds no credential values | Aligned |
| Data retention under GitOps | `Prune=false` and `Delete=false` keep resources [6] | Set on both namespaces and the StatefulSet | Aligned |
| Availability | Not specified for MaaS | One replica, no backup job | Gap: no backup or high availability for API key state (acceptable for a demo; not production) |
| Network isolation | Not specified for MaaS | NetworkPolicy admits only `redhat-ai-gateway-infra`, where `maas-db-config` lives in 3.5 | Aligned |

## References

1. Govern LLM access with Models-as-a-Service, sections 1.2 "Platform and Operator prerequisites for Models-as-a-Service" and 1.5 "Configure the database secret for Models-as-a-Service", Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index
2. Network Policies, "The two sorts of pod isolation" (policies are additive), Kubernetes (upstream). https://kubernetes.io/docs/concepts/services-networking/network-policies/
3. Sync waves and hooks, "How sync waves work?" and "Hook lifecycle and cleanup", Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
4. Diffing customization, "Application Level Configuration", Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/diffing/
5. Diff strategies, "Enabling Server-Side Diff for one application", Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/diff-strategies/
6. Sync options, "No Prune Resources", "No Resource Deletion", "Respect ignore differences configs", Argo CD (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/
