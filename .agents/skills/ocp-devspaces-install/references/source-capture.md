# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Dev Spaces |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28/html-single/installation_guide/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28/html/installation_guide/index |
| Documentation category | Installation guide |
| Official guide | Installing Red Hat OpenShift Dev Spaces 3.28 |
| Capture date | 2026-07-06 |

## Captured Sections

From Installation guide:

- Chapter 1: OpenShift Dev Spaces installation overview
  - 1.1 Installation methods
  - 1.2 Deployment scenarios
- Chapter 2: Requirements
  - 2.1 Supported platforms
  - 2.2 Calculate OpenShift Dev Spaces resource requirements
  - 2.3 OpenShift Dev Spaces scalability
  - 2.4 Install the dsc management tool
  - 2.5 Permissions to install OpenShift Dev Spaces on OpenShift using CLI
  - 2.6 Permissions to install OpenShift Dev Spaces on OpenShift using web console
- Chapter 3: Install Red Hat OpenShift Dev Spaces
  - 3.1 Install Dev Spaces on OpenShift using CLI
  - 3.2 Install Dev Spaces on OpenShift using the web console
  - 3.3 Install OpenShift Dev Spaces in a restricted environment on OpenShift
  - 3.4 Set up an Ansible sample
  - 3.5 Install OpenShift Dev Spaces on OpenShift with Keycloak as external
    identity provider
  - 3.6 Use dsc to configure the CheCluster Custom Resource during installation
  - 3.7 Find the fully qualified domain name (FQDN)
- Chapter 4: Verify the OpenShift Dev Spaces installation
- Chapter 5: Next steps after installation
- Chapter 6: Uninstall OpenShift Dev Spaces

## Source Boundaries

This skill captures the installation lifecycle from the official Installation
guide: requirements, supported platforms, dsc CLI tool, RBAC permissions,
standard CLI and web console installation, restricted environment installation,
external identity provider (Keycloak) integration, CheCluster CR patching
during install, installation verification, and uninstallation.

It does not capture:

- OpenShift Dev Spaces concepts and architecture (separate guide)
- Administration and CheCluster CR field reference (Administration guide)
- User workflows, workspaces, devfiles, IDEs (User guide)
- Release notes and known issues (Release notes)
- Scalability deep-dives beyond the requirements chapter overview

## API Versions Documented

| Resource | apiVersion |
|----------|-----------|
| CheCluster | `org.eclipse.che/v2` |
| ClusterRole (CLI permissions) | `rbac.authorization.k8s.io/v1` |
| ClusterRole (web console permissions) | `rbac.authorization.k8s.io/v1` |
| DevWorkspaceOperatorConfig | `controller.devfile.io/v1alpha1` |
| OLMConfig | `operators.coreos.com/v1` |

## Related Official Sources To Add Later

- Red Hat OpenShift Dev Spaces 3.28 Understanding documentation
- Red Hat OpenShift Dev Spaces 3.28 Administration guide
- Red Hat OpenShift Dev Spaces 3.28 User guide
- Red Hat OpenShift Dev Spaces 3.28 Release notes
