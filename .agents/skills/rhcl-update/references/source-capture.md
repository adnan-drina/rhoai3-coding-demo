# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat Connectivity Link |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Update |
| Official guide | Updating Red Hat Connectivity Link |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html-single/updating_red_hat_connectivity_link/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/updating_red_hat_connectivity_link/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1: Updating Connectivity Link 1.4
- RHCL 1.4.0 deprecation warning
- Supported configuration prerequisite statement
- New customer guidance (do not install 1.4.0)
- Upgrade customer guidance (pin to latest 1.3.z)

## Source Boundaries

The RHCL 1.4 update page is minimal. Its primary content is the deprecation
warning for RHCL 1.4.0. It does not provide:

- Detailed step-by-step update procedures
- Operator channel or Subscription configuration for updates
- Rollback procedures from 1.4.0 to 1.3.z
- Compatibility matrices for OCP and Service Mesh combinations
- Dependent operator update sequencing (Authorino, DNS, Limitador)

Detailed update procedures, OLM lifecycle management, and dependency
coordination must come from the RHCL release notes, RHCL installation guide,
and OLM documentation for the active cluster.

## Related Official Sources

- RHCL 1.4 release notes:
  https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/release_notes/index
- RHCL 1.4 installation guide:
  https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/installing_connectivity_link/index
- RHCL 1.4 documentation landing page:
  https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4
- RHCL product overview:
  https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.4/html/red_hat_connectivity_link/index
