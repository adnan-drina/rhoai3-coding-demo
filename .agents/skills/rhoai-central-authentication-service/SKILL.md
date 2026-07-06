---
name: rhoai-central-authentication-service
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or rebuilding Red Hat OpenShift AI
  centralized authentication service configuration for an external OIDC
  provider: Gateway API prerequisites, direct OIDC assumptions,
  data-science-gateway and kube-auth-proxy behavior, GatewayConfig OIDC
  fields, OIDC client secret handling in openshift-ingress, provider CA trust,
  service account bearer-token access, and authentication troubleshooting for
  Dashboard, Gateway, and OpenShift AI service APIs. Do NOT use for configuring the
  OpenShift cluster identity provider itself; use official OpenShift
  documentation. Do NOT use for RHOAI user/group access policy; use
  rhoai-users-groups-access. Do NOT use for general certificate management;
  use rhoai-certificate-management. For live cluster diagnostics, pair with
  env-troubleshoot and the OpenShift safety guard.
---

# RHOAI Central Authentication Service

Use this skill to manage the OpenShift AI centralized authentication service
and external OIDC provider integration for the active baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is product authority. This skill adapts the
official Administer chapter to this repo's GitOps and secret-handling model.

## Demo Policy

For this repo:

- Treat centralized authentication as optional platform infrastructure until a
  demo step explicitly requires external OIDC.
- Keep real OIDC client secrets, tokens, and provider credentials out of Git.
- Use placeholders in examples; implement secrets through the future approved
  GitOps secret pattern.
- Verify the live `GatewayConfig` resource name before authoring patches
  because official examples use more than one name.
- Do not configure the OpenShift identity provider from this skill; this skill
  starts after the OpenShift cluster is already using the intended external
  OIDC provider.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Confirm the OpenShift cluster is already configured for direct OIDC with
   the intended external provider.
3. Confirm Gateway API and OpenShift AI prerequisites in
   `references/official-doc-extraction.md`.
4. Verify the active `GatewayConfig` name in the cluster before creating GitOps
   patches.
5. Create or reference an OIDC client Secret in `openshift-ingress` without
   committing the real secret value.
6. Configure `GatewayConfig.spec.oidc` with issuer URL, client ID, and
   `clientSecretRef`.
7. Add `spec.providerCASecretName` only when the provider uses a custom or
   private CA.
8. Validate routes and API access with
   `references/validation-checklist.md`.
9. For failures, inspect `data-science-gateway` and `kube-auth-proxy` logs
   before changing manifests.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/central-authentication-service-patterns.md`
