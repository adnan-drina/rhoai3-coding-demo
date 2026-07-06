---
name: mta-install
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "mta"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Application Modernization"
description: >
  Use when installing MTA 8.1 operator, UI, and CLI on OpenShift, including
  prerequisites, namespace setup, and verification. Do NOT use for using tools
  (use mta-cli/mta-ui) or AI features (use mta-lightspeed).
---

# MTA Install

Use this skill to ground Migration Toolkit for Applications installation
procedures in the official Red Hat MTA 8.1 installation guide.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Installation Overview

MTA 8.1 provides three installation paths:

1. **MTA Operator on OpenShift** — installs the UI, backend, database,
   Keycloak, and all required components
2. **CLI via .zip download** — standalone binary for analysis on Linux, macOS,
   or Windows
3. **CLI in disconnected environments** — container image pull and transfer for
   air-gapped installations

The MTA Operator deploys to the `openshift-mta` namespace and manages:

- Hub database and file storage
- Keycloak (Red Hat build) for authentication
- Front-end UI
- Back-end analyzer services
- Developer Lightspeed database (kai-db)

## Key Topics

- Operator prerequisites: 4 vCPUs, 8 GB RAM, 40 GB persistent storage,
  OpenShift 4.13–4.15, cluster-admin
- Persistent volume requirements: 2 RWO PVs minimum; 2 additional RWX PVs
  when `rwx_supported: true`
- Tackle CR: `apiVersion: tackle.konveyor.io/v1alpha1`, `kind: Tackle`
- Keycloak (RHBK): managed instance with tackle-admin, tackle-architect,
  tackle-migrator roles
- CLI installation: .zip download per OS/arch, `JAVA_HOME` + JDK 17+,
  Maven 3.9.9+
- Disconnected CLI: container mode with `--run-local=false`, image save/load
- Windows Docker CLI: Docker Desktop with Windows containers for .NET analysis

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify the installation target:
   - OpenShift Operator + UI instance
   - CLI on developer workstation
   - CLI in disconnected / air-gapped environment
   - CLI with Docker on Windows (.NET migrations)
4. Verify prerequisites before installation.
5. For Operator installs, confirm PV availability and storage class.
6. After installation, verify pods in `openshift-mta` namespace.
7. For CLI installs, verify `mta-cli` binary is on `$PATH`.

## Custom Resource Reference

```yaml
kind: Tackle
apiVersion: tackle.konveyor.io/v1alpha1
metadata:
  name: mta
  namespace: openshift-mta
spec:
  hub_bucket_volume_size: "100Gi"
  maven_data_volume_size: "100Gi"
  rwx_supported: "false"
```

Key CR settings: `cache_data_volume_size`, `cache_storage_class`,
`feature_auth_required`, `feature_isolate_namespace`,
`hub_database_volume_size`, `hub_bucket_volume_size`,
`keycloak_database_data_volume_size`, `rwx_supported`, `rwo_storage_class`,
`analyzer_container_limits_cpu`, `analyzer_container_limits_memory`.

## RBAC and Personas

MTA uses Red Hat build of Keycloak with three roles:

| Role | Persona | Capabilities |
|------|---------|--------------|
| `tackle-admin` | Administrator | Full access, credential management, Admin view |
| `tackle-architect` | Architect | Assessments, app management, consume credentials |
| `tackle-migrator` | Migrator | Application analysis only |

Default login: `admin` / `Passw0rd!` (change immediately after install).

## Related Skills

- Use `mta-release-notes` for MTA 8.1 release notes and known issues.
- Use `mta-cli` for CLI usage and analysis workflows (planned).
- Use `mta-ui` for UI usage and assessment workflows (planned).
- Use `mta-lightspeed` for Developer Lightspeed AI features (planned).

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
