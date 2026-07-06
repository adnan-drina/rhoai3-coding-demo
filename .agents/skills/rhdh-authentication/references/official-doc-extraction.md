# Official Doc Extraction

Use this reference when authoring or reviewing RHDH authentication and user
provisioning content.

## Component Purpose

Authentication in Red Hat Developer Hub enables users to sign in using
credentials from an external identity provider (RHBK, GitHub, Microsoft Azure,
GitLab) and provision user and group data to the software catalog.

User provisioning and authentication are independent mechanisms:
- **Provisioning** imports user/group entities from an IdP into the catalog
  asynchronously via catalog provider plugins.
- **Authentication** validates credentials at sign-in time and resolves the
  authenticated identity to a catalog User entity.

## Architecture Overview

1. User accesses RHDH and is redirected to the configured auth provider.
2. The external IdP authenticates the user.
3. The RHDH auth plugin processes the IdP response, resolves the identity via
   sign-in resolvers, and establishes a session.
4. Separately, catalog provider plugins periodically query the IdP and
   create/update User and Group entities in the catalog.

## Guest Access

| Setting | Effect |
|---------|--------|
| `auth.environment: development` | Guest login enabled on login page |
| `auth.environment: production` | Guest login disabled |

Guest access is for trial/non-production environments only.

## Secret Sharing Requirements by Provider

### RHBK (Chapter 3.1)

Required secrets:
- `KEYCLOAK_CLIENT_ID` — Client ID from RHBK
- `KEYCLOAK_CLIENT_SECRET` — Client Secret from RHBK
- `KEYCLOAK_BASE_URL` — RHBK realm base URL (e.g., `https://<rhbk>/realms/<realm>`)
- `KEYCLOAK_REALM` — Realm name for provisioning
- `KEYCLOAK_LOGIN_REALM` — Realm name for authentication
- `SESSION_SECRET` — Session secret key

RHBK client configuration:
- Valid redirect URI: `https://<rhdh_domain>/api/auth/oidc/handler/frame`

### GitHub (Chapter 3.3)

Two separate GitHub Apps (principle of least privilege):
- **Integration App**: `GITHUB_APP_APP_ID`, `GITHUB_APP_CLIENT_ID_INTEGRATION`,
  `GITHUB_APP_CLIENT_SECRET_INTEGRATION`, `GITHUB_APP_PRIVATE_KEY`
- **Authentication App**: `GITHUB_APP_CLIENT_ID`, `GITHUB_APP_CLIENT_SECRET`
- Shared: `GITHUB_URL`, `GITHUB_ORG`

### Microsoft Azure (Chapter 3.4)

Required secrets:
- `MICROSOFT_TENANT_ID` — Directory (tenant) ID
- `MICROSOFT_CLIENT_ID` — Application (client) ID
- `MICROSOFT_CLIENT_SECRET` — Application (client) secret

Azure App required permissions:
- Application: `GroupMember.Read.All`, `User.Read.All`
- Delegated: `User.Read`, `email`, `offline_access`, `openid`, `profile`

### GitLab (Chapter 3.5)

Required secrets:
- `GITLAB_HOST`, `GITLAB_CLIENT_ID`, `GITLAB_CLIENT_SECRET`, `GITLAB_TOKEN`,
  `GITLAB_URL`, `GITLAB_PARENT_ORG`

### LDAP (Chapter 3.2)

Required secrets:
- `LDAP_SECRET` — LDAP bind password
- Optional: `ldap_certs.pem`, `ldap_keys.pem` for `ldaps://`

## User Provisioning Configuration

### RHBK Catalog Provider (Chapter 4.1)

Plugin: `backstage-community-plugin-catalog-backend-module-keycloak-dynamic`

```yaml
catalog:
  providers:
    keycloakOrg:
      default:
        baseUrl: ${KEYCLOAK_BASE_URL}
        clientId: ${KEYCLOAK_CLIENT_ID}
        clientSecret: ${KEYCLOAK_CLIENT_SECRET}
        realm: ${KEYCLOAK_REALM}
        loginRealm: ${KEYCLOAK_LOGIN_REALM}
        schedule:
          frequency: { hours: 1 }
          timeout: { minutes: 50 }
          initialDelay: { seconds: 15 }
```

### LDAP Catalog Provider (Chapter 4.2)

Plugin: `backstage-plugin-catalog-backend-module-ldap-dynamic`

```yaml
catalog:
  providers:
    ldapOrg:
      default:
        target: ldaps://ds.example.net
        bind:
          dn: cn=admin,ou=Users,dc=rhdh
          secret: ${LDAP_SECRET}
        users:
          - dn: OU=Users,OU=RHDH Local,DC=rhdh,DC=test
            options:
              filter: (uid=*)
        groups:
          - dn: OU=Groups,OU=RHDH Local,DC=rhdh,DC=test
        schedule:
          frequency: PT1H
          timeout: PT15M
```

LDAP provisioning works with any authentication provider.

### GitHub Catalog Provider (Chapter 4.3)

Plugin: `backstage-plugin-catalog-backend-module-github-org-dynamic`

```yaml
catalog:
  providers:
    githubOrg:
      id: githuborg
      githubUrl: "${GITHUB_URL}"
      orgs: ["${GITHUB_ORG}"]
      schedule:
        frequency: { minutes: 30 }
        initialDelay: { seconds: 15 }
        timeout: { minutes: 15 }
integrations:
  github:
    - host: "${GITHUB_URL}"
      apps:
        - appId: ${GITHUB_APP_APP_ID}
          clientId: ${GITHUB_APP_CLIENT_ID_INTEGRATION}
          clientSecret: ${GITHUB_APP_CLIENT_SECRET_INTEGRATION}
          privateKey: |
            ${GITHUB_APP_PRIVATE_KEY}
```

### Microsoft Graph Catalog Provider (Chapter 4.4)

Plugin: `backstage-plugin-catalog-backend-module-msgraph-dynamic`

```yaml
catalog:
  providers:
    microsoftGraphOrg:
      providerId:
        target: https://graph.microsoft.com/v1.0
        tenantId: ${MICROSOFT_TENANT_ID}
        clientId: ${MICROSOFT_CLIENT_ID}
        clientSecret: ${MICROSOFT_CLIENT_SECRET}
        schedule:
          frequency: { hours: 1 }
          timeout: { minutes: 50 }
          initialDelay: { minutes: 50 }
```

### GitLab Catalog Provider (Chapter 4.5)

```yaml
catalog:
  providers:
    gitlab:
      default:
        host: ${GITLAB_HOST}
        orgEnabled: true
        group: ${GITLAB_PARENT_ORG}
        schedule:
          frequency: { minutes: 50 }
          timeout: { minutes: 50 }
integrations:
  gitlab:
    - host: ${GITLAB_HOST}
      token: ${GITLAB_TOKEN}
```

## Authentication Provider Configuration

### OIDC/RHBK (Chapter 5.1)

```yaml
auth:
  environment: production
  session:
    secret: ${SESSION_SECRET}
  providers:
    oidc:
      production:
        metadataUrl: ${KEYCLOAK_BASE_URL}
        clientId: ${KEYCLOAK_CLIENT_ID}
        clientSecret: ${KEYCLOAK_CLIENT_SECRET}
        prompt: auto
signInPage: oidc
```

Key fields:
- `prompt: auto` — allows IdP to determine whether to prompt for credentials
- `signIn.resolvers` — list of resolvers tried in order
- `sessionDuration` — user session lifespan
- `backstageTokenExpiration` — short-term token validity (10min–24h)

### GitHub (Chapter 5.3)

```yaml
auth:
  environment: production
  providers:
    github:
      production:
        clientId: ${GITHUB_APP_CLIENT_ID}
        clientSecret: ${GITHUB_APP_CLIENT_SECRET}
signInPage: github
```

### Microsoft Azure (Chapter 5.4)

```yaml
auth:
  environment: production
  providers:
    microsoft:
      production:
        clientId: ${MICROSOFT_CLIENT_ID}
        clientSecret: ${MICROSOFT_CLIENT_SECRET}
        tenantId: ${MICROSOFT_TENANT_ID}
signInPage: microsoft
```

### GitLab (Chapter 5.5)

```yaml
auth:
  environment: production
  providers:
    gitlab:
      production:
        clientId: ${GITLAB_CLIENT_ID}
        clientSecret: ${GITLAB_CLIENT_SECRET}
signInPage: gitlab
```

## Verification Patterns

Successful provisioning log pattern:
```
Read N <Provider> users and M <Provider> groups in X.X seconds. Committing...
Committed N <Provider> users and M <Provider> groups in X.X seconds.
```

Login page verification:
1. Navigate to RHDH login page.
2. Confirm sign-in button shows provider name.
3. Confirm guest login is disabled when `auth.environment: production`.

## Dynamic Plugins Required

| Provider | Plugin package |
|----------|---------------|
| RHBK provisioning | `./dynamic-plugins/dist/backstage-community-plugin-catalog-backend-module-keycloak-dynamic` |
| LDAP provisioning | `./dynamic-plugins/dist/backstage-plugin-catalog-backend-module-ldap-dynamic` |
| GitHub provisioning | `./dynamic-plugins/dist/backstage-plugin-catalog-backend-module-github-org-dynamic` |
| Azure provisioning | `./dynamic-plugins/dist/backstage-plugin-catalog-backend-module-msgraph-dynamic` |

Enable in `dynamic-plugins.yaml`:
```yaml
plugins:
  - package: '<plugin-path>'
    disabled: false
```

## Security Considerations

- In production, configure only ONE sign-in resolver per provider.
- Never enable `dangerouslyAllowSignInWithoutUserInCatalog` in production.
- Use `ldaps://` with proper certificates for LDAP connections.
- Enable refresh token rotation in RHBK to prevent older token misuse.
- Use separate GitHub Apps for integration vs authentication (least privilege).
