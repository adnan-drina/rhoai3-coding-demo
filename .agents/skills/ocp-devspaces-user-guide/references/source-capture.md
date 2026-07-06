# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Dev Spaces |
| Product version | 3.28 |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Usage and Administration |
| Official guide | User guide |
| Source URL | https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28/html-single/user_guide/index |
| Multi-page URL | https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.28/html/user_guide/index |
| Capture date | 2026-07-06 |

## Captured Sections

From User guide (Red Hat OpenShift Dev Spaces 3.28):

- Chapter 1: Get started with OpenShift Dev Spaces
  - 1.1 Start a workspace from a Git repository URL (URL patterns per Git provider)
  - 1.2 Start a workspace from a raw devfile URL
  - 1.3 Basic actions you can perform on a workspace
  - 1.4 Git server authentication from a workspace
- Chapter 2: Optional parameters for the URLs for starting a new workspace
  - 2.1 URL parameter concatenation
  - 2.2 URL parameter for the IDE (`che-editor=`)
  - 2.3 URL parameter for the IDE image (`editor-image=`)
  - 2.4 URL parameter for starting duplicate workspaces (`new`)
  - 2.5 URL parameter for existing workspace name (`existing`)
  - 2.6 URL parameter for the devfile file name (`df=`)
  - 2.7 URL parameter for the devfile file path (`devfilePath=`)
  - 2.8 URL parameter for the workspace storage (`storageType=`)
  - 2.9 URL parameter for additional remotes (`remotes=`)
  - 2.10 URL parameter for a container image (`image=`)
  - 2.11 URL parameter for a memory limit (`memoryLimit=`)
  - 2.12 URL parameter for a CPU limit (`cpuLimit=`)
- Chapter 3: Use fuse-overlayfs for containers
  - 3.1 The fuse-overlayfs storage driver for Podman and Buildah
  - 3.2 Access /dev/fuse in workspace containers
  - 3.3 Enable fuse-overlayfs with a ConfigMap
  - 3.4–3.6 Kubedock usage and configuration
- Chapter 4: Prevent workspace idling for long-running commands
  - CLI Watcher and `.noidle` file
- Chapter 5: Use OpenShift Dev Spaces in team workflow
  - 5.1 Factory badge for first-time contributors
  - 5.2 Review pull and merge requests
  - 5.3–5.4 Try in Web IDE GitHub action
- Chapter 6: Customize workspace components
  - 6.1 Workspace component customization overview
  - 6.2 Introduction to devfile in OpenShift Dev Spaces
  - 6.3 IDEs in workspaces (supported IDEs table)
  - 6.4–6.6 JetBrains Gateway and Toolbox integration
  - 6.7 JetBrains Gateway plugin compatibility matrix
  - 6.8 Automate installation of VS Code extensions at workspace startup
  - 6.9 Set up GitHub Copilot Chat
  - 6.10–6.11 Define a common IDE and che-editor.yaml parameters
- Chapter 7: Use credentials and configurations in workspaces
  - 7.1 Credentials and configurations overview
  - 7.2 Mount Secrets (file, subpath, env)
  - 7.3–7.5 Create image pull Secrets (oc, .dockercfg, config.json)
  - 7.6 Use a Git provider access token
  - 7.7 Mount ConfigMaps
  - 7.8 Mount Git configuration
  - 7.9 Mount SSH configuration
- Chapter 8: Enable artifact repositories in a restricted environment
  - 8.1–8.6 Maven, Gradle, npm, Python, Go, NuGet repository configuration
- Chapter 9: Request persistent storage for workspaces
  - 9.1 Persistent storage overview
  - 9.2 Request persistent storage in a devfile
  - 9.3 Request persistent storage in a PVC
- Chapter 10: Restore workspaces from backups
  - 10.1 View backups in the dashboard
  - 10.2 Restore a workspace from a backup
- Chapter 11: Integrate with OpenShift
  - 11.1 OpenShift integration overview
  - 11.2–11.6 List, create, stop, start, remove workspaces via oc
  - 11.7 Automatic OpenShift token injection
  - 11.8–11.11 OpenShift Developer Perspective and console integration
- Chapter 12: Troubleshoot OpenShift Dev Spaces
  - 12.1 Workspace logs (CLI, console, language server)
  - 12.2 Slow workspace troubleshooting
  - 12.3 Network problems
  - 12.4 Webview loading error
  - 12.5 Devfile issues (syntax, component, command, volume/endpoint)

## Source Boundaries

This skill covers the User guide for Red Hat OpenShift Dev Spaces 3.28. It
provides user-facing workflows for starting, configuring, and managing
workspaces, devfile authoring, IDE customization, Git integration, credential
management, persistent storage, container tooling, restricted-environment
configuration, OpenShift integration, and basic troubleshooting. It does not
cover:

- Dev Spaces concepts and architecture (separate guide — About)
- Installation, upgrading, and operator configuration (separate guide — Install)
- Administration and CheCluster CR configuration (separate guide — Admin)
- Release notes and version-specific changes (separate guide — Release Notes)
- API reference details beyond user-facing workflows

## API Versions Documented

| Resource | API Version |
|----------|-------------|
| DevWorkspace | `workspace.devfile.io/v1alpha2` |
| Secret | `v1` |
| ConfigMap | `v1` |
| PersistentVolumeClaim | `v1` |

## Key Labels and Annotations

| Label / Annotation | Purpose |
|--------------------|---------|
| `controller.devfile.io/mount-to-devworkspace: 'true'` | Mount Secret/ConfigMap/PVC to all workspaces |
| `controller.devfile.io/watch-secret: 'true'` | Watch Secret for changes |
| `controller.devfile.io/watch-configmap: 'true'` | Watch ConfigMap for changes |
| `controller.devfile.io/mount-as: file\|subpath\|env` | How to mount the resource |
| `controller.devfile.io/mount-path: <path>` | Override default mount path |
| `controller.devfile.io/devworkspace_pullsecret: 'true'` | Mark as image pull secret |
| `controller.devfile.io/storage-type: ephemeral` | Ephemeral workspace storage |
| `app.kubernetes.io/component: scm-personal-access-token` | Git personal access token |
| `app.kubernetes.io/part-of: che.eclipse.org` | Part of Dev Spaces ecosystem |

## Related Official Sources To Add Later

- About Red Hat OpenShift Dev Spaces (concepts and architecture)
- Installing Red Hat OpenShift Dev Spaces (installation guide)
- Administration guide for Red Hat OpenShift Dev Spaces
- Red Hat OpenShift Dev Spaces release notes
- Devfile v2 specification (devfile.io)
