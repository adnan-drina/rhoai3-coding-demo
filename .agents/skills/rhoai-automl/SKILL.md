---
name: rhoai-automl
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when someone proposes OpenShift AI AutoML (automated model selection
  for tabular or time-series data): the dashboard `automl` flag, optimization
  runs, the leaderboard, predictions or deploying an AutoML model. Not
  deployed in this demo (`automl: false` in odh-dashboard-config; excluded
  from scope). Do NOT use for AutoRAG (use rhoai-autorag), pipeline servers
  (use rhoai-ai-pipelines), or serving (use rhoai-model-deployment).
---

# RHOAI AutoML

Thin skill: AutoML in OpenShift AI 3.5. **Not deployed in this demo** and
excluded from its scope (`docs/OPERATIONS.md`, `BACKLOG.md`).

## When to use

- A request to show AutoML, or a change to `automl` in the dashboard config.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Dashboard flag `automl: false` (its documented default, written down to make the intent visible) | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/odhdashboardconfig.yaml`, `.../rhoai-platform/README.md` | [Automated model selection with AutoML][overview] |
| AutoML and AutoRAG excluded from the demo's intended scope | `docs/OPERATIONS.md`, `stages/010-openshift-ai-platform-foundation/README.md` | — |
| The only pipeline server is in the admin-only `evaluated-models` project | `gitops/stages/050-model-evaluation/050-model-qualification/pipeline-server.yaml` | see `rhoai-ai-pipelines` |

## If enabled

1. Agree the scope change first: the guide has a Technology Preview
   limitations section ([limitations][tp]); label it that way in demo text.
2. The flag in `odh-dashboard-config` is owned by Stage 010 and not
   delegated; either change it there or delegate it to the owning stage
   (rules in `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/README.md`).
3. Give the target project a pipeline server and an S3 connection
   (`rhoai-ai-pipelines`), and serve the result through the existing model
   serving stack (`rhoai-model-deployment`).
4. Read-only check after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o jsonpath='{.spec.dashboardConfig.automl}{"\n"}'
   ```

## Pitfalls

- Editing the live dashboard config is reverted by Argo CD.
- Read the supported task types and data limits in the guide before
  promising a data set.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Overview | [AutoML][overview], [Workflow][workflow], [Supported task types][tasks], [Technology Preview limitations][tp] |
| Use | [Create a run][create], [Evaluate results][evaluate], [Run predictions][predict], [Deploy a model][deploy] |
| Reference | [Evaluation metrics][metrics], [Configuration parameters][params] |

## Related skills

`rhoai-autorag`, `rhoai-ai-pipelines`, `rhoai-model-deployment`,
`rhoai-dashboard-customization`.

[overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_automl/index#automl-overview_automl
[workflow]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_automl/index#automl-workflow_automl
[tasks]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_automl/index#supported-task-types_automl
[tp]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_automl/index#technology-preview-limitations_automl
[create]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_automl/index#creating-automl-optimization-run_automl
[evaluate]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_automl/index#evaluating-automl-results_automl
[predict]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_automl/index#running-predictions-automl-model_automl
[deploy]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_automl/index#deploying-automl-model_automl
[metrics]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_automl/index#automl-evaluation-metrics_automl
[params]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_automl/index#automl-configuration-parameters_automl
