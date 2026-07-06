# Validation Checklist

Use this checklist before accepting RBAC, service-account, or SCC guidance.

## Source Validation

- The active OCP baseline is read from `docs/PLATFORM_BASELINE.md`.
- The source URL uses the pinned OCP documentation version.
- RBAC and SCC behavior comes from official OCP docs or active cluster schema.
- Privileged, host access, wildcard, or cluster-admin permissions have a
  documented product or demo reason.
- Identity-provider work is not mixed into RBAC/SCC changes.

## Manifest Review

- Role and binding scope is correct.
- Service account namespace references are correct.
- ClusterRoles are used only when namespace-scoped Roles are insufficient.
- Default SCCs are not modified or deleted.
- Custom SCCs are created only when required.
- SCC grants target specific service accounts or groups.

## Discovery Commands

Run only after the OpenShift safety guard confirms the target cluster:

```sh
oc auth can-i <verb> <resource> -n <namespace> --as <user-or-service-account>
oc adm policy who-can <verb> <resource> -n <namespace>
oc get role,rolebinding -n <namespace>
oc get clusterrole,clusterrolebinding
oc get serviceaccount -A
oc get scc
oc describe scc <scc-name>
```

For schema checks:

```sh
oc explain role.rules
oc explain rolebinding.subjects
oc explain clusterrole.rules
oc explain securitycontextconstraints.security.openshift.io
```
