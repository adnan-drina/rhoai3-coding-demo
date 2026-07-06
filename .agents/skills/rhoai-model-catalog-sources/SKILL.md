---
name: rhoai-model-catalog-sources
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or administering Red Hat OpenShift AI model
  catalog source governance: viewing catalog sources in Model catalog settings,
  adding Hugging Face repository or YAML-file sources, enabling or disabling
  sources, previewing include and exclude model visibility patterns, managing
  or deleting sources, configuring the model-catalog-sources ConfigMap in
  rhoai-model-registries, default source boundaries, Hugging Face
  public/non-gated and connected-environment limitations, YAML catalog labels,
  and verification in AI hub -> Catalog. Do NOT use for model registry
  lifecycle, model deployment, dashboard feature visibility, or live cluster
  changes without the OpenShift safety guard.
---

# RHOAI Model Catalog Sources

Use this skill to manage and govern OpenShift AI model catalog sources for the
active product baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is product authority. This skill adapts the
official model catalog source governance guide to this repo's GitOps review
model.

## Scope

This skill covers:

- dashboard governance from Settings -> Model resources and operations -> Model
  catalog settings
- source review for the default Red Hat AI, Red Hat AI validated, and Other
  catalog sources
- adding catalog sources from Hugging Face repositories or YAML files
- enabling and disabling catalog sources without deleting source configuration
- include and exclude model visibility patterns and Preview validation
- Hugging Face organization slug handling and public, non-gated source limits
- YAML catalog source metadata requirements and labels
- deleting non-default catalog sources
- configuring custom YAML catalog sources through the `model-catalog-sources`
  ConfigMap in the `rhoai-model-registries` namespace
- verification in AI hub -> Catalog

Use other skills for adjacent work:

- `rhoai-model-catalog-workflows` for data scientist and AI engineer catalog
  discovery, evaluation, registration, and deployment workflows
- `rhoai-dashboard-customization` for the `disableModelCatalog` dashboard flag
  and broader `OdhDashboardConfig` feature visibility
- `rhoai-model-serving-platform` for deploying catalog-selected models on
  KServe, vLLM, NIM, or related serving runtimes
- `rhoai-model-management-monitoring` for operating already deployed models
- `rhoai-model-registry` for model registry provisioning, database selection,
  permissions, and administrator lifecycle
- `rhoai-model-registry-workflows` for registering catalog-selected models into
  registries and operating model versions

## Demo Policy

For this repo:

- Treat the model catalog as a governed discovery surface, not a trust stamp.
- Prefer Red Hat-provided catalog sources for default demo flows.
- Require explicit compliance and provenance review before exposing external
  Hugging Face or custom YAML catalog sources to users.
- Keep new sources disabled until source metadata, visibility patterns, and
  Preview output are reviewed.
- Use include patterns first to narrow the source and exclude patterns second
  to remove blocked models.
- Do not use Hugging Face catalog sources for disconnected demo environments.
- Do not model gated or private Hugging Face repositories through this feature.
- Manage long-lived custom YAML catalog sources through GitOps once active
  GitOps implementation exists.
- Keep source-controlled YAML catalog examples minimal and traceable to
  official docs or approved demo policy.
- Do not delete default catalog sources.
- Do not claim custom catalog source support on `s390x`.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Decide whether the task is dashboard-based source governance or
   ConfigMap/GitOps-based custom source configuration.
4. For Hugging Face sources, confirm the organization slug, connected-cluster
   requirement, and public non-gated model boundary.
5. For YAML sources, confirm model definitions include model name, description,
   and deployment information.
6. Apply include and exclude visibility patterns, then use Preview before
   enabling a source.
7. Verify source status in Model catalog settings and model visibility in AI
   hub -> Catalog.
8. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/model-catalog-source-patterns.md`
