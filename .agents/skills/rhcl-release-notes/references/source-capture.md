# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat Connectivity Link |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | What's New |
| Official guide | Release notes |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/release_notes/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/release_notes/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1: Red Hat Connectivity Link 1.4 release notes
  - About this release (RHBA-2026:25234, MCP gateway 0.7.0 TP, lifecycle)
  - New features and enhancements:
    - X.509 cryptographic identity verification
    - MCP gateway prompt federation (GA)
    - MCP gateway Vault documentation
    - MCP gateway audit trail documentation
    - Notable technical changes (EnvoyFilter, CR cache, toolPrefix rename)
  - Technology Preview features:
    - GRPCRoute policy attachment
    - Disconnected installation documentation
    - OCP web console plugin for API management
  - Known issues (CONNLINK-856: Limitador Redis restart)
  - Asynchronous releases:
    - 1.4.1 bug fix and security update (RHBA-2026:34242):
      - AuthConfig CRD v1beta2/v1beta3 upgrade fix (CONNLINK-1131)

## Source Boundaries

This source covers release-level announcements. It does not provide:

- Detailed feature configuration procedures
- Step-by-step migration guides for CR field changes
- Complete CR schemas or API references
- Installation or upgrade procedures (separate guides)
- Troubleshooting for listed known issues

## Related Official Sources

- RHCL 1.4 Updating Red Hat Connectivity Link:
  https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/updating_red_hat_connectivity_link/index
- RHCL 1.4 Registering MCP servers (prefix migration context):
  https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/registering_mcp_servers_and_creating_policies/index
- Red Hat Connectivity Link Life Cycle Policy:
  https://access.redhat.com/support/policy/updates/rhcl
- RHBA-2026:25234 (1.4.0 advisory)
- RHBA-2026:34242 (1.4.1 advisory)
