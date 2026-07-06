---
name: ocp-devspaces-install
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when installing, upgrading, or uninstalling Red Hat OpenShift Dev Spaces
  3.28, including dsc CLI usage, CheCluster CR, OperatorHub installation,
  and disconnected/restricted network installation. Do NOT use for concepts
  (use ocp-devspaces-about), administration (use ocp-devspaces-admin), user
  workflows (use ocp-devspaces-user-guide), or release notes (use
  ocp-devspaces-release-notes).
---

# OCP Dev Spaces Install

Use this skill to ground OpenShift Dev Spaces installation guidance in the
official Red Hat OpenShift Dev Spaces 3.28 Installation guide for the active
baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers the installation
lifecycle: requirements, `dsc` CLI, RBAC permissions, standard installation
(CLI and web console), restricted environment installation, external identity
provider (Keycloak), CheCluster CR patching during install, verification, and
uninstallation. It does not cover administration, CheCluster field reference,
user workflows, or release notes.

## Prerequisites

- OpenShift Container Platform 4.16–4.22 cluster (CLI install requires 4.22+)
- Supported architectures: `x86_64`, `s390x`, `ppc64le`, `arm64`
- Active `oc` session with administrative permissions
- `dsc` CLI management tool installed (for CLI method)
- Only one Dev Spaces instance per cluster

## Installation Methods

Two methods are supported:

- **CLI (`dsc`)**: Full control over configuration. Install with
  `dsc server:deploy --platform openshift`. Supports CheCluster CR patching via
  `--che-operator-cr-patch-yaml`.
- **Web console**: Standard OperatorHub workflow. Install the Operator, create
  the `openshift-devspaces` namespace, then create a `CheCluster` instance from
  the Installed Operators page.

The Dev Spaces Operator depends on the Dev Workspace Operator. Both must be
installed in the same namespace. The same applies if Web Terminal Operator is
also deployed.

### Restricted Environment

Air-gapped clusters require mirroring container images and the Operator catalog
to a private registry before installation. Key parameters include
`--catalog-source-name=devspaces-disconnected-install` and
`--skip-devworkspace-operator`. Network policies must allow traffic from
`openshift-devspaces` to user project pods.

### External Identity Provider (Keycloak)

Deploy with Keycloak as external OIDC provider by patching the CheCluster CR
with `spec.networking.auth` fields including `oAuthClientName`,
`identityProviderURL`, and OAuth proxy environment variables. Requires creating
a `devspaces` client in Keycloak and adding it to the OpenShift authentication
audiences.

## CheCluster CR Overview

The `CheCluster` CR (`apiVersion: org.eclipse.che/v2`) is the central
configuration object. During installation, pass a patch file to `dsc` with
`--che-operator-cr-patch-yaml`. After installation, edit with
`oc edit checluster/devspaces -n openshift-devspaces`. Key spec sections
include `networking.auth`, `components.cheServer`, and `devEnvironments`.

## Upgrade

The Operator supports automatic upgrades through OLM approval strategy. Use
`dsc server:deploy` to upgrade an existing installation. For restricted
environments, re-run the mirroring script with updated version parameters
before upgrading.

## Uninstallation

Remove Dev Spaces with `dsc server:delete`. Options:

- `--delete-namespace`: Also removes the `openshift-devspaces` namespace
- `--delete-all`: Also removes the Dev Workspace Operator

Verify removal:

```shell
oc get namespace openshift-devspaces
```

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns installation, restricted environment
   setup, identity provider integration, verification, or uninstallation.
4. For GitOps manifests, verify all API versions and CheCluster fields before
   committing.
5. For live operations, use the repo environment guard.
6. Validate the output with `references/validation-checklist.md` when present.

## Related Skills

- Use `ocp-devspaces-about` for Dev Spaces concepts and architecture overview.
- Use `ocp-devspaces-admin` for CheCluster CR administration and configuration.
- Use `ocp-devspaces-user-guide` for workspace creation and user workflows.
- Use `ocp-devspaces-release-notes` for release notes and known issues.
- Use `manage-devspaces` for demo-specific Dev Spaces workspace management.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
