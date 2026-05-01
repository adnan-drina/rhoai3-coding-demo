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
| 020 | `020-gpu-infrastructure-private-ai` | NFD, GPU Operator, GPU MachineSets |
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
- Git branch used by Argo CD: `codex/stage-refactor-demo-validation`
- Latest validated code commit: `157d2ba`

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
| 010 OpenShift AI Platform Foundation | Passed | `./stages/010-openshift-ai-platform-foundation/validate.sh`: 11 passed, 0 warnings, 0 failed |
| 020 GPU Infrastructure for Private AI | Passed | `./stages/020-gpu-infrastructure-private-ai/validate.sh`: 9 passed, 0 warnings, 0 failed |
| 030 Private Model Serving | Passed | `./stages/030-private-model-serving/validate.sh`: 8 passed, 0 warnings, 0 failed |
| 040 Governed Models-as-a-Service | Passed | `./stages/040-governed-models-as-a-service/validate.sh`: 17 passed, 0 warnings, 0 failed |
| 050 Approved External Model Access | Passed with expected warning | `./stages/050-approved-external-model-access/validate.sh`: 8 passed, 1 warning, 0 failed |
| 060 MCP Context Integrations | Passed with expected warnings | `./stages/060-mcp-context-integrations/validate.sh`: 6 passed, 2 warnings, 0 failed |
| 070 Controlled Developer Workspaces | Passed | `./stages/070-controlled-developer-workspaces/validate.sh`: 5 passed, 0 warnings, 0 failed |
| 080 AI-Assisted Application Modernization | Passed | `./stages/080-ai-assisted-application-modernization/validate.sh`: 20 passed, 0 warnings, 0 failed |
| 090 Developer Portal and Self-Service | Passed | `./stages/090-developer-portal-self-service/validate.sh`: 10 passed, 0 warnings, 0 failed |

Final sweep:

- All nine Argo CD Applications reported `Synced` and `Healthy`.
- A full live validation sweep from Stage 010 through Stage 090 completed without critical failures.
- Expected warnings remain for Stage 050 external inference because `OPENAI_API_KEY` is not set, and Stage 060 optional Slack/BrightData MCP runtimes because `SLACK_BOT_TOKEN` and `BRIGHTDATA_API_TOKEN` are not set.

Stage 010 findings:

- Automated sync initially stalled after bootstrap while waiting on `ClusterRole/job-approve-sm-installplan` and `ClusterRole/job-patch-dsci-ca`, even though both resources existed. Manual `argocd app sync 010-openshift-ai-platform-foundation` advanced the operation and completed successfully. Improvement candidate: add a bootstrap readiness wait for the Argo CD application-controller cache before applying the first stage, and document `argocd app sync` as the recovery command for this startup race.
- Validation found `OdhDashboardConfig.spec.dashboardConfig.genAiStudio` absent. Root cause: the Stage 010 Application ignored the entire `OdhDashboardConfig.spec` while `RespectIgnoreDifferences=true`, so Argo CD reported the resource synced without enforcing the MaaS-required dashboard flags. Fix applied in commit `8e4ce3d`: stop ignoring `OdhDashboardConfig.spec`; keep operator-managed drift ignores only where they do not hide required demo configuration.
- After the fix, Stage 010 re-synced to commit `8e4ce3d` and validation passed with 11 checks, 0 warnings, and 0 failures.

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
- MaaS generated the gateway policy as `gateway-default-auth`, not the older `gateway-auth-policy` name used by the hook. Improvement being applied: patch `gateway-default-auth` and use a JSON patch to replace `maas-api-auth-policy` authorization with an explicit empty object.
- After the gateway and RHCL were healthy, the existing `LLMInferenceService` resources still reported the earlier AuthPolicy CRD discovery error. A controlled restart of `kserve-controller-manager` refreshed API discovery and immediately created the model HTTPRoutes. Improvement being applied: add a Stage 040 hook to restart KServe after RHCL/Gateway readiness in this staged demo flow.
- Final evidence for Stage 040: CloudNativePG, Red Hat Connectivity Link, Kuadrant, MaaS API, local `MaaSModelRef` resources, local `MaaSAuthPolicy`, local `MaaSSubscription`, per-route AuthPolicies, and Grafana all validated successfully. Argo CD reports Stage 040 `Synced` and `Healthy`.

Stage 050 findings:

- `OPENAI_API_KEY` is not set in this demo environment. Stage 050 registered the approved external model resources with the placeholder `openai-api-key` credential, so external inference was intentionally not validated.
- Final evidence for Stage 050: `ExternalModel` and `MaaSModelRef` resources for `gpt-4o` and `gpt-4o-mini` are registered and Ready. `external-models-access` and `external-models-subscription` are Active. Argo CD reports Stage 050 `Synced` and `Healthy`.

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
- The validator initially checked Tackle AI conditions before the operator finished updating status. Improvement applied: Stage 080 validation now waits for `KaiAPIKeysConfigured`, `LLMProxyReady`, and `KaiSolutionServerReady`.
- Temporary MaaS API keys created while testing the subscription field were deleted through the MaaS API.
- Final evidence for Stage 080: MTA Operator CSV `mta-operator.v8.1.1` succeeded; MTA Hub, UI, Kai API, LLM proxy, and Kai solution server are ready; OpenShift login is visible on the MTA login page; MaaS auth against the private Nemotron model returns HTTP 200 using `kai-api-keys`; Argo CD reports Stage 080 `Synced` and `Healthy`.

Stage 090 findings:

- Initial Stage 090 sync installed Red Hat Developer Hub successfully, but the configure hook's 180 second rollout wait was too short for the first cold RHDH image pull and dynamic plugin install. Improvement applied: increase the hook deadline and rollout timeout.
- The `Backstage` manifest included `spec.application.replicas`, but the installed RHDH `v1alpha5` CRD does not define that field. The API server pruned it, leaving Argo CD OutOfSync. Improvement applied: remove the unsupported field rather than masking the drift.
- The configure hook regenerated OIDC and session secrets on every sync, which forced unnecessary RHDH restarts. Improvement applied: reuse existing non-placeholder secret values and restart only when secret data changes.
- The first idempotency check treated uppercase placeholder values as real secrets. Improvement applied: make placeholder detection case-insensitive and validate that `RHDH_OIDC_CLIENT_SECRET` and `SESSION_SECRET` are non-placeholder.
- Final evidence for Stage 090: RHDH Operator CSV `rhdh-operator.v1.9.3` succeeded; `Backstage` CR `developer-hub` is present; the RHDH deployment is ready; the portal route returns HTTP 200; OIDC/session secrets are generated; the ConsoleLink points to the real RHDH route; Argo CD reports Stage 090 `Synced` and `Healthy`.

### Stage 020

Stage 020 creates GPU infrastructure. New GPU nodes can take several minutes to provision and join the cluster.

The GPU Operator Subscription does not pin a channel. OLM uses the certified catalog default channel available in the target cluster. This avoids carrying an unexplained demo-specific version pin while still installing from the certified operator catalog.

Useful checks:

```bash
oc get machineset -n openshift-machine-api | grep -i gpu
oc get nodes -l node-role.kubernetes.io/gpu
oc get clusterpolicy -A
```

### Stage 030

Stage 030 deploys local private model serving resources: the `maas` project, local `LLMInferenceService` resources, LeaderWorkerSet prerequisites, and model registry seed data.

Useful checks:

```bash
oc get llminferenceservice -n maas
oc get pods -n maas
oc get job model-registry-seed -n rhoai-model-registries
```

### Stage 040

Stage 040 deploys the governed Models-as-a-Service control point: MaaS controller, Gateway API, Red Hat Connectivity Link, Kuadrant, Authorino, local model subscriptions, rate limits, token limits, telemetry, and Grafana.

The upstream `maas-controller` and `maas-api` image override are intentional demo deviations. They demonstrate external model registration through upstream and Red Hat OpenShift AI 3.4 early access MaaS capabilities while the Red Hat OpenShift AI 3.3 supported operator path does not provide that full behavior. Keep the workaround visible in `BACKLOG.md` and remove it when a supported Red Hat OpenShift AI release provides equivalent external model registration.

The Grafana dashboard was copied from a Red Hat quickstart repository, but the operator source is `community-operators`. This is acceptable as a disposable demo add-on. Prefer a Red Hat-supported monitoring or observability path for long-lived environments.

Useful checks:

```bash
oc get maasmodelref -n maas
oc get maasauthpolicy,maassubscription -n models-as-a-service
oc get gateway maas-default-gateway -n openshift-ingress
oc get pods -n redhat-ods-applications -l control-plane=maas-controller
```

### Stage 050

Stage 050 deploys approved external model access through MaaS.

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

Useful checks:

```bash
oc get backstage developer-hub -n rhdh -o yaml
oc get pods -n rhdh
oc get route -n rhdh
oc get consolelink rhdh -o yaml
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
