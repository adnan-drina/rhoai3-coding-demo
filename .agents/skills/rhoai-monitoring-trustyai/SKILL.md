---
name: rhoai-monitoring-trustyai
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, installing, configuring, or operating Red
  Hat OpenShift AI TrustyAI model monitoring from the official Monitoring your
  AI systems guide: TrustyAI component enablement, TrustyAIService custom
  resources, per-project TrustyAI service installation, PVC or database
  storage, MariaDB/MySQL database credentials, KServe RawDeployment logging
  integration, OAuth proxy authentication, training data upload, model
  registration checks, field name mapping, bias metrics, Statistical Parity
  Difference, Disparate Impact Ratio, drift metrics, MeanShift, FourierMMD,
  KSTest, ApproxKSTest, OpenShift dashboard metric views, TrustyAI REST
  endpoints, metric request deletion, and TrustyAI Prometheus metrics. Do NOT
  use for OpenShift AI observability stack setup (use rhoai-observability),
  deployed model runtime dashboards, KServe timeouts, KEDA/CMA, or NIM metrics
  (use rhoai-model-management-monitoring), LLM evaluation or automated risk
  assessment (use rhoai-evaluation), runtime guardrails (use
  rhoai-guardrails-safety), model-serving platform configuration beyond the
  TrustyAI logger handoff (use rhoai-model-serving-platform), or live cluster
  changes without the OpenShift safety guard.
---

# RHOAI TrustyAI Monitoring

Use this skill for official Red Hat OpenShift AI TrustyAI monitoring workflows
on the active product baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior details.
Official Red Hat documentation is product authority. This skill adapts the
official Monitoring your AI systems guide to this repo's GitOps and README
review model.

## Scope

This skill covers:

- TrustyAI monitoring for data drift and bias
- administrator enablement of the `trustyai` `DataScienceCluster` component
- `TrustyAIService` custom resources in model project namespaces
- one TrustyAI service instance per project
- PVC-backed TrustyAI storage
- database-backed TrustyAI storage with MariaDB/MySQL credentials
- database migration from PVC to database storage
- KServe RawDeployment logger integration and CA bundle handling
- TrustyAI OAuth proxy authentication with user or service account tokens
- training data upload through `/data/upload`
- TrustyAI model registration checks through `InferenceService` logger fields
- field name mapping through `/info/names`
- observation verification with `trustyai_model_observations_total`
- bias metric creation, viewing, duplication, and deletion
- Statistical Parity Difference and Disparate Impact Ratio interpretation
- drift metric creation, viewing, and deletion
- MeanShift, FourierMMD, KSTest, and ApproxKSTest interpretation
- TrustyAI REST endpoint discovery through `/q/openapi`
- OpenShift Observe metrics for `trustyai_*` metrics

Use other skills for adjacent work:

- `rhoai-observability` for OpenShift AI observability stack installation,
  OpenTelemetry Collector, Prometheus, Alertmanager, Tempo, dashboard menu,
  and user workload scrape policy
- `rhoai-model-management-monitoring` for deployed model metrics, KServe
  operational metrics, KEDA/CMA autoscaling, Grafana dashboards, and NIM
  metrics
- `rhoai-model-serving-platform` for KServe, vLLM, OVMS, `ServingRuntime`, and
  `InferenceService` platform configuration outside TrustyAI logger handoff
- `rhoai-evaluation` for EvalHub, LM-Eval, automated risk assessment, Garak,
  judge models, and measured LLM safety evaluation
- `rhoai-guardrails-safety` for NeMo Guardrails, FMS Guardrails, detector
  services, and runtime safety controls
- `rhoai-project-workflows` for project lifecycle and project access
- `rhoai-api-tiers` for TrustyAI API support posture and CRD durability

## Demo Policy

For this repo:

- Treat this skill as the product source for TrustyAI bias and data-drift
  monitoring.
- Do not use TrustyAI monitoring from this guide for the active vLLM/Nemotron
  private LLM path unless the active Red Hat documentation confirms support.
  The guide states that TrustyAI only supports models deployed with OpenVINO
  Model Server and warns that non-OVMS models are not supported.
- Use `rhoai-evaluation` for LLM evaluation and risk assessment claims.
- Use `rhoai-guardrails-safety` for runtime LLM safety controls.
- Install only one `TrustyAIService` instance in a project.
- Prefer database-backed storage for production-shaped narratives because the
  guide recommends it for scalability, performance, and data management.
- Keep database usernames, passwords, TLS keys, and service account tokens in
  Kubernetes Secrets. Never commit secret values.
- Use PVC-backed storage only for development, testing, or small demo flows,
  and label it accordingly.
- Create bias metrics only when the protected attribute, privileged group,
  unprivileged group, favorable outcome, threshold, and batch size are
  meaningful for the scenario.
- Create drift metrics only after training/reference data is uploaded and the
  reference tag is known.
- Do not claim fairness, reliability, or absence of drift from one metric
  alone. Record metric choice, threshold, data window, and limitation.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - TrustyAI component enablement
   - TrustyAI project service installation
   - storage and database configuration
   - KServe RawDeployment logger integration
   - training data upload and field mapping
   - bias metric configuration
   - drift metric configuration
   - dashboard or OpenShift Observe metric review
   - metric deletion or cleanup
4. Use `examples/trustyai-monitoring-patterns.md` for compact review patterns.
5. For live cluster work, follow the OpenShift safety guard in `AGENTS.md`.
6. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/trustyai-monitoring-patterns.md`
