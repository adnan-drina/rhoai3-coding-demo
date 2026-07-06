---
name: rhoai-component-resource-customization
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or changing Red Hat OpenShift AI
  Operator-related component Deployment CPU and memory requests or limits in
  redhat-ods-applications; checking deployment names for KServe, Ray, Kueue,
  workbenches, dashboard, model serving, model registry, AI pipelines, and
  Training Operator; preserving custom resource settings by avoiding the
  opendatahub.io/managed annotation; disabling customization by adding
  opendatahub.io/managed: true; and re-enabling customization through the
  documented delete-and-reconcile workflow. Do NOT use for user workload
  quotas, GPU node scaling, Kueue queues, hardware profiles, model-serving
  runtime resources, live resource changes without the OpenShift safety guard,
  or full GitOps ownership of Operator-created Deployments without explicit
  design approval.
---

# RHOAI Component Resource Customization

Use this skill to customize Red Hat OpenShift AI Operator-related component
Deployment resources for the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior details.
Official Red Hat documentation is product authority. This skill adapts the
official component Deployment resource customization workflow to this repo's
GitOps review model.

## Scope

This skill covers:

- CPU and memory requests/limits on OpenShift AI component Deployments in
  `redhat-ods-applications`
- documented component Deployment names
- the `opendatahub.io/managed: true` annotation behavior
- disabling customization and restoring default Operator-managed values
- re-enabling customization through delete-and-reconcile
- safe review of patch-based changes to Operator-related Deployments

This skill does not cover:

- resource quotas, LimitRanges, or cluster autoscaling
- GPU MachineSets or cost-control scaling
- Kueue queue design
- data science project workload resources
- KServe model runtime sizing
- hardware profile sizing
- full lifecycle management of Operator-owned Deployments through ArgoCD

## Persistence Rule

For component resource customizations to persist without being overwritten by
the OpenShift AI Operator, the component Deployment YAML must not contain:

```yaml
opendatahub.io/managed: true
```

That annotation is absent by default. Adding it disables customization and
restores default values. Do not manually remove it or set it to `false`; use
the documented re-enable workflow.

## Demo Policy

For this repo:

- Prefer documenting component resource customizations as scoped patches or
  post-install operations instead of making ArgoCD own the full
  Operator-created Deployment.
- If GitOps automation is used, keep it narrow and explicit: patch only the
  intended Deployment, container, and `resources` fields.
- Never add `opendatahub.io/managed: true` unless the intent is to disable
  customization and restore defaults.
- Treat Deployment deletion as disruptive and require explicit approval before
  using it to re-enable customization.
- Preserve Technology Preview support boundaries when a customized component is
  marked Technology Preview in the official docs.
- Verify the active Deployment and container names before patching.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify the target component Deployment in `redhat-ods-applications`.
4. Verify the current Deployment YAML and container names.
5. Decide whether the task is:
   - customize CPU/memory requests or limits
   - disable customization and restore defaults
   - re-enable customization after it was disabled
6. Use `examples/component-resource-customization-patterns.md` for review
   patterns.
7. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/component-resource-customization-patterns.md`
