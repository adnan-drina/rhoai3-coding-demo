---
name: ocp-pipelines-performance
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_pipelines
  docs-version: "1.24"
  skill-group: "OpenShift Platform"
description: >
  Use when tuning resource use of this demo's Tekton runs: step compute
  resources, co-scheduling of PVC workspaces, pruning volume, TaskRun pod
  evictions, resource quotas and priority classes, and whether multicluster
  (hub/spoke, MultiKueue) pipelines apply. Do NOT use for operator install or
  TektonConfig field ownership (use ocp-pipelines-install-config), pipeline
  authoring (use ocp-pipelines-cicd), or GPU Kueue queues (use
  rhoai-kueue-workload-management).
---

# OpenShift Pipelines performance in this repo

Thin skill: the few repo decisions here, product guidance in the linked
OpenShift Pipelines 1.24 sections. The repo sets no quota, priority class or
multicluster configuration for pipelines.

## When to use

- A TaskRun is OOMKilled, evicted, or waits to be scheduled.
- Someone proposes ResourceQuota, LimitRange, priority classes or
  multicluster pipelines for the build namespaces.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Project Tasks set no step `computeResources`; namespace defaults apply | `gitops/stages/070-advanced-app-platform/pipelines/project-pipeline/task-*.yaml` | [Step compute resources][step] |
| Migration provisioning step: requests 256Mi, limit 1Gi (an earlier 256Mi limit OOMKilled at CLI start) | `gitops/stages/070-advanced-app-platform/pipelines/build/task-provision-migration-run.yaml` | [Override step resources][override] |
| `coschedule: pipelineruns` keeps all pods of a run on one node so RWO workspaces do not reattach | `gitops/stages/070-advanced-app-platform/pipelines/build/tektonconfig-affinity.yaml` | not in the 1.24 Red Hat guides (upstream Tekton field) |
| Pruner keep 10 hourly limits completed-pod and PVC buildup | `gitops/stages/070-advanced-app-platform/pipelines/operators/configure-tekton-pruner.yaml` | see `ocp-pipelines-install-config` |
| No ResourceQuota, priority class or multicluster (hub/spoke) setup for pipelines | — | [Quota alternatives][quota-alt], [Multicluster][multi] |

## Procedure

Read-only, after the OpenShift safety guard in `AGENTS.md`:

```bash
oc get taskrun -n <namespace> -o custom-columns=NAME:.metadata.name,REASON:.status.conditions[0].reason
oc get pod -n <namespace> -l tekton.dev/taskRun=<taskrun> -o jsonpath='{.items[0].status.containerStatuses[*].state}{"\n"}'
oc get resourcequota,limitrange -n <namespace>
```

Change step resources in the Task in Git, then
`./stages/070-advanced-app-platform/validate.sh --static`.

## Pitfalls

- Evictions for ephemeral storage come from node image caches (modelcars),
  not from the TaskRun: `docs/TROUBLESHOOTING.md#pipeline-or-workspace-pods-evicted-for-ephemeral-storage`.
- A quota on a build namespace needs requests on every step, which the
  project Tasks do not set; read [Quota alternatives][quota-alt] first.
- Priority classes also apply to the affinity-assistant pod ([priority class quota][prio]).

## Official documentation (OpenShift Pipelines 1.24)

| Topic | Section |
|---|---|
| Performance and resource consumption | [Improving performance][improve], [Resource consumption][consumption], [Mitigating extra consumption][mitigate] |
| Step resources | [Override step resources][override], [Step compute resources][step] |
| Quotas | [Quota alternatives][quota-alt], [Priority class quota][prio] |
| Node drains | [Eviction protection][eviction] |
| Multicluster (not used) | [Multicluster support][multi] |
| Controller tuning | [TektonConfig performance tuning][tuning] |

## Related skills

`ocp-pipelines-install-config`, `ocp-pipelines-cicd`, `ocp-nodes`.

[improve]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/managing_performance_and_resource_use/index#improving-performance_managing-pipelines-performance
[consumption]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/managing_performance_and_resource_use/index#op-understanding-pipelines-resource-consumption_reducing-pipelines-resource-consumption
[mitigate]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/managing_performance_and_resource_use/index#op-mitigating-extra-pipeline-resource-consumption_reducing-pipelines-resource-consumption
[override]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/managing_performance_and_resource_use/index#op-override-step-resources-pipelinerun_reducing-pipelines-resource-consumption
[step]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/managing_performance_and_resource_use/index#op-setting-compute-resources-for-a-task-step_reducing-pipelines-resource-consumption
[quota-alt]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/managing_performance_and_resource_use/index#alternative-approaches-compute-resource-quota-pipelines_setting-compute-resource-quota-for-openshift-pipelines
[prio]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/managing_performance_and_resource_use/index#specifying-pipelines-resource-quota-using-priority-class_setting-compute-resource-quota-for-openshift-pipelines
[eviction]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/managing_performance_and_resource_use/index#protecting-tekton-workloads-from-eviction-during-node-drains
[multi]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/managing_performance_and_resource_use/index#configuring-multicluster-support
[tuning]: https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/1.24/html-single/installing_and_configuring/index#op-performance-tuning-using-tektonconfig-cr_customizing-configurations-in-the-tektonconfig-cr
