---
name: rhoai-api-tiers
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or authoring Red Hat OpenShift AI manifests,
  API clients, README support claims, upgrade notes, or GitOps resources that
  depend on RHOAI API stability tiers: Tier 1, Tier 2, Tier 4, Beta, and Alpha.
  Covers the RHOAI API tier meanings, deprecation windows, customer-accessible
  API version mapping, KServe v1alpha1 footnote exceptions, Technology Preview
  and Developer Preview posture, and when to avoid direct customer dependence
  on internal Tier 4 APIs. Do NOT use as a substitute for component-specific
  configuration docs, live CRD schema verification, or Red Hat Support guidance.
---

# RHOAI API Tiers

Use this skill to classify Red Hat OpenShift AI APIs by support and stability
posture before treating them as durable demo interfaces.

## Source Grounding

Read `references/source-capture.md` before using API tier details. The copied
API tier map is a baseline snapshot from the Red Hat OpenShift AI API Tiers
content supplied for this repo. Recheck the upstream Red Hat supported
configurations and lifecycle pages when the product baseline changes.

## Scope

This skill covers:

- API tier meanings and deprecation-window expectations
- API version to tier mapping for RHOAI customer-accessible endpoints
- distinction between API tier, component support phase, Technology Preview,
  and Developer Preview
- Tier 4 handling for internal or component-owned APIs
- Beta and Alpha support posture for TP/DP APIs
- review guidance for GitOps manifests, README claims, code clients, and
  upgrade notes

Use other skills for adjacent work:

- component-specific `rhoai-*` skills for supported fields, workflows, images,
  and examples
- `project-gitops-authoring` for GitOps layout and Argo CD authoring
- `project-manifest-review` for YAML structure and cross-resource review
- `project-red-hat-doc-alignment-review` for official-source alignment across
  README and GitOps changes

## Demo Policy

For this repo:

- Prefer Tier 1 and Tier 2 APIs for long-lived GitOps resources and demo
  automation.
- Treat Tier 4 APIs as internal or component-owned unless official RHOAI docs
  explicitly instruct customers to configure them.
- Label Beta APIs as Technology Preview in README and presentation material
  when they are used in a user-visible capability.
- Label Alpha APIs as unsupported Developer Preview and avoid using them in
  core demo flows unless the user explicitly accepts that posture.
- Do not infer stability from the Kubernetes version string alone. For example,
  some `v1alpha1` APIs are Tier 2 in the Red Hat table, while other
  `v1alpha1` APIs are Alpha.
- Use the KServe footnote exceptions before classifying
  `*.serving.kserve.io/v1alpha1`.
- When an API version is not in the captured table, mark the tier unresolved
  and verify through current Red Hat docs, CRD metadata, release notes, or
  support guidance.

## Workflow

1. Confirm the active product baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md` for tier meanings.
3. Read `references/api-tier-map.md` for the API version table.
4. For each manifest, API client, README claim, or runbook:
   - identify the API group, version, endpoint, SDK, or library
   - map it to a tier
   - record whether the capability is GA, Technology Preview, Developer
     Preview, internal, or unresolved
5. For Tier 4, Beta, or Alpha dependencies, document the risk and decide
   whether the demo should avoid, isolate, or explicitly label the API.
6. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/api-tier-map.md`
- `references/validation-checklist.md`
- `examples/api-tier-review-patterns.md`
