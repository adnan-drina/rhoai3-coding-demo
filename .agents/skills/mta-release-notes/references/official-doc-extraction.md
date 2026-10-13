# Current Verified Guidance — MTA 8.3

Reviewed 2026-10-13 in the public Red Hat documentation browser. Sources:

- https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/release_notes/index

## Current decisions
- Latest release documented in this capture: 8.3.0. MTA Agents add single-agent and predetermined multi-stage workflows, sandbox execution and Git handoff continuity; both are Developer Preview.
- mta-ops adds same-cluster PVC StorageClass conversion, indirect S3 transfer, structured progress and an append-only audit log. AWS S3 is the validated indirect-transfer provider; other S3-compatible stores are not thereby qualified.
- BuildConfig-to-Shipwright conversion is Technology Preview. Developer Lightspeed, Solution Server and IDE Agent AI keep their own Technology Preview boundaries.
- The wildcard-import annotation analysis limitation MTA-6530 remains open in 8.3. A completed analyzer process is not proof that every annotation was discovered.
- MTA-6863 fixes applying unsaved code-review suggestions. MTA-7870 warns that mta-ops can continue without an audit file when the file cannot be opened; validate the file if the workflow requires an audit trail.
- Use the 8.3 chapter for current claims. Earlier 8.0–8.2 sections in the same release-notes book are historical, not features newly added in 8.3.

## Project workflow

Keep platform configuration in native Kustomize/Argo CD resources. Helm may be
used to render a pinned chart during authoring; do not install or upgrade a live
Helm release for this project. Keep credentials outside Git. Before any live
cluster access, use `load_env` and `check_oc_logged_in` from
`scripts/shared/lib.sh`; match the selected cluster and product schema.

## Earlier detailed reference — not a fresh product qualification

The material below retains the earlier extraction's provenance and useful
detail. Where a command, support level, version, default or field conflicts
with the current decisions above, the current decisions take precedence.
Verify any remaining version-sensitive detail against the current linked guide
and installed CLI/CRD before use. Historical runtime observations are not new
8.3 validation.

---

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
