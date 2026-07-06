# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Dev Spaces |
| Version | 3.28 |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Discover |
| Official guide | Discover OpenShift Dev Spaces |
| Source URL (single-page) | https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28/html-single/discover_openshift_dev_spaces/index |
| Source URL (multi-page) | https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28/html/discover_openshift_dev_spaces/index |
| Architecture chapter URL | https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28/html/discover_openshift_dev_spaces/assembly_architecture_discover |
| Capture date | 2026-07-06 |

## Captured Sections

From "Discover OpenShift Dev Spaces":

- Preface (evaluation context)
- Chapter 1: What is OpenShift Dev Spaces?
  - Core goals (onboarding, consistency, security)
  - What OpenShift Dev Spaces provides (workspaces, IDEs, extensibility, enterprise integration)
  - Workspace model (source + dependencies + IDE as pod)
- Chapter 2: What problems does OpenShift Dev Spaces solve?
  - Environment inconsistency
  - Slow developer onboarding
  - Security and credential management
  - Environment drift over time
  - Resource constraints on developer laptops
  - Compliance in regulated environments
- Chapter 3: Who is OpenShift Dev Spaces for?
  - Platform administrators
  - Developers
  - Team sizes and deployment models
- Chapter 4: When to use OpenShift Dev Spaces
  - Teams that benefit
  - Enterprise capabilities (on-premises, air-gapped, RBAC, devfile standard)
  - Developer requirements (browser only)
- Chapter 5: How OpenShift Dev Spaces works
  - Component overview (server components, DWO, user workspaces)
  - Operator and lifecycle management (CheCluster CRD/CR)
  - Dev Workspace Operator and workspace pods
  - Custom Resources overview (DevWorkspace, DevWorkspaceTemplate, DevWorkspaceOperatorConfig, DevWorkspaceRouting)
  - DWO operands (controller-manager, webhook-server)
  - Gateway and request routing (Traefik, OAuth2 Proxy, kube-rbac-proxy)
  - Dashboard and workspace management (startup sequence)
  - Server and namespace provisioning
  - Plug-in registry and editor definitions
  - What developers get in a workspace (pod contents, PV, devfile v2)

## Source Boundaries

This skill covers the "Discover OpenShift Dev Spaces" guide only. It provides
conceptual understanding of architecture, components, DevWorkspace CRDs, and
the workspace model. It does not cover:

- Installation and configuration (separate guide)
- Administration and CheCluster CR field reference (separate guide)
- User guide and workspace workflows (separate guide)
- Release notes and known issues (separate guide)
- Devfile authoring specifics beyond conceptual overview

## API Versions Documented

| Resource | API Version |
|----------|-------------|
| CheCluster | `org.eclipse.che/v2` |
| DevWorkspace | `workspace.devfile.io/v1alpha2` |
| DevWorkspaceTemplate | `workspace.devfile.io/v1alpha2` |
| DevWorkspaceOperatorConfig | `controller.devfile.io/v1alpha1` |
| DevWorkspaceRouting | `controller.devfile.io/v1alpha1` |
| Subscription (DWO) | `operators.coreos.com/v1alpha1` |

## Related Official Sources To Add Later

- Installation guide (https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28/html-single/installation_guide/index)
- Administration guide (https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28/html-single/administration_guide/index)
- User guide (https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28/html-single/user_guide/index)
- Release notes (https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28/html-single/release_notes_and_known_issues/index)
