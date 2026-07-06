# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat Connectivity Link |
| Product version | 1.3 (demo pins rhcl-operator.v1.3.4) |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Discover |
| Official guide | Red Hat Connectivity Link |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html-single/red_hat_connectivity_link/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html/red_hat_connectivity_link/index |
| Capture date | 2026-07-06 |

## Captured Sections

From Red Hat Connectivity Link guide:

- Chapter 1: About Connectivity Link
  - About Red Hat Connectivity Link (overview, policy types, Gateway API)
  - Connectivity Link benefits (Kubernetes-native, hybrid cloud, infrastructure as code)
  - Connectivity Link features (multicloud connectivity, ingress policy, composable API management)
  - User workflows (platform engineer, application developer, business user)
  - Using Connectivity Link technologies and patterns (policy attachment, WASM plugin, multicluster mirroring, API management)
  - Connectivity Link policy APIs (TLSPolicy, AuthPolicy, RateLimitPolicy, DNSPolicy, observability)
  - Supported configurations (OCP versions, operators, cloud providers, DNS providers, data stores, IAM)

## Source Boundaries

This skill covers the "Red Hat Connectivity Link" about/concepts guide only. It
provides conceptual understanding of the product architecture, policy APIs, user
workflows, and supported configurations. It does not cover:

- Installation and configuration (separate guide)
- MCP gateway concepts and architecture (separate guide)
- Release notes and version history (separate guide)
- Operational procedures and troubleshooting

## API Versions Documented

| Resource | API Version |
|----------|-------------|
| RateLimitPolicy | `kuadrant.io/v1` |
| AuthPolicy | `kuadrant.io/v1` |
| TLSPolicy | `kuadrant.io/v1` |
| DNSPolicy | `kuadrant.io/v1` |

## Version Deprecation Notice

RHCL 1.4.0 is deprecated. The demo stays on RHCL 1.3.4. All guidance in this
skill is grounded in RHCL 1.3 documentation only.

## Related Official Sources To Add Later

- Installing Red Hat Connectivity Link
- Configuring Red Hat Connectivity Link policies
- Observability guide
- Multicluster guide
