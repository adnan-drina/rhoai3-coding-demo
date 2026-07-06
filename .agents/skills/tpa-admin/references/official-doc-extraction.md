# Official Doc Extraction

Use this extraction to keep RHTPA administration content grounded in official
Red Hat sources. When implementation needs exact Helm values or CR fields,
verify against the actual chart and cluster state before authoring manifests.

## Product Overview

Red Hat Trusted Profile Analyzer (RHTPA) is part of the Red Hat Trusted
Software Supply Chain suite. It provides a centralized, unified "Single Pane
of Glass" (SPOG) view of application security profiles. The underlying RESTful
APIs power the RHTPA web console and notification services.

Exhort is the RHTPA backend endpoint that receives API requests to retrieve
analysis data including package dependencies and vulnerabilities. The Red Hat
Dependency Analytics (RHDA) IDE plugin uses this endpoint.

RHTPA aggregates and analyzes:
- **SBOMs**: CycloneDX and SPDX format; stores, indexes, and queries
- **VEX**: Vulnerability Exploitability eXchange security advisories
- **CVE**: Common Vulnerabilities and Exposures with CVSS scoring (1-10)

## Data Importers

### Available Sources

| Importer | Default State |
|----------|---------------|
| Red Hat CSAFs | Disabled |
| Red Hat SBOMs | Disabled |
| CVE list v5 | Enabled |
| GitHub advisory database | Enabled |
| Quay | Disabled |

### Scheduling

Default schedule: 1 day (24 hours from last successful completion).

### Resource Requirements

Default resource request per importer and API server deployment:
- CPU: 1
- Memory: 8 GB RAM
- Limits: none by default

Pods may fail to start or remain Pending if computing resources are inadequate.

## Creating SBOMs with Syft

> **Technology Preview**: Syft binary is not supported with Red Hat production
> SLAs.

### From Container Images

CycloneDX:

```bash
syft IMAGE_PATH -o cyclonedx-json@1.5
syft registry:example.io/hello-world:latest -o cyclonedx-json@1.5
```

SPDX:

```bash
syft IMAGE_PATH -o spdx-json@2.3
syft registry:example.io/hello-world:latest -o spdx-json@2.3
```

### From Local Filesystem

CycloneDX:

```bash
syft dir:DIRECTORY_PATH -o cyclonedx-json@1.5
syft file:FILE_PATH -o cyclonedx-json@1.5
```

SPDX:

```bash
syft dir:DIRECTORY_PATH -o spdx-json@2.3
syft file:FILE_PATH -o spdx-json@2.3
```

## Scanning SBOMs

Upload via the RHTPA console: SBOMs > Generate vulnerability report > drag and
drop or browse. Supports standard SBOM, AIBOM (language models), and CBOM
(cryptographic materials). Red Hat does not retain uploaded SBOMs.

Accepted formats: CycloneDX 1.3-1.6, SPDX 2.2-2.3.

## Search Capabilities

Navigate to Search from the RHTPA console. Results include SBOM documents,
software packages, vulnerabilities, and advisories. Filter by date range,
SBOM format, and license expression.

## License Information

Download license export as CSV from SBOM options menu. The license reference
CSV applies only to SPDX-formatted SBOMs.

## Label Management

Add labels by typing in the Label field and clicking Add. Remove labels by
clicking X on the label under "Labels of SBOM". Save after editing.

## Deleting SBOMs and Advisories

Navigate to SBOM or Advisories, click options menu > Delete, confirm deletion.
Verify the item is no longer displayed.

## Microsoft Entra ID OIDC Configuration

### Prerequisites

- OCP 4.16 or later
- Microsoft Azure account with app registration permissions
- Microsoft Entra ID tenant

### API Application Registration

Required scopes:

| Scope | Purpose |
|-------|---------|
| `create:document` | Create documents in RHTPA |
| `read:document` | Read documents in RHTPA |
| `update:document` | Update documents in RHTPA |
| `delete:document` | Delete documents in RHTPA |

Application ID URI: accept default. Token version: `accessTokenAcceptedVersion: 2`.

### Application Roles

| Role Value | Member Type |
|------------|-------------|
| `App.Read.Document` | Applications |
| `App.Create.Document` | Applications |
| `App.Update.Document` | Applications |
| `App.Delete.Document` | Applications |

### Frontend Application Registration

- Platform: Single-page application (SPA)
- Redirect URI: `https://rhtpa.apps.example.com/`
- Implicit grant: do not check Access tokens or ID tokens
- Allow public client flows: No

### auth.yaml ConfigMap

The `auth.yaml` maps OIDC scopes to RHTPA internal permissions:

```yaml
authentication:
  clients:
    - clientId: FRONTEND_CLIENT_ID
      issuerUrl: https://login.microsoftonline.com/TENANT_ID/v2.0
      requiredAudience: API_CLIENT_ID
      scopeMappings:
        "read:document":
          - "ai"
          - "read.sbom"
          - "read.advisory"
          - "read.importer"
          - "read.metadata"
          - "read.sbomGroup"
          - "read.weakness"
          - "read.systemInformation"
        "create:document":
          - "create.sbom"
          - "create.advisory"
          - "create.importer"
          - "create.metadata"
          - "create.sbomGroup"
          - "create.weakness"
          - "update.sbom"
          - "update.advisory"
          - "update.importer"
          - "update.metadata"
          - "update.sbomGroup"
          - "update.weakness"
          - "upload.dataset"
        "update:document":
          - "update.sbom"
          - "update.advisory"
          - "update.importer"
          - "update.metadata"
          - "update.sbomGroup"
          - "update.weakness"
        "delete:document":
          - "delete.sbom"
          - "delete.advisory"
          - "delete.importer"
          - "delete.metadata"
          - "delete.sbomGroup"
          - "delete.vulnerability"
          - "delete.weakness"
    - clientId: API_CLIENT_ID
      issuerUrl: https://login.microsoftonline.com/TENANT_ID/v2.0
      requiredAudience: API_CLIENT_ID
      scopeSelector: "$['scope','scp','roles']"
      scopeMappings:
        "App.Read.Document":
          - "ai"
          - "read.sbom"
          - "read.advisory"
          - "read.importer"
          - "read.metadata"
          - "read.sbomGroup"
          - "read.weakness"
          - "read.systemInformation"
        "App.Create.Document":
          - "create.sbom"
          - "create.advisory"
          - "create.importer"
          - "create.metadata"
          - "create.sbomGroup"
          - "create.weakness"
          - "update.sbom"
          - "update.advisory"
          - "update.importer"
          - "update.metadata"
          - "update.sbomGroup"
          - "update.weakness"
          - "upload.dataset"
        "App.Update.Document":
          - "update.sbom"
          - "update.advisory"
          - "update.importer"
          - "update.metadata"
          - "update.sbomGroup"
          - "update.weakness"
        "App.Delete.Document":
          - "delete.sbom"
          - "delete.advisory"
          - "delete.importer"
          - "delete.metadata"
          - "delete.sbomGroup"
          - "delete.vulnerability"
          - "delete.weakness"
```

### Helm Values (oidc section)

```yaml
oidc:
  issuerUrl: https://login.microsoftonline.com/TENANT_ID/v2.0
  uiScope: >-
    openid profile email offline_access
    api://API_CLIENT_ID/create:document
    api://API_CLIENT_ID/read:document
    api://API_CLIENT_ID/update:document
    api://API_CLIENT_ID/delete:document
  loadUser: false
  clients:
    frontend:
      clientId: FRONTEND_CLIENT_ID
    cli:
      clientId: API_CLIENT_ID
      clientSecret: CLIENT_SECRET
```

### Authenticator ConfigMap Reference

```yaml
authenticator:
  configMapRef:
    name: server-entra-auth
    key: auth.yaml
```

### Applying OIDC Changes Post-Deployment

```bash
helm upgrade --install redhat-trusted-profile-analyzer \
  openshift-helm-charts/redhat-trusted-profile-analyzer \
  -n $NAMESPACE \
  --values values-rhtpa.yaml \
  --values values-importers.yaml \
  --set-string appDomain=$APP_DOMAIN_URL
```

## FAQ Highlights

- RHTPA is available as a hosted service on Hybrid Cloud Console (free) and as
  a self-managed deployment on RHEL or OCP
- Supports CycloneDX 1.6 or lower and SPDX 2.3 or lower
- CI/CD integration: add a task for SBOM generation and upload to RHTPA
- Telemetry: application telemetry, SRE metrics, and system metrics are
  collected
