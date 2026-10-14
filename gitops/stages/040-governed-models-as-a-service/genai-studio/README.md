# Gen AI Studio (`040-genai-studio`)

This Application prepares the Gen AI playground (Gen AI studio) for the demo project **AI Coding Sandbox**
(`demo-sandbox`) and publishes platform MCP servers to every playground. It provisions a playground custom endpoint for
GPT-6 Luna, a saved agent "OpenShift Ops Assistant" with its reviewed system prompt in the MLflow prompt registry, a
retained state PVC, and the cluster-wide MCP server discovery ConfigMap. Users create the playground itself from the
dashboard.

| | |
|---|---|
| Argo CD Application | `040-genai-studio` ([manifest](../../../argocd/app-of-apps/040-governed-models-as-a-service/genai-studio.yaml)) |
| Deployed by | `stages/040-governed-models-as-a-service/deploy.sh` (deploy-order 7); `deploy.sh` then runs `publish-catalog-mcp.py` for the two MCP entries |
| Validated by | `stages/040-governed-models-as-a-service/validate.sh --readiness` (`validate-native.py` runs `publish-catalog-mcp.py --validate` for `OpenShift-MCP` and `OpenShift-MCP-ReadWrite`, deferring while the Stage 060 MCP runtime is absent; `stage_apps.py status` for Synced/Healthy); `qualify-catalog-mcp.py` (model-free MCP qualification, run by hand) |
| Sync | Automated, `prune` and `selfHeal`. Sync options `CreateNamespace`, `SkipDryRunOnMissingResource`, `RespectIgnoreDifferences` (and a `ServerSideDiff=true` sync option that has no effect). Compare option `ServerSideDiff=true` (annotation). `ignoreDifferences` on ConfigMap `redhat-ods-applications/gen-ai-aa-mcp-servers`: `/data/OpenShift-MCP` and `/data/OpenShift-MCP-ReadWrite` |
| Depends on | Stage 010 (namespace `demo-sandbox`, OpenShift AI with MLflow), `040-maas-platform` (MaaS API; its `enable-maas` Job enables the OGX component and the dashboard flags `genAiStudio`, `aiAssetCustomEndpoints`, `agentConfigManagement`, `promptManagement`, and declares the cluster ingress domain internal for custom endpoints), `040-gateway-governance` (Gateway `maas-default-gateway` listener `api`), `040-model-access` (subscription `playground-sandbox`), `040-local-models` (`qwen3-8-27b` for the agent), `040-external-models` (`gpt-6-luna`), Stage 060 `agent-tools` (MCP servers `openshift-mcp-server`, `openshift-mcp-server-rw`) |
| Used by | Playground users in `demo-sandbox`; every playground (MCP list from `gen-ai-aa-mcp-servers`); Stage 050 helpers that import `studio-api.py` |

## Why

The Gen AI playground lets users test governed model endpoints, prompts, MCP tools and saved agents without deploying
anything [1]. It is a Technology Preview feature [1][2]. The demo pre-provisions the parts that a platform team owns:
the MCP servers every playground may connect to (a ConfigMap in `redhat-ods-applications` [1, section 2.1]), a reviewed
agent, and a workaround endpoint for a model that the 3.5.1 playground cannot call on its normal MaaS path. One
Application holds them because they all change with the playground experience and none of them affects model serving.

## What

### Playground custom endpoint for GPT-6 Luna (workaround)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServiceAccount | `playground-maas-key-provisioner` | `demo-sandbox` | Owner of subscription `playground-sandbox`; mints its MaaS key. Wave 18 |
| Role + RoleBinding | `playground-endpoint-provisioner` | `demo-sandbox` | `create/get/patch/update` on Secrets and ConfigMaps in `demo-sandbox`. Wave 18 |
| Role + RoleBinding | `playground-endpoint-provisioner-gateway-reader` | `openshift-ingress` | `get` on Gateway `maas-default-gateway` only (reads the `api` hostname). Wave 18 |
| Job (Sync hook) | `provision-playground-endpoint` | `demo-sandbox` | Mints or keeps the MaaS key, writes Secret `endpoint-api-key-gpt-6-luna-maas` and ConfigMap `gen-ai-aa-custom-model-endpoints`. Wave 20, `hook-delete-policy: BeforeHookCreation,HookSucceeded` |

### Saved agent "OpenShift Ops Assistant"

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ConfigMap | `openshift-ops-assistant-prompt` | `demo-sandbox` | Reviewed system prompt (`template.md`) and the registration script (`provision.py`). Wave 18 |
| ServiceAccount + Role + RoleBinding | `agent-prompt-provisioner` | `demo-sandbox` | `get/list/create/update` on `mlflow.kubeflow.org` `registeredmodels` (the MLflow permission check for prompts), nothing else. Wave 18 |
| Job (Sync hook) | `agent-prompt-provisioner` | `demo-sandbox` | Registers the prompt in the project's MLflow prompt registry when the template changed. Pinned `odh-pipeline-runtime-datascience-cpu-py312-rhel9` image digest, non-root, `RuntimeDefault` seccomp, all capabilities dropped. Wave 20, `BeforeHookCreation,HookSucceeded` |
| ConfigMap | `agent-profile-e0e610ff-3438-5d81-a3c7-eeb3e20a9ff8` | `demo-sandbox` | `AgentProfile` (labels `opendatahub.io/dashboard`, `opendatahub.io/agent-profile`): model `publishers/internal-models/models/qwen3-8-27b` through MaaS, prompt `openshift-ops-assistant` from MLflow, temperature 0.2, 2,048 output tokens, MCP server `OpenShift-MCP` limited to `resources_list`, `resources_get`, `pods_list_in_namespace`, `pods_get`, `events_list`. The name is a uuid5 of a fixed string. Wave 21 |

### Playground state

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| PersistentVolumeClaim | `genai-playground-state` | `demo-sandbox` | 1 Gi RWO volume for the playground's SQLite state. `studio-api.py` mounts it into a newly created playground (`OGXServer` workload override). Wave 8, `Prune=false,Delete=false` |

### MCP server discovery (`mcp/`)

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ConfigMap | `gen-ai-aa-mcp-servers` | `redhat-ods-applications` | MCP servers listed in every playground and under AI asset endpoints. Git owns the object with empty `data`; the keys are delegated. Wave 19 |

### Objects not in Git

| Object | Owner |
|---|---|
| Keys `OpenShift-MCP` and `OpenShift-MCP-ReadWrite` in `gen-ai-aa-mcp-servers` | `stages/040-governed-models-as-a-service/publish-catalog-mcp.py` (from the Stage 060 MCP servers), preserved by `ignoreDifferences` |
| Secret `endpoint-api-key-gpt-6-luna-maas` (keys `api_key`, `key_id`, `expires_at`, `subscription`) | Job `provision-playground-endpoint` |
| ConfigMap `gen-ai-aa-custom-model-endpoints` | Job `provision-playground-endpoint` creates it when absent; users may extend it from the dashboard |
| MLflow prompt `openshift-ops-assistant` and its versions | Job `agent-prompt-provisioner` |
| Playground `OGXServer` `lsd-genai-playground`, its pgvector database and service account | Dashboard and OpenShift AI (created when a user creates the playground) |

## How

**Ordering.** Application wave 4, deploy-order 7 (after model access). Inside it: PVC (8), ServiceAccounts, RBAC and the
prompt ConfigMap (18), MCP ConfigMap (19), the two Sync-hook Jobs (20), the agent profile (21). Sync hooks run with the
manifests of a sync, and the delete policies remove a finished Job and replace an old one [5]. Because automated syncs
that skip hooks would not rerun the Jobs, `deploy.sh` runs one native hook sync per component that has not completed a
sync at the deployed revision.

**Workaround: GPT-6 Luna custom endpoint.** GPT-6 Luna rejects `max_tokens` and any temperature other than 1. In 3.5.1
the playground's MaaS provider path sends a provider-level `max_tokens` (RHOAIENG-90257, fixed upstream, not in 3.5.1).
Custom endpoints [1, chapters 4-5] carry no such default. The Job:
1. reads the Gateway `api` hostname and fails if it is a placeholder;
2. keeps the stored key while `GET /maas-api/v1/api-keys/{id}` reports it `active` for `playground-sandbox`; otherwise it
   revokes the old key and mints a new one as the ServiceAccount (key lifetime is the 90-day maximum [3], so a sync after
   expiry renews it);
3. writes the key to the Secret with `oc apply` from a private temp file, never to logs or arguments;
4. creates `gen-ai-aa-custom-model-endpoints` with a `remote::openai` provider on `https://maas.<cluster-domain>/v1`,
   model `gpt-6-luna`, display name "GPT-6 Luna (Playground)". If the ConfigMap exists, it only reconciles its own
   entry's display name; a ConfigMap that users extended without this entry is left untouched with a warning.

The `aiAssetCustomEndpoints` flag and the internal cluster domain (`genAiStudioConfig.aiAssetCustomEndpoints.clusterDomains`, with `externalProviders: false`) are set by the `040-maas-platform` Job [1, chapter 4]. The
`gen-ai-aa-custom-model-endpoints` format is the dashboard backend's internal format; the product docs describe the
feature flags and the UI, not this ConfigMap. Users add the endpoint model to the playground and set Temperature to 1.
Remove this workaround when the RHOAIENG-90257 fix ships.

**Prompt registration.** The Job uses MLflow SDK 3.14 with `MLFLOW_TRACKING_AUTH=kubernetes-namespaced`: inside the
cluster the plugin uses the mounted ServiceAccount token and namespace [4]. `MLFLOW_WORKSPACE=demo-sandbox` and the
service CA bundle are set explicitly. `provision.py` registers a new version only when the template differs from the
latest version. The agent profile references the prompt by name and loads its latest version, so a template change in
Git reaches the agent on the next sync.

**Saved agent.** Saved playground agents are a Developer Preview feature [1, chapter 15]. The profile restricts tools
with `allowedTools`; the read-only MCP server additionally acts as its own bounded ServiceAccount (Stage 060), which
cannot read Secrets or write.

**MCP discovery and delegated fields.** The product reads MCP servers from ConfigMap `gen-ai-aa-mcp-servers` in
`redhat-ods-applications`; each key is a case-sensitive unique name with a JSON value holding `url` and `description`
[1, section 2.1]. Git creates the empty object; `publish-catalog-mcp.py` writes each key from the endpoint the Stage 060
lifecycle operator reports (in-cluster service address for the token-less read-only server, HTTPS Route for the
read-write server). `ignoreDifferences` on exactly those two JSON pointers with `RespectIgnoreDifferences=true` keeps
Argo CD from removing them [6][7]. `publish-catalog-mcp.py` refuses to write unless this Application is Synced and Healthy
at the expected revision, and needs `--replace` to change a published value.

**Retained state PVC.** `Prune=false,Delete=false` keeps playground history when the Application or object is removed
[6]. `studio-api.py` attaches it only to a freshly created playground; moving existing state needs the backup and
restore procedure in `docs/OPERATIONS.md`.

**Secrets.** No secret values in Git. The only Secret is the endpoint key, minted at runtime.

**Cluster-specific values.** The MaaS hostname is read from the Gateway at Job run time; the MCP endpoints are read from
the Stage 060 objects at publication time.

## Validation

`validate.sh --readiness` requires this Application to be Synced and Healthy at the deployed revision and runs
`publish-catalog-mcp.py --validate` for both MCP keys (it passes with an explicit deferral while the Stage 060 MCP
runtime is absent). It does not check the endpoint Secret, the custom endpoint ConfigMap, the MLflow prompt or the agent
profile; playground use is a user acceptance step. `qualify-catalog-mcp.py` checks MCP session status, tool lists and
caller permissions without a model.

By hand (read-only; do not print the Secret):

```bash
oc get configmap gen-ai-aa-mcp-servers -n redhat-ods-applications -o jsonpath='{.data}' | python3 -c 'import json,sys; print(sorted(json.load(sys.stdin)))'
oc get configmap gen-ai-aa-custom-model-endpoints,agent-profile-e0e610ff-3438-5d81-a3c7-eeb3e20a9ff8 -n demo-sandbox
```

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| MCP servers | ConfigMap `gen-ai-aa-mcp-servers` in `redhat-ods-applications`, one JSON entry per unique key [1, section 2.1] | Same object; keys published by script and delegated | Aligned |
| Custom endpoints | Enabled with `aiAssetCustomEndpoints`; credential stored as a project Secret; created in the UI [1, chapters 4-5] | Created by a Job writing the backend ConfigMap and Secret | Deviation (justified: GitOps pre-provisioning of the RHOAIENG-90257 workaround; depends on an undocumented internal format) |
| Saved agents | Developer Preview [1, chapter 15] | One agent provisioned from Git | Aligned (demo use only) |
| Prompt registry | Saved prompts are stored in MLflow [1, chapter 13]; SDK `kubernetes-namespaced` auth with the pod's ServiceAccount [4] | Job registers the prompt with that auth | Aligned |
| Support status | Gen AI playground is Technology Preview [1][2] | Demo use | Aligned |
| Job image | Pinned images | Prompt Job pinned by digest; endpoint Job uses `registry.redhat.io/openshift4/ose-cli` without tag or digest | Gap (endpoint Job image floats) |
| TLS | Verify server certificates | Endpoint Job calls the MaaS API with `curl -k` | Gap (TLS verification disabled when sending the ServiceAccount token) |
| Pod security | Restricted profile | Prompt Job sets non-root, seccomp, drop ALL; endpoint Job sets no security context or resources | Gap (endpoint Job relies on SCC defaults) |
| Hook lifecycle | `BeforeHookCreation`, `HookSucceeded` delete policies [5] | Both Jobs | Aligned |

## References

1. Experimenting with models in the Gen AI playground, Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/experimenting_with_models_in_the_gen_ai_playground/index
2. Release notes, "Technology Preview features", Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/technology-preview-features_relnotes
3. Govern LLM access with Models-as-a-Service, "Deploy and manage Models-as-a-Service" (API key expiration), Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/govern_llm_access_with_models-as-a-service/deploy-and-manage-models-as-a-service
4. Working with MLflow, "Install and authenticate the MLflow SDK", Red Hat OpenShift AI Self-Managed 3.5. https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/working_with_mlflow/installing-and-authenticating-mlflow-sdk_mlflow
5. Argo CD, "Sync Phases and Waves" (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
6. Argo CD, "Sync Options" (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-options/
7. Argo CD, "Diffing Customization" (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/diffing/
