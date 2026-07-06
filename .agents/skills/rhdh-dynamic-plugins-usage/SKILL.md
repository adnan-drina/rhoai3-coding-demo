---
name: rhdh-dynamic-plugins-usage
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when using Red Hat Developer Hub 1.10 plugins to access development
  infrastructure and software development tools, including Argo CD, Tekton,
  Topology, Keycloak, JFrog Artifactory, and Nexus Repository Manager plugins.
  Do NOT use for developing new plugins (use rhdh-dynamic-plugins-develop) or
  for installing plugins (use rhdh-dynamic-plugins-install).
---

# RHDH Dynamic Plugins: Usage

Use this skill to understand how to use installed dynamic plugins in Red Hat
Developer Hub 1.10 to interact with development infrastructure and tools.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers usage procedures for
shipped RHDH plugins including Argo CD, Tekton, Topology, Keycloak, JFrog
Artifactory, and Nexus Repository Manager.

## Available Plugins

### Argo CD Plugin

Visualize CD workflows in OpenShift GitOps:

- **CD tab** — view deployment details: commit message, author, container
  image, deployment history
- **Deployment summary** — overview across namespaces in the Overview tab
- **Deep links** — click link icon to open deployment details in Argo CD
- **Revision tracking** — click commit ID to review changes in GitLab/GitHub

**Prerequisites:** Argo CD plugin must be enabled in RHDH.

### Tekton Plugin

Visualize CI/CD pipeline run results from Kubernetes/OpenShift clusters:

- **CI tab** — list of `PipelineRun` resources with NAME, VULNERABILITIES,
  STATUS, TASK STATUS, STARTED, DURATION
- **Pipeline visualization** — expand a PipelineRun to see task cards; hover
  for step details
- **Component view** — select a component from Catalog to see its pipelines

**Prerequisites:** Tekton plugin must be installed per the "Installing" guide.

### Topology Plugin

View workloads as nodes on Kubernetes clusters:

- **TOPOLOGY tab** — visual node graph of deployments and pods
- **Node details** — select a node for Details and Resources tabs
- **Open URL** — access associated Ingresses to run the application

**RBAC permissions required:**

| Permission | Purpose |
|-----------|---------|
| `kubernetes.clusters.read` + `read` | View Topology panel |
| `kubernetes.resources.read` + `read` | View Topology panel |
| `kubernetes.proxy` + `use` | View pod logs |
| `catalog-entity` + `read` | View catalog items |

Example RBAC policy (`rbac-policy.csv`):

```csv
g, user:default/<USERNAME>, role:default/topology-viewer
p, role:default/topology-viewer, kubernetes.clusters.read, read, allow
p, role:default/topology-viewer, kubernetes.resources.read, read, allow
p, role:default/topology-viewer, kubernetes.proxy, use, allow
p, role:default/topology-viewer, catalog-entity, read, allow
```

### Keycloak Plugin

Synchronize Keycloak users and groups into the RHDH catalog:

- **User sync** — imports users from a Keycloak realm
- **Group sync** — imports groups and their members
- **Scheduled sync** — configure a schedule for periodic imports
- **Browse** — Catalog > User/Group entity type filter

### JFrog Artifactory Plugin

Display container image information from JFrog Artifactory:

- **Image Registry tab** — list of container images with Version,
  Repositories, Manifest, Modified, Size
- Navigate from a Catalog component to its images

**Prerequisites:** JFrog Artifactory plugin must be enabled.

### Nexus Repository Manager Plugin

View build artifacts from Nexus Repository Manager:

- **BUILD ARTIFACTS tab** — list with VERSION, REPOSITORY, REPOSITORY TYPE,
  MANIFEST, MODIFIED, SIZE
- Navigate from a Catalog component to its artifacts

**Prerequisites:** Nexus Repository Manager plugin must be installed.

### Ansible Plugins (Technology Preview)

Ansible-specific portal experience with:
- Curated learning paths
- Push-button content creation
- Integrated development tools

**Note:** Technology Preview — not supported for production use.

## Plugin Navigation Pattern

All plugins follow a consistent pattern:
1. Open RHDH application
2. Select a component from the Catalog page
3. Navigate to the plugin-specific tab (CD, CI, TOPOLOGY, BUILD ARTIFACTS,
   Image Registry, Feedback)

## Workflow

1. Identify the plugin needed for the development tool.
2. Confirm the plugin is enabled (Administration > Extensions > Installed).
3. Navigate to a Catalog component entity page.
4. Select the appropriate tab for the plugin.
5. For Topology, ensure RBAC permissions are granted.

## Related Skills

- `rhdh-dynamic-plugins-develop` — developing custom dynamic plugins
- `rhdh-dynamic-plugins-install` — installing and configuring plugins

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
