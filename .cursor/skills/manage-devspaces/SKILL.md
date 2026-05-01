---
name: manage-devspaces
description: >-
  Manage OpenShift Dev Spaces workspaces for the RHOAI coding demo. Use when
  creating, deleting, recreating, debugging, or updating DevWorkspace resources
  in wksp-* namespaces, or when troubleshooting workspace startup failures,
  OOM crashes, or DevWorkspace configuration.
---

# Managing Dev Spaces Workspaces

## Environment

- **CheCluster**: `devspaces` in `openshift-devspaces` (open-vsx.org, 1200s timeout, no-idle)
- **Workspaces**: 3 DevWorkspace CRs named `exercises` in `wksp-kubeadmin`, `wksp-ai-admin`, `wksp-ai-developer`
- **Cloned repos**:
  - `https://github.com/adnan-drina/coding-exercises.git` (devfile + exercises + Continue config) — all workspaces
  - `https://github.com/konveyor-ecosystem/coolstore.git` (Java EE migration target) — ai-admin, ai-developer only
- **Extensions**: Continue 1.3.38 + MTA 8.1.1 (pack + core + java) via `DEFAULT_EXTENSIONS` and `postStart` curl
- **GitOps**: Managed by ArgoCD `step-04-devspaces` Application with `Replace=true` sync option
- **Manifest**: `gitops/step-04-devspaces/base/devspaces/workspaces.yaml`

## Key Behaviors Learned

### DevWorkspace CR vs Repo Devfile

GitOps-created DevWorkspaces use the **inline CR spec only**. The `devfile.yaml` in the cloned repo is ignored. All commands, events, components, and resource limits must be defined inline in the DevWorkspace CR.

### postStart Race Condition

postStart `exec` commands run before git clone completes. Always include a wait loop:

```yaml
commands:
  - id: copy-continue-config
    exec:
      commandLine: |
        for i in $(seq 1 30); do
          [ -f /projects/coding-exercises/.vscode/config.yaml ] && break
          sleep 2
        done
        mkdir -p ~/.continue
        cp /projects/coding-exercises/.vscode/config.yaml ~/.continue/config.yaml 2>/dev/null
      component: tooling-container
events:
  postStart:
    - copy-continue-config
```

**Known issue**: postStart exec commands in GitOps-managed DevWorkspace CRs may not execute reliably. The manual fallback is:

```bash
cp /projects/coding-exercises/.vscode/config.yaml ~/.continue/config.yaml
```

### Extension Downloads in postStart

VSIX downloads from OpenVSX use CDN redirects that can time out silently. Always use `--max-time 120`:

```bash
curl -fsSL --max-time 120 -o /tmp/mta.vsix "https://open-vsx.org/api/redhat/mta-vscode-extension/8.1.1/file/redhat.mta-vscode-extension-8.1.1.vsix" 2>/dev/null || true
```

The MTA extension pack (`mta-vscode-extension`) does not reliably resolve its dependencies (`mta-core`, `mta-java`) from a local VSIX in Dev Spaces. Pin and download all three individually.

### Project Order Matters for MTA

The MTA Konveyor Core extension warns "Multi-root workspaces are not supported! Only the first workspace folder will be analyzed." List `coolstore` before `coding-exercises` so MTA analyzes the migration target by default.

### Memory Requirements

The default tooling container memory (~1152Mi) is insufficient for VS Code + Continue + MTA + Java/Maven. Use:

- **kubeadmin**: 4Gi limit / 1Gi request (coding-exercises only)
- **ai-admin, ai-developer**: 6Gi limit / 2Gi request (coolstore + MTA analysis + Maven builds)

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

ArgoCD with `ServerSideDiff=true` may not detect changes in nested arrays (e.g., `projects[0].git.remotes.origin`). Use `Replace=true` sync option:

```yaml
annotations:
  argocd.argoproj.io/sync-options: SkipDryRunOnMissingResource=true,Replace=true
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
oc patch application step-04-devspaces -n openshift-gitops --type=json \
  -p '[{"op":"remove","path":"/spec/syncPolicy/automated"}]'
oc patch devworkspace exercises -n $NS --type=merge -p '{"spec":{"started":false}}'
sleep 10
oc delete devworkspace exercises -n $NS --force --grace-period=0
oc delete pvc --all -n $NS --force --grace-period=0
sleep 5
oc apply -f gitops/step-04-devspaces/base/devspaces/workspaces.yaml
oc patch application step-04-devspaces -n openshift-gitops --type=merge \
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

# Check if Continue config was copied
oc exec $POD -n wksp-ai-developer -c tooling-container -- head -3 ~/.continue/config.yaml 2>/dev/null

# Check VSIX files downloaded
oc exec $POD -n wksp-ai-developer -c tooling-container -- ls -lh /tmp/*.vsix 2>/dev/null

# Check projects cloned
oc exec $POD -n wksp-ai-developer -c tooling-container -- ls /projects/ 2>/dev/null
```

### Debug Failed Workspace

```bash
NS=wksp-ai-developer
# Check failure reason
oc get devworkspace exercises -n $NS -o jsonpath='{.status.message}'

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

## Users

| User | Namespace | Username annotation |
|------|-----------|-------------------|
| `kube:admin` | `wksp-kubeadmin` | `kube:admin` |
| `ai-admin` | `wksp-ai-admin` | `ai-admin` |
| `ai-developer` | `wksp-ai-developer` | `ai-developer` |
