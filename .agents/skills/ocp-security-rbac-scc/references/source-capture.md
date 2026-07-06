# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Container Platform |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Authentication and authorization, Security and compliance |
| Official guide | Authentication and authorization |
| Source URL | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/authentication_and_authorization/index |
| RBAC chapter | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/authentication_and_authorization/using-rbac |
| SCC chapter | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/authentication_and_authorization/managing-pod-security-policies |
| Security and compliance index | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/security_and_compliance/index |
| Capture date | 2026-06-10 |

## Captured Sections

- Using RBAC to define and apply permissions
- Role and binding concepts
- Service account concepts
- Managing security context constraints
- Default SCCs and custom SCC guidance
- SCC command reference
- Pod security admission relationship

## Source Boundaries

This skill covers OpenShift authorization and pod admission controls. It does
not configure identity providers, direct OIDC, LDAP group sync, RHOAI dashboard
group selection, or application-specific security frameworks.

Cluster-admin, privileged SCC, host access, and broad cluster-scoped grants are
high-risk choices. They must be tied to official product requirements or
documented demo constraints.
