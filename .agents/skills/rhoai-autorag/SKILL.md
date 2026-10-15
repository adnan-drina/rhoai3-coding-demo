---
name: rhoai-autorag
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when someone asks to show, enable or review OpenShift AI AutoRAG
  (Technology Preview RAG optimization runs, test data, leaderboard, generated
  RAG pattern) in this repo, where the dashboard flag `autorag` is set to
  false by Stage 010 and AutoRAG is not deployed. Do NOT use for OGX servers
  and vector stores (use rhoai-llama-stack), RAG application design (use
  rhoai-enterprise-rag), pipeline servers (use rhoai-ai-pipelines), or EvalHub
  evaluations (use rhoai-evaluation).
---

# RHOAI AutoRAG

Thin skill. **Not deployed in this demo.** Product behavior lives in the linked
OpenShift AI 3.5 sections; this file records the repo state and what enabling
it would touch.

## Repo state

| Fact | Where in Git |
|---|---|
| Dashboard flag `autorag: false` (the documented default), written down so `validate.sh` intent is visible | `gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/odhdashboardconfig.yaml` |
| `/spec/dashboardConfig/autorag` is not in the `010-rhoai-platform` `ignoreDifferences`, so Argo CD restores `false` if it is changed live | `gitops/applications/010-rhoai-platform.yaml` |
| Stage 010 README lists AutoRAG and AutoML as disabled | `stages/010-openshift-ai-platform-foundation/README.md` |
| Building blocks a run could use do exist: OGX (Stage 040), AI pipelines (DSC `aipipelines` Managed by Stage 050), MLflow (Stage 050) | `gitops/stages/040-governed-models-as-a-service/maas-platform/jobs/enable-maas-job.yaml`, `gitops/stages/050-model-evaluation/mlflow/dsc-enablement/` |

No AutoRAG test data, run, vector database for AutoRAG, or notebook is in Git.

## When it would apply

- A workshop story that compares RAG patterns over a document corpus and hands
  the chosen pattern to a developer.
- Label it Technology Preview in every README and talk track
  ([limitations][tplimits]).

## If enabled

1. Decide the owning stage and record the decision in that stage README (Why /
   What / How, alignment table).
2. Delegate `/spec/dashboardConfig/autorag` in the `010-rhoai-platform`
   Application and set it from that stage's enablement Sync-hook Job, as Stage
   040 does for `guardrails` (`gitops/stages/040-governed-models-as-a-service/maas-platform/jobs/enable-maas-job.yaml`).
   Never edit the live `OdhDashboardConfig` by hand.
3. Read the prerequisites in [Create an optimization run][createrun] and
   [Configuration parameters][params] before choosing models; route the
   foundation and embedding models through MaaS.
4. Add a validate step to the stage's `validate.sh`; keep test data in Git
   without customer content.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Overview, workflow, limitations | [AutoRAG overview][overview], [Workflow][workflow], [Technology Preview limitations][tplimits] |
| Test data | [Prepare test data][testdata] |
| Runs and results | [Create a run][createrun], [Evaluate results][evaluate], [Run the RAG pattern][runpattern] |
| Metrics and parameters | [Evaluation metrics][metrics], [Configuration parameters][params], [Recommended embedding models][embed], [Recommended foundation models][foundation] |

## Related skills

`rhoai-llama-stack`, `rhoai-enterprise-rag`, `rhoai-ai-pipelines`,
`rhoai-gen-ai-playground`, `rhoai-dashboard-customization`.

[overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_autorag/index#autorag-overview_autorag
[workflow]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_autorag/index#autorag_workflow
[tplimits]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_autorag/index#technology_preview_limitations
[testdata]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_autorag/index#preparing-test-data-for-autorag_autorag
[createrun]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_autorag/index#creating-autorag-optimization-run_autorag
[evaluate]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_autorag/index#evaluating-autorag-results_autorag
[runpattern]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_autorag/index#running-rag-pattern_autorag
[metrics]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_autorag/index#autorag-evaluation-metrics_autorag
[params]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_autorag/index#autorag-configuration-parameters_autorag
[embed]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_autorag/index#recommended_embedding_models
[foundation]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_autorag/index#recommended_foundation_models
