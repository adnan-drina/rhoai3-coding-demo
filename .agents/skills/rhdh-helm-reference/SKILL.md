---
name: rhdh-helm-reference
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when looking up Helm Chart configuration values, parameters, and
  customization options for Red Hat Developer Hub deployment. Covers root
  namespace, global namespace, orchestrator, route, test, upstream Backstage
  chart values, PostgreSQL, service, serviceAccount, ingress, networking,
  metrics, diagnostics, and Orchestrator infrastructure Helm Chart values. Do
  NOT use for configuring individual dynamic plugin settings (use
  rhdh-dynamic-plugins-configure), looking up plugin names or support tiers (use
  rhdh-dynamic-plugins-reference), or live cluster changes without the OpenShift
  safety guard.
---

# RHDH Helm Chart Configuration Reference

Use this skill to look up Helm Chart configuration values for deploying and
customizing Red Hat Developer Hub on the active baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior details.
Official Red Hat documentation is product authority. This skill adapts the
official Helm Chart configuration reference to this repo's operations and
GitOps review model.

## Scope

This skill covers:

- displaying Helm Chart values with Helm CLI (`helm pull`, `helm show values`)
- root namespace: `nameOverride`
- global namespace: `global.auth`, `global.catalogIndex`, `global.clusterRouterBase`,
  `global.dynamic`, `global.host`, `global.imagePullSecrets`, `global.imageRegistry`
- orchestrator namespace: `orchestrator.enabled`, `orchestrator.plugins`,
  `orchestrator.serverlessLogicOperator`, `orchestrator.sonataflowPlatform`
- route namespace: OpenShift Route parameters, TLS configuration
- test namespace: `test.enabled`, test pod image configuration
- upstream Backstage chart: `upstream.backstage.*` including image, replicas,
  resources, probes, env vars, volumes, init containers, security context,
  autoscaling, PDB, diagnostics
- upstream PostgreSQL: `upstream.postgresql.*` including auth, image, architecture
- upstream service: ports, type, annotations, session affinity
- upstream serviceAccount: create, name, annotations, automount
- upstream ingress: host, path, TLS, class
- upstream networking: NetworkPolicy, egress/ingress rules
- upstream metrics: ServiceMonitor configuration
- Orchestrator infrastructure Helm Chart: `serverlessLogicOperator`,
  `serverlessOperator` subscriptions

Use other skills for adjacent work:

- `rhdh-dynamic-plugins-reference` for plugin names, versions, support tiers,
  and OCI paths
- `rhdh-dynamic-plugins-configure` for configuring individual plugin settings,
  app-config fragments, and annotations

## Demo Policy

For this repo:

- Prefer OpenShift Route (`route.enabled: true`) over Ingress for the demo.
- Use an external PostgreSQL database for production; the built-in PostgreSQL
  is acceptable for demo purposes.
- Do not invent Helm Chart keys or values not documented in the official
  reference.
- Reference the correct Helm Chart version for the active RHDH baseline.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - looking up a specific Helm Chart value or its default
   - configuring global, route, upstream, or orchestrator parameters
   - reviewing PostgreSQL, service, ingress, or networking settings
   - pulling and inspecting the Helm Chart locally
4. Use the official reference tables as the configuration authority.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
