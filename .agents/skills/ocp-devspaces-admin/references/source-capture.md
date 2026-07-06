# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Dev Spaces |
| Product version | 3.28 |
| Documentation category | Usage and Administration |
| Official guide | Administration Guide |
| Source URL (single-page) | https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28/html-single/administration_guide/index |
| Source URL (multi-page) | https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28/html/administration_guide/index |
| Capture date | 2026-07-06 |

## Captured Sections

The Administration Guide contains 21 chapters:

1. Security best practices — project isolation, RBAC, SCC, quotas, network
   policies, secrets, disconnected environments, extension management
2. Configure the CheCluster Custom Resource — CR structure, CLI editing, full
   fields reference (`apiVersion: org.eclipse.che/v2`)
3. Configure projects — namespace templates, pre-provisioning, user namespace
   configuration
4. Configure server components — mounting Secrets/ConfigMaps as files, subPaths,
   environment variables; advanced server configuration
5. Configure autoscaling — HPA for Dev Spaces operands, machine autoscaler
   integration
6. Configure workspaces globally — workspace limits (per-user, per-cluster,
   concurrent), self-signed Git certs, nodeSelector, allowed URLs, container
   run capabilities
7. Cache images for faster workspace start — Kubernetes Image Puller
   configuration
8. Configure observability — telemetry plugins, server logging, log levels, HTTP
   traffic logging, `dsc` log collection, DevWorkspace Operator metrics,
   Prometheus ServiceMonitor, web console dashboards, server JVM metrics
9. Configure networking — network policies, hostname, TLS certificate import,
   Router Sharding, workspace endpoint base domain, proxy configuration
10. Configure storage — storage requirements (RWX for per-user), storage
    classes, storage strategies (per-user/per-workspace/ephemeral), storage
    sizes, persistent user home
11. Configure dashboard — getting started samples, editor definitions, default
    editor, branding images
12. Manage identities and authorizations — cluster roles for users, advanced
    authorization (allow/deny users/groups), GDPR user data removal
13. Configure OAuth for Git providers — GitHub App/OAuth, GitLab, Bitbucket
    Server/Cloud, Microsoft Entra ID, token refresh
14. Configure fuse-overlayfs — `/dev/fuse` access, fuse-overlayfs for all
    workspaces
15. Back up workspaces — integrated OpenShift registry, OCI-compatible registry
16. Managing IDE extensions — Open VSX registry, extension management, internal
    registry deployment
17. Configure Visual Studio Code - Open Source — multiroot workspaces, trusted
    extensions, default extensions, ConfigMap-based configuration
18. Use the OpenShift Dev Spaces server API
19. Upgrade using the web console — update approval strategy, web console
    upgrade, DevWorkspace Operator repair
20. Upgrade using the CLI management tool — CLI upgrade, restricted environment
    upgrade
21. Troubleshooting administration — workspace startup failures (pod scheduling,
    image pull, DevWorkspace, resource quota errors), OAuth configuration errors

## Source Boundaries

This skill captures the Administration Guide content. It does not cover:

- Dev Spaces conceptual overview (see Discover OpenShift Dev Spaces guide)
- Installation procedures (see Install OpenShift Dev Spaces guide)
- User-facing workspace workflows (see User Guide)
- Release notes and known issues (see version-specific release notes)

The CheCluster CR fields reference table in Chapter 2 is extensive. The
extraction file captures the most important fields grouped by administration
area. For the complete field list, use `oc explain checluster.spec --recursive`
on the target cluster.

## API Versions Documented

| Resource | API Version |
|----------|-------------|
| CheCluster | `org.eclipse.che/v2` |
| NetworkPolicy | `networking.k8s.io/v1` |
| ServiceMonitor | `monitoring.coreos.com/v1` |
| HorizontalPodAutoscaler | `autoscaling/v2` |
| ClusterRole / ClusterRoleBinding | `rbac.authorization.k8s.io/v1` |
| Role / RoleBinding | `rbac.authorization.k8s.io/v1` |

## Related Official Sources To Add Later

- Red Hat OpenShift Dev Spaces 3.28 Install Guide:
  https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28/html/install_openshift_dev_spaces
- Red Hat OpenShift Dev Spaces 3.28 User Guide:
  https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28/html/user_guide
- Red Hat OpenShift Dev Spaces 3.28 Discover Guide:
  https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28/html/discover_openshift_dev_spaces
- Red Hat OpenShift Dev Spaces 3.28 Release Notes:
  https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28/html/3.28.0_release_notes_and_known_issues
- Red Hat OpenShift Dev Spaces product landing page:
  https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28
