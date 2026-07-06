# Official Doc Extraction

Use this extraction to keep OpenShift authentication guidance grounded in the
official OCP source. Verify exact fields with `oc explain` or the active
cluster CRD before authoring manifests.

## Identity Provider Model

OpenShift authentication is configured through the cluster-scoped `OAuth`
resource in the `config.openshift.io/v1` API group. Identity providers are
listed under `spec.identityProviders`.

The provider configuration includes:

- a provider `name`
- a `mappingMethod` that controls how provider identities map to OpenShift
  `User` objects
- a provider `type`
- provider-specific configuration and referenced secrets or config maps

When changing identity providers, map identities carefully so existing users do
not lose expected access. Use the official provider chapter for the supported
provider-specific fields.

## Provider Posture

Official OCP documentation covers multiple provider types, including htpasswd,
Keystone, LDAP, basic authentication, request-header, GitHub, GitLab, Google,
and OpenID Connect.

For this demo:

- Prefer enterprise identity providers when the environment already has them.
- Use htpasswd only for development or constrained demo environments, and label
  that choice clearly.
- Keep identity-provider secrets in `openshift-config`; never commit generated
  password files, private keys, or token material.

## Direct External OIDC

Direct external OIDC authentication lets OpenShift use an external OIDC
provider directly for token issuance instead of the built-in OpenShift OAuth
server.

Before enabling it:

- back up current users, groups, OAuth clients, and identity-provider
  configuration
- ensure a long-lived cluster-admin recovery login method exists
- confirm only one direct OIDC provider is required
- confirm workloads and automation do not depend on OAuth or user APIs that
  become unavailable under direct authentication

For the first clean-slate demo implementation, prefer using the cluster's
existing authentication setup unless the user explicitly asks to include direct
OIDC in GitOps.

## Group Integration

OpenShift users and groups are the source substrate for RHOAI access. LDAP
group sync can be used when the enterprise identity design requires OpenShift
groups to reflect an external LDAP source. RHOAI dashboard group selection is a
separate RHOAI workflow and must not be inferred from OpenShift identity
provider configuration alone.

## Validation Signals

Healthy authentication work should verify:

- `OAuth` cluster resource shape and provider references
- referenced secrets and config maps in `openshift-config`
- current users, identities, and groups
- login behavior for at least one cluster-admin and one ordinary user
- RHOAI group names after authentication changes, if RHOAI access depends on
  those groups

Do not run live authentication changes without the repository OpenShift safety
guard and explicit confirmation of the target cluster.
