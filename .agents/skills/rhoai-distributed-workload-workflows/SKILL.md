---
name: rhoai-distributed-workload-workflows
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when a user workflow would run distributed jobs from OpenShift AI: Ray
  clusters through the CodeFlare SDK, Training Operator PyTorchJobs, Kubeflow
  Trainer v2 TrainJobs and runtimes, fine-tuning, checkpointing to PVC or S3,
  workload metrics, or user-facing Ray/Kueue errors. Not deployed in this demo.
  Do NOT use for enabling the components (use rhoai-distributed-workloads),
  quota, RDMA or administrator troubleshooting (use
  rhoai-distributed-workload-operations), Kueue integration (use
  rhoai-kueue-workload-management), the model customization notebooks (use
  rhoai-model-customization-training), or Spark (use
  rhoai-kubeflow-spark-operator).
---

# RHOAI Distributed Workload Workflows

Thin skill: data scientist workflows for distributed workloads in OpenShift AI
3.5. **Not deployed in this demo**: `ray`, `trainingoperator` and `trainer`
are `Removed` in `default-dsc`, so no RayCluster, PyTorchJob or TrainJob can
run here.

## When to use

- A future stage proposes training or fine-tuning inside the platform.
- Someone asks whether the demo can run a Ray or TrainJob example.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Distributed training operators not installed (`ray`, `trainingoperator`, `trainer` `Removed`) | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/datasciencecluster.yaml` | [Overview of distributed workloads][overview] |
| Workbenches exist (Stage 010 `workbenches` Managed) and `demo-sandbox` is a Kueue-managed project with GPU LocalQueues | `gitops/stages/010-openshift-ai-platform-foundation/010-access/namespace-demo-sandbox.yaml`, `gitops/stages/020-gpu-infrastructure-private-ai/020-gpu-quotas/queues/` | [Create a workbench for distributed training][workbench] |
| Experiment tracking uses the Stage 010 MLflow server | `gitops/stages/010-openshift-ai-platform-foundation/010-mlflow/` | see `rhoai-mlflow` |

## If enabled

1. Enable the operators and add quota first (`rhoai-distributed-workloads`,
   `rhoai-distributed-workload-operations`).
2. Pick one path (Ray, Training Operator `PyTorchJob`, or Trainer v2
   `TrainJob` with a `ClusterTrainingRuntime`) and confirm its support status
   for 3.5 (`rhoai-release-and-support-posture`) before demo use.
3. Keep jobs, runtimes and PVCs in GitOps under the new stage; tokens and S3
   keys stay in `.env` or cluster Secrets, never in notebooks.
4. Label every job with its project LocalQueue (`kueue.x-k8s.io/queue-name`).
5. After the OpenShift safety guard in `AGENTS.md`, read-only:

   ```bash
   oc get trainjobs,pytorchjobs,rayclusters -n <project>
   oc get workloads -n <project>
   ```

## Pitfalls

- GPU jobs share the two GPUs per ClusterQueue with model servers and
  workbenches; a training job can hold them for hours.
- Running Ray from an AI pipeline (Stage 050 has a pipeline server) still
  needs the Ray component and quota.
- Checkpoint storage must fit the local and shared storage needs in the
  checkpointing chapter before long runs.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Concepts | [Overview of distributed workloads][overview] |
| Environment | [Prepare the training environment][prepare], [Custom training images][images] |
| Ray | [Run Ray-based workloads][ray], [From AI pipelines][ray-pipelines] |
| Training Operator | [Run Training Operator workloads][kfto] |
| Trainer v2 | [Run Trainer v2 workloads][trainer], [Training runtimes][runtimes], [Fine-tune with Trainer v2][finetune] |
| Checkpointing | [Configure model checkpointing][checkpoint] |
| Monitoring, errors | [Monitor distributed workloads][monitor], [Troubleshooting for users][ts] |
| RoCE for LLM serving | [Configure RoCE networking][roce] |

## Related skills

`rhoai-distributed-workloads`, `rhoai-distributed-workload-operations`,
`rhoai-kueue-workload-management`, `rhoai-model-customization-training`,
`rhoai-mlflow`, `rhoai-basic-workbenches`.

[overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_distributed_workloads/index#overview-of-distributed-workloads_distributed-workloads
[prepare]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_distributed_workloads/index#preparing-the-distributed-training-environment_distributed-workloads
[workbench]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_distributed_workloads/index#creating-a-workbench-for-distributed-training_distributed-workloads
[images]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_distributed_workloads/index#managing-custom-training-images_distributed-workloads
[ray]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_distributed_workloads/index#running-ray-based-distributed-workloads_distributed-workloads
[ray-pipelines]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_distributed_workloads/index#running-distributed-data-science-workloads-from-ai-pipelines_distributed-workloads
[kfto]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_distributed_workloads/index#running-kfto-based-distributed-training-workloads_distributed-workloads
[trainer]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_distributed_workloads/index#running-kubeflow-trainerv2_distributed-workloads
[runtimes]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_distributed_workloads/index#understanding-and-using-training-runtimes_distributed-workloads
[finetune]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_distributed_workloads/index#fine-tuning-a-model-by-using-kubeflow-trainerv2_distributed-workloads
[checkpoint]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_distributed_workloads/index#configuring-model-checkpointing-for-distributed-training-with-kubeflow-trainerv2_distributed-workloads
[monitor]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_distributed_workloads/index#monitoring-distributed-workloads_distributed-workloads
[ts]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_distributed_workloads/index#troubleshooting-common-problems-with-distributed-workloads-for-users_distributed-workloads
[roce]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_distributed_workloads/index#configuring-roce-networking-for-distributed-llm-deployments_distributed-llm-roce
