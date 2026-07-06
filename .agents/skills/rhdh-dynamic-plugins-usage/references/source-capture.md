# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat Developer Hub |
| Product version | 1.10 |
| Documentation category | Extend |
| Official guide | Using dynamic plugins in Red Hat Developer Hub |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/using_dynamic_plugins_in_red_hat_developer_hub/index |
| Single-page URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/using_dynamic_plugins_in_red_hat_developer_hub/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Preface
- Chapter 1: Using Ansible plug-ins for Red Hat Developer Hub (Tech Preview)
- Chapter 2: Use the Argo CD plugin
  - CD tab, deployment details, deep links to Argo CD, deployment summary
- Chapter 3: Use the JFrog Artifactory plugin
  - Image Registry tab, container image details
- Chapter 4: Use Keycloak
  - User synchronization, group synchronization, scheduled imports
- Chapter 5: Use the Nexus Repository Manager plugin
  - BUILD ARTIFACTS tab, build artifact details
- Chapter 6: Use the Tekton plugin
  - CI tab, PipelineRun visualization, task cards, step details
- Chapter 7: Use the Topology plugin
  - 7.1 Enable users to use the Topology plugin (RBAC permissions)
  - 7.2 Use the Topology plugin (node graph, Details/Resources tabs)

## Source Boundaries

This source is authoritative for using RHDH 1.10 dynamic plugins to interact
with development infrastructure and tools. It covers user-facing procedures
for Argo CD, Tekton, Topology, Keycloak, JFrog Artifactory, Nexus Repository
Manager, and Ansible plugins.

It does **not** cover:
- Plugin installation or configuration (separate "Installing" guide)
- Plugin development and packaging (separate "Develop" guide)
- Plugin configuration reference or detailed pluginConfig settings
- RHDH platform administration
- Plugins not listed in this guide (e.g., GitHub, GitLab, SonarQube)

## Related Official Sources

- Red Hat Developer Hub 1.10 "Installing and viewing plugins" guide
- Red Hat Developer Hub 1.10 "Develop and deploy dynamic plugins" guide
- Red Hat Developer Hub 1.10 "Configuring plugins" guide
- Red Hat Developer Hub 1.10 "Dynamic plugins reference" guide
