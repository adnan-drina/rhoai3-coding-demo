# Operations Guide

> **Foundation migration (2026-07-06):** stages 010-040 now import the
> validated rhoai3-demo foundation (former 050/060 folded into 040). Sections
> below that describe the pre-migration 010-060 implementation are historical
> until rewritten after the first migrated deployment.

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
- The cluster has enough capacity for GPU nodes and model-serving workloads. Specifically (AWS/RHPDS baseline): Stage 020's PreSync hook derives the GPU MachineSet from an existing **worker** MachineSet — so the cluster must have a worker pool whose region/AZ offers **`g6e.2xlarge` (NVIDIA L40S)** instances (the hook inherits the worker's AZ). The hook scales the worker pool to **4** (`m6a.4xlarge` or equivalent, ~16 vCPU / 64 GiB) and provisions **2** GPU nodes; a smaller cluster will not fit RHOAI + model-serving + RHDH + pipelines + Dev Spaces workspaces. On a non-AWS platform the derivation's GPU instance type must be adjusted in `provision-gpu-machineset.yaml`.
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

MCP integrations have their own prerequisites. Stage 040 includes the read-only OpenShift MCP server (uses ServiceAccount RBAC, no token needed). Slack and BrightData are credential-gated integrations. Set `SLACK_BOT_TOKEN` and `BRIGHTDATA_API_TOKEN` in `.env` when those integrations are approved; missing credentials produce validation warnings, not failures.

## Bootstrap

Run bootstrap once per cluster:

> **Cluster-local step (not in GitOps):** on AWS clusters, raise the default
> ingress ELB idle timeout or long-lived websockets (Dev Spaces IDE
> terminals) and LLM streams die at the AWS Classic ELB default of 60s:
>
> ```
> oc patch ingresscontroller default -n openshift-ingress-operator --type merge \
>   -p '{"spec":{"endpointPublishingStrategy":{"type":"LoadBalancerService","loadBalancer":{"scope":"External","providerParameters":{"type":"AWS","aws":{"type":"Classic","classicLoadBalancer":{"connectionIdleTimeout":"1h"}}}}}}}'
> ```
>
> The MaaS gateway's own ELB is covered in GitOps (`040 gateway.yaml`
> `infrastructure.annotations`); this patch covers the `*.apps` router.

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
./stages/050-advanced-app-platform/deploy.sh
```

Stages 060–080 are workflow-only (no deploy scripts, no Argo CD Applications of their own): stage 050 owns their infrastructure as components (identity, devspaces, pipelines, sonarqube, rhdh, mta). Validate their demo prerequisites with each stage's read-only `validate.sh`. Stage 050's deploy script provisions `app-platform-build` secrets from `.env` (`GITHUB_WEBHOOK_SECRET`, `GITHUB_TOKEN`) before applying the Application.

Each script applies one file from `gitops/argocd/app-of-apps/`. The ordered source of truth is `flows/default.yaml`.

| Stage | Argo CD app | Purpose |
|------|-------------|---------|
| 010 | `010-openshift-ai-platform-foundation` | OpenShift AI platform foundation |
| 020 | `020-gpu-infrastructure-private-ai` | NFD, GPU Operator, GPU MachineSets, Red Hat build of Kueue, queue quota, KEDA readiness |
| 030 | `030-private-model-serving` | Local private model serving |
| 040 | `040-governed-models-as-a-service` | MaaS control plane, gateway, governance, external models, MCP context |
| 050 | `050-advanced-app-platform` | Platform RHBK identity, Dev Spaces, webhook dispatcher + per-project pipelines + SonarQube gate, Developer Hub, Trusted Artifact Signer, MTA + Lightspeed, coolstore dev environment |
| 060 | *(workflow-only)* | AI-assisted development on stage 050 workspaces |
| 070 | *(workflow-only)* | AI-agentic development (OpenCode + skills) |
| 080 | *(workflow-only)* | AI-autonomous migration on the stage 050 MTA stack |

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

## Developer Workflow Branch Validation

Stages `100-170` are not part of [`../flows/default.yaml`](../flows/default.yaml) yet. When validating developer-workflow changes on a sandbox cluster, patch only the existing platform applications that own the affected live resources.

For Stage 060 vibe-coding changes, patch only Stage 060 and Stage 050 to the feature branch being validated:

```bash
oc patch application 060-ai-assisted-development -n openshift-gitops --type=merge -p '{"spec":{"source":{"targetRevision":"<feature-branch>"}}}'
oc patch application 050-advanced-app-platform -n openshift-gitops --type=merge -p '{"spec":{"source":{"targetRevision":"<feature-branch>"}}}'
oc annotate application 060-ai-assisted-development -n openshift-gitops argocd.argoproj.io/refresh=hard --overwrite
oc annotate application 050-advanced-app-platform -n openshift-gitops argocd.argoproj.io/refresh=hard --overwrite
```

Rollback to the stable platform branch:

```bash
oc patch application 060-ai-assisted-development -n openshift-gitops --type=merge -p '{"spec":{"source":{"targetRevision":"main"}}}'
oc patch application 050-advanced-app-platform -n openshift-gitops --type=merge -p '{"spec":{"source":{"targetRevision":"main"}}}'
oc annotate application 060-ai-assisted-development -n openshift-gitops argocd.argoproj.io/refresh=hard --overwrite
oc annotate application 050-advanced-app-platform -n openshift-gitops argocd.argoproj.io/refresh=hard --overwrite
```

Do not merge a feature branch to `main` only to validate developer workflow catalog or workspace changes. Do not create Stage `100-170` Argo CD applications until a workflow owns executable artifacts or dedicated cluster resources.

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

> **Historical numbering.** Entries below are point-in-time records and keep
> the stage numbering that was in effect when they were written (before the
> 2026-07-06 developer-arc restructure and the 2026-07-10 advanced-app-platform
> restructure). Do not renumber them. Current numbering lives in
> `flows/default.yaml`. Stage 090 (AI Self-Service Portal) was absorbed into
> Stage 050 during the 2026-07-10 renumbering; validation paths referencing
> `090-ai-self-service-portal` in entries before that date are historical.

### 2026-07-21 cluster-kjbwr: OLM shared-InstallPlan merge fixed (kuadrant install-then-unsubscribe); model scheduler co-location findings; all five stages green

Fresh-env deploy on cluster-kjbwr. Stages 010–050 all Synced/Healthy; 040 validation 75/0-fail, 050 validation 39/0-fail (RHDH allowed its ~15 min first-boot plugin init).

**OLM shared-InstallPlan merge blocked Stage 050 — root-caused and fixed reproducibly.** Pipelines + RHTAS could not install: OLM bundled the pinned-forbidden `rhcl-operator.v1.4.1` into their shared `openshift-operators` InstallPlan, which the trusted-delivery guard (correctly) refused (2026-07-10 incident policy). Root cause: RHCL's only channel (`stable`) heads at 1.4.x, so a standing Manual Subscription pends the MaaS-incompatible upgrade forever; because kuadrant (rhcl/authorino/dns/limitador) and pipelines/rhtas are all **AllNamespaces** operators sharing openshift-operators, OLM co-resolves every change into one plan. Namespace separation (Red Hat's documented remedy, KCS 6389681) is impossible here — two all-namespaces OperatorGroups make every namespace a member of two groups. **Fix:** replaced the standing kuadrant Subscriptions + rhcl approve-guard with one idempotent provisioning Job (`040-.../prerequisites/rhcl/base/provision-kuadrant.yaml`) that installs+pins the family then **deletes the Subscriptions**. CSVs / running operators persist (MaaS unaffected — models stayed Ready throughout); only OLM upgrade-tracking stops, which is the intent. With no kuadrant Subscription pending, OLM regenerated a clean `[rhtas v1.4.2, pipelines v1.22.4]` plan that auto-approved and completed. 040 validate now checks the pinned CSV is Succeeded **and** the Subscription is absent (the positive signal the pattern ran). This is the durable, reproducible form of the recurring 2026-07-06/-10/-14 "OLM bundled an unexpected CSV" incident class.

**Model router-scheduler disk co-location — two candidate fixes empirically rejected.** The llm-d `LLMInferenceService` stamps the 30-37 GiB modelcar onto the CPU router-scheduler pod (operator RFE) with no `ephemeral-storage` request, so kube-scheduler is disk-blind and can co-locate both models' schedulers on one ~100 GiB worker → `DiskPressure` eviction churn (which also evicted cluster-wide pods incl. the OLM approve jobs, compounding the 050 block). Tested and **reverted**: (a) `podAntiAffinity` via `spec.router.scheduler.template` — the field is a full pod-template *replace*, so an affinity-only template drops the operator-injected containers and the operator fails reconcile (`containers: Required value`); (b) a namespace LimitRange default `ephemeral-storage` request — the scheduler pods route through the RHOAI-managed `default` Kueue queue (covers cpu/memory only), so the request makes them Kueue-inadmissible, and covering it means mutating shared RHOAI state. Interim remediation that works: delete the co-located scheduler pod once its node is `DiskPressure`-tainted — the NoSchedule taint repels it to a clean worker (no cordon needed). Durable fixes remain BYO-EPP (`pool.endpointPickerRef`, drops the modelcar) or a 200 GiB worker disk resize — see BACKLOG. In practice with 4 CPU workers + 2 models the schedulers usually spread on their own; both models ended Ready and stable.

**RHDH first-boot recovered from a migration surge-race.** After the operators came up, Developer Hub stayed `0/1` (route 503) — the backend `Backend startup failed` on `relation "casbin_rule" already exists` / `"…public_keys…migrations_lock" already exists`. Root cause: the deployment strategy is `RollingUpdate` with `maxSurge: 1`, so a fresh-DB rollout brought up **two** backend pods that raced each other's Backstage per-plugin DB migrations and both crashed (not corrupted data — a pure concurrency collision, seeded by the configure-rhdh patch landing mid-first-boot). **Non-destructive fix:** `oc scale deploy backstage-developer-hub -n rhdh --replicas=0` then `--replicas=1` — a single pod runs migrations without a surge peer and starts clean (route 200, 1/1). Do NOT drop the `backstage_plugin_*` databases; the data was fine, only the concurrent start was the problem. **Durable fix (implemented, commit on 2026-07-21):** the Backstage CR now carries `spec.deployment.patch.spec.strategy.rollingUpdate.maxSurge: 0` (+ `maxUnavailable: 1`), so the operator's Deployment removes the old pod before starting the new one — only one migrator ever runs, on fresh deploys too. Note: `strategy.type: Recreate` does NOT work here — the operator merges it onto its base template but keeps the base `rollingUpdate` block, producing an invalid Deployment (`rollingUpdate may not be specified when type is 'Recreate'`) that the operator then refuses to apply, leaving RHDH with no Deployment at all. Use `maxSurge: 0`, not `Recreate`.

**Monitoring hygiene re-asserted.** The eviction churn regenerated four operator ServiceMonitors (kueue/nfd/odh-model-controller/lws) without `openshift.io/user-monitoring=false` and reset the Istio PodMonitor's metrics-port relabel → `PrometheusOperatorRejectedResources`/`TargetDown`. Re-applied the exclusions (deploy.sh `ensure_known_monitoring_noise_is_excluded` logic); alerts cleared. Note: these are imperative deploy.sh patches that operator regeneration can undo — a demo-prep re-check, not a durable guarantee.

### 2026-07-20 Fresh-env reproducibility: GitOps↔live drift audit; GPU MachineSet derivation; OpenCode CA fix; IPP streaming verdict

GitOps↔live drift audit ahead of a fresh-environment install.

**Models — reproducible, no drift.** Qwen 3.6 and Nemotron are both fully in GitOps (`040-.../local-models/{qwen,nemotron}-llminferenceservice.yaml`) with portable OCI model sources (`oci://registry.redhat.io/rhai/modelcar-…`), full vLLM specs, `replicas: 2`; the `040` app is Synced/Healthy. A fresh install brings up both models. (Live currently runs 1 GPU node / Qwen only — a temporary cost-saving scale-down, not the target state.)

**GPU MachineSet — was NOT reproducible; fixed.** The old `machineset-gpu.yaml` hardcoded cluster-specific infra (infra id, RHCOS AMI, subnet/SG filters, IAM profile, tags), so on any other cluster the filters match nothing and no GPU node provisions. Replaced it with a Stage 020 PreSync hook (`machineset/base/provision-gpu-machineset.yaml`) that **derives** the GPU MachineSet from the fresh cluster's own worker MachineSet — inheriting real infra — and applies only GPU overrides (g6e.2xlarge/L40S, GPU labels + `nvidia-gpu-only` taint, 200Gi disk, `replicas: 2`), and **scales the worker pool to 4**. Idempotent (worker scaled up only if <4; GPU MachineSet created only if absent, so `scripts/resume-gpu-demo.sh` scale-downs survive re-sync). Created MachineSets carry `argocd.argoproj.io/compare-options: IgnoreExtraneous` so Stage 020's prune+selfHeal never deletes the GPU node. Migration on the live cluster: the pre-existing Argo-managed GPU MachineSet was annotated `IgnoreExtraneous` so the transition did not prune the running node.

**OpenCode CA fix (shipped earlier same day).** OpenCode embeds Bun, and Bun 1.3+ dropped default system-CA trust (oven-sh/bun#23735) → it rejected the MaaS gateway's ingress cert for every model. Fix: `NODE_USE_SYSTEM_CA=1` exported by the init script and set as a devfile container env. Verified end-to-end.

**IPP external-model streaming — no viable 3.4 fix (documented).** Streaming through the gateway is buffered for external models (KB "MaaS streaming responses buffered through gateway"). All three approaches tested live are worse (KB `ipp-disable` 404s external models; MERGE crashloops; REPLACE 504s) — see `docs/TROUBLESHOOTING.md`. Internal models stream fine; external models are non-streaming-only until RHOAI 3.5. **Decision: `qwen3-235b` and `minimax-m2` were removed from the deployment** (serving CRs, access-policy modelRefs, and OpenCode provider blocks/keys/`enabled_providers`) so a fresh install ships only working models; `gpt-4o-mini` kept (playground-only). Re-add both on the RHOAI 3.5 upgrade — see BACKLOG.



Stage 070 (OpenCode agentic development) went from known-gap to demo-ready in one day, validated by live scaffold cycles throughout.

Scaffold hardening (golden repo agentic-quarkus-scaffold, each fix found by a live run):

- OpenCode devfile wiring (`cb13ed8`): cli-ai-tools image + platform init-script postStart — factory workspaces previously got NO tool (only repo devfiles apply to factory starts; no platform CR carries wiring for them).
- quarkus-jacoco (`5ca6fb3`, the 060 lesson applied proactively) and the redhat-ga repository declaration (`d4a19bf` + structure fix) — the corporate BOM is not on Maven Central; a fresh namespace's cold-cache first build failed resolving the build extension.
- spec-kit pre-baked (`36c700b`): `specify init --integration opencode` committed — ten /speckit.* commands + .specify/ templates. The scaffold ships ONLY .specify/; spec-kit's own scripts create specs/ at runtime (SPECS_DIR is hardcoded upstream). Hand-rolled specs/TEMPLATE.md retired.
- Official Quarkus Agent MCP (`c845789`): pinned 1.2.3 native binary installed to the persistent volume, joins the generated OpenCode config next to openshift-mcp. Doc search needs a container runtime — workspace pods block nested podman twice over (no /dev/net/tun; crun proc-mount denied) — degraded gracefully, options in BACKLOG. The MCP stays workspace-local stdio BY DESIGN (project-scoped tools); do not centralize.

Template/platform:

- Per-run catalog links via a scaffolder catalog:fetch of the platform coolstore entity (`0ab27bb`) — no cluster hostname in git; link order in catalog/all.yaml is load-bearing. Proven on a live scaffold.
- fetch:template `replace: true` (`4527487`): skeleton files now overwrite golden-repo copies — without it the per-run devfile name never landed (fetch:template keeps existing files by default).
- Birth-certificate seed runs (`b7ef42f`): project-provisioner seeds exactly one app-push run per scaffolded project (guards: bootstrap Argo app exists, creds, pipeline, zero runs). The publish-time push races namespace creation by design, so first runs never materialized and CI tabs started empty. Self-healing: delete a failed seed and the next tick re-seeds.
- delete-scaffolded-project.sh: seven-surface teardown (workspace, optional volume wipe, catalog Location AND its location entity in refresh_state — catalog:register creates TWO records and the entity keeps re-emitting the component; Argo app + namespace; SonarQube; GitHub repo via the user's gh oauth — `env -u GITHUB_TOKEN`, the pipeline PAT deliberately lacks delete_repo; Quay manual). macOS bash-3.2 portable.
- OpenCode current + governed (`585a120`): official installer to the persistent home (image binary is root-owned/stale), autoupdate on, `enabled_providers` allowlist restricts /models to the four MaaS providers. Kilo removed from 070 factory workspaces (`a3393b6`) — the namespace-wide editor recommendation was auto-installing it; every Kilo workspace installs explicitly, so removal is safe.

External-model streaming (IPP) fix:

- MiniMax "Connection reset" root-caused to RHOAI 3.4 Ingress Payload Processing buffering streaming responses (Red Hat KB confirms; fix in 3.5). Clients starve ~60s then reset; hard cut ~310KB. Fix deployed (`c54f7ec`): a separate non-operator-owned EnvoyFilter MERGEs response_body_mode NONE + response_trailer_mode SKIP onto the bbr filter — keeps request-side IPP that external models need (model resolution, API-key injection; all our providers are OpenAI- compatible so response translation is unnecessary). Trap recorded: NONE with trailer SEND breaks ALL external requests (504); never edit the operator-owned filter (controller reverts). Long streams now match direct-upstream latency. Recipe in TROUBLESHOOTING; BACKLOG pins removal on RHOAI 3.5.

Registry-outage resilience (registry.redhat.io / access 502/503 wave):

- The 2-minute provisioner starved on ose-cli:latest (implicit Always) despite node caches → `imagePullPolicy: IfNotPresent` (`631c8be`).
- A seed run died fetching the UBI base image; deleting the failed run let the next tick re-seed to green — the self-healing path working as designed on its first real incident.

Stage 070 exercise (`85ec059`..`b94114f`): 11-step coding-exercise.md around **coolstore-catalog** — spec-driven Quarkus rebuild of the original coolstore catalog-spring-boot behavior (reference clone in tmp/). Three spec-kit-shaped briefs in demo-assets: 001 product listing (original seed data; itemIds shared with the 060 inventory service), 002 availability from the deployed inventory service (spec-anchored evolution, cross-service integration), 003 optional AI search via MaaS (double-governance beat). Education step framed by Fowler's memory-bank/specs model with a seven-source go-deeper table; concepts precede the workspace tour. Framing per review: the gate STAYS — specs and skills improve the input, not replace inspection. Dry-run validated through step 3 live (template links, per-run naming, seed run green after the outage). quarkus-skills repo earmarked for stage 080 (migrate-spring-to-quarkus).

### 2026-07-15 Stage 060 validated end-to-end; model quality arc; governed embeddings; reset hardened

The full 12-step coding exercise ran live twice (demo + reset lifecycle). Every failure encountered was folded back into code, config, or docs the same day.

Model quality arc (Nemotron → Qwen default):

- Nemotron stalls mid-task in Kilo traced to tool calls leaking into the reasoning channel (Nano-class drift on multi-step agentic work). Serving config aligned to the RedHatAI/NVIDIA-Nemotron-3-Nano-30B-A3B-FP8 model card (`9d966b9`, `b6851e7`): `--max-num-seqs=8`, `--kv-cache-dtype=fp8`, tool-calling sampling default `temperature 0.6 / top_p 0.95` via `--override-generation-config`. Two documented L40S deviations: `--max-model-len` stays 131072 (48Gi vs the card's H100-80Gi), and `VLLM_USE_FLASHINFER_MOE_FP8` dropped — no FlashInfer FP8 MoE backend supports sm89; the engine crashes at startup (`c398076`). vLLM's own backend choice (Triton FP8 MoE) is correct for L40S.
- Sampling + a new always-provide-tool-arguments rule reduced but did not eliminate drift. Live head-to-head on the Module 1 generation prompt: Qwen3.6 35B one-shot clean where Nemotron drifted twice. **Qwen3.6 is now the Kilo default** (`ef4fe64`); Nemotron stays as the large-context local alternative. Rollout hit the GPU-quota rolling deadlock twice (see new TROUBLESHOOTING recipe).

Governed embeddings (Cursor-executed, audited):

- `granite-embedding-english-r2` (149M) serves on CPU workers via `vllm-cpu-rhel9:3.4.1` with `--runner=pooling` (no llm-d scheduler — it cannot route `/v1/embeddings`); registered in MaaS, added to `devspaces-coding-models` at 500K tokens/h, key minted into the workspace Secret (`5833f3d`, `79914c9`, `0a219eb`). Gateway smoke test: 768-dim vector, 11 tokens metered. Kilo codebase indexing can now be pointed at a governed embedder (wiring via `kilo-code.new.indexing.*` VS Code settings is backlog).

Workspace tooling:

- Kilo Code 7.4.8 (patch published same day, `e9e7be6`). The bump surfaced its commercial "Kilo Gateway" catalog plus z.ai models inside governed workspaces — suppressed via `disabled_providers: ["kilo", "zai"]` in the provisioned config (`22658cf`). **Treat `disabled_providers` as part of the governance surface: review it on every Kilo version bump.**
- Provisioned rules gained Markdown-formatting and tool-argument rules; all Kilo providers gained timeout/chunkTimeout parity with OpenCode; init script now configures git identity on fresh volumes and sweeps project-level `.continue` (`bf6ab32`, `11daafa`, `975d9b5`).

Stage 060 exercise redesign (validated live):

- The generation prompt is now a deliberately flawed specification (console printing, exception swallowing, field injection, plus a demand for unit tests) — smells are instructed, not hoped for, making the red gate deterministic with any obedient model. Lesson reframed: the model is not the weakest link; the specification is.
- Coverage lesson: the gate's `new_coverage >= 80%` condition could never pass — the app had no coverage tooling. `quarkus-jacoco` added to the coolstore pom (`7236899`). Final green run: 92.5% new-code coverage, 0 violations, deployed endpoint verified.
- Guide fully illustrated (17 live screenshots) with value-statement callouts adapted from the Parasol workshop, prompt-engineering theory (7 principles, 4 linked sources) in step 6, and an admin BONUS section on token-consumption observability (`bd3c503`).

Demo reset hardened:

- Live reset exposed two traps: resetting against a stale `golden` (order: bless golden FIRST), and SonarQube counting re-introduced baseline debt as new violations after a post-demo rewind. Fresh-sonar is now the reset default (`--keep-sonar` opts out, `b8bde43`). Baseline: `a55ace5` (landing page + jacoco, no stats endpoint). Reset validated end-to-end: rewind → fresh baseline analysis green → workspace recreated.

Observability findings:

- The Usage dashboard's per-user/subscription/model metrics come from a `kuadrant-limitador-monitor` PodMonitor the operator creates — and deletes/recreates every 10 minutes (RFE candidate; recipe recorded).
- External-model routes (`minimax-m2`, `qwen3-235b`) are enforced (request counters + defined token budgets) but export no `model` label and no token-usage counters — invisible in the per-model consumption view (RFE candidate; recipe recorded).
- Disk pressure struck a third time (cached images on the qwen modelcar node evicted a maven-build pod mid-demo); user added one CPU node; the 200GiB worker-disk resize is promoted on the backlog.

### 2026-07-14 (afternoon) AI assistant swap: Continue → Cline → Kilo Code; subscription rename

Actions:

- Completed the AI coding assistant swap in Dev Spaces workspaces: Continue (original) → Cline (interim) → Kilo Code (current). Kilo Code is now the primary IDE AI assistant installed as a default extension in all persona workspaces. OpenCode remains the terminal-based agentic assistant. GitHub Copilot is available as a third option but is not provisioned by the platform.
- Renamed the MaaS developer-tools subscription from `rhoai-developers-gpt-4o-mini` to `rhoai-developers-coding-models` to reflect multi-model developer tooling rather than a single model name. Manifests, validate scripts, and Stage 080 MaaS key references updated in the same commit.
- Lifecycle hardening: workspace init script updated for Kilo Code configuration rendering; Che Code editor default-extensions policy updated; `DEFAULT_EXTENSIONS` references updated in DevWorkspace specs.
- Documentation sweep: all stage READMEs (050, 060, 070, 080), root README, TROUBLESHOOTING, and BACKLOG updated to reference Kilo Code as the current assistant. Historical log entries preserved.

### 2026-07-14 (evening) Subscription restructure, external models, key lifecycle, Prometheus persistence

Actions:

- **Assistant saga completed:** Continue (EOL — Cursor acquisition) → Cline (rejected — 4.0.8 keeps provider config in VS Code `globalState`, not headlessly provisionable) → Kilo Code 7.4.7 (current). Key commits: `7307f2b` Cline in, `ab31efd` Kilo pivot, `6ad5253` MCP URL fix, `6e01e76` VSIX skip-guard.
- **Subscription restructure + Red Hat internal external models:** commits `153bd5d` + `2a753d9` and fix chain. Retired `rhoai-developers-coding-models` (renamed from the earlier `rhoai-developers-gpt-4o-mini`). New architecture: six purpose-built subscriptions (`devspaces-coding-models`, `mta-migration-models`, three personal subscriptions at priority 150, `developer-hub-models` reserved) plus `model-evaluation` and `ai-safety-guardrails`. Two Red Hat internal external models added: `qwen3-235b` (16K ctx) and `minimax-m2` (196K ctx) via LiteLLM proxy, ExternalModel + MaaSModelRef pattern, one shared key (`REDHAT_MODELS_API_KEY`).
- **Key lifecycle proven:** orphaned and test keys from earlier sessions reaped via `DELETE /maas-api/v1/api-keys/{id}` (admin cross-identity path).
- **Prometheus persistence fix:** commit `561c13a` (if present) — platform and UWM Prometheus replicas moved from emptyDir to gp3-csi volumeClaimTemplates (platform 2×40Gi 7d/8GB, UWM 2×20Gi 7d/5GB), resolving the growing component of the worker disk-pressure eviction feedback loop.

Validation evidence:

- Stage 040: 79 passed, 1 warning, 0 failed.
- Stage 050: 38 passed, 1 warning, 0 failed.
- Stage 060: 113 passed, 0 warnings, 0 failed.
- **Live proving:** all 5 models (Nemotron, Qwen-local, qwen3-235b, minimax-m2, gpt-4o-mini) accessible in GenAI Playground per-user subscriptions. Kilo Code: 4 governed providers + MCP `openshift` server tool-calling green.

### 2026-07-14 (morning) Post-resume eviction wave; OLM upgrade cleanup audited

Context: the sandbox cluster was resumed in the morning (GPU nodes are recreated on every resume). A separate assistant session worked the cluster and repo first (commits `015b605`, `586072d`, `d205da8`, `30369de`), including OLM surgery on two stuck operator upgrades.

Actions and findings:

- OLM audit after the other session's remediation (it deleted stuck NFD/DevWorkspace CSVs and InstallPlans and restarted OLM pods in `openshift-operators`): end state verified clean. All pins intact — `rhcl-operator.v1.3.5`, `authorino-operator.v1.3.2`, `limitador-operator.v1.3.1`, `dns-operator.v1.3.1`, `cluster-observability-operator.v1.4.0`, all Succeeded. Neither touched operator is pinned (NFD and DevWorkspace are `Automatic`); `devworkspace-operator.v0.42.0` and Dev Spaces 3.29.0 completed their upgrades (Succeeded).
- `KubeNodeEviction` root-caused: kubelet disk-pressure eviction wave on workers `ip-10-0-20-23` and `ip-10-0-32-234` (`EvictionThresholdMet ... ephemeral-storage`). Each node permanently holds a full modelcar image (30.5 GiB Nemotron / 36.7 GiB Qwen) pinned by the llm-d `*-kserve-router-scheduler` pods — CPU-side components that carry the modelcar as init container + sidecar and cannot schedule on the tainted GPU nodes. Post-resume restart churn plus fresh operator image pulls tipped both 100 GiB `/var` filesystems over the threshold. Evicted along the way: GitOps repo-server (the "repo-server crash" seen by the morning session), RHOAI dashboard, Perses (3x), Thanos, NooBaa, Authorino, Dev Spaces server, SonarQube, kuadrant operator, and others. Pressure cleared on its own (nodes at 80%/74% after image GC + evictions); model serving itself never left the GPU nodes. New recipe in TROUBLESHOOTING ("Worker Nodes Evict Pods After A Cluster Resume"), capacity watch item in BACKLOG. Evicted `Failed` pod husks (10) left for manual cleanup.
- Repo follow-ups from reviewing the morning session's commits: stage 050 `validate.sh` Dev Spaces links check updated for the direct `agentic-coolstore` workspace link (was still passing only on the retired factory URL), TROUBLESHOOTING catalog-hook recipe updated for the `syncResult.revision`-first resolution order.

### 2026-07-13 (evening) Phase C: scaffolded-project bootstrap live; catalog slimmed

Actions:

- Phase B closed out with a webhook-equivalence test: a signed synthetic push payload POSTed to the `app-platform-listener` Route produced `coolstore-inventory-service-push-zs2dx` in `coolstore-dev` — Succeeded (interceptor chain, cross-namespace dispatch, credentials, gate, image push, `:latest` retag all proven; only GitHub's own delivery leg was not re-exercised, it was proven pre-restructure).
- Catalog scope decision executed: `coolstore-inventory-service` is the one and only Component; `getting-started-ai-coding` and MCA `coolstore` removed from `catalog/all.yaml`. RHDH `orphanStrategy: delete` removed both live entities once the runtime catalog was regenerated (verified in the catalog database).
- Phase C delivered: template-published repos carry a `rhoai3-scaffolded` topic; the dispatcher's new bootstrap trigger creates a per-project Argo CD Application (source = this repo's `project-pipeline` base, kustomize-namespaced to `<repo>-dev`, `CreateNamespace` + `managedNamespaceMetadata` stamping the `pipeline-project` label), and a second topic-filtered trigger routes every push to an `app-push` PipelineRun in `<repo>-dev` via CEL overlay. Applications land in the new `scaffolded-projects` AppProject (platform repo source + `*-dev` destinations only). Scaffold pom aligned to the corporate Red Hat build of Quarkus BOM (3.27.3.SP1-redhat-00002) — requires a `bootstrap-golden-repos.sh` re-push of `agentic-quarkus-scaffold`.
- Live verification with a synthetic scaffolded push for `agentic-quarkus-scaffold`: bootstrap Application Synced/Healthy in seconds, namespace created with the provisioning label, provisioner distributed credentials on its next tick, and the follow-up push produced a fully green 6-task `app-push` run in `agentic-quarkus-scaffold-dev` (test stack removed afterwards; the auto-created `quay.io/rhoai3-coding-demo/agentic-quarkus-scaffold` image repository is demo debris that can be deleted in the Quay UI).
- Sync gotcha recurrence: the automated sync that picked up the pushed revision arrived as a PARTIAL operation rendered from a stale manifest cache — new trigger resources were neither applied nor listed until `argocd.argoproj.io/refresh=hard`; hooks stayed skipped, so the runtime catalog was converged by hand per the TROUBLESHOOTING recipe.

### 2026-07-13 Stage 050 per-project pipeline seeding after the restructure

Actions:

- After the per-project-pipelines restructure synced (all five Applications Synced/Healthy at `e3a473f`), `validate.sh` failed twice: no `sonarqube-credentials` in `coolstore-dev` and no green pipeline run there. Root cause: the `rhoai3.redhat.com/pipeline-project=true` label added to `coolstore-dev`'s manifest never reached the live namespace — the 050 Application ignores Namespace label diffs (`ignoreDifferences` + `RespectIgnoreDifferences=true`), so labels only land at namespace creation. The project-provisioner CronJob therefore found "No project namespaces labeled" and distributed nothing, while the Application reported Synced. New TROUBLESHOOTING recipe: "A Namespace Label Added In Git Never Reaches The Cluster".
- Fixed `deploy.sh`: `seed_coolstore` now asserts the provisioning label imperatively (step 0) and skips the seed only when the deployment is Available AND a green per-project run exists (previously a deployment left over from the retired shared pipeline was enough to skip, so the seed never ran).
- Re-ran `deploy.sh`: label applied, provisioner distributed `github-basic-auth`/`quay-push-secret`/`sonarqube-credentials`/ `app-platform-build-config` into `coolstore-dev`, seed PipelineRun (clone → maven → sonar gate → build/push → tag-latest) succeeded on the per-project `app-push` pipeline, deployment rolled onto the fresh `:latest`. `validate.sh`: 34 passed, 0 failed, 1 expected warning (Securesign arrives with a later phase).

### 2026-07-13 Stage 050 pre-validation check and RHDH OIDC recovery after cluster resume

Actions:

- Pre-work for manual stage 050 validation (RHDH access with the ai users, catalog state, golden-path templates): ran `validate.sh` (29 passed, 0 failed, 1 expected warning — Securesign instance arrives with a later phase), confirmed `ai-admin`/`ai-developer` OpenShift users exist for the Keycloak federated-identity pre-creation, confirmed the runtime catalog's three template Locations resolve to a pushed commit with no drift against `origin/main`, and confirmed all three golden repositories answer on GitHub.
- RHDH OIDC sign-in failed with `OPError ... 504 Gateway Timeout` after the sandbox cluster resumed at 06:16 UTC (Keycloak restarted; the RHDH backend process, up since before the suspend, kept failing issuer discovery while fresh connections from the same pod succeeded). Recovered with `oc rollout restart deployment/backstage-developer-hub -n rhdh`; `/api/auth/oidc/start` answers 302 afterwards. New recipe recorded in TROUBLESHOOTING ("Red Hat Developer Hub OIDC Sign-In Fails With 504 Gateway Timeout").
- Operator note (outside the cluster): quay.io offers no org-wide default visibility setting, so each pipeline-auto-created image repository is created private and must be flipped to Public manually (expect this step for new app images from the 070/080 flows).

### 2026-07-10 Stage 050 advanced-app-platform first live deploy (new numbering)

Actions:

- Deleted the five pre-restructure Argo CD Applications (no finalizers, so non-cascading) and deployed the consolidated `050-advanced-app-platform`.
- Fixed live and committed upstream: Subscription health lua gap (installed CSV with empty OLM `status.state` wedged wave 2), PVC health for WaitForFirstConsumer storage (unbound PVCs deadlocked wave 5), SonarQube image env contract (missing empty `LDAP_REALM`/`SONAR_SECURITY_REALM` crash-looped the web process).
- Repaired two pre-existing cluster faults: orphaned devworkspace-operator Subscription (CSV deleted; webhook server CrashLoopBackOff 26h) and the RHCL 1.4.x drift that killed the MaaS gateway at 08:50 (rolled back to the pinned 1.3.x set per the deprecation advisory; both procedures recorded in TROUBLESHOOTING).

Validation evidence:

- `050-advanced-app-platform` reached Synced/Healthy/Succeeded including all PostSync hooks (SonarQube admin rotation + scanner token + fail-on-new-issue default gate, RHDH OIDC, MTA MaaS hooks).
- MaaS gateway restored: `/maas-api/v1/models` answers 401 (serving) after the 1.3.x rollback; kuadrant CSVs at rhcl 1.3.4 / authorino 1.3.1 / limitador 1.3.1 / dns 1.3.1.
- End-to-end golden-path delivery chain FULLY GREEN: push to golden-path repo main → GitHub App webhook → EventListener (HMAC verified) → PipelineRun in seconds → clone → Maven build (warm cache: full run 1m38s) → SonarQube analysis + custom quality gate → buildah push to `quay.io/rhoai3-coding-demo/<app>:<sha>`, with quay auto-creating the repository via the org `pipeline` team's Creator role (robot `rhoai3-coding-demo+pipeline`). Fixes applied live along the way: coschedule=pipelineruns for dual PVC workspaces, image-provided mvn (build image lacks gzip for the wrapper), CEL topic scoping of the webhook. Note: org default repository visibility should be Public or auto-created image repos are private (pull secrets needed for deploys).
- Post-rollback follow-up: RHCL upgraded 1.3.4→1.3.5 to match the stage 040 guard; stale 1.4-rendered WasmPlugin/EnvoyFilters caused valid-key requests to hang in the gateway filter chain until deleted and re-rendered by the 1.3 operator (recipe extended in TROUBLESHOOTING); after cleanup, model-route requests answer in milliseconds.

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
- `bash -n scripts/*.sh stages/*/*.sh` passed.
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
| 070 AI-Assisted Development | Passed | `./stages/050-ai-assisted-development/validate.sh`: 18 passed, 0 warnings, 0 failed |
| 080 Autonomous Application Migration | Passed | `./stages/070-ai-autonomous-migration/validate.sh`: 22 passed, 0 warnings, 0 failed |
| 090 AI Self-Service Portal | Passed | `./stages/090-ai-self-service-portal/validate.sh`: 16 passed, 0 warnings, 0 failed |

Final sweep:

- All nine Argo CD Applications reported `Synced` and `Healthy` at commit `b5bb770`.
- A full live validation sweep from Stage 010 through Stage 090 completed without critical failures.
- Expected warnings remain for Stage 050 external inference because `OPENAI_API_KEY` was not set during the initial full sweep, and Stage 070 optional Slack/BrightData MCP runtimes because `SLACK_BOT_TOKEN` and `BRIGHTDATA_API_TOKEN` are not set. Later Stage 050 smoke validation passed after an approved provider key was provisioned.
- A GitOps hygiene sweep found no remaining Argo CD resources with `requiresPruning=true` after re-syncing Stage 090 hook resources.
- Merge-readiness static checks also passed: `git diff --check origin/main...HEAD`, `bash -n scripts/*.sh stages/*/*.sh`, and `./scripts/validate-stage-flow.sh`.
- Merge-readiness security check found no committed `.env` file and no real kubeadmin password, provider key, kubeconfig, bearer token, or private key in the branch diff. Only placeholder and masked key examples such as `sk-oai-*` were present.
- After merging PR #1, all canonical stage Argo CD Applications were repointed from `codex/stage-refactor-demo-validation` to `main` and reported `Synced` and `Healthy` at commit `ec2b4c1`. Stage 090 was reconfigured so `RHDH_CATALOG_URL` resolves to the `main` catalog URL, then Stage 090 validation passed with 16 checks, 0 warnings, and 0 failures. Later docs-only commits may advance Argo CD's displayed revision without changing managed stage resources.

Validation hardening pass:

- Validators now check demo-owned outcomes in addition to service readiness: GPU node allocatable capacity and taints, local model metadata and registry entries, generated MaaS routes/policies/token limits, external model endpoint and credential wiring, MCP service discovery and credential gating, Dev Spaces RoleBindings, MTA ConsoleLink, and RHDH OIDC/catalog configuration.
- `scripts/validate-lib.sh` now handles zero matching pods without producing a malformed `0 0` count.
- Hook Jobs are treated as non-durable operational evidence. Stage 030 validates the durable model registry contents instead of failing when the `model-registry-seed` hook Job has already been cleaned up.

GitOps hygiene pass:

- Broad `ignoreDifferences` entries were reduced where they hid demo-owned desired state. Operator-generated and cluster-specific fields remain ignored only where they are not useful GitOps ownership points.
- Stage 020 now records GPU Operator and Node Feature Discovery defaults in Git so Argo CD can manage those specs without broad masking.
- Hook delete policies now include `HookSucceeded` for stage manifests, which reduced stale hook resources and pruning noise.
- A regression was found while tightening Stage 040: the MaaS Gateway hostname and TLS certificate reference are intentionally patched from the cluster ingress domain and certificate. Removing the old broad Gateway spec ignore let Argo CD restore `maas.placeholder.example.com`, which caused the Stage 070 MTA MaaS hook to patch placeholder values into `Tackle` and `kai-api-keys`.
- Fix applied: Stage 040 now ignores only `/spec/listeners/0/hostname`, `/spec/listeners/1/hostname`, and `/spec/listeners/1/tls/certificateRefs/0/name` for `Gateway/maas-default-gateway`. The rest of the Gateway spec remains GitOps-managed.
- Fix applied: Stage 070 now fails fast if the discovered MaaS hostname still contains `placeholder`, preventing a bad hook run from overwriting runtime configuration with placeholder values.
- Final evidence after the fix: Stage 040 re-synced to the real `maas.apps.cluster-t977r.t977r.sandbox3022.opentlc.com` host, Stage 070 re-provisioned `kai-api-keys` with a real `sk-oai-*` MaaS key for the demo subscription, and Stages 040, 080, and 090 validated successfully.

Red Hat alignment review:

- Stage 040 is aligned with the Red Hat OpenShift AI 3.4 MaaS architecture in the core platform pattern: KServe-backed model serving, Gateway API, Red Hat Connectivity Link, Kuadrant/Authorino policy enforcement, API-key authentication, subscription/group-based access, rate limits, token limits, dashboard enablement, and GitOps-managed desired state. Red Hat OpenShift AI 3.4 documentation describes MaaS as subscription-based governance that replaces the 3.3 tier model, while several MaaS-adjacent paths still require conservative Technology Preview or Developer Preview language.
- Stage 040 deviations remain intentional and documented: gateway/AuthPolicy patches for the current dashboard-forwarded user token path and cluster-specific gateway hostname patching. The previous tokens bridge, upstream MaaS controller, `maas-api` image override, tier-based policy resources, and community Grafana add-on were removed for Red Hat OpenShift AI 3.4 alignment because they conflict with or duplicate operator-owned MaaS resources and subscription-based MaaS telemetry.
- Stage 070 aligns with Red Hat Developer Lightspeed for MTA guidance by using a centrally managed LLM provider configuration through MTA, the LLM proxy, and an OpenAI-compatible endpoint backed by Red Hat OpenShift AI/MaaS. Developer Lightspeed for MTA is also Technology Preview in the referenced MTA 8.1 documentation, so production-readiness language must stay conservative.
- Stage 090 aligns with Red Hat Developer Hub 1.9 operator guidance by using the `Backstage` custom resource, app config mounted from a ConfigMap, environment-substituted secrets, and `dynamic-plugins.yaml` mounted through `dynamicPluginsConfigMapName`.
- Fix applied from the alignment review: RHDH catalog configuration no longer hard-codes the `main` branch. `app-config-rhdh.yaml` now uses `${RHDH_CATALOG_URL}`, and the Stage 090 PostSync hook derives that URL from the live Argo CD Application `repoURL` and `targetRevision`. This keeps the developer portal catalog on the same Git revision as the deployed demo.
- Final evidence after the alignment fix: Stage 090 re-synced to commit `cff7e4a`; `RHDH_CATALOG_URL` resolved to `https://raw.githubusercontent.com/adnan-drina/rhoai3-coding-demo/codex/stage-refactor-demo-validation/gitops/stages/090-ai-self-service-portal/base/catalog/all.yaml`; Stage 090 validation passed with 16 checks, 0 warnings, and 0 failures; all nine Argo CD Applications reported `Synced` and `Healthy`.

Documentation and deviation-register cleanup:

- `BACKLOG.md` now treats workaround removal as a supported-capability review, not as an automatic Red Hat OpenShift AI 3.4 cleanup. This matches the current Red Hat OpenShift AI 3.4 posture where the core platform is 3.4, while specific demo-adjacent paths still require live validation and support-scope checks.
- Current validation wording now distinguishes external model registration from external inference. Stage 050 registers `gpt-4o` and `gpt-4o-mini` without requiring provider token spend; external inference is credential-gated and has been validated with an approved `OPENAI_API_KEY` by using the opt-in smoke test.
- Stage 040, Stage 070, and Stage 090 READMEs now call out Red Hat alignment, support-scope posture, and demo-specific deviations close to the affected implementation.
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
- Final evidence for Stage 030: `qwen3-6-35b-a3b` and `nemotron-3-nano-30b-a3b` were registered in the model registry. Both model pods were scheduled on GPU nodes and were in init/model-pull startup. Both `LLMInferenceService` resources reported `HTTPRouteReconcileError` because `AuthPolicy` is introduced by Stage 040.
- After Stage 040 installed RHCL and refreshed KServe discovery, Stage 030 re-validation passed with both local `LLMInferenceService` resources ready.

Stage 040 findings:

- The first Stage 040 auto-sync stalled on `tenants.maas.opendatahub.io` even though the CRD existed. Manual hard refresh plus explicit `argocd app sync` advanced the operation. This is the same Argo CD startup/cache pattern seen in Stage 010.
- CloudNativePG generated install plan `install-kjljp` with `APPROVAL=Manual` and `APPROVED=false` even though the Subscription requested `installPlanApproval: Automatic`. Improvement being applied: add a narrow Stage 040 approval hook that only approves pending CloudNativePG install plans in `openshift-operators`.
- The first approval hook version used a later sync wave than the CloudNativePG Subscription, so Argo CD did not run it while the Subscription was still Progressing. The hook now runs in the same dependency wave as the Subscription, with RBAC created one wave earlier.
- The `configure-kuadrant` hook ran before the MaaS controller and generated AuthPolicy resources were created. Improvement being applied: move that hook after the MaaS API, gateway, and local MaaS resources, extend its deadline, and fail explicitly if required AuthPolicy resources are not created in time.
- The MaaS controller reported that `openshift-ingress/maas-default-gateway` was missing because Gateway resources were later than the controller and local MaaS resources. Improvement being applied: move `GatewayClass` and the default MaaS `Gateway` before the MaaS controller deployment, and move the Kuadrant patch hook after the gateway-dependent resources.
- MaaS generated the gateway policy as `gateway-default-auth`, not the older `gateway-auth-policy` name used by the earlier hook implementation. Improvement applied: patch `gateway-default-auth` and use a JSON patch to replace `maas-api-auth-policy` authorization with an explicit empty object.
- After the gateway and RHCL were healthy, the existing `LLMInferenceService` resources still reported the earlier AuthPolicy CRD discovery error. A controlled restart of `llmisvc-controller-manager` refreshed AuthPolicy discovery and created the model HTTPRoutes. Improvement applied: the Stage 040 hook restarts both `kserve-controller-manager` and `llmisvc-controller-manager` after RHCL/Gateway readiness in this staged demo flow.
- Follow-up GitOps hygiene finding: the MaaS Gateway listener hostnames and TLS certificate reference are cluster-specific values patched by `job-patch-gateway-hostname`. They must not be masked by a broad Gateway spec ignore, but they must be ignored narrowly so Argo CD does not restore placeholder values after the patch hook runs.
- Final evidence for Stage 040: CloudNativePG, Red Hat Connectivity Link, Kuadrant, MaaS API, local `MaaSModelRef` resources, local `MaaSAuthPolicy`, `demo-models-subscription`, per-route AuthPolicies, and Grafana all validated successfully. Argo CD reports Stage 040 `Synced` and `Healthy`.

Stage 050 findings:

- Stage 050 registered the approved external model resources and, when an approved `OPENAI_API_KEY` was later supplied through `.env`, completed an opt-in external inference smoke test through MaaS.
- Final evidence for Stage 050: `ExternalModel` and `MaaSModelRef` resources for `gpt-4o` and `gpt-4o-mini` are registered and Ready. `external-models-access` is Active and `demo-models-subscription` covers the private and approved external model choices. Argo CD reports Stage 050 `Synced` and `Healthy`. The opt-in external smoke validation passed with 19 checks, 0 warnings, and 0 failures; a direct OpenAI-compatible call through MaaS to `gpt-4o-mini` returned HTTP `200` with non-empty assistant content.

Stage 070 findings:

- `SLACK_BOT_TOKEN` and `BRIGHTDATA_API_TOKEN` are not set in this demo environment. Slack and BrightData MCP discovery entries are present in the GenAI Playground ConfigMap, but their runtimes are disabled at zero replicas until credentials are approved and an enabling overlay is added.
- Initial Stage 070 sync showed that running optional MCP pods without credentials leaves Argo CD Progressing. Improvement applied: keep optional Slack and BrightData MCP deployments at zero replicas by default so missing optional credentials produce validation warnings instead of deployment failures.
- Final evidence for Stage 070: OpenShift MCP is running, OpenShift/Slack/BrightData MCP entries are registered in `gen-ai-aa-mcp-servers`, and Argo CD reports Stage 070 `Synced` and `Healthy`.

Stage 050 findings:

- Initial Stage 050 sync attempted to create the `CheCluster` before the Dev Spaces operator webhook service had endpoints, producing a transient `no endpoints available for service "devspaces-operator-service"` admission error. A manual hard refresh and sync succeeded after the operator and webhook pods became ready.
- Improvement applied: add a narrow Sync hook that waits for the `devspaces-operator` deployment rollout and `devspaces-operator-service` endpoints before Argo CD applies the `CheCluster`.
- Follow-up GitOps finding: `DevWorkspace` resources had `Replace=true`, which is incompatible with controller-assigned immutable DevWorkspace IDs on later syncs. Improvement applied: remove `Replace=true`, add a repair hook for stale live annotations from earlier revisions, and allow Argo CD to patch/observe the resources.
- Stage 050 follow-up: the Stage 050 Application previously ignored the entire `DevWorkspace.spec`, which hid updates to workspace setup commands. The ignore rule now covers only `/spec/started`, so GitOps owns the workspace definitions while Dev Spaces can still start and stop workspaces at runtime.
- Final evidence for Stage 050: Dev Spaces operator CSV `devspacesoperator.v3.27.1` succeeded, `CheCluster` phase is `Active`, the Dev Spaces URL is `https://devspaces.apps.cluster-t977r.t977r.sandbox3022.opentlc.com`, and Argo CD reports Stage 050 `Synced` and `Healthy`.

Stage 070 findings:

- Initial Stage 070 sync applied the `Tackle` CR successfully, but the MaaS patch hook ran before MTA operator-owned resources such as `llm-proxy` and the MTA route existed. Improvement applied: the hook now waits for the generated route and `llm-proxy` deployment before patching the ConsoleLink and rolling the proxy.
- MaaS API keys created without an explicit subscription could default to a subscription that did not cover the requested local model, producing HTTP 403. Improvement applied: the hook now creates or rotates the `kai-api-keys` key with `subscription: demo-models-subscription`.
- Follow-up GitOps hygiene finding: when Stage 040 temporarily restored the placeholder MaaS Gateway hostname, the Stage 070 hook accepted it and patched placeholder values into `Tackle.spec.kai_llm_baseurl` and the `kai-api-keys` Secret. Improvement applied: the hook now rejects placeholder MaaS hostnames before patching any MTA resources.
- The validator initially checked Tackle AI conditions before the operator finished updating status. Improvement applied: Stage 070 validation now waits for `KaiAPIKeysConfigured`, `LLMProxyReady`, and `KaiSolutionServerReady`.
- Temporary MaaS API keys created while testing the subscription field were deleted through the MaaS API.
- Final evidence for Stage 070: MTA Operator CSV `mta-operator.v8.1.1` succeeded; MTA Hub, UI, Kai API, LLM proxy, and Kai solution server are ready; OpenShift login is visible on the MTA login page; MaaS auth against the private Nemotron model returns HTTP 200 using `kai-api-keys`; Argo CD reports Stage 070 `Synced` and `Healthy`.

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
- `qwen3-6-35b-a3b` and `nemotron-3-nano-30b-a3b` both reached `Ready=True`.
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

- Static checks passed: - `bash -n stages/030-private-model-serving/deploy.sh stages/030-private-model-serving/validate.sh` - `kustomize build gitops/stages/030-private-model-serving/base` - `kustomize build gitops/stages/030-private-model-serving/base | oc apply --dry-run=server -f -` - `git diff --check`
- Live validation after image pull, cold start, and probe remediation: `./stages/030-private-model-serving/validate.sh`: 30 passed, 0 warnings, 0 failed.
- Both router-scheduler pods were created and running.
- Both new model workloads were admitted by Kueue and assigned to GPU nodes.
- Both `qwen3-6-35b-a3b` and `nemotron-3-nano-30b-a3b` are `Ready=True`, with model pods `2/2 Running`.
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
- `nemotron-3-nano-30b-a3b` and `qwen3-6-35b-a3b` both recovered to `Ready=True` after large model image pulls and vLLM cold start.
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
- Updated Stage 050 validation so the optional external smoke test creates a runtime MaaS API key for `demo-models-subscription` instead of reusing an unrelated coding-assistant key.
- Updated the GuideLLM wrapper to support `GUIDELLM_VALIDATE_BACKEND`; Stage 050 sets it to `false` because the external MaaS path does not expose a vLLM-style `/health` endpoint.

Validation evidence:

- Stage 030 validation after the documentation refresh passed with 34 checks, 0 warnings, and 0 failures.
- Stage 040 validation after the documentation refresh passed with 58 checks, 0 warnings, and 0 failures. Result ConfigMap from the embedded GuideLLM run: `maas/guidellm-nemotron-3-nano-30b-a3b-20260502182022-results`.
- Stage 050 validation with external smoke test passed: `GUIDELLM_EXTERNAL_SMOKE_TEST=true GUIDELLM_REQUESTS=1 GUIDELLM_OUTPUT_TOKENS=32 ./stages/050-approved-external-model-access/validate.sh`: 19 passed, 0 warnings, 0 failed. Result ConfigMap: `maas/guidellm-gpt-4o-mini-20260502182117-results`.
- A direct OpenAI-compatible call through MaaS to `gpt-4o-mini` returned HTTP `200` with non-empty assistant content.
- The provider key and runtime MaaS key were not printed, committed, or stored in Git.

### 2026-05-02 Gen AI Playground MaaS token validation

Actions:

- Investigated a Playground-only failure where direct Llama Stack calls worked for all four MaaS models, but browser requests through the Gen AI Playground succeeded for only the models covered by the selected MaaS subscription.
- Confirmed the dashboard BFF obtains a MaaS token and passes it to Llama Stack as request provider data. The Llama Stack `remote::vllm` provider prefers that request `vllm_api_token` over provider-specific environment tokens.
- Replaced the split local/external consumer subscriptions with one `demo-models-subscription` token boundary for models that appear together in the same Playground.
- Stage 040 now ensures the demo subscription exists for private models without downgrading a Stage 050-expanded subscription. Stage 050 declaratively owns the expanded four-model subscription after the external `MaaSModelRef` resources exist.

Validation evidence:

- Stage 040 and Stage 050 both synced from commit `c071832` and reported `Synced` and `Healthy`.
- Live `demo-models-subscription` contains `qwen3-6-35b-a3b`, `nemotron-3-nano-30b-a3b`, `gpt-4o`, and `gpt-4o-mini`, with all four token-limit statuses ready.
- `GENAI_PLAYGROUND_BFF_SMOKE_TEST=true GUIDELLM_EXTERNAL_SMOKE_TEST=false ./stages/050-approved-external-model-access/validate.sh` passed with 24 checks, 0 warnings, and 0 failures.
- Recent Llama Stack logs show successful `POST /v1/responses` calls after the fix. The earlier `subscription ... does not include model` authorization error is no longer present in current validation.

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

Stage 030 deploys local private model serving resources: the `maas` project, local `LLMInferenceService` resources, LeaderWorkerSet prerequisites, and model registry seed data. The local models use the Red Hat OpenShift AI llm-d `LLMInferenceService` path with vLLM as the inference runtime. The demo configures single-GPU-per-replica serving, explicit scheduler enablement, Kueue queue admission, an 8,192-token chunked-prefill scheduling budget for long developer prompts, and vLLM metric aliases for future autoscaling analysis. It does not deploy multi-node, disaggregated prefill/decode inference, Gateway API Inference Extension `InferencePool` resources, or agentgateway body-based routing.

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

Stage 040 deploys the governed Models-as-a-Service control point around the Red Hat OpenShift AI 3.4 MaaS controller and API: Gateway API, Red Hat Connectivity Link, Kuadrant, Authorino, the shared demo consumer subscription, token limits, and tenant telemetry.

RHOAI 3.4 owns the MaaS controller and `maas-api` deployments. Do not reintroduce the previous upstream `maas-controller` deployment or `maas-api` image override: those pre-3.4 workarounds conflict with the operator-owned selectors, RBAC, CRDs, and images. GitOps should manage only demo MaaS model references, access policies, subscriptions, gateway policy, observability helpers, and validation jobs unless product documentation and live schema checks require otherwise.

RHOAI 3.4 uses MaaS subscriptions instead of the 3.3 tier model. The active GitOps path no longer creates `tier-to-group-mapping`, `tier-*` groups, tier ServiceAccount RBAC, or tier-shaped dashboard metrics. Access is granted to the demo OpenShift groups through `MaaSAuthPolicy`, quota and token limits are set through `MaaSSubscription`, and telemetry is enabled on `Tenant/default-tenant`.

Stage 040 validation runs a short GuideLLM load test when a MaaS API key is available. Red Hat OpenShift AI 3.4 lists GuideLLM support through the Evaluation Stack control plane as a Developer Preview capability; this demo currently uses the upstream GuideLLM container directly to generate repeatable load against the MaaS OpenAI-compatible endpoint. Results are stored as `ConfigMap` objects in the `maas` namespace with names beginning `guidellm-`.

The Gen AI Playground token path uses the dashboard BFF to request a MaaS token, then passes that token to Llama Stack as request provider data. Llama Stack's `remote::vllm` provider gives that request token precedence over provider-specific environment tokens. To keep one Playground usable with private and approved external MaaS models, the demo uses one consumer subscription named `demo-models-subscription`. Stage 040 creates it with private model refs and expands it after the approved external `MaaSModelRef` resources are Ready. Product MaaS API key creation is validated through `/maas-api/v1/api-keys`.

To compare the two private models with the same governed MaaS traffic shape, run:

```bash
./stages/040-governed-models-as-a-service/compare-private-models.sh
./stages/040-governed-models-as-a-service/summarize-guidellm-results.sh
```

Useful checks:

```bash
oc get maasmodelref -n maas
oc get maasauthpolicy,maassubscription -n models-as-a-service
oc get maassubscription demo-models-subscription -n models-as-a-service -o yaml
oc get gateway maas-default-gateway -n openshift-ingress
oc get deployment maas-controller maas-api -n redhat-ods-applications
oc get tenant default-tenant -n models-as-a-service -o yaml
oc get configmap -n maas -l app.kubernetes.io/name=guidellm-load-test
```

Useful GuideLLM overrides:

```bash
GUIDELLM_MODEL=qwen3-6-35b-a3b \
GUIDELLM_PROFILE=constant \
GUIDELLM_RATE=1 \
GUIDELLM_MAX_SECONDS=20 \
GUIDELLM_REQUESTS=5 \
GUIDELLM_OUTPUT_TOKENS=64 \
GUIDELLM_PROMPT="Explain why governed model access matters for enterprise software teams." \
./stages/040-governed-models-as-a-service/run-guidellm-load-test.sh
```

### Stage 040 — approved external model access

Stage 040 owns approved external model access through MaaS (folded in from the former external-models stage by the 2026-07-06 restructure).

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
oc get maassubscription demo-models-subscription -n models-as-a-service
oc get secret openai-api-key -n maas -o jsonpath='{.data.api-key}' | base64 -d | head -c10
```

External inference validation is opt-in because it spends provider tokens:

```bash
GUIDELLM_EXTERNAL_SMOKE_TEST=true \
GUIDELLM_REQUESTS=1 \
GUIDELLM_OUTPUT_TOKENS=32 \
./stages/050-approved-external-model-access/validate.sh
```

The opt-in check creates a MaaS API key for `demo-models-subscription` at runtime and passes it to the GuideLLM Job without printing or committing it. The external-model validation disables GuideLLM's default `/health` backend probe for this path because the MaaS route validates external access through the OpenAI-compatible inference API rather than a vLLM-style health endpoint.

To validate the same dashboard path used by the Gen AI Playground, set:

```bash
GENAI_PLAYGROUND_BFF_SMOKE_TEST=true \
./stages/050-approved-external-model-access/validate.sh
```

That check sends small non-streaming requests through the dashboard BFF to all four Playground MaaS model entries. It is intentionally opt-in because it can exercise approved external provider credentials.

### Stage 040 — MCP context integrations

Stage 040 owns the MCP context integrations (folded in from the former MCP stage by the 2026-07-06 restructure).

| `.env` variable | Secret created | Namespace | Purpose |
|----------------|----------------|-----------|---------|
| `SLACK_BOT_TOKEN` | `slack-mcp-credentials` | `coding-assistant` | Slack MCP server authentication |
| `BRIGHTDATA_API_TOKEN` | `brightdata-mcp-credentials` | `coding-assistant` | BrightData MCP server authentication |

Useful checks:

```bash
oc get pods -n coding-assistant
oc get configmap gen-ai-aa-mcp-servers -n redhat-ods-applications -o yaml
```

### Stage 050 — Dev Spaces (devspaces component)

The stage 050 `devspaces` component installs Red Hat OpenShift Dev Spaces and pre-provisions workspaces (consumed by the workflow-only stages 060/070).

Validation now checks both service readiness and persona workspace readiness. The stage is not considered fully validated unless `wksp-kubeadmin`, `wksp-ai-admin`, and `wksp-ai-developer` exist, each contains the `getting-started-ai-coding` and `coolstore-inventory-service` DevWorkspaces, and the `ai-admin` / `ai-developer` workspace edit RoleBindings point at the expected OpenShift users. The `mca-coolstore` modernization workspaces in the same namespaces belong to the `mta` component and are validated by stage 080's `validate.sh`.

Useful checks:

```bash
oc get checluster devspaces -n openshift-devspaces
oc get devworkspace -A
oc get pods -n openshift-devspaces
```

### Stage 050 — Identity (identity component)

The stage 050 `identity` component deploys the standalone platform RHBK (Red Hat build of Keycloak, namespace `rhbk`): RHBK Operator (`stable-v26`), a PostgreSQL backing store, the `platform-rhbk` Keycloak CR (HTTP-enabled behind an edge-terminated Route, `proxy.headers: xforwarded`), a `KeycloakRealmImport` for the `platform` realm shell, and the `configure-platform-identity` PostSync job that patches the `platform-keycloak` OAuthClient, creates the `openshift-v4` identity provider, and pre-creates the demo users with IdP links. RHDH signs in against this realm; the MTA-operator-managed Keycloak is MTA-only.

Useful checks:

```bash
oc get keycloak platform-rhbk -n rhbk -o jsonpath='{.status.conditions[?(@.type=="Ready")].status}'
oc get keycloakrealmimport platform-realm -n rhbk -o jsonpath='{.status.conditions[?(@.type=="Done")].status}'
oc get route platform-rhbk -n rhbk -o jsonpath='{.spec.host}'
oc get oauthclient platform-keycloak -o jsonpath='{.redirectURIs[0]}'
```

### Stage 050 — MTA (mta component)

The stage 050 `mta` component installs Migration Toolkit for Applications and configures Red Hat Developer Lightspeed for MTA to use MaaS (consumed by the workflow-only stage 080). It also owns the `mca-coolstore` modernization workspaces (MTA VS Code extension pack + hub wiring) in the three persona namespaces and the `mta-hub-workspace-config` PostSync job; stage 080's `validate.sh` covers them.

Useful checks:

```bash
oc get tackle mta -n openshift-mta -o yaml
oc get deployment -n openshift-mta
oc get secret kai-api-keys -n openshift-mta -o jsonpath='{.data.OPENAI_API_BASE}' | base64 -d
```

### Stage 050 — Coolstore dev environment (coolstore component)

The `coolstore` component keeps a running `coolstore-inventory-service` in `coolstore-dev` so the demo starts from a deployed brownfield system. The Deployment pins `quay.io/…/coolstore-inventory-service:latest`; the shared pipeline's `tag-latest` task republishes that tag on every green run. `deploy.sh` seeds the first run (topic, PipelineRun, rollout) and provisions `quay-pull-secret` from `.env`. If the deployment shows ImagePullBackOff on a fresh cluster, the seed run has not completed yet — re-run `stages/050-advanced-app-platform/deploy.sh`.

Useful checks:

```bash
oc get pipelinerun -n coolstore-dev -l backstage.io/kubernetes-id=coolstore-inventory-service
oc get deployment,route -n coolstore-dev
curl -s https://$(oc get route coolstore-inventory-service -n coolstore-dev -o jsonpath='{.spec.host}')/q/health/ready
```

### Stage 050 — Developer Hub (rhdh component)

The stage 050 `rhdh` component installs Red Hat Developer Hub and configures OIDC through the platform RHBK (realm `platform`) from the `identity` component of the same stage; the MTA-operator-managed Keycloak serves only MTA.

The RHDH catalog location is runtime-derived from the Stage 050 Argo CD Application source. This avoids loading catalog entities from `main` when the demo is deployed from a validation branch or fork.

After a cluster suspend/resume, restart RHDH before demoing: the long-running backend can hold stale connections from before the suspend and fail OIDC sign-in with 504 errors even though Keycloak is healthy (`oc rollout restart deployment/backstage-developer-hub -n rhdh`; see TROUBLESHOOTING "Red Hat Developer Hub OIDC Sign-In Fails With 504 Gateway Timeout").

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

For documentation changes:

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

After any cluster suspend/resume, also restart the Stage 050 Developer Hub deployment — its long-running backend holds stale connections across the suspend and OIDC sign-in fails with 504 errors until it is bounced (see the Stage 050 Developer Hub notes and TROUBLESHOOTING).

## Coolstore Demo Reset

The stage 060 coding exercise pushes real commits to `coolstore-inventory-service` `main` (required — pipeline triggers listen only on `refs/heads/main`). To make demo runs repeatable, a `golden` branch in that repo pins the pristine baseline.

```bash
./scripts/reset-coolstore-demo.sh
```

| Flag | Effect |
|------|--------|
| `--yes` | Skip the confirmation prompt |
| `--keep-sonar` | Skip the SonarQube project deletion (deletion is the default: a post-demo rewind re-introduces fixed lines as new violations and the validation run goes red without it) |
| `--skip-workspace` | Leave the DevWorkspace as-is |
| `--wait-pipeline` | Poll the reset PipelineRun until Succeeded/Failed (max 15 min) |

The script rewinds `main` to `golden` via the GitHub API, recreates the `agentic-coolstore` DevWorkspace (Argo CD self-heals it to `Stopped`), and optionally clears SonarQube history. The force-push fires one expected `app-push` PipelineRun in `coolstore-dev` that re-validates the chain and re-tags `:latest`.

**Advancing the baseline:** when the demo app legitimately evolves, push the new baseline commit to `main`, verify the pipeline is green, then update the golden branch:

```bash
gh api -X PATCH "repos/adnan-drina/coolstore-inventory-service/git/refs/heads/golden" \
  -f sha="$(gh api repos/adnan-drina/coolstore-inventory-service/git/refs/heads/main --jq .object.sha)" \
  -F force=true
```

Or: `git push origin main:golden --force`.

## Cleanup Guidance

The Argo CD Applications intentionally do not include finalizers. Deleting an Application by itself orphans the resources that it created.

For a full cleanup, prefer an explicit Argo CD cascade delete from the OpenShift GitOps UI or CLI:

```bash
argocd app delete 050-advanced-app-platform --cascade
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
