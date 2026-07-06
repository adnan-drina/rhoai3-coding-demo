# Official Doc Extraction

Use this extraction to keep MTA UI content grounded in official Red Hat
sources. When implementation needs exact fields or operator configuration,
verify against the actual cluster state before authoring manifests.

## Product Overview

Migration Toolkit for Applications (MTA) is a set of tools that you can use
to accelerate large-scale application modernization efforts across hybrid
cloud environments on Red Hat OpenShift. The MTA user interface provides
portfolio-level and application-level assessment, analysis, and migration
management capabilities.

## Instance Environment Configuration

### Credential Types

| Type | Fields |
|------|--------|
| Source Control | Username/Password or SCM Private Key/Passphrase |
| Maven Settings File | Upload or paste `settings.xml` content |
| Proxy | HTTP and HTTPS proxy host, port, credentials |
| Basic Auth (Jira) | Username and password |
| Bearer Token (Jira) | Token value |

Credentials can be set as defaults. Maven credentials not assigned before
analysis may impact quality and performance.

### Repository Configuration

- Git and Subversion repositories for consuming and managing MTA custom rules
- Consumed repositories: used by MTA during analysis
- Custom migration target repositories: host custom rulesets

### Proxy Settings

Configure HTTP and HTTPS proxy with host, port, and optional identity
(credentials). Exclude specific hosts via exclusion list.

### Custom Migration Targets

Create reusable migration targets with custom rulesets:
- Upload custom rules manually
- Reference rules from a Git or Subversion repository
- Assign source and target technologies via label selectors
- Associate image for identification

## Instance Setup

### Organizational Entities

| Entity | Purpose |
|--------|---------|
| Stakeholders | People involved in migration decisions |
| Stakeholder groups | Logical groupings of stakeholders |
| Business services | Application purposes and ownership |
| Job functions | Roles within the organization |
| Tag categories | Groups of related tags |
| Tags | Classifiers for applications and archetypes |

## Jira Integration

### Supported Jira Types

| Type | Authentication |
|------|----------------|
| Jira Cloud | Bearer token or basic auth |
| Jira Server | Basic auth or bearer token |
| Jira Datacenter | Basic auth or bearer token |

Connection requires: instance name, URL, type selection, and credentials.
MTA creates tracker issues for migration wave management.

## Application Management

### Application Attributes

- Name (required), Description, Business service, Tags, Owner,
  Contributors, Source code (repo type, URL, branch, root path),
  Binary (Maven group, artifact, version, packaging)

### CSV Import Format

Required column: `Record Type 1` (application name). Optional columns:
description, comments, business service, dependency (direction, name),
tag type, tag.

### Migration Waves

- Date range (start date, end date)
- Associated stakeholder groups and stakeholders
- Applications assigned from inventory
- Maximum one Jira tracker per wave

## Assessment

### Default Questionnaire

Legacy Pathfinder — 5 sections:
1. Application details (team knowledge, dependencies, development model)
2. Application dependencies (internal/external dependencies, impact)
3. Application architecture (execution environment, packaging, state)
4. Application observability (logging, monitoring, health checks)
5. Application cross-cutting concerns (security, compliance, lifecycle)

Risk levels: green (low), amber (medium), red (high), unknown.

### Custom Questionnaires

YAML-based with support for:
- `thresholds`: red and yellow percentage thresholds for risk calculation
- `riskMessages`: messages per risk category (green, amber, red, unknown)
- Conditional questions (include/exclude by tag presence)
- Auto-tagging based on answers
- Section-level ordering

### Assessment Reports

- Identified risks (high/medium/low/unknown)
- Adoption candidate distribution (suggested, not recommended, etc.)
- Suggested adoption plan
- Application confidence score

## Tagging

### Tag Lifecycle

- Create tag categories and tags in Administration view
- Manual tagging: Migration view > Application > kebab > Manage tags
- Automatic tagging: enabled by default during analysis; includes
  language discovery and technology discovery

## Archetypes

- Defined by criteria tags (match applications) and archetype tags
- Applications inherit assessments and reviews from archetypes
- Used for grouping assessment and asset generation

## Analysis Profiles (Technology Preview)

Analysis profiles centralize configuration management:
- Created by Architects in the MTA Hub
- Synced to UI, CLI, and VS Code extension
- Contain: analysis mode, scope, targets, custom rules, label selectors
- Profiles stored in `.konveyor/profiles` when synced to client tools
- Hub connection settings: URL, SSL verification, authentication

## Application Analysis

### Analysis Modes

| Mode | Description |
|------|-------------|
| Binary | Analyze compiled binary |
| Source code | Analyze source code only |
| Source code and dependencies | Analyze source and dependency code |
| Upload a local binary | Upload and analyze a local binary file |

### Migration Targets

JBoss EAP 7, JBoss EAP 8, Containerization, Quarkus, OracleJDK to
OpenJDK, OpenJDK 11/17/21, Linux, Jakarta EE 9, Spring Boot on Red Hat
Runtimes, Open Liberty, Camel (2→3, 3→4), Azure App Service.

### Analysis Scope Options

- Application and internal dependencies only
- Application and all dependencies (including known OSS libraries)
- Manual package list selection
- Package exclusion list

### Custom Rules

- Manual upload (drag and drop)
- Repository mode (Git or Subversion)
- Optional: exclude rules by tag, set source technologies

### Analysis Output

- Issues categorized by severity (mandatory, optional)
- Effort estimates per issue
- Affected files with line-level markers
- Downloadable analysis reports
- Analysis insights with dependencies and technologies

## Task Manager

- View all running and completed tasks
- Filter by status, application, or task type
- Cancel running tasks
- Review task logs for troubleshooting

## Platform Awareness

### Source Platforms

Cloud Foundry (CF) is the supported source platform in MTA 8.0.0+.

### Discovery Workflow

1. Administrator creates CF source platform instance (name, type, API URL,
   credentials) in Administration view
2. Discover applications by organization, space, and name filters
3. Applications imported to Application Inventory
4. Generate discovery manifests per application or in bulk
5. Discovery manifests contain platform and runtime configurations

### Discovery in Both Views

- Administration view: Source platforms > Options > Discover applications
- Migration view: Options menu near Analyze > Discover applications

## Asset Generation

### Entities

| Entity | Purpose |
|--------|---------|
| Generator | Uses Helm templating engine with template repository |
| Target profile | Represents target platform; contains sequence of generators |
| Archetype | Groups applications by criteria tags; links to target profile |
| Asset repository | Git/Subversion repo where generated assets are stored |

### Workflow

1. Configure generator with Helm template repository
2. Create target profile with one or more generators
3. Configure archetype with criteria tags and target profile
4. Configure asset repository on applications
5. Generate assets from discovery manifest or implicit application data
6. Assets pushed to configured repository
