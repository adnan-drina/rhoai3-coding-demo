---
name: rhdh-customize
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when customizing Red Hat Developer Hub appearance, templates, Learning
  Paths, Tech Radar, Home page, quick access cards, global header, floating
  action buttons, navigation, branding, and localization. Do NOT use for
  provisioning config maps and secrets (use rhdh-configure), TechDocs plugin
  setup (use rhdh-techdocs-config), or upgrade procedures (use rhdh-upgrade).
---

# RHDH Customize

Use this skill to customize Red Hat Developer Hub 1.10 appearance and features
grounded in official product documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers title, base URL,
backend secret, Software Templates, Learning Paths, global header, floating
action buttons, quick start plugin, Tech Radar, theme and branding, navigation,
persona-specific homepages, quick access cards, metadata cards, and
localization.

## Key Customization Areas

1. **Title and base URL** — `app.title`, `app.baseUrl`, `backend.baseUrl`
2. **Backend secret** — `BACKEND_SECRET` for service-to-service auth
3. **Software Templates** — `template.yaml` scaffolding, versioning,
   provenance tracking, automated lifecycle management
4. **Learning Paths** — JSON-based learning content configuration
5. **Global header** — Header links, profile menu, logo placement via
   `dynamicPlugins.frontend` config
6. **Floating action button** — Configurable action buttons via
   `app-config.yaml`
7. **Quick start plugin** — Guided walkthroughs for developers
8. **Tech Radar** — Radar visualization of technology adoption status
9. **Theme and branding** — Custom logos, colors, fonts, page titles
10. **Navigation** — Sidebar menu customization
11. **Persona-specific homepages** — Targeted content for distinct teams
12. **Quick access cards** — Homepage quick links configuration
13. **Metadata card** — Settings page RHDH metadata display
14. **Localization** — Multi-language support

## Software Templates

### Template versioning

Enable version tracking with custom actions:
- `catalog:scaffolded-from` — provenance annotation
- `catalog:template:version` — version annotation

Required plugins:
```yaml
global:
  dynamic:
    plugins:
      - package: ./dynamic-plugins/dist/backstage-community-plugin-catalog-backend-module-scaffolder-relation-processor-dynamic
        disabled: false
      - package: ./dynamic-plugins/dist/backstage-plugin-notifications
        disabled: false
      - package: ./dynamic-plugins/dist/backstage-plugin-notifications-backend-dynamic
        disabled: false
```

### Template update notifications

```yaml
scaffolder:
  notifications:
    templateUpdate:
      enabled: true
      message:
        title: 'Custom title for $ENTITY_DISPLAY_NAME'
        description: 'Custom description'
```

### Automated template lifecycle

```yaml
scaffolder:
  pullRequests:
    templateUpdate:
      enabled: true
```

### Default environment parameters

```yaml
scaffolder:
  defaultEnvironment:
    parameters:
      githubOrg: my-org
      defaultOwner: platform-team
    secrets:
      GITHUB_TOKEN: ${GITHUB_TOKEN}
```

Access via `${{ environment.parameters.* }}` and
`${{ environment.secrets.* }}` in templates.

## Theme and Branding

Custom theme configuration in `app-config.yaml`:
- Custom logos (light/dark mode, full/icon variants)
- Color palette overrides
- Font customization
- Page title

## Navigation Customization

Sidebar navigation items configured via `dynamicPlugins.frontend` in the
dynamic plugins configuration.

## Persona-Specific Homepages

Deploy targeted content for distinct teams using conditional homepage
configuration based on user groups.

## Workflow

1. Read `references/official-doc-extraction.md` for exact YAML patterns.
2. Identify the customization task:
   - Title, URL, or branding changes
   - Software Template authoring or versioning
   - Homepage or navigation customization
   - Plugin-based features (Tech Radar, Learning Paths, etc.)
3. Apply configuration to the appropriate file (`app-config.yaml` or
   dynamic plugins ConfigMap).
4. Restart/redeploy RHDH to apply changes.
5. Verify in the RHDH UI.

## Related Skills

- `rhdh-configure` — Config maps, secrets, and infrastructure configuration
- `rhdh-upgrade` — Upgrade procedures
- `rhdh-techdocs-config` — TechDocs plugin configuration

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
