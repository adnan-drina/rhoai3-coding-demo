---
name: ocp-ingress-gateway-routes
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when documenting, reviewing, or rebuilding OpenShift Container Platform
  external access guidance from official OCP documentation: Ingress Operator,
  IngressController, cluster ingress domain, Routes, route TLS termination,
  wildcard routes, router certificates, Ingress objects, Gateway API,
  GatewayClass, Gateway, HTTPRoute, GRPCRoute, ReferenceGrant, DNS management,
  and ingress troubleshooting. Do NOT use for RHOAI-specific Gateway API
  workbench-image migration; use rhoai-workbench-gateway-api-migration. Do NOT
  use for MaaS governance or RHOAI model-serving configuration; use the
  relevant rhoai-* skill.
---

# OCP Ingress Gateway Routes

Use this skill to ground OpenShift external access decisions in official OCP
ingress, route, and Gateway API documentation for the active baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill handles platform ingress and
route primitives; product-specific RHOAI routing belongs in RHOAI component
skills.

## Demo External Access Posture

For this AWS-hosted RHOAI demo:

- Prefer the cluster's existing default ingress domain and router unless a demo
  requirement demands a custom domain or dedicated IngressController.
- Use OpenShift `Route` resources for simple application exposure when a
  product component supports routes.
- Use Gateway API only when the component or official RHOAI guidance requires
  it, and verify Gateway API prerequisites and conflicts first.
- Treat custom default certificates, wildcard routes, DNS changes, router
  scaling, and GatewayClass creation as live cluster operations.

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns:
   - default ingress domain or Ingress Operator health
   - `IngressController` configuration
   - OpenShift `Route` authoring or TLS termination
   - Kubernetes `Ingress`
   - Gateway API resources
   - DNS management or router certificates
4. For manifests, verify API versions and fields with official docs and active
   cluster schema.
5. For live operations, follow the OpenShift safety guard and pair this skill
   with the relevant `env-*` skill.
6. Validate with `references/validation-checklist.md`.

## Related Skills

- Use `rhoai-workbench-gateway-api-migration` for RHOAI custom workbench image
  compatibility with Gateway API routing.
- Use `rhoai-maas-governance` for RHOAI Models-as-a-Service gateway and
  governance workflows.
- Use `project-gitops-authoring` for repo-specific Route, Gateway, or
  HTTPRoute manifest placement.
- Use `env-troubleshoot` for live connectivity and TLS failures.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/external-access-review.md`
