---
name: manage-devspaces
metadata:
  author: rhoai3-coding-demo
  version: 1.1.0
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

- **CheCluster**: `devspaces` in `openshift-devspaces` (open-vsx.org, 1200s timeout, no-idle)
- **Workspaces**: 3 DevWorkspace CRs in each `wksp-kubeadmin`, `wksp-ai-admin`, and `wksp-ai-developer` namespace: `getting-started-ai-coding`, `coolstore-inventory-service`, and `mca-coolstore`
- **Cloned repos**:
  - `https://github.com/adnan-drina/getting-started-ai-coding.git` — Stage 060 onboarding and MaaS checks
  - `https://github.com/adnan-drina/coolstore-inventory-service.git` — deferred engineering workflows
  - `https://github.com/rhpds/mca-coolstore.git` — modernization workflow
- **Extensions**: Kilo Code 7.4.7 via `DEFAULT_EXTENSIONS` in all workspaces; MTA 8.1.2 (pack + core + java) via `DEFAULT_EXTENSIONS` only in `mca-coolstore`
- **GitOps**: Managed by ArgoCD `050-advanced-app-platform` Application with repair hook (no Replace on DevWorkspaces)
- **AI tool selection**: `.opencode/` directory in repo selects OpenCode; absent selects Kilo Code (mutually exclusive)
- **Manifest**: `gitops/stages/050-advanced-app-platform/base/devspaces/workspaces.yaml`

## Key Behaviors Learned

### DevWorkspace CR vs Repo Devfile

GitOps-created DevWorkspaces use the **inline CR spec only**. The `devfile.yaml` in the cloned repo is ignored. All commands, events, components, and resource limits must be defined inline in the DevWorkspace CR.

### postStart Initialization

The postStart event runs the `init-ai-tools` command, which executes the centralized init script from the `devspace-ai-tools-init` ConfigMap. This script handles Kilo Code configuration, extension installation, and tool setup.

postStart `exec` commands run before git clone completes. The init script includes a wait loop to handle the race condition.

**Known issue**: postStart exec commands in GitOps-managed DevWorkspace CRs may not execute reliably. The manual fallback is to exec into the pod and run the init script manually.

### Extension Downloads in postStart

VSIX downloads from OpenVSX use CDN redirects that can time out silently. Always use `--max-time 120`:

```bash
curl -fsSL --max-time 120 -o /tmp/kilo.vsix "https://open-vsx.org/api/kilocode/kilo-code/linux-x64/7.4.7/file/kilocode.kilo-code-7.4.7@linux-x64.vsix" 2>/dev/null || true
curl -fsSL --max-time 120 -o /tmp/mta.vsix "https://open-vsx.org/api/redhat/mta-vscode-extension/8.1.2/file/redhat.mta-vscode-extension-8.1.2.vsix" 2>/dev/null || true
```

The MTA extension pack (`mta-vscode-extension`) does not reliably resolve its dependencies (`mta-core`, `mta-java`) from a local VSIX in Dev Spaces. Pin and download all three individually.

### Project Order Matters for MTA

The MTA Konveyor Core extension warns "Multi-root workspaces are not supported! Only the first workspace folder will be analyzed." Keep `mca-coolstore` as a single-repository workspace so MTA analyzes the migration target by default.

### Memory Requirements

The default tooling container memory (~1152Mi) is insufficient for VS Code + Kilo Code + MTA + Java/Maven. Use:

- **getting-started-ai-coding** and **coolstore-inventory-service**: 4Gi limit / 1Gi request
- **mca-coolstore**: 6Gi limit / 2Gi request for MTA analysis and Maven builds

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

The Dev Spaces operator reconciles DevWorkspaces. Manual `oc apply` changes may be reverted. To update a workspace spec:

1. Disable ArgoCD auto-sync
2. Stop the workspace (`spec.started: false`)
3. Delete the DevWorkspace CR
4. Delete PVCs in the namespace
5. Apply the new CR
6. Re-enable ArgoCD auto-sync

## Common Operations

### Recreate a Workspace (clean slate)

```bash
NS=wksp-ai-developer
oc patch application 050-advanced-app-platform -n openshift-gitops --type=json \
  -p '[{"op":"remove","path":"/spec/syncPolicy/automated"}]'
oc patch devworkspace getting-started-ai-coding -n $NS --type=merge -p '{"spec":{"started":false}}'
sleep 10
oc delete devworkspace getting-started-ai-coding -n $NS --force --grace-period=0
oc delete pvc --all -n $NS --force --grace-period=0
sleep 5
oc apply -f gitops/stages/050-advanced-app-platform/base/devspaces/workspaces.yaml
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
oc exec $POD -n wksp-ai-developer -c tooling-container -- cat ~/.config/kilo/kilo.json 2>/dev/null | head -5

# Check VSIX files downloaded
oc exec $POD -n wksp-ai-developer -c tooling-container -- ls -lh /tmp/*.vsix 2>/dev/null

# Check projects cloned
oc exec $POD -n wksp-ai-developer -c tooling-container -- ls /projects/ 2>/dev/null
```

### Debug Failed Workspace

```bash
NS=wksp-ai-developer
# Check failure reason
oc get devworkspace getting-started-ai-coding -n $NS -o jsonpath='{.status.message}'

# Check events
oc get events -n $NS --sort-by='.lastTimestamp' | tail -15

# Common failures:
# - "FailedMount" → stale routing reference, delete and recreate
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

The `agentic-coolstore` DevWorkspace is the Stage 060/070 golden-path entry point. It clones `rhpds/mca-coolstore` with an `.opencode/` directory, selecting OpenCode as the AI tool instead of Kilo Code. This workspace is used for agentic development demos.

## Users

| User | Namespace | Username annotation |
|------|-----------|-------------------|
| `kube:admin` | `wksp-kubeadmin` | `kube:admin` |
| `ai-admin` | `wksp-ai-admin` | `ai-admin` |
| `ai-developer` | `wksp-ai-developer` | `ai-developer` |
