---
name: rhdh-authentication
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when configuring authentication to external services, identity providers,
  and SSO in Red Hat Developer Hub: RHBK/OIDC, GitHub, Microsoft Azure, GitLab
  authentication providers; user and group provisioning from RHBK, LDAP, GitHub,
  Azure, GitLab; sign-in resolvers; session configuration; guest access; sharing
  secrets with identity providers; and custom user/group transformers. Do NOT use
  for RBAC, permission policies, or role management; use rhdh-authorization. Do
  NOT use for RHDH installation, deployment topology, or plugin management.
---

# RHDH Authentication

Use this skill to configure authentication and user provisioning in Red Hat
Developer Hub 1.10.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is product authority. This skill adapts the
official Authentication guide to this repo's GitOps and secret-handling model.

## Key Concepts

- **User provisioning** and **authentication** are independent mechanisms.
  Provisioning populates the software catalog with user/group entities from an
  IdP. Authentication validates user credentials at sign-in time.
- Provisioning is required for catalog ownership features and RBAC group-based
  access controls.
- The `dangerouslyAllowSignInWithoutUserInCatalog` resolver option bypasses the
  provisioning requirement but is NOT recommended for production.

## Supported Identity Providers

| Provider | Auth plugin key | Provisioning plugin |
|----------|----------------|---------------------|
| RHBK (OIDC) | `oidc` | `backstage-community-plugin-catalog-backend-module-keycloak-dynamic` |
| GitHub | `github` | `backstage-plugin-catalog-backend-module-github-org-dynamic` |
| Microsoft Azure | `microsoft` | `backstage-plugin-catalog-backend-module-msgraph-dynamic` |
| GitLab | `gitlab` | GitLab catalog provider (built-in config) |
| LDAP | (any auth provider) | `backstage-plugin-catalog-backend-module-ldap-dynamic` |

## Workflow

1. **Share secrets** with the chosen identity provider (Chapter 3).
2. **Enable provisioning** by configuring the catalog provider plugin and
   `catalog.providers.*` section in `app-config.yaml` (Chapter 4).
3. **Enable authentication** by configuring `auth.providers.*` and `signInPage`
   in `app-config.yaml` (Chapter 5).
4. **Configure sign-in resolvers** to match authenticated users to catalog
   entities.
5. **Disable guest access** by setting `auth.environment: production`.
6. **Verify** provisioning via console logs and authentication via the login
   page.

## Demo Policy

For this repo:

- Keep real IdP client secrets, tokens, and credentials out of Git.
- Use environment variable placeholders (`${VAR}`) in `app-config.yaml`
  examples.
- Prefer RHBK/OIDC as the primary authentication provider for demo
  environments, since MTA and other stage components already use RHBK.
- Treat LDAP provisioning as an optional add-on that works independently of
  the authentication provider.

## Critical Configuration Points

- `auth.environment`: `development` (guest enabled) or `production` (guest
  disabled).
- `auth.session.secret`: Required for OIDC provider; session support must be
  enabled.
- `signInPage`: Must match the provider key (`oidc`, `github`, `microsoft`,
  `gitlab`).
- `auth.providers.<provider>.<env>.signIn.resolvers`: Controls how
  authenticated identities map to catalog User entities.
- `catalog.providers.<providerOrg>`: Configures user/group import schedule,
  filters, and field mappings.

## Sign-In Resolvers by Provider

| Provider | Default resolver | Additional resolvers |
|----------|-----------------|---------------------|
| OIDC/RHBK | `oidcSubClaimMatchingKeycloakUserId` | `preferredUsernameMatchingUserEntityName`, `emailMatchingUserEntityProfileEmail`, `emailLocalPartMatchingUserEntityName`, `oidcLdapUuidMatchingAnnotation` |
| GitHub | `usernameMatchingUserEntityName` | `preferredUsernameMatchingUserEntityName`, `emailMatchingUserEntityProfileEmail` |
| Microsoft | `userIdMatchingUserEntityAnnotation` | `emailMatchingUserEntityAnnotation`, `emailLocalPartMatchingUserEntityName`, `emailMatchingUserEntityProfileEmail` |
| GitLab | `usernameMatchingUserEntityName` | `emailMatchingUserEntityProfileEmail` |

## Validation

- Console logs show `Read N <provider> users and M <provider> groups in X
  seconds. Committing...` on successful provisioning.
- Login page shows the configured sign-in button and guest access is
  disabled when `auth.environment: production`.
- Users appear in the Catalog under the User kind after provisioning runs.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
