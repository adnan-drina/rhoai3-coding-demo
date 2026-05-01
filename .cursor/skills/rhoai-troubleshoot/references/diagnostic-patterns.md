# Diagnostic Patterns

Known symptom -> cause -> fix patterns for the RHOAI demo on OpenShift AI 3.3 with selected early-access MaaS resources.

## General Platform Patterns

| Pattern | Likely Cause | First Check |
|---------|-------------|-------------|
| Operator not installing | CatalogSource, Subscription issue | `oc get csv -n <ns>`, `oc get sub -n <ns>` |
| CRD not found | Operator CSV not succeeded | `oc get csv -A \| grep <name>` |
| Pod not starting | Resource limits, image pull, taint | `oc describe pod`, `oc get events` |

## ArgoCD Patterns

| Pattern | Likely Cause | First Check |
|---------|-------------|-------------|
| Argo CD not syncing | Resource conflict, RBAC | `oc get application <name> -n openshift-gitops -o yaml` |
| Argo CD ComparisonError | CRD schema not resolvable | Add `ServerSideDiff=true` to syncOptions |
| ArgoCD Application uses `project: default` | Bootstrap didn't run or Applications weren't updated | Verify `oc get appproject rhoai-demo -n openshift-gitops` |
| ArgoCD shows false Out-of-Sync on operator resources | Label tracking instead of annotation tracking | Verify tracking: `oc get argocd openshift-gitops -n openshift-gitops -o jsonpath='{.spec.resourceTrackingMethod}'` must be `annotation` |
| ArgoCD reconciles all stages on unrelated commit | Missing `manifest-generate-paths` annotation | Add `argocd.argoproj.io/manifest-generate-paths: gitops/stages/NNN-name` to each Application |

## RHOAI Step-01 Patterns

| Pattern | Likely Cause | First Check |
|---------|-------------|-------------|
| RHOAI Operator CSV stuck | InstallPlan not approved | `oc get installplan -n redhat-ods-operator` |
| DataScienceCluster not Ready | Components still reconciling | `oc get datasciencecluster default-dsc -o jsonpath='{.status.phase}'` |
| Service Mesh 3 not installing | Install plan needs manual approval | `oc get installplan -n openshift-operators \| grep servicemesh` |
| Dashboard not accessible | Route not ready or pods pending | `oc get route -n redhat-ods-applications`, `oc get pods -n redhat-ods-applications` |
| HardwareProfiles missing | DSC not fully reconciled yet | Wait for DSC Ready, then check `oc get hardwareprofiles -n redhat-ods-applications` |
| GenAI Studio not visible in Dashboard | OdhDashboardConfig not patched | `oc get odhdashboardconfig -n redhat-ods-applications -o jsonpath='{.spec.dashboardConfig.genAiStudio}'` |

## KServe / Model Serving Patterns

| Pattern | Likely Cause | First Check |
|---------|-------------|-------------|
| InferenceService not ready | GPU scheduling, model storage | `oc get pods`, `oc describe isvc`, `oc get workload` |
| Predictor pod in Init:0/1 | Storage-initializer downloading model | Wait — check init logs |
| Model scaling overwritten | Used `oc scale` (imperative) | Use `oc patch inferenceservice` (declarative) |

## Security / Secrets Patterns

| Pattern | Likely Cause | First Check |
|---------|-------------|-------------|
| Secret deleted seconds after ArgoCD creates it | `opendatahub.io/managed: "true"` label triggers ODH controller deletion | Remove the label from the GitOps manifest |
| Pod can't pull image | Missing pull secret or wrong registry | `oc describe pod` — look for ImagePullBackOff events |
