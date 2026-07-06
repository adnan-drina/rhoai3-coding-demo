---
name: ocp-lightspeed-install
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when installing or uninstalling Red Hat OpenShift Lightspeed 1.0,
  including operator installation, OLSConfig CR creation, LLM provider
  credential setup, and prerequisite verification. Do NOT use for concepts
  (use ocp-lightspeed-about), configuring (use ocp-lightspeed-configure),
  operations (use ocp-lightspeed-operate), or troubleshooting
  (use ocp-lightspeed-troubleshoot).
---

# OCP Lightspeed Install

Use this skill to ground OpenShift Lightspeed installation guidance in the
official Red Hat OpenShift Lightspeed 1.0 install documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers the Operator
installation lifecycle, LLM provider prerequisites, subscription requirements,
and operator verification. It does not cover Lightspeed configuration,
day-2 operations, or troubleshooting topics.

> **Gap note**: The official Install guide (as captured 2026-07-06) covers
> Operator installation only. OLSConfig CR creation, LLM provider secret
> creation, and uninstallation procedures are expected in the separate
> "Configuring" guide. Those topics should be added to this skill or to
> `ocp-lightspeed-configure` once that documentation is captured.

## Prerequisites

- OpenShift Container Platform 4.16 to 4.19 (OperatorHub path) or 4.20+
  (software catalog path).
- `cluster-admin` role on the cluster.
- An LLM provider already configured and reachable. The Operator does not
  install an LLM provider. Supported providers:
  - Red Hat Enterprise Linux AI (RHEL AI)
  - Red Hat OpenShift AI
  - IBM watsonx (requires IBM Cloud project and API key)
  - OpenAI (requires API key or project name)
  - Microsoft Azure OpenAI (requires Azure OpenAI Service instance with at
    least one model deployment)
- A valid subscription to one of: Red Hat OpenShift Kubernetes Engine,
  Red Hat OpenShift Virtualization Engine, OpenShift Container Platform, or
  Red Hat OpenShift Platform Plus.

## Installation

The Operator can be installed via the web console using one of two paths
depending on the OCP version. See `references/official-doc-extraction.md` for
the full step-by-step procedures.

- **OperatorHub** (OCP 4.16-4.19): Operators > OperatorHub > search
  "OpenShift Lightspeed" > Install with defaults > verify `Succeeded` status.
- **Software catalog** (OCP 4.20+): Ecosystem > Software Catalog > select
  `openshift-marketplace` project > search "OpenShift Lightspeed" > Install
  with defaults > verify `Succeeded` status under Ecosystem > Installed
  Operators.

### Post-Installation

After the Operator is installed, you must configure the OpenShift Lightspeed
Service by creating an OLSConfig CR and LLM provider credentials. These steps
are documented in the OpenShift Lightspeed "Configuring" guide and should be
captured in `ocp-lightspeed-configure`.

## Uninstallation

> **Gap**: The official Install guide does not include uninstallation steps.
> Uninstallation is expected in a separate guide. Add uninstallation procedures
> once that documentation is captured.

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Verify that an LLM provider is available and reachable before starting
   Operator installation.
4. Choose the installation path based on OCP version (OperatorHub vs software
   catalog).
5. Install the Operator using default settings.
6. Verify installation status shows `Succeeded`.
7. Proceed to OLSConfig and LLM credential configuration (see
   `ocp-lightspeed-configure`).
8. For live operations, use the repo environment guard from `AGENTS.md`.

## Related Skills

- `ocp-lightspeed-about` for OpenShift Lightspeed conceptual overview.
- `ocp-lightspeed-configure` for OLSConfig CR, LLM provider secrets, and
  service configuration.
- `ocp-lightspeed-operate` for day-2 operations and administration.
- `ocp-lightspeed-troubleshoot` for diagnostics and recovery.
- `ocp-lightspeed-upgrade` for Operator upgrade procedures.
- `ocp-lightspeed-uninstall` for removal procedures (if separated from
  configure).

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
