# Operations Guide

This document explains how to deploy, validate, and operate the workshop environment. The README files teach the architecture and product story; this guide is the operational companion for people running the demo.

The executable source of truth remains the scripts:

- `scripts/bootstrap.sh`
- `stages/NNN-*/deploy.sh`
- `stages/NNN-*/validate.sh`

Use this guide to understand when to run those scripts, what they do, and how to interpret the results.

## Operating Model

The repository follows a GitOps-first pattern:

1. `scripts/bootstrap.sh` installs and configures OpenShift GitOps.
2. Each stage `deploy.sh` applies one Argo CD `Application`.
3. Argo CD reconciles manifests from `gitops/stages/NNN-*/base`.
4. Sync waves and in-cluster Jobs perform cluster-specific setup.
5. Each `validate.sh` confirms that the stage reached the expected operational state.

The deploy scripts do not imperatively install every component themselves. They hand ownership to Argo CD.

## Prerequisites

Before deploying the workshop, confirm:

- You are logged into the target OpenShift cluster with sufficient privileges.
- The cluster has enough capacity for GPU nodes and model-serving workloads.
- `oc`, `git`, `bash`, `curl`, and `jq` are available locally.
- You are using the intended branch and remote for the GitOps source.
- `env.example` has been copied to `.env` and configured with required credentials.
- `OPENAI_API_KEY` is set in `.env` if external model inference (gpt-4o, gpt-4o-mini) will be exercised.
- Optional: `SLACK_BOT_TOKEN` and/or `BRIGHTDATA_API_TOKEN` in `.env` if those MCP servers are needed.

Recommended checks:

```bash
oc whoami
oc whoami --show-server
git remote -v
git status --short
```

MCP integrations have their own prerequisites. Stage 060 includes the read-only OpenShift MCP server (uses ServiceAccount RBAC, no token needed). Slack and BrightData are credential-gated integrations. Set `SLACK_BOT_TOKEN` and `BRIGHTDATA_API_TOKEN` in `.env` when those integrations are approved; missing credentials produce validation warnings, not failures.

## Bootstrap

Run bootstrap once per cluster:

```bash
cp env.example .env
oc login --token=<token> --server=<api>
./scripts/bootstrap.sh
```

`bootstrap.sh` performs these actions:

- Auto-detects the Git remote and updates Argo CD Applications for forks.
- Installs the OpenShift GitOps operator.
- Grants the Argo CD application controller cluster-admin permissions for the demo.
- Sets Argo CD resource tracking to `annotation`.
- Configures custom health checks for resources such as PVCs and InferenceServices.
- Creates the `rhoai-demo` Argo CD project.

This broad GitOps control is intentional for disposable demo clusters because the stages create cluster-scoped operators, CRDs, RBAC, Gateway API resources, and OpenShift platform configuration. Do not treat the bootstrap RBAC and wildcard AppProject as a production recommendation. For a shared or long-lived environment, scope Argo CD permissions, destinations, source repositories, and cluster resource allow-lists to the smallest workable set.

Operator Subscriptions use `installPlanApproval: Automatic` so a disposable demo cluster can reconcile without manual OLM approval steps. This is a repeatability choice for the workshop, not a blanket recommendation for production change control.

Monitor GitOps:

```bash
oc get pods -n openshift-gitops
oc get route openshift-gitops-server -n openshift-gitops
```

## Deployment Order

Deploy stages in order:

```bash
./stages/010-openshift-ai-platform-foundation/deploy.sh
./stages/020-gpu-infrastructure-private-ai/deploy.sh
./stages/030-private-model-serving/deploy.sh
./stages/040-governed-models-as-a-service/deploy.sh
./stages/050-approved-external-model-access/deploy.sh
./stages/060-mcp-context-integrations/deploy.sh
./stages/070-controlled-developer-workspaces/deploy.sh
./stages/080-ai-assisted-application-modernization/deploy.sh
./stages/090-developer-portal-self-service/deploy.sh
```

Each script applies one file from `gitops/argocd/app-of-apps/`. The ordered source of truth is `demo/flows/default.yaml`.

Compatibility note: the old `steps/step-*` scripts remain as wrappers, but the old `step-*` Argo CD Applications should not be run alongside the new stage Applications on the same cluster. For an existing cluster that already has the old six applications, use a clean redeploy or remove the old Applications before adopting the staged flow so Argo CD ownership does not overlap.

| Stage | Argo CD app | Purpose |
|------|-------------|---------|
| 010 | `010-openshift-ai-platform-foundation` | OpenShift AI platform foundation |
| 020 | `020-gpu-infrastructure-private-ai` | NFD, GPU Operator, GPU MachineSets, Red Hat build of Kueue, queue quota, KEDA readiness |
| 030 | `030-private-model-serving` | Local private model serving |
| 040 | `040-governed-models-as-a-service` | MaaS control plane, gateway, governance, observability |
| 050 | `050-approved-external-model-access` | External OpenAI models behind MaaS |
| 060 | `060-mcp-context-integrations` | OpenShift, Slack, and BrightData MCP integrations |
| 070 | `070-controlled-developer-workspaces` | Red Hat OpenShift Dev Spaces, workspaces, AI coding tools |
| 080 | `080-ai-assisted-application-modernization` | MTA, Red Hat Developer Lightspeed for MTA, MaaS integration |
| 090 | `090-developer-portal-self-service` | Red Hat Developer Hub portal |

## Validation Strategy

Run static flow validation before cluster work:

```bash
./scripts/validate-stage-flow.sh
```

Run the matching validation script after each stage:

```bash
./stages/040-governed-models-as-a-service/validate.sh
```

Validation scripts use these exit codes:

| Exit code | Meaning |
|-----------|---------|
| `0` | All checks passed |
| `1` | One or more critical failures |
| `2` | Warnings only |

Warnings are acceptable only when the script clearly explains that the condition is temporary or expected. For a polished demo, aim for zero warnings.

Check all Argo CD apps:

```bash
oc get applications -n openshift-gitops \
  -o custom-columns='APP:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status'
```

## Argo CD Operations

Inspect an application:

```bash
oc get application 040-governed-models-as-a-service -n openshift-gitops -o yaml
```

List resources managed by an application:

```bash
oc get application 040-governed-models-as-a-service -n openshift-gitops -o json \
  | jq -r '.status.resources[]? | [.kind,.namespace,.name,.status,.health.status] | @tsv'
```

Force a sync from the CLI if needed:

```bash
argocd app sync 040-governed-models-as-a-service
```

If the `argocd` CLI is unavailable, use the OpenShift GitOps UI or wait for automated sync. Most applications have automated sync enabled.

## Stage-Specific Operational Notes

### Stage 010

Stage 010 installs OpenShift AI and platform dependencies. Operator reconciliation can take several minutes.

Useful checks:

```bash
oc get datasciencecluster default-dsc -o yaml
oc get pods -n redhat-ods-applications
oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o yaml
```

## Live Validation Log

This section records the current validation run against the disposable demo environment.

### 2026-05-01 validation run

Cluster:

- Console: `https://console-openshift-console.apps.cluster-t977r.t977r.sandbox3022.opentlc.com`
- API: `https://api.cluster-t977r.t977r.sandbox3022.opentlc.com:6443`
- OpenShift: `4.20.19`
- Kubernetes: `v1.33.9`
- Git branch used by Argo CD: `main`
- Latest full stage validation code commit: `b5bb770`
- Initial Argo CD source commit after repointing to `main`: `ec2b4c1`

Preflight:

- `./scripts/validate-stage-flow.sh` passed.
- `bash -n scripts/*.sh stages/*/*.sh steps/step-*/*.sh` passed.
- `git diff --check` passed.
- Cluster operators were Available and not Progressing or Degraded before bootstrap.
- Default StorageClass was `gp3-csi`.
- No GPU nodes were present before Stage 020.

Bootstrap:

- `./scripts/bootstrap.sh` completed.
- OpenShift GitOps operator Subscription was created.
- Demo `openshift-gitops-cluster-admin` ClusterRoleBinding was created.
- Argo CD resource tracking was set to `annotation`.
- Custom health checks were configured for Subscription, PVC, InferenceService, and TrustyAIService.
- AppProject `rhoai-demo` was created.
- Argo CD route: `openshift-gitops-server-openshift-gitops.apps.cluster-t977r.t977r.sandbox3022.opentlc.com`

Stage results:

| Stage | Status | Evidence |
|------|--------|----------|
| 010 OpenShift AI Platform Foundation | Passed | `./stages/010-openshift-ai-platform-foundation/validate.sh`: 18 passed, 0 warnings, 0 failed |
| 020 GPU Infrastructure for Private AI | Passed | `./stages/020-gpu-infrastructure-private-ai/validate.sh`: 15 passed, 0 warnings, 0 failed |
| 030 Private Model Serving | Passed | `./stages/030-private-model-serving/validate.sh`: 19 passed, 0 warnings, 0 failed |
| 040 Governed Models-as-a-Service | Passed | `./stages/040-governed-models-as-a-service/validate.sh`: 38 passed, 0 warnings, 0 failed |
| 050 Approved External Model Access | Passed with expected warning | `./stages/050-approved-external-model-access/validate.sh`: 17 passed, 1 warning, 0 failed |
| 060 MCP Context Integrations | Passed with expected warnings | `./stages/060-mcp-context-integrations/validate.sh`: 14 passed, 2 warnings, 0 failed |
| 070 Controlled Developer Workspaces | Passed | `./stages/070-controlled-developer-workspaces/validate.sh`: 18 passed, 0 warnings, 0 failed |
| 080 AI-Assisted Application Modernization | Passed | `./stages/080-ai-assisted-application-modernization/validate.sh`: 22 passed, 0 warnings, 0 failed |
| 090 Developer Portal and Self-Service | Passed | `./stages/090-developer-portal-self-service/validate.sh`: 16 passed, 0 warnings, 0 failed |

Final sweep:

- All nine Argo CD Applications reported `Synced` and `Healthy` at commit `b5bb770`.
- A full live validation sweep from Stage 010 through Stage 090 completed without critical failures.
- Expected warnings remain for Stage 050 external inference because `OPENAI_API_KEY` was not set during the initial full sweep, and Stage 060 optional Slack/BrightData MCP runtimes because `SLACK_BOT_TOKEN` and `BRIGHTDATA_API_TOKEN` are not set. Later Stage 050 smoke validation passed after an approved provider key was provisioned.
- A GitOps hygiene sweep found no remaining Argo CD resources with `requiresPruning=true` after re-syncing Stage 090 hook resources.
- Merge-readiness static checks also passed: `git diff --check origin/main...HEAD`, `bash -n scripts/*.sh stages/*/*.sh steps/step-*/*.sh`, and `./scripts/validate-stage-flow.sh`.
- Merge-readiness security check found no committed `.env` file and no real kubeadmin password, provider key, kubeconfig, bearer token, or private key in the branch diff. Only placeholder and masked key examples such as `sk-oai-*` were present.
- After merging PR #1, all canonical stage Argo CD Applications were repointed from `codex/stage-refactor-demo-validation` to `main` and reported `Synced` and `Healthy` at commit `ec2b4c1`. Stage 090 was reconfigured so `RHDH_CATALOG_URL` resolves to the `main` catalog URL, then Stage 090 validation passed with 16 checks, 0 warnings, and 0 failures. Later docs-only commits may advance Argo CD's displayed revision without changing managed stage resources.

Validation hardening pass:

- Validators now check demo-owned outcomes in addition to service readiness: GPU node allocatable capacity and taints, local model metadata and registry entries, generated MaaS routes/policies/token limits, external model endpoint and credential wiring, MCP service discovery and credential gating, Dev Spaces RoleBindings, MTA ConsoleLink, and RHDH OIDC/catalog configuration.
- `scripts/validate-lib.sh` now handles zero matching pods without producing a malformed `0 0` count.
- Hook Jobs are treated as non-durable operational evidence. Stage 030 validates the durable model registry contents instead of failing when the `model-registry-seed` hook Job has already been cleaned up.

GitOps hygiene pass:

- Broad `ignoreDifferences` entries were reduced where they hid demo-owned desired state. Operator-generated and cluster-specific fields remain ignored only where they are not useful GitOps ownership points.
- Stage 020 now records GPU Operator and Node Feature Discovery defaults in Git so Argo CD can manage those specs without broad masking.
- Hook delete policies now include `HookSucceeded` for stage and compatibility manifests, which reduced stale hook resources and pruning noise.
- A regression was found while tightening Stage 040: the MaaS Gateway hostname and TLS certificate reference are intentionally patched from the cluster ingress domain and certificate. Removing the old broad Gateway spec ignore let Argo CD restore `maas.placeholder.example.com`, which caused the Stage 080 MTA MaaS hook to patch placeholder values into `Tackle` and `kai-api-keys`.
- Fix applied: Stage 040 and compatibility Step 03 now ignore only `/spec/listeners/0/hostname`, `/spec/listeners/1/hostname`, and `/spec/listeners/1/tls/certificateRefs/0/name` for `Gateway/maas-default-gateway`. The rest of the Gateway spec remains GitOps-managed.
- Fix applied: Stage 080 and compatibility Step 05 now fail fast if the discovered MaaS hostname still contains `placeholder`, preventing a bad hook run from overwriting runtime configuration with placeholder values.
- Final evidence after the fix: Stage 040 re-synced to the real `maas.apps.cluster-t977r.t977r.sandbox3022.opentlc.com` host, Stage 080 re-provisioned `kai-api-keys` with a real `sk-oai-*` MaaS key for `local-models-subscription`, and Stages 040, 080, and 090 validated successfully.

Red Hat alignment review:

- Stage 040 is aligned with the Red Hat OpenShift AI 3.4 MaaS architecture in the core platform pattern: KServe-backed model serving, Gateway API, Red Hat Connectivity Link, Kuadrant/Authorino policy enforcement, API-key authentication, tier-based access, rate limits, token limits, dashboard enablement, and GitOps-managed desired state. MaaS remains a Technology Preview capability in the referenced Red Hat OpenShift AI 3.4 documentation, so the demo must continue to describe it as an early-access showcase rather than a production baseline.
- Stage 040 deviations remain intentional and documented: upstream MaaS controller/`maas-api` image override for external model registration, tokens bridge for the Playground token endpoint, gateway/AuthPolicy patches, and community Grafana for demo observability. These are acceptable for the disposable environment but not Red Hat-supported production implementation guidance.
- Stage 080 aligns with Red Hat Developer Lightspeed for MTA guidance by using a centrally managed LLM provider configuration through MTA, the LLM proxy, and an OpenAI-compatible endpoint backed by Red Hat OpenShift AI/MaaS. Developer Lightspeed for MTA is also Technology Preview in the referenced MTA 8.1 documentation, so production-readiness language must stay conservative.
- Stage 090 aligns with Red Hat Developer Hub 1.9 operator guidance by using the `Backstage` custom resource, app config mounted from a ConfigMap, environment-substituted secrets, and `dynamic-plugins.yaml` mounted through `dynamicPluginsConfigMapName`.
- Fix applied from the alignment review: RHDH catalog configuration no longer hard-codes the `main` branch. `app-config-rhdh.yaml` now uses `${RHDH_CATALOG_URL}`, and the Stage 090 PostSync hook derives that URL from the live Argo CD Application `repoURL` and `targetRevision`. This keeps the developer portal catalog on the same Git revision as the deployed demo.
- Final evidence after the alignment fix: Stage 090 re-synced to commit `cff7e4a`; `RHDH_CATALOG_URL` resolved to `https://raw.githubusercontent.com/adnan-drina/rhoai3-coding-demo/codex/stage-refactor-demo-validation/gitops/stages/090-developer-portal-self-service/base/catalog/all.yaml`; Stage 090 validation passed with 16 checks, 0 warnings, and 0 failures; all nine Argo CD Applications reported `Synced` and `Healthy`.

Documentation and deviation-register cleanup:

- `BACKLOG.md` now treats workaround removal as a supported-capability review, not as an automatic Red Hat OpenShift AI 3.4 GA cleanup. This matches the current Red Hat OpenShift AI 3.4 documentation posture where MaaS is Technology Preview.
- Current validation wording now distinguishes external model registration from external inference. Stage 050 registers `gpt-4o` and `gpt-4o-mini` without requiring provider token spend; external inference is credential-gated and has been validated with an approved `OPENAI_API_KEY` by using the opt-in smoke test.
- Stage 040, Stage 080, and Stage 090 READMEs now call out Red Hat alignment, Technology Preview posture, and demo-specific deviations close to the affected implementation.
- `docs/TROUBLESHOOTING.md` now includes `RHDH_CATALOG_URL` diagnostics for Developer Hub catalog failures.

Stage 010 findings:

- Automated sync initially stalled after bootstrap while waiting on `ClusterRole/job-approve-sm-installplan` and `ClusterRole/job-patch-dsci-ca`, even though both resources existed. Manual `argocd app sync 010-openshift-ai-platform-foundation` advanced the operation and completed successfully. Improvement candidate: add a bootstrap readiness wait for the Argo CD application-controller cache before applying the first stage, and document `argocd app sync` as the recovery command for this startup race.
- Validation found `OdhDashboardConfig.spec.dashboardConfig.genAiStudio` absent. Root cause: the Stage 010 Application ignored the entire `OdhDashboardConfig.spec` while `RespectIgnoreDifferences=true`, so Argo CD reported the resource synced without enforcing the MaaS-required dashboard flags. Fix applied in commit `8e4ce3d`: stop ignoring `OdhDashboardConfig.spec`; keep operator-managed drift ignores only where they do not hide required demo configuration.
- After the fix, Stage 010 re-synced to commit `8e4ce3d` and validation passed with 11 checks, 0 warnings, and 0 failures.
- Follow-up identity finding: `demo-htpasswd` and the `rhoai-admins` / `rhoai-users` groups were present, but `OAuth/cluster` still had `spec: {}`. Root cause: the Stage 010 Application ignored the entire `OAuth.spec` while `RespectIgnoreDifferences=true`, so Argo CD applied the OAuth singleton without the `demo-htpasswd` identity provider and still reported `Synced` and `Healthy`.
- Fix applied during validation: stop ignoring `OAuth.spec` for Stage 010, re-sync the Stage 010 Application, and add explicit validation for the demo HTPasswd Secret, OAuth identity provider, RHOAI groups, and demo persona login lifecycle. `ai-admin` and `ai-developer` OpenShift `User` records are created only after first successful login; validating the OAuth identity provider and group membership is the durable deployment check.
- Final evidence for Stage 010 after the identity fix: `OAuth/cluster` includes the `demo-htpasswd` HTPasswd identity provider, the `demo-htpasswd` Secret exists in `openshift-config`, `rhoai-admins` includes `ai-admin`, `rhoai-users` includes `ai-admin` and `ai-developer`, both demo users can log in with the demo password, and validation passed with 18 checks, 0 warnings, and 0 failures.

Stage 020 findings:

- The GPU MachineSet hook created MachineSet `cluster-t977r-vs62m-g6e-us-east-2c` with two `g6e.2xlarge` Machines. The Machines became Running and the nodes registered Ready.
- The initial hook patched the MachineSet template after creating the MachineSet. The first Machines could be created before that patch was observed, so the live GPU nodes had `nvidia.com/gpu.present=true` but did not have `node-role.kubernetes.io/gpu` or the `nvidia.com/gpu=true:NoSchedule` taint.
- Improvement being applied: make the MachineSet hook idempotent. It should always repair the MachineSet template and also label/taint already-created live nodes selected by `node.kubernetes.io/instance-type`.
- Follow-up RBAC finding: the repair logic also needs narrow Node `get`, `list`, and `patch` permissions. Without those verbs the hook can repair the MachineSet template but cannot repair already-created Nodes.
- Follow-up command finding: `oc get nodes -o name` returns `node/<name>`, which works for `oc label` but not for `oc adm taint` in this script. Use bare node names from JSONPath and pass `oc label node "$NODE"` / `oc adm taint node "$NODE"` explicitly.
- Fix applied through commits `52bead9`, `e144001`, and `9e72be4`. Stage 020 re-synced successfully.
- Final evidence: MachineSet `cluster-t977r-vs62m-g6e-us-east-2c` created two `g6e.2xlarge` nodes. Both nodes were Ready, labeled `node-role.kubernetes.io/gpu`, tainted `nvidia.com/gpu=true:NoSchedule`, labeled `nvidia.com/gpu.present=true`, and advertised `nvidia.com/gpu: 1` allocatable. NVIDIA `ClusterPolicy` state was `ready`.

Stage 030 findings:

- The model registry deployment was healthy, but the `model-registry-seed` hook could not reach `demo-registry.rhoai-model-registries.svc:8080`.
- Root cause: Stage 010 created a NetworkPolicy for the model registry that allowed dashboard traffic from `redhat-ods-applications`, but did not allow the Stage 030 seed Job running in `rhoai-model-registries`.
- Improvement being applied: add a narrow Stage 030 NetworkPolicy that permits only pods labeled `app=model-registry-seed` to connect to the model registry API on port 8080.
- The `LLMInferenceService` resources were created and scheduled on GPU nodes. They currently report `HTTPRouteReconcileError` until Stage 040 installs Red Hat Connectivity Link and the `AuthPolicy` CRD. Stage 030 validation treats model readiness as a warning because gateway governance is introduced in Stage 040.
- Fix applied in commit `1042add`. Stage 030 re-synced successfully, and the `model-registry-seed` hook completed.
- Final evidence for Stage 030: `gpt-oss-20b` and `nemotron-3-nano-30b-a3b` were registered in the model registry. Both model pods were scheduled on GPU nodes and were in init/model-pull startup. Both `LLMInferenceService` resources reported `HTTPRouteReconcileError` because `AuthPolicy` is introduced by Stage 040.
- After Stage 040 installed RHCL and refreshed KServe discovery, Stage 030 re-validation passed with both local `LLMInferenceService` resources ready.

Stage 040 findings:

- The first Stage 040 auto-sync stalled on `tenants.maas.opendatahub.io` even though the CRD existed. Manual hard refresh plus explicit `argocd app sync` advanced the operation. This is the same Argo CD startup/cache pattern seen in Stage 010.
- CloudNativePG generated install plan `install-kjljp` with `APPROVAL=Manual` and `APPROVED=false` even though the Subscription requested `installPlanApproval: Automatic`. Improvement being applied: add a narrow Stage 040 approval hook that only approves pending CloudNativePG install plans in `openshift-operators`.
- The first approval hook version used a later sync wave than the CloudNativePG Subscription, so Argo CD did not run it while the Subscription was still Progressing. The hook now runs in the same dependency wave as the Subscription, with RBAC created one wave earlier.
- The `configure-kuadrant` hook ran before the MaaS controller and generated AuthPolicy resources were created. Improvement being applied: move that hook after the MaaS API, gateway, and local MaaS resources, extend its deadline, and fail explicitly if required AuthPolicy resources are not created in time.
- The MaaS controller reported that `openshift-ingress/maas-default-gateway` was missing because Gateway resources were later than the controller and local MaaS resources. Improvement being applied: move `GatewayClass` and the default MaaS `Gateway` before the MaaS controller deployment, and move the Kuadrant patch hook after the gateway-dependent resources.
- MaaS generated the gateway policy as `gateway-default-auth`, not the older `gateway-auth-policy` name used by the earlier hook implementation. Improvement applied: patch `gateway-default-auth` and use a JSON patch to replace `maas-api-auth-policy` authorization with an explicit empty object.
- After the gateway and RHCL were healthy, the existing `LLMInferenceService` resources still reported the earlier AuthPolicy CRD discovery error. A controlled restart of `kserve-controller-manager` refreshed API discovery and immediately created the model HTTPRoutes. Improvement being applied: add a Stage 040 hook to restart KServe after RHCL/Gateway readiness in this staged demo flow.
- Follow-up GitOps hygiene finding: the MaaS Gateway listener hostnames and TLS certificate reference are cluster-specific values patched by `job-patch-gateway-hostname`. They must not be masked by a broad Gateway spec ignore, but they must be ignored narrowly so Argo CD does not restore placeholder values after the patch hook runs.
- Final evidence for Stage 040: CloudNativePG, Red Hat Connectivity Link, Kuadrant, MaaS API, local `MaaSModelRef` resources, local `MaaSAuthPolicy`, local `MaaSSubscription`, per-route AuthPolicies, and Grafana all validated successfully. Argo CD reports Stage 040 `Synced` and `Healthy`.

Stage 050 findings:

- Stage 050 registered the approved external model resources and, when an approved `OPENAI_API_KEY` was later supplied through `.env`, completed an opt-in external inference smoke test through MaaS.
- Final evidence for Stage 050: `ExternalModel` and `MaaSModelRef` resources for `gpt-4o` and `gpt-4o-mini` are registered and Ready. `external-models-access` and `external-models-subscription` are Active. Argo CD reports Stage 050 `Synced` and `Healthy`. The opt-in external smoke validation passed with 19 checks, 0 warnings, and 0 failures; a direct OpenAI-compatible call through MaaS to `gpt-4o-mini` returned HTTP `200` with non-empty assistant content.

Stage 060 findings:

- `SLACK_BOT_TOKEN` and `BRIGHTDATA_API_TOKEN` are not set in this demo environment. Slack and BrightData MCP discovery entries are present in the GenAI Playground ConfigMap, but their runtimes are disabled at zero replicas until credentials are approved and an enabling overlay is added.
- Initial Stage 060 sync showed that running optional MCP pods without credentials leaves Argo CD Progressing. Improvement applied: keep optional Slack and BrightData MCP deployments at zero replicas by default so missing optional credentials produce validation warnings instead of deployment failures.
- Final evidence for Stage 060: OpenShift MCP is running, OpenShift/Slack/BrightData MCP entries are registered in `gen-ai-aa-mcp-servers`, and Argo CD reports Stage 060 `Synced` and `Healthy`.

Stage 070 findings:

- Initial Stage 070 sync attempted to create the `CheCluster` before the Dev Spaces operator webhook service had endpoints, producing a transient `no endpoints available for service "devspaces-operator-service"` admission error. A manual hard refresh and sync succeeded after the operator and webhook pods became ready.
- Improvement applied: add a narrow Sync hook that waits for the `devspaces-operator` deployment rollout and `devspaces-operator-service` endpoints before Argo CD applies the `CheCluster`.
- Follow-up GitOps finding: `DevWorkspace` resources had `Replace=true`, which is incompatible with controller-assigned immutable DevWorkspace IDs on later syncs. Improvement applied: remove `Replace=true`, add a repair hook for stale live annotations from earlier revisions, and allow Argo CD to patch/observe the resources while continuing to ignore controller-managed `DevWorkspace.spec` drift.
- Final evidence for Stage 070: Dev Spaces operator CSV `devspacesoperator.v3.27.1` succeeded, `CheCluster` phase is `Active`, the Dev Spaces URL is `https://devspaces.apps.cluster-t977r.t977r.sandbox3022.opentlc.com`, and Argo CD reports Stage 070 `Synced` and `Healthy`.

Stage 080 findings:

- Initial Stage 080 sync applied the `Tackle` CR successfully, but the MaaS patch hook ran before MTA operator-owned resources such as `llm-proxy` and the MTA route existed. Improvement applied: the hook now waits for the generated route and `llm-proxy` deployment before patching the ConsoleLink and rolling the proxy.
- MaaS API keys created without an explicit subscription defaulted to `external-models-subscription`, which produced HTTP 403 for the local `nemotron-3-nano-30b-a3b` model. Improvement applied: the hook now creates or rotates the `kai-api-keys` key with `subscription: local-models-subscription`.
- Follow-up GitOps hygiene finding: when Stage 040 temporarily restored the placeholder MaaS Gateway hostname, the Stage 080 hook accepted it and patched placeholder values into `Tackle.spec.kai_llm_baseurl` and the `kai-api-keys` Secret. Improvement applied: the hook now rejects placeholder MaaS hostnames before patching any MTA resources.
- The validator initially checked Tackle AI conditions before the operator finished updating status. Improvement applied: Stage 080 validation now waits for `KaiAPIKeysConfigured`, `LLMProxyReady`, and `KaiSolutionServerReady`.
- Temporary MaaS API keys created while testing the subscription field were deleted through the MaaS API.
- Final evidence for Stage 080: MTA Operator CSV `mta-operator.v8.1.1` succeeded; MTA Hub, UI, Kai API, LLM proxy, and Kai solution server are ready; OpenShift login is visible on the MTA login page; MaaS auth against the private Nemotron model returns HTTP 200 using `kai-api-keys`; Argo CD reports Stage 080 `Synced` and `Healthy`.

Stage 090 findings:

- Initial Stage 090 sync installed Red Hat Developer Hub successfully, but the configure hook's 180 second rollout wait was too short for the first cold RHDH image pull and dynamic plugin install. Improvement applied: increase the hook deadline and rollout timeout.
- The `Backstage` manifest included `spec.application.replicas`, but the installed RHDH `v1alpha5` CRD does not define that field. The API server pruned it, leaving Argo CD OutOfSync. Improvement applied: remove the unsupported field rather than masking the drift.
- The configure hook regenerated OIDC and session secrets on every sync, which forced unnecessary RHDH restarts. Improvement applied: reuse existing non-placeholder secret values and restart only when secret data changes.
- The first idempotency check treated uppercase placeholder values as real secrets. Improvement applied: make placeholder detection case-insensitive and validate that `RHDH_OIDC_CLIENT_SECRET` and `SESSION_SECRET` are non-placeholder.
- Follow-up Red Hat alignment finding: the RHDH catalog URL was hard-coded to the `main` branch, while the deployed demo was sourced from `codex/stage-refactor-demo-validation`. Improvement applied: make the catalog URL environment-driven and derive it from the live Argo CD Application source.
- Final evidence for Stage 090: RHDH Operator CSV `rhdh-operator.v1.9.3` succeeded; `Backstage` CR `developer-hub` is present; the RHDH deployment is ready; the portal route returns HTTP 200; OIDC/session secrets are generated; the catalog URL matches the deployed GitOps source; the ConsoleLink points to the real RHDH route; Argo CD reports Stage 090 `Synced` and `Healthy`.

### 2026-05-02 Stage 020 GPUaaS validation run

Cluster:

- API: `https://api.cluster-t977r.t977r.sandbox3022.opentlc.com:6443`
- OpenShift: `4.20.19`
- Validation branch: `codex/stage020-gpuaas`
- Validation commits: `ceda099`, `75af578`, `d42d72a`

Actions:

- Restored GPU capacity by scaling MachineSet `cluster-t977r-vs62m-g6e-us-east-2c` from 0 to 2 replicas.
- Temporarily pointed Argo CD Applications `010-openshift-ai-platform-foundation`, `020-gpu-infrastructure-private-ai`, and `030-private-model-serving` at branch `codex/stage020-gpuaas` for live GitOps validation.
- Forced a hard Argo CD refresh after pushing the branch so the controller rendered commit `ceda099`.
- Corrected the Red Hat build of Kueue channel from planned `stable-v1.0` to `stable-v1.3` after live package discovery showed the OpenShift 4.20 catalog exposes `stable-v1.1`, `stable-v1.2`, and `stable-v1.3`.
- Fixed Stage 020 validation to use the explicit `kueues.kueue.openshift.io` API resource because `oc get kueue` is ambiguous when both OpenShift AI and Red Hat build of Kueue CRDs are installed.
- Fixed Stage 020 validation to accept multiple healthy KEDA runtime pods.
- Resolved a follow-on Argo CD issue in Stage 050 after `maas` was recreated by the Stage 020 namespace ownership change. The external model Secret, `ExternalModel`, `MaaSModelRef`, `MaaSAuthPolicy`, and `MaaSSubscription` resources were reapplied and `050-approved-external-model-access` returned to `Synced` and `Healthy`.

Stage 020 evidence:

- `./stages/020-gpu-infrastructure-private-ai/validate.sh`: 43 passed, 2 warnings, 0 failed.
- Argo CD Application `020-gpu-infrastructure-private-ai`: `Synced` and `Healthy`.
- Red Hat build of Kueue Operator CSV `kueue-operator.v1.3.1`: `Succeeded`.
- Custom Metrics Autoscaler CSV `custom-metrics-autoscaler.v2.18.1-2`: `Succeeded`.
- `Kueue` CR `cluster`: `Available=True`, `readyReplicas=2`.
- `ResourceFlavor` `nvidia-l4-gpu`, `ClusterQueue` `private-model-serving-gpu`, and `LocalQueue` `private-model-serving` are present.
- `LocalQueue` reported `pending=0`, `admitted=2`, and `reserving=2` after Stage 030 reconciliation.
- Queue-based hardware profiles `nvidia-l4-1gpu-queued` and `nvidia-l4-2gpu-queued` are present in `redhat-ods-applications`.
- `KedaController` `keda` reports `Installation Succeeded`.
- GPU MachineSet `cluster-t977r-vs62m-g6e-us-east-2c` has 2 ready replicas.
- Both GPU nodes are Ready, tainted `nvidia.com/gpu=true:NoSchedule`, labeled with the GPU role, and advertise `nvidia.com/gpu: 1`.
- NVIDIA `ClusterPolicy` reports `Ready=True` and `state=ready`.
- Dashboard ConfigMaps `nvidia-dcgm-exporter-dashboard` and `rhoai-gpuaas-dashboard` exist.

Remaining Stage 020 warnings:

- Raw Prometheus proxy queries for `DCGM_FI_DEV_GPU_UTIL` and `kueue_pending_workloads` returned authentication errors from `oc get --raw`. The dashboard ConfigMap is present, but metric query validation remains a warning until the supported console/Prometheus query path is confirmed.

Stage 030 evidence:

- Initial validation while images were still pulling: `./stages/030-private-model-serving/validate.sh`: 20 passed, 2 warnings, 0 failed.
- Final validation after model image pulls completed: `./stages/030-private-model-serving/validate.sh`: 22 passed, 0 warnings, 0 failed.
- Argo CD Application `030-private-model-serving`: `Synced` and `Healthy`.
- Both `LLMInferenceService` resources have `kueue.x-k8s.io/queue-name=private-model-serving`.
- Kueue created two `Workload` objects for private model-serving pods, both admitted through `private-model-serving-gpu`.
- The `private-model-serving` `LocalQueue` reported two admitted workloads and zero pending workloads.
- `gpt-oss-20b` and `nemotron-3-nano-30b-a3b` both reached `Ready=True`.
- Both private model-serving pods are `Running`, with all containers ready, on the two GPU nodes.

Argo CD status after remediation:

- `010-openshift-ai-platform-foundation`, `020-gpu-infrastructure-private-ai`, and `030-private-model-serving` point to `codex/stage020-gpuaas` for validation and are `Synced`/`Healthy`.
- Stages `040` through `090` point to `main`; all are `Synced`/`Healthy` after the Stage 050 resync.

### 2026-05-02 Stage 030 llm-d scale-ready validation run

Cluster:

- API: `https://api.cluster-t977r.t977r.sandbox3022.opentlc.com:6443`
- OpenShift: `4.20.19`
- Validation branch: `codex/stage020-gpuaas`
- Validation commit: `08b37b0`

Actions:

- Confirmed the installed `LLMInferenceService` `v1alpha1` CRD supports `spec.router.scheduler`, `spec.parallelism`, `spec.prefill`, and `spec.worker`, but does not expose `spec.scaling`.
- Added explicit `spec.router.scheduler: {}` to both private model `LLMInferenceService` resources. Live reconciliation created one router-scheduler Deployment per model using the OpenShift AI llm-d inference scheduler image.
- Added single-GPU-per-replica deployment metadata, NVIDIA L4 accelerator labeling, vLLM prefix-caching arguments, explicit cold-start probe timings, and a `PrometheusRule` that aliases documented vLLM metrics for future autoscaling analysis.
- Synced Argo CD Application `030-private-model-serving` to branch commit `08b37b0`; Argo CD reported `Synced` and `Healthy`.
- During rollout, the two old model ReplicaSets still held the two admitted Kueue GPU reservations while the new scheduler-enabled pods waited behind `SchedulingGated`. Because the demo `ClusterQueue` intentionally has only two GPUs, the stale ReplicaSets were manually scaled to zero to release quota for the new revision.

Validation evidence:

- Static checks passed:
  - `bash -n stages/030-private-model-serving/deploy.sh stages/030-private-model-serving/validate.sh`
  - `kustomize build gitops/stages/030-private-model-serving/base`
  - `kustomize build gitops/stages/030-private-model-serving/base | oc apply --dry-run=server -f -`
  - `git diff --check`
- Live validation after image pull, cold start, and probe remediation: `./stages/030-private-model-serving/validate.sh`: 30 passed, 0 warnings, 0 failed.
- Both router-scheduler pods were created and running.
- Both new model workloads were admitted by Kueue and assigned to GPU nodes.
- Both `gpt-oss-20b` and `nemotron-3-nano-30b-a3b` are `Ready=True`, with model pods `2/2 Running`.
- `PrometheusRule` `vllm-metrics-alias` exists in the `maas` namespace.
- GPT-OSS briefly reached readiness and then restarted because the default liveness delay was too short for cold vLLM compilation after image pull. The manifests now set an explicit 600-second liveness initial delay for both private models.

Current limitation:

- The demo now uses the Red Hat OpenShift AI llm-d `LLMInferenceService` path with vLLM as the runtime and scheduler enablement, but it does not deploy full Workload Variant Autoscaler configuration, multi-node serving, or disaggregated prefill/decode workers. That limitation is tracked in `BACKLOG.md`.

### 2026-05-02 GPU resume-from-zero validation run

Actions:

- Scaled GPU MachineSet `cluster-t977r-vs62m-g6e-us-east-2c` from 2 replicas to 0 with `./scripts/resume-gpu-demo.sh down`.
- Confirmed private model resources moved to `Ready=False` with `MinimumReplicasUnavailable` while Kueue queue resources and admitted workload records remained present.
- Ran `./scripts/resume-gpu-demo.sh resume` to sync Stage 020, scale the GPU MachineSet back to 2, wait for replacement GPU nodes, and continue Stage 020/030 recovery.
- Observed a cold-start timing issue: GPU nodes advertised allocatable `nvidia.com/gpu` before NVIDIA `ClusterPolicy` returned to `state=ready`. The resume script now waits for `ClusterPolicy` readiness before Stage 020 validation.

Validation evidence:

- GPU MachineSet returned to 2 ready replicas.
- Replacement GPU nodes became Ready, retained `node-role.kubernetes.io/gpu`, retained `nvidia.com/gpu=true:NoSchedule`, and advertised `nvidia.com/gpu: 1`.
- NVIDIA `ClusterPolicy` returned to `Ready=True` and `state=ready`.
- Stage 020 validation after operator readiness: 43 passed, 2 warnings, 0 failed. The two warnings are the existing raw Prometheus query warnings for GPU/Kueue metrics.
- Kueue admitted both private model workloads through `private-model-serving-gpu`.
- `nemotron-3-nano-30b-a3b` and `gpt-oss-20b` both recovered to `Ready=True` after large model image pulls and vLLM cold start.
- Stage 030 validation after resume: 30 passed, 0 warnings, 0 failed.

### 2026-05-02 Stage 040 GuideLLM load validation run

Actions:

- Added a Stage 040 GuideLLM load-test wrapper that runs as an ephemeral `Job` in the `maas` namespace and targets a MaaS-published OpenAI-compatible endpoint.
- Kept the default load intentionally small: constant profile, 1 request per second, 20-second maximum duration, 5 generated prompt samples, and 64 requested output tokens.
- Stored each benchmark console summary in a labeled `ConfigMap` in the `maas` namespace so operators can retrieve prior short-run evidence and compare model behavior across later reruns.
- Documented the Red Hat OpenShift AI 3.4 Developer Preview status for Evaluation Stack / GuideLLM support. This workshop uses the upstream GuideLLM container directly as demo-scale load tooling until the Red Hat OpenShift AI Evaluation Stack path is ready for this demo.
- Deleted an intermediate raw-result test artifact after confirming GuideLLM JSON/CSV output includes backend arguments. The committed wrapper stores only the safe console summary, and the `kai-api-keys` MaaS key was rotated in the live environment.

Validation evidence:

- Static validation passed: `bash -n stages/040-governed-models-as-a-service/*.sh`.
- Static diff hygiene passed: `git diff --check`.
- Live GuideLLM run against `nemotron-3-nano-30b-a3b` completed 3 requests through the MaaS route with 0 incomplete requests and 0 errors. Result ConfigMap: `maas/guidellm-nemotron-3-nano-30b-a3b-20260502162637-results`.
- Full Stage 040 validation passed after adding the sanitized load test path: `./stages/040-governed-models-as-a-service/validate.sh`: 52 passed, 0 warnings, 0 failed. Result ConfigMap from the validation run: `maas/guidellm-nemotron-3-nano-30b-a3b-20260502163408-results`.
- Stored GuideLLM result ConfigMaps were checked for `api_key` and `sk-oai-` strings after cleanup; no stored key material was found.

### 2026-05-02 Stage 040 Grafana OAuth validation run

Actions:

- Replaced the public Grafana login path with an OpenShift OAuth proxy sidecar managed through the Grafana Operator `Grafana` CR.
- Configured `grafana-sa` as the OpenShift OAuth client with an OAuth redirect reference to `Route/grafana-route`.
- Updated `grafana-route` to target the `oauth-proxy` service port with re-encrypt TLS and OpenShift Service CA.
- Restricted Grafana OAuth browser access to the `rhoai-users` OpenShift group, which includes both demo personas. Added `system:auth-delegator` for `grafana-sa` to support proxy token-review behavior.

Validation evidence:

- Static validation passed: `bash -n stages/040-governed-models-as-a-service/*.sh`, `kustomize build gitops/stages/040-governed-models-as-a-service/base`, `./scripts/validate-stage-flow.sh`, and `git diff --check`.
- Argo CD Stage 040 synced to branch commit `25f1426` and reported `Synced` / `Healthy`.
- Unauthenticated access to `https://grafana-route-grafana.apps.cluster-t977r.t977r.sandbox3022.opentlc.com/` returned HTTP `302` to OpenShift OAuth.
- The failed SAR-based authorization path was replaced with direct `--openshift-group=["rhoai-users"]` authorization after the proxy denied `ai-admin` as `ai-admin@cluster.local`.
- Unauthenticated access to the Grafana route returns HTTP `302` to OpenShift OAuth, and the in-pod Grafana API accepts the trusted `X-Forwarded-User: ai-admin` header from the proxy trust boundary.
- Full Stage 040 validation after OAuth protection passed: `./stages/040-governed-models-as-a-service/validate.sh`: 57 passed, 0 warnings, 0 failed. Result ConfigMap from the embedded GuideLLM run: `maas/guidellm-nemotron-3-nano-30b-a3b-20260502165718-results`.
- After environment recovery, a new GuideLLM run generated fresh MaaS traffic and the Grafana datasource query for `authorized_hits` returned data. Full Stage 040 validation then passed with 58 checks, 0 warnings, and 0 failures. Result ConfigMap from the validation run: `maas/guidellm-nemotron-3-nano-30b-a3b-20260502173602-results`.

### 2026-05-02 uncontrolled shutdown recovery observation

Actions:

- Monitored the environment after it was stopped outside the normal demo scale-down path and then started again.
- Confirmed the API recovered from `/readyz=500` to `/readyz=200`, the OpenShift console returned HTTP `200`, and all nine Argo CD Applications reported `Synced` and `Healthy`.
- Observed that both GPU nodes initially reported `NodeStatusUnknown` because their kubelets stopped posting heartbeats. Machine API showed the GPU Machine objects still existed while the underlying provider instances were `stopped`.
- Added a repair path to `./scripts/resume-gpu-demo.sh`: when a GPU MachineSet has stopped provider instances, the script can scale the MachineSet to zero, delete the stopped Machine objects, wait for cleanup, and scale back to the requested replica count.
- Ran `./scripts/resume-gpu-demo.sh resume` after the environment came back. The GPU instances resumed before replacement was required, but the new stopped-instance repair path remains in place for the next uncontrolled shutdown case.
- Fixed the Stage 040 Grafana health validation to accept both compact and pretty JSON from `/api/health`.

Validation evidence:

- GPU MachineSet `cluster-t977r-vs62m-g6e-us-east-2c` returned to 2 ready and available replicas.
- Both GPU nodes became `Ready`, advertised `nvidia.com/gpu: 1`, and NVIDIA `ClusterPolicy` returned to `Ready=True` and `state=ready`.
- Stage 020 recovery validation completed with 43 passed, 2 warnings, and 0 failed. The warnings are the known raw Prometheus query checks for GPU/Kueue metrics.
- Stage 030 recovery validation completed with 30 passed, 0 warnings, and 0 failed. Both private `LLMInferenceService` resources returned to `Ready=True`.
- Stage 040 recovery validation with `GUIDELLM_SKIP_LOAD_TEST=true` completed with 56 passed, 2 warnings, and 0 failed. The warnings were expected: skipped GuideLLM traffic generation and no fresh MaaS usage metric data yet.

### 2026-05-02 Stage 050 external model smoke validation

Actions:

- Stored the approved OpenAI provider key only in local `.env` and provisioned it into the live `maas/openai-api-key` Secret with the existing Stage 050 deploy path.
- Repointed Stage 050 back to the active feature branch after `deploy.sh` reapplied the app-of-apps manifest from `main`.
- Updated Stage 050 validation so the optional external smoke test creates a runtime MaaS API key for `external-models-subscription` instead of reusing the local-model coding-assistant subscription key.
- Updated the GuideLLM wrapper to support `GUIDELLM_VALIDATE_BACKEND`; Stage 050 sets it to `false` because the external MaaS path does not expose a vLLM-style `/health` endpoint.

Validation evidence:

- Stage 030 validation after the documentation refresh passed with 34 checks, 0 warnings, and 0 failures.
- Stage 040 validation after the documentation refresh passed with 58 checks, 0 warnings, and 0 failures. Result ConfigMap from the embedded GuideLLM run: `maas/guidellm-nemotron-3-nano-30b-a3b-20260502182022-results`.
- Stage 050 validation with external smoke test passed: `GUIDELLM_EXTERNAL_SMOKE_TEST=true GUIDELLM_REQUESTS=1 GUIDELLM_OUTPUT_TOKENS=32 ./stages/050-approved-external-model-access/validate.sh`: 19 passed, 0 warnings, 0 failed. Result ConfigMap: `maas/guidellm-gpt-4o-mini-20260502182117-results`.
- A direct OpenAI-compatible call through MaaS to `gpt-4o-mini` returned HTTP `200` with non-empty assistant content.
- The provider key and runtime MaaS key were not printed, committed, or stored in Git.

### Stage 020

Stage 020 creates the demo-scale GPU-as-a-Service foundation. It installs NFD, the NVIDIA GPU Operator, Red Hat build of Kueue, the OpenShift Custom Metrics Autoscaler Operator, queue/quota resources, queue-based hardware profiles, and GPU dashboards. New GPU nodes can take several minutes to provision and join the cluster.

The GPU Operator Subscription does not pin a channel. OLM uses the certified catalog default channel available in the target cluster. This avoids carrying an unexplained demo-specific version pin while still installing from the certified operator catalog.

The Red Hat build of Kueue Subscription uses the `stable-v1.3` channel from `redhat-operators` on the current OpenShift 4.20 demo cluster. Earlier planning referenced `stable-v1.0`, but live package discovery on this cluster showed only `stable-v1.1`, `stable-v1.2`, and `stable-v1.3`; the implementation follows the available Red Hat catalog channel. OpenShift AI is integrated with this external Kueue installation by Stage 020 after the operator is present: the stage patches `DataScienceCluster.spec.components.kueue.managementState` to `Unmanaged`, enables dashboard Kueue support with `OdhDashboardConfig.spec.dashboardConfig.disableKueue=false`, and creates the `maas` namespace with `kueue.openshift.io/managed=true` and `opendatahub.io/dashboard=true`.

The `private-model-serving-gpu` `ClusterQueue` is intentionally small: two NVIDIA L4 GPUs plus CPU, memory, and pod quota for the current private model-serving path. This demonstrates the GPUaaS operating model without pretending the disposable demo environment represents a large multi-tenant GPU fleet.

OpenShift Custom Metrics Autoscaler/KEDA is installed as a building block only. The stage does not attach `ScaledObject` resources to the private model deployments in the first pass. Production patterns should base scaling on validated Prometheus, Kueue backlog, or idle workload metrics.

Stage 010 still owns the base `DataScienceCluster` and dashboard resources. Its Argo CD Application ignores only the Kueue handoff fields so Stage 020 can enable the Red Hat OpenShift AI 3.4 external Kueue integration without making Stage 010 depend on Kueue being installed first. Stage 020 also owns the `maas` namespace now because the `LocalQueue` must exist before Stage 030 creates model-serving resources in that project.

Useful checks:

```bash
oc get subscription,csv -n openshift-kueue-operator
oc get kueue cluster -n openshift-kueue-operator
oc get resourceflavor,clusterqueue
oc get localqueue -n maas
oc get hardwareprofile -n redhat-ods-applications | grep -i queued
oc get kedacontroller -n openshift-keda
oc get machineset -n openshift-machine-api | grep -i gpu
oc get nodes -l node-role.kubernetes.io/gpu
oc get clusterpolicy -A
```

### Stage 030

Stage 030 deploys local private model serving resources: the `maas` project, local `LLMInferenceService` resources, LeaderWorkerSet prerequisites, and model registry seed data. The local models use the Red Hat OpenShift AI llm-d `LLMInferenceService` path with vLLM as the inference runtime. The demo configures single-GPU-per-replica serving, explicit scheduler enablement, Kueue queue admission, and vLLM metric aliases for future autoscaling analysis. It does not deploy multi-node, disaggregated prefill/decode inference, Gateway API Inference Extension `InferencePool` resources, or agentgateway body-based routing.

The `vllm-metrics-alias` `PrometheusRule` exposes raw and derived runtime signals for operational analysis: request backlog, running requests, request success rate, prompt and generation token throughput, time-to-first-token average, time-per-output-token average, KV cache usage, and prefix-cache hit ratio. These are the private-runtime signals that Stage 040 load tests and future autoscaling work can use.

Useful checks:

```bash
oc get llminferenceservice -n maas
oc get pods -n maas
oc get prometheusrule vllm-metrics-alias -n maas
oc get prometheusrule vllm-metrics-alias -n maas -o jsonpath='{.spec.groups[0].rules[*].record}'
oc get job model-registry-seed -n rhoai-model-registries
```

### Stage 040

Stage 040 deploys the governed Models-as-a-Service control point: MaaS controller, Gateway API, Red Hat Connectivity Link, Kuadrant, Authorino, local model subscriptions, rate limits, token limits, telemetry, and Grafana.

The upstream `maas-controller` and `maas-api` image override are intentional demo deviations. They demonstrate external model registration through upstream MaaS behavior and the Red Hat OpenShift AI 3.4 Technology Preview MaaS direction while the Red Hat OpenShift AI 3.3 supported operator path does not provide that full behavior. Keep the workaround visible in `BACKLOG.md` and remove it only when a supported Red Hat OpenShift AI release provides equivalent external model registration and the replacement has been validated.

The Grafana dashboard was copied from a Red Hat quickstart repository, but the operator source is `community-operators`. This is acceptable as a disposable demo add-on. Prefer a Red Hat-supported monitoring or observability path for long-lived environments.

The demo exposes the Grafana route through an OpenShift `ConsoleLink` named `grafana-maas` in the application menu. Grafana itself is protected by the Red Hat OpenShift OAuth proxy sidecar, using the `grafana-sa` service account as the OAuth client and the operator-owned `grafana-route` as the redirect reference. The route targets the `oauth-proxy` service port with re-encrypt TLS from OpenShift Service CA, and Grafana trusts `X-Forwarded-User` from the proxy through `auth.proxy`. The proxy restricts browser access to the `rhoai-users` OpenShift group, which includes `ai-admin` and `ai-developer`. A more Red Hat-aligned long-term approach is to move MaaS observability into the OpenShift monitoring stack and the web console Observe experience, using user workload monitoring and supported dashboard/query paths instead of a community Grafana dependency.

Grafana queries OpenShift monitoring through the Thanos Querier using a `grafana-sa` service account with the `cluster-monitoring-view` role. The `GrafanaDatasource` manifest keeps only a placeholder token in Git. A Stage 040 sync job mints the runtime token and patches `GrafanaDatasource/prometheus`; Argo CD ignores only that generated token field. If dashboards show `401 Unauthorized`, re-run Stage 040 sync and validate that the datasource can query OpenShift monitoring.

MaaS gateway traffic is emitted from the OpenShift Gateway Envoy metrics endpoint and scraped by `PodMonitor/maas-gateway-metrics` in `openshift-ingress`. The disposable Grafana dashboard currently uses a compatibility recording rule, `PrometheusRule/maas-dashboard-usage-metrics`, to map the real `istio_requests_total` series into the quickstart dashboard's expected `authorized_hits` shape. Treat this as demo observability glue, not production metric design guidance.

Stage 040 validation runs a short GuideLLM load test when a MaaS API key is available. Red Hat OpenShift AI 3.4 lists GuideLLM support through the Evaluation Stack control plane as a Developer Preview capability; this demo currently uses the upstream GuideLLM container directly to generate repeatable load against the MaaS OpenAI-compatible endpoint. Results are stored as `ConfigMap` objects in the `maas` namespace with names beginning `guidellm-`.

To compare the two private models with the same governed MaaS traffic shape, run:

```bash
./stages/040-governed-models-as-a-service/compare-private-models.sh
./stages/040-governed-models-as-a-service/summarize-guidellm-results.sh
```

Useful checks:

```bash
oc get maasmodelref -n maas
oc get maasauthpolicy,maassubscription -n models-as-a-service
oc get gateway maas-default-gateway -n openshift-ingress
oc get pods -n redhat-ods-applications -l control-plane=maas-controller
oc get clusterrolebinding grafana-sa-cluster-monitoring-view
oc get serviceaccount grafana-sa -n grafana -o yaml
oc get clusterrolebinding grafana-oauth-proxy-auth-delegator -o yaml
oc get route grafana-route -n grafana -o jsonpath='{.spec.port.targetPort}{" "}{.spec.tls.termination}{"\n"}'
oc get grafanadatasource prometheus -n grafana
oc get podmonitor maas-gateway-metrics -n openshift-ingress
oc get prometheusrule maas-dashboard-usage-metrics -n openshift-ingress
oc get configmap -n maas -l app.kubernetes.io/name=guidellm-load-test
```

Useful GuideLLM overrides:

```bash
GUIDELLM_MODEL=gpt-oss-20b \
GUIDELLM_PROFILE=constant \
GUIDELLM_RATE=1 \
GUIDELLM_MAX_SECONDS=20 \
GUIDELLM_REQUESTS=5 \
GUIDELLM_OUTPUT_TOKENS=64 \
GUIDELLM_PROMPT="Explain why governed model access matters for enterprise software teams." \
./stages/040-governed-models-as-a-service/run-guidellm-load-test.sh
```

### Stage 050

Stage 050 deploys approved external model access through MaaS.

External models share MaaS governance, subscription, API-key, rate-limit, token-limit, and gateway telemetry controls with private models. They do not share the same runtime observability boundary. OpenShift can observe local vLLM/GPU/Kueue signals for Stage 030 models, but external providers expose only gateway-visible request behavior and provider API success/failure from the demo platform perspective.

**Credential provisioning:** `deploy.sh` reads `.env` and provisions secrets before applying the Argo CD Application:

| `.env` variable | Secret created | Namespace | Purpose |
|----------------|----------------|-----------|---------|
| `OPENAI_API_KEY` | `openai-api-key` | `maas` | Credential injection for external models (gpt-4o, gpt-4o-mini) |

The Argo CD Application has `ignoreDifferences` configured for these Secrets so `selfHeal` does not revert provisioned values to the GitOps placeholder.

If you need to update a credential after initial deployment:

```bash
oc create secret generic openai-api-key -n maas \
    --from-literal=api-key="sk-proj-YOUR-KEY" \
    --dry-run=client -o yaml | oc apply -f -
oc label secret openai-api-key -n maas inference.networking.k8s.io/bbr-managed=true --overwrite
```

Useful checks:

```bash
oc get externalmodel -n maas
oc get maasmodelref gpt-4o gpt-4o-mini -n maas
oc get maasauthpolicy external-models-access -n models-as-a-service
oc get maassubscription external-models-subscription -n models-as-a-service
oc get secret openai-api-key -n maas -o jsonpath='{.data.api-key}' | base64 -d | head -c10
```

External inference validation is opt-in because it spends provider tokens:

```bash
GUIDELLM_EXTERNAL_SMOKE_TEST=true \
GUIDELLM_REQUESTS=1 \
GUIDELLM_OUTPUT_TOKENS=32 \
./stages/050-approved-external-model-access/validate.sh
```

The opt-in check creates a MaaS API key for `external-models-subscription` at runtime and passes it to the GuideLLM Job without printing or committing it. Stage 050 disables GuideLLM's default `/health` backend probe for this external path because the MaaS route validates external access through the OpenAI-compatible inference API rather than a vLLM-style health endpoint.

### Stage 060

Stage 060 deploys MCP context integrations.

| `.env` variable | Secret created | Namespace | Purpose |
|----------------|----------------|-----------|---------|
| `SLACK_BOT_TOKEN` | `slack-mcp-credentials` | `coding-assistant` | Slack MCP server authentication |
| `BRIGHTDATA_API_TOKEN` | `brightdata-mcp-credentials` | `coding-assistant` | BrightData MCP server authentication |

Useful checks:

```bash
oc get pods -n coding-assistant
oc get configmap gen-ai-aa-mcp-servers -n redhat-ods-applications -o yaml
```

### Stage 070

Stage 070 installs Red Hat OpenShift Dev Spaces and pre-provisions workspaces.

Validation now checks both service readiness and persona workspace readiness. The stage is not considered fully validated unless `wksp-kubeadmin`, `wksp-ai-admin`, and `wksp-ai-developer` exist, each contains the `exercises` DevWorkspace, and the `ai-admin` / `ai-developer` workspace edit RoleBindings point at the expected OpenShift users.

Useful checks:

```bash
oc get checluster devspaces -n openshift-devspaces
oc get devworkspace -A
oc get pods -n openshift-devspaces
```

### Stage 080

Stage 080 installs Migration Toolkit for Applications and configures Red Hat Developer Lightspeed for MTA to use MaaS.

Useful checks:

```bash
oc get tackle mta -n openshift-mta -o yaml
oc get deployment -n openshift-mta
oc get secret kai-api-keys -n openshift-mta -o jsonpath='{.data.OPENAI_API_BASE}' | base64 -d
```

### Stage 090

Stage 090 installs Red Hat Developer Hub and configures OIDC through MTA Keycloak.

The RHDH catalog location is runtime-derived from the Stage 090 Argo CD Application source. This avoids loading catalog entities from `main` when the demo is deployed from a validation branch or fork.

Useful checks:

```bash
oc get backstage developer-hub -n rhdh -o yaml
oc get pods -n rhdh
oc get route -n rhdh
oc get consolelink rhdh -o yaml
oc get secret rhdh-secrets -n rhdh -o jsonpath='{.data.RHDH_CATALOG_URL}' | base64 -d
```

## Updating The Demo

For GitOps-managed behavior:

1. Edit manifests under `gitops/`.
2. Commit and push changes to the branch referenced by the Argo CD Applications.
3. Let Argo CD reconcile or manually sync.
4. Run the matching `validate.sh`.

For documentation-only changes:

1. Edit `README.md`, `stages/*/README.md`, or files under `docs/`.
2. Run `git diff --check`.
3. Check that links and references still match the repo.

## Resuming GPU-Backed Stages After Shutdown

Stage 020 and Stage 030 support a first-class "resume from zero GPU nodes" workflow. Use this after the GPU MachineSet was scaled to zero for cost saving, or after the demo environment has been stopped and started again.

```bash
./scripts/resume-gpu-demo.sh status
./scripts/resume-gpu-demo.sh resume
```

The `resume` command requests an Argo CD sync for Stage 020, scales the discovered GPU MachineSet back to `GPU_MACHINESET_REPLICAS` replicas, repairs stopped provider instances when Machine API still has stale GPU Machine objects, waits for GPU nodes with allocatable `nvidia.com/gpu`, waits for NVIDIA `ClusterPolicy` readiness, validates Stage 020, syncs Stage 030, clears stale old model ReplicaSets that can hold Kueue quota during a two-GPU rollout, waits for private models, and runs Stage 030 validation.

To scale GPU capacity down for shutdown:

```bash
./scripts/resume-gpu-demo.sh down
```

Kueue queue resources survive normal cluster restarts because they are Kubernetes API objects. Kueue does not create cloud GPU nodes by itself; GPU node lifecycle remains a platform capacity action through the MachineSet.

## Cleanup Guidance

The Argo CD Applications intentionally do not include finalizers. Deleting an Application by itself orphans the resources that it created.

For a full cleanup, prefer an explicit Argo CD cascade delete from the OpenShift GitOps UI or CLI:

```bash
argocd app delete 090-developer-portal-self-service --cascade
argocd app delete 080-ai-assisted-application-modernization --cascade
argocd app delete 070-controlled-developer-workspaces --cascade
argocd app delete 060-mcp-context-integrations --cascade
argocd app delete 050-approved-external-model-access --cascade
argocd app delete 040-governed-models-as-a-service --cascade
argocd app delete 030-private-model-serving --cascade
argocd app delete 020-gpu-infrastructure-private-ai --cascade
argocd app delete 010-openshift-ai-platform-foundation --cascade
```

Delete in reverse deployment order. Review GPU MachineSets and persistent volumes separately before removing them because cloud infrastructure and storage cleanup can be environment-specific.

If the `argocd` CLI is unavailable, use the OpenShift GitOps UI and choose cascade deletion. Avoid broad namespace deletion unless you have confirmed no shared cluster resources are still needed.

## When To Use Which Document

| Need | Use |
|------|-----|
| Understand the architecture and value | `README.md` and stage READMEs |
| Deploy and validate the environment | This file |
| Diagnose failures | `docs/TROUBLESHOOTING.md` |
| See exact executable behavior | `deploy.sh` and `validate.sh` scripts |

## References

- [OpenShift GitOps documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/)
- [Red Hat OpenShift AI documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/)
- [OpenShift CLI documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/cli_tools/openshift-cli-oc)
- [Argo CD documentation](https://argo-cd.readthedocs.io/)
