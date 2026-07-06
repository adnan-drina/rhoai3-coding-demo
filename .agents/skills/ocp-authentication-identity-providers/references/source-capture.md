# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Container Platform |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Authentication and authorization |
| Official guide | Authentication and authorization |
| Source URL | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/authentication_and_authorization/index |
| Identity provider chapter | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/authentication_and_authorization/understanding-identity-provider |
| Configuring identity providers chapter | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/authentication_and_authorization/configuring-identity-providers |
| Direct external OIDC chapter | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/authentication_and_authorization/external-auth |
| Capture date | 2026-06-10 |

## Captured Sections

- Understanding identity provider configuration
- Supported identity providers
- Identity provider parameters and `mappingMethod`
- Sample `OAuth` identity provider custom resource
- Configuring identity providers, including htpasswd development posture
- Enabling direct authentication with an external OIDC identity provider
- Removing the `kubeadmin` user
- Syncing LDAP groups

## Source Boundaries

This source is authoritative for OpenShift authentication and identity-provider
configuration. It does not define RHOAI dashboard access policy, RHOAI user
roles, RHOAI administrator group selection, or project-specific demo users.

Direct external OIDC authentication changes the cluster authentication model.
Before authoring or applying it, confirm the exact OCP version, current OAuth
state, external IdP readiness, and a long-lived cluster-admin recovery path.

## Related Official Sources

- OpenShift RBAC and SCC guidance belongs to
  `ocp-security-rbac-scc`.
- OpenShift AI user and group access belongs to
  `rhoai-users-groups-access` and `rhoai-access-group-selection`.
