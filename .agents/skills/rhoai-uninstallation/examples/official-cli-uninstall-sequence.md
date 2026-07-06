# Official CLI Uninstall Sequence

These commands are destructive live-cluster operations. Follow the OpenShift
safety guard in `AGENTS.md`, confirm the target cluster with the user, and
confirm PVC backups before running them.

## Product Procedure

Create the deletion ConfigMap:

```bash
oc create configmap delete-self-managed-odh -n redhat-ods-operator
```

Set the deletion label:

```bash
oc label configmap/delete-self-managed-odh \
  api.openshift.com/addon-managed-odh-delete=true \
  -n redhat-ods-operator
```

Wait for `redhat-ods-applications` to be deleted:

```bash
PROJECT_NAME=redhat-ods-applications

while oc get project "$PROJECT_NAME" >/dev/null 2>&1; do
  echo "The $PROJECT_NAME project still exists"
  sleep 1
done

echo "The $PROJECT_NAME project no longer exists"
```

Delete the Operator namespace:

```bash
oc delete namespace redhat-ods-operator
```

## Product Verification

Confirm the `rhods-operator` Subscription no longer exists:

```bash
oc get subscriptions --all-namespaces | rg rhods-operator || true
```

Confirm Operator-managed namespaces no longer exist:

```bash
oc get namespaces | rg "redhat-ods|rhods" || true
```

Expected absent namespaces:

- `redhat-ods-applications`
- `redhat-ods-monitoring`
- `redhat-ods-operator`
- `rhods-notebooks`, only if workbenches were installed

## GitOps Guard

Before running the product procedure in this repo, ensure ArgoCD will not
recreate RHOAI resources. The exact command depends on the active GitOps
implementation, but the review question is fixed:

```text
Are all ArgoCD Applications that manage RHOAI install resources suspended,
removed, or retargeted away from the current cluster?
```

Do not use this uninstall sequence as a shutdown workflow.
