# Official Doc Extraction

Use this extraction to keep Red Hat Developer Hub 1.10 setup content grounded in
official Red Hat sources. When implementation needs exact CR fields, verify the
active cluster schema with `oc explain` or `oc get crd` before authoring GitOps
manifests.

## Production Readiness Checklist

Default configuration runs a minimal feature set without external service
connections. Production requires:

- **Resiliency**: external PostgreSQL, high-availability (replicas >= 2)
- **Performance**: external Redis cache for plugin and TechDocs assets
- **Security**: TLS to external services, user provisioning, authentication,
  RBAC enabled via Web UI
- **Adaptation**: GitHub repository discovery, appearance customization

## Operator Installation

- Install via OperatorHub / software catalog in OCP web console.
- Update channels: `fast` (all updates) or `fast-1.10` (z-stream only).
- Installation mode: "All namespaces on the cluster" (required; specific
  namespace not currently supported).
- Recommended namespace: `rhdh-operator` (dedicated for security and lifecycle
  control).
- Supported OCP versions: 4.18 through 4.21.
- Architecture: AMD64 / Intel 64 (`x86_64`).
- Direct upgrades from any earlier version are supported; review release notes
  for skipped versions.

## External Services

### PostgreSQL

Required for data persistence. Use an external database for resiliency and
disaster recovery. Collect: host, port, username, password, TLS certificates
(`postgres-crt.pem`, `postgres-ca.pem`, `postgres-key.key`).

### GitHub App

Prefer GitHub App over OAuth for fine-grained permissions, short-lived tokens,
and per-repository access control.

**Integration App** (Developer Hub to GitHub):
- Permissions: Contents (Read-only), Commit statuses (Read-only), Members
  (Read-only)
- Secrets: `GITHUB_APP_APP_ID`, `GITHUB_APP_CLIENT_ID_INTEGRATION`,
  `GITHUB_APP_CLIENT_SECRET_INTEGRATION`, `GITHUB_APP_PRIVATE_KEY`

**Authentication App** (user to Developer Hub):
- Permissions: Members (Read-only)
- Authorization callback URL:
  `https://<domain>/api/auth/github/handler/frame`
- Secrets: `GITHUB_APP_CLIENT_ID`, `GITHUB_APP_CLIENT_SECRET`

### Identity Provider Credentials

RHBK secrets: `KEYCLOAK_CLIENT_ID`, `KEYCLOAK_CLIENT_SECRET`,
`KEYCLOAK_BASE_URL`, `KEYCLOAK_REALM`, `KEYCLOAK_LOGIN_REALM`,
`SESSION_SECRET`.

Azure secrets: `MICROSOFT_TENANT_ID`, `MICROSOFT_CLIENT_ID`,
`MICROSOFT_CLIENT_SECRET`.

## Custom Configuration Provisioning

### app-config.yaml

Main RHDH configuration. Key sections:

```yaml
app:
  title: Red Hat Developer Hub
  baseUrl: https://<my_developer_hub_domain>
backend:
  auth:
    externalAccess:
      - type: legacy
        options:
          subject: legacy-default-config
          secret: "${BACKEND_SECRET}"
  baseUrl: https://<my_developer_hub_domain>
  cors:
    origin: https://<my_developer_hub_domain>
```

### dynamic-plugins.yaml

Plugin enablement with includes:

```yaml
includes:
  - dynamic-plugins.default.yaml
plugins:
  - package: ./dynamic-plugins/dist/backstage-plugin-catalog-backend-module-github
    disabled: false
  - package: ./dynamic-plugins/dist/backstage-community-plugin-rbac
    disabled: false
```

### Provisioning to OCP

```bash
oc create namespace my-rhdh-project
oc create configmap my-rhdh-app-config \
  --from-file=app-config.yaml -n my-rhdh-project
oc create configmap dynamic-plugins-rhdh \
  --from-file=dynamic-plugins.yaml -n my-rhdh-project
oc create secret generic my-rhdh-secrets \
  --from-file=secrets.txt -n my-rhdh-project
```

## Authentication Configuration

### User Provisioning vs Authentication

User provisioning and authentication are independent mechanisms:
- **Provisioning**: catalog provider plugins query the IdP asynchronously to
  create/update user and group entities in the software catalog.
- **Authentication**: redirects users to the configured IdP; on success,
  resolves identity in the catalog and establishes a session.

One-way sync model: changes flow from IdP to catalog only.

### Guest Access

- Enable: `auth.environment: development` (non-production only)
- Disable: `auth.environment: production`

### RHBK (OIDC)

Session support required:

```yaml
auth:
  session:
    secret: ${SESSION_SECRET}
  environment: production
  providers:
    oidc:
      production:
        metadataUrl: ${KEYCLOAK_BASE_URL}
        clientId: ${KEYCLOAK_CLIENT_ID}
        clientSecret: ${KEYCLOAK_CLIENT_SECRET}
        prompt: auto
signInPage: oidc
```

Keycloak catalog provider plugin:
`backstage-community-plugin-catalog-backend-module-keycloak-dynamic`

Sign-in resolvers: `oidcSubClaimMatchingKeycloakUserId` (recommended),
`oidcLdapUuidMatchingAnnotation`, `emailLocalPartMatchingUserEntityName`,
`emailMatchingUserEntityProfileEmail`,
`preferredUsernameMatchingUserEntityName`.

### GitHub

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

GitHub org catalog provider plugin:
`backstage-plugin-catalog-backend-module-github-org-dynamic`

Sign-in resolvers: `usernameMatchingUserEntityName` (default),
`preferredUsernameMatchingUserEntityName`,
`emailMatchingUserEntityProfileEmail`.

### Microsoft Azure

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

Microsoft Graph catalog provider plugin:
`backstage-plugin-catalog-backend-module-msgraph-dynamic`

Azure permissions: Application (`GroupMember.Read.All`, `User.Read.All`),
Delegated (`User.Read`, `email`, `offline_access`, `openid`, `profile`).

Sign-in resolvers: `userIdMatchingUserEntityAnnotation` (default),
`emailMatchingUserEntityAnnotation`,
`emailLocalPartMatchingUserEntityName`,
`emailMatchingUserEntityProfileEmail`.

## Backstage CR

```yaml
apiVersion: rhdh.redhat.com/v1alpha5
kind: Backstage
metadata:
  name: <my-rhdh-custom-resource>
spec:
  application:
    appConfig:
      mountPath: /opt/app-root/src
      configMaps:
        - name: my-rhdh-app-config
        - name: rbac-policies
    dynamicPluginsConfigMapName: dynamic-plugins-rhdh
    extraEnvs:
      envs:
        - name: HTTP_PROXY
          value: 'http://10.10.10.105:3128'
      secrets:
        - name: my-rhdh-secrets
    extraFiles:
      mountPath: /opt/app-root/src
      secrets:
        - name: my-rhdh-database-certificates-secrets
          key: postgres-crt.pem, postgres-ca.pem, postgres-key.key
    replicas: 2
  database:
    enableLocalDb: false
```

Apply: `oc apply -f my-rhdh-custom-resource.yaml -n my-rhdh-project`

## RBAC via Web UI

Policy administrators manage roles through Administration > RBAC tab.

Required permissions:
- Create: `policy.entity.create`, `policy.entity.read`, `catalog.entity.read`
- Edit: `policy.entity.update`, `policy.entity.read`, `catalog.entity.read`
- Delete: `policy.entity.delete`, `policy.entity.read`, `catalog.entity.read`

Policies from `policy.csv` or ConfigMap cannot be edited or deleted via Web UI.

## Theme Switching

Settings > Appearance panel: Light, Dark, or Auto (matches system preference).
