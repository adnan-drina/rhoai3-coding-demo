---
name: mta-ui
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "mta"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Application Modernization"
description: >
  Use when using the MTA web UI for application assessment, analysis,
  migration waves, and issue management. Do NOT use for CLI (use mta-cli),
  VS Code (use mta-vscode), IntelliJ (use mta-intellij), or AI features
  (use mta-lightspeed).
---

# MTA User Interface

Use this skill to ground Migration Toolkit for Applications (MTA) 8.2
web UI guidance in the official Configuring and Managing the MTA User
Interface guide. The MTA UI enables portfolio-level and application-level
assessment, analysis, tagging, migration wave management, and deployment
asset generation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official
Red Hat documentation is product authority.

## Key UI Capabilities

### Instance Configuration (Ch 2)

Configure the MTA environment before running assessments or analyses:

- **Credentials**: source control (username/password or SCM key),
  Maven settings file, proxy, Jira (basic auth or bearer token)
- **Repositories**: Git or Subversion for source code and custom rules
- **Proxy**: HTTP/HTTPS proxy settings with exclusion lists
- **Custom migration targets**: reusable targets with custom rulesets
- **Issue management**: Jira integration for tracking migration issues
- **Assessment questionnaires**: import/export YAML questionnaires

### Instance Setup (Ch 3)

Create organizational entities: stakeholders, stakeholder groups,
business services, job functions, and tag categories/tags.

### Jira Integration (Ch 4)

Connect MTA to Jira instances (Cloud, Server, or Datacenter) for
migration wave issue tracking. Supports basic auth and bearer token.

### Application Management (Ch 5)

- Add applications manually or import via CSV
- Assign credentials and configure source code / binary locations
- Create migration waves with stakeholder groups and date ranges
- Create Jira issues for migration wave tracking

### Assessment (Ch 6)

- Legacy Pathfinder default questionnaire (5 sections, risk-based)
- Custom YAML questionnaires with conditional questions, auto-tagging,
  and automated answers
- Assessment reports: identified risks, adoption candidate distribution,
  suggested adoption plan, application confidence

### Tagging (Ch 7)

- Manual and automatic tagging; tag categories and tags
- Analysis-based auto-tagging from language and technology discovery

### Archetypes (Ch 8)

Group applications by shared characteristics (criteria tags,
archetype tags, stakeholders). Applications inherit assessment and
review from assigned archetypes.

### Analysis Profiles (Ch 9, Technology Preview)

Centralized configuration management for analysis profiles with
custom rules, migration targets, and scope settings. Profiles sync
from the MTA Hub to UI, CLI, and VS Code extension.

### Application Analysis (Ch 10)

- Analysis modes: binary, source code, source code + dependencies,
  local binary upload
- Migration targets: JBoss EAP 7/8, containerization, Quarkus,
  OpenJDK 11/17/21, Linux, Jakarta EE 9, Spring Boot, Open Liberty,
  Camel, Azure App Service
- Scope: app only, app + dependencies, manual package list, exclude
- Custom rules: manual upload or Git/Subversion repository
- Reports: issues by category, effort estimates, affected files

### Task Manager (Ch 11)

View, filter, cancel, and review logs for analysis and language/
technology discovery tasks.

### Platform Awareness (Ch 12)

Import applications from Cloud Foundry source platform instances.
Discover applications by organization, space, and name filters.
Generate discovery manifests for imported applications.

### Asset Generation (Ch 13)

Generate deployment assets (Helm-based) for migrating CF applications
to OpenShift or Kubernetes. Requires: generators (template repos),
target profiles, archetypes, and discovery manifests.

## UI Views

| View | Purpose |
|------|---------|
| Migration | Application inventory, assessment, analysis, migration waves |
| Administration | Credentials, repositories, proxy, stakeholders, tags, Jira, generators, source platforms |

## Workflow

1. Confirm the target MTA version (8.2) and deployment type.
2. Read `references/official-doc-extraction.md` for UI procedures.
3. Identify the task: configuration, assessment, analysis, migration
   wave, platform awareness, or asset generation.
4. Follow the documented procedure; verify prerequisites.
5. Validate with `references/source-capture.md` boundaries.

## Related Skills

- Use `mta-vscode` for the VS Code extension.
- Use `mta-cli` for the MTA command-line interface.
- Use `mta-intellij` for the IntelliJ plugin.
- Use `mta-lightspeed` for Developer Lightspeed AI features.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
