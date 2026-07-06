---
name: rhads-sbom
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhads"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Trusted Software Supply Chain"
description: >
  Use when scanning and inspecting SBOMs to gain actionable information about
  application security posture with RHADS-SSC. Do NOT use for template
  customization (use rhads-customize), compliance policies (use
  rhads-compliance), or RHADS-SSC installation.
---

# Inspecting SBOMs with RHADS-SSC

Use this skill when downloading, converting, and analyzing software bills of
materials (SBOMs) produced by Red Hat Advanced Developer Suite - Software Supply
Chain (RHADS-SSC) 1.9 builds with the Red Hat Trusted Profile Analyzer (RHTPA).

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat docs are product authority. This skill covers SBOM download
with Cosign, format conversion with Syft, upload to RHTPA via the Bombastic
API, and vulnerability analysis via the Dependency Analytics Report.

## Key Concepts

### Automatic SBOM Publishing

RHADS-SSC 1.9 automatically publishes SBOMs to RHTPA when building applications
with any supported CI provider. The manual procedure below is only needed if you
prefer to extract and keep a local copy.

### SBOM Lifecycle

1. RHADS-SSC builds an application image.
2. The build produces an SBOM listing all software libraries.
3. The SBOM is published to RHTPA (automatic) or downloaded manually.
4. RHTPA analyzes the SBOM against known CVEs.
5. The Dependency Analytics Report shows vulnerabilities and remediations.

### Prerequisites

- `cosign` — download SBOMs from the container registry.
- `syft` — convert SBOM formats (e.g., CycloneDX version downgrade).
- `jq` — parse JSON responses.
- `oc` — retrieve RHTPA routes and secrets.

## Workflow

1. Read `references/source-capture.md` and confirm the product baseline.
2. Read `references/official-doc-extraction.md` for detailed procedures.
3. Identify the container image address (not the `.sbom` image).
4. Download the SBOM with `cosign download sbom`.
5. Optionally rename the SBOM component for better RHTPA display.
6. Retrieve the Bombastic API URL and authentication token.
7. Upload the SBOM to RHTPA.
8. If upload fails with `storage error: invalid storage content`, convert the
   SBOM to CycloneDX 1.4 with `syft convert` and re-upload.
9. Review the Dependency Analytics Report in the RHTPA UI.

### Download SBOM

```shell
cosign download sbom <registry>/<namespace>/<image>:<tag> \
  > /tmp/sbom.json
```

### Rename SBOM Component (Optional)

Edit `/tmp/sbom.json` and replace the auto-generated name in
`.metadata.component.name` with a meaningful identifier.

### Retrieve Bombastic API URL

```shell
bombastic_api_url="https://$(oc -n tssc get route \
  --selector app.kubernetes.io/name=bombastic-api \
  -o jsonpath='{.items[].spec.host}')"
```

### Obtain Authentication Token

```shell
token_issuer_url=https://$(oc -n tssc-keycloak get route \
  --selector app=keycloak \
  -o jsonpath='{.items[].spec.host}')/realms/chicken/protocol/openid-connect/token

TPA__OIDC__WALKER_CLIENT_SECRET=$(kubectl get \
  -n tssc secrets/tssc-trustification-integration \
  --template={{.data.oidc_client_secret}} | base64 -d)

tpa_token=$(curl \
  -d 'client_id=walker' \
  -d "client_secret=$TPA__OIDC__WALKER_CLIENT_SECRET" \
  -d 'grant_type=client_credentials' \
  "$token_issuer_url" | jq -r .access_token)
```

### Upload SBOM

```shell
curl \
  -H "authorization: Bearer $tpa_token" \
  -H "transfer-encoding: chunked" \
  -H "content-type: application/json" \
  --data @/tmp/sbom.json \
  "$bombastic_api_url/api/v2/sbom?id=my-sbom"
```

### Convert SBOM Format (If Upload Fails)

```shell
syft convert /tmp/sbom.json -o cyclonedx-json@1.4=/tmp/sbom-1-4.json
```

Warnings about merging packages with different pURLs can be safely ignored.

## Validation

- Verify the SBOM appears in the RHTPA UI after upload.
- Check the Dependency Analytics Report tab for CVE analysis.
- Confirm the SBOM component name displays correctly in RHTPA.

## Known Issues

- `storage error: invalid storage content` on upload — convert to CycloneDX
  1.4 with `syft convert` before re-uploading.
- Syft conversion may warn about discarding pURL data; this does not affect
  vulnerability analysis.

## Related Skills

- `rhads-customize` — template and pipeline customization.
- `rhads-compliance` — Conforma policy management and container image signing.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
