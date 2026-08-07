# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Migration Toolkit for Applications |
| Version | 8.2 |
| Documentation category | Using the Tools |
| Official guide | Configuring and using the Visual Studio Code Extension for MTA |
| Source URL | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.2/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.2/html/configuring_and_using_the_visual_studio_code_extension_for_mta/index |
| Capture date | 2026-07-06 |

## Captured Sections

From Configuring and using the Visual Studio Code Extension for MTA:

- Chapter 1: Introduction to the MTA extension for Microsoft Visual Code
  (capabilities: analyze projects, mark issues, provide guidance, automatic
  code replacement; VS Codespaces compatibility)
- Chapter 2: Installing the MTA extension for Visual Studio Code (extension
  pack vs core + language plugin, supported languages — Java GA; C#,
  JavaScript, Go Developer Preview; JDK 17+ prerequisite; macOS maxproc;
  Marketplace installation)
- Chapter 3: Configuring and using the MTA analyzer RPC binary (auto-download,
  restricted network manual configuration, three methods to set analyzer path)
- Chapter 4: Configuring the IDE settings (log level, analyzer path, debug
  webview, solution server settings, GenAI settings; settings access methods)
- Chapter 5: Configuring the MTA profile settings (label selector for
  source/target technologies, profile creation, custom rule selection; analysis
  view page)
- Chapter 6: Running an application analysis (RPC server start, analysis
  execution; C#/.NET prerequisites — dotnet tools, ilspycmd, paket)
- Chapter 7: Running an application analysis by using a profile (Technology
  Preview; Hub connection, profile sync, SSL verification, authentication,
  LLM proxy, `.konveyor/profiles` storage)
- Chapter 8: Reviewing and resolving migration issues (severity icons —
  mandatory vs optional, right-click > Open Code, Mark as Complete, Delete)

## Source Boundaries

This skill covers the MTA VS Code extension guide only. It provides procedures
for installing, configuring, and using the MTA extension in Visual Studio Code
for application analysis and issue resolution. It does not cover:

- MTA CLI usage (separate CLI guide, use mta-cli skill)
- MTA web UI configuration and usage (use mta-ui skill)
- IntelliJ plugin configuration and usage (use mta-intellij skill)
- Developer Lightspeed AI features (use mta-lightspeed skill)
- MTA installation and operator deployment (separate Installation guide)
- Custom rule authoring syntax details (separate Rules guide)
- MTA REST API reference
- MTA architecture internals

## Platform Documented

| Platform | Notes |
|----------|-------|
| VS Code / VS Codespaces | Primary IDE target |
| Red Hat OpenShift Container Platform | Hub connection target |

## Related Official Sources To Add Later

- MTA CLI Guide (mta-cli skill)
- MTA UI Guide (mta-ui skill)
- MTA IntelliJ Plugin Guide (mta-intellij skill)
- Developer Lightspeed Guide (mta-lightspeed skill)
- MTA Installation Guide
- MTA Rules Development Guide
