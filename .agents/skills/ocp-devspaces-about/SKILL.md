---
name: ocp-devspaces-about
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when documenting, reviewing, or explaining OpenShift Dev Spaces concepts,
  architecture, DevWorkspace operator, workspace lifecycle, supported IDEs,
  and cloud development environment capabilities from the official OpenShift
  Dev Spaces 3.28 documentation. Do NOT use for installing (use
  ocp-devspaces-install), administration (use ocp-devspaces-admin), user
  workflows (use ocp-devspaces-user-guide), or release notes (use
  ocp-devspaces-release-notes).
---

# OCP Dev Spaces About

Use this skill to ground OpenShift Dev Spaces conceptual guidance in the
official Red Hat OpenShift Dev Spaces 3.28 "Discover" guide for the active
baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Key Concepts

### What Is OpenShift Dev Spaces

Red Hat OpenShift Dev Spaces is an OpenShift-native platform that provides
cloud development environments (CDEs) to development teams. Developers get
on-demand workspaces — container-based environments with tools, dependencies,
and IDE access — without configuring local machines.

Core goals:
- Accelerate project and developer onboarding (zero-install, browser-based)
- Remove inconsistency between developer environments (devfile-defined)
- Provide built-in security and enterprise readiness (source on cluster, RBAC, OIDC)

### Architecture

OpenShift Dev Spaces runs on three groups of components that communicate through
Dev Workspace custom resources:

1. **Server components** — manage multi-tenancy and workspace lifecycle
   (Operator, gateway, dashboard, server, plug-in registry)
2. **Dev Workspace Operator** — provisions workspace pods, services, and PVs
3. **User workspaces** — container-based development environments with IDE

OpenShift RBAC controls access to all resources. The `CheCluster` CR is the
central configuration object.

### DevWorkspace Operator (DWO)

DWO extends OpenShift to manage workspace pods by reconciling Dev Workspace CRs.
CRDs provided:
- `DevWorkspace` — workspace definition (devfile + editor + attributes)
- `DevWorkspaceTemplate` — reusable spec.template content (e.g., editor definitions)
- `DevWorkspaceOperatorConfig` (DWOC) — operator configuration (global and non-global)
- `DevWorkspaceRouting` — workspace endpoint definitions

DWO operands: controller-manager deployment and webhook-server deployment.

### Supported IDEs and Editors

- Microsoft Visual Studio Code - Open Source (browser-based, default)
- JetBrains IntelliJ IDEA (via JetBrains Gateway for native desktop)
- Extensible through devfiles, VS Code extensions from Open VSX registries,
  and AI coding assistants

### Workspace Lifecycle

1. User opens Git repository URL in the Dev Spaces dashboard
2. Dashboard sends repository URL to server, receives devfile
3. Dashboard collects editor metadata from plug-in registry
4. Dashboard converts devfile + editor into a Dev Workspace CR
5. Dev Workspace CR created in user project via OpenShift API
6. DWO reconciles the CR, creating pod, services, routes, secrets, PVs
7. User is redirected to the running workspace IDE

Workspaces are rebuilt from the devfile on each start; `/home/user` persists
across restarts by default.

### Gateway

The `che-gateway` Deployment routes requests, authenticates users with OIDC
(OAuth2 Proxy), and enforces OpenShift RBAC (kube-rbac-proxy). Uses Traefik
for request routing.

### Server Components

- **OpenShift Dev Spaces Operator** — lifecycle management via CheCluster CR
- **Gateway** — routing, OIDC auth, RBAC enforcement
- **Dashboard** — user-facing workspace creation and management UI
- **Server** — Java web service for namespace provisioning, Git integration
- **Plug-in registry** — editor and extension catalog (Devfile v2 format)

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify the relevant concept (architecture, DWO CRDs, workspace model, etc.).
4. For GitOps manifests, verify all API versions and fields against the
   extraction before committing.
5. For live operations, use the repo environment guard.
6. Validate with `references/source-capture.md` boundaries.

## Related Skills

- Use `ocp-devspaces-about` (this skill) for concepts and architecture.
- Use `ocp-devspaces-install` for installation procedures.
- Use `ocp-devspaces-admin` for administration and CheCluster configuration.
- Use `ocp-devspaces-user-guide` for developer workspace workflows.
- Use `ocp-devspaces-release-notes` for version-specific changes.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
