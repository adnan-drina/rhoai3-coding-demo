---
name: rhads-standalone-clis
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhads"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Trusted Software Supply Chain"
description: >
  Use when using standalone CLI tools (cosign, rekor-cli, conforma, syft,
  roxctl) with RHADS-SSC. Covers which CLIs ship with which component (RHTAS,
  RHTPA, RHACS), their purposes, how to obtain binaries, and supported
  architectures. Do NOT use for pipeline workflows, template creation, or
  architecture overview; use sibling rhads-* skills instead.
---

# RHADS-SSC Standalone CLIs

Use this skill to identify and explain the standalone CLI tools available with
RHADS-SSC 1.9, their source components, and supported architectures.

## Source Grounding

Read `references/source-capture.md` before citing CLI availability or features.

## CLI Overview

Five standalone CLIs are available as part of RHADS-SSC:

| CLI | Source Component | Purpose |
|-----|-----------------|---------|
| `cosign` | RHTAS | Sign container images and verify signatures |
| `rekor` | RHTAS | Transparency log entries: make, verify, query |
| Conforma | RHTAS | Define and enforce security policies for builds |
| Syft | RHTPA | Generate SBOMs for container images or filesystems |
| `roxctl` | RHACS | Run commands on RHACS (scan, check, deploy check) |

## Component Mapping

### RHTAS CLIs (cosign, rekor, Conforma)

- Shipped with Red Hat Trusted Artifact Signer
- Downloaded from OpenShift cluster via web console after RHTAS installation
- Conforma is the Red Hat-supported build of the upstream Conforma project

### RHTPA CLI (Syft)

- Distributed as standalone container image via Red Hat Ecosystem Catalog
- Available for AMD64 architecture on Linux
- For other architectures, install upstream Syft

### RHACS CLI (roxctl)

- Ships with Red Hat Advanced Cluster Security
- Pipelines run three `roxctl` tasks: image scan, image check, deployment check

## Supported Architectures

| Architecture | Cosign, Rekor, Conforma, roxctl | Syft |
|-------------|-------------------------------|------|
| Linux x86_64 | Yes | Yes |
| Linux arm64 | Yes | No (use upstream) |
| Linux ppc64le | Yes | No (use upstream) |
| Linux s390x | Yes | No (use upstream) |
| macOS x86_64 | Yes | No |
| macOS arm64 | Yes | No |
| Windows x86_64 | Yes | No |

## Usage Context

These CLIs can be used:
- With an RHADS-SSC instance on an OpenShift cluster
- On a local workstation for local build/test automation

## Workflow

1. Read `references/official-doc-extraction.md` for full detail.
2. When recommending a CLI, confirm the architecture is supported.
3. When explaining signing/verification, reference cosign + rekor.
4. When explaining policy enforcement, reference Conforma.
5. When explaining SBOM generation, reference Syft.
6. When explaining vulnerability scanning, reference roxctl.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
