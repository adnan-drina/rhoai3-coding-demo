---
name: rhads-customize
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhads"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Trusted Software Supply Chain"
description: >
  Use when customizing RHADS-SSC default software templates and build pipeline
  configurations. Do NOT use for SBOM inspection (use rhads-sbom), compliance
  policies (use rhads-compliance), or RHADS-SSC installation.
---

# Customizing RHADS-SSC

Use this skill when customizing Red Hat Advanced Developer Suite - Software
Supply Chain (RHADS-SSC) 1.9 software templates, build pipelines, Pipeline as
Code (pac) URLs, GitLab pipeline container images, and RHDH image registry
detection.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat docs are product authority. This skill covers the
`tssc-sample-templates` and `tssc-sample-pipelines` repositories and their
customization workflows.

## Key Concepts

### Software Template Customization

Templates live in the forked `tssc-sample-templates` repository. The
`properties` file controls default hosts, organizations, pipeline repo URL,
namespace prefix, ArgoCD settings, and secret references.

Key properties:

| Property | Purpose |
|----------|---------|
| `GITHUB__DEFAULT__HOST` | On-premise GitHub FQDN |
| `GITLAB__DEFAULT__HOST` | On-premise GitLab FQDN |
| `QUAY__DEFAULT__HOST` | On-premise Quay FQDN |
| `PIPELINE__REPO__URL` | Forked pipeline repository URL |
| `PIPELINE__REPO__BRANCH` | Pipeline repo branch |
| `DEFAULT__DEPLOYMENT__NAMESPACE__PREFIX` | Namespace prefix (default: `tssc-app`) |
| `RHTAP__DEFAULT__NAMESPACE` | RHADS-SSC namespace (default: `tssc`) |
| `ARGOCD__DEFAULT__NAMESPACE` | ArgoCD namespace (default: `tssc-gitops`) |

After editing `properties`, run `./generate.sh` to apply values to templates.

### Sample Pipelines Repository

The `tssc-sample-pipelines` repository contains:

| Directory | Purpose |
|-----------|---------|
| `gitops-repo` | Pipeline definitions for GitOps PR validation and promotion |
| `pipelines` | Build and validation pipeline implementations |
| `source-repo` | Dockerfile-based secure supply chain builds (.sig, .att, .sbom) |
| `tasks` | Reusable tasks (ACS checks, custom integrations) |

### Pipeline as Code (pac) URL Customization

Update pac URLs in templates to point to your forked pipelines:

```shell
./scripts/update-tekton-definition {fork_url} {branch_name}
```

### GitLab Pipeline Image Customization

When customizing GitLab pipeline tasks, rebuild the runner container image:

```shell
podman run -v $(pwd):/pwd:z <image_url> cp -r /work/tssc /pwd

# Customize the tasks in the extracted tssc/ directory

podman build -f Dockerfile -t quay.io/<namespace>/<image_name> .
podman push quay.io/<namespace>/<image_name>
```

Base image: `quay.io/redhat-tssc/task-runner:1.9` (built on `ubi/ubi-minimal`).
Use `microdnf` to install additional dependencies.

### Jenkins External Cluster Configuration

When Jenkins is not on the same OCP cluster, update `REKOR_HOST` and
`TUF_MIRROR` in the `env.sh` files:

- `skeleton/ci/gitops-template/jenkins/tssc/env.sh`
- `skeleton/ci/source-repo/jenkins/tssc/env.sh`

Replace `.svc` suffixes with the OCP cluster route. Retrieve routes:

```shell
oc get routes -n tssc-tas
```

### Image Registry Detection in RHDH

RHADS-SSC auto-detects Quay and JFrog Artifactory registries by URL pattern
matching. If the Image Registry tab is missing:

**For a single component** — add the annotation to `catalog-info.yaml`:

```yaml
metadata:
  annotations:
    'quay.io/repository-slug': '<ORG>/<REPO>'
    # or for JFrog:
    'jfrog-artifactory/image-name': '<IMAGE-NAME>'
```

**For all future components** — update the detection logic in the
`tssc-sample-templates` `catalog-info.yaml` template.

## Workflow

1. Read `references/source-capture.md` and confirm the product baseline.
2. Read `references/official-doc-extraction.md` for detailed procedures.
3. Fork and clone `tssc-sample-templates` and `tssc-sample-pipelines`.
4. Customize `properties` file for on-premise hosts and orgs.
5. Run `./generate.sh` to apply template customizations.
6. Update pac URLs with `./scripts/update-tekton-definition`.
7. Optionally rebuild GitLab runner image with customized tasks.
8. Import or refresh templates in RHDH.
9. Create a test application to verify customizations.

## Validation

- Import templates into RHDH and verify they appear in the catalog.
- Create a test application using a customized template.
- Verify pipeline runs complete with customized pac URLs.
- Verify the Image Registry tab appears for components using custom registries.

## Related Skills

- `rhads-sbom` — SBOM inspection with Trusted Profile Analyzer.
- `rhads-compliance` — Conforma policy management and container image validation.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
