# AgentOps console (`060-agent-console`)

This Application turns on the AgentOps view in the OpenShift AI dashboard and lets each persona read the agent
`Sandbox` resources and Services in its own OpenShell workspace. It is discovery only: agents are started, stopped and
deleted through the authenticated OpenShell CLI (`060-openshell-runtime`), never from the console.

| | |
|---|---|
| Argo CD Application | `060-agent-console` ([manifest](../../../argocd/app-of-apps/060-agent-runtime-and-agentops/agent-console.yaml)) |
| Deployed by | [`stages/060-agent-runtime-and-agentops/deploy-console.sh <branch>`](../../../../stages/060-agent-runtime-and-agentops/deploy-console.sh) (own deploy script) |
| Validated by | [`stages/060-agent-runtime-and-agentops/validate-console.sh`](../../../../stages/060-agent-runtime-and-agentops/validate-console.sh) (Application Synced and Healthy at its pinned revision; `agentOps` is `true`; `ai-admin` and `ai-developer` can get/list Sandboxes and Services in their own workspace, cannot create or delete Sandboxes there, and cannot list Sandboxes in the other workspace) |
| Sync | Manual. Pinned to the published SHA; `argocd --core app sync --strategy hook`. Default (client-side) comparison; no sync options. |
| Depends on | `060-openshell-runtime` Synced and Healthy, with the `sandboxes.agents.x-k8s.io` CRD established and namespaces `openshell-admin` and `openshell-developer` present. `010-rhoai-platform` delegating `/spec/dashboardConfig/agentOps` of `odh-dashboard-config`. |
| Used by | Dashboard users `ai-admin` and `ai-developer` (AgentOps / agent deployments view). |

## Why

OpenShift AI 3.5 can list running agent deployments in the dashboard; they are OpenShell-managed `Sandbox` custom
resources, shown with name and status per namespace (Developer Preview) [1]. The view is behind the dashboard flag
`spec.dashboardConfig.agentOps` (Developer Preview, default `false`) [2]. A user sees only what Kubernetes RBAC lets them
read, so each persona needs read access to Sandboxes in its workspace.

The view is kept apart from the runtime because it has a different risk: the runtime component carries the gateway's
write permissions, while this one must never grant a human Sandbox create or delete rights. The generic console
creation wizard is not qualified with the hardened OpenShell launch path, so no create permission is given.

The `OdhDashboardConfig` is owned by Stage 010. This component changes only the delegated `agentOps` field, through a
hook Job, so the shared object keeps one owner.

## What

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| ServiceAccount | `enable-agent-console` | `redhat-ods-applications` | Job identity. Wave 1. |
| Role, RoleBinding | `enable-agent-console` | `redhat-ods-applications` | `get`, `patch` on `odhdashboardconfigs` named `odh-dashboard-config` only. Wave 1. |
| Job | `enable-agent-console` | `redhat-ods-applications` | Sync hook, wave 10, `BeforeHookCreation`. Merge-patches `spec.dashboardConfig.agentOps: true` and reads it back. Pinned `ose-cli` image by digest, restricted security context, 90 s deadline, `backoffLimit: 1`. |

### `console-discovery/` — per-workspace read access

| Kind | Name | Namespace | Purpose |
|---|---|---|---|
| Role | `agent-discovery-readers` | `openshell-admin`, `openshell-developer` | get/list on `agents.x-k8s.io` `sandboxes` and core `services`. Wave 5. |
| RoleBinding | `agent-discovery-readers` | `openshell-admin` | Binds the Role to user `ai-admin`. Wave 5. |
| RoleBinding | `agent-discovery-readers` | `openshell-developer` | Binds the Role to user `ai-developer`. Wave 5. |

Not covered here: the `ai-agents` project, where the OpenCode and Hermes sandboxes run. Visibility there comes from
the `admin` binding for group `rhods-admins` in `060-openshell-runtime`; `ai-developer` has no access to it.

## How

- **Delegation.** Stage 010 lists `/spec/dashboardConfig/agentOps` in its `ignoreDifferences`. `deploy-console.sh`
  checks this with `stage_apps.delegated` before any write.
- **Guards.** The script requires `argocd --core` and kube-context namespace `openshift-gitops`, checks that the
  branch head equals the local commit and the component files are clean, requires the runtime Application to be
  Healthy and Synced and the Sandbox CRD to be established, and refuses foreign-owned objects with the same names.
- **Hook lifecycle.** `BeforeHookCreation` only, so the completed Job stays until the next sync [3].
- **Least privilege.** Read verbs only, two resources, one user per namespace, bound by exact user name. Sandbox
  lifecycle stays in the OpenShell API, where the gateway checks workspace membership.
- **Pruning** this Application removes the Roles and RoleBindings but does not reset the `agentOps` flag.
- **No secrets, no cluster-specific values.**

## Validation

`validate-console.sh` (read-only; uses `oc auth can-i --as`). By hand:

```bash
oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o jsonpath='{.spec.dashboardConfig.agentOps}{"\n"}'
oc auth can-i list sandboxes.agents.x-k8s.io -n openshell-developer --as=ai-developer
```

Expect `true` and `yes`. The validator does not prove that a running agent appears in the browser.

## Alignment with official guidance

| Topic | Official guidance (link) | This repository | Status |
|---|---|---|---|
| Feature flag | `spec.dashboardConfig.agentOps`, Developer Preview, default `false` [2] | Set to `true` by a hook Job | Aligned |
| What the view shows | Running agents as OpenShell-managed `Sandbox` CRs per namespace [1] | Read access to `sandboxes` per workspace | Aligned |
| Access model | Default `view` role sees most objects in a project; `admin` can modify them [4] | Custom Role with get/list on two resources | Aligned (narrower than `view`) |
| Support level | Developer Preview [1], [2] | Stated in the stage README | Aligned |
| GitOps ownership | n/a | Job patches one field of a Stage 010 object under explicit delegation | Deviation (justified: single owner for the shared dashboard config) |
| Coverage | n/a | Roles only for `openshell-admin` and `openshell-developer`; the agents in `ai-agents` rely on `rhods-admins` | Deviation (justified: `ai-agents` is administrator-managed; `rhods-admins` holds `admin` there) |

## References

1. Red Hat OpenShift AI Self-Managed 3.5, Release notes, "Developer Preview features" (View running agent deployments in the dashboard). https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/release_notes/developer-preview-features_relnotes
2. Red Hat OpenShift AI Self-Managed 3.5, Managing resources, "Customizing the dashboard" (dashboard configuration options). https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html/managing_resources/customizing-the-dashboard
3. Argo CD, "Sync Phases and Waves" (hooks and delete policies) (upstream). https://argo-cd.readthedocs.io/en/stable/user-guide/sync-waves/
4. OpenShift Container Platform 4.22, Authentication and authorization, "Using RBAC to define and apply permissions". https://docs.redhat.com/en/documentation/openshift_container_platform/4.22/html/authentication_and_authorization/using-rbac
