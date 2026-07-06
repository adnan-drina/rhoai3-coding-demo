---
name: ocp-devspaces-user-guide
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "ocp"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Use when documenting or explaining OpenShift Dev Spaces 3.28 user workflows,
  including starting workspaces, devfile authoring, IDE customization, Git
  integration, VS Code extensions, credential management, and workspace
  configuration. Do NOT use for concepts (use ocp-devspaces-about), installing
  (use ocp-devspaces-install), administration (use ocp-devspaces-admin), or
  release notes (use ocp-devspaces-release-notes).
---

# OCP Dev Spaces User Guide

Use this skill to ground OpenShift Dev Spaces user workflow guidance in the
official Red Hat OpenShift Dev Spaces 3.28 User Guide.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Starting Workspaces

Workspaces are started by entering a URL in the browser:

```
https://<openshift_dev_spaces_fqdn>#<git_repository_url>
```

Three starting methods are supported:
- **Git repository URL** — clones the repo and applies its devfile (or UDI default)
- **Raw devfile URL** — uses a devfile hosted at any HTTP(S) URL
- **Dashboard** — Create Workspace page with the Git Repo URL field

Optional URL parameters customize workspace creation: IDE selection
(`che-editor=`), IDE image override (`editor-image=`), duplicate workspace
(`new`), storage type (`storageType=`), devfile path (`devfilePath=`), container
image (`image=`), memory limit (`memoryLimit=`), CPU limit (`cpuLimit=`), and
additional remotes (`remotes=`).

## Workspace Management

Basic workspace actions via the dashboard Workspaces page:
- Reopen, restart, stop, start, delete workspaces
- View workspace status and unique URL

CLI management via `oc` and DevWorkspace CRs:
- `oc get devworkspaces` — list workspaces
- `oc patch devworkspace <name> -p '{"spec":{"started":true}}'` — start
- `oc patch devworkspace <name> -p '{"spec":{"started":false}}'` — stop
- `oc delete devworkspace <name>` — remove

## Devfile Authoring

Devfiles (`devfile.yaml` or `.devfile.yaml`) customize workspace components,
commands, and environment. Key fields: `schemaVersion: 2.2.2`, `metadata`,
`components`, `commands`, `projects`.

Without a devfile, workspaces start with the Universal Developer Image (UDI)
and VS Code - Open Source.

Volume components request persistent storage. Container components define
workspace containers with `image`, `memoryLimit`, `cpuLimit`, `env`,
`endpoints`, and `volumeMounts`.

## IDE Customization

Default IDE: Microsoft Visual Studio Code - Open Source
(`che-incubator/che-code/latest`).

Supported IDEs:
- VS Code - Open Source (`che-incubator/che-code/latest` or `insiders`)
- JetBrains IntelliJ IDEA Ultimate over Gateway
  (`che-incubator/che-idea-server/latest` or `next`)
- JetBrains IDEs over Toolbox (`che-incubator/che-idea-server/toolbox`)

Repository-level IDE selection: `/.che/che-editor.yaml` with `id`, `reference`,
or `inline` definitions. The `override` field customizes container resources.

## VS Code Extensions

Automate extension installation by adding `/.vscode/extensions.json` to the
repository:

```json
{
  "recommendations": [
    "<publisher>.<extension>"
  ]
}
```

Extensions are installed from the Open VSX registry. In restricted environments,
use a private Open VSX registry or install from `.vsix` files.

GitHub Copilot Chat: install `Dev Spaces Copilot Chat Integration` v0.36.2,
authenticate via Device Authentication, then refresh.

## Git Integration

Git authentication methods:
- **OAuth** (admin-configured) — GitHub, GitLab, Bitbucket, Azure DevOps
- **Personal access token** — user-created Secret with
  `app.kubernetes.io/component: scm-personal-access-token` label
- **SSH keys** — propagated via User Preferences

Automatic OpenShift token injection: `oc` and `kubectl` commands authenticate
automatically inside workspace containers.

## Credential and Configuration Management

Mount credentials and configs into workspaces using Kubernetes resources:

- **Secrets** — label `controller.devfile.io/mount-to-devworkspace: 'true'`,
  annotate with `mount-as: file|subpath|env` and `mount-path`
- **ConfigMaps** — same labeling pattern, use for non-sensitive data (Git
  config, IDE settings, storage driver config)
- **Image pull Secrets** — label
  `controller.devfile.io/devworkspace_pullsecret: 'true'`

## Persistent Storage

Workspaces are ephemeral by default. Persist data by:
- Adding `volume` components in the devfile
- Applying a PVC with `controller.devfile.io/mount-to-devworkspace: 'true'`

Storage types: `ephemeral`, `per-user` (default), `per-workspace`.

## Container Tooling

UDI includes Podman and Buildah. fuse-overlayfs improves performance over the
default `vfs` driver. Kubedock provides a Podman-like experience for running
containers in workspaces (useful for Testcontainers, Quarkus Dev Services).

## Workspace Idling Prevention

Place a `.noidle` file in the workspace to keep long-running commands from
triggering idle timeout. Configurable `watchedCommands` and `checkPeriodSeconds`.

## OpenShift Integration

- DevWorkspace CR (`workspace.devfile.io/v1alpha2`) represents each workspace
- OpenShift Developer Perspective integration via ConsoleLink
- Edit application source code from Topology view
- Red Hat Applications menu link to Dev Spaces dashboard

## Restricted Environment Support

Configure artifact repositories (Maven, Gradle, npm, Python, Go, NuGet) in
restricted environments by mounting ConfigMaps and Secrets with repository
mirrors and TLS certificates.

## Troubleshooting

Workspace logs: `oc logs` with
`--selector='controller.devfile.io/devworkspace_name=<name>'`. Common issues:
OOMKilled, CrashLoopBackOff, devfile syntax errors, WebSocket failures.

## Workflow

1. Confirm the active OpenShift baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/official-doc-extraction.md`.
3. Identify the relevant workflow area (workspace lifecycle, devfile, IDE,
   credentials, storage, OpenShift integration).
4. For YAML examples, verify all fields against the extraction before
   committing.
5. For live operations, use the repo environment guard.
6. Validate with `references/source-capture.md` boundaries.

## Related Skills

- Use `ocp-devspaces-about` for Dev Spaces concepts and architecture.
- Use `ocp-devspaces-install` for installing and upgrading Dev Spaces.
- Use `ocp-devspaces-admin` for administration and CheCluster configuration.
- Use `ocp-devspaces-release-notes` for version-specific changes.
- Use `ocp-devspaces-user-guide` (this skill) for user workflows.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
