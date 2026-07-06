---
name: ocp-devspaces-release-notes
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when checking OpenShift Dev Spaces 3.28 release notes, new features,
  bug fixes, known issues, and version compatibility. Covers 3.28.0, 3.28.1,
  and 3.28.2 sub-releases. Do NOT use for concepts (use ocp-devspaces-about),
  installing (use ocp-devspaces-install), administration (use
  ocp-devspaces-admin), or user workflows (use ocp-devspaces-user-guide).
---

# OCP Dev Spaces Release Notes

Use this skill to ground OpenShift Dev Spaces release information in the
official Red Hat OpenShift Dev Spaces 3.28 release notes for the active
baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Compatibility

- Based on Eclipse Che 7.117
- Supported on OpenShift 4.16–4.22
- Architectures: AMD64/Intel 64 (x86_64), IBM Z (s390x), IBM Power (ppc64le),
  ARMv8 (arm64)
- IDEs: VS Code - Open Source, JetBrains IntelliJ IDEA Ultimate, PyCharm,
  WebStorm, RubyMine, CLion, GoLand, PhpStorm, Rider

## Release History

- **3.28.2** — cumulative release; adds OpenShift 4.22 platform support
- **3.28.1** — stability and maintenance release
- **3.28.0** — initial GA with new features, bug fixes, known issues

## Key Topics

- GitHub App support for identity management (replaces OAuth App reliance)
- OIDC authentication flow for Microsoft Azure DevOps
- Persistent user home enabled by default (`spec.devEnvironments.persistUserHome.enabled`)
- VS Code - Open Source updated to 1.108.2
- Workspace backups viewable and restorable from Dashboard
- User Dashboard migrated to PatternFly 6
- Full IPv6 support for Dashboard (OpenShift 4.20+)
- SCC mismatch detection and warning for DevWorkspaces
- CHOWN capability added to security context for container run mode
- DevWorkspace Operator 0.41.0: targeted automount, deferred mounting,
  PVC subdirectory mounting
- JetBrains: devfile editing from IDE, Gateway plugin fixes for 2026.1

## Known Issues (Summary)

- SSH workflow fails connecting to UBI 9-based workspaces
- SSH connection fails when nested containers are enabled
- Incompatible with OpenShift BYO External Authentication
- JetBrains editors cause startup failure on IBM Power and IBM Z
- VS Code (desktop) ignores idling timeouts
- Workspace backup list empty for non-administrator users
- Error starting workspace on OpenShift Platform 4.18

Read `references/official-doc-extraction.md` for the full list with details.

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify whether the question concerns:
   - platform compatibility and supported versions
   - new features in a specific sub-release
   - bug fixes
   - known issues and workarounds
   - deprecated or removed features (none in 3.28)
   - Technology Preview features (none in 3.28)
4. Use exact version numbers and component names from the extraction.
5. When advising on upgrades or workspace issues, cross-reference known issues.

## Related Skills

- Use `ocp-devspaces-about` for Dev Spaces concepts and architecture.
- Use `ocp-devspaces-install` for installing and upgrading Dev Spaces.
- Use `ocp-devspaces-admin` for CheCluster configuration and administration.
- Use `ocp-devspaces-user-guide` for workspace usage and developer workflows.
- Use `ocp-devspaces-release-notes` (this skill) for version-specific changes.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
