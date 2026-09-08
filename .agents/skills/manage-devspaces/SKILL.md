---
name: manage-devspaces
metadata:
  author: rhoai3-coding-demo
  version: 1.2.1
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Demo Environment"
description: >-
  Manage OpenShift Dev Spaces workspaces for the RHOAI coding demo. Use when
  creating, deleting, recreating, debugging, or updating DevWorkspace resources
  in wksp-* namespaces, or when troubleshooting workspace startup failures,
  OOM crashes, or DevWorkspace configuration. Do NOT use for general cluster
  troubleshooting (use rhoai-troubleshoot), GPU/model resource lifecycle
  actions (use manage-resources), or GitOps manifest review (use
  review-gitops-change).
---

# Managing Dev Spaces Workspaces

## Environment

- **CheCluster**: `devspaces` in `openshift-devspaces` (open-vsx.org, 1200s timeout, no-idle, `pvcStrategy: per-user`)
- **GitOps DevWorkspaces**: `agentic-coolstore` in `wksp-ai-developer` and `wksp-ai-admin` only (Stage 060 catalog seat). Persona namespaces `wksp-kubeadmin`, `wksp-ai-admin`, and `wksp-ai-developer` stay GitOps-owned.
- **Factory workspaces**: Stages 070 and 080 create per-run DevWorkspaces from RHDH templates (`agentic-quarkus-scaffold`, `app-migration`). Those destfiles live in the cloned repo; GitOps does not pre-create the CRs. Both destfiles set `controller.devfile.io/storage-type: per-workspace` so they can run beside `agentic-coolstore` without multi-attaching the per-user RWO `claim-devworkspace`.
- **Retired standing seats** (do not recreate): `getting-started-ai-coding`, `coolstore-inventory-service`, `mca-coolstore`.
- **Cloned repos**:
  - `https://github.com/adnan-drina/coolstore-inventory-service.git` — Stage 060 `agentic-coolstore` project
  - Stage 070/080 factory repos are published per run; Stage 080 also clones the legacy URL as `/projects/legacy`
- **Extensions**: Kilo Code 7.4.8 via `DEFAULT_EXTENSIONS` on `agentic-coolstore`. MTA 8.2.0 (pack + core + java + redhat.java) via the Stage 080 factory destfile.
- **GitOps**: Managed by Argo CD `050-advanced-app-platform` with a repair hook (no Replace on DevWorkspaces)
- **AI tool selection**: Stage 060 `agentic-coolstore` is Kilo Code. Factory 070/080 destfiles select the agentic/harness tooling for that stage.
- **Manifests**: `gitops/stages/050-advanced-app-platform/base/devspaces/workspaces.yaml` (namespaces + RBAC), `agentic-workspace.yaml` (Stage 060 seats)

## Key Behaviors Learned

### DevWorkspace CR vs Repo Devfile

GitOps-created DevWorkspaces use the **inline CR spec only**. The `devfile.yaml` in the cloned repo is ignored. All commands, events, components, and resource limits must be defined inline in the DevWorkspace CR.

Factory (RHDH) workspaces use the **repo destfile** stamped at create time.

### Workspace Trust (Che Code)

`vscode-editor-configurations` in each `wksp-*` namespace must set both:

- `settings.json` → `security.workspace.trust.enabled: false` (Machine settings)
- `product.json` → `configurationDefaults` for the same key (and `startupPrompt: never`)

Machine settings alone still show **Trust Workspace & Install** on a first factory start: Che Code writes recommended extensions into `/projects/.code-workspace` before the web workbench consults Machine settings. `product.json` is merged before `server-main.js` starts (Dev Spaces 3.28 Admin Guide ch. 17). ConfigMap changes take effect only after a workspace stop/start.

### postStart Initialization

The postStart event runs the `init-ai-tools` command, which executes the centralized init script from the `devspace-ai-tools-init` ConfigMap. This script handles Kilo Code configuration, extension installation, and tool setup.

postStart `exec` commands run before git clone completes. The init script includes a wait loop to handle the race condition.

**Known issue**: postStart exec commands in GitOps-managed DevWorkspace CRs may not execute reliably. The manual fallback is to exec into the pod and run the init script manually.

### Extension Downloads in postStart

VSIX downloads from OpenVSX use CDN redirects that can time out silently. Always use `--max-time 120` (GitOps seats use `--max-time 300` with retries):

```bash
curl -fsSL --max-time 120 -o /tmp/kilo.vsix "https://open-vsx.org/api/kilocode/kilo-code/linux-x64/7.4.8/file/kilocode.kilo-code-7.4.8@linux-x64.vsix" 2>/dev/null || true
curl -fsSL --max-time 120 -o /tmp/mta.vsix "https://open-vsx.org/api/redhat/mta-vscode-extension/8.2.0/file/redhat.mta-vscode-extension-8.2.0.vsix" 2>/dev/null || true
```

The MTA extension pack (`mta-vscode-extension`) does not reliably resolve its dependencies (`mta-core`, `mta-java`) from a local VSIX in Dev Spaces. Pin and download all three plus `redhat.java`.

### Project Order Matters for MTA

The MTA Konveyor Core extension warns "Multi-root workspaces are not supported! Only the first workspace folder will be analyzed." Stage 080 factory destfiles put `legacy` first so analysis targets the migration source.

### Memory Requirements

The default tooling container memory (~1152Mi) is insufficient for VS Code + Kilo Code + MTA + Java/Maven. Current seats:

- **agentic-coolstore**: 6Gi limit / 2Gi request
- **Stage 080 factory destfile**: 12Gi limit / 2Gi request for MTA analysis and the harness

```yaml
components:
  - name: tooling-container
    container:
      memoryLimit: 6Gi
      memoryRequest: 2Gi
      cpuLimit: "2"
      cpuRequest: 500m
```

### ArgoCD ServerSideDiff Issues

Earlier demo revisions used `Replace=true` for nested DevWorkspace changes. Current GitOps does not use `Replace=true` on DevWorkspaces because controller-assigned IDs are immutable. Instead, a repair hook removes stale annotations and lets Argo CD patch the spec while ignoring only `/spec/started`.

```yaml
annotations:
  argocd.argoproj.io/sync-options: SkipDryRunOnMissingResource=true
```

### Operator Reconciliation

The Dev Spaces operator reconciles DevWorkspaces. Manual `oc apply` changes may be reverted. To update a GitOps workspace spec:

1. Disable ArgoCD auto-sync
2. Stop the workspace (`spec.started: false`)
3. Delete the DevWorkspace CR
4. Delete the namespace PVC only if no other workspace in that namespace still needs it (`claim-devworkspace` is per-user and shared)
5. Apply the new CR from GitOps
6. Re-enable ArgoCD auto-sync

## Common Operations

### Recreate the Stage 060 catalog seat (clean slate)

```bash
NS=wksp-ai-developer
oc patch application 050-advanced-app-platform -n openshift-gitops --type=json \
  -p '[{"op":"remove","path":"/spec/syncPolicy/automated"}]'
oc patch devworkspace agentic-coolstore -n $NS --type=merge -p '{"spec":{"started":false}}'
sleep 10
oc delete devworkspace agentic-coolstore -n $NS --force --grace-period=0
# Only delete the per-user claim when no other DevWorkspace in $NS still needs it.
oc delete pvc claim-devworkspace -n $NS --force --grace-period=0
sleep 5
oc apply -f gitops/stages/050-advanced-app-platform/base/devspaces/agentic-workspace.yaml
oc patch application 050-advanced-app-platform -n openshift-gitops --type=merge \
  -p '{"spec":{"syncPolicy":{"automated":{"prune":true,"selfHeal":true}}}}'
```

### Check Workspace Health

```bash
# Status and URL
oc get devworkspace --all-namespaces -o custom-columns='NS:.metadata.namespace,NAME:.metadata.name,STATUS:.status.phase' --no-headers

# Memory usage (if running)
POD=$(oc get pods -n wksp-ai-developer --no-headers -o name | head -1)
oc exec $POD -n wksp-ai-developer -c tooling-container -- cat /sys/fs/cgroup/memory.current 2>/dev/null | awk '{printf "Current: %.0f MB\n", $1/1024/1024}'
oc exec $POD -n wksp-ai-developer -c tooling-container -- cat /sys/fs/cgroup/memory.max 2>/dev/null | awk '{printf "Limit:   %.0f MB\n", $1/1024/1024}'

# Check if Kilo Code config exists
oc exec $POD -n wksp-ai-developer -c tooling-container -- cat ~/.config/kilo/kilo.jsonc 2>/dev/null | head -5

# Check VSIX files downloaded
oc exec $POD -n wksp-ai-developer -c tooling-container -- ls -lh /tmp/*.vsix 2>/dev/null

# Check projects cloned
oc exec $POD -n wksp-ai-developer -c tooling-container -- ls /projects/ 2>/dev/null
```

### Debug Failed Workspace

```bash
NS=wksp-ai-developer
# Check failure reason
oc get devworkspace agentic-coolstore -n $NS -o jsonpath='{.status.message}'

# Check events
oc get events -n $NS --sort-by='.lastTimestamp' | tail -15

# Common failures:
# - "FailedMount" on claim-devworkspace → second workspace inherited
#   CheCluster per-user RWO storage; factory destfiles must set
#   controller.devfile.io/storage-type: per-workspace. Do not delete
#   the shared claim while agentic-coolstore still needs it.
# - OOMKilled → increase memoryLimit in CR
# - postStart failed → git clone race, add wait loop
```

### Namespace Annotations

Dev Spaces requires specific annotations on workspace namespaces:

```yaml
labels:
  app.kubernetes.io/part-of: che.eclipse.org
  app.kubernetes.io/component: workspaces-namespace
annotations:
  che.eclipse.org/username: <username>  # Maps namespace to user
```

For `kube:admin`, the RoleBinding subject must use b64 encoding:

```yaml
subjects:
- apiGroup: rbac.authorization.k8s.io
  kind: User
  name: "b64:a3ViZTphZG1pbg=="
```

## Agentic Workspace

The `agentic-coolstore` DevWorkspace is the Stage 060 catalog entry point. It clones `adnan-drina/coolstore-inventory-service` and selects Kilo Code. Open it from Developer Hub → Coolstore Inventory Service → **Dev Spaces**, not from a factory URL. Stage 070/080 seats are separate factory workspaces.

## Users

| User | Namespace | Username annotation |
|------|-----------|-------------------|
| `kube:admin` | `wksp-kubeadmin` | `kube:admin` |
| `ai-admin` | `wksp-ai-admin` | `ai-admin` |
| `ai-developer` | `wksp-ai-developer` | `ai-developer` |
