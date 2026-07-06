# Connected Application Patterns

These examples are review patterns. Verify the active dashboard state,
application tile, support posture, credentials, and namespace requirements
before using them in demo steps.

## Discovery Pattern

```text
Dashboard path: Applications -> Explore
Application tile: <application-name>
Available action: Enable | documentation/resource link | no direct action
Operator required: yes | no | unknown
Required namespace: <tile-specified-namespace-or-none>
```

Review points:

- The Enable button appears only when the application does not require an
  OpenShift Operator installation.
- Operator installation belongs to administrator or platform workflow.
- Do not assume an Explore tile means the application is installed and ready.

## SaaS Enablement Pattern

```text
Application: <saas-application>
Prerequisite: administrator installed or configured application access
Credential: service key from approved secret source
Verification: tile appears on Applications -> Enabled
Endpoint: <endpoint-shown-on-tile-or-none>
```

Review points:

- Never commit service keys.
- Record endpoint URLs only when the Enabled tile displays them.
- Store endpoint URLs as environment variables in notebooks when useful.

## Disabled Tile Removal Pattern

```text
Dashboard path: Applications -> Enabled
Tile state: Disabled
Action: remove tile link
Verification: tile no longer appears on Enabled page
```

Review points:

- An administrator must disable the application first.
- Removing the tile does not uninstall the backing application or Operator.

## Start Basic Workbench Pattern

```text
Use case: lightweight Jupyter access or external notebook with no project dependencies
Workbench image: <image>
Version: <image-version>
Container size: <size>
Accelerator: none | <accelerator-type-and-count>
Environment variables: placeholders only; Secret for sensitive values
Open behavior: current tab | new tab
```

Review points:

- Prefer project workbenches for normal demo steps.
- Use Secret handling for passwords, keys, and tokens.
- Check accelerator support before selecting accelerators.
- Capture Events log details if startup fails.

## Basic Workbench Settings Update Pattern

```text
JupyterLab -> File -> Hub Control Panel
Stop workbench
Update settings
Start workbench
Verify IDE opens with updated settings
```

Review points:

- Stopping the workbench interrupts the user's active session.
- Increasing memory or compute should be tied to a real workload need.
- Administrator troubleshooting belongs in `rhoai-basic-workbenches` or
  `env-troubleshoot`.

## Handoff Pattern

| Need | Use skill |
|------|-----------|
| Create, hide, or disable dashboard tiles | `rhoai-dashboard-applications` |
| Add user to OpenShift AI groups | `rhoai-users-groups-access` |
| Create project workbench with connections/storage | `rhoai-project-workflows` |
| Notebook, Git, package workflow | `rhoai-data-science-ide-workflows` |
| Basic workbench admin, timeout, tolerations | `rhoai-basic-workbenches` |
| GPU/accelerator enablement | `rhoai-nvidia-gpu-accelerators` |
