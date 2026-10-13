# Current Verified Guidance — MTA 8.3

Reviewed 2026-10-13 in the public Red Hat documentation browser. Sources:

- https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index

## Current decisions
- The 8.3 guide documents MTA Core plus a language extension, or an extension pack. The extension pack and C#/JavaScript/Go extensions are Developer Preview; Java and Core have their documented support posture.
- Prerequisites include JDK 17+ and 8 GB RAM. The analyzer RPC binary is distinct from mta-cli and the extension package.
- For restricted/pinned workspaces, configure `mta-vscode-extension.analyzerPath` or MTA: Override Analyzer Binary to the reviewed RPC binary, then reload the window and validate an analysis. Default behavior downloads the latest RPC; do not use that behavior to qualify a reproducible run.
- The guide's installation example is 8.3.0; the independently selected extension patch must be verified from its package metadata. Do not assume it equals the CLI patch version.
- Configure Hub OIDC, trust the certificate chain, synchronize the intended profile and keep source/target/rule settings explicit. Skip SSL verification is an optional insecure mode, not this project's recommendation.
- Check extension output and analyzer logs as well as diagnostics. AI usage follows mta-lightspeed and the private MaaS path.

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

Use this extraction to keep MTA VS Code extension content grounded in official
Red Hat sources. When implementation needs exact settings keys or configuration
details, verify against the actual extension and cluster state.

## Product Overview

The MTA extension for Visual Studio Code accelerates large-scale application
modernization across hybrid cloud environments on Red Hat OpenShift. It
performs static code analysis to identify migration issues and provides
in-IDE guidance and automatic code replacement where possible.

The extension is compatible with Visual Studio Codespaces (Microsoft
cloud-hosted development environment).

## Installation

### Extension Options

| Option | Contents | Use Case |
|--------|----------|----------|
| Extension Pack | Core + all language plugins | Analyze in all supported languages (Developer Preview) |
| Core + Java | MTA Core extension | Java analysis (GA) |
| Core + C# | MTA Core + C# extension | C# / .NET analysis (Developer Preview) |
| Core + JavaScript | MTA Core + JavaScript extension | JavaScript / Node.js analysis (Developer Preview) |
| Core + Go | MTA Core + Go extension | Go analysis (Developer Preview) |

### Prerequisites

- JDK 17 or later (Oracle JDK, Eclipse Temurin, or OpenJDK)
- macOS: `maxproc` set to 2048 or greater
- C# analysis: `dotnet tools` in `$PATH`, `ilspycmd` CLI, `paket`
  package manager

### Installation Source

Install MTA 8.1.2 Visual Studio Code plugin from the VS Code Marketplace.

## Analyzer RPC Binary

The MTA extension uses an analyzer RPC binary to perform analysis. On
installation, the extension downloads the latest version from the Red Hat
Developer portal automatically.

### Restricted Network Configuration

Three methods to set the local binary path:

1. Extension settings > `Analyzer Path` field
2. `settings.json` > `mta-vscode-extension.analyzerPath`
3. Command Palette > `MTA: Override Analyzer Binary`

## IDE Settings

Access settings via:
- `Extensions` > `MTA Extension for VSCode` > `Settings`
- Command Palette > `Preferences: Open Settings (UI)` > `Extensions` > `MTA`

### Available Settings

| Setting | Description | Default |
|---------|-------------|---------|
| Log level | MTA binary log verbosity | `debug` |
| Analyzer path | Custom binary path | (auto-downloaded) |
| Debug: Webview | Debug logging for Webview messages | disabled |

Additional setting categories: Solution server settings, Generative AI
settings.

## Profile Configuration

### Analysis View Page

Open via:
- Book icon on `MTA: Issues` pane
- Command Palette > `MTA: Open Analysis View`

### Profile Settings

| Setting | Description | Required |
|---------|-------------|----------|
| Label selector | Filter rules by source/target technology | Yes (at least one target or source) |
| Profile | Reusable analysis configuration | Optional |
| Rules | Default rules + custom rules | Optional (custom) |

Custom rule names for new technologies can be typed to create new items.

## Running Analysis

### Standard Analysis

1. Configure profile on MTA Analysis View page
2. Click Start to launch the RPC server
3. Click Run Analysis on MTA Analysis View page

### C# / .NET Prerequisites

- MTA Core and C# extensions installed
- `dotnet tools` installed and in `$PATH`
- `ilspycmd` command line tool (ILSpy .NET decompiler)
- `paket` package manager

## Hub-Based Profiles (Technology Preview)

### Hub Configuration

| Setting | Description |
|---------|-------------|
| Enable Hub | Activate Hub connection |
| Hub URL | MTA user interface URL |
| Skip SSL certificate verification | Bypass local SSL cert check |
| Enable authentication | Log in with MTA UI credentials |
| Enable Solution Server | Suggest resolutions for issues |

### Profile Sync Behavior

- When enabled, MTA periodically downloads latest profiles from Hub
- Profiles and custom rules stored at `.konveyor/profiles` on disk
- Hub connection disables local profile manager options
- When profile sync enabled and LLM proxy deployed in cluster, MTA uses
  proxy service for LLM connection

### Authentication

Username and password credentials of the MTA user interface.

## Issue Review and Resolution

### Severity Icons

| Icon | Meaning |
|------|---------|
| Error (mandatory) | Must fix for successful migration |
| Warning (optional) | Might need addressing during migration |

### Resolution Workflow

1. In left pane, right-click issue > `Open Code` to navigate to file
2. Edit code at the indicated location and save
3. Optional: right-click issue > `Mark as Complete` or `Delete`

### Automatic Code Replacement

The extension performs automatic code replacement where possible. Issues
with available automatic fixes are indicated in the issue list.

## Settings JSON Keys

| Key | Type | Purpose |
|-----|------|---------|
| `mta-vscode-extension.analyzerPath` | string | Custom analyzer binary path |

## Command Palette Commands

| Command | Purpose |
|---------|---------|
| `MTA: Override Analyzer Binary` | Select local analyzer binary |
| `MTA: Open Analysis View` | Open the analysis configuration view |
