# Official Doc Extraction

Use this extraction to keep RBAC and SCC work grounded in official OCP sources.
Verify exact fields with `oc explain` before authoring manifests.

## RBAC Model

OpenShift uses RBAC objects to determine whether a user or service account can
perform an action. Project-scoped access is represented with `Role` and
`RoleBinding`; cluster-scoped access is represented with `ClusterRole` and
`ClusterRoleBinding`.

Review each binding for:

- subject kind, name, and namespace
- verbs
- API groups
- resources and resource names
- namespace scope versus cluster scope
- whether the permission belongs to a product Operator or demo workload

Use `oc auth can-i` and `oc adm policy who-can` to verify behavior rather than
inferring effective access from manifests alone.

## Service Accounts

Service accounts are identities for processes running in pods. When GitOps
introduces a service account, its RBAC should be scoped to the minimum API
groups and resources needed by that workload.

Do not grant cluster-admin or broad wildcard permissions to demo service
accounts unless a Red Hat product source requires it and the decision is
documented.

## SecurityContextConstraints

OpenShift SecurityContextConstraints control permissions for pods, including
privileged containers, privilege escalation, Linux capabilities, host
directories, SELinux context, user IDs, host namespaces, networking, FSGroup,
and supplemental groups.

Critical rules:

- Do not modify default SCCs.
- Do not delete default SCCs.
- Create and maintain custom SCCs only when a workload has a verified need.
- Grant high-privilege SCCs only to trusted workloads and service accounts.
- Do not set the `openshift.io/run-level` label on application namespaces.

When a workload needs a specific SCC, make that dependency explicit in the
README and manifest review notes, and verify the official product reason.

## Validation Signals

Healthy RBAC and SCC work should verify:

- all expected service accounts exist
- effective permissions match intent
- no unexpected wildcard or cluster-admin permissions are introduced
- SCC grants match workload needs
- pod admission failures are tied to SCC or pod security admission findings
- default SCCs remain unmodified
