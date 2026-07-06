# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product | Red Hat Developer Hub |
| Product version | 1.10 |
| Book title | Authentication in Red Hat Developer Hub |
| Book URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/authentication_in_red_hat_developer_hub/index |
| Documentation category | Control access |
| Retrieved date | 2026-07-06 |
| Sections used | Ch 1: Understand authentication and user provisioning; Ch 2: Enable or disable Guest login; Ch 3: Share a secret with your identity provider (RHBK, LDAP, GitHub, Azure, GitLab); Ch 4: Import users and groups (RHBK, LDAP, GitHub, Azure, GitLab + custom transformers); Ch 5: Enable authentication with your identity provider (RHBK/OIDC, GitHub, Azure, GitLab); Ch 5.2: Match users by LDAP UUID with RHBK |

## Supporting Red Hat Sources

| Source | Role |
|--------|------|
| Red Hat Developer Hub 1.10 product documentation | Primary product authority |
| Red Hat Build of Keycloak documentation | Supplemental for RHBK realm/client configuration |
| Dynamic plugins reference for RHDH 1.10 | Plugin package names and version compatibility |

## Source Boundaries

- Product configuration truth: official RHDH 1.10 Authentication guide above.
- Identity provider administration (RHBK realm setup, GitHub App creation,
  Azure App registration, GitLab OAuth2 App creation): covered as procedures
  in the official guide but provider-side admin details are supplemental.
- Demo policy: no real IdP client secrets, tokens, or credentials are
  committed to this repository.
- Verification: console log patterns, login page behavior, catalog entity
  checks.
- Not authoritative: upstream Backstage community plugin documentation unless
  explicitly referenced by the Red Hat guide.

## Unresolved Or Environment-Specific Items

- Exact RHBK realm name, client ID, and issuer URL for the demo environment.
  Verification: obtain from the active RHBK instance or stage 070 MTA
  Keycloak configuration.
- Final GitOps secret mechanism for IdP client secrets.
  Verification: align with the project secret pattern when active.
- Whether LDAP provisioning is needed alongside RHBK authentication.
  Verification: determine based on the demo user directory requirements.
