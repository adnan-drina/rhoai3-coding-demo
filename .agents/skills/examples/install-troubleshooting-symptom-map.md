# Installation Troubleshooting Symptom Map

These commands are examples for evidence collection. Follow the OpenShift
safety guard in `AGENTS.md` before running live `oc` commands.

## Common Readonly Baseline

```bash
oc get subscription,csv,installplan -n redhat-ods-operator
oc get pods -n redhat-ods-operator -o wide
oc get events -n redhat-ods-operator --sort-by=.lastTimestamp
oc get dsci,dsc -A
oc logs -n redhat-ods-operator -l name=rhods-operator --tail=200
```

## Failure To Pull From Quay

Look for:

```text
Failure to pull from quay
```

Evidence:

```bash
oc get events -n redhat-ods-operator --sort-by=.lastTimestamp
oc describe pod <operator-pod> -n redhat-ods-operator
```

Official resolution: contact Red Hat Support after collecting evidence.

## Unsupported Infrastructure

Look for:

```text
ERROR: Deploying on $infrastructure, which is not supported. Failing Installation
```

Evidence:

```bash
oc logs <operator-pod> -n redhat-ods-operator -c rhods-operator
oc get infrastructure cluster -o yaml
```

Resolution path: verify the environment against Red Hat OpenShift AI supported
configurations before attempting a new installation.

## ODH CR Or Notebooks CR Creation Failure

Look for:

```text
ERROR: Attempt to create the ODH CR failed.
ERROR: Attempt to create the RHODS Notebooks CR failed.
```

Evidence:

```bash
oc logs <operator-pod> -n redhat-ods-operator -c rhods-operator
oc get dsci,dsc -A
```

Official resolution: contact Red Hat Support.

## Dashboard Not Accessible After Install

Official condition:

- `redhat-ods-applications`, `redhat-ods-monitoring`, and
  `redhat-ods-operator` namespaces are `Active`
- dashboard still fails because one or more pods are in an error state

Evidence:

```bash
oc get ns redhat-ods-applications redhat-ods-monitoring redhat-ods-operator
oc get pods -A --field-selector=status.phase!=Running,status.phase!=Succeeded
oc get pods -n redhat-ods-applications
oc logs <failing-pod> -n <namespace> --tail=200
```

Resolution path: inspect the failing pod status link or pod logs and continue
with the relevant component troubleshooting path.

## Reinstall Failure From Leftover Auth

Look for:

```text
unable to find DSCInitialization
```

in logs that reference:

```text
{"name":"auth"}
```

Evidence:

```bash
oc logs <operator-pod> -n redhat-ods-operator -c rhods-operator
oc api-resources --api-group=services.platform.opendatahub.io
oc get auth -A
```

Official resolution path:

1. Uninstall the OpenShift AI Operator.
2. Delete the leftover `Auth` custom resource.
3. Install the OpenShift AI Operator again.

Do not delete `Auth` until uninstall state and user intent are confirmed.

## dedicated-admins RBAC Failure

Look for:

```text
ERROR: Attempt to create the RBAC policy for dedicated admins group in $target_project failed.
```

Evidence:

```bash
oc logs <operator-pod> -n redhat-ods-operator -c rhods-operator
oc get rolebinding,clusterrolebinding -A | rg "dedicated-admins|redhat-ods"
```

Official resolution: contact Red Hat Support.

## ODH Parameter Secret Missing

Look for:

```text
ERROR: Addon managed odh parameter secret does not exist.
```

Evidence:

```bash
oc logs <operator-pod> -n redhat-ods-operator -c rhods-operator
oc get secret -A | rg "odh|parameter"
```

Official resolution: contact Red Hat Support.
