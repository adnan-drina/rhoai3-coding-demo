# Source Capture

## Official Source

- Product: Red Hat OpenShift AI Self-Managed
- Baseline: use the active version in `docs/PLATFORM_BASELINE.md`
- Documentation category: Administer
- Guide: Manage and govern model catalog sources
- URL:
  https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/manage_and_govern_model_catalog_sources/index
- Retrieved: 2026-06-10

## Sections Used

- Preface
- Chapter 1. Manage and govern model catalog sources in the OpenShift AI
  dashboard
- 1.1. View model catalog sources
- 1.2. Enable or disable catalog sources
- 1.3. Configure model visibility settings to allow and disallow models
- 1.4. Limitations for Hugging Face model sources
- Chapter 2. Add a model catalog source
- Chapter 3. Manage a model catalog source
- Chapter 4. Delete a model catalog source
- Chapter 5. Configure model catalog sources in OpenShift

## Related Official Sources

- `docs/PLATFORM_BASELINE.md` for the active RHOAI documentation version.
- Working with the model catalog for user-facing model discovery and selection.
- Managing model registries for registry lifecycle, model versions, and
  registry storage.
- Dashboard customization documentation for the `disableModelCatalog`
  visibility flag.
- Configuring your model-serving platform and deploying models documentation
  for model deployment behavior after a model is discovered.

## Source Boundaries

- This source governs model catalog sources and model visibility in the catalog.
- It does not define model registry lifecycle, model-version governance,
  deployed model monitoring, or serving-runtime configuration.
- Hugging Face catalog sources are connected-environment only and public
  non-gated only.
- External model availability is not a Red Hat validation of third-party model
  security or compliance.
- The OpenShift ConfigMap path is a cluster-administrator workflow; this repo
  should express long-lived ConfigMap changes through GitOps once active
  GitOps content exists.
