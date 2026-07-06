---
name: rhoai-evaluation
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, deploying, or operating official Red Hat
  OpenShift AI evaluation workflows from the Evaluating AI systems guide:
  TrustyAI EvalHub deployment, EvalHub REST API, SDK, CLI, multi-tenancy,
  providers, benchmarks, collections, pass criteria, custom providers and
  adapters, MLflow tracking, OCI result export, tenant RBAC, LM-Eval setup,
  LMEvalJob custom resources, dashboard evaluations, external online access,
  remote code execution, PVC and S3 evaluation data, KServe/vLLM endpoint
  evaluation, LLM-as-a-judge metrics, and automated risk assessment with
  Garak, KFP, SDG, judge models, disconnected translation-model cache, and
  custom harm categories. Do NOT use for legacy repo-specific EvalHub scripts,
  RAGAS scoring, custom judge prompts, or Step 08 rebuild details (use
  rhoai-model-evaluation), AutoRAG product optimization (use rhoai-autorag),
  MLflow platform setup (use rhoai-mlflow), AI Pipelines administration (use
  rhoai-ai-pipelines), NeMo/FMS Guardrails control-plane configuration (use
  rhoai-guardrails-safety), or live cluster changes without the OpenShift
  safety guard.
---

# RHOAI Evaluation

Use this skill for official Red Hat OpenShift AI evaluation product workflows
on the active product baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product workflow details.
Official Red Hat documentation is product authority. This skill adapts the
official Evaluating AI systems guide to this repo's demo workflow and GitOps
review model.

## Scope

This skill covers:

- evaluation overview with TrustyAI EvalHub and LM-Eval
- EvalHub concepts: providers, benchmarks, collections, pass criteria,
  thresholds, jobs, and adapters
- EvalHub architecture, deployment through the TrustyAI Operator, and
  PostgreSQL storage
- EvalHub SDK and CLI installation and configuration
- EvalHub tenant header behavior and namespace-scoped resources
- provider and benchmark listing, evaluation job submission, result tracking,
  cancellation, and deletion
- built-in collections and custom collections
- API key and ServiceAccount token authentication for model endpoints
- S3 custom data for EvalHub jobs
- OCI result export and MLflow experiment tracking
- custom providers through API or ConfigMap
- custom evaluation adapters with the Python SDK
- EvalHub API endpoints, configuration, multi-tenancy, RBAC, tenant namespace
  setup, and roles
- LM-Eval setup with `LMEvalJob`
- LM-Eval online access, remote code execution, dashboard evaluations, custom
  Unitxt cards/templates/prompts, PVC, S3, KServe/vLLM endpoint evaluation, and
  LLM-as-a-judge metrics
- automated risk assessment with Garak/KFP/EvalHub, disconnected translation
  model cache, KFP SDK execution, result interpretation, custom harm
  categories, and configuration parameters

Use other skills for adjacent work:

- `rhoai-model-evaluation` for legacy repo-specific RAGAS, EvalHub, LM-Eval,
  custom judge prompts, and Step 08 rebuild details
- `rhoai-autorag` for product AutoRAG optimization runs, leaderboard review,
  and generated notebooks
- `rhoai-mlflow` for MLflow platform deployment, SDK authentication,
  workspaces, and artifact storage
- `rhoai-ai-pipelines` for AI Pipelines server lifecycle, KFP runs, logs,
  workspaces, and artifact storage
- `rhoai-kfp-pipeline-authoring` for repo-specific KFP Python implementation
- `rhoai-s3-object-storage-data` for S3-compatible object operations and
  credential handling outside evaluation-specific manifests
- `rhoai-model-serving-platform` for KServe, vLLM, serving runtimes, and
  OpenAI-compatible endpoint behavior
- `rhoai-model-customization-training` for Training Hub, SDG Hub, Docling, and
  model customization workflows
- `rhoai-guardrails-safety` for NeMo Guardrails, FMS Guardrails, detector
  services, and runtime safety controls that evaluation may test
- `rhoai-monitoring-trustyai` for TrustyAI bias and data-drift monitoring of
  supported OVMS model deployments
- `rhoai-api-tiers` for TrustyAI, EvalHub, and `LMEvalJob` API support posture

## Demo Policy

For this repo:

- Treat this skill as product authority for official RHOAI evaluation
  workflows. Use `rhoai-model-evaluation` only for legacy demo-specific
  evaluation assets and the future Step 08 rebuild.
- Use EvalHub when the demo needs standardized, multi-tenant evaluation job
  orchestration, benchmark collections, provider management, result tracking,
  MLflow integration, or OCI result export.
- Use LM-Eval when the demo needs a direct `LMEvalJob` benchmark workflow or
  dashboard-driven model evaluation.
- Use automated risk assessment when the demo needs adversarial safety testing
  with Garak, generated prompts, judge models, and risk reports.
- Use guardrails as runtime safety controls and evaluation as measurement.
  Do not treat the presence of guardrails as evaluation evidence by itself.
- Keep tenant namespace, ServiceAccount, and model endpoint authorization
  explicit. Do not disable EvalHub authentication for shared environments.
- Store model API keys, S3 credentials, OCI credentials, and service account
  tokens in Kubernetes Secrets. Never commit secret values.
- Enable online access and remote code execution for `LMEvalJob` only when the
  evaluation task requires it and the README/runbook records the risk.
- For disconnected clusters, pre-download translation models for risk
  assessment or disable the translation attack strategy.
- Use MLflow and OCI export only after storage, credentials, and retention
  ownership are documented.
- Treat custom providers, adapters, collections, Unitxt cards, and harm
  categories as code artifacts requiring source review and validation.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - EvalHub deployment or configuration
   - EvalHub job, provider, benchmark, collection, adapter, tenant, or RBAC
     workflow
   - LM-Eval `LMEvalJob` or dashboard evaluation workflow
   - LM-Eval custom Unitxt, PVC, S3, KServe, or LLM-as-a-judge scenario
   - automated risk assessment through EvalHub or KFP SDK
   - disconnected risk-assessment preparation
   - MLflow tracking or OCI result export handoff
4. Use `examples/evaluation-patterns.md` for focused review patterns.
5. For live cluster work, follow the OpenShift safety guard in `AGENTS.md`.
6. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/evaluation-patterns.md`
