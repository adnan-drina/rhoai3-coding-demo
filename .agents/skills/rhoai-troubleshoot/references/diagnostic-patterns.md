# Diagnostic Patterns

Short symptom -> likely cause -> first check table for the RHOAI 3.5 demo.
Detailed entries (symptom, cause, commands, recovery) live in
`docs/TROUBLESHOOTING.md`; add new ones there, not here.

## Argo CD

| Pattern | Likely cause | First check |
|---------|-------------|-------------|
| Application OutOfSync or Degraded | Resource conflict, schema, failed hook | `docs/TROUBLESHOOTING.md#argo-cd-app-is-outofsync` |
| Synced at the new SHA but manifests are old | Stale repo-server render | `docs/TROUBLESHOOTING.md#argo-cd-reports-synced-but-new-manifests-are-missing` |
| Operation stuck on a hook Job | Hook Job failing or waiting | `docs/TROUBLESHOOTING.md#argo-cd-operation-stuck-on-a-hook-job` |
| Manual sync finishes in seconds, hooks did not run | Sync without hooks | `docs/TROUBLESHOOTING.md#manually-triggered-sync-finishes-in-seconds-and-skips-hooks` |
| A stage's DSC or dashboard setting reverts | Field not delegated in `010-rhoai-platform` `ignoreDifferences` | `scripts/stage-apps.sh delegated 010 DataScienceCluster default-dsc --group datasciencecluster.opendatahub.io` |
| Application uses `project: default` | Bootstrap not applied | `oc get appproject rhoai-demo -n openshift-gitops` |

## Operators

| Pattern | Likely cause | First check |
|---------|-------------|-------------|
| CSV not Succeeded | Install plan, dependency, catalog | `docs/TROUBLESHOOTING.md#operator-csv-not-succeeded` |
| Install plan approves more CSVs than expected | Shared namespace passengers | `docs/TROUBLESHOOTING.md#installplan-approval-carries-hidden-passenger-csvs` |
| CRD not found | Component `Removed` or CSV not ready | `oc get datasciencecluster default-dsc -o jsonpath='{.spec.components}'` |

## RHOAI platform

| Pattern | Likely cause | First check |
|---------|-------------|-------------|
| DSC not Ready | A component still reconciling or failed | `oc get datasciencecluster default-dsc -o yaml` (conditions) |
| Dashboard feature missing | Owning stage not deployed (flags are set by Stage 030/040/050/060 Jobs) | `oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o jsonpath='{.spec.dashboardConfig}'` |
| Observability page empty | Monitoring stack or dashboards | `docs/TROUBLESHOOTING.md#observability-dashboard-shows-no-dashboards-found` |

## GPU and serving

| Pattern | Likely cause | First check |
|---------|-------------|-------------|
| GPU nodes missing | MachineSets at 0 after a stop | `docs/TROUBLESHOOTING.md#gpu-nodes-do-not-appear`, `resume-gpu-demo` skill |
| Model pod Pending, no Kueue workload | Queue label or quota | `docs/TROUBLESHOOTING.md#private-models-do-not-produce-kueue-workloads` |
| Model shows "Starting" while its pod is Ready | Dashboard status lag | `docs/TROUBLESHOOTING.md#model-shows-starting-in-the-rhoai-console-but-its-pod-is-ready` |
| Image pull stalls on a GPU node | Large model image | `docs/TROUBLESHOOTING.md#model-image-pull-stalls-on-a-gpu-node` |

## MaaS and playground

| Pattern | Likely cause | First check |
|---------|-------------|-------------|
| MaaS tab shows no models | Model refs or subscriptions | `docs/TROUBLESHOOTING.md#maas-tab-shows-no-models` |
| Gateway holds a response open | Missing usage in the response | `docs/TROUBLESHOOTING.md#maas-gateway-holds-a-response-open-until-the-client-times-out` |
| Playground gets no answer | Model path or custom endpoint | `docs/TROUBLESHOOTING.md#gen-ai-playground-gets-no-answer-from-external-models` |

## Secrets

| Pattern | Likely cause | First check |
|---------|-------------|-------------|
| Secret deleted seconds after Argo CD creates it | `opendatahub.io/managed: "true"` label on a Git Secret | Remove the label from the manifest (`.agents/rules/env.md`) |
| Pod cannot pull image | Pull secret or registry | `oc describe pod` events |
