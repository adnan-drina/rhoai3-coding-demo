# Official Doc Extraction

Use this extraction to keep RHADS-SSC SBOM inspection content grounded in
official Red Hat sources. When implementation needs exact API paths or
authentication details, verify against the installed RHADS-SSC 1.9 cluster.

## Automatic SBOM Publishing

RHADS-SSC 1.9 automatically publishes SBOMs to RHTPA when building applications
with any supported CI provider. The manual workflow below is only needed when
extracting and keeping a local SBOM copy.

## Prerequisites

| Tool | Purpose |
|------|---------|
| `cosign` | Download SBOMs from container registries |
| `syft` | Convert SBOM formats (CycloneDX version downgrade) |
| `jq` | Parse JSON responses |
| `oc` / `kubectl` | Retrieve routes and secrets from the cluster |

## Container Image Address

Use the application image address, not the SBOM image:

```
<registry>/<namespace>/<image>:<tag>
```

Example: `quay.io/app/app-image:ff59e21cc…`

Do not use addresses ending with `.sbom`.

## Download SBOM

```shell
cosign download sbom <registry>/<namespace>/<image>:<tag> \
  > /tmp/sbom.json
```

Redirect output to a `.json` file for later reference.

## Rename SBOM Component (Optional)

By default, Syft names the component based on the filesystem path. Replace the
`name` field in `.metadata.component` with a meaningful identifier:

```json
"component": {
  "bom-ref": "fdef64df97f1d419",
  "type": "file",
  "name": "my-application-v1.2.3"
}
```

Optionally add a `version` field.

## Retrieve Bombastic API URL

```shell
bombastic_api_url="https://$(oc -n tssc get route \
  --selector app.kubernetes.io/name=bombastic-api \
  -o jsonpath='{.items[].spec.host}')"
```

Replace `tssc` with the actual RHADS-SSC namespace if different.

## Obtain Authentication Token

### Token issuer URL

```shell
token_issuer_url=https://$(oc -n tssc-keycloak get route \
  --selector app=keycloak \
  -o jsonpath='{.items[].spec.host}')/realms/chicken/protocol/openid-connect/token
```

### Walker client secret

```shell
TPA__OIDC__WALKER_CLIENT_SECRET=$(kubectl get \
  -n tssc secrets/tssc-trustification-integration \
  --template={{.data.oidc_client_secret}} | base64 -d)
```

### Bearer token

```shell
tpa_token=$(curl \
  -d 'client_id=walker' \
  -d "client_secret=$TPA__OIDC__WALKER_CLIENT_SECRET" \
  -d 'grant_type=client_credentials' \
  "$token_issuer_url" \
  | jq -r .access_token)
```

## Upload SBOM

```shell
curl \
  -H "authorization: Bearer $tpa_token" \
  -H "transfer-encoding: chunked" \
  -H "content-type: application/json" \
  --data @/tmp/sbom.json \
  "$bombastic_api_url/api/v2/sbom?id=my-sbom"
```

## Handle Upload Failure

If the upload returns `storage error: invalid storage content`, convert the
SBOM to CycloneDX version 1.4:

```shell
syft convert /tmp/sbom.json -o cyclonedx-json@1.4=/tmp/sbom-1-4.json
```

Warnings about merging packages with different pURLs can be safely disregarded.
Re-upload using the converted file:

```shell
curl \
  -H "authorization: Bearer $tpa_token" \
  -H "transfer-encoding: chunked" \
  -H "content-type: application/json" \
  --data @/tmp/sbom-1-4.json \
  "$bombastic_api_url/api/v2/sbom?id=my-sbom"
```

## Review Results in RHTPA

1. Open the RHTPA UI.
2. Select the uploaded SBOM (most recent upload).
3. Navigate to the Dependency Analytics Report tab.
4. Review vulnerabilities and available remediations.

## Key API Details

| API | Endpoint | Auth |
|-----|----------|------|
| Bombastic API v2 | `/api/v2/sbom?id=<sbom-id>` | Bearer token via Keycloak |
| Keycloak token | `/realms/chicken/protocol/openid-connect/token` | `client_id=walker`, client credentials grant |

| Secret | Namespace | Key |
|--------|-----------|-----|
| `tssc-trustification-integration` | `tssc` | `oidc_client_secret` |

| Route selector | Namespace |
|----------------|-----------|
| `app.kubernetes.io/name=bombastic-api` | `tssc` |
| `app=keycloak` | `tssc-keycloak` |

## Boundaries

- This extraction covers SBOM inspection workflows only.
- Template and pipeline customization belong in `rhads-customize`.
- Conforma compliance and container signing belong in `rhads-compliance`.
- RHTPA installation and administration are not covered here.
