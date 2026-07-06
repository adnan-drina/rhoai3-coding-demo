# Official Doc Extraction

This extraction is derived from the official RHADS-SSC 1.9 "Using standalone
CLIs" guide captured in `source-capture.md`.

## Overview

Five CLI programs are available as part of RHADS-SSC to enhance security and
compliance in the software supply chain. They are shipped with Red Hat products
that are components or dependencies of RHADS-SSC.

## RHTAS CLIs

Red Hat Trusted Artifact Signer (RHTAS) provides access to three CLI tools.
RHTAS can be installed simultaneously with RHADS-SSC or later using OLM.
Binaries are downloaded from the OpenShift cluster via the web console.

### Cosign

- Tool for signing container images and verifying signatures
- Binary name: `cosign`

### Rekor

- Data log storing metadata of signed software artifacts
- Provides transparency for signatures
- CLI operations: make, verify, and query entries in the Rekor transparency log
- Binary name: `rekor`

### Conforma

- Defines and enforces security policies for building and testing container
  images
- Red Hat-supported build of the upstream open source Conforma project
- Previously known as Enterprise Contract (EC)

## RHTPA CLI

Red Hat Trusted Profile Analyzer (RHTPA) automates SBOM creation and
management. Can be installed during RHADS-SSC installation.

### Syft

- Generates Software Bill of Materials (SBOMs) for container images or local
  file systems
- Provides detailed information about packages, libraries, and dependencies
- Distributed as standalone container image through Red Hat Ecosystem Catalog
- Available for AMD64 architecture on Linux only
- For other architectures: install upstream version of Syft

## RHACS CLI

Red Hat Advanced Cluster Security (RHACS) is automatically installed and
configured during RHADS-SSC installation. Scans artifacts for vulnerabilities.

### roxctl

- CLI for running commands on RHACS
- RHADS-SSC pipelines run three `roxctl` tasks:
  1. Scanning container images for vulnerabilities
  2. Checking build-time violations of security policies in container images
  3. Checking build-time violations in YAML deployment files

## Supported Architectures

| Architecture | Cosign, Rekor, Conforma, roxctl | Syft |
|-------------|-------------------------------|------|
| Linux x86_64 | Yes | Yes |
| Linux arm64 | Yes | No |
| Linux ppc64le | Yes | No |
| Linux s390x | Yes | No |
| macOS x86_64 | Yes | No |
| macOS arm64 | Yes | No |
| Windows x86_64 | Yes | No |

Note: To use Syft on architectures other than x86_64 on Linux, install the
upstream version of Syft.

## Binary Availability

- RHTAS CLIs: Download from OpenShift cluster web console after RHTAS
  installation
- Syft: Pull container image from Red Hat Ecosystem Catalog
- roxctl: Available after RHACS installation

## Usage Context

All CLIs can be used in two ways:
1. With an RHADS-SSC instance running on an OpenShift cluster
2. Installed on a local workstation for local build and test automation

## Unresolved Items

This chapter does not define:

- Detailed CLI command syntax or flags
- RHTAS installation procedure
- RHACS installation procedure
- Cosign keyless signing configuration
- Rekor server setup
- Conforma policy authoring
- Syft output format options

Use the respective product documentation for those items.
