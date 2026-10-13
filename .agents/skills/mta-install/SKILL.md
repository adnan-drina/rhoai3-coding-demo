---
name: mta-install
metadata:
  author: rhoai3-coding-demo
  version: 1.1.0
  platform-family: "mta"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Application Modernization"
description: >
  Use when installing MTA 8.3 operator, UI, and CLI on OpenShift, including
  prerequisites, namespace setup, and verification. Do NOT use for using tools
  (use mta-cli/mta-ui) or AI features (use mta-lightspeed).
---

# MTA Installation — 8.3

Read `references/source-capture.md` and the current-update section of
`references/official-doc-extraction.md` before selecting an installation path.
The product baseline and deployment status are in `docs/PLATFORM_BASELINE.md`.

## Workflow

1. Identify Operator/UI, standalone CLI, or restricted-network installation.
2. Verify OpenShift compatibility (the 8.3 UI guide specifies 4.21–4.22),
   available storage and the catalog's reviewed Operator version.
3. Change the Git-managed Subscription and `tackle.konveyor.io/v1alpha1`
   Tackle CR. Let the Operator own its generated deployments and databases.
4. Configure Hub OIDC and any external IdP through supported fields. A fresh
   installation does not deploy a dedicated Keycloak instance; preserve an
   existing legacy IdP until its explicit migration is complete.
5. Size the Hub RWO database; account for optional RWX Maven/file storage
   when `rwx_supported` is enabled. Size optional AI storage separately.
6. Keep CLI, RPC and extension artifacts distinct. Verify OS/architecture,
   archive digest and complete extracted layout. Test actual CLI help and an
   analysis; an executable file alone is not a working analyzer.
7. Validate CSV/CRD, Tackle readiness, Route, login and an analysis independently.

For Java containerless CLI analysis, verify JDK 17+, Maven 3.9.9+, JAVA_HOME,
PATH and JVM_MAX_MEM. Do not renew a frozen migration run's analyzer pin.

## AI boundary

Use `mta-lightspeed` for the proxy and Solution Server (Technology Preview).
Native MTA Agents are Developer Preview and additionally require Agent Sandbox
Operator, SCM push access and Gateway configuration. Do not infer agent readiness
from a healthy MTA UI.

## Project delivery

Manage native resources through Kustomize/Argo CD and keep credentials outside
Git. Use the repository cluster guard before any live access. This skill refresh
does not establish that the Stage 070 upgrade is deployed or qualified.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
