---
name: ocp-ai-workloads
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp
  docs-version: "4.22"
  skill-group: "OpenShift Platform"
description: >
  Use when reviewing the OpenShift AI-workload operators this repo installs: the
  Red Hat build of Kueue Operator in
  gitops/stages/020-gpu-infrastructure-private-ai/kueue/ (stable-v1.4,
  openshift-kueue-operator, cert-manager prerequisite, DSC Unmanaged hook Job)
  and the Leader Worker Set Operator in
  gitops/stages/040-governed-models-as-a-service/maas-operators/lws/
  (stable-v1.0, LeaderWorkerSetOperator cluster), or deciding whether JobSet is
  needed. Do NOT use for ResourceFlavor, ClusterQueue, LocalQueue and hardware
  profile design (use rhoai-kueue-workload-management and
  rhoai-hardware-profiles) or llm-d serving (use
  rhoai-distributed-inference-llmd).
---

# OCP AI workloads

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift Container Platform 4.22 sections. Detailed records:
`gitops/stages/020-gpu-infrastructure-private-ai/kueue/README.md` and
`gitops/stages/040-governed-models-as-a-service/maas-operators/README.md`.

## When to use

- A change touches the Kueue or LWS operator installation, their channel or
  the minimums in `scripts/platform/check-operator-policy.py`.
- Stage 020 sync hangs on `job-enable-dsc-kueue`, or the `Kueue` CR is not
  `Available`.
- Someone proposes multi-node serving (LWS) or JobSet.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Red Hat build of Kueue Operator: namespace `openshift-kueue-operator` with cluster-monitoring label, all-namespaces OperatorGroup, Subscription `kueue-operator` on `stable-v1.4`, Automatic; policy minimum `1.4.2` | `kueue/namespace.yaml`, `kueue/operatorgroup.yaml`, `kueue/subscription.yaml`, `scripts/platform/check-operator-policy.py` | [Red Hat build of Kueue][kueue] |
| cert-manager Operator is a prerequisite but not declared here; `deploy.sh` refuses to continue without a `Succeeded` `cert-manager-operator.v1.20.*` CSV | `stages/020-gpu-infrastructure-private-ai/deploy.sh` | [Red Hat build of Kueue][kueue] |
| `Kueue` CR (`cluster`) is not in Git: OpenShift AI creates it when the DSC sets kueue `Unmanaged` | (operator-created) | [Red Hat build of Kueue][kueue] |
| DSC kueue subtree set to `Unmanaged`, `autoCreateQueues: false` by an Argo CD Sync hook Job with scoped RBAC, because Stage 010 owns `default-dsc` and delegates `/spec/components/kueue` | `kueue/dsc-enablement/` | [Red Hat build of Kueue][kueue] |
| Leader Worker Set Operator: namespace `openshift-lws-operator`, own-namespace OperatorGroup, Subscription `leader-worker-set` on `stable-v1.0`, Automatic, `LeaderWorkerSetOperator` `cluster` `Managed`; policy minimum `1.0.1` | `gitops/stages/040-governed-models-as-a-service/maas-operators/lws/` | [Leader Worker Set Operator][lws] |
| LWS is installed only as the llm-d multi-node prerequisite; current models are single-node, no `LeaderWorkerSet` objects | `gitops/stages/040-governed-models-as-a-service/maas-operators/README.md` | [Leader Worker Set Operator][lws] |
| JobSet Operator not installed | (none declared) | [JobSet Operator][jobset] |

Paths are relative to `gitops/stages/020-gpu-infrastructure-private-ai/` unless they start with `gitops/`, `stages/` or `scripts/`.

## Procedure

1. Change channels in Git and the matching entries in
   `scripts/platform/check-operator-policy.py` (`channels` and `minimum`) in
   the same commit; `deploy.sh` refuses an unreviewed channel.
2. Deploy and validate Kueue with
   `./stages/020-gpu-infrastructure-private-ai/deploy.sh` and `validate.sh`
   (CSV current, DSC `Unmanaged` with `autoCreateQueues=false`, one `Kueue`
   `Available` and `CertManagerAvailable`); LWS with
   `./stages/040-governed-models-as-a-service/validate.sh`.
3. Read-only checks after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get subscription kueue-operator -n openshift-kueue-operator -o jsonpath='{.status.installedCSV}{"\n"}'
   oc get kueue cluster -o jsonpath='{range .status.conditions[*]}{.type}={.status} {end}{"\n"}'
   oc get datasciencecluster default-dsc -o jsonpath='{.spec.components.kueue}{"\n"}'
   oc get subscription leader-worker-set -n openshift-lws-operator -o jsonpath='{.status.installedCSV}{"\n"}'
   ```

## Pitfalls

- Automatic approval renames the CSV; anything that waits for a fixed CSV
  name hangs. The hook follows `status.installedCSV`
  (`docs/TROUBLESHOOTING.md#stage-020-sync-hangs-on-job-enable-dsc-kueue-after-an-operator-update`).
- `Managed` Kueue in the DSC is deprecated and incompatible with the Red Hat
  build of Kueue Operator; do not switch back.
- With `autoCreateQueues: false` nothing creates queues for a new namespace;
  queues come from `020-gpu-quotas` and the consuming stages
  (`docs/TROUBLESHOOTING.md#kueue-or-gpuaas-queue-resources-are-missing`).
- A rolling update of a 1-replica GPU model with the GPU quota fully admitted
  deadlocks in `SchedulingGated`
  (`docs/TROUBLESHOOTING.md#model-rollout-deadlocks-with-the-new-pod-schedulinggated`).
- Kueue `Workload` creation for `LLMInferenceService` is not a documented
  integration; treat missing Workloads as a warning
  (`docs/TROUBLESHOOTING.md#private-models-do-not-produce-kueue-workloads`).

## Official documentation (OpenShift Container Platform 4.22)

| Topic | Section |
|---|---|
| Overview | [Overview of AI workloads on OpenShift Container Platform][about] |
| Kueue | [Red Hat build of Kueue][kueue] |
| LWS | [Leader Worker Set Operator][lws] |
| Not used here | [JobSet Operator][jobset] |

## Related skills

`rhoai-kueue-workload-management`, `rhoai-hardware-profiles`,
`rhoai-distributed-workloads`, `rhoai-distributed-inference-llmd`,
`rhoai-dsci-dsc-configuration`, `ocp-nodes`.

[about]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/ai_workloads/index#ai-workloads-about
[kueue]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/ai_workloads/index#red-hat-build-of-kueue
[lws]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/ai_workloads/index#leader-worker-set-operator
[jobset]: https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html-single/ai_workloads/index#jobset-operator
