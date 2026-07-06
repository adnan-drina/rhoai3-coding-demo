# Validation Checklist

Use this checklist before accepting TrustyAI monitoring README content, GitOps
manifests, examples, runbooks, notebooks, or scripts.

## Source Alignment

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official Monitoring your AI systems guide is recorded when TrustyAI
  monitoring, bias, or drift behavior is introduced.
- OVMS-only support is stated when presenting TrustyAI monitoring.
- vLLM, Nemotron, and general LLM safety claims are not routed through this
  skill unless active Red Hat docs confirm support.
- OpenShift AI observability stack behavior is checked with
  `rhoai-observability`.
- Deployed model operational metrics are checked with
  `rhoai-model-management-monitoring`.
- Model-serving platform behavior is checked with
  `rhoai-model-serving-platform`.
- Evaluation and risk-assessment behavior is checked with `rhoai-evaluation`.
- Runtime guardrails behavior is checked with `rhoai-guardrails-safety`.
- API support posture is checked with `rhoai-api-tiers`.

## TrustyAI Service Review

- `DataScienceCluster.spec.components.trustyai.managementState` is `Managed`.
- `trustyai-service-operator-controller-manager` is running in
  `redhat-ods-applications`.
- Exactly one `TrustyAIService` exists in the monitored project namespace.
- The monitored namespace contains only supported model deployments for this
  workflow.
- `TrustyAIService` API version and fields are verified against official docs
  or active CRD schema.
- Storage type is intentionally selected:
  - `DATABASE` for production-shaped narratives
  - `PVC` for development, testing, or small demo flows
- Database credentials and TLS keys are stored in Secrets.
- No database password, TLS key, token, or training data with sensitive values
  is committed.
- Database version and operator caveats are reviewed.
- PVC-to-database migration annotation is used only for migration, not for
  fresh installs.

## KServe And Data Capture Review

- Model-serving monitoring handoff is configured before expecting TrustyAI
  model observations.
- KServe RawDeployment logger ConfigMap changes are reviewed with the
  model-serving skill.
- CA bundle ConfigMap name and `caCertFile` match the KServe logger config.
- The model `InferenceService` shows logger mode `all` and a TrustyAI service
  URL.
- Training/reference data is uploaded before bias or drift metrics are
  configured.
- `/info` confirms model schema, uploaded data, and observed records.
- Field mappings are applied through `/info/names` when dashboard or metric
  configuration needs meaningful names.
- `trustyai_model_observations_total` reports observed inferences.

## Bias Metric Review

- The protected attribute, privileged group, unprivileged group, model output,
  favorable outcome, threshold, and batch size are meaningful for the scenario.
- Bias metric type is documented.
- Statistical Parity Difference and Disparate Impact Ratio interpretation is
  not generalized beyond the chosen threshold and data window.
- Existing metrics are duplicated rather than edited when changes are needed.
- Deleting a bias metric is intentional and documented because dashboard
  deletion cannot be undone.
- CLI delete requests include the correct periodic task request ID.

## Drift Metric Review

- Reference training data and `referenceTag` are known.
- Drift metric type is selected for the expected data distribution.
- MeanShift is used only when normal-distribution assumptions are acceptable.
- For unknown or non-normal distributions, a different drift metric is chosen
  or the limitation is documented.
- `trustyai_*` metrics appear in OpenShift Observe after metric creation.
- Deleting a drift metric is intentional and request IDs are verified first.

## Optional Read-Only Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get datasciencecluster default-dsc -o yaml
oc get deployment trustyai-service-operator-controller-manager -n redhat-ods-applications
oc get trustyai -A
oc get trustyaiservice -A
oc get route trustyai-service -n <project>
oc describe inferenceservice <model> -n <project>
```

Schema checks:

```bash
oc explain datasciencecluster.spec.components.trustyai
oc explain trustyaiservice.spec
oc explain inferenceservice.spec.predictor
```

TrustyAI endpoint checks:

```bash
TRUSTY_ROUTE=https://$(oc get route/trustyai-service -n <project> --template='{{.spec.host}}')
TOKEN=$(oc whoami -t)
curl -sk -H "Authorization: Bearer ${TOKEN}" "${TRUSTY_ROUTE}/info"
curl -sk -H "Authorization: Bearer ${TOKEN}" "${TRUSTY_ROUTE}/q/openapi"
curl -sk -H "Authorization: Bearer ${TOKEN}" "${TRUSTY_ROUTE}/metrics/all/requests"
```

OpenShift metrics checks:

```text
trustyai_model_observations_total
trustyai_*
trustyai_meanshift
```

## Fail Conditions

Stop and correct the work if any of these are true:

- TrustyAI monitoring is promised for non-OVMS models without active official
  Red Hat support evidence.
- A README claims fairness or no drift without metric configuration, data
  window, threshold, and limitation notes.
- Multiple `TrustyAIService` instances exist in one project.
- Secret values, TLS keys, tokens, or sensitive training data are committed.
- Metric configuration uses unexplained protected attributes, thresholds, or
  reference data.
- KServe RawDeployment logging and CA bundle config are missing but TrustyAI
  observations are expected.
- A live cluster command bypasses the OpenShift safety guard.
