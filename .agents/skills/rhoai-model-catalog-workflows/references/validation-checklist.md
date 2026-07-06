# Validation Checklist

Use this checklist when reviewing model catalog workflow documentation,
runbooks, notebooks, or demo scripts.

## Source Alignment

- The RHOAI documentation version matches `docs/PLATFORM_BASELINE.md`.
- The official Working with the model catalog source is recorded when the
  workflow is introduced.
- The task is a user catalog workflow, not administrator catalog source
  governance.
- Serving-runtime details are checked against `rhoai-model-serving-platform`.
- Registry-side lifecycle details are checked against
  `rhoai-model-registry-workflows`.

## Discovery

- The dashboard path is AI hub -> Models -> Catalog unless the active dashboard
  shows a changed label.
- The runbook distinguishes Red Hat AI models, Red Hat AI validated models,
  Other models, and administrator-labeled custom categories.
- Search and filters use documented fields: model name, description, provider,
  task, license, language, and tensor type.
- Model card claims preserve provider-supplied intended use, limitations,
  training data, and evaluation results.

## Performance Evaluation

- Performance Insights is used only for validated models.
- Performance filters document scenario, latency metric, percentile, Max RPS,
  and hardware constraints.
- `E2E`, `TTFT`, `TPS`, and `ITL` are interpreted correctly.
- Model performance view is documented as showing validated models only.
- The breadcrumb behavior between catalog and Performance Insights is described
  when filter transfer matters.

## Tensor Variants

- Tensor type is treated as a compression variant of the base model.
- Variant trade-offs are framed as quality, efficiency, hardware, latency, and
  throughput considerations.
- The Tensor type filter is documented as available with or without Model
  performance view.
- The Model variants by tensor type card is expected only for validated models
  with variants.

## Registration

- The user has access to an available model registry.
- Model name, version name, model format, and model format version are recorded.
- The catalog-provided model URI is reviewed and not manually changed in the
  registration workflow.
- Registration from the catalog is not claimed as supported on `s390x`.
- Verification checks the model details Overview tab and the Model registry
  page.

## Deployment

- Model serving prerequisites are complete before deployment.
- The `modelregistry` component is enabled.
- Catalog model location and URI are documented as read-only in the deployment
  wizard.
- Resource name constraints are preserved.
- Catalog models use `default-profile` unless the active docs change.
- Runtime auto-selection or manual runtime selection is reviewed with
  `rhoai-model-serving-platform`.
- Advanced settings are not claimed as supported on `s390x`.
- AI asset endpoint behavior is documented when Gen AI studio playground
  testing is expected.
- Verification checks AI hub -> Deployments, Latest deployments, and the
  registry Deployments tab.

## Fail Conditions

Stop and correct the work if any of these are true:

- A non-validated model is described as having Red Hat validated performance
  data.
- Catalog benchmark data is presented as a substitute for project validation.
- A catalog model card limitation is omitted from user-facing claims.
- Catalog registration is claimed as supported on `s390x`.
- Advanced catalog deployment settings are claimed as supported on `s390x`.
- The global cluster pull secret requirement for catalog ModelCar pulls is
  omitted from deployment notes.
