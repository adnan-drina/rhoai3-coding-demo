---
name: tpa-admin
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "tpa"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Trusted Software Supply Chain"
description: >
  Use when administering Red Hat Trusted Profile Analyzer 2.2, including
  service configuration, user management, data management, API usage, and
  operational tasks. Do NOT use for deployment (use tpa-deployment), quick
  start (use tpa-quick-start), or release notes (use tpa-release-notes).
---

# TPA Administration

Use this skill to ground Red Hat Trusted Profile Analyzer (RHTPA) 2.2
administration guidance in the official Administration Guide. RHTPA is part
of the Red Hat Trusted Software Supply Chain suite and provides centralized
SBOM management, vulnerability analysis, and advisory tracking.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official
Red Hat documentation is product authority.

## Key Administration Areas

### Data Importers

RHTPA ships with five importer sources: Red Hat CSAFs, Red Hat SBOMs, CVE
list v5, GitHub advisory database, and Quay. By default Red Hat CSAF, Red Hat
SBOM, and Quay importers are disabled. Each enabled importer runs on a 24-hour
schedule. Default resource request: 1 CPU / 8 GB RAM per importer and API
server deployment; no resource limits by default.

### SBOM Lifecycle

- **Create**: generate CycloneDX (1.3-1.6) or SPDX (2.2-2.3) SBOMs using
  Syft from container images or local filesystems
- **Scan**: upload SBOMs via the RHTPA console for vulnerability analysis;
  supports standard SBOM, AIBOM (language models), and CBOM (cryptographic
  materials); Red Hat does not retain uploaded SBOMs
- **Search**: find SBOM documents, packages, CVEs, advisories, and license
  expressions; filter by date range, SBOM format, and license
- **Labels**: add or remove custom labels on SBOMs and advisories for
  organization
- **Delete**: remove SBOM documents and advisories via the console
- **License export**: download CSV license information from SPDX-formatted
  SBOMs

### OIDC / Microsoft Entra ID Integration

RHTPA supports Microsoft Entra ID as an OpenID Connect provider. The
integration requires:

- An API application registration with scopes: `create:document`,
  `read:document`, `update:document`, `delete:document`
- Application roles: `App.Read.Document`, `App.Create.Document`,
  `App.Update.Document`, `App.Delete.Document`
- A frontend SPA application registration with delegated permissions
- Token version set to `accessTokenAcceptedVersion: 2`
- `auth.yaml` ConfigMap with `scopeMappings` for both frontend and CLI clients
- Helm values in `values-rhtpa.yaml` under the `oidc` section with
  `loadUser: false`

Prerequisites: OCP 4.16+, Microsoft Azure account with app registration
permissions, Entra ID tenant.

### Helm Upgrade for Configuration Changes

Post-deployment configuration changes require a Helm upgrade:

```bash
helm upgrade --install redhat-trusted-profile-analyzer \
  openshift-helm-charts/redhat-trusted-profile-analyzer \
  -n $NAMESPACE \
  --values values-rhtpa.yaml \
  --values values-importers.yaml \
  --set-string appDomain=$APP_DOMAIN_URL
```

## Supported Formats

| Format | Versions |
|--------|----------|
| CycloneDX | 1.3, 1.4, 1.5, 1.6 |
| SPDX | 2.2, 2.3 |

Syft binary is Technology Preview only.

## Workflow

1. Confirm the target RHTPA version (2.2) and deployment platform (RHEL or
   OCP).
2. Read `references/official-doc-extraction.md` for admin procedures.
3. Identify the task: importer management, SBOM operations, OIDC
   configuration, or Helm upgrade.
4. Follow the documented procedure; verify prerequisites.
5. For OIDC integration, collect Tenant ID, API Client ID, Frontend Client
   ID, Client Secret, and Scopes before starting.
6. Validate with `references/source-capture.md` boundaries.

## Related Skills

- Use `tpa-deployment` for installing and deploying RHTPA on RHEL or OCP.
- Use `tpa-quick-start` for getting started with RHTPA quickly.
- Use `tpa-release-notes` for version-specific changes and known issues.
- Use `ocp-pipelines-cicd` for integrating SBOM generation into CI/CD
  pipelines.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
