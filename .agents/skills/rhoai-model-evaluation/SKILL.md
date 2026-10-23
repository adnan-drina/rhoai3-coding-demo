---
name: rhoai-model-evaluation
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when deciding what "good enough" means for a coding model in this repo:
  the evaluation-driven development criteria (versioned `agentic-coding-*`
  collections and their gates), adding or changing a criterion as a new `-vN`
  collection, the qualification verdict (QUALIFIED or NOT QUALIFIED against
  fixed gates, recorded on the model registry version), onboarding a candidate
  model such as `qwen3-8-27b-int4`, or reading and recording qualification
  results. Do NOT
  use for running and debugging EvalHub jobs, providers and access (use
  rhoai-evaluation), pipeline code (use rhoai-kfp-pipeline-authoring), the
  pipeline server and runs (use rhoai-ai-pipelines), or MLflow (use
  rhoai-mlflow).
---

# Model Evaluation (qualification design)

Repo-specific skill: how this demo decides whether a model qualifies for the
coding tools. Running the jobs is `rhoai-evaluation`. Detailed record:
`stages/050-model-evaluation/edd/README.md`,
`gitops/stages/050-model-evaluation/050-model-qualification/README.md`,
`stages/050-model-evaluation/README.md` ("Model qualification pipeline").
The legacy RAG judge, LMEvalJob templates and `backup/` scripts of the old
skill are not in this repo and are not used (LM-Eval is deprecated in 3.5).

## When to use

- Proposing a new benchmark, gate or threshold.
- Onboarding a candidate model.
- Explaining a NOT QUALIFIED verdict, or why a dimension is its own evaluation.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Criteria are defined before models are compared: versioned EvalHub collections for capability (LiveCodeBench alone; MBPP + HumanEval), latency and throughput, and the `garak-kfp` catalog gates for security (`avid_security`) and risk assessment (`intents`) | `gitops/stages/050-model-evaluation/050-evaluation-content/edd/`, `stages/050-model-evaluation/edd/README.md` | [Add a collection by ConfigMap][collcm], [Automated risk assessment][risk] |
| Security and risk assessment are `garak-kfp` benchmark jobs, not collections: `kfp_config.model_url` is the candidate's own URL, which a collection cannot carry; `intents` needs abliterated SDG and judge models (a safety-aligned model sanitised every harmful intent) | `stages/050-model-evaluation/qualification/pipeline.py`, `gitops/stages/050-model-evaluation/050-model-qualification/risk-assessment-gemma-2-9b-abliterated.yaml` | [Automated risk assessment][risk] |
| One dimension per collection, because a job score is one weighted average against one threshold and the metrics do not share scale or direction | `stages/050-model-evaluation/edd/README.md` | [Create a custom collection][custom] |
| A changed criterion is a new `-vN` collection, never an in-place edit, so each MLflow run stays tied to the criteria that judged it; old versions stay registered | `gitops/stages/050-model-evaluation/050-evaluation-content/edd/` | [MLflow experiment tracking][mlflow] |
| One candidate per pipeline run, judged on fixed gates only (no production baseline, decision 2026-10-23); the report reads only this run's jobs (tag `run=<pipeline run id>`); QUALIFIED needs every evaluation run and passed plus capability 3:2:1 at least 0.50 | `stages/050-model-evaluation/qualification/pipeline.py` | not product guidance |
| The verdict and each benchmark's result, evaluation page, MLflow run and pipeline run are recorded on the model registry version (`model_version_id` run parameter); `record.sh` does the same for a manual job | `stages/050-model-evaluation/qualification/pipeline.py`, `stages/050-model-evaluation/evaluation/record.sh` | not product guidance |
| A candidate is a project `InferenceService` with the same revision and serving arguments as production, so a pass carries over on promotion; it is stopped in Git between runs | `gitops/stages/050-model-evaluation/050-model-qualification/candidate-qwen3-8-27b-int4.yaml` | [Compare evaluation runs][compare] |
| CI gating template uses the EvalHub CLI with a full job body | `stages/050-model-evaluation/edd/agentic-coding-python-tasks.ci.yaml` | [Install the SDK and CLI][cli] |

## Procedure

1. New or changed criterion: add `agentic-coding-<dimension>-v<N+1>.yaml` under
   `gitops/stages/050-model-evaluation/050-evaluation-content/edd/`, list it in the
   EvalHub CR (`rhoai-evaluation`), update the table in
   `stages/050-model-evaluation/edd/README.md`, and add a pipeline step only
   through `rhoai-kfp-pipeline-authoring` (new PipelineVersion).
2. Deploy and validate Stage 050 at one SHA:

   ```bash
   ./stages/050-model-evaluation/deploy.sh
   ./stages/050-model-evaluation/validate.sh
   ```

3. Qualify: start a pipeline run with `model_name`, `model_version_id` and
   MLflow experiment `models-onboarding`
   (`docs/OPERATIONS.md#stage-050-model-qualification-pipeline-2026-10-12`);
   the candidate and `gemma-2-9b-abliterated` on the L40S queue need two GPUs
   (`GPU_POOL=l40s stages/020-gpu-infrastructure-private-ai/deploy.sh --gpus 2`).
4. The last step records the verdict on the model version (dashboard model
   version **Properties**); a promotion is a Stage 040 change, not an
   evaluation change.

## Pitfalls

- EvalHub runs a collection's benchmarks in parallel: never mix a saturation
  benchmark with a single-session latency benchmark in one collection.
- EvalHub matches a primary metric by exact key; a wrong metric key yields
  no pass/fail (the reason LiveCodeBench needed `-v2`).
- A Garak result without per-probe `<probe>_asr` metrics is an empty scan
  (job without the model auth Secret), not a pass: the report and `record.sh`
  refuse it (TROUBLESHOOTING).
- `intents` must not set `sdg_max_tokens` on 3.5.2: the provider rebuilds the
  SDG block without its model and the step fails.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Overview | [Evaluation of AI systems][overview], [Built-in collections][builtin] |
| Collections | [Create a custom collection][custom], [Add a collection by ConfigMap][collcm] |
| Results | [MLflow experiment tracking][mlflow], [Compare evaluation runs][compare], [Evaluation cards][cards] |
| Agents and EDD | [MCP `edd_workflow` prompt][edd], [CLI][cli] |
| Safety scans | [Automated risk assessment][risk] |

## Related skills

`rhoai-evaluation`, `rhoai-kfp-pipeline-authoring`, `rhoai-ai-pipelines`,
`rhoai-mlflow`, `rhoai-model-registry-workflows`, `run-guidellm-load-test`.

[overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#overview-evaluating-ai-systems_evaluate
[builtin]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-built-in-collections_evaluate
[custom]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-create-a-custom-collection_evaluate
[collcm]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-add-a-collection-configmap_evaluate
[mlflow]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-configure-mlflow-experiment-tracking_evaluate
[compare]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-evaluation-run-comparison_evaluate
[cards]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-evalcard-overview_evaluate
[edd]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#edd_workflow_prompt
[cli]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#evalhub-install-the-evalhub-sdk-and-cli_evaluate
[risk]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/evaluating_ai_systems/index#automated-risk-assessment-overview_evaluate
