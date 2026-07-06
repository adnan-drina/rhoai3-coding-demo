---
name: rhads-getting-started
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhads"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Trusted Software Supply Chain"
description: >
  Use when getting started with RHADS-SSC, initial setup, and first pipeline
  workflows. Covers the development workflow (install, create app, update, view
  security insights, deploy/promote), software template usage in RHDH,
  application creation form fields, pipeline security tasks (roxctl, SBOM,
  Conforma), build promotion across dev/stage/prod, and Conforma compliance
  reports. Do NOT use for CLI tool installation, architecture concepts, or
  release notes; use sibling rhads-* skills instead.
---

# RHADS-SSC Getting Started

Use this skill to guide users through first-time RHADS-SSC workflows: creating
an application from a template, triggering pipelines, viewing security insights,
and promoting builds.

## Source Grounding

Read `references/source-capture.md` before citing procedures.

## Development Workflow Summary

| Step | Action |
|------|--------|
| 1 | Install RHADS-SSC |
| 2 | Create an application from a template in RHDH |
| 3 | Update application source code (triggers pipeline) |
| 4 | View security insights (RHACS, SBOM, Conforma) |
| 5 | Promote build (dev -> stage -> prod via GitOps) |
| 6 | (Optional) Customize templates and pipelines |

## Application Creation

Applications are created from RHDH software templates with these choices:

- **CI provider**: Tekton (SLSA 3), GitHub Actions (SLSA 2), Jenkins (SLSA 2),
  GitLab CI (SLSA 2), Azure Pipelines (SLSA 2, Tech Preview)
- **Source repo**: GitHub, GitLab, Bitbucket
- **Registry**: Quay, JFrog Artifactory, Sonatype Nexus

Default deployment namespace prefix: `tssc-app` (creates `-development`,
`-stage`, `-prod` namespaces).

## Pipeline Security Tasks

When RHACS is configured, pipelines run:

- `roxctl image scan` — identifies vulnerabilities in the image
- `roxctl image check` — verifies build-time security policy violations
- `roxctl deployment check` — checks YAML deployment files

The `show-sbom` task generates an SBOM listing all libraries with source,
name, version, and license.

## Build Promotion

Promotion follows a GitOps pull-request model:

1. Copy container image URL from `development/deployment-patch.yaml`
2. Paste into `stage/deployment-patch.yaml` (or stage -> prod)
3. Create a PR to trigger promotion pipeline with Conforma validation
4. Merge PR to trigger Argo CD deployment

## Conforma Compliance

The promotion pipeline validates images using Conforma policies and Sigstore
cosign. Tasks include: `git-clone`, `gather-deploy-images`,
`verify-enterprise-contract`, `deploy-images`,
`download-sbom-from-url-in-attestations`, `upload-sbom-to-trustification`.

## Workflow

1. Read `references/official-doc-extraction.md` for full procedural detail.
2. When guiding app creation, reference the form fields and CI/repo/registry
   options.
3. When explaining security, reference the pipeline tasks and SBOM structure.
4. When explaining promotion, reference the GitOps PR workflow.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
