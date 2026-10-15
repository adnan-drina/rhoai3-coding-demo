---
name: ocp-devspaces-about
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: ocp_devspaces
  docs-version: "3.30"
  skill-group: "OpenShift Platform"
description: >
  Use when explaining OpenShift Dev Spaces 3.30 concepts as this demo uses
  them: the Dev Spaces operator and CheCluster, the Dev Workspace Operator and
  workspace pods, gateway, dashboard and server, user namespaces, the plug-in
  registry, and why workspaces are the developer entry point for Stages
  110-130. Do NOT use for installing (use ocp-devspaces-install),
  administration (use ocp-devspaces-admin), devfiles and workspace usage
  (use ocp-devspaces-user-guide), or release notes (use
  ocp-devspaces-release-notes).
---

# Dev Spaces concepts

Thin skill: how the product's architecture maps onto this repo, with links to
the Dev Spaces 3.30 Discover topics. Detailed record:
`gitops/stages/070-advanced-app-platform/070-devspaces/README.md` (Why).

## When to use

- Explaining where a workspace runs, who owns which object, or why the demo
  uses cloud development environments.
- Orienting before an install, admin or devfile change.

## Repo decisions

| Concept in this repo | Where in Git | Official section |
|---|---|---|
| One `CheCluster` `devspaces` in `openshift-devspaces` drives server, dashboard, gateway and plug-in registry | `gitops/stages/070-advanced-app-platform/070-devspaces/checluster.yaml` | [Operator and lifecycle][operator], [Server components][components] |
| DevWorkspaces are reconciled by the Dev Workspace Operator (0.43.0 observed), which OLM installs with Dev Spaces in `openshift-operators` | `070-devspaces/subscription.yaml` | [Dev Workspace Operator][dwo] |
| Each persona works in a pre-provisioned project (`wksp-ai-developer`, `wksp-ai-admin`, `wksp-kubeadmin`) | `gitops/stages/070-advanced-app-platform/070-namespaces/namespaces.yaml` | [Server and namespace provisioning][server] |
| Users sign in with native OpenShift login; Git access through GitLab OAuth | `gitops/stages/070-advanced-app-platform/070-gitlab/README.md` | [Gateway and routing][gateway] |
| Extensions come from `open-vsx.org` or baked VSIX files | `070-devspaces/checluster.yaml`, `stages/070-advanced-app-platform/workspace-image/` | [Plug-in registry][registry] |
| Source and AI assistance stay in the cluster: workspaces call the governed MaaS gateway | `070-devspaces/maas-api-key-provisioning.yaml` | [What developers get][workspaces] |
| Stages 110-130 consume workspaces; Developer Hub templates create them | `stages/110-ai-assisted-development/`, `stages/120-ai-agentic-development/`, `stages/130-ai-autonomous-migration/` | [Roles and tasks][roles] |

## Procedure

Read-only orientation after the OpenShift safety guard in `AGENTS.md`:

```bash
oc get checluster devspaces -n openshift-devspaces -o jsonpath='{.status.cheURL}{"\n"}'
oc get pods -n openshift-devspaces
oc get devworkspace -A
```

## Pitfalls

- "Workspace" in this repo means a DevWorkspace in a `wksp-*` project; the
  Stage 130 Hermes worker runs inside it, it is not a separate runtime.
- Dev Spaces, OpenShift AI and Argo CD keep native OpenShift login; only the
  application tools use the Keycloak `platform` realm
  (`docs/OPERATIONS.md#stage-070--identity-identity-component`).

## Official documentation (Dev Spaces 3.30)

| Topic | Section |
|---|---|
| What and why | [What is Dev Spaces][what], [Problems it solves][problems], [Cloud vs local][when] |
| Architecture | [How it works][how], [Overview][arch], [Server components][components], [Operator][operator], [Dev Workspace Operator][dwo], [Gateway][gateway], [Dashboard][dashboard], [Server][server], [Plug-in registry][registry] |
| Users | [What developers get][workspaces], [Roles and tasks][roles] |
| Planning | [Supported platforms][platforms] |

## Related skills

`ocp-devspaces-install`, `ocp-devspaces-admin`, `ocp-devspaces-user-guide`,
`ocp-devspaces-release-notes`, `manage-devspaces`.

[what]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/discover-con_what_is_devspaces
[problems]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/discover-con_what_problems_devspaces_solves
[when]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/discover-con_cloud_vs_local_development
[how]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/discover-assembly_architecture
[arch]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/discover-con_architecture_overview
[components]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/discover-con_server_components
[operator]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/discover-con_devspaces_operator
[dwo]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/discover-con_devworkspace_operator
[gateway]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/discover-con_gateway
[dashboard]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/discover-con_dashboard
[server]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/discover-con_devspaces_server
[registry]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/discover-con_plugin_registry
[workspaces]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/discover-con_user_workspaces
[roles]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/discover-ref_roles_and_tasks
[platforms]: https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/3.30/plan-supported_platforms_ref
