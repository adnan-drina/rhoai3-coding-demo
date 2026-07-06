# User Group Access Patterns

These examples are command and review patterns. Follow the OpenShift safety
guard in `AGENTS.md` before running live commands.

## Suggested Demo Groups

Use environment-provided identity-provider groups when available. Otherwise,
for a disposable demo cluster, use clear OpenShift group names:

```text
rhoai-users
rhoai-admins
```

Select those groups in:

```text
OpenShift AI dashboard -> Settings -> User management
```

Do not rely on `system:authenticated` when the demo story requires explicit
access control.

## OpenShift Group Review

```bash
oc get groups
oc describe group rhoai-users
oc describe group rhoai-admins
```

If a group is created directly in OpenShift for a demo:

```bash
oc adm groups new rhoai-users
oc adm groups new rhoai-admins
oc adm groups add-users rhoai-users <username>
oc adm groups add-users rhoai-admins <admin-username>
```

Prefer identity-provider-managed groups for real environments.

## Access Verification

```text
Admin user:
- can log in to OpenShift AI
- can see Settings
- can manage workbenches and pipeline applications across projects

Normal user:
- can log in to OpenShift AI
- can use projects and workbenches
- cannot see administrator-only settings

Unauthorized user, when access is restricted:
- cannot access the dashboard
- receives an access-needed message
```

## User Removal Checklist

Before removing user access:

```text
1. Confirm the username.
2. Stop user-owned basic workbenches.
3. Remove the user from rhoai-users and/or rhoai-admins.
4. Remove the user from the identity-provider allowed group if full removal is required.
5. Ask the user to log out of OpenShift AI and Jupyter sessions.
6. Back up PVC data before deleting storage.
```

Readonly cleanup discovery:

```bash
username="<username>"
oc get pods -A | rg "jupyter-nb-${username}"
oc get pvc -A | rg "jupyter-nb-${username}"
oc get configmap -A | rg "jupyterhub-singleuser-profile-${username}"
```

Destructive cleanup, only after backup and explicit approval:

```bash
oc delete pod -n <workbench-namespace> "jupyter-nb-${username}-<suffix>"
oc delete pvc -n <workbench-namespace> "jupyter-nb-${username}"
oc delete configmap -n <workbench-namespace> "jupyterhub-singleuser-profile-${username}"
```

Do not bulk-delete user projects without a reviewed project ownership and
backup plan.
