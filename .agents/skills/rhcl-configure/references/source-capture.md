# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat Connectivity Link |
| Product version | 1.4 |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Configure |
| Official guide | Deploying Red Hat Connectivity Link |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/deploying_red_hat_connectivity_link/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1: Configuring and deploying gateway policies
  - Secure, protect, and connect APIs
  - Set up environment and deploy application
  - DNS provider secret
  - Create Gateway object
  - About configuring Gateway, routes, and policy resources
  - GRPCRoute policy attachment (Technology Preview)
  - Add TLS certificate issuer and TLSPolicy
  - Setting DNSPolicy
  - Setting default AuthPolicy (deny-all)
  - Setting default RateLimitPolicy
  - Rate-limit headers
  - TokenRateLimitPolicy for LLM APIs
  - Override gateway policies for auth and rate limiting
  - HTTPRoute for applications
  - RateLimitPolicy override per user
- Chapter 2: Using on-premise DNS with CoreDNS

## Source Boundaries

This skill covers Connectivity Link policy configuration and deployment on
single and multicluster environments. It does not cover operator installation,
MCP gateway installation, MCP server registration, observability, or upgrading.

Multicluster policies require applying resources to each cluster individually
unless specifically excluded.
