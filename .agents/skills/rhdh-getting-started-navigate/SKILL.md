---
name: rhdh-getting-started-navigate
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when learning to navigate the Red Hat Developer Hub 1.10 interface, log
  in, verify identity, discover software components, use Software Templates,
  browse TechDocs, test APIs, search for resources, use Developer Lightspeed
  for RHDH, manage extensions, customize interface settings, or star items
  for quick access. Do NOT use for installing or configuring a RHDH instance
  (use rhdh-getting-started-setup).
---

# RHDH Getting Started — Navigate

Use this skill to ground developer onboarding and navigation guidance in the
official Red Hat Developer Hub 1.10 documentation for the active baseline in
`docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Purpose of RHDH

Red Hat Developer Hub is an internal developer portal (IDP) that centralizes
infrastructure management, software project generation, tools and services, and
technical documentation. It reduces context switching by unifying code
repositories, CI/CD, monitoring, and API documentation in one interface.

Core capabilities:
- **Software Catalog** — centralized inventory of components, APIs, systems
- **Software Templates** — self-service project scaffolding
- **TechDocs** — docs-as-code rendered inside the portal
- **Plugins** — extend with Jira, Jenkins, ArgoCD, Kubernetes, etc.
- **Global Search** — unified search across the software ecosystem

## Onboarding Workflow

1. **Log in** — authenticate via SSO, Keycloak, GitHub, GitLab, Azure, or guest
   (limited, non-production).
2. **Verify profile** — Settings > User Entity; check ownership card.
3. **Organize workspace** — star frequently used components, pin sidebar.
4. **Explore production resources** — browse Docs, APIs, Software Templates.

## Interface Navigation

### Global Header

- **Search** — locate components, APIs, docs, and users instantly.
- **Create (+)** — access Software Templates for self-service scaffolding.
- **User profile** — manage settings, appearance (Light/Dark/Auto), log out.
- **Help (?)** — support resources and Quick start panel.
- **Starred Items** — bookmarked entities.
- **Application Launcher** — integrated applications and tools.

### Left Navigation Sidebar

- **Home** — personalized dashboard with team updates and recent items.
- **Catalog** — software components, services, and resources inventory.
- **Docs** — TechDocs library linked to software entities.
- **APIs** — centralized API definition browser.

## Software Catalog

Filter components by Kind (Component, API, Template, Group), Type (Library,
Website, Service, Tool), Owner, and Lifecycle (production, experimental,
deprecated). Select a component card to view Overview, Docs, Dependencies, and
Relations tabs.

## Software Templates

Create new components via Catalog > Self-service or Create (+) in the header.
Templates use YAML definitions with sequential actions (scaffolding, repo
creation, CI/CD setup). Required permissions: `scaffolder.template.parameter.read`,
`scaffolder.template.step.read`, `scaffolder.task.create`.

Import templates via `catalog.locations` in `app-config.yaml`:

```yaml
catalog:
  rules:
    - allow: [Template]
  locations:
    - type: url
      target: https://<repository_url/template-name>.yaml
```

## TechDocs

Docs-as-code documentation rendered inside the portal. Search, filter by
Owner, Tags, Starred, or Owned. Navigate content using table of contents,
navigation menu, and search bar within documents.

## API Browser

Browse APIs via the left sidebar or Catalog > Kind: API. View Definition tab
for rendered Swagger/AsyncAPI/GraphQL. Interactive testing: Try it out > enter
parameters > Run. Supported formats: OpenAPI, AsyncAPI, GraphQL.

## Global Search

Unified search indexes the entire software ecosystem. Filter results by Kind,
Type, and Lifecycle. Results categorize matches as Components, APIs, TechDocs,
and Users.

## Developer Lightspeed for RHDH

AI assistant for platform questions, log analysis, code generation, and test
plans. Features:

- Thinking cards with reasoning visibility
- MCP tool call transparency
- RAG citations from internal documentation
- Context preservation across model changes
- Notebooks for private knowledge bases (Developer Preview)

Safety guards use Llama Guard by default; configurable via `run.yaml`.

## Extensions Marketplace

Browse extensions via left sidebar > Extensions. Categories: Installed,
Available. End users typically cannot install plugins; contact administrator
to request new integrations.

## Interface Customization

Settings > Appearance:
- Theme: Light, Dark, Auto
- Language: preferred interface language
- Pin Sidebar: keep left navigation expanded (enabled by default)

Profile: verify User Entity, view Direct Relations vs Aggregated Relations.

## Starred Items

Star components in Catalog > Actions column (star icon). Access starred items
from the Home page (Your Starred Entities card) or Starred Items in the header.

## Workflow

1. Confirm the active RHDH baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md` for detailed feature coverage.
3. Log in and verify your identity and ownership.
4. Explore the Software Catalog, APIs, TechDocs, and Templates.
5. Customize your workspace (starred items, theme, pinned sidebar).
6. Use Developer Lightspeed for AI-assisted help if configured.

## Related Skills

- Use `rhdh-getting-started-setup` for installing and configuring a RHDH
  instance, authentication, and RBAC setup.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
