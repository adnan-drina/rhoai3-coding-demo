---
name: rhoai-platform-planning
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when planning, documenting, or reviewing the Red Hat OpenShift AI
  platform baseline for the demo: supported OpenShift versions, AWS
  self-managed posture, subscriptions, cluster-admin access, worker resources,
  default storage class, identity provider, registry access, object storage,
  component prerequisites, supported configurations, component support status,
  hardware and accelerator planning, and Red Hat AI Inference compatibility.
  Do NOT use for exact DSC fields (use rhoai-dsci-dsc-configuration), GPU
  implementation manifests (use rhoai-nvidia-gpu-accelerators), update channel
  policy (use rhoai-update-channels), or live environment validation
  (use env-deploy-and-evaluate).
---

# RHOAI Platform Planning

Use this skill before writing demo GitOps that assumes a particular OpenShift
AI platform shape.

## Source Grounding

1. Read `docs/PLATFORM_BASELINE.md`.
2. Read `.agents/rules/rhoai.md`.
3. Use `references/source-capture.md` for source provenance.
4. Use `references/official-doc-extraction.md` for planning facts.
5. Use `references/validation-checklist.md` before finalizing planning claims.

## Demo Planning Policy

- The demo targets Red Hat OpenShift AI Self-Managed on an existing AWS-hosted
  OpenShift cluster.
- Confirm OpenShift, RHOAI, ODF, OpenTelemetry, and tracing baselines before
  using component-specific guidance.
- Prefer NVIDIA GPUs for this demo, but verify accelerator support through the
  active GPU skill and Red Hat supported configuration sources.
- Treat object storage as a platform prerequisite for model serving, AI
  Pipelines, model registry, MLflow, and RHOAI data workflows.
- Do not treat a supported component as implemented until the demo GitOps,
  documentation, and validation exist.

## Workflow

1. Confirm the target platform versions in `docs/PLATFORM_BASELINE.md`.
2. Check supported OpenShift versions and architecture support.
3. Check component support status and prerequisites for the planned demo
   capability.
4. Confirm storage, identity provider, and registry/network prerequisites.
5. Hand off implementation details to the matching component skill.

## Related Skills

- `rhoai-release-and-support-posture` for lifecycle, GA, EUS, Early Access,
  Technology Preview, Developer Preview, deprecation, and removal posture.
- `rhoai-nvidia-gpu-accelerators` for demo GPU profile and NVIDIA enablement.
- `odf-multicloud-gateway` and `odf-object-bucket-claims` for object storage.
- `rhoai-dsci-dsc-configuration` for platform CR configuration.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/platform-planning-review.md`
