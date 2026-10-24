# OpenShell agent runtime (`060-openshell-runtime`)

This Application runs the agent sandbox platform for Stage 060. It installs the Red Hat build of Agent Sandbox
operator, the authenticated NVIDIA OpenShell gateway (from a rendered upstream chart), the workspace projects
`openshell-admin`, `openshell-developer` and `ai-agents`, the images and MaaS subscriptions for the standalone OpenCode
and Hermes agents, and the MLflow trace permission for the selected-call tracing check. Workspace owners use it
through the OpenShell CLI, from a laptop through the gateway Route; the AgentOps console (`060-agent-console`) only reads what it creates.

| | |
|---|---|
| Argo CD Application | `060-openshell-runtime` ([manifest](../../../applications/060-openshell-runtime.yaml)) |
| Deployed by | [`stages/060-agent-runtime-and-agentops/deploy.sh`](../../../../stages/060-agent-runtime-and-agentops/deploy.sh) `--component 060-openshell-runtime` (also part of a full `deploy.sh` run) |
| Validated by | No component validator. `deploy.sh --component 060-openshell-runtime` gates on its runtime setup step, `check_operator_policy` and `stage-apps.sh wait` (Synced and Healthy at the SHA). Opt-in qualification: [`sandboxes/qualify.sh`](../../../../stages/060-agent-runtime-and-agentops/sandboxes/README.md) (`host`, `inference`, `opencode`, `hermes`, `client`). [`validate.sh`](../../../../stages/060-agent-runtime-and-agentops/validate.sh) reports the stage as pending (exit 2). |
| Sync | Manual (documented exception in `.agents/rules/gitops.md`). The script pins it to the selected published SHA and starts a hook-strategy sync through `scripts/stage-apps.sh`. Annotation `compare-options: ServerSideDiff=true`. Sync option `RespectIgnoreDifferences=true`; `ignoreDifferences` on `/data` of three runtime-owned objects. |
| Depends on | `060-openshell-identity` (realm `openshell` must exist for the issuer check). Stage 040 MaaS (`MaaSSubscription` API, model `internal-models/qwen3-8-27b`). Stage 050 MLflow (`mlflow.kubeflow.org` authorization). Group `rhods-admins` (Stage 010). The `redhat-operators` catalog with package `agent-sandbox-operator`. |
| Used by | `060-agent-console` (needs this Application Healthy and the Sandbox CRD). OpenCode and Hermes sandboxes in `ai-agents` and the developer's OpenCode sandbox in `openshell-developer`, created through the gateway by [`sandboxes/create.sh`](../../../../stages/060-agent-runtime-and-agentops/sandboxes/README.md), and the 2026-10 trace clients (MLflow experiment `agent-runtime-traces`). |

## Why

RHOAI 3.5 ships agent sandboxing with OpenShell as a Developer Preview built from upstream artifacts [1]. The
dashboard's agent deployment list reads OpenShell-managed `Sandbox` custom resources [1], which the Agent Sandbox
operator serves. Red Hat build of Agent Sandbox is a downstream build of `kubernetes-sigs/agent-sandbox` that projects
such as OpenShell use to create and manage sandbox pods [5]. OpenCode deployment on OpenShift AI is a separate
Technology Preview [2].

This repository diverges from the upstream getting-started guide [6] on purpose:

| Upstream guide [6] | This component | Reason |
|---|---|---|
| Chart 0.0.116, `odh-openshell-*` images | NVIDIA chart and images pinned by digest at commit `12cec59bf` [4] (dev build `0.1.3-dev.99`, merge of upstream PR 4150) | The earlier v0.1.2 tuple returned no bytes on the OpenCode HTTP path; the pinned commit passed qualification (stage plan). Not a tagged or supported release. |
| `allowUnauthenticatedUsers=true` | OIDC required, issuer from `060-openshell-identity` | Shared cluster. |
| `privileged` SCC for the sandbox service account | No SCC grant; workloads admitted under `restricted-v2` | `restricted-v2` drops all capabilities, sets RuntimeDefault seccomp and uses a namespace UID range [9]; the pinned build confines sockets on loopback without extra privilege (qualified by `sandboxes/qualify.sh host`). |
| Sandboxes in `openshell` | Operator workspace mode: one namespace per workspace, allowlisted by label | Per-owner isolation. |
| Passthrough Route | Passthrough Route `openshell`; the setup scripts still port-forward | Developers reach the gateway from a laptop CLI; every call still needs the OIDC login. The certificate does not name the Route host, so clients skip TLS verification (demo posture). |

One Application owns the whole runtime because the gateway, its workspaces, its images and its prerequisites share
one lifecycle and one readiness gate. Helm is not run by Argo CD: the chart is rendered offline and committed (see
[`chart/README.md`](chart/README.md)), so Argo CD stays the single owner.

## What

`oc kustomize` renders 65 objects.

### `chart/rendered/` — OpenShell gateway (rendered chart, 32 objects)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Namespace | `openshell` | — | Gateway project. Wave -30, `Delete=false,Prune=false`. |
| Namespace | `openshell-admin`, `openshell-developer`, `ai-agents` | — | Workspace projects, label `rhoai3.redhat.com/openshell-workspace=true` (gateway allowlist). `ai-agents` is shown in the dashboard as "AI Agents". Wave -30, `Delete=false,Prune=false`. |
| ServiceAccount, Role, RoleBinding | `openshell-sandbox` | each workspace | Gateway rights in the workspace: Sandbox CRUD, Pods, Services/NetworkPolicies create/get, Secrets create/delete. Wave -20. |
| NetworkPolicy | `openshell-sandbox-ssh` | each workspace | Admits only the gateway pod to sandbox port 2222. Wave -20. |
| RoleBinding | `rhods-admins-ai-agents-admin` | `ai-agents` | `admin` for group `rhods-admins`. Wave -20. |
| ServiceAccount, Role, RoleBinding | `openshell-certgen` | `openshell` | Certgen identity; Secret get limited to the three PKI Secret names. Wave -20 (Helm hook annotations removed). |
| Job | `openshell-certgen` | `openshell` | Sync hook, wave -10, `BeforeHookCreation,HookSucceeded`. Creates `openshell-server-tls`, `openshell-client-tls`, `openshell-jwt-keys` only if absent. |
| ServiceAccount | `openshell` | `openshell` | Gateway identity. |
| ClusterRole, ClusterRoleBinding | `openshell-node-reader-openshell` | — | Cluster read only: nodes, namespaces, RuntimeClasses, PriorityClasses, Sandbox list/watch, TokenReview create. No cluster-wide workload CRUD. |
| Role, RoleBinding | `openshell-peer`, `openshell-workspace-secret-source` | `openshell` | Pod get for peer discovery; get on `openshell-client-tls` only. |
| ConfigMap | `openshell-config` | `openshell` | `gateway.toml`: Kubernetes driver in operator workspace mode, mTLS, sandbox/supervisor image digests, `policy_validation_failure_mode = fail_closed`, websocket tunnel off. |
| Service | `openshell`, `openshell-peer` | `openshell` | ClusterIP gRPC 8080 and metrics 9090; headless peer service. |
| StatefulSet | `openshell` | `openshell` | One gateway replica, SQLite on a 1Gi RWO claim, PVC retention `Retain` on delete and scale. |

### `access/` — gateway Route

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Route | `openshell` | `openshell` | Passthrough TLS to the gateway's gRPC port, 1 h router timeout for long streams. Wave 5. Used by [`sandboxes/login.sh`](../../../../stages/060-agent-runtime-and-agentops/sandboxes/README.md) and developer CLIs. |

### `chart/controller/` — Agent Sandbox operator

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Namespace | `agent-sandbox-system` | — | Operator project. Wave -30. |
| OperatorGroup | `agent-sandbox` | `agent-sandbox-system` | `spec: {}` (all namespaces). Wave -20. |
| Subscription | `agent-sandbox-operator` | `agent-sandbox-system` | Channel `preview-0.9`, `redhat-operators`, `installPlanApproval: Automatic`, no `startingCSV`. Wave -20. |

### `init/` — runtime prerequisites and startup gate

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Secret | `openshell-credentials` | `openshell` | Empty placeholder (wave -25). The runtime setup step of `stages/060-agent-runtime-and-agentops/deploy.sh` adds `key-encryption-key`. |
| ConfigMap | `openshell-identity` | `openshell` | Empty placeholder (wave -25). The runtime setup step adds `issuer`. |
| ConfigMap | `openshell-runtime-ready` | `openshell` | Empty placeholder (wave -25). The runtime setup step adds `controller-ready`, `source-revision`, `controller-csv-uid`. |
| ServiceAccount, Role, RoleBinding | `openshell-runtime-init` | `openshell` | Get on exactly those three objects. Wave -25. |
| Role, RoleBinding | `openshell-runtime-app-reader` | `openshift-gitops` | Get on Application `060-openshell-runtime` only. Wave -25. |
| Job | `openshell-runtime-prerequisites` | `openshell` | Sync hook, wave -5, `BeforeHookCreation,HookSucceeded`, deadline 360 s. The startup gate (see How). |
| NetworkPolicy | `deny-direct-sandbox-router` | `agent-sandbox-system` | Empty ingress for the operator's `sandbox-router` pods: sandboxes are reached only through the gateway. Wave -25. |

### `images/`, `hermes-images/` — agent images

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ImageStream | `opencode-runtime` | `ai-agents` | Receives `opencode-runtime:1.18.16` from the BuildConfig below; no spec tags. `Delete=false,Prune=false`. |
| BuildConfig | `opencode-runtime` | `ai-agents` | Binary Docker build [14] to `opencode-runtime:1.18.16`; started by [`images/build-opencode.sh`](../../../../stages/060-agent-runtime-and-agentops/images/README.md). |
| ImageStream, BuildConfig | `hermes-runtime-api` | `ai-agents` | Binary Docker build to `hermes-runtime-api:0.20.5-api`; started by [`images/build-hermes.sh`](../../../../stages/060-agent-runtime-and-agentops/images/README.md). ImageStream `Delete=false,Prune=false`. |
| Role, RoleBinding | `opencode-runtime-pull`, `hermes-runtime-api-pull` | `ai-agents` | `imagestreams/layers` get for the workspace `openshell-sandbox` account; in `ai-agents`, `opencode-runtime-pull` also admits the `openshell-developer` account for the developer's OpenCode sandbox. |

All at wave 10.

The earlier `opencode-runtime` ImageStream, BuildConfig and pull Role/RoleBinding in `openshell` were retired on
2026-10-24. A sync with prune removes the BuildConfig and RBAC; the ImageStream keeps `Prune=false`, so delete it once on
a cluster that has it: `oc delete imagestream opencode-runtime -n openshell`.

### `opencode/`, `hermes/` — agent model access and contracts

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| MaaSSubscription | `opencode-private-qwen38`, `hermes-private-qwen38` | `models-as-a-service` | Owner `ai-admin`, only `internal-models/qwen3-8-27b`, 100,000 tokens per hour, priority 140 / 130, cost metadata. Wave 18, `SkipDryRunOnMissingResource=true`. |
| MaaSSubscription | `opencode-developer-qwen38` | `models-as-a-service` | The same scope for owner `ai-developer`'s OpenCode sandbox, priority 135. |
| ConfigMap | `opencode-runtime-contract`, `hermes-runtime-contract` | `ai-agents` | Non-secret names read by the setup helpers: workspace, sandbox, provider, subscription, model, key expiry (30 d). Image digests live in the sandbox templates. Wave 18. |

### `client-traces/` — selected-call tracing

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Role, RoleBinding | `agent-trace-experiments`, `ai-admin-agent-trace-experiments` | `ai-agents` | `mlflow.kubeflow.org` `experiments` get/list/create/update for `ai-admin`. |

### Not in Git

| Object | Owner |
|---|---|
| KEK value in `openshell-credentials`, issuer value, ready stamp | The runtime setup step of `stages/060-agent-runtime-and-agentops/deploy.sh` (delegated by `ignoreDifferences`) |
| Secrets `openshell-server-tls`, `openshell-client-tls`, `openshell-jwt-keys` | Certgen Job; no owner reference, not pruned |
| PVC `openshell-data-openshell-0` | StatefulSet claim template (retained) |
| Operator CSV, `agent-sandbox-controller` and `sandbox-router-deployment`, Sandbox CRDs | OLM / Agent Sandbox bundle |
| Gateway store: workspaces, members, global policy, providers, sandbox templates | Gateway SQLite; written through the gateway API by `stages/060-agent-runtime-and-agentops/deploy.sh` (workspace and members) and by `stages/060-agent-runtime-and-agentops/sandboxes/create.sh` (profiles, providers, templates, global policy) |
| Sandboxes `opencode`, `hermes` and their pods/claims in `ai-agents` | Gateway and Agent Sandbox controller |
| MaaS API keys bound to the two subscriptions | `sandboxes/create.sh`; stored only in the gateway provider credential |
| Recovery set `openshell-data-pre-pr4150` (PVC, snapshot, Secret copies) | Manual, from the 2026-10-06 upgrade |

## How

- **Order inside one sync.** Waves: namespaces -30; init RBAC and placeholders -25; operator Subscription, certgen
  RBAC and workspace RBAC -20; certgen Job -10; prerequisites Job -5; gateway 0; image objects 10; subscriptions and
  contracts 18. Hooks run in the Sync phase in wave order [13].
- **The startup gate.** The gateway Pod needs the issuer, the KEK and a ready Sandbox API, and none of these can be in
  Git. `deploy.sh --component 060-openshell-runtime` therefore starts the sync and works alongside it:
  1. applies the Application pinned to the published SHA and starts the sync;
  2. waits for the three placeholders, then runs the prepare part of its runtime setup, which writes `issuer` (derived
     from the `keycloak` Route and checked against the realm's OIDC discovery) and a 32-byte KEK. It reuses an existing
     KEK and refuses to create a new one while a gateway claim exists, because the KEK encrypts the stored credentials;
  3. waits for the operator CSV (`check_operator_policy --wait 900`), then runs the rest of the runtime setup, which checks
     the Subscription, the Succeeded CSV, the controller Deployments and the established Sandbox CRD, and stamps
     `openshell-runtime-ready` with `controller-ready=true`, `source-revision=<SHA>` and the CSV UID.

  Meanwhile the `openshell-runtime-prerequisites` hook (wave -5) polls for up to 300 s until `controller-ready` is
  `true`, `source-revision` equals the Application's `spec.source.targetRevision`, the issuer starts with `https://`
  and the KEK is present. Only then does the sync reach the gateway wave. Because the stamp must match the revision
  being synced, a sync of a new revision cannot pass on an old stamp; each revision needs a fresh runtime setup.
  For a sync that timed out, re-run `deploy.sh --component 060-openshell-runtime`; it stamps again and waits.
- **Delegated data.** `ignoreDifferences` covers all of `/data` on `openshell-credentials`, `openshell-identity` and
  `openshell-runtime-ready`, with `RespectIgnoreDifferences=true` so a sync does not write Git's empty map over the
  runtime values [7], [8]. Metadata, Secret type and every other object stay compared. Adding authored data to these
  placeholders would need this boundary revisited.
- **Server-side comparison.** Commit `30466007` had switched this Application to client-side comparison
  (`ServerSideDiff=false`) without a recorded reason. Re-tested on 2026-10-14 with server-side diff after
  a769444a widened the ignores to whole maps: Synced, no resource out of sync. The annotation is `true` again,
  like every other Application.
- **Operator install.** Channel `preview-0.9`, `Automatic` approval, no `startingCSV`, checked by
  `check_operator_policy` before the first write. The first install (2026-10-06) used a manually approved
  InstallPlan for `agent-sandbox-operator.v0.9.0`; that InstallPlan is still listed as `Manual`, approved.
- **Gateway configuration.** Non-default values are in [`chart/values.yaml`](chart/values.yaml) and the post-render
  patches: StatefulSet with SQLite, `fsGroup`/`runAsUser` removed so `restricted-v2` assigns them, telemetry off,
  OIDC audience `openshell-gateway`, roles claim `realm_access.roles`, admin role `openshell-platform-admin`, user role
  `openshell-user`, unauthenticated users off, JWT Secret mode `0440`, `workspaceMode: operator` with the namespace
  label allowlist, chart preflight off (Helm cannot discover APIs offline; the runtime setup step checks them instead),
  Route and GRPCRoute off. Details and the PKI lifecycle: [`chart/README.md`](chart/README.md).
- **MaaS subscriptions.** Each agent has its own Qwen 3.8-only subscription. Priority is higher than the personal
  defaults; the setup helpers name the subscription when they create a key, which bypasses priority selection [11].
- **Secrets.** No credential is in Git. KEK and issuer come from the runtime setup step of `stages/060-agent-runtime-and-agentops/deploy.sh`; PKI from certgen; MaaS keys and
  agent listener credentials from the retired OpenCode/Hermes setup helpers, held as gateway provider credentials.
- **Cluster-specific values.** Issuer host (from the Keycloak Route) and the MaaS host in the sandbox policy are
  rendered at run time; no hostname is committed.

## Validation

There is no read-only validator for this component; `validate.sh` deliberately reports the stage as pending.
`deploy.sh --component 060-openshell-runtime` ends with `stage-apps.sh wait` (Synced and Healthy at the SHA) and then checks the `ai-agents`
workspace and its `ai-admin` membership. By hand:

```bash
oc get application 060-openshell-runtime -n openshift-gitops \
  -o jsonpath='{.spec.source.targetRevision} {.status.sync.status} {.status.health.status}{"\n"}'
oc get configmap openshell-runtime-ready -n openshell \
  -o jsonpath='{.data.controller-ready} {.data.source-revision}{"\n"}'
oc get statefulset openshell -n openshell; oc get csv -n agent-sandbox-system | grep agent-sandbox
```

`source-revision` must equal `targetRevision`.

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Support level | OpenShell sandboxing is Developer Preview, upstream artifacts, not for production [1] | Stage README states Developer Preview | Aligned |
| OpenShell version | Release notes point to the agent-ops guide (chart 0.0.116, ODH images) [1], [6] | Pinned upstream dev build `0.1.3-dev.99` (`12cec59bf`), images by digest | Deviation (justified: earlier tuple failed the OpenCode HTTP path; pins in `chart/source-pins.json`) |
| Authentication | Guide enables unauthenticated users and warns against it on shared clusters [6] | OIDC required | Deviation (justified: stricter) |
| Pod security | Guide grants `privileged` SCC [6] | `restricted-v2` (drop ALL, RuntimeDefault, namespace UID range) [9] | Deviation (justified: stricter, host qualification recorded) |
| Agent Sandbox operator | Downstream of `kubernetes-sigs/agent-sandbox`; OpenShell delegates pod management to it [5] | Installed from `redhat-operators`, channel `preview-0.9` | Aligned |
| Operator namespace | Guide installs in `openshift-operators` [6] | Own namespace `agent-sandbox-system`, AllNamespaces OperatorGroup | Deviation (justified: isolated ownership and NetworkPolicy) |
| Install approval | OLM Automatic or Manual approval strategy [12] | Automatic, repository policy for fresh installs | Aligned |
| Dashboard listing | Dashboard lists OpenShell-managed `Sandbox` CRs [1] | Sandboxes in `ai-agents`, visible to `rhods-admins` | Aligned |
| OpenCode | OpenCode deployment is Technology Preview with MLflow tracing [2] | Built image 1.18.16, Qwen 3.8 via MaaS, selected-call MLflow traces | Aligned (own build, not the Red Hat-provided image) |
| MLflow authorization | `experiments` pseudo-resource in `mlflow.kubeflow.org` covers runs and traces [3] | Project-wide Role for `ai-admin` in `ai-agents` | Aligned |
| MaaS access | Subscriptions grant per-model token limits; explicit subscription bypasses priority [11] | One subscription per agent, Qwen 3.8 only | Aligned |
| Delegated fields | `RespectIgnoreDifferences` applies ignores during sync [8] | Used for the three runtime-owned data maps | Aligned |
| Diff strategy | Server-side diff is opt-in per Application or global [10] | `ServerSideDiff=true` | Aligned (re-tested 2026-10-14) |
| Validation | n/a | No read-only component validator | Gap |

## References

1. Red Hat OpenShift AI Self-Managed 3.5, Release notes, "Developer Preview features". https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes
2. Red Hat OpenShift AI Self-Managed 3.5, Release notes, "Technology Preview features" (OpenCode coding agent deployment and operation). https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/technology-preview-features_relnotes
3. Red Hat OpenShift AI Self-Managed 3.5, Working with MLflow, "RBAC model for MLflow API usage". https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_mlflow/installing-mlflow_mlflow#rbac-model-api-usage_mlflow
4. NVIDIA OpenShell at commit `12cec59bf` (upstream). https://github.com/NVIDIA/OpenShell/tree/12cec59bf4c36c305032143eb90870bd16d8820b
5. Red Hat Developer, "Red Hat build of Agent Sandbox: isolated workload management for Kubernetes" (2026-07-15). https://developers.redhat.com/articles/2026/07/15/red-hat-build-agent-sandbox-isolated-workload-management-kubernetes
6. opendatahub-io/agent-ops, "Getting started with OpenShell on OpenShift" (pinned commit) (upstream). https://github.com/opendatahub-io/agent-ops/blob/7230605c8c0a4cec41c3e39e52e521db5c941355/guides/getting-started-openshell-openshift.md
7. Argo CD, "Diffing customization" (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/diffing/
8. Argo CD, "Sync Options" (RespectIgnoreDifferences, Prune=false, Delete=false, SkipDryRunOnMissingResource) (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/
9. OpenShift Container Platform 4.22, Authentication and authorization, "Managing security context constraints". https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/authentication_and_authorization/managing-pod-security-policies
10. Argo CD, "Diff Strategies" (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/diff-strategies/
11. Red Hat OpenShift AI Self-Managed 3.5, Govern LLM access with Models-as-a-Service, "Models-as-a-Service subscriptions". https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/govern_llm_access_with_models-as-a-service/deploy-and-manage-models-as-a-service
12. OpenShift Container Platform 4.22, Operators, "Administrator tasks" (approval strategy). https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/operators/administrator-tasks
13. Argo CD, "Sync Phases and Waves" (hooks and delete policies) (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
14. OpenShift Container Platform 4.22, Builds using BuildConfig, "Creating build inputs" (binary source). https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/builds_using_buildconfig/creating-build-inputs
