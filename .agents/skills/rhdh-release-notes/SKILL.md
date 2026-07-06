---
name: rhdh-release-notes
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when checking RHDH 1.10 release notes, new features, bug fixes, known
  issues, deprecated features, removed features, or Technology Preview and
  Developer Preview status from the official release notes. Do NOT use for
  product concepts or architecture (use rhdh-about), installing or configuring
  (use rhdh-install/rhdh-configure), or preview feature details
  (use rhdh-preview-features).
---

# RHDH Release Notes

Use this skill to ground Red Hat Developer Hub 1.10 release note inquiries in
the official release notes document.

## Source Grounding

Read `references/source-capture.md` before citing specific features or fixes.
Official Red Hat documentation is product authority.

## Release Summary

RHDH 1.10 is GA. It is a productized version of upstream Backstage 1.49.4.
Plugins may be compatible with a newer Backstage version. Updated to Node.js 24.

## Highlights

Key new features in RHDH 1.10:

- **Developer Lightspeed for RHDH** available as default plugin (requires LLM
  configuration by platform engineer). MCP servers manageable from chat
  interface.
- **Personalized homepages** for user groups via dynamic plugins and visibility
  rules.
- **Default RBAC role and baseline permissions** via
  `permission.rbac.defaultPermissions`.
- **PingFederate** as new authentication provider.
- **Flavor-based Operator configuration** via v1alpha5 API with
  `spec.flavours[]`.
- **New Frontend System (NFS)** support for Red Hat GA frontend plugins.
- **Scorecard enhancements**: file-level compliance checks, aggregated KPI
  cards, navigation and data freshness.
- **Scaffolder MCP tools** for template discovery, validation, and execution.
- **Single database deployments** with `pluginDivisionMode: schema`.
- **Bulk Import** scoped to signed-in user OAuth with pending import filtering.
- **Localization**: Spanish and German added.
- **Orchestrator**: Loki backend (GA), retry configuration, custom review pages.
- **OCP 4.21** and Kubernetes 1.34 supported.

## Deprecated Features

- Global Floating Action Button disabled by default (use Global Header).
- Community-supported auth providers (Atlassian, Auth0, Azure-easyauth,
  Bitbucket, Bitbucket Server, Cloudflare Access, Google, Google IAP, OAuth 2
  Custom Proxy, OneLogin, Okta) will move to dynamic plugins in a future
  release.
- `backstage-community-plugin-acr` moved to Community support.

## Removed Features

- OCM plugin and wrapper removed.
- Operator no longer auto-deletes user-created resources when features disabled.
- Several plugins downgraded from GA/TP to Community support and removed as
  embedded wrappers (quay, tekton, scaffolder-backend-argocd). Use `oci://`
  references instead.

## Known Issues

See `references/official-doc-extraction.md` for the complete list including:
- Orchestrator in-place upgrade fails on immutable database-creation Job.
- OCI images from registry.access.redhat.com fail plugin path auto-detection.
- Custom threshold configuration unavailable for Filecheck/Openssf/Dependabot
  Scorecard modules.
- Bulk Import marks repos with open PRs as already imported.
- Label casing mismatch in conditional HAS_LABEL RBAC policies.

## Fixed Issues

RHDH 1.10.0 and 1.10.1 include fixes tracked in Red Hat Bug Advisories
RHBA-2026:25065 and RHBA-2026:25382. See
`references/official-doc-extraction.md` for the complete list.

## Security Fixes

Security issues fixed in RHDH 1.10.0 are tracked in RHSA-2026:24841.

## Workflow

1. Read `references/official-doc-extraction.md` for detailed feature and fix
   listings.
2. Check whether a feature is GA, Technology Preview, or Developer Preview
   before documenting or implementing.
3. Verify deprecated auth providers before configuring authentication.
4. Check known issues before reporting new bugs.

## Related Skills

- `rhdh-about` — RHDH concepts, architecture, sizing, and deployment methods.
- `rhdh-preview-features` — Technology Preview and Developer Preview details.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
