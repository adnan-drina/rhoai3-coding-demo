---
name: ocp-devspaces-admin
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when administering Red Hat OpenShift Dev Spaces 3.28, including
  CheCluster CR customization, storage configuration, workspace limits,
  user management, RBAC, networking, TLS certificates, and monitoring.
  Do NOT use for concepts (use ocp-devspaces-about), installing (use
  ocp-devspaces-install), user workflows (use ocp-devspaces-user-guide),
  or release notes (use ocp-devspaces-release-notes).
---

# OCP Dev Spaces Administration

Use this skill to ground OpenShift Dev Spaces administration guidance in the
official Red Hat OpenShift Dev Spaces 3.28 Administration Guide.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. Detailed CheCluster CR field values,
storage strategies, networking, RBAC, monitoring, and troubleshooting procedures
come from the Administration Guide captured in
`references/official-doc-extraction.md`.

## Key Administration Areas

### CheCluster Custom Resource

The `CheCluster` CR (`apiVersion: org.eclipse.che/v2`) is the central
configuration object. The Operator translates it into ConfigMaps consumed by
each component. Key top-level spec sections:

- `spec.components` — cheServer, dashboard, pluginRegistry, devfileRegistry,
  imagePuller, metrics
- `spec.devEnvironments` — workspace defaults, storage, limits, defaultEditor,
  defaultNamespace, security, nodeSelector
- `spec.networking` — hostname, TLS, auth, proxy, domain, labels, annotations

Edit with `oc edit checluster/devspaces -n openshift-devspaces` or `oc patch`.

### Storage Configuration

Three strategies controlled by `spec.devEnvironments.storage.pvc.pvcStrategy`:

- `per-user` (default) — single RWX PVC shared across all user workspaces
  (requires ReadWriteMany; default 10Gi)
- `per-workspace` — each workspace gets its own PVC (default 5Gi)
- `ephemeral` — no persistent storage; changes lost on stop

Storage classes set via `perUserStrategyPvcConfig.storageClass` and
`perWorkspaceStrategyPvcConfig.storageClass`. Persistent user home
(`/home/user`) enabled by default via `spec.devEnvironments.persistUserHome`.

### Workspace Limits and Quotas

- `maxNumberOfWorkspacesPerUser` — total workspaces per user (default -1,
  unlimited)
- `maxNumberOfRunningWorkspacesPerUser` — concurrent running per user (default
  1)
- `maxNumberOfRunningWorkspacesPerCluster` — cluster-wide running limit
- `containerResourceCaps` — cap container resource requests/limits
- `defaultContainerResources` — default resources for containers without specs
- Memory limit override via `CHE_WORKSPACE_DEFAULT__MEMORY__LIMIT__MB`

### Project and Namespace Configuration

Default namespace template: `<username>-devspaces`. Configured via
`spec.devEnvironments.defaultNamespace.template`. Supports `<username>` and
`<userid>` placeholders. Auto-provisioning controlled by
`defaultNamespace.autoProvision`.

### Identity and Authorization

- Cluster roles for users: `spec.devEnvironments.user.clusterRoles` and
  `spec.components.cheServer.clusterRoles`
- Advanced authorization:
  `spec.networking.auth.advancedAuthorization.{allowUsers,allowGroups,denyUsers,denyGroups}`
- Default RBAC: Operator creates `<namespace>-cheworkspaces-clusterrole` and
  `<namespace>-cheworkspaces-devworkspace-clusterrole`
- Git OAuth: GitHub App/OAuth, GitLab, Bitbucket, Microsoft Entra ID

### Networking

- Hostname: `spec.networking.hostname`
- TLS: `spec.networking.tlsSecretName`; custom CA certs via labeled ConfigMap
  (`app.kubernetes.io/component=ca-bundle`)
- Network policies for Dev Workspace webhook, workspace namespaces, and
  OpenShift API server
- Router Sharding: `spec.networking.{labels,domain,annotations}`
- Proxy: `spec.components.cheServer.proxy.{url,port,nonProxyHosts,
  credentialsSecretName}`

### Monitoring and Observability

- Dev Workspace Operator metrics on port 8443 (`/metrics`):
  `devworkspace_started_total`, `devworkspace_started_success_total`,
  `devworkspace_fail_total`, `devworkspace_startup_time`
- Server JVM metrics on port 8087 via `spec.components.metrics.enable`
- ServiceMonitor for Prometheus scraping; label namespace with
  `openshift.io/cluster-monitoring=true`
- Server logging: `CHE_LOGGER_CONFIG` in
  `spec.components.cheServer.extraProperties`
- Log collection with `dsc` CLI tool

### Security Best Practices

- Per-user project isolation (`<username>-devspaces`)
- SCC constraints; container build/run capabilities control
- Resource Quotas and LimitRanges
- Network policies for ingress restriction
- Extension management and secret handling

## Workflow

1. Read `references/source-capture.md` and confirm the Dev Spaces version.
2. Read `references/official-doc-extraction.md` for specific procedures.
3. Identify the administration area (CheCluster CR, storage, networking, RBAC,
   monitoring, upgrade, troubleshooting).
4. For CheCluster CR changes, verify fields with
   `oc explain checluster.spec --recursive` on the target cluster.
5. For networking changes, check TLS, Route, and NetworkPolicy resources.
6. For monitoring, verify ServiceMonitor and namespace labeling.
7. For troubleshooting, check workspace startup errors, OAuth errors, and
   DevWorkspace Operator logs.

## Related Skills

- `ocp-devspaces-about` — Dev Spaces concepts and architecture
- `ocp-devspaces-install` — installing and upgrading Dev Spaces
- `ocp-devspaces-user-guide` — user workflows, devfiles, workspaces
- `ocp-devspaces-release-notes` — release notes and known issues
- `ocp-devspaces-admin` — this skill (administration guide)

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
