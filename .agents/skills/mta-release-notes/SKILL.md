---
name: mta-release-notes
metadata:
  author: rhoai3-coding-demo
  version: 1.1.0
  platform-family: "mta"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Application Modernization"
description: >
  Use when checking MTA 8.3 release notes, new features, bug fixes, known
  issues, and deprecated features. Do NOT use for installing (use mta-install),
  using tools (use mta-cli/mta-ui), or AI features (use mta-lightspeed).
---

# MTA Release Notes — 8.3

Read `references/source-capture.md` and the current-update section of
`references/official-doc-extraction.md` for exact source and support boundaries.

## Current release

The captured release is 8.3.0. New native MTA Agents support single runs and
predetermined multistage workflows with sandbox execution and shared-Git
handoffs. These capabilities are **Developer Preview**.

mta-ops adds same-cluster PVC StorageClass conversion, indirect transfer through
S3, persistent structured audit logging and clearer transfer progress. AWS S3
is the validated indirect-transfer provider. S3 compatibility alone does not
qualify NooBaa for this particular transfer workflow.

BuildConfig-to-Shipwright conversion is **Technology Preview**. Developer
Lightspeed, Solution Server and IDE Agent AI retain their own preview boundaries.

## Changes to check

- The CLI's deprecated listing, test and transform commands have replacements
  under rules, provider and openrewrite.
- MTA-6530 still misses annotation incidents through wildcard imports.
- MTA-6863 fixes applying unsaved review-editor suggestions.
- MTA-7870 can leave mta-ops executing without an audit file after a warning;
  verify the artifact if the workflow requires it.

The release book contains historical 8.0–8.2 chapters. Attribute a feature or
fix to its actual release. Do not copy those chapters as new 8.3 functionality.
Verify installed Operator, CLI, RPC and IDE versions separately.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
