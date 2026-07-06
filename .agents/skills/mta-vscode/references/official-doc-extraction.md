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
