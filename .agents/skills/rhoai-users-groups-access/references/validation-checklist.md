# Validation Checklist

Use this checklist before approving OpenShift AI user/group access changes,
runbooks, or cleanup operations.

## Source Review

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- Access behavior matches official docs: default all OpenShift users, optional
  restriction through selected OpenShift groups.
- `system:authenticated` is treated as broad access.
- LDAP group use requires LDAP group sync into OpenShift.
- Dashboard settings are not represented as invented CR fields.
- User cleanup guidance distinguishes access revocation from data deletion.

## Group Review

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get groups
oc describe group <rhoai-user-group>
oc describe group <rhoai-admin-group>
oc adm policy who-can get notebooks.kubeflow.org
```

Check:

- user and administrator groups exist, or default unrestricted access is
  intentional and documented
- group names are consistent between OpenShift and OpenShift AI dashboard
- administrator users can see the Settings navigation menu
- user-group members can access projects/workbenches as expected
- users outside selected groups cannot access the dashboard when access is
  restricted

## Dashboard Selection Review

Use the official dashboard path:

```text
OpenShift AI dashboard -> Settings -> User management
```

Check:

- administrator groups are selected under administrator groups
- user groups are selected under user groups
- `system:authenticated` is used only when broad access is intended
- users are instructed to log out of active OpenShift AI and Jupyter sessions
  after permission changes

## User Deletion Review

Before deleting user resources:

- user-owned basic workbenches are stopped
- user is removed from OpenShift AI groups or the identity-provider allowed
  group
- PVC data has been backed up or the owner has approved deletion without backup
- target PVC, ConfigMap, pod, and project names are listed
- destructive deletion has explicit approval

Readonly checks:

```bash
oc get pods -A | rg 'jupyter-nb-<username>'
oc get pvc -A | rg 'jupyter-nb-<username>'
oc get configmap -A | rg 'jupyterhub-singleuser-profile-<username>'
oc get projects | rg '<username>|<expected-user-project>'
```

Post-cleanup checks:

- user cannot access OpenShift AI
- stale `jupyter-nb-<username>` pods are gone
- selected user PVCs and ConfigMaps are absent
- user-owned projects are preserved, exported, or deleted according to the
  approved plan

## Fail Conditions

- A runbook claims access is restricted while `system:authenticated` still
  grants access.
- User permission changes are expected to take effect in active Jupyter
  sessions without logout.
- LDAP groups are selected before they are synced into OpenShift.
- PVCs or user projects are deleted without backup confirmation and explicit
  approval.
- Dashboard user-management backing fields are guessed.
