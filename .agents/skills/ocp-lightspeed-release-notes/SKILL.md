---
name: ocp-lightspeed-release-notes
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when checking OpenShift Lightspeed 1.0 release notes, new features,
  bug fixes, known issues, deprecated features, and version compatibility
  information. Do NOT use for concepts (use ocp-lightspeed-about), installing
  (use ocp-lightspeed-install), configuring (use ocp-lightspeed-configure),
  operations (use ocp-lightspeed-operate), or troubleshooting
  (use ocp-lightspeed-troubleshoot).
---

# OCP Lightspeed Release Notes

Use this skill to ground OpenShift Lightspeed release information in the
official Red Hat OpenShift Lightspeed 1.0 release notes for the active
baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## FIPS Compliance

Red Hat OpenShift Lightspeed is designed for FIPS. When running on OpenShift
Container Platform in FIPS mode, it uses Red Hat Enterprise Linux cryptographic
libraries submitted (or planned to be submitted) to NIST for FIPS validation on
`x86_64`, `ppc64le`, and `s390X` architectures only.

## Release History

OpenShift Lightspeed 1.0 has the following sub-releases documented:

- **1.1.1** — security fix release addressing CVE-2026-48710 and
  CVE-2026-44432; stability improvements for OCP 4.16+
- **1.1** — feature release with MCP server enhancements, Google Vertex AI
  provider support, TLS hardening, rich text clipboard, Prometheus alert
  attachment, and expandable code blocks
- **1.0** — initial GA release with cluster interaction, PostgreSQL
  persistence, token quota, Technology Preview features, and known issues

## Key Topics

- FIPS compliance posture
- New features: cluster interaction, PostgreSQL persistence, token quota
  (1.0); Kubernetes MCP server read/write with human-in-the-loop, Google
  Vertex AI and Vertex AI Anthropic providers, strong TLS cipher enforcement,
  rich text clipboard copy, Prometheus alert attachment, expandable code
  blocks (1.1)
- Security fixes: CVE-2026-48710, CVE-2026-44432 (1.1.1)
- Technology Preview features in 1.0 (cluster interaction, PostgreSQL
  persistence, token quota)
- Known issues: Lightspeed icon disappearing on namespace/project creation
  (OLS-1815), quota parameter changes not taking effect until period expiry
  (OLS-1826), postgres pod restart breaking service connectivity (OLS-1835)

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the question concerns:
   - new features in a specific sub-release
   - Technology Preview capabilities
   - security fixes (CVEs)
   - known issues and workarounds
   - supported OCP versions
   - FIPS compliance
4. Use exact version numbers and feature names from the extraction.
5. When advising on upgrades, cross-reference known issues and security fixes.

## Related Skills

- Use `ocp-lightspeed-about` for OpenShift Lightspeed concepts and
  architecture.
- Use `ocp-lightspeed-install` for installing the OpenShift Lightspeed
  Operator.
- Use `ocp-lightspeed-configure` for configuring OLSConfig custom resources
  and providers.
- Use `ocp-lightspeed-operate` for day-2 operations and administration.
- Use `ocp-lightspeed-troubleshoot` for diagnosing and resolving Lightspeed
  issues.
- Use `ocp-lightspeed-release-notes` (this skill) for version-specific
  release information.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
