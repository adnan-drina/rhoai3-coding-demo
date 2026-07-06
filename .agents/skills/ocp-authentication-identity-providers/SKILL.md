---
name: ocp-authentication-identity-providers
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when documenting, reviewing, or rebuilding OpenShift Container Platform
  authentication and identity-provider guidance from official OCP
  documentation: OAuth cluster configuration, identity provider mapping,
  htpasswd, LDAP, OIDC, GitHub, GitLab, Keystone, request-header providers,
  direct external OIDC authentication, kubeadmin removal, users, identities,
  groups, LDAP group sync, and cluster-admin access continuity. Do NOT use for
  Red Hat OpenShift AI dashboard administrator or user group selection; use
  rhoai-users-groups-access and rhoai-access-group-selection. Do NOT use for
  RBAC, service-account permissions, or SecurityContextConstraints; use
  ocp-security-rbac-scc.
---

# OCP Authentication Identity Providers

Use this skill to keep OpenShift authentication and identity-provider work
grounded in the official OCP authentication and authorization documentation for
the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers identity-provider
selection and configuration boundaries, not application-level authorization or
RHOAI dashboard group policy.

## Demo Authentication Posture

For this AWS-hosted RHOAI demo:

- Treat the underlying OpenShift cluster identity provider as pre-existing
  unless the implementation explicitly includes identity-provider GitOps.
- Preserve a cluster-admin recovery path before proposing OAuth or direct OIDC
  changes.
- Keep RHOAI-specific administrator and user group selection in the RHOAI
  skills; this skill only establishes the OpenShift user, group, and identity
  substrate.
- Do not use htpasswd as a production enterprise recommendation. It is useful
  for development clusters and small demo environments only when documented as
  such.
- Treat direct external OIDC authentication as high-impact because it replaces
  the built-in OpenShift OAuth flow and changes available OAuth/user APIs.

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns:
   - identity-provider review or selection
   - `OAuth` cluster resource configuration
   - identity-to-user mapping behavior
   - direct external OIDC authentication
   - `kubeadmin` removal or emergency access
   - users, identities, groups, or LDAP group sync
4. For GitOps authoring, verify every API version, field, secret reference,
   namespace, and supported provider option against official docs and cluster
   schema.
5. For live operations, follow the OpenShift safety guard and pair this skill
   with the relevant `env-*` skill.
6. Validate with `references/validation-checklist.md`.

## Related Skills

- Use `ocp-security-rbac-scc` for RBAC, service accounts, and SCCs.
- Use `rhoai-users-groups-access` for OpenShift AI user and administrator
  access behavior.
- Use `rhoai-access-group-selection` for dashboard workflows that select
  OpenShift groups for RHOAI access.
- Use `env-troubleshoot` for live login or OAuth failures.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/identity-provider-review.md`
