# Validation Checklist

Use this checklist when reviewing model catalog source documentation, dashboard
runbooks, or GitOps manifests.

## Source Alignment

- The RHOAI documentation version matches `docs/PLATFORM_BASELINE.md`.
- The official source URL is recorded in the README, runbook, or skill reference
  that introduces the behavior.
- The task is catalog-source governance, not model registry lifecycle or model
  serving configuration.

## Dashboard Governance

- The documented path is Settings -> Model resources and operations -> Model
  catalog settings.
- Default sources are treated as managed product sources and not deleted.
- New or changed sources are previewed before they are enabled for users.
- Enablement and validation status are checked after changes.
- AI hub -> Catalog is used to confirm user-visible result.

## Hugging Face Sources

- The source uses an organization URL slug, not a display name.
- The source is public and non-gated.
- The environment is connected to Hugging Face.
- The review notes that Red Hat does not validate third-party model security.
- Visibility patterns use model names without the organization prefix.

## YAML Sources

- The source includes model name, description, and deployment information.
- Visibility patterns use the full model name prefix including organization.
- Labels are intentional and match how models should be grouped in AI hub ->
  Catalog.
- Long-lived YAML source content is source-controlled and GitOps-managed once
  active GitOps content exists.
- Custom source support is not claimed for `s390x`.

## ConfigMap Review

- The namespace is `rhoai-model-registries`.
- The ConfigMap name is `model-catalog-sources`.
- `data.sources.yaml` contains a `catalogs` list.
- Each custom YAML source has `name`, `id`, `type: yaml`, and
  `properties.yamlCatalogPath`.
- `enabled` is intentionally set or the default enabled behavior is accepted.
- The referenced catalog YAML file is present when stored in the same ConfigMap.

## Fail Conditions

Stop and correct the work if any of these are true:

- A Hugging Face source requires API keys, secrets, private access, or gated
  model approval.
- A disconnected environment is expected to use a Hugging Face catalog source.
- A source is enabled before source provenance and Preview output are reviewed.
- A default catalog source is marked for deletion.
- A custom source is documented as supported on `s390x`.
- A ConfigMap change is treated as long-lived state without a GitOps path.
