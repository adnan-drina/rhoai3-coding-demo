# Official Doc Extraction

Use this extraction to keep Trusted Profile Analyzer release information
grounded in the official Red Hat Trusted Profile Analyzer 2.2 release notes.
All feature names, API endpoints, Helm values, and behavioral changes are taken
directly from the official documentation.

## Introduction

Red Hat Trusted Profile Analyzer (RHTPA) is a proactive service for risk
management of Open Source Software (OSS) packages and dependencies. It provides
awareness and remediation of OSS vulnerabilities discovered within the software
supply chain. The latest sub-release is 2.2.5.

## New Features and Enhancements

### Read-Only Mode

RHTPA can be switched to read-only mode for upgrades and data migration. When
enabled, the `trustd` and `importer` services reject content changes and halt
data ingestion. Configure via the RHTPA Helm Chart by setting the top-level
property `readOnly: true` for both the `trustd` and `importer` services. The
RHTPA console displays a "Read-only" banner and disables update buttons.

### Optimized Data Model for Large-Scale SBOM Deletions

The data model has been optimized so API calls to delete SBOM documents are
efficient and performant at scale, with faster deletion operations.

### Automated AIBOM and CBOM Labeling

RHTPA automatically applies labels based on SBOM type (CycloneDX or SPDX).
When a CycloneDX-formatted SBOM is ingested:

- A `machine-learning-model` component results in an `aibom` label
- A `cryptographic-asset` component results in a `cbom` label

### Improved License Search Capabilities

A new License screen presents all unique license expressions from all SBOM
documents, with counts of packages and SBOMs referencing each expression.
Filters on SBOM and Package list screens enable searching for license
expressions. RHTPA's core functionality now encompasses software license
management.

### Upload Functionality Relocation

The Upload section has been removed from the navigation sidebar. The SBOMs page
now has an "Upload SBOM" button and the Advisories page has an "Upload
Advisory" button.

### New API Endpoint for Recommendations

A new API endpoint fetches package recommendations and remediation of
vulnerabilities. It accepts a list of package URLs for analysis. For each
package URL, RHTPA finds the trusted package version.

### Trusted Profile Analyzer Operator GA

The TPA Operator for Red Hat OpenShift is no longer a Technology Preview feature
and is generally available (GA), ready for production workloads.

### SBOM Generator for Quay Container Images

Users can select container images from Quay, have them extracted, and generate
SBOM documents for each image using Syft. Useful for container images missing
an SBOM. Generated SBOMs are uploaded to the RHTPA instance.

## Bug Fixes

### Replica Logic

Default `replicas=0` in `values.yaml` was silently ignored because the
hard-coded replica value was `1`. Fixed to allow deploying with zero replicas
and scaling up manually. Undefined `replicas` defaults to `1`.

### Microsoft Entra ID OIDC Authentication

RHTPA now properly utilizes Azure AD single-audience tokens. Scope claims can
be obtained from the `scp` field in Entra ID tokens. Users can configure which
scopes the console requests from the OIDC provider. The `/oidc/userinfo` call
can be disabled by setting `loadUser` to `false`. Entra ID is now supported as
an OIDC provider.

### API Endpoint Consistency — analysis/latest/component

The `analysis/latest/component` endpoint no longer excludes SBOMs with an
"upstream" top root. The top root is now the top-level product root.

### Dashboard SBOM Deletion Handling

Deleted SBOMs referenced in user preferences no longer cause `unable to
connect` errors. The affected dashboard section resets to its default state.

### Latest API Ancestors

Cache filling and node collection implementations made consistent for the
`latest` endpoint, ensuring all expected nodes are retrieved.

### Missing API Results

Fixed `analysis/latest/component` to return one latest version per component
matching `analysis/component` search criteria. Both endpoints now work
consistently.

### Metrics Endpoint Ordering

The `/purl/recommend` and `/vulnerability/analyze` endpoints were moved before
conflicting endpoints so OpenTelemetry reports metrics for all endpoints
correctly.

### Circular SBOM References

SBOMs with circular links in package/component structures are now processed.
The system tracks visited nodes and halts on re-visits, returning all
discovered items with a warning on re-discovered nodes.

### CVE Schema 5.2.0 Import

Fixed the CVE data importer to support CVE schema version 5.2.0. Previously
failed with `data did not match any variant of untagged enum`.

### Zstd Compression Upgrade Path

Upgrading to RHTPA 2.2 broke downloads of SBOM and advisory files uploaded with
`storage.compression=zstd` in RHTPA 2.1.1 and earlier due to Zstd library
incompatibility. Fixed by ensuring output streams are properly shut down after
writing buffered data.

### Vulnerability Retrieval Performance

Retrieving large numbers of vulnerabilities for SBOM packages was causing poor
performance (minutes). Optimized to load thousands of vulnerabilities in
seconds.

### spec.image Default Prevents Operator Upgrade

The default `spec.image` in the CR template contained a hard-coded image
version, preventing automatic Operator upgrades. Removed from the template. For
existing CRs, remove the `image` key from `spec`:

```bash
oc patch rhtpa/trustedprofileanalyzer-sample --type=json -p '[{"op":"remove", "path":"/spec/image"}]'
```

### SBOM Deletion Performance

Decoupled the Garbage Collector from the SBOM deletion API call. Previously the
Garbage Collector triggered on every deletion, causing extended completion times
by identifying all orphaned packages.

### Operator Reconciliation Frequency

Modified the RHTPA Operator Controller Manager to reconcile every minute
instead of every second, reducing events, log entries, and collisions with
manual configuration changes.

### Importer PVC Pending State

OpenShift without a default storage class caused PVC pending state. Fixed by
adding `modules.importer.storageClassName` and `storage.storageClassName`
fields, configurable before or after deployment.

### Quay Image Tag Expiry During Import

The importer now proactively handles image/tag issues during Quay import,
completing without interruption and reporting individual image issues in logs.

### Orphaned Document Cleanup

Document storage no longer lags behind the database, eliminating orphaned
documents and optimizing storage usage.

## Known Issues

### Resolved Known Issues

The following issues from earlier 2.2.x releases have been resolved:

- **CVE schema 5.2.0 import** — fixed in a subsequent 2.2.x release
- **Operator reconciliation loop** — fixed; reconciliation interval changed to
  one minute
- **Importer PVC pending** — fixed; storageClassName fields added

### Unresolved Known Issues

**Parallel RHTPA instances not supported**: The Operator uses a
cluster-scoped service account and role mapping. Multiple instances cause
reconciliation problems for CRs in other namespaces. Not supported by Red Hat.

**Importer crash in read-only mode**: Importer jobs may clean up stale jobs,
causing database writes. If the database is also read-only, the importer
crashes. Workaround: disable and stop importers before enabling read-only mode.

**Console read-only false positive**: The console temporarily defaults to
read-only mode while the server info API loads, showing a misleading warning
on every page load. No workaround available.

**Helm Chart validation in OpenShift Console**: Installing or upgrading via
Helm in the OpenShift Console can fail to download schema specs. Workaround:
use the `helm` CLI tool.

**authenticator.content Helm value**: Specifying `authenticator.content` in
the Helm Chart causes server pod crashes from invalid `auth.yaml`. Workaround:
use `authenticator.configMapRef` referencing a custom ConfigMap:

```yaml
authenticator:
  configMapRef:
    name: custom-configmap-name
    key: auth.yaml
```

**Package details missing for ML model SBOMs**: Machine-learning models are
stored as packages. The relationship between ML model components and parent
SBOMs is not reflected in the data model. Workaround: observe ML model
components on the SBOM Packages screen.

**Cryptographic methods as package names**: Cryptographic asset component types
fill the package name field with the cryptographic method name. No workaround.

**Bulk SBOM upload partial failures**: Large concurrent requests to S3/object
storage during bulk ingestion can cause errors. Workaround: stop or scale down
the importer during bulk uploads.

**First CVSS score chosen instead of highest**: When a vulnerability has
multiple advisories, the first CVSS score is chosen instead of the highest.
No workaround.

**License info not SPDX-compliant**: Embedded license info in packages does not
comply with SPDX standards. Packages are marked as `NOASSERTION`. No
workaround.

**Self-signed Quay certificate import failure**: Custom Quay sources with
self-signed certificates fail to import. Workaround: mount the Root CA
certificate to the importer pod.

**ODF IncompleteBody error**: ODF does not support the `aws-sdk` Rust client
compression logic, resulting in `409` responses. Workaround: compression logic
removed from RHTPA source when using ODF.

**Large vulnerability page loads**: Correlating vulnerability data between
advisories and large SBOMs can cause slow page loads. No workaround.

**SBOM version search inconsistency**: Searching by SBOM version numbers
returns inconsistent results. No workaround.

**Load balancer idle connection drops**: Uploading large data sets (e.g.,
350 MB) may cause load balancer to drop idle connections. Workaround: split
uploads into 10-20 MB parts.

**No CPE 2.3 support**: CPE string bindings do not render properly in the
console or license exports. No workaround.

**Helm 3.17+ requirement**: RHTPA 2.2 requires Helm version 3.17 or later.

**No CVSS v4 support**: CVSS version 4 scores are not supported. No
workaround.

**Advisory env/temporal score upload failure**: CSAF documents with CVSS
vectors containing environment or temporal scores fail to upload. No
workaround.

## Deprecated Functionality

**Delete vulnerability API endpoint removed**: Deleting vulnerabilities via the
API endpoint was unintended behavior since advisory deletion already removes
related vulnerabilities. The endpoint has been removed and deprecated.
