# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Configuring dynamic plugins |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/configuring_dynamic_plugins/index |
| Documentation category | Extend / Configuring dynamic plugins |
| Retrieved date | 2026-07-06 |
| Sections used | Preface; 1 Installing Ansible plugins; 2 Install and configure Argo CD (2.1 Enable, 2.2 Rollouts); 3 Enable and configure JFrog (3.1 Enable, 3.2 Configure); 4 Enable and configure Nexus Repository Manager (4.1 Enable, 4.2 Configure); 5 Enable the Tekton plugin; 6 Install the Topology plugin (6.1 Install, 6.2 Configure, 6.3 Labels and annotations); 7 Bulk importing (7.1-7.9 Repository visibility, enabling, GitHub/GitLab import, audit logs, Scaffolder, Orchestrator); 8 ServiceNow custom actions (8.1 Entity linking, 8.2 Enable, 8.3 Supported actions); 9 Kubernetes custom actions (9.1 Enable, 9.2 Use, 9.3 Templates, 9.4 Supported actions); 10 GitHub Events Module (10.1 Configure); 11 Override Core Backend Service Configuration |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/dynamic_plugins_reference/index | Plugin names, versions, support tiers, and required variables |
| https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/helm_chart_configuration_reference/index | Helm Chart values for deployment configuration |
| https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/installing_and_viewing_plugins_in_red_hat_developer_hub/index | Plugin installation and viewing context |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHDH baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |

## Source Boundaries

- Product authority: the official Red Hat Developer Hub 1.10 configuring
  dynamic plugins guide above.
- This skill defines plugin configuration procedures, app-config fragments,
  annotations, ClusterRole requirements, and integration options.
- It does not define the catalog of available plugins or their support tiers.
  Use `rhdh-dynamic-plugins-reference` for that.
- It does not define Helm Chart values. Use `rhdh-helm-reference` for that.
