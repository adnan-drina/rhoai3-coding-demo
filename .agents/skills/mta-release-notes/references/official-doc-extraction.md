# Official Doc Extraction

Use this extraction to keep Migration Toolkit for Applications release
information grounded in the official Red Hat MTA 8.1 release notes. All feature
names, issue IDs, and behavioral changes are taken directly from the official
documentation.

## Introduction

The Migration Toolkit for Applications (MTA) is a set of tools to accelerate
large-scale application modernization across hybrid cloud environments on Red
Hat OpenShift. MTA provides inventory, assessment, analysis, and management of
applications for faster migration to OpenShift at both portfolio and application
levels.

## MTA 8.1.0

### New Features and Enhancements

#### Centralized Configuration Management

Profiles contain analysis configuration that allows organizations to
standardize configuration and simplify management by adopting a platform
engineering approach. Applicable across:

- User interface (UI)
- Command-line interface (CLI)
- Visual Studio Code MTA extension

Architects can create, update, and delete profiles and custom rules. Migrators
sync with MTA Hub to download configuration bundles and use them for analysis.

#### LLM Proxy Service

Client endpoints (e.g., MTA VS Code extension) can use the proxy service to
access large language models. Authentication flow:

1. Client uses Keycloak credentials to authenticate to MTA Hub
2. Client sends JWT issued by Keycloak to the proxy service
3. Proxy validates client JWT against Hub's Keycloak instance
4. Proxy authenticates to LLM using cluster secret with LLM API key

Allows administrators to create, manage, and rotate LLM API keys without
sharing keys with multiple client endpoints.

### Developer Preview Features

#### C# Provider

External `csharp` provider for `source-only` mode analysis of C# source code.
Available in CLI, UI, and VS Code extension. Uses tree-sitter for parsing and
stack graph for analysis to find references to types, methods, classes, and
fields.

#### VS Code Extension Pack

MTA VS Code extension consists of an analyzer RPC binary. Available as:

- Extension pack (bundles Core + all language extensions)
- Core extension + individual language extension

Supported language extensions: C#, Java, Javascript, Go.

### Known Issues (8.1.0)

| Issue | Description | Workaround |
|-------|-------------|------------|
| Gradle UI violations | MTA UI does not trigger violations for open source dependencies in `source+dependency` analysis of Gradle applications | Analyze Gradle apps using CLI instead |

### Fixed Issues (8.1.0)

| Issue | Description |
|-------|-------------|
| Source Control credentials | Creating credentials no longer fails when password exceeds 120-character limit; no maximum length enforced |
| Non-UTF-8 static report | Non-UTF-8 encoded source files display correctly in static reports |
| CF service bindings | MTA CLI correctly processes Cloud Foundry applications with service bindings; `VCAP_SERVICES` parsing fixed |

## MTA 8.0.1

### New Features and Enhancements

- **Pre-generated Maven index**: Bundled Maven index enables fast, low-memory
  lookups without network connection. Supports Java binary analysis in
  disconnected environments. (MTA-6231)

### Known Issues (8.0.1)

| ID | Issue | Workaround |
|----|-------|------------|
| MTA-6262 | Assessment form selects wrong option with custom questionnaire | Ensure unique `order` numbers in `answers` section |
| MTA-6211 | UI Gradle `source+dependency` violations missing | Use CLI for Gradle apps |
| MTA-6424 | UI fails to process CF apps with service bindings | Use CLI for CF discovery |
| MTA-6402 | `METHOD_CALL`/`CONSTRUCTOR_CALL` rules with params don't match | No workaround |

### Fixed Issues (8.0.1)

| ID | Description |
|----|-------------|
| MTA-6357 | Binary analysis correctly classifies open source dependencies |
| MTA-6271 | CF import allows specifying organizations |
| MTA-6399 | CLI processes CF apps with service bindings |
| MTA-6282 | Imported CF apps get automatic `Cloud Foundry` tag |
| MTA-6120 | Architects can import CF apps from Application Inventory |
| MTA-6230 | Concurrent Developer Lightspeed usage no longer causes race conditions |
| MTA-6195 | FQNs used in ANNOTATION rules to match annotations |
| MTA-4027 | Rules match wildcard import statements |
| MTA-6263 | Secure SVN application editing works correctly |
| MTA-6141 | Language and tech discovery works for Java apps in SVN |
| MTA-6105 | Source repository URL shown without repository type selection |
| MTA-6143 | Custom questionnaire assessment can be completed |
| MTA-6029 | Multiple custom rules upload detected simultaneously |

## MTA 8.0.0

### New Features and Enhancements

- **Developer Lightspeed for MTA**: AI-assisted code resolution using RAG in
  VS Code extension. Uses solved examples and source code context for migration
  issue resolution. Requires Red Hat Advanced Developer Suite (RHADS)
  subscription.
- **Solution Server (Technology Preview)**: Builds collective memory of code
  changes across an organization. Provides contextual hints and migration
  success metrics.
- **Agentic AI (Technology Preview)**: Iterative resolution mode where
  Developer Lightspeed makes fixes, then scans for diagnostic/linting issues
  introduced by accepted solutions.
- **Platform awareness**: Discover and import applications from Cloud Foundry
  platform instances into MTA application inventory. (MTA-4846)
- **Asset generation**: Generate deployment assets (Helm templates) for
  OpenShift/Kubernetes from discovery manifests. (MTA-4847)
- **CLI live discovery**: Perform live discovery of apps in remote CF clusters.
- **CLI conceal sensitive data**: `mta-cli discover cloud-foundry
  --conceal-sensitive-data` conceals services and Docker credentials.
- **Analysis insights in UI**: View technology usage insights from UI without
  needing static reports. (MTA-5420)
- **New VS Code IDE plugin**: GenAI-enabled by default; can be disabled for
  standard analysis. (MTA-5360)
- **Default credentials in UI**: Define default Maven or source control
  credentials for bulk application imports. (MTA-5254)

### Technology Preview Features (8.0.0)

- Solution Server for Developer Lightspeed
- Agentic AI in Developer Lightspeed

### Removed Features (8.0.0)

- **XML rules**: Removed and no longer supported in UI or CLI. (MTA-5357)
- **Eclipse IDE plugin**: Removed; use VS Code extension instead.

### Known Issues (8.0.0)

| ID | Issue | Workaround |
|----|-------|------------|
| MTA-6125 | CLI analysis fails with "invalid header line" | Clear `.metadata` and Maven cache |
| MTA-6129 | Analysis result unchanged after adding/removing custom rule | Restart analyzer process |
| MTA-6195 | ANNOTATION location rules don't match on FQNs | No workaround |
| MTA-6204 | Developer Lightspeed DB connection error under load | Set idle session timeout on kai-db |

### Fixed Issues (8.0.0)

| ID | Description |
|----|-------------|
| MTA-5793 | Default `values.yaml` merged with discover `values.yaml` for Helm |
| MTA-4033 | CLI detects Gradle dependencies in containerless mode |
| MTA-5907 | UI analyzes Gradle 7+ projects successfully |
| MTA-6030 | Discovery manifest lists all web process types |
