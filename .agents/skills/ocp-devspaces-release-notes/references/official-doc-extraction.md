# Official Doc Extraction

Use this extraction to keep OpenShift Dev Spaces release information grounded in
the official Red Hat OpenShift Dev Spaces 3.28 release notes. All version
numbers, features, and behavioral changes are taken directly from the official
documentation.

## Platform Compatibility

| Field | Value |
|-------|-------|
| Product | Red Hat OpenShift Dev Spaces 3.28 |
| Upstream base | Eclipse Che 7.117 |
| Supported OCP | 4.16, 4.17, 4.18, 4.19, 4.20, 4.21, 4.22 |
| Architectures | AMD64/Intel 64 (x86_64), IBM Z (s390x), IBM Power (ppc64le), ARMv8 (arm64) |
| DevWorkspace Operator | 0.41.0 |
| VS Code - Open Source | 1.108.2 |

Supported IDEs: Microsoft Visual Studio Code - Open Source, JetBrains IntelliJ
IDEA Ultimate, PyCharm, WebStorm, RubyMine, CLion, GoLand, PhpStorm, Rider.

## Release Notes for 3.28.2

Cumulative release. Extends supported platform matrix to include OpenShift 4.22.
No separately documented new features beyond platform support. Incorporates all
3.28.0 and 3.28.1 content.

## Release Notes for 3.28.1

Stability and maintenance release. No separately documented features or fixes
beyond what is in the cumulative release notes.

## Release Notes for 3.28.0 (Initial GA)

### New Features and Enhancements

#### 2.1. GitHub App Support for Identity Management

OpenShift Dev Spaces now supports using a GitHub App, in addition to OAuth Apps,
for managing identities and authorizations. GitHub App tokens use application
permissions instead of token scopes, so token scope validation has been disabled
accordingly.

#### 2.2. OIDC Authentication Flow for Azure DevOps

Azure DevOps is deprecating its standard OAuth2 authentication flow. OpenShift
Dev Spaces now supports the newer OIDC (OpenID Connect) authentication flow for
Microsoft Azure DevOps. This ensures continued compatibility with Azure DevOps
for Git operations such as clone, push, and pull as Microsoft transitions away
from the legacy OAuth2 flow.

#### 2.3. Persistent User Home Enabled by Default

Persistent user home is now enabled by default in the CheCluster CR by using
`spec.devEnvironments.persistUserHome.enabled`. Non-ephemeral workspaces
automatically have a PVC mounted at `/home/user`.

#### 2.4. Visual Studio Code - Open Source Updated to 1.108.2

Visual Studio Code - Open Source ("Code - OSS") has been updated to the 1.108.2
upstream version.

#### 2.5. Workspace Backups Viewable from Dashboard

If backups are configured for OpenShift Dev Spaces, you can now view workspace
backups from the Dashboard in the Backups tab. Backups for both existing and
deleted workspaces are available. You can use workspace backups to recover
uncommitted code changes for workspaces that have been deleted from the cluster.
After you identify the backup, you can restore the workspace from the Dashboard.

#### 2.6. JetBrains Devfile Editing from IDE

If you use a JetBrains IDE over Gateway, you can now edit your cluster devfile
and apply the changes directly from the editor.

#### 2.7. Detect SCC Mismatch Warnings for DevWorkspaces

The Dashboard now detects and warns when a DevWorkspace Security Context
Constraint (SCC) configuration does not match the current server settings. This
typically occurs when container run capabilities are enabled after workspaces
have already been created. Affected workspaces display a warning icon with a
tooltip that explains the mismatch. Workspace startup is not blocked, but users
are informed that the workspace might fail because of the SCC configuration
change.

#### 2.8. Full IPv6 Support

The Dashboard now fully supports single-stack IPv6 environments, such as
OpenShift 4.20+ clusters. Previously, some URLs and API calls failed because of
incorrect handling of IPv6 addresses.

#### 2.9. CHOWN Capability for Container Run Mode

The `CHOWN` Linux capability is now added to the default security context for
workspace containers when container run mode is enabled, alongside the existing
`SETGID` and `SETUID` capabilities. This allows containers to change file
ownership, which is needed for nested container scenarios.

#### 2.10. PatternFly 6 Migration for User Dashboard

The User Dashboard has been migrated from PatternFly 5 to PatternFly 6. This
includes updated Layout, Card, and Form components with replaced CSS variables
and class names.

#### 2.11. New Automount Resource Management Features in DevWorkspace Operator 0.41.0

DevWorkspace Operator 0.41.0 introduces improvements to automount resource
management, including targeted mounting by workspace name, deferred mounting to
avoid workspace restarts, and PVC subdirectory mounting.

**Mount automount resources only to specific DevWorkspaces:**

Two new annotations allow administrators to control which DevWorkspaces receive
automounted ConfigMaps, Secrets, and PVCs by workspace name pattern:

- `controller.devfile.io/mount-to-devworkspace-include`: mount the resource only
  to workspaces whose names match the specified pattern
- `controller.devfile.io/mount-to-devworkspace-exclude`: mount the resource to
  all workspaces except those whose names match the specified pattern

When either annotation is set, the DevWorkspace Operator also watches the
annotated resource and triggers reconciliation of the targeted workspaces when
the resource changes.

**Prevent workspace restart when automount resources are created or modified:**

A new `controller.devfile.io/mount-on-start` annotation can be set on
automounted ConfigMaps, Secrets, and PVCs. When this annotation is set to
`"true"`, adding or modifying the resource will not immediately restart running
workspaces. The resource will be mounted the next time the workspace starts.

**Mount PVC subdirectory into workspace using subPath:**

Automounted PVCs now support mounting a subdirectory within the PVC using the
`subPath` field. This is configured by providing a JSON array as the value of
the `controller.devfile.io/mount-path` annotation, where each entry specifies
both a `path` (mount point in the container) and a `subPath` (subdirectory
within the PVC).

### Bug Fixes

#### 3.1. Advanced Authorization with Special Characters

Before this update, usernames or group names containing commas would break the
advanced authorization configuration because commas were hardcoded as the
delimiter. With this update, OpenShift Dev Spaces automatically picks a safe
delimiter that does not conflict with the usernames or group names.

#### 3.2. che-server Metrics Collection

Before this update, che-server metrics collection failed because of incompatible
Prometheus integration package changes introduced by the Micrometer upgrade from
1.11.5 to 1.16.1. With this update, the Micrometer upgrade is reverted. Metrics
collection works correctly.

#### 3.3. Bitbucket Server Default Branch Browse URLs

Before this update, opening a workspace from a Bitbucket Server default branch
browse URL without the `?at=` query parameter caused a NullPointerException in
the URL parser. With this update, the URL parser handles default branch browse
URLs correctly.

#### 3.4. Loader and Status Icon Styles

Before this update, loader and status icon colors used inconsistent styling. With
this update, all progress and status indicator colors use PatternFly design
tokens. Dark theme status label colors are also corrected.

#### 3.5. Multiple Accessibility Issues on the User Dashboard

Multiple accessibility issues resolved including:

- Keyboard navigation for editor selection, appearance settings, and provider
  dropdowns
- Correct focus order and tab navigation on the User Preferences page
- Improved color contrast for code editor line numbers and fold icons
- Proper validation messages and required field indicators across Personal Access
  Token, SSH Keys, and Gitconfig forms
- Distinct context for Upload buttons in the Add SSH Keys window
- Private repository cloning now prompts for credentials instead of failing

#### 3.6. Gateway Plugin Connects to JetBrains 2026.1

Before this update, the Gateway plugin could not connect to JetBrains
2026.1-based remote IDEs. With this update, the trusted path configuration is
added to ensure a smooth project loading process.

#### 3.7. Gateway Plugin Connects to Remote JetBrains IDEs Without a Project

Before this update, the Gateway plugin could not connect to a remote JetBrains
IDE that did not have a project open. With this update, the plugin connects
successfully to the IDE welcome screen.

### Technology Preview Features

None in this release.

### Deprecated Functionalities

None in this release.

### Removed Functionalities

None in this release.

## Known Issues

### 7.1. SSH Development Workflow Fails When Connecting to UBI 9-based Workspaces

There is a known issue where the SSH development workflow fails when connecting
to UBI 9-based workspaces.

### 7.2. Restarting a Workspace Fails After Disconnecting from a JetBrains Desktop Editor

There is a known issue where restarting a workspace fails after disconnecting
from a JetBrains desktop editor. The workspace shows a message that it has not
received an IDE heartbeat in the last 20 minutes and prompts users to re-open
the workspace.

### 7.3. C# Extension Not Available for .NET Workspaces on IBM Power and IBM Z

There is a known issue where the recommended C# extension is not available in
.NET sample workspaces on IBM Power (ppc64le) and IBM Z (s390x).

### 7.4. Workspace Backup List Is Empty for Non-Administrator Users

There is a known issue where the workspace backup list appears empty after
removing a workspace when logged in as a non-administrator user.

### 7.5. Podman Build Fails with Permission Denied Error on IBM Z with NFS Storage

There is a known issue where Podman build fails with a permission denied error
on IBM Z with NFS storage classes.

### 7.6. Workspaces Using Visual Studio Code (Desktop) Editor Ignores Idling Timeouts

There is a known issue where workspaces using the Visual Studio Code (desktop)
editor ignore idling timeouts.

### 7.7. SSH Connection to Workspaces Fails When Nested Containers Are Enabled

There is a known issue where SSH connection to workspaces fails when nested
containers are enabled.

### 7.8. The Kiro Remote Extension Host Does Not Install in Airgapped Clusters

There is a known issue where the Kiro remote extension host does not install in
airgapped clusters.

### 7.9. Incompatibility with OpenShift BYO External Authentication

The Red Hat OpenShift Dev Spaces Operator does not currently support OpenShift
clusters configured with Bring Your Own (BYO) External Authentication. Dev
Spaces currently relies on the built-in OpenShift OAuth server. Configurations
that replace the built-in OAuth server with external corporate OIDC Identity
Providers (IdPs) are not supported in this release.

### 7.10. "504 Gateway Time-out" Error

There is a known issue where a "504 Gateway Time-out" error may occur.

### 7.11. "PostStartHook failed" Error

There is a known issue where a "PostStartHook failed" error may occur during
workspace startup.

### 7.12. .NET Sample Fails to Start on arm64 Architecture

There is a known issue where the .NET sample fails to start on arm64
architecture.

### 7.13. Error When Starting a Workspace in Dev Spaces Deployed to OpenShift Platform 4.18

There is a known issue affecting workspaces in Dev Spaces deployed to OpenShift
Platform 4.18. When you start the workspace, the following error message
appears: "Error creating DevWorkspace deployment: Container tools has state
ImagePullBackOff".

### 7.14. JetBrains Editors Cause Workspace Startup Failure on IBM Power and IBM Z

There is a known issue where JetBrains editors cause workspace startup failure
on IBM Power and IBM Z architectures.

### 7.15. Refresh Token Mode Causes Cyclic Reload of the Workspace Start Page

There is a known issue where refresh token mode causes cyclic reload of the
workspace start page.
