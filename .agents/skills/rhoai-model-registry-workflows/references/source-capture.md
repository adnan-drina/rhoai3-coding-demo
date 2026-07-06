# Source Capture

## Official Source

- Product: Red Hat OpenShift AI Self-Managed
- Baseline: use the active version in `docs/PLATFORM_BASELINE.md`
- Documentation category: Develop
- Guide: Working with model registries
- Page title: Register, version, and promote models with the model registry
- URL:
  https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_model_registries/index
- Retrieved: 2026-06-10

## Sections Used

- Preface
- Chapter 1. Overview of the model catalog and model registries
- 1.1. Model catalog
- 1.2. Model registry
- Chapter 2. Working with model registries
- 2.1. Registering a model from the dashboard
- 2.2. Registering a model version
- 2.3. Registering and storing a model as an OCI image
- 2.4. Monitoring model transfer jobs
- 2.5. Retrying a failed model transfer job
- 2.6. Deleting a model transfer job
- 2.7. Viewing registered models
- 2.8. Viewing registered model versions
- 2.9. Editing model metadata in a model registry
- 2.10. Editing model version metadata in a model registry
- 2.11. Deploying a model version from a model registry
- 2.12. Editing the deployment properties of a deployed model version from a
  model registry
- 2.13. Deleting a deployed model version from a model registry
- 2.14. Archiving a model
- 2.15. Archiving a model version
- 2.16. Restoring a model
- 2.17. Restoring a model version

## Related Official Sources

- `docs/PLATFORM_BASELINE.md` for the active RHOAI documentation version.
- Managing model registries for administrator provisioning, permissions, and
  database configuration.
- Working with the model catalog for registering a catalog model into a registry.
- Deploying models and configuring the model-serving platform for deployment
  wizard prerequisites and serving runtime behavior.
- Managing and monitoring models for deployed model operations and metrics.

## Source Boundaries

- This source defines data scientist and AI engineer workflows in the registry.
- It assumes an administrator has already provisioned registry access.
- It does not define model registry database configuration or generated RBAC.
- It does not define full serving-runtime configuration after registry handoff.
- It does not define catalog source governance.
