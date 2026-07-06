# Group Selection Patterns

These examples are review and runbook patterns. They are not active automation.

## Recommended Demo Group Model

| OpenShift AI role | Example group | Purpose |
|-------------------|---------------|---------|
| Administrator | `rhoai-admins` | Platform administrators who can access Settings and manage OpenShift AI configuration |
| User | `rhoai-users` | Demo users who can access OpenShift AI components such as projects and workbenches |

Use identity-provider group names instead when the demo environment already
provides enterprise groups.

## Dashboard Runbook

```text
1. Log in to OpenShift AI as an administrator.
2. Open Settings -> User management.
3. Under Red Hat OpenShift AI administrator groups, select rhoai-admins.
4. Under Red Hat OpenShift AI user groups, select rhoai-users.
5. Confirm system:authenticated is absent unless broad access is intended.
6. Save changes.
```

## Access Acceptance Matrix

| Test user | Expected result |
|-----------|-----------------|
| Member of administrator group | Can log in and see Settings |
| Member of user group | Can log in and use projects/workbenches |
| Member of neither group | Cannot access OpenShift AI when access is restricted |
| OpenShift `cluster-admin` | Has OpenShift AI administrator access by default |

## Read-Only Group Precheck

Run only after following the repository OpenShift safety guard:

```bash
oc get groups
oc describe group rhoai-admins
oc describe group rhoai-users
```

Review points:

- Groups exist before dashboard selection.
- Group membership matches the intended demo audience.
- LDAP-backed groups are synced into OpenShift before selection.

## Operations Note Template

```markdown
## OpenShift AI Access Groups

The demo restricts OpenShift AI access to explicit OpenShift groups:

- Administrator group: `rhoai-admins`
- User group: `rhoai-users`

Dashboard path:

`OpenShift AI dashboard -> Settings -> User management`

`system:authenticated` is not selected because the demo environment should not
grant OpenShift AI access to every authenticated OpenShift user.
```
