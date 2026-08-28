---
name: mta-vscode
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "mta"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Application Modernization"
description: >
  Use when using the MTA VS Code extension for identifying and resolving
  migration issues in the IDE. Do NOT use for CLI (use mta-cli), UI
  (use mta-ui), IntelliJ (use mta-intellij), or AI features (use
  mta-lightspeed).
---

# MTA VS Code Extension

Use this skill to ground Migration Toolkit for Applications (MTA) 8.2
VS Code extension guidance in the official Configuring and Using the
Visual Studio Code Extension for MTA guide. The extension enables
in-IDE application analysis, issue identification, and guided code
remediation for migration and modernization.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official
Red Hat documentation is product authority.

## Key Extension Capabilities

### Installation (Ch 2)

Install the MTA extension pack or MTA Core extension with a
language-specific plugin from the VS Code Marketplace:

| Extension | Language | Support Level |
|-----------|----------|---------------|
| MTA Core + Java | Java | GA |
| Extension Pack | All languages | Developer Preview |
| MTA Core + C# | C# / .NET | Developer Preview |
| MTA Core + JavaScript | JavaScript / Node.js | Developer Preview |
| MTA Core + Go | Go | Developer Preview |

Prerequisites: JDK 17+ (Oracle, Eclipse Temurin, or OpenJDK).
macOS requires `maxproc >= 2048`.

### Analyzer RPC Binary (Ch 3)

The extension downloads the analyzer RPC binary automatically. In
restricted networks, configure the binary path manually:

- Extension settings: `Analyzer Path` field
- `settings.json`: `mta-vscode-extension.analyzerPath`
- Command Palette: `MTA: Override Analyzer Binary`

### IDE Settings (Ch 4)

- **Log level**: controls MTA binary verbosity (default: `debug`)
- **Analyzer path**: custom binary location
- **Debug: Webview**: enables debug logging for Webview messages

### Profile Configuration (Ch 5)

Configure analysis profiles before running analysis:

- **Label selector**: filter rules by source/target technology
- **Profile**: reusable analysis configuration
- **Rules**: enable default rules, add custom rules

Source or target technology must be configured before analysis.

### Running Analysis (Ch 6)

Run static code analysis using the RPC server:

1. Configure analysis profile on MTA Analysis View page
2. Select profile and click Start to launch RPC server
3. Click Run Analysis

For C#/.NET analysis, requires: `dotnet tools`, `ilspycmd`, `paket`.

### Hub-Based Analysis Profiles (Ch 7, Technology Preview)

Connect to MTA Hub for centralized profile management:

- Enable Hub and enter MTA UI URL
- Optional: skip SSL verification, enable authentication
- Profiles and custom rules downloaded to `.konveyor/profiles`
- Profile Sync keeps profiles updated from Hub
- LLM proxy available when administrator deploys it in cluster

### Reviewing and Resolving Issues (Ch 8)

Issue severity icons:
- Mandatory: must fix for successful migration
- Optional: might need addressing during migration

Resolution workflow:
1. Right-click issue > Open Code to navigate to affected file
2. Edit code and save
3. Optional: Mark as Complete or Delete resolved issues

## Supported Languages

| Language | Extension | Status |
|----------|-----------|--------|
| Java | MTA Core (built-in) | GA |
| C# / .NET | C# extension | Developer Preview |
| JavaScript / Node.js | JavaScript extension | Developer Preview |
| Go | Go extension | Developer Preview |

## Workflow

1. Confirm the target MTA version (8.2).
2. Read `references/official-doc-extraction.md` for extension procedures.
3. Identify the task: installation, configuration, analysis, issue
   resolution, or Hub connection.
4. Follow the documented procedure; verify prerequisites.
5. Validate with `references/source-capture.md` boundaries.

## Related Skills

- Use `mta-ui` for the MTA web UI.
- Use `mta-cli` for the MTA command-line interface.
- Use `mta-intellij` for the IntelliJ plugin.
- Use `mta-lightspeed` for Developer Lightspeed AI features.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
