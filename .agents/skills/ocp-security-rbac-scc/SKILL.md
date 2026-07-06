---
name: ocp-security-rbac-scc
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when documenting, reviewing, or rebuilding OpenShift Container Platform
  RBAC and workload security guidance from official OCP documentation: Role,
  ClusterRole, RoleBinding, ClusterRoleBinding, service accounts, oc auth
  can-i, who-can checks, SecurityContextConstraints, SCC grants, custom SCCs,
  default SCC preservation, pod security admission interaction, namespace
  privilege boundaries, and least-privilege review. Do NOT use for
  identity-provider configuration; use ocp-authentication-identity-providers.
  Do NOT use for RHOAI dashboard access groups; use rhoai-users-groups-access.
---

# OCP Security RBAC SCC

Use this skill to ground OpenShift permissions and workload security posture in
official OCP RBAC, service-account, and SecurityContextConstraints guidance for
the active baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers OpenShift platform
authorization and pod admission controls, not identity-provider configuration.

## Demo Security Posture

For this AWS-hosted RHOAI demo:

- Prefer least-privilege Roles and RoleBindings for demo workloads.
- Use cluster-wide privileges only when the product component requires them and
  the README or operations doc explains why.
- Do not modify or delete default SCCs.
- Prefer product Operator-managed RBAC and SCC integration where official docs
  define it.
- Treat `privileged`, host access, broad cluster-admin grants, and custom SCCs
  as exceptional and review them before GitOps authoring.

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns:
   - project-scoped RBAC
   - cluster-scoped RBAC
   - service accounts or service-account tokens
   - `oc auth can-i` or `oc adm policy who-can` checks
   - SCC admission, custom SCCs, or SCC grants
   - pod security admission interaction
4. Verify API versions, subjects, verbs, resources, namespace scope, and SCC
   grants before authoring manifests.
5. For live operations, follow the OpenShift safety guard and pair this skill
   with the relevant `env-*` skill.
6. Validate with `references/validation-checklist.md`.

## Related Skills

- Use `ocp-authentication-identity-providers` for OAuth, identity providers,
  users, identities, and groups.
- Use `project-manifest-review` for read-only manifest review across
  Kubernetes, OpenShift, Argo CD, and RHOAI resources.
- Use `project-gitops-authoring` for repo-specific RBAC manifest placement.
- Use `env-troubleshoot` for live permission or pod admission failures.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/rbac-scc-review.md`
