---
name: rhads-install
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhads"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Trusted Software Supply Chain"
description: >
  Use when installing Red Hat Trusted Application Pipeline / RHADS-SSC on
  OpenShift, including prerequisites, operator installation, and verification:
  downloading the tssc CLI container, creating and customizing config.yaml,
  integrating external services (GitHub, GitLab, Bitbucket, Quay, JFrog,
  Nexus, RHACS, RHTAS, RHTPA, Jenkins, Azure Pipelines), deploying with
  tssc deploy, retrieving credentials, and understanding hardware
  requirements and component versions for RHADS-SSC 1.9. Do NOT use for
  CI/CD pipeline authoring or integration workflows (use rhads-cicd-*),
  customization beyond config.yaml (use rhads-customize), or compliance
  policy configuration (use rhads-compliance).
---

# RHADS-SSC Install

Use this skill to ground RHADS-SSC installation guidance in the official
Red Hat Advanced Developer Suite - software supply chain 1.9 installing guide.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official
Red Hat documentation is product authority. This skill covers the installer
workflow, hardware requirements, service integrations, deployment, upgrade
posture, credentials reference, and component list.

## Product Overview

RHADS-SSC is a suite that deploys a secure, automated CI/CD platform on
OpenShift. It includes:

- Red Hat Advanced Cluster Security (RHACS)
- Red Hat Developer Hub (RHDH)
- Conforma (policy engine)
- OpenShift GitOps (Argo CD)
- OpenShift Pipelines (Tekton)
- Red Hat Trusted Artifact Signer (RHTAS)
- Red Hat Trusted Profile Analyzer (RHTPA)
- Red Hat build of Keycloak (IAM)

## Prerequisites

- Minimum 3-node OpenShift Container Platform cluster
- `cluster-admin` access
- Container management tool (Podman or Docker) on the workstation
- Default storage class with dynamic PV provisioning
- Worker nodes: minimum 5 CPU cores / 17 GiB RAM per node; recommended
  8 cores / 24 GiB RAM per node

## Installation Workflow

1. **Download**: Pull the installer image
   `quay.io/redhat-tssc/cli:1.9.0` and start an interactive container.
2. **Login**: `oc login` to the target cluster inside the container.
3. **Create config**: `tssc config --create` generates the default
   `config.yaml` ConfigMap.
4. **Customize**: Edit `config.yaml` to disable/enable products, set IAM
   provider (`github` or `gitlab`), configure RBAC, namespace prefixes, and
   `manageSubscription`.
5. **Integrate**: Run `tssc integration <provider>` commands for Git,
   registry, and pre-existing product instances (RHACS, RHTAS, RHTPA).
6. **Deploy**: `tssc deploy` installs all enabled components. Typical
   deployment takes ~1 hour. Re-run on failure before contacting support.

## Upgrade Posture

The installer does not support upgrades. After initial deployment, upgrade
each component individually via its Operator or Helm chart. RHADS-SSC 1.9
targets: RHDH Operator 1.9, RHACS Operator 4.10, RHTPA 2.2 Helm,
RHTAS Operator 2.2, OpenShift Pipelines Operator 1.21.

## Key Integrations

| Provider | Command | Purpose |
|----------|---------|---------|
| GitHub | `tssc integration github-app` | IAM + source repos |
| GitLab | `tssc integration gitlab` | IAM + source repos + CI |
| Quay | `tssc integration quay` | Container image registry |
| JFrog | `tssc integration artifactory` | Artifact registry |
| Nexus | `tssc integration nexus` | Artifact registry |
| RHACS | `tssc integration acs` | Pre-existing ACS instance |
| RHTAS | `tssc integration trusted-artifact-signer` | Pre-existing signing |
| RHTPA | `tssc integration trustification` | Pre-existing SBOM analysis |
| Jenkins | `tssc integration jenkins` | CI provider |
| Azure | `tssc integration azure` | CI provider (Tech Preview) |

An image registry (Quay, JFrog, or Nexus) **must** be integrated or
installation will fail.

## Credentials Reference

After deployment, retrieve component credentials with `oc` from their
namespaces. See `references/official-doc-extraction.md` for the full
credentials table covering RHACS (`tssc-acs`), GitOps (`tssc-gitops`),
Keycloak (`tssc-keycloak`), RHTAS (`tssc-tas`), RHTPA (`tssc-tpa`), and
RHDH (`tssc-dh`).

## Verification

```shell
# Confirm the tssc container is running
podman ps | grep cli:1.9.0

# After deploy, verify component health
oc get pods -n tssc
oc get routes -n tssc-dh
oc get routes -n tssc-acs
oc get routes -n tssc-gitops
```

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the task concerns prerequisites, config creation,
   integration, deployment, credentials, or upgrade.
4. For GitOps manifests, verify all API versions and fields before committing.
5. For live operations, use the repo environment guard.

## Related Skills

- Use future `rhads-cicd-*` for CI/CD pipeline authoring and integration.
- Use future `rhads-customize` for post-install component customization.
- Use future `rhads-compliance` for Conforma policy configuration.
- Use `ocp-pipelines-install-config` for standalone OpenShift Pipelines
  installation outside RHADS-SSC.
- Use `rhdh-install-ocp` for standalone RHDH installation outside RHADS-SSC.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
