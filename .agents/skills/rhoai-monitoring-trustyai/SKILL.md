---
name: rhoai-monitoring-trustyai
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when someone proposes TrustyAI bias or data-drift monitoring
  (TrustyAIService, SPD/DIR, MeanShift, FourierMMD, KSTest) for this demo,
  when reviewing what the `trustyai` DataScienceCluster component enabled by
  the Stage 050 hook (gitops/stages/050-model-evaluation/050-mlflow/dsc-enablement/)
  does here, or when a TrustyAIService appears next to the vLLM models in
  `internal-models` or `evaluated-models`. Do NOT use for EvalHub evaluations,
  which the same component runs (use rhoai-evaluation), model serving metrics
  and dashboards (use rhoai-model-management-monitoring), or runtime safety
  (use rhoai-guardrails-safety).
---

# RHOAI TrustyAI Monitoring

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/050-model-evaluation/050-mlflow/README.md` (component enablement).

## When to use

- A request to add fairness or drift monitoring to a model of this demo.
- Reviewing why `trustyai` is `Managed` and what that allows.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| `trustyai` is set `Managed` by the `enable-model-evaluation` Sync hook (delegated DSC field) because EvalHub runs on the TrustyAI operator; the hook waits for `trustyais/default-trustyai` `Ready` | `gitops/stages/050-model-evaluation/050-mlflow/dsc-enablement/enable-job.yaml` | [Enable the TrustyAI component][enable] |
| No `TrustyAIService`, no bias or drift metric in Git: the served models are vLLM (`LLMInferenceService` in `internal-models`, candidate `InferenceService` in `evaluated-models`), and TrustyAI monitoring supports only OpenVINO Model Server models | `gitops/stages/040-governed-models-as-a-service/040-local-models/`, `gitops/stages/050-model-evaluation/050-model-qualification/` | [Install the TrustyAI service][install] |
| Model quality evidence comes from EvalHub benchmarks recorded in MLflow and the registry, not TrustyAI metrics | `gitops/stages/050-model-evaluation/050-evalhub/` | see `rhoai-evaluation` |

## Procedure

1. Before adding monitoring, confirm the model is deployed with OVMS and
   choose a project without vLLM models ([Install the TrustyAI
   service][install]). None of this demo's models qualifies today; record the
   decision in the Stage 050 README first.
2. If adopted: one `TrustyAIService` per project, database storage rather than
   PVC ([database setup][db]), credentials in Secrets created outside Git, and
   the KServe RawDeployment integration ([KServe integration][kserve]).
3. Check the component read-only, after the OpenShift safety guard in
   `AGENTS.md`:

   ```bash
   oc get datasciencecluster default-dsc -o jsonpath='{.spec.components.trustyai.managementState}{"\n"}'
   oc get trustyai default-trustyai -o jsonpath='{range .status.conditions[*]}{.type}={.status} {end}{"\n"}'
   oc get trustyaiservice -A
   ./stages/050-model-evaluation/validate-ai-services.sh
   ```

## Pitfalls

- Non-OVMS models in the same namespace as a TrustyAI service are unsupported
  and can cause errors ([Install the TrustyAI service][install]); do not put a
  `TrustyAIService` in `internal-models` or `evaluated-models`.
- Database storage: MySQL is not supported, and TLS does not work with
  MariaDB operator 0.29 or later ([database setup][db]).
- Setting `trustyai` to `Removed` also removes EvalHub; the Stage 050 hook and
  `validate-ai-services.sh` expect it `Managed`.
- One metric is not a fairness or drift verdict: record the metric, threshold,
  data window and limitation with any claim ([bias metrics][usebias],
  [drift metrics][usedrift]).

## Official documentation (RHOAI 3.5)

| Topic | Section |
|---|---|
| Overview | [AI system monitoring][overview] |
| Configure | [Configure TrustyAI][configure], [Serving platform monitoring][servingmon], [Enable][enable], [Database][db], [Install service][install], [CLI install][installcli], [KServe RawDeployment][kserve] |
| Project setup | [Set up TrustyAI for a project][setup], [Authenticate][auth], [Upload training data][upload], [Label data fields][labels] |
| Bias | [Monitor model bias][bias], [Create a bias metric][createbias], [View][viewbias], [Use][usebias] |
| Drift | [Monitor data drift][drift], [Create a drift metric][createdrift], [View][viewdrift], [Use][usedrift] |

## Related skills

`rhoai-evaluation`, `rhoai-model-management-monitoring`,
`rhoai-observability`, `rhoai-guardrails-safety`,
`rhoai-dsci-dsc-configuration`.

[overview]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/monitoring_your_ai_systems/index#overview-of-monitoring-your-ai-systems_monitor
[configure]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/monitoring_your_ai_systems/index#configuring-trustyai_monitor
[servingmon]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/monitoring_your_ai_systems/index#configuring-monitoring-for-your-model-serving-platform_monitor
[enable]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/monitoring_your_ai_systems/index#enabling-trustyai-component_monitor
[db]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/monitoring_your_ai_systems/index#configuring-trustyai-with-a-database_monitor
[install]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/monitoring_your_ai_systems/index#installing-trustyai-service_monitor
[installcli]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/monitoring_your_ai_systems/index#installing-trustyai-service-using-cli_monitor
[kserve]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/monitoring_your_ai_systems/index#enabling-trustyai-kserve-integration_monitor
[setup]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/monitoring_your_ai_systems/index#setting-up-trustyai-for-your-project_monitor
[auth]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/monitoring_your_ai_systems/index#authenticating-trustyai-service_monitor
[upload]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/monitoring_your_ai_systems/index#uploading-training-data-to-trustyai_monitor
[labels]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/monitoring_your_ai_systems/index#labeling-data-fields_monitor
[bias]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/monitoring_your_ai_systems/index#monitoring-model-bias_bias-monitoring
[createbias]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/monitoring_your_ai_systems/index#creating-a-bias-metric_bias-monitoring
[viewbias]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/monitoring_your_ai_systems/index#viewing-bias-metrics_bias-monitoring
[usebias]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/monitoring_your_ai_systems/index#using-bias-metrics_bias-monitoring
[drift]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/monitoring_your_ai_systems/index#monitoring-data-drift_drift-monitoring
[createdrift]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/monitoring_your_ai_systems/index#creating-a-drift-metric_drift-monitoring
[viewdrift]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/monitoring_your_ai_systems/index#viewing-drift-metrics_drift-monitoring
[usedrift]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/monitoring_your_ai_systems/index#using-drift-metrics_drift-monitoring
