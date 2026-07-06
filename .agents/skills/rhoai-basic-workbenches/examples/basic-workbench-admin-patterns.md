# Basic Workbench Administration Patterns

These examples are dashboard runbooks and review patterns. They are not active
GitOps manifests because the captured Red Hat chapter describes dashboard and
console workflows.

## Administration Interface

```text
OpenShift AI dashboard
-> Applications
-> Enabled
-> Start basic workbench
-> Open application
-> Administration
```

Review points:

- The operator must have OpenShift AI administrator privileges.
- If the tile is hidden, review dashboard configuration before diagnosing the
  workbench itself.

## Start Another User's Basic Workbench

```text
1. Open the Start basic workbench application.
2. Open Administration.
3. Locate the user in Users.
4. Click Start workbench.
5. Complete the Start a basic workbench page.
6. Optionally select Start workbench in current tab.
7. Click Start workbench.
8. Confirm JupyterLab opens.
```

Review points:

- Confirm the selected image and size match available cluster capacity.
- Use administrator-start only for support, troubleshooting, or controlled
  setup.

## Access Another User's Running Workbench

```text
1. Open the Start basic workbench application.
2. Open Administration.
3. Locate the user in Users.
4. Click View server.
5. Click Access workbench.
6. Confirm JupyterLab opens in the user's workbench.
```

Review points:

- Record why administrator access is needed.
- Prefer user-led troubleshooting when administrator access is not required.

## Stop Basic Workbenches

Stop one workbench:

```text
1. Open Administration.
2. Locate the target user.
3. Use the row action menu and select Stop server.
4. Confirm Stop server.
5. Verify the action changes to Start workbench.
```

Stop all workbenches:

```text
1. Open Administration.
2. Click Stop all workbenches.
3. Click OK.
4. Verify running workbenches are stopped.
```

Review points:

- Use Stop all only when broad interruption is acceptable.
- Use this before shutdown or during resource pressure when user impact is
  understood.

## Idle Workbench Timeout

```text
OpenShift AI dashboard
-> Settings
-> Cluster settings
-> Idle workbench timeout
-> Stop idle workbenches after defined period
-> enter hours and minutes
-> Save changes
```

Verification:

```bash
oc get configmap notebook-controller-culler-config -n redhat-ods-applications -o yaml
```

Expected keys to review:

```text
ENABLE_CULLING
IDLENESS_CHECK_PERIOD
CULL_IDLE_TIME
```

## Workbench Pod Toleration

```text
OpenShift AI dashboard
-> Settings
-> Cluster settings
-> Workbench pod tolerations
-> Add a toleration to workbench pods to allow them to be scheduled to tainted nodes
-> Toleration key for workbench pods: workbenches-only
-> Save changes
```

Review points:

- A matching machine pool taint must exist before this affects scheduling.
- New workbench pods receive the toleration when created.
- Existing workbench pods receive the toleration after restart.

Verification:

```bash
oc describe pod <jupyter-nb-pod> -n rhods-notebooks
```

Check:

```text
Node
Tolerations
```

## Troubleshooting Triage Matrix

| Symptom | First checks | Resolution path |
|---------|--------------|-----------------|
| Jupyter 404 | User is in an OpenShift AI allowed user group | Add user to the correct group or contact Red Hat Support |
| Workbench does not start | `jupyter-nb-<username>-*` pod exists, pod state, CPU/RAM availability | Delete intermittent failed pod, choose smaller size, add resources, or collect logs for support |
| Database or disk full | `jupyter-nb-*` pod logs and workbench storage usage | Expand PV through OpenShift storage guidance or remove files permanently |

## Disk Cleanup Note

```markdown
Deleting files from the JupyterLab file explorer moves them to:

`/opt/app-root/src/.local/share/Trash/files`

To free persistent storage, permanently remove files from that trash location
after confirming they are no longer needed.
```
