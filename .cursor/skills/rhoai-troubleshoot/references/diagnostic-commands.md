# Diagnostic Commands Reference

Quick-reference commands organized by component for troubleshooting the RHOAI demo on OpenShift AI 3.3 with selected early-access MaaS resources.

## RHOAI Dependency Operators

RHOAI relies on external operators that must be installed and healthy before RHOAI components can function.
This catalog is based on Red Hat's [odh-gitops](https://github.com/opendatahub-io/odh-gitops) reference repository.

| Operator | Namespace | Required By | Depends On |
|----------|-----------|-------------|-----------|
| **cert-manager** | `cert-manager-operator` | Kueue, Ray, RHCL | — |
| **Kueue** | `openshift-kueue-operator` | Distributed workloads, Trainer | cert-manager |
| **Cluster Observability Operator** | `openshift-cluster-observability-operator` | Monitoring | — |
| **OpenTelemetry** | `openshift-opentelemetry-operator` | Tracing | — |
| **Leader Worker Set** | `openshift-lws-operator` | Distributed inference | cert-manager |
| **JobSet Operator** | `openshift-jobset-operator` | Trainer | — |
| **Custom Metrics Autoscaler (KEDA)** | `openshift-keda` | Model Serving autoscaling | — |
| **Tempo Operator** | `openshift-tempo-operator` | Distributed tracing | — |
| **Red Hat Connectivity Link (RHCL)** | `kuadrant-system` | KServe auth (Authorino) | LWS, cert-manager |
| **Node Feature Discovery (NFD)** | `openshift-nfd` | GPU Operator, LlamaStack | — |
| **NVIDIA GPU Operator** | `nvidia-gpu-operator` | Model Serving (GPU) | NFD |
| **MariaDB Operator** | `mariadb-operator` | TrustyAI (database mode) | — |
| **Service Mesh 3** | `openshift-operators` | RHOAI (auto-installed, Manual approval) | — |

Not all dependencies are required for every deployment. Install only what your demo stages need.

```bash
# Quick health check: all dependency CSVs
oc get csv -A --no-headers | grep -E "cert-manager|kueue|nfd|gpu-operator|servicemesh|observability|opentelemetry|tempo|keda|lws|jobset|mariadb|connectivity-link" | awk '{printf "%-50s %-30s %s\n", $2, $1, $NF}'

# Check dependency install order (operators with unmet dependencies)
oc get csv -A | grep -v Succeeded | grep -v "^NAMESPACE"
```

## Argo CD

```bash
# App status overview
oc get application <app-name> -n openshift-gitops

# Detailed sync status and health
oc get application <app-name> -n openshift-gitops -o yaml | grep -A 20 'status:'

# Sync errors
oc get application <app-name> -n openshift-gitops -o jsonpath='{.status.conditions[*].message}'

# Resource health breakdown
oc get application <app-name> -n openshift-gitops -o jsonpath='{range .status.resources[*]}{.kind}/{.name}: {.health.status} {.status}{"\n"}{end}'

# Force sync
oc patch application <app-name> -n openshift-gitops --type merge -p '{"operation":{"sync":{}}}'

# Argo CD server logs
oc logs deploy/openshift-gitops-server -n openshift-gitops --tail=50

# Verify AppProject usage (all apps should show rhoai-demo, not default)
oc get applications -n openshift-gitops -o custom-columns=NAME:.metadata.name,PROJECT:.spec.project

# Verify annotation tracking
oc get argocd openshift-gitops -n openshift-gitops -o jsonpath='{.spec.resourceTrackingMethod}'

# Check manifest-generate-paths coverage
oc get applications -n openshift-gitops -o custom-columns='NAME:.metadata.name,PATHS:.metadata.annotations.argocd\.argoproj\.io/manifest-generate-paths'
```

## Operators (CSV, Subscription, InstallPlan)

```bash
# All CSVs across namespaces
oc get csv -A | grep -v Succeeded

# Subscription details
oc get sub -n <namespace> -o yaml

# InstallPlan status
oc get installplan -n <namespace>
oc describe installplan <name> -n <namespace>

# CatalogSource health
oc get catalogsource -n openshift-marketplace
oc get pods -n openshift-marketplace
```

## Pods

```bash
# Pod status with node placement
oc get pods -n <namespace> -o wide

# Describe pod (events, conditions, volumes)
oc describe pod <pod-name> -n <namespace>

# Current logs
oc logs <pod-name> -n <namespace> [-c <container>] --tail=100

# Previous container logs (after crash)
oc logs <pod-name> -n <namespace> [-c <container>] --previous

# Events in namespace (sorted by time)
oc get events -n <namespace> --sort-by=.lastTimestamp | tail -20

# Resource usage
oc adm top pods -n <namespace>
```

## GPU & Nodes

```bash
# GPU node status
oc get nodes -l node-role.kubernetes.io/gpu -o wide

# Node labels (GPU, NFD)
oc get nodes --show-labels | grep -E "gpu|nvidia|kernel-version"

# Node taints
oc get nodes -o custom-columns='NAME:.metadata.name,TAINTS:.spec.taints[*].key'

# MachineSet status
oc get machineset -n openshift-machine-api | grep gpu

# Machine status (provisioning)
oc get machines -n openshift-machine-api | grep gpu

# GPU allocatable resources
oc get nodes -l nvidia.com/gpu.present=true -o jsonpath='{range .items[*]}{.metadata.name}: {.status.allocatable.nvidia\.com/gpu} GPUs{"\n"}{end}'
```

## KServe / InferenceService

```bash
# InferenceService status
oc get inferenceservice -n <namespace>

# Detailed conditions
oc get inferenceservice <name> -n <namespace> -o jsonpath='{range .status.conditions[*]}{.type}: {.status} ({.reason}){"\n"}{end}'

# Predictor pod
oc get pods -n <namespace> | grep <isvc-name>
oc describe pod <predictor-pod> -n <namespace>
oc logs <predictor-pod> -n <namespace> --tail=100

# ServingRuntime
oc get servingruntime -n <namespace> -o yaml

# Dashboard runtime recognition (check template annotations)
oc get servingruntime -n <namespace> -o custom-columns='NAME:.metadata.name,TEMPLATE:.metadata.annotations.opendatahub\.io/template-name,DISPLAY:.metadata.annotations.opendatahub\.io/template-display-name'
```

## Networking (Routes, Services)

```bash
# Routes in namespace
oc get route -n <namespace>

# Test route externally
curl -sk https://<route-host>/

# Services and endpoints
oc get svc -n <namespace>
oc get endpoints -n <namespace>
```

## Storage (PVC, MinIO)

```bash
# PVC status
oc get pvc -n <namespace>

# StorageClass
oc get storageclass
```

## RHOAI Platform

```bash
# DataScienceCluster status
oc get datasciencecluster default-dsc

# DSCInitialization status
oc get dscinitializations default-dsci -o yaml

# RHOAI Dashboard pods
oc get pods -n redhat-ods-applications

# RHOAI Operator CSV
oc get csv -n redhat-ods-operator | grep "OpenShift AI"

# Hardware Profiles
oc get hardwareprofiles -n redhat-ods-applications

# Service Mesh 3 operator (RHOAI auto-installs with Manual approval)
oc get subscription servicemeshoperator3 -n openshift-operators
oc get installplan -n openshift-operators | grep servicemesh
```

## Data Science Pipelines

```bash
# DSPA status
oc get dspa -n <namespace>

# Pipeline pods
oc get pods -n <namespace> -l pipeline/runid --sort-by=.metadata.creationTimestamp | tail -10

# Pipeline server
oc get pods -n <namespace> | grep ds-pipeline
```
