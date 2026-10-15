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
  collection, the qualification leaderboard's PROMOTE or HOLD rule against the
  production baseline, onboarding a candidate model such as
  `qwen3-8-27b-int4`, or reading and recording qualification results. Do NOT
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
- Onboarding or comparing a candidate model against production.
- Explaining a HOLD, or why a dimension is its own collection.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Criteria are defined before models are compared, as versioned EvalHub collections: capability (LiveCodeBench alone; MBPP + HumanEval), security (Garak quick per change, full nightly or pre-promotion), latency, throughput | `gitops/stages/050-model-evaluation/050-evaluation-content/edd/` | [Add a collection by ConfigMap][collcm] |
| One dimension per collection, because a job score is one weighted average against one threshold and the metrics do not share scale or direction | `stages/050-model-evaluation/edd/README.md` | [Create a custom collection][custom] |
| A changed criterion is a new `-vN` collection, never an in-place edit, so each MLflow run stays tied to the criteria that judged it; old versions stay registered | `gitops/stages/050-model-evaluation/050-evaluation-content/edd/` | [MLflow experiment tracking][mlflow] |
| One model per pipeline run; the last step ranks every qualified model from EvalHub history (newest finished job per model and collection) and recommends PROMOTE or HOLD; capability combines 3:2:1 with gate 0.50 | `stages/050-model-evaluation/qualification/pipeline.py` | not product guidance |
| Production records the baseline once; candidates are compared with that record and never re-run it | `stages/050-model-evaluation/qualification/pipeline.py` | not product guidance |
| A candidate is a project `InferenceService` with the same revision and serving arguments as production, so a pass carries over on promotion; it is stopped in Git between runs | `gitops/stages/050-model-evaluation/050-model-qualification/candidate-qwen3-8-27b-int4.yaml` | [Compare evaluation runs][compare] |
| CI gating template uses the EvalHub CLI with a full job body | `stages/050-model-evaluation/edd/agentic-coding-capability.ci.yaml` | [Install the SDK and CLI][cli] |

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

3. Qualify: start a pipeline run with `model_name` and MLflow experiment
   `agentic-coding-qualification` (`docs/OPERATIONS.md#stage-050-model-qualification-pipeline-2026-10-12`);
   a candidate on the L40S queue needs that GPU pool up (`resume-gpu-demo`).
4. Record results on the model's registry version with
   `stages/050-model-evaluation/record-evaluation.sh` and in
   `docs/OPERATIONS.md`; a promotion is a Stage 040 change, not an evaluation
   change.

## Pitfalls

- The baseline through MaaS includes gateway latency; read latency and
  throughput gates with the MaaS path in mind (`docs/OPERATIONS.md`, Qwen 3.6
  results).
- EvalHub runs a collection's benchmarks in parallel: never mix a saturation
  benchmark with a single-session latency benchmark in one collection.
- The leaderboard matches a primary metric by exact key; a wrong metric key
  yields no pass/fail (the reason LiveCodeBench needed `-v2`).
- `security-full-v2` is skipped by default (`skip_security_full`) because it
  takes about two hours.
- Deleting EvalHub jobs changes the leaderboard, which reads only remaining
  jobs.

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
