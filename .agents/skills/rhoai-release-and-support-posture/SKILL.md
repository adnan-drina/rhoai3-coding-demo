---
name: rhoai-release-and-support-posture
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or deciding Red Hat OpenShift AI release
  and support posture: release notes, lifecycle phases, GA, EUS, Early Access,
  Technology Preview, Developer Preview, deprecated and removed functionality,
  known issues, support windows, upgrade-support expectations, and demo labels
  for feature maturity. Do NOT use for Operator channel manifests (use
  rhoai-update-channels), API tier stability (use rhoai-api-tiers), supported
  hardware planning (use rhoai-platform-planning), or component implementation
  details (use the relevant rhoai-* skill).
---

# RHOAI Release And Support Posture

Use this skill to prevent demo documentation from overstating support status or
feature maturity.

## Source Grounding

1. Read `docs/PLATFORM_BASELINE.md`.
2. Read `.agents/rules/rhoai.md`.
3. Use `references/source-capture.md` for source provenance.
4. Use `references/official-doc-extraction.md` for support-posture facts.
5. Use `references/validation-checklist.md` before finalizing claims.

## Scope

- RHOAI release notes and lifecycle.
- Full Support, Maintenance Support, Extended Update Support, GA, EUS, and
  Early Access release types.
- Technology Preview and Developer Preview support boundaries.
- Deprecated and removed features that affect demo design.
- Known issues and upgrade risk notes.

## Demo Policy

- Label preview features explicitly in READMEs, architecture notes, and demo
  scripts.
- The demo may showcase latest features and Technology Preview capabilities,
  but must not describe them as production supported.
- Developer Preview and Early Access content is not production-ready and should
  be used only when the user explicitly wants unsupported demo behavior.
- Use this skill whenever a README says "supported", "GA", "preview",
  "deprecated", "removed", "EUS", or "production".

## Related Skills

- `rhoai-update-channels` for Operator channel and install-plan policy.
- `rhoai-api-tiers` for API compatibility and deprecation windows.
- `rhoai-platform-planning` for product and hardware supported configuration.
- Component-specific `rhoai-*` skills for feature behavior.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/support-posture-labels.md`
