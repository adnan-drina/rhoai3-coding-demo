# Official Doc Extraction

Use this extraction to keep Red Hat Developer Hub 1.10 navigation and developer
onboarding content grounded in official Red Hat sources.

## Product Overview

Red Hat Developer Hub (RHDH) is an internal developer portal (IDP) that
centralizes infrastructure management, software project generation, tools and
services, and technical documentation. It addresses fragmented developer
workflows across code repositories, ticketing, CI/CD, and monitoring.

Key value: unified discovery, search, self-service capabilities, service
visibility, and extensibility through plugins.

## Onboarding Workflow

### Log In and Verify Profile

1. Navigate to the RHDH URL provided by administrator.
2. Authenticate via corporate SSO, Keycloak, OAuth (GitHub/GitLab/Azure), or
   guest access (limited, non-production).
3. Click avatar/name > Settings to verify User Entity matches corporate identity.
4. Navigate to My Profile > Ownership card to confirm component ownership.

Guest access limitations: read-only exploration, cannot create or register
components. Production environments typically disable guest access.

### Organize Workspace

- Star frequently used components in Catalog (Actions column > star icon).
- Access starred items via Starred Items in the Global Header.
- Configure sidebar pinning via Settings > Pin Sidebar.

## Interface Structure

### Global Header

| Element | Function |
|---------|----------|
| Search | Locate components, APIs, docs, users across ecosystem |
| Create (+) | Access Software Templates for self-service scaffolding |
| User profile | Settings, appearance (Light/Dark/Auto), log out |
| Help (?) | Support resources, Quick start panel toggle |
| Starred Items | Bookmarked entities |
| Application Launcher | Integrated applications and tools |
| Support/Notifications | System alerts and platform help |

### Left Navigation Sidebar

| Item | Purpose |
|------|---------|
| Home | Personalized dashboard, team updates, recent items |
| Catalog | Software components, services, resources inventory |
| Docs | TechDocs library linked to software entities |
| APIs | Centralized API definition browser |

## Software Catalog

Centralized inventory for software components, APIs, and systems. Supports
filtering by:

- **Kind**: Component, API, Template, Group
- **Type**: Library, Website, Service, Tool
- **Owner**: specific users or groups
- **Lifecycle**: production, experimental, deprecated

Each component has tabs: Overview, Docs, Dependencies/Relations.

### Microservice Dependencies

Filter by Kind: Component, Type: Service. Review Overview tab for owner and
source code links. Select Dependencies/Relations tab for upstream/downstream
connections.

## Software Templates

Automate creation of new projects using YAML-defined templates with sequential
actions (scaffolding, repo creation, CI/CD pipeline setup).

### Creating Components

1. Navigate to Catalog > Self-service or click Create (+) in Global Header.
2. Select a template and click Choose.
3. Follow wizard instructions for project details.
4. Review and click Create.

Required permissions: `scaffolder.template.parameter.read`,
`scaffolder.template.step.read`, `scaffolder.task.create`.

### Importing Templates

Add to `app-config.yaml`:

```yaml
catalog:
  rules:
    - allow: [Template]
  locations:
    - type: url
      target: https://<repository_url/template-name>.yaml
```

Verify: Catalog > Kind: Template.

## TechDocs

Docs-as-code documentation rendered inside the portal. Prerequisites: TechDocs
plugin enabled, documentation imported, required roles/permissions.

### Search and Filter

- Search bar for keywords within documents
- Filter by: Owner, Tags, Starred, Owned

### Navigation

- Table of contents for section jumping
- Navigation menu for switching between documents in same book
- Next button for sequential reading
- Add-ons for additional actions (text size, etc.)

## API Browser

### Browsing APIs

Navigate via left sidebar > APIs, or Catalog > Kind: API. View Definition tab
for rendered specification (Swagger/AsyncAPI/GraphQL).

### Interactive Testing

1. Select API > Definition tab.
2. Locate operation > click Try it out.
3. Enter parameters/request body.
4. Click Run.
5. Examine Server response (status code, body, headers).

401/403 errors: verify credentials with API owner.

### Supported Formats

- **OpenAPI**: RESTful APIs, interactive documentation with request execution
- **AsyncAPI**: event-driven architectures, message schemas, broker details
- **GraphQL**: schema exploration including queries, mutations, types

Format support depends on instance configuration and enabled plugins.

## Global Search

Unified search indexes the entire software ecosystem. Real-time suggestions
categorize matches by entity types (Components, APIs, TechDocs, Users).

### Filtering

- Kind: Component, API, Template, Group
- Type: service, library, website
- Lifecycle: production, experimental, deprecated

## Developer Lightspeed for RHDH

Generative AI assistant integrated into RHDH for platform questions, log
analysis, code generation, and test plans.

### Features

- **Thinking cards**: expandable reasoning display with pulse animation
- **Tool call transparency**: MCP tool call details in expandable cards
- **RAG citations**: appear only when AI uses internal documentation
- **Context preservation**: new conversation on model change, history preserved
- **Display modes**: Overlay, Dock to window, Fullscreen (bookmarkable URL)
- **File attachments**: `.yaml`, `.json`, `.txt` via (+) icon in prompt bar
- **Chat management**: new chats, rename, pin, sort, delete, search history

### Safety Guards

Default: Llama Guard as safety shield. Override via custom `run.yaml`. Disable
via `run-no-guard.yaml` (development environments only).

### Notebooks (Developer Preview)

Isolated research workspaces for private knowledge base creation. Upload files
(`.txt`, `.md`, `.pdf`, `.docx`, `.log`, `.yaml`, `.json`) for AI grounding.

Constraints: 20MB per file, 100k tokens per session, no scanned PDFs/audio/
video/images.

### Best Practices

- Specify technologies in queries
- Include environment context
- Use conversation context for refinement
- Validate with documentation citations
- Rate responses for model tuning
- Do not include sensitive data in queries

## Extensions

### Global Plugins

Platform-wide tools in left sidebar: Tech Radar, Cost Insights, Developer
Lightspeed, Learning Paths.

### Entity Plugins

Per-component tabs: CI/CD (Jenkins, GitHub Actions), Kubernetes (pod health),
Topology (resource relationships).

### Marketplace

Left sidebar > Extensions. Categories: Installed, Available. End users cannot
install plugins; request via administrator.

## Interface Customization

### Settings

- **Theme**: Light, Dark, Auto (syncs with OS preference)
- **Language**: preferred interface language
- **Pin Sidebar**: keep left navigation expanded (default: enabled)

### Profile

- View User Entity and verify identity
- Toggle between Direct Relations (explicit ownership) and Aggregated Relations
  (inherited through groups)

## Starred Items

Star components in Catalog via Actions column star icon. View starred items on
Home page (Your Starred Entities card) and via Starred Items in Global Header.
