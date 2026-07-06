---
name: rhoai-update-channels
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when selecting, documenting, reviewing, or changing Red Hat OpenShift AI
  Operator update channels and update strategy for the demo. Covers fast,
  fast-x.y, stable, stable-x.y, eus-x.y, and alpha channel intent; choosing a
  feature-forward channel for latest product capabilities and technology
  previews; validating channel availability through OLM; and avoiding legacy
  embedded/beta channels. Do NOT use for specific component CR fields,
  installation manifests beyond Subscription channel policy, or live cluster
  troubleshooting; use the relevant RHOAI component skill and env-* skills.
---

# RHOAI Update Channels

Use this skill to choose and review Red Hat OpenShift AI Operator update
channels for the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is product authority. Lifecycle and support-scope
pages are supporting sources for channel availability, lifecycle posture, and
preview support boundaries.

## Demo Channel Policy

This demo intentionally prioritizes latest product features and selected
technology-preview capabilities over long-lived channel stability.

Default policy:

- Prefer `fast-3.x` or the active `fast-x.y` channel family when the active OLM
  catalog exposes that channel for the target RHOAI baseline.
- Use `installPlanApproval: Automatic` with the feature-forward channel when
  the goal is to receive monthly updates without manual channel maintenance.
- If `fast-3.x` is not available for the target release, do not invent it.
  Verify available channels from the catalog and choose the documented latest
  supported GA channel, usually `stable-3.x` or a numbered stable channel for
  the active baseline.
- Treat `alpha` as development or early-access only. Do not use it for
  production-like demo environments unless the user explicitly wants
  unsupported early-access behavior.
- Do not use `embedded` or `beta` for new Operator installations.
- Represent RHOAI channel and approval strategy in Git through the operator
  overlay pattern from `project-red-hat-operator-gitops`; do not change the
  live Subscription as the normal lifecycle path.

Technology Preview note: choosing a faster update channel does not make every
Technology Preview feature production-supported. Use the relevant release notes
and component docs to identify preview posture, then label the demo capability
accordingly.

## Workflow

1. Read `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Decide the channel intent:
   - latest supported product features: `fast` or `fast-x.y` when available
   - latest GA with less churn: `stable`
   - version-pinned GA planning window: `stable-x.y`
   - extended update support: `eus-x.y`
   - early-access development feedback: `alpha`
4. Verify channel availability in the active OLM catalog before writing GitOps.
5. When implementing the Subscription, keep channel policy, install-plan
   approval strategy, and support posture documented together.
6. For upgrades, update the GitOps channel overlay and sync the operator
   Application before changing DSC/DSCI component patches that rely on new
   schema.
7. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/subscription-channel-policy.md`
