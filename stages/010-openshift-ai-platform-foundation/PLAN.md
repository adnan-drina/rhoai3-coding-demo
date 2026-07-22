# Stage 010: OpenShift AI Platform Foundation — Plan

## Intent

- Stage identifier: `110`
- Stage family: `1xx AI Platform Foundation`
- Stage slug: `010-openshift-ai-platform-foundation`
- Concept introduced: End-to-end AI platform foundation — GitOps reconciliation, S3-compatible object storage (ODF MCG), RHOAI observability prerequisites, and the RHOAI Operator with a minimal shared `DataScienceCluster` (Dashboard + Workbenches + Model Registry + standalone Kueue integration point). All subsequent demo stages build on top of this base.
- Target audience: Platform engineer, solution architect
- Enterprise value: Control, governance, portability, compliance, cost (on-premises object storage replaces cloud dependency)
- Depends on: None (first stage)
- New components: OpenShift GitOps, ODF MCG, Cluster Observability Operator, Red Hat build of OpenTelemetry, Tempo Operator, RHOAI Operator, DSCInitialization, DataScienceCluster
- Existing components reused: Underlying OCP 4.20 cluster on AWS
- Non-goals:
  - GPU/accelerator setup (implemented separately by `020-gpu-infrastructure-private-ai`)
  - Full ODF StorageCluster/Ceph block and file storage
  - RHOAI model serving, Ray, pipelines, TrustyAI (all deferred)
- Included access layer (added after initial deploy): htpasswd IdP (`ai-admin`, `ai-developer`), `demo-sandbox` data science project, Contributor RBAC, and an OBC-backed S3 connection. Model registry is enabled in the base DSC.

**Scope note:** Stage 010 owns shared platform resources that later stages depend on, including the single rendered `DataScienceCluster`. Later stages must not render competing copies of shared platform resources.

## Acceptance Criteria

- [ ] README explains Why and What without runbook detail.
- [ ] Why and business value are grounded in at least one Red Hat narrative source from `rh-brain/`.
- [ ] What and related product components are grounded in active-baseline official Red Hat docs.
- [ ] Relevant Red Hat-linked GitHub reference implementations were searched and captured, or absence is documented.
- [ ] Official Red Hat docs are captured for every product component.
- [ ] Design decisions and applied configuration choices reference the sources used.
- [ ] GitOps ownership model is explicit.
- [ ] Manifests render and configuration is cross-checked against official sources or verified schema.
- [ ] Deploy script applies the Argo CD Application or shared owner first and handles sensitive data through documented non-committed paths.
- [ ] Validate script proves the user-visible outcome.
- [ ] Manifest and Red Hat source-alignment reviews pass.

## Source Capture

| Purpose | Source | Skill | Notes |
|---------|--------|-------|-------|
| Enterprise AI value / hybrid cloud | [From inference to agents: Scaling AI in the enterprise with Red Hat AI 3.4](https://www.redhat.com/en/blog/inference-agentic-ai-scaling-enterprise-foundation-red-hat-ai-34) | `project-documentation-authoring` | Metal-to-agent platform, consistent across environments |
| Infrastructure foundation narrative | [Our journey to AI-centricity, Part 1](https://www.redhat.com/en/blog/our-journey-ai-centricity-part-1-building-stable-foundation) | `project-documentation-authoring` | Standardise first, then AI — Red Hat's own experience |
| Open source vs proprietary model flexibility | [The state of open source AI models in 2025](https://developers.redhat.com/articles/2026/01/07/state-open-source-ai-models-2025) | `project-documentation-authoring` | Regulated sectors, sovereignty, vLLM, open model ecosystem |
| ODF MCG for AI developers | [ODF for developers and data scientists](https://developers.redhat.com/articles/2024/07/31/red-hat-openshift-data-foundation-developers-and-data-scientists) | `odf-multicloud-gateway` | MCG standalone, OBC workflow, S3 endpoint discovery |
| RHOAI install | [RHOAI 3.4 install guide](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/installing-and-deploying-openshift-ai_install) | `rhoai-self-managed-installation` | Namespace, OperatorGroup, Subscription, DSCI, DSC |
| RHOAI DSCI/DSC config | [Managing RHOAI 3.4](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai) | `rhoai-dsci-dsc-configuration` | Component managementState, predefined namespaces |
| RHOAI observability | [RHOAI 3.4 Managing observability](https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/managing-observability_managing-rhoai) | `rhoai-observability` | Prerequisite operators, `DSCInitialization.spec.monitoring`, dashboard flag, `redhat-ods-monitoring` stack |
| OCP observability boundary | [OCP 4.20 Observability overview](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/observability_overview/index) | `ocp-observability` | OpenShift observability component boundary and Cluster Observability Operator positioning |
| Red Hat build of OpenTelemetry | [Red Hat build of OpenTelemetry 3.9](https://docs.redhat.com/en/documentation/red_hat_build_of_opentelemetry/3.9) | `ocp-opentelemetry` | OpenTelemetry prerequisite operator |
| Red Hat OpenShift distributed tracing platform | [Distributed tracing platform 3.9](https://docs.redhat.com/en/documentation/red_hat_openshift_distributed_tracing_platform/3.9) | `ocp-distributed-tracing` | Tempo prerequisite operator |
| ODF MCG standalone | [ODF 4.20 on AWS](https://docs.redhat.com/en/documentation/red_hat_openshift_data_foundation/4.20/html-single/deploying_openshift_data_foundation_using_amazon_web_services/index) | `odf-storagecluster`, `odf-multicloud-gateway` | MCG-only `StorageCluster` posture |
| OCP GitOps | [OCP 4.20 GitOps](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/gitops/index) | `ocp-gitops-operator` | Operator channel, ArgoCD instance, resource tracking |
| GitOps manifests pattern | [github.com/redhat-ai-services/ai-accelerator](https://github.com/redhat-ai-services/ai-accelerator) | `project-red-hat-operator-gitops` | CoP operator/instance/aggregate Kustomize layout, DSC base |

### `rh-brain` Article Selection

- Candidate articles reviewed: "From inference to agents" (2026-04-30), "Our journey to AI-centricity Part 1" (2026-03-20), "The state of open source AI models in 2025" (2026-01-07), "ODF for developers" (2024-07-31), "From lab to ledger: Scaling enterprise AI at Red Hat Summit 2026" (2026-04-20)
- Selected for Why section: "From inference to agents" (enterprise platform value), "Our journey to AI-centricity Part 1" (infrastructure-first narrative), "The state of open source AI models in 2025" (open vs proprietary)
- Reasons selected: "From inference to agents" provides the most comprehensive and recent Red Hat AI 3.4 enterprise value framing; "AI-centricity Part 1" provides the concrete infrastructure-first lesson from Red Hat's own experience; "Open source AI models" directly addresses the proprietary vs open model question with regulated-sector examples
- Links to GitHub/code examples: "Open source AI models" links to vLLM, Ollama, RamaLama GitHub repos; "ODF for developers" includes concrete YAML examples
- Linked implementation source: https://github.com/vllm-project/vllm (vLLM), https://github.com/containers/ramalama (RamaLama)

## Skill Routing

- Coordinator: `project-demo-stage-authoring`
- Documentation: `project-documentation-authoring`
- GitOps: `project-gitops-authoring`, `project-red-hat-operator-gitops`
- Product skills: `rhoai-self-managed-installation`, `rhoai-dsci-dsc-configuration`, `rhoai-observability`, `rhoai-update-channels`, `odf-storagecluster`, `odf-multicloud-gateway`, `ocp-gitops-operator`, `ocp-observability`, `ocp-opentelemetry`, `ocp-distributed-tracing`
- Review skills: `project-manifest-review`, `project-red-hat-doc-alignment-review`, `rhoai-api-tiers`
- Environment skills: `env-deploy-and-evaluate`, `env-troubleshoot`

## GitOps Ownership

- Ownership model: stage-owned (bootstrap is imperative; ODF + RHOAI resources are ArgoCD-managed after bootstrap)
- Owning Application: `010-openshift-ai-platform-foundation` in `openshift-gitops` namespace
- Source path: `gitops/stages/010-openshift-ai-platform-foundation/base`
- Shared resources touched: `DataScienceCluster` (owned here; later stages patch it), `DSCInitialization` monitoring configuration, ODF `StorageCluster` (owned here)
- Argo CD sync or ordering requirements:
  - GitOps operator is bootstrapped imperatively before ArgoCD exists
  - ODF operator must be `Succeeded` before the MCG `StorageCluster` is applied (handled by `SkipDryRunOnMissingResource=true` + retry)
  - Cluster Observability Operator, Red Hat build of OpenTelemetry, and Tempo Operator must be installed before the RHOAI observability stack can materialize
  - Cluster Observability Operator is held at `cluster-observability-operator.v1.4.0` through OLM `startingCSV` and manual approval automation; operand images, copied CSVs, and generated Perses resources remain operator-managed
  - `redhat-ods-monitoring` is GitOps-managed before Stage 010 creates the service-ca Secret sync hook and Perses dashboard access resources
  - The `prometheus-web-tls-ca` sync hook waits for the service-ca injected ConfigMap, then creates the Secret referenced by the generated `MonitoringStack`
  - RHOAI operator must be `Succeeded` before DSCI/DSC are applied (same mechanism)
  - `argocd.argoproj.io/sync-wave` annotations manage within-Application ordering
- Secret and credential handling: No credentials committed. NooBaa admin credentials and OBC-generated secrets are runtime-only.

## Manifest Inventory

| File | Kind | Source authority | Validation |
|------|------|------------------|------------|
| `gitops/bootstrap/base/subscription.yaml` | Subscription (openshift-gitops-operator, placeholder channel) | OCP 4.20 GitOps docs | `oc get csv -n openshift-operators` |
| `gitops/bootstrap/overlays/operator/patch-channel.yaml` | Subscription channel patch (`gitops-1.20`) | OCP 4.20 GitOps docs (verified live) | `oc get subscription openshift-gitops-operator -n openshift-operators -o jsonpath='{.spec.channel}'` |
| `gitops/bootstrap/overlays/demo/argocd-instance.yaml` | ArgoCD (annotation resource tracking) | ai-accelerator instance/base pattern | `oc get argocd openshift-gitops -n openshift-gitops -o jsonpath='{.spec.resourceTrackingMethod}'` |
| `gitops/bootstrap/overlays/demo/argocd-project.yaml` | AppProject | ArgoCD docs | `oc get appproject rhoai-demo -n openshift-gitops` |
| `gitops/stages/010-openshift-ai-platform-foundation/base/odf/operator/base/namespace.yaml` | Namespace | ODF 4.20 AWS guide | `oc get ns openshift-storage` |
| `gitops/stages/010-openshift-ai-platform-foundation/base/odf/operator/base/operator-group.yaml` | OperatorGroup | ODF 4.20 install | `oc get operatorgroup -n openshift-storage` |
| `gitops/stages/010-openshift-ai-platform-foundation/base/odf/operator/base/subscription.yaml` | Subscription (odf-operator, `stable-4.20`) | ODF 4.20 AWS guide (verified live) | `oc get csv -n openshift-storage` |
| `gitops/stages/010-openshift-ai-platform-foundation/base/odf/instance/base/storagecluster.yaml` | StorageCluster (standalone MCG, `reconcileStrategy: standalone`) | ODF 4.20 live CRD (StorageSystem API removed in 4.20) | `oc get noobaa -n openshift-storage` |
| `gitops/stages/010-openshift-ai-platform-foundation/base/odf/instance/base/console-plugin-{rbac,script,job}.yaml` | SA/ClusterRole/CRB/ConfigMap/Job | colleague config (adapted) | `oc get consoles.operator.openshift.io cluster -o jsonpath='{.spec.plugins}'` |
| `gitops/stages/010-openshift-ai-platform-foundation/base/observability/cluster-observability-operator/operator/overlays/stable-1.4` | Subscription (`cluster-observability-operator`, `stable`, `startingCSV: cluster-observability-operator.v1.4.0`) + generated InstallPlan approval hook | RHOAI 3.4 observability prerequisites + OLM package metadata + compatibility validation | `oc get subscription cluster-observability-operator -n openshift-cluster-observability-operator` |
| `gitops/stages/010-openshift-ai-platform-foundation/base/observability/opentelemetry/operator/overlays/stable` | Subscription (`opentelemetry-product`, `stable`) | RHOAI 3.4 observability prerequisites + Red Hat build of OpenTelemetry docs + live package metadata | `oc get subscription opentelemetry-product -n openshift-opentelemetry-operator` |
| `gitops/stages/010-openshift-ai-platform-foundation/base/observability/tempo/operator/overlays/stable` | Subscription (`tempo-product`, `stable`) | RHOAI 3.4 observability prerequisites + distributed tracing docs + live package metadata | `oc get subscription tempo-product -n openshift-tempo-operator` |
| `gitops/stages/010-openshift-ai-platform-foundation/base/rhoai/operator/base/namespace.yaml` | Namespace | RHOAI 3.4 install guide | `oc get ns redhat-ods-operator` |
| `gitops/stages/010-openshift-ai-platform-foundation/base/rhoai/operator/base/operator-group.yaml` | OperatorGroup | RHOAI 3.4 install guide | `oc get operatorgroup -n redhat-ods-operator` |
| `gitops/stages/010-openshift-ai-platform-foundation/base/rhoai/operator/base/subscription.yaml` | Subscription (rhods-operator) | RHOAI 3.4 install guide | `oc get csv -n redhat-ods-operator` |
| `gitops/stages/010-openshift-ai-platform-foundation/base/rhoai/instance/base/dsc-init.yaml` | DSCInitialization with managed observability metrics and traces | RHOAI 3.4 Managing RHOAI and observability docs | `oc get dscinitialization default-dsci`; `oc get monitoring.services.platform.opendatahub.io default-monitoring` |
| `gitops/stages/010-openshift-ai-platform-foundation/base/rhoai/instance/base/datasciencecluster.yaml` | DataScienceCluster (dashboard + workbenches + modelregistry Managed; later-stage components Removed) | RHOAI 3.4 Managing RHOAI + Model registry docs | `oc get datasciencecluster default-dsc` |
| `gitops/stages/010-openshift-ai-platform-foundation/base/access/base/namespace-demo-sandbox.yaml` | Namespace (DS project) | rhoai-project-workflows | `oc get ns demo-sandbox -o jsonpath='{.metadata.labels}'` |
| `gitops/stages/010-openshift-ai-platform-foundation/base/access/base/group-rhoai-developers.yaml` | Group | rhoai-users-groups-access | `oc get group rhoai-developers` |
| `gitops/stages/010-openshift-ai-platform-foundation/base/access/base/rolebinding-developer-edit.yaml` | RoleBinding (edit) | rhoai-project-workflows | `oc get rolebinding rhoai-developers-edit -n demo-sandbox` |
| `gitops/stages/010-openshift-ai-platform-foundation/base/access/base/rolebinding-admins-admin.yaml` | RoleBinding (admin) | rhoai-users-groups-access | `oc get rolebinding rhods-admins-admin -n demo-sandbox` |
| `gitops/stages/010-openshift-ai-platform-foundation/base/access/base/obc-demo-sandbox.yaml` | ObjectBucketClaim | odf-object-bucket-claims | `oc get obc demo-sandbox-bucket -n demo-sandbox` |
| `setup-access.sh` (imperative) | htpasswd IdP, rhods-admins membership, `demo-sandbox-s3` connection | ocp-authentication-identity-providers, rhoai-users-groups-access, rhoai-s3-object-storage-data | `oc get oauth cluster`; `oc get secret demo-sandbox-s3 -n demo-sandbox` |
| `gitops/argocd/app-of-apps/010-openshift-ai-platform-foundation.yaml` | Application | project-gitops-authoring | `oc get applications.argoproj.io 010-openshift-ai-platform-foundation -n openshift-gitops` |

## Script Plan

### `deploy.sh`

- Guard behavior: reads `.env`, validates `RHOAI_EXPECTED_API_SERVER` against current cluster API server URL; exits if mismatch
- First action: `oc apply -k gitops/bootstrap/base` (installs OpenShift GitOps operator)
- Wait/report behavior:
  1. Wait for `openshift-gitops-operator` CSV to be `Succeeded`
  2. Wait for `openshift-gitops` ArgoCD instance to become Available
  3. `oc apply -k gitops/bootstrap/overlays/demo` (resource tracking patch + AppProject)
  4. Apply the stage-010 Application to ArgoCD
  5. Report ArgoCD Application sync URL to console

### `validate.sh`

- Readiness checks:
  - `openshift-gitops-operator` CSV phase = `Succeeded`
  - ArgoCD instance `openshift-gitops` Available
  - `odf-operator` CSV phase = `Succeeded`
  - `cluster-observability-operator`, `opentelemetry-product`, and `tempo-product` CSV phases = `Succeeded`
  - `rhods-operator` CSV phase = `Succeeded`
  - `noobaa` phase = `Ready` in `openshift-storage`
  - `dscinitialization` phase = `Ready`
  - `DSCInitialization.spec.monitoring.managementState=Managed`, metrics storage configured, PV-backed traces configured, dashboard flag enabled, RHOAI `Monitoring` service Ready, and `redhat-ods-monitoring` stack pods present
  - `datasciencecluster` phase = `Ready`
  - RHOAI Dashboard route responds HTTP 200
- Functional checks:
  - ArgoCD Application `010-openshift-ai-platform-foundation` Synced + Healthy
- Expected success output: all checks print `✓` and exit 0

## Operations And Troubleshooting

- `docs/OPERATIONS.md` update needed: yes — bootstrap sequence, day-2 ArgoCD access, ODF MCG S3 endpoint discovery
- `docs/TROUBLESHOOTING.md` update needed: yes — common bootstrap failures, RHOAI operator stuck, NooBaa not Ready
- `docs/BACKLOG.md` update needed: yes — deferred GPU stage, GitOps channel verification, identity provider

## Risks And Deferred Work

| Item | Type | Resolution |
|------|------|------------|
| OpenShift GitOps channel for OCP 4.20 | resolved | Verified live on cluster-klvxt (OCP 4.20.24): pinned to `gitops-1.20`; operator v1.20.4 installed |
| ODF StorageSystem MCG-only CR fields | resolved | ODF 4.20 removed the `odf.openshift.io` StorageSystem CRD; replaced with `StorageCluster` (`ocs.openshift.io/v1`) + `multiCloudGateway.reconcileStrategy: standalone`, verified against live CRD |
| GPU-as-a-Service | implemented separately | Stage `020-gpu-infrastructure-private-ai` (NFD + GPU Operator + AWS GPU MachineSet + Kueue queues + hardware profiles) |
| Identity provider / access groups | deferred | Future stage in 1xx family |
| RHOAI component enablement (kueue, kserve, MaaS, ray, etc.) | deferred | Each component added by its dedicated stage through a GitOps hook patch; Stage 010 ignores those DSC component fields to avoid self-healing later-stage state |
| ODF full StorageCluster | deferred | Added only if a future stage needs block/file storage |
| RHOAI observability dashboard backing stack | resolved with compatibility hold | Stage 010 installs Cluster Observability Operator at `cluster-observability-operator.v1.4.0`, Red Hat build of OpenTelemetry, and Tempo Operator before enabling DSCI monitoring and the dashboard flag. COO operand images remain operator-managed; do not patch generated Perses resources, generated datasources, copied CSVs, or operator-created Deployments. |

## Review Log

- Manifest review: pending
- Red Hat source-alignment review: pending
- Live deploy: succeeded on cluster-klvxt (OCP 4.20.24) 2026-06-11
- Live validation: PASSED 2026-06-11 — `validate.sh` 16/16 (platform 11 + access 5: htpasswd IdP, ai-admin in rhods-admins, demo-sandbox project, OBC Bound, S3 connection). Login verified for both users; ai-developer Contributor-scoped to demo-sandbox.
