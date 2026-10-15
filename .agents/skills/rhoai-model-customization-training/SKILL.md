---
name: rhoai-model-customization-training
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when someone proposes customizing a model with the OpenShift AI 3.5
  model customization workflow: the Red Hat Python index, Docling data
  processing, SDG Hub synthetic data, MCP tool-calling evaluation data,
  Training Hub fine-tuning (OSFT, SFT, LoRA), Training Hub with MLflow or
  Kubeflow Trainer, or inference-time scaling. Not deployed in this demo:
  the served models are used as published. Do NOT use for TrainJob and
  PyTorchJob mechanics (use rhoai-distributed-workload-workflows), pipeline
  servers (use rhoai-ai-pipelines), model evaluation (use rhoai-evaluation),
  or RAG ingestion (use rhoai-enterprise-rag).
---

# RHOAI Model Customization

Thin skill: model customization in OpenShift AI 3.5. **Not deployed in this
demo**: no fine-tuned models, no Docling or SDG Hub jobs, no training
operators. The models in Stages 030 and 040 are served as published and
qualified in Stage 050.

## When to use

- A stage proposes fine-tuning a model for coding or tool calling.
- Someone asks whether the demo can run the customization notebooks.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| No customization stage; `trainer` and `trainingoperator` are `Removed` in `default-dsc` | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/datasciencecluster.yaml` | [Model customization workflow][workflow] |
| A customized model would be qualified like any candidate: served in `evaluated-models` and run through the qualification pipeline before promotion | `gitops/stages/050-model-evaluation/050-model-qualification/README.md` | see `rhoai-evaluation`, `rhoai-ai-pipelines` |
| Experiment tracking would use the Stage 050 MLflow server | `gitops/stages/050-model-evaluation/050-mlflow/` | [Track experiments with MLflow and Training Hub][mlflow] |

## If enabled

1. Decide the scope: data preparation (Docling, SDG Hub) runs in a
   workbench or an AI pipeline; distributed fine-tuning with the Kubeflow
   Trainer needs `trainer` enabled (`rhoai-distributed-workloads`) and GPU
   quota (`rhoai-distributed-workload-operations`).
2. Install packages from the Red Hat Python index into a supported workbench
   image; record any other package source as a demo exception.
3. Pipelines that automate data processing follow
   `rhoai-kfp-pipeline-authoring` and run on a pipeline server
   (`rhoai-ai-pipelines`).
4. Keep source data, synthetic data and checkpoints in project S3
   connections or PVCs; credentials stay out of Git.
5. Promote the result only through Stage 050 qualification.

## Pitfalls

- The guide states which parts Red Hat supports (index packages on
  supported images versus your own flows); read the support philosophy
  chapter before presenting a flow as supported.
- GPU memory for fine-tuning comes from the same two GPUs per ClusterQueue
  the model servers use; estimate memory first.
- MCP tool exploration calls real tools; read the safety section before
  pointing it at a writable MCP server.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Workflow | [Model customization workflow][workflow], [End-to-end workflow][e2e], [Support philosophy][support] |
| Environment | [Set up your work environment][setup], [Red Hat Python index][index] |
| Data | [Prepare your data (Docling)][data], [Automate with AI pipelines][data-kfp], [Generate synthetic data][sdg] |
| Tool calling | [Generate evaluation data for tool calling][mcp], [MCP safety][mcp-safety] |
| Training | [Train the model][train], [Support matrix][matrix], [Estimate memory][memory], [Distribute with Kubeflow Trainer][distribute] |
| Inference | [Inference-time scaling][scaling] |

## Related skills

`rhoai-distributed-workload-workflows`, `rhoai-distributed-workloads`,
`rhoai-ai-pipelines`, `rhoai-kfp-pipeline-authoring`, `rhoai-mlflow`,
`rhoai-evaluation`, `rhoai-enterprise-rag`.

[workflow]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/customize_models_for_gen_ai_and_agentic_ai_applications/index#overview-of-the-model-customization-workflow_custom-models
[e2e]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/customize_models_for_gen_ai_and_agentic_ai_applications/index#end-to-end-model-customization-workflow_custom-models
[support]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/customize_models_for_gen_ai_and_agentic_ai_applications/index#support-philosophy_custom-models
[setup]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/customize_models_for_gen_ai_and_agentic_ai_applications/index#set-up-your-working-environment_custom-models
[index]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/customize_models_for_gen_ai_and_agentic_ai_applications/index#about-the-python-index_custom-models
[data]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/customize_models_for_gen_ai_and_agentic_ai_applications/index#prepare-your-data-for-ai-consumption_custom-models
[data-kfp]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/customize_models_for_gen_ai_and_agentic_ai_applications/index#automate_data_processing_steps_by_building_ai_pipelines
[sdg]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/customize_models_for_gen_ai_and_agentic_ai_applications/index#generate-synthetic-data_custom-models
[mcp]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/customize_models_for_gen_ai_and_agentic_ai_applications/index#generate-evaluation-data-for-tool-calling_custom-models
[mcp-safety]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/customize_models_for_gen_ai_and_agentic_ai_applications/index#safety-considerations-for-mcp-tool-exploration_custom-models
[train]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/customize_models_for_gen_ai_and_agentic_ai_applications/index#train-the-model-by-using-your-prepared-data_custom-models
[matrix]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/customize_models_for_gen_ai_and_agentic_ai_applications/index#training-hub-algorithm-and-model-support-matrix_custom-models
[memory]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/customize_models_for_gen_ai_and_agentic_ai_applications/index#estimate-memory-usage_custom-models
[mlflow]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/customize_models_for_gen_ai_and_agentic_ai_applications/index#track-experiments-with-mlflow_custom-models
[distribute]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/customize_models_for_gen_ai_and_agentic_ai_applications/index#distribute-training-jobs_custom-models
[scaling]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/customize_models_for_gen_ai_and_agentic_ai_applications/index#improve-model-accuracy_custom-models
