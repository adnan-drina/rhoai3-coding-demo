# Source Capture

## Official Source

- Product: Red Hat OpenShift AI Self-Managed
- Baseline: use the active version in `docs/PLATFORM_BASELINE.md`
- Documentation category: Administer
- Guide: Managing model registries
- URL:
  https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/managing_model_registries/index
- Retrieved: 2026-06-10

## Sections Used

- Preface
- Chapter 1. Overview of the model catalog and model registries
- 1.1. Model catalog
- 1.2. Model registry
- Chapter 2. Enabling the model registry component
- Chapter 3. Creating a model registry
- Chapter 4. Editing a model registry
- Chapter 5. Managing model registry permissions
- Chapter 6. Deleting a model registry

## Related Official Sources

- `docs/PLATFORM_BASELINE.md` for the active RHOAI documentation version.
- Manage and govern model catalog sources for catalog source governance.
- Working with model registries for data scientist and AI engineer workflows
  such as registering, versioning, deploying, archiving, and restoring models.
- Working with the model catalog for model discovery and evaluation.
- OpenShift AI certificate documentation for trusted CA bundle behavior.
- OpenShift RBAC documentation for role binding and group behavior.

## Source Boundaries

- This source defines administrator workflows for provisioning registries and
  managing access.
- It does not define the end-user model version workflow in the Registry tab.
- It does not define model serving runtime behavior after a model is registered.
- It documents dashboard workflows for creating and editing registries; direct
  GitOps manifests for registry instances require separate schema verification.
- Deleting a model registry does not remove connected databases.
