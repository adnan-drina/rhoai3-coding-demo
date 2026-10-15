---
name: mta-intellij
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: mta
  docs-version: "8.3"
  skill-group: "Application Modernization"
description: >
  Use only to find the official MTA 8.3 IntelliJ IDEA plugin documentation
  (install, run configuration, reviewing issues, Quick Fix). This repo does
  not use IntelliJ; workspaces run Code - OSS with the MTA VS Code
  extensions. Do NOT use for the workspace IDE (use mta-vscode), CLI analysis
  (use mta-cli), or rules (use mta-rules).
---

# MTA IntelliJ IDEA plugin (link-only stub)

## When to use

- A user asks about the MTA plugin for IntelliJ IDEA on a local machine.

## Not used in this repo

Dev Spaces workspaces run Code - OSS with the MTA VS Code extensions baked
into the workspace image (`stages/070-advanced-app-platform/workspace-image/artifacts.lock.json`,
`gitops/stages/070-advanced-app-platform/070-rhdh/templates/app-migration/skeleton/devfile.yaml`).
No IntelliJ plugin is installed or configured. Use `mta-vscode` for the
workspace IDE.

## Official documentation (MTA 8.3)

| Topic | Section |
|---|---|
| About the plugin | [About][about] |
| Install | [Install the plugin][install] |
| Run configuration | [Create a run configuration][run] |
| Issues | [Review issues][review], [Resolve issues][resolve], [Quick Fix][quickfix] |

## Related skills

`mta-vscode`, `mta-cli`, `mta-rules`.

[about]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/intellij_idea_plugin_guide/index#about-ide-addons_idea-plugin-guide
[install]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/intellij_idea_plugin_guide/index#intellij-idea-plugin-extension_idea-plugin-guide
[run]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/intellij_idea_plugin_guide/index#intellij-idea-plugin-run-configuration_idea-plugin-guide
[review]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/intellij_idea_plugin_guide/index#intellij-idea-plugin-reviewing-issues_idea-plugin-guide
[resolve]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/intellij_idea_plugin_guide/index#intellij-resolving-issues_idea-plugin-guide
[quickfix]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/intellij_idea_plugin_guide/index#using-quick-fix_intellij-resolving-issues
