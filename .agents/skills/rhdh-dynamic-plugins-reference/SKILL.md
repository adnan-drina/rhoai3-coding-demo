---
name: rhdh-dynamic-plugins-reference
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when looking up preinstalled dynamic plugins, their names, configuration
  options, and support status in Red Hat Developer Hub. Covers Red Hat GA
  plugins, Technology Preview plugins, community-supported plugins, deprecated
  plugins, other installable plugins, plugin versioning and tagging, OCI image
  references, SHA256 digest determination, and required environment variables.
  Do NOT use for configuring individual plugin settings and integration options
  (use rhdh-dynamic-plugins-configure), Helm Chart deployment values (use
  rhdh-helm-reference), or live cluster changes without the OpenShift safety
  guard.
---

# RHDH Dynamic Plugins Reference

Use this skill to look up preinstalled and installable dynamic plugin names,
versions, OCI paths, support tiers, and required environment variables for
Red Hat Developer Hub on the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior details.
Official Red Hat documentation is product authority. This skill adapts the
official dynamic plugins reference guide to this repo's operations and GitOps
review model.

## Scope

This skill covers:

- preinstalled dynamic plugins and their default enabled/disabled state
- Red Hat Generally Available (GA) plugins: names, versions, package paths,
  required environment variables
- Red Hat Technology Preview plugins: names, versions, package paths, required
  environment variables, and TP support boundary
- community-supported plugins in `ghcr.io`: names, versions, OCI paths,
  required environment variables
- other installable plugins not preinstalled in the RHDH image
- deprecated plugins status
- plugin versioning: `bs_<backstage-version>__<plugin-version>` tag format
- SHA256 digest determination via Skopeo CLI or the RHDH Plugin Export Overlays
  repository
- enabling a disabled preinstalled plugin via `dynamic-plugins.yaml`
- overriding default plugin configuration with `pluginConfig`

Use other skills for adjacent work:

- `rhdh-dynamic-plugins-configure` for configuring individual plugin settings,
  app-config fragments, annotations, ClusterRoles, and integration options
- `rhdh-helm-reference` for Helm Chart configuration values, global/upstream
  namespace parameters, route, test, and orchestrator settings

## Demo Policy

For this repo:

- Reference the dynamic plugins reference guide for plugin names and support
  tiers when reviewing or authoring RHDH plugin configuration.
- Distinguish GA, Technology Preview, and community-supported plugins clearly
  in any documentation or review output.
- Do not claim Technology Preview plugins are production-ready.
- Use SHA256 digests for environment stability when pinning community plugins.
- Do not invent plugin names, versions, or OCI paths not listed in the official
  reference.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - looking up a plugin name, version, or support tier
   - finding the OCI path or required environment variables for a plugin
   - determining the correct tag or SHA256 digest for a community plugin
   - checking whether a plugin is preinstalled or must be installed externally
   - reviewing plugin enablement in `dynamic-plugins.yaml`
4. Cross-reference the official docs when uncertain about support status.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
