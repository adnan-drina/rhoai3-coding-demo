---
name: mta-intellij
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "mta"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Application Modernization"
description: >
  Use when using the MTA IntelliJ IDEA plugin for analyzing applications and
  resolving migration issues, including installation, run configuration, issue
  review, and Quick Fix resolution. Do NOT use for CLI analysis (use mta-cli),
  web UI workflows (use mta-ui), VS Code plugin (use mta-vscode), AI-assisted
  resolution (use mta-lightspeed), or custom rule authoring (use mta-rules).
---

# MTA IntelliJ IDEA Plugin

Use this skill to ground Migration Toolkit for Applications (MTA) 8.2 IntelliJ
IDEA plugin guidance in the official IntelliJ IDEA Plugin Guide. The MTA plugin
analyzes projects using customizable rulesets, marks issues in source code,
provides guidance to fix issues, and offers automatic code replacement where
possible.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official
Red Hat documentation is product authority.

## Plugin Overview

The MTA plugin for IntelliJ IDEA supports both the Community Edition and
Ultimate version. It analyzes application source code using the MTA CLI engine
and customizable rulesets, producing migration reports and inline issue markers
in the IDE.

### What MTA Analyzes

MTA examines application artifacts including project source directories and
application archives and produces reports highlighting areas needing changes.
Supported migration paths include:

- Upgrading to the latest Red Hat JBoss EAP release
- Migrating from Oracle WebLogic or IBM WebSphere to JBoss EAP
- Containerizing applications and making them cloud-ready
- Migrating from Java Spring Boot to Quarkus
- Updating from Oracle JDK to OpenJDK
- Upgrading between OpenJDK versions (8 to 11, 11 to 17, 17 to 21)
- Migrating JBoss EAP or Spring Boot Java applications to Azure

## Prerequisites

- Java Development Kit (JDK) 17 or later (Oracle JDK, Eclipse Temurin, or
  OpenJDK)
- Latest `mta-cli` binary from the MTA download page
- IntelliJ IDEA (Community Edition or Ultimate)

## Installation

1. In IntelliJ IDEA, click the **Plugins** tab on the Welcome screen.
2. Enter `migration toolkit for applications` in the Search field on the
   **Marketplace** tab.
3. Select the **migration toolkit for applications (MTA) by Red Hat** plugin
   and click **Install**.
4. The plugin appears on the **Installed** tab.

## Workflow

### Creating a Run Configuration

1. Click the **migration toolkit for applications** tab on the left side.
2. If this is the first configuration, the run configuration panel is displayed.
   Otherwise, right-click a configuration and select **New configuration**.
3. Complete configuration fields:
   - **CLI**: path to the `mta-cli` executable (e.g.,
     `$HOME/mta-cli-8.1.2.GA-redhat/bin/mta-cli`)
   - **Input**: click **Add** and enter the input file or directory
   - **Target**: select one or more target migration paths
4. Right-click the new configuration and select **Run Analysis**.
5. The **Console (MTA)** terminal emulator opens, showing analysis progress.
6. When complete, click **Report** (opens HTML report) or **Results** (opens
   hints directory).

### Reviewing Issues

Results display in a directory format with hints and classifications per
application analyzed.

- **Hint**: read-only code snippet with a single issue, often with a Quick Fix
- **Classification**: file-level issue without Quick Fix suggestions

Severity icons:

- Mandatory: must fix for successful migration
- Optional: might need to fix for migration

### Resolving Issues

**Using Quick Fix:**

1. In the left pane, click a hint with an error indicator.
2. Quick Fixes appear as child folders with the Quick Fix icon.
3. Right-click a Quick Fix and select **Preview Quick Fix**.
4. To accept the fix, click **Apply Quick Fix**.
5. Optionally, right-click and select **Mark As Complete**.

**Editing classifications directly:**

1. Click the file in the Classifications section.
2. Make changes to the code and save.
3. Optionally, mark the issue as complete or delete it.

## Related Skills

- Use `mta-rules` for creating custom analysis rules.
- Use `mta-cli` for command-line analysis workflows.
- Use `mta-ui` for web console analysis workflows.
- Use `mta-vscode` for VS Code plugin workflows.
- Use `mta-lightspeed` for AI-assisted code resolution.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
