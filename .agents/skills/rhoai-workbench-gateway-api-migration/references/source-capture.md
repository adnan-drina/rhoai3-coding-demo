# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Configure user access, storage, and telemetry in OpenShift AI |
| Chapter title | Chapter 4. Introducing the Kubernetes Gateway API for custom image migration |
| Chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/introducing-kubernetes-gateway-api_resource-mgmt |
| Documentation category | Administer / Managing resources |
| Retrieved date | 2026-06-10 |
| Sections used | 4.1 Understanding path-based routing; 4.2 Migrating your custom workbench images to the Kubernetes Gateway API; 4.3 Migrating your custom workbench images to the Kubernetes Gateway API using NGINX |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/importing-a-custom-workbench-image_resource-mgmt | Dashboard import of custom workbench images |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/creating-custom-workbench-images | Custom workbench image build and compatibility guidance |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/creating_a_workbench/index | Workbench creation with ImageStream and Notebook resources |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-workbenches-custom-images/SKILL.md` | Broader custom workbench image build and Notebook behavior |
| `.agents/skills/rhoai-workbench-image-import/SKILL.md` | Dashboard import workflow for existing custom images |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Managing resources
  chapter above.
- This chapter defines custom workbench application compatibility with Gateway
  API path-based routing, not Gateway API installation or cluster ingress
  design.
- NGINX is a compatibility pattern for applications that cannot be configured
  with a base path.
- Verification requires a running custom workbench pod; follow the OpenShift
  safety guard before live `oc` commands.

## Unresolved Or Environment-Specific Items

- Exact Gateway Controller namespace and log selector in a target cluster.
  Verification: identify the active controller deployment before documenting a
  concrete log command.
- The custom workbench application framework and base-path setting.
  Verification: record per image in image build docs.
- Whether NGINX is needed.
  Verification: prefer native base-path support and use NGINX only if the
  application cannot be changed.
