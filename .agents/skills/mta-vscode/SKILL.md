---
name: mta-vscode
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: mta
  docs-version: "8.3"
  skill-group: "Application Modernization"
description: >
  Use when the MTA 8.3 VS Code extensions in Dev Spaces migration workspaces
  change or misbehave: the baked mta-vscode-extension, mta-core and mta-java
  8.3.1 VSIX files, DEFAULT_EXTENSIONS ordering with the Red Hat Java
  extension, Hub OIDC connection and profile sync, GenAI settings, and
  in-IDE analysis. Do NOT use for Lightspeed proxy or model settings (use
  mta-lightspeed), CLI analysis (use mta-cli), IntelliJ (use mta-intellij),
  or Dev Spaces extension policy in general (use ocp-devspaces-user-guide).
---

# MTA VS Code extension

Thin skill: repo decisions and pitfalls here, extension usage in the linked
MTA 8.3 guide. The extensions run in Code - OSS inside Dev Spaces migration
workspaces created from the Developer Hub `app-migration` template.

## When to use

- The extension is missing, does not register its Java provider, or cannot
  reach the Hub in a migration workspace.
- The VSIX lock or `DEFAULT_EXTENSIONS` list changes.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| VSIX files `mta-vscode-extension`, `mta-core`, `mta-java` 8.3.1 and the Red Hat Java extension are SHA-256 locked and baked to `/opt/rhoai3/extensions/` | `stages/070-advanced-app-platform/workspace-image/artifacts.lock.json`, `Dockerfile`, `verify-image.py` | [Install the extension][install] |
| Loaded through `DEFAULT_EXTENSIONS` (Java extension before `mta-java`); postStart asserts each VSIX is non-empty | `gitops/stages/070-advanced-app-platform/rhdh/templates/app-migration/skeleton/devfile.yaml` | see `ocp-devspaces-user-guide` |
| Workspace settings: JDT.LS `Standard` launch mode (so `mta-java` registers its provider), `mta-core.genai.enabled: true`, `mta-core.hub.auth.method: oidc` | same devfile (postStart) | [IDE settings][ide], [Hub OIDC][oidc] |
| Hub connection: `HUB_URL` from the template, `HUB_INSECURE=false`, `HUB_PROFILE_SYNC_ENABLED=true` | same devfile | [Hub OIDC][oidc], [Hub profile analysis][profile] |
| No analyzer RPC binary is installed separately; the extensions use the baked image | `stages/070-advanced-app-platform/workspace-image/` | [Analyzer RPC binary][rpc] |

## Procedure

1. Change VSIX versions only through `artifacts.lock.json` + `Dockerfile` +
   `verify-image.py`, then publish a new workspace image digest (outside
   this repo, see `docs/OPERATIONS.md#workspace-overlay-images`).
2. A template change publishes through the Stage 070 catalog
   (`rhdh` component); existing workspaces keep the devfile they were
   created with.
3. In a running workspace (read-only):

   ```bash
   ls -l /opt/rhoai3/extensions/
   echo "$DEFAULT_EXTENSIONS"
   ```

## Pitfalls

- Image, CLI (8.3.0) and VSIX (8.3.1) versions are pinned separately; a
  version string alone is not qualification:
  `docs/TROUBLESHOOTING.md#stage-070-workspace-tools-or-mta-ai-are-unavailable`.
- Without JDT.LS `Standard` mode the Java provider does not register and the
  analysis shows no Java incidents.
- The devfile sets `HUB_SOLUTION_SERVER_ENABLED=true` while the Hub's
  Solution Server is disabled (`mta-lightspeed`); expect Solution Server
  features in the IDE to be unavailable.
- A missing Hub URL refuses the migration template rather than producing a
  workspace without Hub access.

## Official documentation (MTA 8.3)

| Topic | Section |
|---|---|
| Overview and install | [Introduction][intro], [Install][install], [Analyzer RPC][rpc] |
| Settings | [IDE settings][ide], [Profile settings][profiles] |
| Analysis | [Run an analysis][run], [Hub OIDC][oidc], [Hub profile analysis][profile], [Review and resolve issues][resolve] |

## Related skills

`mta-lightspeed`, `mta-cli`, `mta-ui`, `ocp-devspaces-user-guide`, `manage-devspaces`.

[intro]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index#intro-to-vscode-for-mta_vsc-extension-guide
[install]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index#installing-vscode-extension_vsc-extension-guide
[rpc]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index#installing-analyzer-rpc_vsc-extension-guide
[ide]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index#configuring-lighstspeed-ide-settings_vsc-extension-guide
[profiles]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index#configuring-profile-settings_vsc-extension-guide
[run]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index#vscode-analyzing-application_vsc-extension-guide
[oidc]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index#configure-oidc-authentication-ide-extension_vsc-extension-guide
[profile]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index#analyzing-application-profiles_vsc-extension-guide
[resolve]: https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.3/html-single/configuring_and_using_the_visual_studio_code_extension_for_mta/index#vscode-reviewing-and-resolving-issues_vsc-extension-guide
