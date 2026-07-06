# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat Developer Hub |
| Product version | 1.10 |
| Documentation category | Configure |
| Official guide | Customizing Red Hat Developer Hub |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/customizing_red_hat_developer_hub/index |
| Single-page URL | https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.10/html-single/customizing_red_hat_developer_hub/index |
| Capture date | 2026-07-06 |

## Captured Sections

- Chapter 1: Customize your Red Hat Developer Hub title
- Chapter 2: Customize your Red Hat Developer Hub base URL
- Chapter 3: Customize Red Hat Developer Hub backend secret
- Chapter 4: About Software Templates
  - 4.1 Version a Software Template
  - 4.2 Enable Software Template version update notifications
- Chapter 5: Track Component origin and Software Template version
  - 5.1 Configure provenance and versioning
  - 5.2 View Software Template dependencies
- Chapter 6: Automated Software Template lifecycle management
  - 6.1 Enable automated template updates
  - 6.2 Template sync considerations and limitations
  - 6.3 Template synchronization and notification outcomes
- Chapter 7: Standardize project development with software templates
  - 7.1 Software Templates in RHDH
  - 7.2 Create a basic software template
  - 7.3 Default environment parameters and secrets
- Chapter 8: Customize the Learning Paths
- Chapter 9: Configure the global header
- Chapter 10: Configure a floating action button
- Chapter 11: Customize the quick start plugin
- Chapter 12: Customize the Tech Radar page
- Chapter 13: Customize Red Hat Developer Hub theme and branding
- Chapter 14: Customize Red Hat Developer Hub navigation
- Chapter 15: Deploy persona-specific homepages
- Chapter 16: Customize the Quick access card
- Chapter 17: Customize the RHDH Metadata card on the Settings page
- Chapter 18: Localization in Red Hat Developer Hub

## Source Boundaries

This source is authoritative for customizing the appearance and features of
Red Hat Developer Hub 1.10. It covers display title, base URL, backend secret,
Software Templates (authoring, versioning, provenance, lifecycle management),
Learning Paths, global header, floating action buttons, quick start plugin,
Tech Radar, theme/branding, navigation, persona-specific homepages, quick
access cards, metadata cards, and localization.

It does **not** cover:
- Provisioning config maps and secrets (separate "Configuring" guide)
- Authentication providers (separate "Authentication" guide)
- RBAC policies (separate "Authorization" guide)
- TechDocs plugin setup (separate "TechDocs" guide)
- Dynamic plugin installation mechanics (separate "Administration" guide)
- Upgrade procedures (separate "Upgrading" guide)

## API Versions Documented

| Resource | apiVersion | Kind |
|----------|-----------|------|
| Backstage CR | `rhdh.redhat.com/v1alpha5` | `Backstage` |
| Software Template | `scaffolder.backstage.io/v1beta3` | `Template` |
| Catalog Entity | `backstage.io/v1alpha1` | `Component` |

## Related Official Sources

- Red Hat Developer Hub 1.10 "Configuring" guide — config maps, secrets, deployment
- Red Hat Developer Hub 1.10 "Upgrading" guide — version upgrades
- Red Hat Developer Hub 1.10 "TechDocs" guide — TechDocs plugin
- Red Hat Developer Hub 1.10 "Authentication" guide — auth providers
- Red Hat Developer Hub 1.10 "Administration" guide — dynamic plugins
