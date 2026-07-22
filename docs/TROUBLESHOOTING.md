# Troubleshooting Guide

> **Foundation migration (2026-07-06):** stages 010-040 now import the
> validated rhoai3-demo foundation (former 050/060 folded into 040). Sections
> below that describe the pre-migration 010-060 implementation are historical
> until rewritten after the first migrated deployment.

This guide collects operational failure modes for the workshop. Keep the README files educational; put recovery procedures here.

Use this format for new entries:

````markdown
## Symptom

**Affected stage:** Stage NNN

**Likely cause:** ...

**Diagnose:**
```bash
...
```

**Recover:**
```bash
...
```
````

## General Diagnostic Flow

Start with the failing stage's validation script:

```bash
./stages/NNN-*/validate.sh
```

Then inspect Argo CD:

```bash
oc get applications -n openshift-gitops \
  -o custom-columns='APP:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status'
```

For a specific app:

```bash
APP=040-governed-models-as-a-service
oc get application "$APP" -n openshift-gitops -o json \
  | jq -r '.status.resources[]? | select(.status != "Synced" or .health.status != "Healthy") | [.kind,.namespace,.name,.status,.health.status,.message] | @tsv'
```

Check pods:

```bash
oc get pods -A | egrep 'CrashLoopBackOff|ImagePullBackOff|Error|Pending'
```

## Argo CD App Is OutOfSync

**Affected stage:** Any

**Likely cause:** Operator-managed fields, PostSync patch jobs, dynamic route values, or manual changes.

**Diagnose:**

```bash
APP=050-advanced-app-platform
oc get application "$APP" -n openshift-gitops -o json \
  | jq -r '.status.resources[]? | select(.status != "Synced") | [.kind,.namespace,.name,.status,.message] | @tsv'
```

**Recover:**

- If drift is expected and cluster-specific, add a narrow `ignoreDifferences` entry to the Argo CD Application.
- If drift is not expected, fix the Git manifest or re-sync the app.
- Avoid broad ignores such as a whole CR `spec` unless the operator truly owns that full field.

## Model Shows "Starting" In The RHOAI Console But Its Pod Is Ready

**Affected stage:** Stage 030 (until Stage 040 is deployed)

**Likely cause:** The RHOAI console shows "Starting" for any `LLMInferenceService` whose CR-level `Ready` condition is not True. After Stage 030 the model workload itself is healthy (`MainWorkloadReady=True`, pod `2/2 Running`, in-cluster OpenAI API answering), but `RouterReady` and `HTTPRoutesReady` stay False with `GatewayPreconditionNotMet` because the maas-default-gateway and the Kuadrant AuthPolicy CRD only arrive with Stage 040 (Red Hat Connectivity Link).

**Diagnose:**

```bash
oc get llminferenceservice -n maas <model> \
  -o jsonpath='{range .status.conditions[*]}{.type}={.status} {.reason}{"\n"}{end}'
```

**Recover:** Deploy Stage 040. The router conditions reconcile once the gateway and policy CRDs exist, and the console flips to green. No action is needed on the model itself.

## Large Hybrid-MoE Model Crash-Loops With CUDA OOM At Engine Init

**Affected stage:** Stage 040 (qwen3-6-35b-a3b on a 48GB L40S)

**Likely cause:** a ~35GB-weight hybrid SSM/MoE model leaves almost no headroom on a 44.4GiB-usable card, and several vLLM consumers claim the rest by default: the multimodal vision-encoder cache (profiled with a max-size image), the per-slot mamba/GDN state cache sized by max_num_seqs (~8GiB at the default), and the MoE prefill activation workspace sized by max_num_batched_tokens. vLLM sizes the KV budget from the profiling peak, so these overheads produce num_gpu_blocks=0 and an OOM when the KServe template block override forces an allocation anyway.

**Diagnose:** read the engine log memory ledger in order — "Model loading took X GiB", "Initial profiling/warmup run", "Available KV cache memory", "num_gpu_blocks". Zero available KV with weights far below the utilization budget means resident overhead, not weights.

**Recover (the fit recipe that ships in GitOps):**

- `--limit-mm-per-prompt={"image":0,"video":0}` — text-only serving drops the vision encoder cache;
- `--max-num-seqs=64` — caps the per-slot hybrid state cache (the ~8GiB term; the KV pool, not the slot count, is the practical concurrency limit);
- `--kv-cache-dtype=fp8` — halves cache bytes, keeps the 32K context;
- `--max-num-batched-tokens=4096` — small MoE prefill workspace, but MUST exceed the mamba-aligned attention block size (2096 tokens with fp8 KV; the engine asserts otherwise);
- result: ~5GiB KV = ~130K cached tokens = 11x concurrency at 32K.

Rolling updates of single-replica GPU models deadlock when the new pod is SchedulingGated behind the old pod's Kueue quota: delete the old pod to hand over the card; the replacement the old ReplicaSet creates stays gated and is removed when the new pod reports Ready.

## Model Image Pull Stalls On A GPU Node

**Affected stage:** Stage 040 (first pull of a large modelcar)

**Likely cause:** kubelet DiskPressure mid-pull. Modelcar images are large (~30-36GB); on a 100GB root volume the pull plus cached base images crosses the image-GC threshold and garbage collection thrashes the very layers being pulled. Fixed by the 200GB gp3 default in generate-gpu-machineset.sh; note that MachineSet template changes only apply to newly created machines.

**Diagnose:**

```bash
oc describe node <gpu-node> | grep -A3 Conditions:   # DiskPressure transitions
oc get events -n models-as-a-service --sort-by=.lastTimestamp | grep -i pull
oc debug node/<gpu-node> -- chroot /host df -h /var  # watch used% growth
```

**Recover:**

- If the volume is undersized, recreate the GPU machines: scale the GPU MachineSet to 0, regenerate with `generate-gpu-machineset.sh --write` (200GB gp3 default), sync Stage 020, scale back up.
- If pressure already cleared, the pull resumes on its own; disk usage growth in /var confirms progress.

## InstallPlan Approval Carries Hidden Passenger CSVs

**Affected stage:** any operator in `openshift-operators` (shared namespace)

**Likely cause:** OLM bundles all co-pending CSVs of a namespace into one InstallPlan. Approving a plan to unblock one operator can silently upgrade others past their pins (observed live: approving the Stage 050 pipelines/rhtas plan carried rhcl-operator v1.3.4→v1.3.5), and dependency-generated subscriptions (authorino, created by OLM for RHCL) then sit in `UpgradePending` toward versions we never approve — which wedged every Stage 040 sync until the Argo Subscription health check learned that an installed CSV with a pending channel upgrade is Healthy by policy.

**Diagnose:**

```bash
oc get installplan -n openshift-operators -o json |   jq -r '.items[] | select(.spec.approved==false) | "\(.metadata.name) \(.spec.clusterServiceVersionNames)"'
```

**Recover:**

- Read every CSV in a plan BEFORE approving; pick the minimal plan that contains only versions compatible with your pins (there is usually one per generation).
- If a pin was jumped: verify the affected stage live, then move the pin to the installed version and document the event inline.
- The bootstrap Subscription health check (gitops/bootstrap overlays) treats installed-with-pending-upgrade as Healthy; keep that rule when regenerating Argo configuration.

## Argo CD Operation Stuck On A Hook Job

**Affected stage:** any stage with Sync-hook Jobs (waits, seeds, patches)

**Likely cause:** a hook Job that waits on external state (an API that never answers, a webhook that is not up yet) keeps the sync operation Running indefinitely — and a running operation silently blocks every newer Git revision from syncing. Variants seen live: "waiting for completion of hook", "waiting for deletion of hook", and a retry loop after a hook was deleted mid-operation.

**Diagnose:**

```bash
oc get application <app> -n openshift-gitops   -o jsonpath='{.status.operationState.phase} {.status.operationState.startedAt} {.status.operationState.message}'
# startedAt far in the past + Running = stuck operation
```

**Recover:**

```bash
# 1. Terminate the operation
oc patch application <app> -n openshift-gitops --type=merge   -p '{"status":{"operationState":{"phase":"Terminating"}}}'
# 2. Remove the offending hook Job if it lingers
oc delete job <hook-job> -n <ns> --ignore-not-found
# 3. Start a clean sync
oc patch application <app> -n openshift-gitops --type=merge   -p '{"operation":{"initiatedBy":{"username":"operator"},"sync":{"prune":true}}}'
```

Prevention: hook jobs must have bounded retries and fail fast; never let a wait-loop hook depend on state created by a later wave of the same sync.

## Manually Triggered Sync Finishes In Seconds And Skips Hooks

**Affected stage:** Any, observed on Stage 050 catalog changes

**Symptom:** A sync operation triggered by patching `.operation` on the Application completes in ~15 seconds, applies only a handful of resources, and never runs Sync/PostSync hook Jobs (e.g. `job-generate-rhdh-catalog`). The controller logs `Partial sync operation to <rev> succeeded`.

**Likely cause:** The self-heal auto-sync writes partial operations that carry an `operation.sync.resources` filter. A later `oc patch --type=merge` of `.operation` inherits that filter (merge patches keep fields you omit), and partial syncs skip hooks by design. Even a `--type=json` replace can be clobbered when self-heal immediately overwrites the operation with a new partial one. Observed live 2026-07-13. Also observed the same evening: the automated sync that picks up a NEWLY PUSHED revision can itself arrive as a partial operation (2-resource filter) rendered from a stale manifest cache — new resources in the pushed commit were neither applied nor listed until `argocd.argoproj.io/refresh=hard` was annotated, after which the missing resources applied within seconds (hooks still skipped; converge hook output by hand per below).

**Recover:**

- Prefer the OpenShift GitOps UI **Sync** button (full sync, proper operation object) for hook re-runs.
- For the RHDH catalog specifically, the hook's output can be converged by hand: fetch `catalog/all.yaml` at the synced revision, apply the same placeholder replacements as `generate-rhdh-catalog.yaml` (Dev Spaces route, empty RHDH URL, revision), and `oc patch` the `catalog-runtime-rhdh` ConfigMap in `rhdh`.
- Related fix (committed 2026-07-13, refined 2026-07-14): the generate hook resolves the revision as `status.operationState.syncResult.revision` first (what the operation actually synced), then `status.operationState.operation.sync.revision` (the in-flight request, which merge-patched partial operations can inherit stale from a previous explicit-revision sync), then `status.sync.revision` (which still holds the previous revision while an operation runs).

## Argo CD Reports Synced But New Manifests Are Missing

**Affected stage:** any

**Likely cause:** The Argo CD repo-server can serve a stale manifest cache for a revision, especially right after quick successive pushes. The app reports Synced at the new revision while resources added in that revision were never rendered or applied. A normal refresh does not bust the manifest cache.

**Diagnose:**

```bash
# Compare what git has against what Argo tracked
kustomize build gitops/stages/<stage>/base | grep <new-resource>
oc get application <stage> -n openshift-gitops -o json \
  | jq -r '.status.resources[] | "\(.kind) \(.namespace)/\(.name)"' | grep <new-resource>
```

**Recover:**

```bash
oc annotate application <stage> -n openshift-gitops \
  argocd.argoproj.io/refresh=hard --overwrite
# Auto-sync does not refire for an already-seen revision; trigger it:
oc patch application <stage> -n openshift-gitops --type=merge \
  -p '{"operation":{"initiatedBy":{"username":"operator"},"sync":{"prune":true}}}'
```

## Operator CSV Not Succeeded

**Affected stage:** Any operator install stage

**Likely cause:** InstallPlan pending, catalog issue, insufficient permissions, or dependency operator not ready.

**Diagnose:**

```bash
oc get subscription,csv,installplan -A
oc describe subscription <name> -n <namespace>
oc describe installplan <name> -n <namespace>
```

**Recover:**

- If install approval is manual, approve the InstallPlan.
- If the package or channel is unavailable, confirm the package manifest in `openshift-marketplace`.
- Re-run the stage validation after the CSV reaches `Succeeded`.

## GPU Nodes Do Not Appear

**Affected stage:** Stage 020

**Likely cause:** MachineSet provisioning delay, cloud quota issue, instance type unavailable, or Machine API failure.

**Diagnose:**

```bash
oc get machineset -n openshift-machine-api | grep -i gpu
oc get machine -n openshift-machine-api | grep -i gpu
oc get nodes -l node-role.kubernetes.io/gpu
oc describe machineset <gpu-machineset> -n openshift-machine-api
```

**Recover:**

- Wait if machines are still provisioning.
- Check cloud quota and instance availability.
- Inspect Machine API events.
- Re-run `./stages/020-gpu-infrastructure-private-ai/validate.sh`.

## Kueue Or GPUaaS Queue Resources Are Missing

**Affected stage:** Stage 020

**Likely cause:** Red Hat build of Kueue Operator has not completed installation, the `Kueue` CR is not reconciled yet, the Stage 020 `maas` namespace or `LocalQueue` failed to sync, or the Kueue API version/channel differs in the target cluster.

**Diagnose:**

```bash
oc get subscription,csv,installplan -n openshift-kueue-operator
oc get kueue cluster -n openshift-kueue-operator -o yaml
oc get resourceflavor,clusterqueue
oc get localqueue -n maas
oc get namespace maas -o jsonpath='{.metadata.labels.kueue\.openshift\.io/managed}{"\n"}'
oc get datasciencecluster default-dsc -o jsonpath='{.spec.components.kueue.managementState}{"\n"}'
oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications \
  -o jsonpath='{.spec.dashboardConfig.disableKueue}{"\n"}'
```

**Recover:**

- Wait for the Kueue CSV to reach `Succeeded`.
- Confirm the `kueue-operator` package and configured channel are available in `redhat-operators` for the cluster release. On the current OpenShift 4.20 demo cluster, Stage 020 uses `stable-v1.3`.
- If the `maas` namespace or `LocalQueue` is missing, re-sync the `020-gpu-infrastructure-private-ai` Argo CD Application before deploying Stage 030.
- Re-run `./stages/020-gpu-infrastructure-private-ai/validate.sh`.

## Demo Was Restarted With Zero GPU Nodes

**Affected stage:** Stage 020 and Stage 030

**Likely cause:** The GPU MachineSet was intentionally scaled to zero for cost saving. Kueue queue resources persist, but private model pods cannot be admitted and run until GPU capacity returns. During model rollout, old ReplicaSets can also keep Kueue reservations in a two-GPU demo environment.

**Diagnose:**

```bash
./scripts/resume-gpu-demo.sh status
```

**Recover:**

```bash
./scripts/resume-gpu-demo.sh resume
```

The recovery script syncs Stage 020, scales GPU capacity back up, waits for allocatable GPUs, validates GPUaaS, syncs Stage 030, clears stale old model ReplicaSets if needed, waits for private models, and validates Stage 030.

## Worker Nodes Evict Pods After A Cluster Resume (KubeNodeEviction)

**Affected stage:** platform-wide (observed via Stage 030 model routing and Stage 050 components)

**Symptom:** `KubeNodeEviction` fires shortly after a sandbox cluster resume. Node events show `NodeHasDiskPressure` and `EvictionThresholdMet ... Attempting to reclaim ephemeral-storage` on CPU worker nodes, and a wave of pods across unrelated namespaces lands in `Failed` with reason `Evicted` (observed live 2026-07-14: GitOps repo-server, RHOAI dashboard, Perses, Thanos, NooBaa, Authorino, Dev Spaces server, SonarQube, kuadrant operator, among others). Secondary failures look like their own incidents — Argo CD syncs abort with repo-server restarts, Dev Spaces workspace postStart hooks time out.

**Likely cause (two components):**

(a) **Fixed cost — modelcar images on CPU workers:** the llm-d `*-kserve-router-scheduler` pods are CPU-side components, but by operator design they carry the full modelcar image as an init container and a sidecar (the KV-cache-aware tokenizer reads the model files). Each served model therefore pins its entire model image (~30–37 GiB for the demo's Nemotron/Qwen modelcars) on whichever CPU worker the router-scheduler landed on — and image GC can never reclaim it because the image is in use. These are NOT relocatable: `LLMInferenceService.spec.router.scheduler` has no scheduling fields (toleration, nodeSelector, affinity), so they cannot be co-located with the GPU nodes that already hold the model images.

(b) **The grower — Prometheus emptyDir TSDBs:** four Prometheus replicas (2 platform + 2 UWM) with emptyDir TSDBs on the three workers grow in lockstep. After a cluster resume, eviction → churn → new-series creates a feedback loop that amplifies disk pressure.

**FIXED** by `gitops/stages/030-.../monitoring/base/` volumeClaimTemplates (gp3-csi; platform 2×40Gi 7d/8GB, UWM 2×20Gi 7d/5GB), which moves the TSDB growth off ephemeral storage. The modelcar cost remains fixed.

**Diagnostic gold:** `oc get --raw /api/v1/nodes/<node>/proxy/stats/summary` returns per-pod ephemeral storage usage — use this to identify which pods dominate `/var` on a suspect worker.

**Note:** limitador counters are in-memory: a restart resets all usage-metrics counters (subscriptions, rate limits, token limits).

**Diagnose:**

```bash
# Which nodes hit the threshold, and for which resource?
oc get events -n default --field-selector reason=EvictionThresholdMet

# Disk headroom on a suspect worker
oc debug node/<node> -q -- chroot /host df -h /var

# Confirm the modelcar is the dominant image on that node
oc debug node/<node> -q -- chroot /host crictl images | sort -k7 -h | tail -5

# Which router-scheduler pinned it there
oc get pods -n models-as-a-service -o wide | grep router-scheduler
```

**Recover:**

- The pressure usually clears on its own: kubelet image GC plus the evictions reclaim space, and workloads reschedule. Verify no node still reports `DiskPressure` in `oc describe node`.
- Delete the evicted pod husks (`oc get pods -A --field-selector status.phase=Failed`) — controllers have already replaced them, and the husks keep the alert noisy.
- Do not chase the evicted components individually: a repo-server crash or a workspace postStart timeout during the wave is a symptom, not a separate incident.
- If a worker stays above ~85% on `/var`, prune unused images (`oc debug node/<node> -- chroot /host crictl rmi --prune`) — the in-use modelcar itself cannot be reclaimed. Longer-term options are tracked in `BACKLOG.md` (bigger worker disks or co-locating router-schedulers with the GPU nodes that already hold the model images).

`TaintManagerEviction` events around the resume timestamp are a different, benign artifact: nodes briefly go NotReady while the sandbox restores and the taint manager clears leftover pods (for example finished pipeline pods in `coolstore-dev`).

## Private Models Do Not Produce Kueue Workloads

**Affected stage:** Stage 030

**Likely cause:** Red Hat OpenShift AI 3.4 documents Kueue queue enforcement for `InferenceService`, `Notebook`, `PyTorchJob`, `RayCluster`, and `RayJob`. This demo uses `LLMInferenceService`; Kueue `Workload` creation for that resource must be validated in the live environment.

**Diagnose:**

```bash
oc get llminferenceservice -n maas --show-labels
oc get workloads.kueue.x-k8s.io -n maas
oc get events -n maas --sort-by=.lastTimestamp | tail -30
```

**Recover:**

- Treat missing `Workload` objects as a warning unless the demo is explicitly relying on Kueue admission for `LLMInferenceService`.
- Keep the `kueue.x-k8s.io/queue-name=private-model-serving` labels on the model resources so the manifests remain aligned with the GPUaaS operating model.
- For a strict queue-enforcement demo, add a small supported workload type such as a labeled `Job` or officially documented OpenShift AI `InferenceService` as a separate validation asset.

## MaaS Tab Shows No Models

**Affected stage:** Stage 040

**Likely cause:** the Red Hat OpenShift AI MaaS controller or `maas-api` deployment is not ready, the `models-as-a-service/default-tenant` reconciliation failed, `MaaSModelRef` resources are not ready, or the dashboard feature flags have not been reconciled after an operator upgrade. In RHOAI 3.4 environments, also check that the MaaS `Config/default` anchor exists and that the `redhat-ods-applications/maas-db-config` secret is present. Without the database connection secret, the operator-managed `maas-api` service can exist with no backing endpoint, which makes the dashboard tab appear empty.

**Diagnose:**

```bash
oc get deployment maas-api -n redhat-ods-applications \
  -o jsonpath='{.spec.template.spec.containers[0].image}{"\n"}'

oc get dsc default-dsc \
  -o jsonpath='{.status.conditions[?(@.type=="ModelsAsServiceReady")].status}{" "}{.status.conditions[?(@.type=="ModelsAsServiceReady")].reason}{"\n"}'

oc get tenant default-tenant -n models-as-a-service \
  -o jsonpath='{.status.phase}{" "}{.status.conditions[?(@.type=="Ready")].reason}{"\n"}'

oc get config.maas.opendatahub.io default
oc get secret maas-db-config -n redhat-ods-applications
oc get endpoints maas-api -n redhat-ods-applications

oc get maasmodelref -n maas
oc get externalmodel -n maas
```

**Recover:**

If the `maas-controller` or `maas-api` deployment was created by an older demo workaround, delete the stale deployment and let the Red Hat OpenShift AI 3.4 operator recreate it:

```bash
oc delete deployment maas-controller -n redhat-ods-applications
oc delete deployment maas-api -n redhat-ods-applications
oc annotate dsc default-dsc \
  recovery.rhoai-demo.io/restarted-at="$(date -u +%Y-%m-%dT%H:%M:%SZ)" --overwrite
oc rollout status deployment/maas-controller -n redhat-ods-applications
oc rollout status deployment/maas-api -n redhat-ods-applications
```

Then re-run:

```bash
argocd app sync 040-governed-models-as-a-service
./stages/040-governed-models-as-a-service/validate.sh
```

## Observability Dashboard Shows No Dashboards Found

**Affected stage:** Stage 010 and Stage 040

**Likely cause:** The RHOAI observability stack, dashboard feature flag, Kuadrant observability, or MaaS telemetry is missing; the Perses operator cannot reach the `redhat-ods-monitoring` Perses backend; or the dashboard user cannot list Perses dashboard resources. In current sandbox clusters, OLM can install the Perses operator in `openshift-operators` while the generated backend NetworkPolicy only allows the historical observability operator namespace. If the Usage tab opens but the panels are empty, the Tenant might be collecting MaaS metrics without the `user` label required by the generated dashboard queries.

**Diagnose:**

```bash
oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications \
  -o jsonpath='{.spec.dashboardConfig.observabilityDashboard}{"\n"}'

oc get kuadrant kuadrant -n kuadrant-system \
  -o jsonpath='{.spec.observability.enable}{"\n"}'

oc get tenant default-tenant -n models-as-a-service \
  -o jsonpath='{.spec.telemetry.enabled}{" "}{.spec.telemetry.metrics.captureUser}{" "}{.spec.telemetry.metrics.captureModelUsage}{"\n"}'

oc exec -n openshift-user-workload-monitoring prometheus-user-workload-0 -c prometheus -- \
  sh -c 'curl -sG http://localhost:9090/api/v1/query --data-urlencode query="authorized_hits{user!=\"\"}"' \
  | jq -r '.data.result | length'

oc get persesdashboard,persesdatasource -A

oc get persesdashboard dashboard-3-maas-usage-admin -n redhat-ods-applications \
  -o jsonpath='{.status.conditions[?(@.type=="Available")].status}{" "}{.status.conditions[?(@.type=="Available")].reason}{"\n"}'

oc get persesdashboard -A -l app.opendatahub.io/modelsasservice=true \
  -o custom-columns='NAMESPACE:.metadata.namespace,NAME:.metadata.name,TAB:.spec.config.display.name'

oc get pods -n openshift-operators -l app.kubernetes.io/name=perses-operator

oc auth can-i list persesdashboards.perses.dev \
  --as=ai-admin --as-group=rhoai-admins --as-group=rhoai-users \
  -n redhat-ods-applications

oc auth can-i list persesdashboards.perses.dev \
  --as=ai-admin --as-group=rhoai-admins --as-group=rhoai-users \
  --all-namespaces

oc auth can-i get prometheuses/k8s --subresource=api \
  --as=ai-admin --as-group=rhoai-admins --as-group=rhoai-users \
  -n openshift-monitoring

oc auth can-i create prometheuses/k8s --subresource=api \
  --as=ai-admin --as-group=rhoai-admins --as-group=rhoai-users \
  -n openshift-monitoring
```

**Recover:**

```bash
oc apply -f gitops/stages/010-openshift-ai-platform-foundation/base/observability-operators/perses-backend-operator-access.yaml
oc apply -f gitops/stages/010-openshift-ai-platform-foundation/base/observability-operators/perses-dashboard-rbac.yaml
oc apply -f gitops/stages/040-governed-models-as-a-service/base/models-maas-crds/tenant.yaml
oc apply -f gitops/stages/040-governed-models-as-a-service/base/jobs/label-observability-dashboard-tabs.yaml

ts="$(date -u +%Y%m%d%H%M%S)"
oc get persesdashboard -A -o jsonpath='{range .items[*]}{.metadata.namespace}{" "}{.metadata.name}{"\n"}{end}' \
  | while read -r ns name; do
      oc annotate persesdashboard "$name" -n "$ns" \
        rhoai3.redhat.com/reconcile-ts="$ts" --overwrite
    done

oc get persesdatasource -A -o jsonpath='{range .items[*]}{.metadata.namespace}{" "}{.metadata.name}{"\n"}{end}' \
  | while read -r ns name; do
      oc annotate persesdatasource "$name" -n "$ns" \
        rhoai3.redhat.com/reconcile-ts="$ts" --overwrite
    done
```

If the dashboard page opens but only the Usage tab is visible, verify that the product-generated `dashboard-0-cluster-admin` and `dashboard-1-model` resources carry `app.opendatahub.io/modelsasservice=true`. Stage 040 applies that label through `job-label-observability-dashboard-tabs` so the OpenShift AI MaaS dashboard discovers the documented Cluster, Models, and Usage tabs without copying or replacing the operator-managed dashboards. The OpenShift AI observability frontend also filters the Cluster and Models tabs unless the user can `get` `prometheuses/api/k8s` in `openshift-monitoring`, and panel queries require `create` on the same subresource because Perses submits Prometheus queries with POST requests. Stage 010 grants those narrow checks to `rhoai-admins`.

After recovery, hard-refresh the OpenShift AI dashboard. The dashboard page should show the Cluster, Models, and Usage tabs; MaaS usage panels show non-zero data only after recent MaaS traffic exists in the selected time range.

## PrometheusOperatorRejectedResources Warning Alert Fires

**Affected stage:** Stage 010 (visible any time afterwards)

**Likely cause:** The Tempo operator, the Red Hat build of OpenTelemetry operator, and the RHOAI `odh-model-controller` ship ServiceMonitor resources that authenticate with `bearerTokenFile`. User-workload Prometheus prohibits file-system access from scrape configs and rejects those ServiceMonitors, which fires the warning alert. This is a known Operator SDK-era pattern in operator bundles, not a resource this repository owns or applies.

**Diagnose:**

```bash
oc logs -n openshift-user-workload-monitoring deploy/prometheus-operator \
  | grep -i rejected | tail -5
```

Expected offenders: `openshift-operators/tempo-operator-controller-manager-metrics-monitor`, `openshift-operators/opentelemetry-operator-metrics-monitor`, `redhat-ods-applications/odh-model-controller-metrics-monitor`.

**Impact and recovery:**

- Only the operators' own controller self-metrics are skipped. Demo telemetry (RHOAI MonitoringStack Prometheus, OpenTelemetry collector, Tempo traces, MaaS usage metrics) flows through `redhat-ods-monitoring` and is unaffected — Stage 010 validation covers it.
- Do not patch the ServiceMonitors; OLM and the operators reconcile them back. Treat the warning as benign for this demo and silence it in Alertmanager if it distracts from screenshots or demos. Track operator releases that migrate to `authorization`-based scrape configs.

## RHOAI Monitoring Prometheus Stuck In Init

**Affected stage:** Stage 010

**Likely cause:** The RHOAI 3.4 generated `MonitoringStack` can reference `Secret/prometheus-web-tls-ca` while the OpenShift service-ca injection path has created `ConfigMap/prometheus-web-tls-ca`. Without the Secret, the Prometheus pod waits on a missing volume and MaaS observability is not fully available.

**Diagnose:**

```bash
oc describe pod prometheus-data-science-monitoringstack-0 \
  -n redhat-ods-monitoring

oc get configmap prometheus-web-tls-ca -n redhat-ods-monitoring
oc get secret prometheus-web-tls-ca -n redhat-ods-monitoring
```

**Recover:**

Re-sync Stage 010 so the GitOps hook creates the Secret from the injected ConfigMap:

```bash
argocd app sync 010-openshift-ai-platform-foundation
./stages/010-openshift-ai-platform-foundation/validate.sh
```

## Gen AI Playground External Model Works But Local Models Fail

**Affected stage:** Stage 040

**Likely cause:** The Playground dashboard BFF requests a MaaS token and passes it to Llama Stack as request provider data. Llama Stack's `remote::vllm` provider prefers that request `vllm_api_token` over provider-specific environment tokens. If the selected MaaS token belongs to a subscription that does not include the local models, the local model request fails even though direct Llama Stack calls with provider environment tokens work.

**Diagnose:**

```bash
oc logs -n coding-assistant \
  -l app.kubernetes.io/instance=lsd-genai-playground --tail=200 | \
  grep -E "subscription .* does not include model|OpenAI response failed"

oc get maassubscription demo-models-subscription \
  -n models-as-a-service \
  -o jsonpath='{.spec.modelRefs[*].name}{"\n"}'

oc get tenant default-tenant \
  -n models-as-a-service \
  -o jsonpath='{.spec.telemetry.enabled}{"\n"}'
```

**Recover:**

- Re-sync Stage 040 so the product MaaS API route, `Tenant`, and `MaaSSubscription` are reconciled.
- Re-sync Stage 040 so the external-model PostSync hook expands `demo-models-subscription` to include `qwen3-6-35b-a3b`, `nemotron-3-nano-30b-a3b`, `gpt-4o`, and `gpt-4o-mini`.
- Avoid adding a second broad subscription with overlapping model refs. The MaaS controller generates token-rate-limit policy names per model, so overlapping subscriptions can create policy conflicts.

```bash
argocd app sync 040-governed-models-as-a-service
argocd app sync 050-approved-external-model-access

GENAI_PLAYGROUND_BFF_SMOKE_TEST=true \
./stages/050-approved-external-model-access/validate.sh
```

## AI Asset Endpoints MaaS API Key Dialog Shows An Empty Key

**Affected stage:** Stage 040

**Likely cause:** The Gen AI AI asset endpoints modal expects the generated credential in the response shape used by its current browser bundle. If the browser is still running an older cached bundle after the dashboard rolled, MaaS can still create a real API key while the modal displays an empty input.

**Diagnose:**

```bash
oc logs deployment/maas-api -n redhat-ods-applications --tail=100 | \
  grep -E 'Created API key|/v1/api-keys'

oc get tenant default-tenant -n models-as-a-service \
  -o jsonpath='{.spec.apiKeys.maxExpirationDays}{"\n"}'
```

The logs must show successful key creation, but must not print full API keys. Only prefixes, field names, and key lengths are acceptable in troubleshooting output.

**Recover:**

- Re-sync Stage 040 so the product MaaS API route and `Tenant` configuration are current.
- Hard-refresh the OpenShift AI browser tab so the browser uses the dashboard bundle that matches the live Gen AI backend.
- Generate a new one-time key.

```bash
argocd app sync 040-governed-models-as-a-service
./stages/040-governed-models-as-a-service/validate.sh
```

## MaaS Grafana Route Does Not Redirect To OpenShift OAuth

**Affected stage:** Stage 040

**Likely cause:** The Grafana Operator generated a Route for the Grafana service, but the route is not targeting the OAuth proxy sidecar or the Service CA certificate has not been issued yet. In this demo, the external Route must target `oauth-proxy` and use re-encrypt TLS.

**Diagnose:**

```bash
oc get route grafana-route -n grafana -o yaml
oc get serviceaccount grafana-sa -n grafana -o yaml
oc get secret grafana-oauth-proxy-tls -n grafana
oc get svc,endpoints,pods -n grafana -o wide
GRAFANA_HOST=$(oc get route grafana-route -n grafana -o jsonpath='{.spec.host}')
curl -k -s -o /dev/null -w '%{http_code}\n' "https://${GRAFANA_HOST}/"
```

**Recover:**

```bash
oc patch grafana grafana -n grafana --type=merge \
  -p '{"spec":{"route":{"spec":{"port":{"targetPort":"oauth-proxy"},"tls":{"termination":"reencrypt","insecureEdgeTerminationPolicy":"Redirect"}}}}}'

oc patch application 040-governed-models-as-a-service -n openshift-gitops \
  --type=merge -p '{"operation":{"sync":{}}}'
```

Expected unauthenticated response is HTTP `302` to OpenShift OAuth. Use an OpenShift bearer token when testing Grafana APIs directly.

## MaaS Grafana OAuth Login Returns 403 Invalid Account

**Affected stage:** Stage 040

**Likely cause:** The OAuth proxy is running with stale or malformed session configuration. The proxy must restrict access with the plain OpenShift group argument `--openshift-group=rhoai-users` and use the generated `grafana-oauth-session` Secret for browser session cookies. If Argo CD reverts a manual patch, the browser can reach OpenShift OAuth, authenticate `ai-admin`, and still return `403 Permission Denied`.

**Diagnose:**

```bash
oc get group rhoai-users -o yaml
oc get secret grafana-oauth-session -n grafana
oc get deployment grafana-deployment -n grafana -o jsonpath='{range .spec.template.spec.containers[?(@.name=="oauth-proxy")].args[*]}{.}{"\n"}{end}'
oc logs deployment/grafana-deployment -n grafana -c oauth-proxy --tail=100
```

The proxy args should include:

```text
--cookie-secret-file=/etc/oauth/session/session_secret
--openshift-group=rhoai-users
```

**Recover:**

```bash
oc annotate application 040-governed-models-as-a-service -n openshift-gitops \
  argocd.argoproj.io/refresh=hard --overwrite
oc patch application 040-governed-models-as-a-service -n openshift-gitops \
  --type=merge -p '{"operation":{"sync":{}}}'
oc wait --for=condition=complete job/job-configure-grafana-oauth -n grafana --timeout=180s
oc rollout status deployment/grafana-deployment -n grafana --timeout=180s
```

If a browser still has a failed OAuth session, clear the Grafana route cookies and sign in again as `ai-admin` or `ai-developer`.

## MaaS Grafana Dashboard Shows 401 Unauthorized

**Affected stage:** Stage 040

**Likely cause:** The Grafana datasource is still using the Git placeholder bearer token, or the `grafana-sa` service account is missing `cluster-monitoring-view`. The dashboard loads, but Prometheus-backed panels return `401 Unauthorized`.

**Diagnose:**

```bash
oc get clusterrolebinding grafana-sa-cluster-monitoring-view
oc get grafanadatasource prometheus -n grafana -o yaml
DATASOURCE_UID=$(oc get grafanadatasource prometheus -n grafana -o jsonpath='{.status.uid}')
oc exec deployment/grafana-deployment -n grafana -c grafana -- \
  curl -s -H "X-Forwarded-User: ai-admin" \
  "http://localhost:3000/api/datasources/uid/${DATASOURCE_UID}/resources/api/v1/query?query=up"
```

Do not print or commit the runtime bearer token value. If `secureJsonData.httpHeaderValue1` still contains `Bearer ${GRAFANA_SA_TOKEN}`, the Stage 040 token job has not completed or Argo CD has reverted the runtime field.

**Recover:**

```bash
oc annotate application 040-governed-models-as-a-service -n openshift-gitops \
  argocd.argoproj.io/refresh=hard --overwrite
oc patch application 040-governed-models-as-a-service -n openshift-gitops \
  --type=merge -p '{"operation":{"sync":{}}}'
oc wait --for=condition=complete job/job-configure-grafana-sa -n grafana --timeout=180s
oc rollout status deployment/grafana-deployment -n grafana --timeout=180s
./stages/040-governed-models-as-a-service/validate.sh
```

## MaaS Grafana Dashboard Shows No Data

**Affected stage:** Stage 040

**Likely cause:** Grafana can query Prometheus, but the MaaS Gateway metrics are not being scraped yet, the compatibility recording rule has not evaluated, or no governed MaaS traffic has occurred in the selected dashboard time range.

**Diagnose:**

```bash
oc get podmonitor maas-gateway-metrics -n openshift-ingress
oc get prometheusrule maas-dashboard-usage-metrics -n openshift-ingress
DATASOURCE_UID=$(oc get grafanadatasource prometheus -n grafana -o jsonpath='{.status.uid}')
oc exec deployment/grafana-deployment -n grafana -c grafana -- \
  curl -s -H "X-Forwarded-User: ai-admin" \
  "http://localhost:3000/api/datasources/uid/${DATASOURCE_UID}/resources/api/v1/query?query=sum%28authorized_hits%29"
```

**Recover:**

Generate a small amount of governed MaaS traffic, wait for the scrape and recording rule interval, then refresh the dashboard:

```bash
MAAS_HOST=$(oc get gateway maas-default-gateway -n openshift-ingress \
  -o jsonpath='{.spec.listeners[0].hostname}')
MAAS_KEY=$(oc get secret kai-api-keys -n openshift-mta \
  -o jsonpath='{.data.OPENAI_API_KEY}' | base64 -d)
curl -sk -H "Authorization: Bearer ${MAAS_KEY}" \
  "https://${MAAS_HOST}/models-as-a-service/nemotron-3-nano-30b-a3b/v1/models"
sleep 60
./stages/040-governed-models-as-a-service/validate.sh
```

## GuideLLM Load Test Does Not Run

**Affected stage:** Stage 040

**Likely cause:** The `ghcr.io/vllm-project/guidellm` image cannot be pulled, `kai-api-keys` is missing, the MaaS Gateway hostname is still a placeholder, or the target model is not ready.

**Diagnose:**

```bash
oc get gateway maas-default-gateway -n openshift-ingress \
  -o jsonpath='{.spec.listeners[0].hostname}{"\n"}'
oc get secret kai-api-keys -n openshift-mta
oc get maasmodelref -n maas
oc get jobs,pods -n maas -l app.kubernetes.io/name=guidellm-load-test
```

**Recover:**

```bash
GUIDELLM_MODEL=nemotron-3-nano-30b-a3b \
GUIDELLM_PROFILE=constant \
GUIDELLM_RATE=1 \
GUIDELLM_MAX_SECONDS=20 \
GUIDELLM_REQUESTS=5 \
GUIDELLM_OUTPUT_TOKENS=64 \
GUIDELLM_PROMPT="Explain why governed model access matters for enterprise software teams." \
./stages/040-governed-models-as-a-service/run-guidellm-load-test.sh
```

Set `GUIDELLM_SKIP_LOAD_TEST=true` when you need Stage 040 structural validation without exercising the model endpoint.

## MaaS Gateway Is Not Reachable

**Affected stage:** Stage 040

**Likely cause:** Gateway hostname or HTTPS listener not patched, route not admitted, or gateway policy not ready.

**Diagnose:**

```bash
oc get gateway maas-default-gateway -n openshift-ingress -o yaml
oc get httproute -A | grep -i maas
oc get authpolicy,tokenratelimitpolicy -n maas
```

**Recover:**

- Confirm the Stage 040 PostSync jobs completed.
- Confirm the Gateway has an HTTPS listener with the expected cluster domain.
- Re-sync Stage 040 if the patch job did not run.

## Red Hat Developer Lightspeed for MTA Cannot Call MaaS

**Affected stage:** Stage 080

**Likely cause:** `kai-api-keys` contains placeholder values, the MaaS API key is invalid, or `llm-proxy` did not restart after secret patching.

**Diagnose:**

```bash
oc get secret kai-api-keys -n openshift-mta -o jsonpath='{.data.OPENAI_API_BASE}' | base64 -d
oc get secret kai-api-keys -n openshift-mta -o jsonpath='{.data.OPENAI_API_KEY}' | base64 -d
oc get deployment llm-proxy -n openshift-mta -o yaml
oc logs deployment/llm-proxy -n openshift-mta --tail=100
```

**Recover:**

- Re-run or re-sync Stage 080 so the PostSync job provisions the MaaS key and restarts `llm-proxy`.
- Confirm `./stages/080-ai-autonomous-migration/validate.sh` reports the MaaS credential checks as passing.

## MTA OpenShift Login Does Not Appear

**Affected stage:** Stage 080

**Likely cause:** OAuthClient redirect URI not patched, Keycloak identity provider not configured, or MTA route not available when the PostSync job ran.

**Diagnose:**

```bash
oc get oauthclient mta-keycloak -o yaml
oc get route mta -n openshift-mta
oc logs job/job-patch-mta-maas-url -n openshift-mta --tail=200
```

**Recover:**

- Re-sync Stage 080.
- Confirm the MTA route exists before the auth configuration job runs.
- Re-run Stage 080 validation.

## Red Hat Developer Hub OIDC Sign-In Fails With 504 Gateway Timeout

**Affected stage:** Stage 050

**Symptom:** The RHDH sign-in popup fails with `OPError: expected 200 OK, got: 504 Gateway Timeout` and `/api/auth/oidc/start` returns 500, while Keycloak itself is healthy — the OIDC discovery URL answers 200 from outside the cluster and even from a fresh process inside the RHDH pod.

**Likely cause:** The cluster was suspended and resumed (sandbox stop/start) and Keycloak restarted while the long-running RHDH backend process kept stale connection state toward the router. Every OIDC issuer discovery from the live process then gets 504 from the router, while fresh connections succeed. Observed live 2026-07-13 after a 06:16 UTC cluster resume; RHDH configuration, secrets, and the Keycloak client were all correct.

**Diagnose:**

```bash
# 1. Keycloak discovery healthy from outside? (expect 200)
curl -sk -o /dev/null -w "%{http_code}\n" \
  "https://$(oc get route mta -n openshift-mta -o jsonpath='{.spec.host}')/auth/realms/mta/.well-known/openid-configuration"

# 2. RHDH backend still failing on every sign-in attempt?
oc logs deployment/backstage-developer-hub -n rhdh --tail=200 | grep -i "OPError\|504"

# 3. Did Keycloak restart more recently than RHDH?
oc get pod mta-rhbk-0 -n openshift-mta \
  -o jsonpath='{.status.containerStatuses[0].state.running.startedAt}{"\n"}'
oc get pods -n rhdh
```

If check 1 returns 200 while check 2 shows fresh `Issuer.discover` 504 errors, the fault is stale state inside the running RHDH process, not the configuration — do not rotate secrets or re-run the configure hook.

**Recover:**

```bash
oc rollout restart deployment/backstage-developer-hub -n rhdh
oc rollout status deployment/backstage-developer-hub -n rhdh --timeout=600s
```

Then retry sign-in; `/api/auth/oidc/start` should answer 302 (redirect to Keycloak). Expect this after any overnight cluster suspend — bounce RHDH as part of demo-day preparation after a cluster resume.

## Developer Hub Topology/CI/Kubernetes Tabs Show "Problem Retrieving Kubernetes Objects"

**Affected stage:** Stage 050

**Symptom:** The Kubernetes-backed entity tabs show a warning banner; expanding it reveals `FETCH_ERROR ... reason: self-signed certificate in certificate chain` for every object query, while cluster discovery (the cluster dropdown) works and the Argo CD card is fine.

**Likely cause:** RHDH bootstraps `global-agent` (proxy support), which by default (`GLOBAL_AGENT_FORCE_GLOBAL_AGENT=true`) routes every https request through its own agent and **discards the kubernetes plugin's per-request agent** — so neither `skipTLSVerify: true` nor `caFile`/`caData` in the cluster config ever reach the TLS handshake. Reproduced both ways in-pod 2026-07-13: the identical fetch succeeds without global-agent, fails with it, and succeeds again once the cluster CA is in Node's trust store. This is why the upstream reference config in `tmp/ocp-app-platform-demo-developer-hub-config` resorted to pod-wide `NODE_TLS_REJECT_UNAUTHORIZED=0` — avoid that; it disables TLS validation for ALL RHDH egress.

**Recover:** add the cluster CA to Node's trust store. Two pieces are needed because the RHDH operator sets `automountServiceAccountToken: false` (the usual `/var/run/secrets/.../ca.crt` path does not exist in the pod):

```yaml
# backstage.yaml (CR): mount the namespace kube-root-ca.crt ConfigMap
extraFiles:
  configMaps:
    - name: kube-root-ca.crt
      mountPath: /opt/app-root/src/k8s-ca

# backstage.yaml (CR): trust it process-wide (adds trust; nothing disabled)
extraEnvs:
  envs:
    - name: NODE_EXTRA_CA_CERTS
      value: /opt/app-root/src/k8s-ca/ca.crt

# app-config kubernetes cluster entry (correct per docs; kept although
# global-agent bypasses it — harmless once NODE_EXTRA_CA_CERTS is set)
caFile: /opt/app-root/src/k8s-ca/ca.crt
```

Diagnose the underlying access independently of the plugin with:

```bash
oc auth can-i list pods --as=system:serviceaccount:rhdh:rhdh-kubernetes-reader -A
oc exec deployment/backstage-developer-hub -n rhdh -c backstage-backend -- \
  sh -c 'echo ${RHDH_KUBERNETES_SA_TOKEN:+token-present}'
```

## Red Hat Developer Hub Catalog Does Not Load Coolstore

**Affected stage:** Stage 050

**Likely cause:** RHDH backend is not allowed to read the raw GitHub catalog URL, the catalog location is not reachable, or `RHDH_CATALOG_URL` does not match the GitOps revision deployed by Argo CD.

**Diagnose:**

```bash
oc logs deployment/backstage-developer-hub -n rhdh --tail=200 | grep -i catalog
oc get configmap app-config-rhdh -n rhdh -o yaml
oc get secret rhdh-secrets -n rhdh -o jsonpath='{.data.RHDH_CATALOG_URL}' | base64 -d; echo
oc get application 050-advanced-app-platform -n openshift-gitops \
  -o jsonpath='{.spec.source.repoURL}{" "}{.spec.source.targetRevision}{"\n"}'
```

Look for errors like:

```text
is not allowed. You may need to configure an integration for the target host, or add it to backend.reading.allow
```

**Recover:**

- Add a narrow `backend.reading.allow` entry or configure the GitHub integration.
- Re-sync Stage 050 so the configure hook derives `RHDH_CATALOG_URL` from the live Argo CD Application source.
- Confirm the Stage 050 hook ServiceAccount can `get` `applications.argoproj.io` in `openshift-gitops`.
- Restart the RHDH deployment.
- Re-run Stage 050 validation after adding catalog checks.

## Red Hat Developer Hub Is Healthy But Stage 050 Is OutOfSync

**Affected stage:** Stage 050

**Likely cause:** Operator-defaulted fields differ from Git, or PostSync jobs patched dynamic fields.

**Diagnose:**

```bash
oc get application 050-advanced-app-platform -n openshift-gitops -o json \
  | jq -r '.status.resources[]? | select(.status != "Synced") | [.kind,.namespace,.name,.status,.message] | @tsv'

oc get backstage developer-hub -n rhdh -o yaml
```

**Recover:**

- Make Git match stable operator defaults where possible.
- Add narrow `ignoreDifferences` only for dynamic cluster-specific values.
- Avoid ignoring the full Backstage spec.

## Red Hat OpenShift Dev Spaces Workspace Does Not Start

**Affected stage:** Stage 060

**Likely cause:** DevWorkspace operator issue, image pull problem, insufficient workspace resources, or postStart command failure.

**Diagnose:**

```bash
oc get devworkspace -A
oc get pods -n wksp-ai-developer
oc describe devworkspace getting-started-ai-coding -n wksp-ai-developer
oc describe devworkspace coolstore-inventory-service -n wksp-ai-developer
oc describe devworkspace mca-coolstore -n wksp-ai-developer
oc logs -n wksp-ai-developer <workspace-pod> -c tooling-container --tail=100
```

**Recover:**

- Restart the workspace from the Red Hat OpenShift Dev Spaces dashboard.
- Confirm resource requests/limits are sufficient.
- Re-run Stage 060 validation.

## Kilo Code Is Missing From A Dev Spaces Workspace

**Affected stage:** Stage 060

**Likely cause:** The workspace was started from an older DevWorkspace spec that predates the Kilo Code extension policy, or the workspace did not restart after the `DEFAULT_EXTENSIONS` policy changed.

**Diagnose:**

```bash
oc get devworkspace getting-started-ai-coding -n wksp-ai-developer -o yaml \
  | grep -E 'DEFAULT_EXTENSIONS|kilo-code'

POD=$(oc get pod -n wksp-ai-developer \
  -l controller.devfile.io/devworkspace_name=getting-started-ai-coding \
  -o jsonpath='{.items[0].metadata.name}')

oc exec -n wksp-ai-developer "$POD" -c tooling-container -- \
  ls ~/.kilo-code/ 2>/dev/null && echo "Kilo Code config present"
```

**Recover:**

- Sync Stage 050 so each DevWorkspace sets the current `DEFAULT_EXTENSIONS` policy with the Kilo Code extension.
- Stop and restart the affected workspace from the Dev Spaces dashboard, or patch `spec.started` to `false` and then back to `true`.
- Confirm the Kilo Code sidebar appears in Che Code and that the MaaS configuration has been rendered by the init script.

## Kilo Code Cannot Reach MaaS Endpoint

**Affected stage:** Stage 060

**Likely cause:** The `devspace-ai-tools-init` ConfigMap init script did not run or failed to render the Kilo Code configuration with the correct MaaS base URL and API key. The workspace may have started before the MaaS key provisioner completed, or the `devspace-maas-key-provisioner` ServiceAccount lacks authorization on the `rhoai-developers-coding-models` subscription.

**Diagnose:**

```bash
POD=$(oc get pod -n wksp-ai-developer \
  -l controller.devfile.io/devworkspace_name=getting-started-ai-coding \
  -o jsonpath='{.items[0].metadata.name}')

oc logs -n wksp-ai-developer "$POD" -c tooling-container --tail=200 \
  | grep -iE 'kilo|maas|api.key|init'

oc get secret -n wksp-ai-developer -l app.kubernetes.io/part-of=devspaces-maas
```

**Recover:**

- Confirm the MaaS key Secret exists in the workspace namespace.
- Restart the workspace so the init script re-renders tool configuration.
- If the key Secret is missing, re-run `stages/050-advanced-app-platform/deploy.sh` to re-provision keys.

## Coding Assistant Project Is Missing From OpenShift AI Projects

**Affected stage:** Stage 080

**Likely cause:** The `coding-assistant` namespace was created before the Stage 080 Argo CD Application reconciled its namespace metadata, or Argo CD was configured to ignore namespace labels and annotations. OpenShift AI shows accessible OpenShift projects in the Projects page when they carry the dashboard project metadata and the user has suitable RBAC.

**Diagnose:**

```bash
oc get namespace coding-assistant \
  -o jsonpath='{.metadata.labels.opendatahub\.io/dashboard}{" "}{.metadata.annotations.openshift\.io/display-name}{"\n"}'

oc get rolebinding ai-developer-edit ai-admin-admin -n coding-assistant
```

**Recover:**

```bash
oc label namespace coding-assistant opendatahub.io/dashboard=true --overwrite
oc annotate namespace coding-assistant \
  openshift.io/display-name="Coding Assistant" \
  openshift.io/description="AI-assisted development with governed MaaS and MCP context" \
  --overwrite

oc annotate application 060-mcp-context-integrations -n openshift-gitops \
  argocd.argoproj.io/refresh=hard --overwrite
./stages/060-mcp-context-integrations/validate.sh
```

## MaaS Gateway Times Out On Every Path (RHCL 1.4.x Drift)

**Affected stage:** Stage 040 (breaks every AI consumer: Kilo Code, key provisioning, app LLM calls)

**Symptoms (observed live 2026-07-10):** `curl https://maas.<apps-domain>/maas-api/v1/models` returns 000 from outside AND from in-cluster pods (even via the gateway Service ClusterIP); the `maas-default-gateway-*` envoy pod shows repeated OOMKills and logs `Unknown field ... 'allow_on_headers_stop_iteration'` wasm config rejections.

**Likely cause:** the cluster drifted past the RHCL 1.3.z pin — a shared `openshift-operators` Manual InstallPlan bundled the kuadrant family (rhcl/authorino/limitador/dns) to 1.4.x when some other operator's plan was approved. RHCL 1.4.0-line is deprecated with documented gateway instability/memory pressure (see the `rhcl-update` skill).

**Diagnose:**

```bash
oc get csv -n openshift-operators | grep -E "rhcl|authorino|limitador|dns-oper"
oc logs deploy/maas-default-gateway-data-science-gateway-class -n openshift-ingress --tail=10
```

**Recover (documented 1.3.z rollback; OLM cannot downgrade in place):**

1. `oc delete csv rhcl-operator.v1.4.x authorino-operator.v1.4.x limitador-operator.v1.4.x dns-operator.v1.4.x -n openshift-operators`
2. Delete the four kuadrant Subscriptions (gitops names are OLM-style: `<pkg>-stable-redhat-operators-openshift-marketplace`, plus `rhcl-operator`).
3. Re-sync Stage 040 so Argo recreates the pinned Manual Subscriptions.
4. Delete any leftover unapproved 1.4.x InstallPlan, then approve the plan whose `clusterServiceVersionNames` lists ONLY the pinned 1.3.x set.
5. Verify: all four CSVs Succeeded; `curl .../maas-api/v1/models` returns 401 (serving, auth required) instead of 000.
6. **The operator rollback is not sufficient by itself** (observed live): 1.4-rendered Istio artifacts persist and requests carrying a valid-format API key hang forever in the filter chain (dummy keys 403 instantly — they never reach the rate-limit callout). Delete the rendered artifacts and let the 1.3 operator re-render, then restart the gateway:

   ```bash
   oc delete wasmplugin kuadrant-maas-default-gateway -n openshift-ingress
   oc delete envoyfilter kuadrant-auth-maas-default-gateway \
     kuadrant-ratelimiting-maas-default-gateway \
     kuadrant-maas-default-gateway -n openshift-ingress
   oc rollout restart deployment kuadrant-operator-controller-manager -n openshift-operators
   # wait for the WasmPlugin + EnvoyFilters to be recreated, then:
   oc rollout restart deployment maas-default-gateway-data-science-gateway-class -n openshift-ingress
   ```

   Verify with a real key: `curl -H "Authorization: Bearer <key>"
   .../models-as-a-service/<model>/v1/models` answers in milliseconds.

## Operator Subscription Claims A CSV That No Longer Exists

**Affected stage:** any OLM operator (observed live 2026-07-10 on devworkspace-operator: webhook server CrashLoopBackOff for 26h with `serviceaccounts "devworkspace-controller-serviceaccount" not found`)

**Likely cause:** the Subscription's `status.installedCSV` references a CSV object that was deleted (e.g., during catalog churn or manual cleanup). OLM will not reinstall because the Subscription believes the operator is installed; dependent workloads (controller Deployment, ServiceAccounts) are gone.

**Diagnose:**

```bash
oc get subscription <sub> -n <ns> -o jsonpath='{.status.installedCSV}{" / state: "}{.status.state}'
oc get csv <that-csv> -n <ns>   # NotFound = orphaned subscription
```

**Recover:** back up the Subscription spec, delete it, and recreate it clean (same channel/source; drop or update `startingCSV`). OLM resolves fresh and reinstalls. Argo-managed subscriptions are recreated by a stage re-sync.

## A Namespace Label Added In Git Never Reaches The Cluster

**Affected stage:** any Argo-managed namespace (observed live 2026-07-13: `coolstore-dev` missing `rhoai3.redhat.com/pipeline-project=true`, so the project-provisioner CronJob completed with "No project namespaces labeled" and never distributed pipeline credentials, while the 050 Application reported Synced).

**Likely cause:** the stage Application ignores Namespace metadata diffs (`ignoreDifferences: /metadata/labels` + the `RespectIgnoreDifferences=true` sync option). Ignored fields are excluded from sync patches, so a label added to an *existing* namespace manifest is never applied — labels from git only land when Argo first creates the namespace. Because the diff is ignored, the app stays Synced and self-heal never notices.

**Diagnose:**

```bash
oc get ns <ns> -o jsonpath='{.metadata.labels}'   # label missing live
git show HEAD:<path>/namespace.yaml                # label present in git
oc get application <app> -n openshift-gitops -o json \
  | jq '.spec.ignoreDifferences[] | select(.kind=="Namespace")'
```

**Recover:** apply the label imperatively (`oc label ns <ns> key=value --overwrite`). For labels a controller depends on (like the pipeline-project provisioning label), the stage deploy.sh must assert the label on every run — see `seed_coolstore` step 0 in stage 050.

## OpenCode: "unknown certificate verification error" for Every Model

**Affected stage:** Stage 070 (OpenCode workspaces)

**Symptom:** OpenCode fails on *every* model (MiniMax, Qwen, Nemotron) with `Error: unknown certificate verification error`. The request never reaches the MaaS gateway (no access-log entry). Kilo Code and the VS Code Kubernetes tabs keep working against the same endpoint.

**Likely cause:** OpenCode embeds Bun, and **Bun 1.3.0 stopped trusting the system CA store by default** ([oven-sh/bun#23735](https://github.com/oven-sh/bun/issues/23735)). The MaaS gateway serves the cluster's ingress (Let's Encrypt) certificate, whose chain root lives in the OS trust store but not in Bun's embedded Mozilla roots — so Bun rejects it. Kilo Code / VS Code are unaffected because Electron uses the OS trust store. The platform never set a CA env for OpenCode because it relied on Bun's pre-1.3 default of reading the system store; the "always-latest OpenCode" policy (`ensure_opencode_latest` + `autoupdate`) silently moved onto a Bun 1.3.x build.

**Diagnose:**

```bash
# In the workspace terminal:
strings ~/.opencode/bin/opencode | grep -m1 -aoE 'bun-v[0-9.]+'   # >= 1.3.0
grep 'certificate verification' ~/.local/share/opencode/log/opencode.log
# curl (system store) trusts it, opencode (Bun) does not:
curl -sSI https://<maas-host>/ >/dev/null && echo "OS store: OK"
```

**Recover:**

- **Durable (platform):** `init-ai-tools.sh` exports `NODE_USE_SYSTEM_CA=1` into `~/.bashrc` alongside the opencode PATH block, so every workspace start trusts the gateway. See `gitops/stages/050-.../devspaces/maas-api-key-provisioning.yaml` (`ensure_opencode_latest`). Applies on a fresh workspace/PV.
- **Immediate (running workspace):** quit OpenCode, then `export NODE_USE_SYSTEM_CA=1 && opencode` — the new server inherits it.
- **Do NOT** use `NODE_EXTRA_CA_CERTS` (broken on Bun 1.3.x — [oven-sh/bun#24581](https://github.com/oven-sh/bun/issues/24581)) or `NODE_TLS_REJECT_UNAUTHORIZED=0` (Bun's `fetch` ignores it, and it disables verification entirely).

## Kilo Code Shows "Move Your OpenCode Configuration"

**Affected stage:** Stage 060

**Likely cause:** Kilo Code detects an OpenCode-schema config and offers to adopt it. Dismissal is stored in VS Code `globalState`. Kilo-only workspaces (coolstore, getting-started) have no triggers after the self-scoping. Scaffolded 070 workspaces show it once on first open — just close the notification.

**Recover:** dismiss the notification. It does not reappear in the same workspace volume.

## MaaS Gateway Returns 429

**Affected stage:** Stage 040 (affects all downstream consumers)

**Likely cause:** token-rate-limit budget for the subscription/user/model/hour combination has been exhausted. Each `MaaSSubscription` carries per-model token-rate-limit entries (e.g. 1M tokens/hour for coding-tier models).

**Diagnose:**

```bash
oc get tokenratelimitpolicy -n models-as-a-service
oc get maassubscription -n models-as-a-service -o yaml | grep -A5 tokenRateLimit
```

**Recover:**

- Wait for the hourly window to roll over, or
- adjust the limit in `gitops/stages/040-.../base/policies/` files and re-sync Stage 040. The coding tier uses 1M tokens/hour per model.

## ose-cli curl Version Does Not Support --retry-all-errors

**Affected stage:** any stage using Job-based hook scripts with `curl`

**Likely cause:** the `ose-cli` image ships curl 7.61, which does not support `--retry-all-errors` (added in curl 7.71). Hook Job scripts that retry on transient failures must use `--retry` alone or a shell loop instead of `--retry-all-errors`.

**Recover:** replace `--retry-all-errors` with `--retry <n>` (retries on connection errors and some HTTP errors) or wrap in a shell retry loop with explicit HTTP status checks.

## API-Key Admin Cleanup Path

**Affected stage:** Stage 040

**Symptom:** orphaned or revoked MaaS API keys need to be cleaned up, but the search endpoint is non-trivial.

**Admin cleanup commands:**

```bash
MAAS_HOST=$(oc get gateway maas-default-gateway -n openshift-ingress \
  -o jsonpath='{.spec.listeners[0].hostname}')
ADMIN_KEY="<admin-api-key>"

# List all keys (returns {"object":"list","data":[...]})
# Note: the name filter parameter is ignored — filter client-side.
# Results include revoked keys and keys from other identities.
curl -sk -H "Authorization: Bearer ${ADMIN_KEY}" \
  "https://${MAAS_HOST}/maas-api/v1/api-keys" | jq '.data[] | {id, name, identity, revoked}'

# Delete a specific key by ID (works cross-identity as admin)
curl -sk -X DELETE -H "Authorization: Bearer ${ADMIN_KEY}" \
  "https://${MAAS_HOST}/maas-api/v1/api-keys/{id}"
```

**Recover:** use the commands above to identify and delete orphaned keys. The search API ignores the `name` query parameter and returns all keys visible to the admin identity — always filter the JSON response client-side.

## Argo CD Reports Synced But The Cluster Has Stale Manifests

**Affected stage:** any (observed twice on 2026-07-15: 050 ConfigMap, 040 LLMInferenceService)

**Symptom:** the Application shows `Synced`/`Succeeded` at the correct git revision, but a resource in the cluster lacks the change; the sync result message says `<resource> unchanged`.

**Likely cause:** the Argo CD repo-server served a stale cached render for the new revision.

**Diagnose:** compare the local render against the live object:

```bash
oc kustomize gitops/stages/<app path> | grep <your change>
oc get <kind> <name> -n <ns> -o yaml | grep <your change>
```

If git and the local render have the change while the live object does not — and the app claims Synced at the right SHA — it is the stale cache.

**Recover:** hard refresh, then sync:

```bash
oc annotate application <app> -n openshift-gitops \
  argocd.argoproj.io/refresh=hard --overwrite
```

Auto-sync apps re-sync on their own after the refresh; manual apps need a Sync click. Root cause in the repo-server cache is not yet identified.

## Model Rollout Deadlocks With The New Pod SchedulingGated

**Affected stage:** Stage 040 (any LLMInferenceService config change while GPU quota is fully allocated)

**Symptom:** after a spec change, the new kserve pod sits in `SchedulingGated` with gates `kueue.x-k8s.io/admission`; the old pod keeps running. The Kueue Workload says `insufficient unused quota for nvidia.com/gpu ... 1 more needed`.

**Likely cause:** rolling update with replicas=1 while the ClusterQueue's GPUs are all admitted — the new pod cannot get quota until the old one releases it, and the old one waits for the new one to become ready.

**Recover:** delete the old pod to free its GPU:

```bash
oc get workload -n models-as-a-service | grep <model>
oc delete pod -n models-as-a-service <old-kserve-pod>
```

Kueue admits the gated pod immediately; expect the usual model load time. If a crash-looping pod holds the quota (bad config baked into its spec), delete that one — its ReplicaSet will not recreate it once the new ReplicaSet's pod is admitted and ready.

## Pipeline Or Workspace Pods Evicted For Ephemeral Storage

**Affected stage:** any pipeline or workspace scheduling onto a modelcar-hosting CPU node

**Symptom:** a TaskRun fails with `The node was low on resource: ephemeral-storage`; the node sits at ~85% disk with kubelet image GC oscillating at the threshold.

**Likely cause:** cached container images — multi-GB modelcars plus accumulating build/task images. Per-pod ephemeral usage is usually innocent (verify via the node's `stats/summary`).

**Recover:** prune unused images on the pressured node:

```bash
oc debug node/<node> -- chroot /host sh -c 'crictl rmi --prune'
```

Caveats: `--prune` never removes in-use images (a modelcar backing a running scheduler stays); if the debug pod itself fails with "container not available", the node is too full to pull the tools image — wait for kubelet GC to free a little headroom and retry. `DeadlineExceeded` errors on large image deletions are harmless. Structural fix: the 200GiB worker-disk resize (backlog).

## SonarQube Gate Fails On new_coverage 0% Despite Passing Tests

**Affected stage:** Stage 060 (any Quarkus app in the pipeline)

**Symptom:** `new_violations` is 0, tests run green in `maven-build`, yet the gate fails `new_coverage: 0.0 < 80`.

**Likely cause:** the application produces no coverage report — SonarQube reads "no data" as 0%. Prompting an AI (or a human) for more tests changes nothing.

**Recover:** wire coverage into the build. For Quarkus: `io.quarkus:quarkus-jacoco` dependency (test scope) plus `<sonar.coverage.jacoco.xmlReportPaths>target/jacoco-report/jacoco.xml</sonar.coverage.jacoco.xmlReportPaths>` in the pom (coolstore fix: `7236899`). A plain jacoco-maven-plugin agent fights Quarkus class transformation — use the extension.

## Usage Dashboard Shows Zeros Or Gaps (Limitador PodMonitor Churn)

**Affected stage:** Stage 040 observability

**Symptom:** the RHOAI Observability Usage tab intermittently shows zero tokens; `authorized_hits` instant queries return no data while limitador's own `/metrics` endpoint has the counters.

**Likely cause (two distinct):**

1. Before the first Kuadrant reconcile enables observability, no `kuadrant-limitador-monitor` PodMonitor exists at all — nothing scrapes the per-user metrics.
2. The kuadrant-operator deletes and recreates that PodMonitor every ~10 minutes on its resync (log signature: `event logger ... eventTypes:{"delete":1}` followed by `ObservabilityReconciler "create object" v1.PodMonitor`), causing brief scrape gaps. RFE candidate.

Also verify the boring explanation first: a short "Last 30 minutes" window with genuinely no model traffic correctly shows zeros — check `sum(increase(authorized_hits[30m]))` in Thanos before suspecting the pipeline.

**Recover:** for (1), ensure `spec.observability.enable: true` on the Kuadrant CR (it is, in git) and wait for the operator reconcile. For (2), no configuration fix exists on our side; widen the dashboard time window.

## External Models Missing From Per-Model Token Consumption

**Affected stage:** Stage 040 observability

**Symptom:** `minimax-m2` and `qwen3-235b` never appear in the Usage tab's Token Consumption table even during active use.

**Likely cause:** the ExternalModel route policy exports request counters with subscription/user labels but no `model` label and no token-usage counters — the wasm usage-extraction pass (`--enable-force-include-usage`
+ model descriptor) is wired only for LLMInferenceService kserve routes in
this RHOAI 3.4 MaaS build. Enforcement is intact (request limits + defined token budgets); per-model token visibility is not. RFE candidate.

**Diagnose:**

```bash
oc port-forward -n kuadrant-system svc/limitador-limitador 18080:8080 &
curl -s http://localhost:18080/metrics | grep minimax
```

**Recover:** no platform-side fix; track via the subscription-level counters and the maas-rhdp provider's own accounting.

## External Model Streaming Resets Through The MaaS Gateway ("Connection reset by server")

**Affected stage:** Stage 040 external models (minimax-m2, qwen3-235b, gpt-4o-mini)

**Symptom:** streaming chat completions through the gateway stall (client sees nothing for ~60s, then "Connection reset") or die mid-stream around 310KB; the identical request sent directly to the upstream provider completes cleanly. Short non-streaming requests work.

**Root cause (RHOAI 3.4 known issue):** Ingress Payload Processing (IPP) — the operator-owned `payload-processing` ext_proc (gateway-api-inference- extension BBR) — buffers response bodies (`response_body_mode: FULL_DUPLEX_STREAMED`) for ALL gateway traffic, to translate non-OpenAI-native external APIs into OpenAI-compatible SSE. In 3.4 that response processing is applied even to already-OpenAI-compatible traffic, so streamed SSE is held and arrives as one end-of-response burst; the client (OpenCode's Bun `fetch`) times out at ~60s. Internal vLLM models and the external endpoints hit directly both stream fine — the buffer is purely this stage. Red Hat KB: "MaaS streaming responses buffered through gateway (RHOAI 3.4)"; product fix planned for 3.5.

**Diagnose:**

```bash
GW=$(oc get pods -n openshift-ingress -l gateway.networking.k8s.io/gateway-name=maas-default-gateway -o jsonpath='{.items[0].metadata.name}')
# Envoy access log: 200 DC downstream_remote_disconnect, bytes_sent 0, ~60s duration
oc logs -n openshift-ingress "$GW" -c istio-proxy --since=30m | grep chat/completions | tail -3
# IPP present on the gateway (count > 0 = active); compare stream direct-to-endpoint (works) vs via gateway (buffers)
oc exec -n openshift-ingress "$GW" -c istio-proxy -- pilot-agent request GET config_dump | grep -c ext_proc.bbr
```

**There is NO viable RHOAI 3.4 gateway fix for clusters that use external models.** All three approaches were tested live on 2026-07-20 and each is worse than the buffering — do NOT re-attempt them:

| Attempt | Result |
|---|---|
| KB `ipp-disable` — separate EnvoyFilter, `operation: REMOVE` the bbr filter | **External models 404** — they need BBR for body-based routing + API-key injection. The KB is explicitly "internal models only (no External Models)." |
| Separate filter, `MERGE` `response_body_mode: NONE` + `SKIP` | No-op — `NONE` is the protobuf zero-value a MERGE silently drops — AND the resulting `FULL_DUPLEX_STREAMED`+`SKIP` listener is invalid → istiod NACK → **gateway crashloop** (all MaaS down). |
| Separate filter, `REPLACE` bbr with `response_body_mode: NONE` | **All traffic 504** — breaks the ext_proc full-duplex contract; `failure_mode_allow: false` then fails every request. |

**Resolution (RHOAI 3.4):** do NOT patch the gateway; never edit the operator-owned `payload-processing` filter (the MaaS controller reverts it). Use **internal** models (`qwen3-6-35b-a3b`) for streaming-dependent flows (OpenCode's spec-kit cycle) — they stream cleanly. External models (`minimax-m2`, `qwen3-235b`) stay usable for **non-streaming / short** requests. Apply the product fix on the RHOAI 3.5 upgrade (BACKLOG).

## Red Hat Registry Outage Starves Scaffolded-Project Provisioning

**Affected stage:** Stage 050/070 (project-provisioner, seed runs, any pipeline building from UBI base images)

**Symptom:** freshly scaffolded projects get no credentials and no seed PipelineRun; the provisioner CronJob's `lastSuccessfulTime` stops advancing; pods show `ErrImagePull` with `503 Service Unavailable` from registry.redhat.io, or a seed run fails at `build-and-push` with `502 Bad Gateway` from registry.access.redhat.com.

**Likely cause:** transient Red Hat registry outage. The provisioner ran `ose-cli:latest` with the implicit Always pull policy, so every 2-minute tick required a live registry even though nodes cache the image (fixed: `imagePullPolicy: IfNotPresent`, `631c8be`).

**Diagnose:**

```bash
oc get cronjob project-provisioner -n app-platform-build -o jsonpath='{.status.lastSuccessfulTime}'
oc get pods -n app-platform-build | grep provisioner
curl -s -o /dev/null -w '%{http_code}' https://registry.access.redhat.com/v2/
```

**Recover:** nothing to fix once the registry returns — provisioning self-heals on the next tick. If a seed run failed mid-outage, delete it; the zero-runs guard re-seeds automatically:

```bash
oc delete pipelinerun <name>-seed-<hash> -n <name>-dev
```

Stuck pre-fix Jobs (pull policy Always baked into their pods) must be deleted for the CronJob to mint fresh ones.

## Scaffolded Project Does Not Self-Provision (No Argo CD App / Pipeline)

**Affected stage:** Stage 050 (RHDH scaffolder → dispatcher bootstrap)

**Symptom:** a developer creates a project from the "New Quarkus App" template; the GitHub repo is created (with topics `rhoai3-golden-path` + `rhoai3-scaffolded`) and pushed, but no `project-<repo>` Argo CD Application appears, no `<repo>-dev` namespace or `app-push` pipeline is created, and no build runs. Nothing is happening in the background.

**Root cause:** the self-provisioning flow has NO per-repo webhook — it relies on the **GitHub App** delivering push events to the shared `app-platform-listener` dispatcher. The tell for every variant below is an **EventListener with zero recent activity** (`oc logs` the `el-app-platform-listener-*` pod shows nothing for the repo) even though the repo and its push exist on GitHub.

1. **Stale webhook URL (the #1 fresh-env cause).** A GitHub App has a SINGLE, App-level webhook URL. It is cluster-specific — it embeds the cluster's ingress domain (`…apps.<cluster>.<base-domain>`). When you redeploy the demo to a NEW cluster, GitHub keeps delivering to the OLD cluster's route until you update the App's webhook URL. Symptom: NOTHING provisions (not even the platform coolstore repo builds on push), because every delivery lands on a dead/previous cluster. Confirm in GitHub → the App → **App settings → Advanced → Recent Deliveries**: the target URL won't match this cluster, and/or deliveries fail. Fresh-env redeploys almost always hit this.
2. **Selected-repositories scope.** If the App is installed on *Only select repositories*, a newly scaffolded repo is outside its scope, so ITS pushes don't deliver (but the pre-seeded golden repos still do). Check GitHub → the App → **Configure → Repository access = All repositories**.

**Diagnose:**

```bash
# 1. Repo created with the scaffolded topic? (should be present)
gh api repos/<owner>/<repo> --jq '.topics'
# 2. Did the dispatcher receive ANYTHING? (empty output = webhook never arrived)
EL=$(oc get pods -n app-platform-build -l eventlistener=app-platform-listener -o name | head -1)
oc logs -n app-platform-build $EL --since=30m | grep -i "<repo>"
# 3. No per-repo webhook exists (delivery is App-only by design):
gh api repos/<owner>/<repo>/hooks --jq 'length'   # 0
```

**Fix — re-point the App webhook URL to THIS cluster (do this on every fresh deploy):** GitHub → the App → **App settings → General → Webhook → URL**, set it to the current route:

```bash
echo "https://$(oc get route app-platform-listener -n app-platform-build -o jsonpath='{.spec.host}')"
```

Keep the secret equal to `.env` `GITHUB_WEBHOOK_SECRET` (verify: `oc get secret github-webhook-secret -n app-platform-build -o jsonpath='{.data.token}' | base64 -d`). Then **Advanced → Recent Deliveries → Redeliver** a recent push, or push a commit. Also confirm **Repository access = All repositories** so scaffolder-created repos are in scope. This webhook-URL step is the piece most easily missed on a fresh env — the `.env` swap re-points the *cluster*, but the App's single endpoint still points at the previous cluster until you change it in GitHub.

Validate one live scaffold end-to-end afterwards: the dispatcher CEL filter matches on `body.repository.topics`; if topics turn out to be absent from the push payload on your GitHub, switch the trigger to a per-repo webhook created by the scaffolder template instead.

**Recover an already-created project without waiting for the App fix** (what to run for a repo that was scaffolded while the App was still on Selected repos):

```bash
# Create the bootstrap Argo CD Application the dispatcher would have created:
oc apply -f - <<'APP'
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: project-<repo>
  namespace: openshift-gitops
  labels: { rhoai3.redhat.com/scaffolded-project: "true" }
  finalizers: [ resources-finalizer.argocd.argoproj.io ]
spec:
  project: scaffolded-projects
  source:
    repoURL: https://github.com/<owner>/rhoai3-coding-demo
    targetRevision: main
    path: gitops/stages/050-advanced-app-platform/base/pipelines/project-pipeline
    kustomize: { namespace: <repo>-dev }
  destination: { server: https://kubernetes.default.svc, namespace: <repo>-dev }
  syncPolicy:
    automated: { prune: true, selfHeal: true }
    syncOptions: [ CreateNamespace=true ]
    managedNamespaceMetadata:
      labels:
        rhoai3.redhat.com/pipeline-project: "true"
        app.kubernetes.io/part-of: <repo>
APP
# Distribute build credentials immediately (else wait for the 2-min CronJob):
oc create job -n app-platform-build provisioner-now --from=cronjob/project-provisioner
# Verify: namespace Active, app-push pipeline present, github-basic-auth +
# quay-push-secret secrets present in <repo>-dev.
```

The pipeline still needs a push to build — fix the App scope (or seed a run) for that.

## References

- [OpenShift troubleshooting documentation](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/support/troubleshooting)
- [OpenShift GitOps documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/)
- [Red Hat OpenShift AI documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/)
- [Red Hat Developer Hub documentation](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9)
- [Migration Toolkit for Applications documentation](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.1)
