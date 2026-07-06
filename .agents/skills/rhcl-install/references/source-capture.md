# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat Connectivity Link |
| Product version | 1.4 |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Install |
| Official guide | Installing Connectivity Link |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/installing_connectivity_link/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1: Installing on OpenShift Container Platform
  - Getting ready to install (required platforms, optional components, supported
    configurations)
  - Installing with the web console
  - Installing from the CLI (Cluster Ingress Operator as gateway controller)
  - Installing from the CLI with Istio as gateway controller
  - Configuring DNS provider credentials (AWS, Google Cloud, Azure)
  - Installing in a multicluster environment
  - Disconnected installation considerations

## Source Boundaries

This skill covers Connectivity Link operator installation, Kuadrant CR
creation, and prerequisite platform setup. It does not cover policy deployment
(AuthPolicy, RateLimitPolicy, DNSPolicy, TLSPolicy), MCP gateway installation,
or observability configuration.

The demo pins operator lifecycle at 1.3.4 for production stability. The 1.4
documentation captures the full install procedure; apply the 1.3.x Subscription
lifecycle pin from Stage 040 GitOps manifests when deploying.
