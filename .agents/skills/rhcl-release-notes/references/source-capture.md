# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat Connectivity Link |
| Product version | 1.3 (demo pins rhcl-operator.v1.3.4) |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | What's New |
| Official guide | Release notes |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html-single/release_notes/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html/release_notes/index |
| Capture date | 2026-07-06 |

## Captured Sections

From Release notes guide:

- Chapter 1: Connectivity Link 1.3 release notes
  - Red Hat Connectivity Link 1.3 release notes (product overview, Kuadrant, Service Mesh 3.2)
  - New features and enhancements (CoreDNS GA, observability docs)
  - Known issues (Limitador first-request skip with Redis, CONNLINK-856)
  - Async releases:
    - 1.3.5 (1 July 2026): AuthConfig CRD v1beta2/v1beta3 upgrade fix (CONNLINK-1131)
    - 1.3.4 (2 June 2026): Limitador PVC fix (CONNLINK-855), DNS wildcard fix (Kuadrant-750), DNS zone-matching fix (Kuadrant-765), Authorino TLS preflight fix (Kuadrant-309)
    - 1.3.3 (30 April 2026): MCP gateway Technology Preview, elicitation support, MCPGatewayExtension known issue
    - 1.3.2 (8 April 2026): wasm-shim race condition fix (CONNLINK-912)
    - 1.3.1 (18 March 2026): wasm-shim header replacement fix (CONNLINK-867)

## Source Boundaries

This skill covers the "Release notes" guide for RHCL 1.3 only. It provides
information about new features, bug fixes, known issues, and async patch
releases. It does not cover:

- Product concepts and architecture (separate guide)
- Installation and configuration (separate guide)
- MCP gateway detailed architecture (separate guide)
- RHCL 1.4.0 release notes (deprecated version, not tracked)

## Advisory References

| Version | Advisory | Date |
|---------|----------|------|
| 1.3.5 | RHBA-2026:34242 | 1 July 2026 |
| 1.3.4 | RHBA-2026:22741 | 2 June 2026 |
| 1.3.3 | RHEA-2026:10743 | 30 April 2026 |
| 1.3.2 | RHBA-2026:7016 | 8 April 2026 |
| 1.3.1 | RHBA-2026:4903 | 18 March 2026 |

## Bug Tracker References

| Issue ID | Component | Summary |
|----------|-----------|---------|
| CONNLINK-1131 | AuthConfig CRD | v1beta2 CEL schema blocked upgrades |
| CONNLINK-912 | wasm-shim | Race condition: upstream received denied requests |
| CONNLINK-867 | wasm-shim | Header append instead of replace |
| CONNLINK-856 | Limitador | First request skip with Redis storage after restart |
| CONNLINK-855 | Limitador | Multi-Attach PVC error with disk storage |
| Kuadrant-750 | DNS Operator | Wildcard replacement silently discarded |
| Kuadrant-765 | DNS Operator | Private suffixes rejected during zone-matching |
| Kuadrant-309 | Authorino Operator | TLS preflight missed empty-string cert secret |

## Version Deprecation Notice

RHCL 1.4.0 is deprecated. The demo stays on RHCL 1.3.4. All guidance in this
skill is grounded in RHCL 1.3 release notes only.

## Related Official Sources To Add Later

- Red Hat Connectivity Link Life Cycle Policy
- Updating Red Hat Connectivity Link
