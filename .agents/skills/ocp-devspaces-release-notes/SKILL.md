---
name: ocp-devspaces-release-notes
metadata:
  author: rhoai3-coding-demo
  version: 1.1.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when checking OpenShift Dev Spaces 3.30 release notes, new features,
  bug fixes, known issues, and version compatibility. Covers 3.30.0, 3.30.1,
  and 3.30.2 sub-releases. Do NOT use for concepts (use ocp-devspaces-about),
  installing (use ocp-devspaces-install), administration (use
  ocp-devspaces-admin), or user workflows (use ocp-devspaces-user-guide).
---

# OpenShift Dev Spaces Release Notes — 3.30

Read `references/source-capture.md` and the current-update section of
`references/official-doc-extraction.md` before advising an upgrade.

## Captured release

Latest patch captured: **3.30.2**, released 2026-09-30. It fixes custom dashboard
samples disappearing when the internal devfile registry is disabled and
addresses two code-rhel9 CVEs.

3.30 includes DWO 0.43 and Eclipse Che 7.120/7.121, and documents support for
OpenShift 4.16–4.22. Code - OSS supports extension API 1.128.x. Validate the
actual editor and extension packages rather than carrying forward 3.28 pins.

## Adoption checks

- JetBrains IDE binaries are cached after their first download.
- TLS certificate references propagate to DWO.
- The dashboard can re-inject Kubernetes/registry credentials and restart a
  running workspace in debug mode.
- Multicluster redirection uses all assigned groups.
- Workspace creation events can be paused/resumed in the dashboard.
- AI-provider injection is Technology Preview; it is separate from the
  project's governed MaaS configuration.

Credential re-injection must preserve the restricted migration-worker boundary.
Product feature availability does not authorize wider worker permissions.
Check the selected patch's known issues and actual DWO before qualifying the
upgrade; no live upgrade is proved by this documentation update.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
