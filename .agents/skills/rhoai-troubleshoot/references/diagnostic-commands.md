# Diagnostic Commands Reference

Read-only quick-reference commands, by component, for the RHOAI 3.5 demo on
OpenShift 4.22. Run them after the OpenShift safety guard in `AGENTS.md`.
Changes go through Git and the stage `deploy.sh`, not through these commands.

## Operators installed from Git

The operators this demo installs are the `Subscription` objects under
`gitops/` (list them with `git grep -l "kind: Subscription" -- gitops`). Most
use Automatic approval; MTA and Developer Hub (Stage 070) use Manual approval
with a pinned `startingCSV`.

```bash
# CSVs that are not Succeeded
oc get csv -A --no-headers | grep -v Succeeded

# Install plans and their approval state
oc get installplan -A

# Subscription and CatalogSource health
oc get sub -n <namespace> -o yaml
oc get catalogsource -n openshift-marketplace
```

## Argo CD

```bash
# All Applications: sync, health
oc get applications -n openshift-gitops \
  -o custom-columns='APP:.metadata.name,SYNC:.status.sync.status,HEALTH:.status.health.status'

# Components of one stage
scripts/stage-apps.sh names 040

# Sync errors and non-healthy resources of one Application
oc get application <app-name> -n openshift-gitops -o jsonpath='{.status.conditions[*].message}'
oc get application <app-name> -n openshift-gitops -o jsonpath='{range .status.resources[*]}{.kind}/{.name}: {.health.status} {.status}{"\n"}{end}'

# Deployed revision (compare with the commit the stage deploy.sh published)
oc get application <app-name> -n openshift-gitops -o jsonpath='{.status.sync.revision}{"\n"}'

# Delegated fields of a shared object (Stage 010 DSC)
scripts/stage-apps.sh delegated 010 DataScienceCluster default-dsc --group datasciencecluster.opendatahub.io

# Project and tracking method (expected: rhoai-demo, annotation)
oc get applications -n openshift-gitops -o custom-columns=NAME:.metadata.name,PROJECT:.spec.project
oc get argocd openshift-gitops -n openshift-gitops -o jsonpath='{.spec.resourceTrackingMethod}'

# Argo CD controller and server logs
oc logs statefulset/openshift-gitops-application-controller -n openshift-gitops --tail=50
oc logs deploy/openshift-gitops-server -n openshift-gitops --tail=50
```

## Pods

```bash
oc get pods -A | grep -E 'CrashLoopBackOff|ImagePullBackOff|Error|Pending'
oc describe pod <pod-name> -n <namespace>
oc logs <pod-name> -n <namespace> [-c <container>] --tail=100
oc logs <pod-name> -n <namespace> [-c <container>] --previous
oc get events -n <namespace> --sort-by=.lastTimestamp | tail -20
oc adm top pods -n <namespace>
```

## GPU and nodes

```bash
oc get machineset -n openshift-machine-api | grep gpu
oc get machines -n openshift-machine-api | grep gpu
oc get nodes -l nvidia.com/gpu.present=true -o jsonpath='{range .items[*]}{.metadata.name}: {.status.allocatable.nvidia\.com/gpu} GPUs{"\n"}{end}'
oc get nodes -o custom-columns='NAME:.metadata.name,TAINTS:.spec.taints[*].key'
oc get workloads.kueue.x-k8s.io -A
```

## Model serving (llm-d and KServe)

```bash
# Production model (Stage 040) and candidate (Stage 050)
oc get llminferenceservice -n internal-models
oc get inferenceservice -A

# Conditions
oc get llminferenceservice qwen3-8-27b -n internal-models -o jsonpath='{range .status.conditions[*]}{.type}={.status} ({.reason}){"\n"}{end}'

# Serving pods
oc get pods -n internal-models
oc logs deploy/qwen3-8-27b-kserve -n internal-models --tail=100

# MaaS publication
oc get maasmodelref -n internal-models
```

## Networking

```bash
oc get route -n <namespace>
oc get svc,endpoints -n <namespace>
oc get gateway -n openshift-ingress
oc get httproute -A
```

## Storage

```bash
oc get pvc -n <namespace>
oc get storageclass
oc get obc -A
```

## RHOAI platform

```bash
oc get datasciencecluster default-dsc -o jsonpath='{.status.phase}{"\n"}'
oc get dscinitializations default-dsci -o jsonpath='{.status.phase}{"\n"}'
oc get csv -n redhat-ods-operator
oc get pods -n redhat-ods-applications
oc get hardwareprofiles -n redhat-ods-applications
oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o jsonpath='{.spec.dashboardConfig}{"\n"}'
```

## AI pipelines

```bash
oc get dspa -n <namespace>
oc get pods -n <namespace> | grep ds-pipeline
oc get workflows.argoproj.io -n <namespace>
```
