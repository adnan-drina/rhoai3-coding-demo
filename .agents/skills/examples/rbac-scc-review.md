# RBAC And SCC Review Pattern

Use this pattern when reviewing planned permissions:

1. Identify the workload identity: user, group, or service account.
2. Decide whether the permission can be namespace-scoped.
3. Check the exact API group, resource, and verb needed.
4. Verify the effective permission with `oc auth can-i`.
5. If pod admission fails, inspect SCC and pod security admission before adding
   broad privileges.
6. Keep any cluster-admin or privileged SCC grant tied to a documented product
   requirement.
