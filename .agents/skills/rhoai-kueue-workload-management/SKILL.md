---
name: rhoai-kueue-workload-management
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when reviewing or changing how this demo integrates OpenShift AI with the
  Red Hat build of Kueue: the kueue-operator Subscription (stable-v1.4), the
  job-enable-dsc-kueue hook that sets default-dsc kueue Unmanaged with
  autoCreateQueues false, the Stage 020 ResourceFlavors, ClusterQueues and
  LocalQueues (cq-gpu-rtxpro6000, cq-gpu-reserved-demo, cq-cpu-default),
  kueue.openshift.io/managed namespaces, queue-name labels on model servers,
  disableKueue, and Kueue admission errors. Do NOT use for HardwareProfile
  objects (use rhoai-hardware-profiles), Ray/training quota examples or RDMA
  (use rhoai-distributed-workload-operations), or the OCP Kueue API itself
  (use ocp-ai-workloads).
---

# RHOAI Kueue Workload Management

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/020-gpu-infrastructure-private-ai/020-kueue/README.md` and
`gitops/stages/020-gpu-infrastructure-private-ai/020-gpu-quotas/README.md`.

## When to use

- A change touches `gitops/stages/020-gpu-infrastructure-private-ai/020-kueue/` or `.../gpu-quotas/queues/`.
- A project needs a LocalQueue, or a workload is not admitted.
- The Stage 020 sync waits on `job-enable-dsc-kueue`.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Red Hat build of Kueue Operator, channel `stable-v1.4`, Automatic, in `openshift-kueue-operator` (cluster monitoring label); minimum 1.4.2 enforced | `020-kueue/subscription.yaml`, `020-kueue/namespace.yaml`, `check_operator_policy` in `scripts/lib.sh` | [Kueue workload management][kueue]; OCP side: `ocp-ai-workloads` |
| DSC `kueue.managementState: Unmanaged`, `autoCreateQueues: false`, set by an Argo CD Sync hook Job because Stage 010 owns `default-dsc` and delegates `/spec/components/kueue` | `020-kueue/dsc-enablement/job.yaml`, `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/datasciencecluster.yaml` | [Kueue workload management][kueue] |
| The `Kueue` CR is left to OpenShift AI (live name `cluster`); not in Git | — | [Kueue workload management][kueue] |
| cert-manager not declared; `deploy.sh` requires a `cert-manager-operator.v1.20.*` CSV `Succeeded` | `stages/020-gpu-infrastructure-private-ai/deploy.sh` | [Configure workload management][kueue-config] |
| Admin-owned queues in Git, `kueue.x-k8s.io/v1beta2`: flavors `default-flavor`, `gpu-rtxpro6000`, `gpu-l40s`; one ClusterQueue per GPU type (2 GPUs each) plus `cq-cpu-default`; LocalQueues `lq-*` in `demo-sandbox` | `020-gpu-quotas/queues/` | [Manage queues outside the Operator][kueue-outside] |
| GPU flavors select their pool by `cluster-api/accelerator` and tolerate `nvidia-gpu-only`; no cohorts, no preemption settings (non-preemptive, needed for workbenches) | `020-gpu-quotas/queues/gpu-*.yaml`, `cq-*.yaml` | [Kueue workload management][kueue] |
| Managed namespaces: `demo-sandbox` (Stage 010), `internal-models` (Stage 040), `evaluated-models` (Stage 050) carry `kueue.openshift.io/managed: "true"` and their own LocalQueues | `gitops/stages/010-openshift-ai-platform-foundation/010-access/namespace-demo-sandbox.yaml`, `gitops/stages/040-governed-models-as-a-service/040-local-models/`, `gitops/stages/050-model-evaluation/050-model-qualification/` | [Kueue workload management][kueue] |
| Dashboard Kueue UI on: `disableKueue: false` | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/odhdashboardconfig.yaml` | [Enable Kueue in the dashboard][kueue-dash] |

## Procedure

1. Change Subscriptions, queues and flavors in Git only. A new GPU type gets
   its own ResourceFlavor, ClusterQueue, LocalQueues in each consuming project,
   and a profile (`rhoai-hardware-profiles`).
2. Deploy and validate:
   `./stages/020-gpu-infrastructure-private-ai/deploy.sh`, then
   `./stages/020-gpu-infrastructure-private-ai/validate.sh --readiness`
   (DSC delegation, `Kueue` Available and `CertManagerAvailable`, each flavor
   selects only its pool, queues `Active`, LocalQueues in `internal-models`
   and `evaluated-models`).
3. By hand, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get datasciencecluster default-dsc -o jsonpath='{.spec.components.kueue}{"\n"}'
   oc get kueue -A
   oc get resourceflavor,clusterqueue
   oc get localqueue -A
   oc get workloads.kueue.x-k8s.io -A
   ```

4. Queue-admission acceptance test (Pod integration): `docs/OPERATIONS.md#stage-020`.

## Pitfalls

- `Managed` (embedded Kueue) is deprecated and incompatible with the Red Hat
  build of Kueue Operator ([Kueue workload management][kueue]); migration:
  [Migrate to the Red Hat build of Kueue Operator][kueue-migrate].
- In 3.5 `autoCreateQueues` defaults to `false`; every project that selects a
  queue-based profile needs the LocalQueue, or admission fails
  ([local_queue does not exist][kueue-lq-missing]).
- The 3.5 enforcement list names `InferenceService`, `Notebook`, `PyTorchJob`,
  `RayCluster`, `RayJob`, not `LLMInferenceService`; the repo labels its
  `LLMInferenceService` objects anyway. Verify `Workload` objects live.
- Kueue fails a workload whose pods are not ready in 5 minutes by default; a
  large model image pull can hit this
  ([pod terminated before the image is pulled][kueue-imgpull]).
- Removing `/spec/components/kueue` from Stage 010 `ignoreDifferences` restores
  `Removed` and uninstalls the integration.
- Hook stuck after an operator update:
  `docs/TROUBLESHOOTING.md#stage-020-sync-hangs-on-job-enable-dsc-kueue-after-an-operator-update`;
  missing queues: `docs/TROUBLESHOOTING.md#kueue-or-gpuaas-queue-resources-are-missing`.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Concepts, states, enforcement | [Kueue workload management][kueue], [Kueue workflow][kueue-flow] |
| Configuration | [Configure workload management][kueue-config], [Enable Kueue in the dashboard][kueue-dash], [Manage queues outside the Operator][kueue-outside] |
| Troubleshooting | [Kueue troubleshooting][kueue-ts], [webhook error][kueue-webhook], [local_queue does not exist][kueue-lq-missing], [image pull][kueue-imgpull] |
| Migration | [Migrate to the Red Hat build of Kueue Operator][kueue-migrate] |

## Related skills

`rhoai-hardware-profiles`, `rhoai-distributed-workloads`,
`rhoai-distributed-workload-operations`, `ocp-ai-workloads`,
`rhoai-dsci-dsc-configuration`, `rhoai-dashboard-customization`.

[kueue]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#overview-of-managing-workloads-with-kueue_kueue
[kueue-flow]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#kueue-workflow_kueue
[kueue-config]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#configuring-workload-management-with-kueue_kueue
[kueue-dash]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#enabling-kueue-in-the-dashboard_kueue
[kueue-outside]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#managing-queues-outside-the-operator_kueue
[kueue-ts]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#troubleshooting-common-problems-with-Kueue_kueue
[kueue-webhook]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#a_user_receives_a_failed_to_call_webhook_error_message_for_kueue
[kueue-lq-missing]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#a_user_receives_a_local_queue_provided_does_not_exist_error_message
[kueue-imgpull]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#the_pod_provisioned_by_kueue_is_terminated_before_the_image_is_pulled
[kueue-migrate]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#migrating-to-the-rhbok-operator_kueue
