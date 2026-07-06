# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat Developer Hub |
| Product version | 1.10 |
| Documentation category | Configure |
| Official guide | TechDocs for Red Hat Developer Hub |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/techdocs_for_red_hat_developer_hub/index |
| Single-page URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/techdocs_for_red_hat_developer_hub/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1: About TechDocs
  - Docs-like-code approach
  - Documentation site generation with MkDocs
  - Metadata and integrations
  - Built-in navigation and search
  - Add-ons overview
- Chapter 2: Configure TechDocs
  - 2.1 Configuring storage for TechDocs files
    - 2.1.1 Configure Amazon S3 for file storage
    - 2.1.2 Configure OpenShift Data Foundation for file storage
      - 2.1.2.1 Make storage accessible (Helm chart)
      - 2.1.2.2 Make storage accessible (Operator)
  - 2.2 Configuring CI/CD to generate and publish TechDocs sites
- Chapter 3: TechDocs add-ons
  - 3.1 Install and configure a TechDocs add-on
    - 3.1.1 External add-on using the Operator
    - 3.1.2 External add-on using the Helm chart
    - 3.1.3 Install and configure a third-party TechDocs add-on
- Chapter 4: Create a TechDocs add-on

## Source Boundaries

This source is authoritative for configuring and managing the TechDocs plugin
in Red Hat Developer Hub 1.10. It covers TechDocs concepts, builder modes,
storage backends (AWS S3 and OpenShift Data Foundation), CI/CD pipeline
generation with techdocs-cli, preinstalled and external add-ons, third-party
add-on packaging and installation, and custom add-on creation.

It does **not** cover:
- General RHDH configuration (separate "Configuring" guide)
- MkDocs configuration details (upstream MkDocs documentation)
- Software Catalog setup (separate "Configuring" guide)
- Appearance customization (separate "Customizing" guide)
- Upgrade procedures (separate "Upgrading" guide)

## API Versions Documented

| Resource | apiVersion | Kind |
|----------|-----------|------|
| ObjectBucketClaim | `objectbucket.io/v1alpha1` | `ObjectBucketClaim` |
| Backstage CR | `rhdh.redhat.com/v1alpha5` | `Backstage` |
| ConfigMap | `v1` | `ConfigMap` |

## Related Official Sources

- Red Hat Developer Hub 1.10 "Configuring" guide — general RHDH config
- Red Hat Developer Hub 1.10 "Customizing" guide — appearance, templates
- Red Hat Developer Hub 1.10 "Upgrading" guide — version upgrades
- OpenShift Data Foundation documentation — ODF Operator and storage setup
- MkDocs documentation — mkdocs.yml configuration details
