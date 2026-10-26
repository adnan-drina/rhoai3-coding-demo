---
name: rhoai-hardware-profiles
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when reviewing or changing the OpenShift AI HardwareProfile objects of
  Stage 020 (cpu-default, gpu-rtxpro6000, gpu-reserved-demo in
  redhat-ods-applications, under gitops/stages/020-gpu-infrastructure-private-ai/020-gpu-quotas/hardware-profiles/),
  their Queue scheduling and LocalQueue names, CPU/memory/GPU limits sized to
  g7e.2xlarge or g6e.2xlarge workers, the hardware-profile annotations on
  Stage 040/050 model servers, or recommended-accelerator annotations on serving
  runtimes. Do NOT use for GPU nodes, NFD or the NVIDIA GPU Operator (use
  rhoai-nvidia-gpu-accelerators), Kueue queues and DSC integration (use
  rhoai-kueue-workload-management), or project-scoped profile copies (use
  rhoai-project-scoped-resources).
---

# RHOAI Hardware Profiles

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/020-gpu-infrastructure-private-ai/020-gpu-quotas/README.md`.

## When to use

- A change touches `gitops/stages/020-gpu-infrastructure-private-ai/020-gpu-quotas/hardware-profiles/`.
- A model server or workbench names a profile (`opendatahub.io/hardware-profile-name`)
  or a profile does not appear in the dashboard.
- A profile's limits no longer fit the GPU worker it targets.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Three global profiles in `redhat-ods-applications`: `cpu-default`, `gpu-rtxpro6000` (default GPU, one RTX PRO 6000 per `g7e.2xlarge`), `gpu-reserved-demo` (L40S pool, `g6e.2xlarge`) | `020-gpu-quotas/hardware-profiles/*.yaml` | [Manage hardware profiles][hwp] |
| All three use scheduling type `Queue` with `kueue.localQueueName` `lq-<profile>`; no node selectors or tolerations, the Kueue ResourceFlavor places the pod | `020-gpu-quotas/hardware-profiles/*.yaml`, `020-gpu-quotas/queues/gpu-*.yaml` | [Create a hardware profile][hwp-create]; [Kueue workload management][kueue] |
| Accelerator identifier `nvidia.com/gpu`, exactly 1 per workload (min = max = 1); one physical GPU per unit, no time-slicing | `020-gpu-quotas/hardware-profiles/gpu-*.yaml` | [Create a hardware profile][hwp-create]; time slicing not used ([GPU time slicing][timeslice]) |
| `gpu-rtxpro6000` caps CPU at 7 and memory at 56Gi so one pod fits one `g7e.2xlarge` worker (about 7.5 CPU / 58 GiB allocatable) | `020-gpu-quotas/hardware-profiles/gpu-rtxpro6000.yaml`, comment in `queues/cq-gpu-rtxpro6000.yaml` | [Create a hardware profile][hwp-create] |
| The profiles' LocalQueues exist only in `demo-sandbox` (Stage 020), `internal-models` (Stage 040) and `evaluated-models` (Stage 050); recorded deviation from "a queue name that exists in all user projects" | `020-gpu-quotas/queues/lq-*.yaml`, `020-gpu-quotas/README.md` (Alignment table) | [Create a hardware profile][hwp-create] |
| Stage 040 Qwen model names `gpu-rtxpro6000` plus label `kueue.x-k8s.io/queue-name: lq-gpu-rtxpro6000`; Stage 050 candidate names `gpu-rtxpro6000` / `lq-gpu-rtxpro6000`, the risk assessment model `gpu-reserved-demo` / `lq-gpu-reserved-demo` | `gitops/stages/040-governed-models-as-a-service/040-local-models/qwen38-27b-llminferenceservice.yaml`, `gitops/stages/050-model-evaluation/050-model-qualification/candidate-qwen3-8-27b-nvfp4.yaml`, `gitops/stages/050-model-evaluation/050-model-qualification/risk-assessment-gemma-2-9b-abliterated.yaml` | [Kueue workflow][kueue-flow] |
| ServingRuntime `vllm-cuda-runtime` carries `opendatahub.io/recommended-accelerators: '["nvidia.com/gpu"]'` | `gitops/stages/050-model-evaluation/050-model-qualification/serving-runtime.yaml` | [Recommended accelerator for serving runtimes][rec-runtime] |
| Profiles are GitOps objects of `020-gpu-quotas` at sync-wave 5 (after their ClusterQueues at wave 4), `SkipDryRunOnMissingResource` because the CRD comes from OpenShift AI | `gitops/applications/020-gpu-quotas.yaml` | — (repo GitOps rule) |

The `default-profile` HardwareProfile is created by OpenShift AI and is not in Git.

## Procedure

1. Change profiles in Git only. Before adding a field, read the served schema:
   `oc explain hardwareprofile.spec --api-version=infrastructure.opendatahub.io/v1`
   (the 3.5 guide names the CRD but not its API version).
2. A new GPU profile needs its own ResourceFlavor, ClusterQueue and LocalQueues
   first (see `rhoai-kueue-workload-management`), and a LocalQueue in every
   project that will select it.
3. Size `maxCount` for CPU and memory at or below one worker's allocatable
   capacity; check with `oc describe node -l cluster-api/accelerator=<pool>`.
4. Deploy and validate:
   `./stages/020-gpu-infrastructure-private-ai/deploy.sh`, then
   `./stages/020-gpu-infrastructure-private-ai/validate.sh --readiness`
   (checks each profile names `lq-<suffix>`).
5. By hand, after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get hardwareprofile -n redhat-ods-applications \
     -o custom-columns=NAME:.metadata.name,QUEUE:.spec.scheduling.kueue.localQueueName
   oc get localqueue -A
   ```

## Pitfalls

- A queue-based profile must not carry node selectors or tolerations
  ([Kueue workload management][kueue]); placement belongs to the ResourceFlavor.
- Selecting a global profile in a project without its LocalQueue fails
  admission ("local_queue provided does not exist", see
  [Kueue troubleshooting][kueue-lq-missing]).
- Profile maximums stay below one worker's allocatable capacity:
  `gpu-reserved-demo` allows at most 7 CPU / 56Gi on an 8 vCPU / 64 GiB L40S
  instance, like the RTX profile. `gpu-reserved-demo`'s display name still says "NVIDIA L40S (48 GB)";
  the L40S pool is parked at zero and used only by the Stage 050 risk assessment model.
- Profiles appear in the dashboard only while `disableKueue: false`
  (`gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/odhdashboardconfig.yaml`).

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Profile lifecycle | [Manage hardware profiles][hwp], [Create][hwp-create], [Update][hwp-update], [Delete][hwp-delete] |
| Recommended accelerators | [Workbench images][rec-wb], [Serving runtimes][rec-runtime] |
| Kueue handoff | [Kueue workload management][kueue], [Kueue workflow][kueue-flow], [Kueue troubleshooting][kueue-lq-missing] |
| Time slicing (not used) | [Enable GPU time slicing][timeslice] |

## Related skills

`rhoai-nvidia-gpu-accelerators`, `rhoai-kueue-workload-management`,
`rhoai-project-scoped-resources`, `rhoai-model-deployment`,
`rhoai-workbench-image-import`, `rhoai-model-serving-platform`.

[hwp]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_accelerators/index#working-with-hardware-profiles_accelerators
[hwp-create]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_accelerators/index#creating-a-hardware-profile_accelerators
[hwp-update]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_accelerators/index#updating-a-hardware-profile_accelerators
[hwp-delete]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_accelerators/index#deleting-a-hardware-profile_accelerators
[rec-wb]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_accelerators/index#configuring-a-recommended-accelerator-for-workbench-images_accelerators
[rec-runtime]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_accelerators/index#configuring-a-recommended-accelerator-for-serving-runtimes_accelerators
[timeslice]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_accelerators/index#about-gpu-time-slicing_accelerators
[kueue]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#overview-of-managing-workloads-with-kueue_kueue
[kueue-flow]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#kueue-workflow_kueue
[kueue-lq-missing]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#a_user_receives_a_local_queue_provided_does_not_exist_error_message
