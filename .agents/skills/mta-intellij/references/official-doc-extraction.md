# Official Doc Extraction

Use this extraction to keep MTA IntelliJ IDEA plugin content grounded in
official Red Hat sources. When implementation needs exact CLI paths or plugin
configuration, verify against the actual MTA release and IntelliJ version.

## Product Overview

The Migration Toolkit for Applications (MTA) IntelliJ IDEA plugin analyzes
application projects using customizable rulesets. It marks issues directly in
the source code, provides guidance to fix them, and offers automatic code
replacement (Quick Fix) where possible. Both the Community Edition and
Ultimate version of IntelliJ IDEA are supported.

MTA is an extensible, rule-based tool that simplifies migration and
modernization of Java applications. It examines application artifacts including
project source directories and application archives, then produces an HTML
report highlighting areas needing changes.

## Prerequisites

| Requirement | Detail |
|-------------|--------|
| JDK | Oracle JDK 17+, Eclipse Temurin JDK 17+, or OpenJDK 17+ |
| MTA CLI | Latest `mta-cli` binary from the MTA download page |
| IDE | IntelliJ IDEA Community Edition or Ultimate |

## Installation Procedure

1. In IntelliJ IDEA, click the **Plugins** tab on the Welcome screen.
2. Enter `migration toolkit for applications` in the Search field on the
   **Marketplace** tab.
3. Select the **migration toolkit for applications (MTA) by Red Hat** plugin
   and click **Install**.
4. The plugin is listed on the **Installed** tab.

## Run Configuration

### Configuration Fields

| Field | Description |
|-------|-------------|
| CLI | Path to the `mta-cli` executable (e.g., `$HOME/mta-cli-8.1.2.GA-redhat/bin/mta-cli`) |
| Input | Application file or directory to analyze (click **Add** to set) |
| Target | One or more target migration paths |
| Output | Location set automatically by the plugin |

### Creating a Configuration

1. Click the **migration toolkit for applications** tab on the left.
2. For a first configuration, the panel is displayed automatically.
3. For additional configurations, right-click an existing configuration and
   select **New configuration**.
4. Fill in CLI, Input, and Target fields.

### Running an Analysis

1. In the configuration list, right-click the configuration and select
   **Run Analysis**.
2. The **Console (MTA)** terminal emulator opens showing analysis progress.
3. When the analysis completes, two options appear below the configuration name:
   - **Report**: opens the MTA HTML report describing migration issues
   - **Results**: opens a directory displaying hints (issues) per application

## Analysis Results Structure

Results are displayed in a directory format showing hints and classifications
for each application analyzed.

### Hints

A hint is a read-only snippet of code that contains a single issue to address
before migration. Often a Quick Fix is suggested which can be accepted or
ignored.

### Classifications

A classification is a file that has an issue but does not have any suggested
Quick Fixes. Classifications can be edited directly.

### Severity Icons

| Icon | Meaning |
|------|---------|
| Mandatory (error) | Must fix for migration or modernization to succeed |
| Optional (warning) | Might need to fix for migration or modernization |

## Resolving Issues

### Quick Fix Workflow

1. In the left pane, click a hint that has an error indicator.
2. Quick Fixes are displayed as child folders with the Quick Fix icon.
3. Right-click a Quick Fix and select **Preview Quick Fix** to see the current
   code alongside the suggested change.
4. To accept the fix, click **Apply Quick Fix**.
5. Optionally, right-click the issue and select **Mark As Complete** to display
   the green check mark indicator.

### Editing Classifications

1. In the left pane, click the file under the **Classifications** section.
2. Make changes to the code and save the file.
3. Optionally, right-click the issue and select **Mark as Complete** or
   **Delete**.

## Supported Migration Paths

| From | To |
|------|----|
| Oracle WebLogic | Red Hat JBoss EAP |
| IBM WebSphere Application Server | Red Hat JBoss EAP |
| Earlier JBoss EAP | Latest JBoss EAP |
| Java Spring Boot | Quarkus |
| Oracle JDK | OpenJDK |
| OpenJDK 8 | OpenJDK 11 |
| OpenJDK 11 | OpenJDK 17 |
| OpenJDK 17 | OpenJDK 21 |
| JBoss EAP Java applications | Azure |
| Spring Boot Java applications | Azure |
| Traditional applications | Containerized / cloud-ready |
