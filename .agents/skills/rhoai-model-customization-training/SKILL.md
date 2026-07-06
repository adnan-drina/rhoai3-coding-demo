---
name: rhoai-model-customization-training
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or operating Red Hat OpenShift AI model
  customization and training workflows from the official Customize Models for
  Gen AI and Agentic AI Applications guide: Red Hat Python index, disconnected
  package mirroring, JupyterLab workbench setup, Docling data preparation,
  Kubeflow Pipeline data processing, SDG Hub synthetic data generation,
  Training Hub fine-tuning with SFT, OSFT, LoRA, and QLoRA, memory estimation,
  MLflow tracking handoff, Kubeflow Trainer distributed fine-tuning,
  inference-time scaling with ITS Hub, Knowledge Tuning examples, and Red Hat
  support philosophy for model customization packages. Do NOT use for generic
  workbench lifecycle (use rhoai-project-workflows), generic IDE workflows
  (use rhoai-data-science-ide-workflows), AI Pipelines server administration
  (use rhoai-ai-pipelines), repo-specific KFP code (use
  rhoai-kfp-pipeline-authoring), MLflow platform or SDK configuration (use
  rhoai-mlflow), distributed workload operations outside Training Hub context
  (use rhoai-distributed-workload-workflows), model serving platform
  configuration (use rhoai-model-serving-platform), formal evaluation
  workflows (use rhoai-model-evaluation), runtime guardrails and safety
  controls (use rhoai-guardrails-safety), or live cluster changes without the
  OpenShift safety guard.
---

# RHOAI Model Customization And Training

Use this skill for Red Hat OpenShift AI model customization workflows on the
active product baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product workflow details.
Official Red Hat documentation is product authority. This skill adapts the
official Customize Models for Gen AI and Agentic AI Applications guide to this
repo's demo workflow and governance model.

## Scope

This skill covers:

- end-to-end model customization workflow framing
- Red Hat Python index use, package support posture, and disconnected mirroring
- JupyterLab workbench setup with Red Hat AI package index access
- example notebook repository selection and clone workflow
- Docling data preparation for unstructured data
- Docling-based Kubeflow Pipeline data processing examples
- SDG Hub synthetic data generation examples and KFP patterns
- Training Hub fine-tuning examples
- Training Hub algorithm and model support matrix review
- memory estimation for SFT and OSFT
- SFT, OSFT, LoRA, and QLoRA tradeoffs
- in-workbench Training Hub execution with the Training Jupyter PyTorch CUDA
  image
- MLflow tracking handoff for Training Hub
- distributed fine-tuning with Kubeflow Trainer
- inference-time scaling with ITS Hub against OpenAI-compatible endpoints
- end-to-end Knowledge Tuning notebook and pipeline examples
- Red Hat support philosophy for customization Python packages

Use other skills for adjacent work:

- `rhoai-project-workflows` for project, workbench, connection, storage, and
  project access lifecycle
- `rhoai-data-science-ide-workflows` for JupyterLab Git, notebook, and package
  workflows inside a running workbench
- `rhoai-workbenches-custom-images` and `rhoai-workbench-image-import` for
  custom workbench image creation or import
- `rhoai-ai-pipelines` for AI Pipelines product workflows, server lifecycle,
  imported pipelines, runs, schedules, logs, and caching
- `rhoai-kfp-pipeline-authoring` for repo-specific KFP Python pipeline code
- `rhoai-distributed-workload-workflows` for user workflows using Ray,
  CodeFlare, Training Operator, Kubeflow Trainer, `PyTorchJob`, or `TrainJob`
- `rhoai-mlflow` for MLflow platform setup, SDK authentication, experiment
  tracking, and artifact storage
- `rhoai-model-serving-platform` for KServe, vLLM, serving runtimes, and
  OpenAI-compatible model endpoints
- `rhoai-model-registry-workflows` for registering and deploying trained model
  versions
- `rhoai-evaluation` for official EvalHub, LM-Eval, and automated risk
  assessment workflows after customization
- `rhoai-guardrails-safety` for runtime guardrails, PII checks, prompt
  injection checks, and guarded generation around customized models
- `rhoai-model-evaluation` for legacy repo-specific RAGAS, custom judge, and
  Step 08 evaluation rebuild details
- `rhoai-api-tiers` when manifests or APIs from training workflows become
  durable GitOps contracts

## Demo Policy

For this repo:

- Treat the official guide as the source of truth for Red Hat model
  customization workflow shape: prepare data, generate synthetic data,
  fine-tune, track experiments, distribute training when needed, improve
  inference behavior, then serve and consume the customized model.
- Prefer Red Hat-provided workbench images and the Red Hat Python index for
  customization notebooks. Do not mix arbitrary package sources into demo
  notebooks without a documented exception.
- For disconnected environments, mirror the versioned Red Hat Python index that
  matches the active product baseline and runtime.
- Label model customization Python package support accurately: Red Hat supports
  installation from the Red Hat Python index on supported OpenShift AI base
  images and supports the underlying OpenShift AI platform; custom flows and
  standalone package use are not directly supported as product behavior.
- Use Docling for source-grounded data processing examples, especially
  document conversion, chunking, extraction, subset selection, and RAG
  preparation.
- Use SDG Hub for synthetic data generation only when synthetic examples are
  clearly labeled and separated from real enterprise records.
- Choose Training Hub algorithms intentionally:
  - SFT for supervised full fine-tuning workflows
  - OSFT for controlled continual-learning style customization
  - LoRA or QLoRA for parameter-efficient fine-tuning and lower memory use
- Use the memory estimator before promising that a model will fit on the demo
  GPU profile.
- Use MLflow for training evidence when comparing runs or presenting
  reproducibility.
- Use Kubeflow Trainer only when distributed training is required; keep
  notebook-only training for small interactive experiments.
- Treat inference-time scaling as inference behavior improvement that does not
  change model weights and increases compute per query.
- Do not present upstream GitHub examples as active demo implementation until
  they are adapted, reviewed, and tied to active project GitOps and validation.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - README concept authoring for model customization
   - Red Hat Python index or disconnected package mirror review
   - workbench and example notebook setup
   - Docling data preparation
   - SDG Hub synthetic data generation
   - Training Hub algorithm or model support review
   - memory estimation and GPU sizing
   - MLflow tracking handoff
   - Kubeflow Trainer distributed fine-tuning
   - inference-time scaling
   - end-to-end Knowledge Tuning workflow alignment
4. Use `examples/model-customization-patterns.md` for focused review patterns.
5. For live cluster work, follow the OpenShift safety guard in `AGENTS.md`.
6. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/model-customization-patterns.md`
