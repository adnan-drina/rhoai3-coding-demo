# Kueue Workload Management Patterns

These examples are review patterns. Follow the OpenShift safety guard before
running live commands.

## Activate Kueue Integration

Use Red Hat build of Kueue Operator with `Unmanaged` RHOAI integration.

```bash
oc patch datasciencecluster default-dsc \
  --type='merge' \
  -p '{"spec":{"components":{"kueue":{"managementState":"Unmanaged"}}}}' \
  -n redhat-ods-operator
```

With custom default queue names:

```bash
oc patch datasciencecluster default-dsc \
  --type='merge' \
  -p '{"spec":{"components":{"kueue":{"managementState":"Unmanaged","defaultClusterQueueName":"gpu-cluster-queue","defaultLocalQueueName":"gpu-local-queue"}}}}' \
  -n redhat-ods-operator
```

## Enable Kueue In The Dashboard

```bash
oc patch odhdashboardconfig odh-dashboard-config \
  -n redhat-ods-applications \
  --type merge \
  -p '{"spec":{"dashboardConfig":{"disableKueue":false}}}'
```

## Enable Existing Projects

New projects created from the OpenShift AI dashboard are labeled
automatically when dashboard Kueue is enabled. Existing projects and projects
created with `oc` need the label:

```bash
oc label namespace <project-namespace> kueue.openshift.io/managed=true --overwrite
```

Verify:

```bash
oc get ns <project-namespace> \
  -o jsonpath='{.metadata.labels.kueue\.openshift\.io/managed}{"\n"}'
oc get localqueues -n <project-namespace>
```

## Workload Queue Label Fragment

For CLI or SDK-created workloads in Kueue-managed namespaces:

```yaml
metadata:
  labels:
    kueue.x-k8s.io/queue-name: gpu-local-queue
```

The RHOAI validation webhook enforces this label for:

```text
InferenceService
Notebook
PyTorchJob
RayCluster
RayJob
```

Dashboard-created workloads should receive this through a hardware profile that
specifies a local queue.

## Migration Review Fragment

Embedded Kueue `Managed` mode is deprecated. To migrate:

```yaml
spec:
  components:
    kueue:
      managementState: Removed
```

After embedded Kueue is removed and Red Hat build of Kueue Operator is
installed:

```yaml
spec:
  components:
    kueue:
      managementState: Unmanaged
      defaultClusterQueueName: gpu-cluster-queue
      defaultLocalQueueName: gpu-local-queue
```

Optional preservation of the old ConfigMap for reference:

```bash
oc annotate configmap kueue-manager-config \
  -n redhat-ods-applications \
  opendatahub.io/managed=false
```

## Troubleshooting Discovery

```bash
oc get pods -n openshift-kueue-operator
oc logs -n openshift-kueue-operator deployment/kueue-controller-manager --tail=100
oc get localqueues -n <project-namespace>
oc get clusterqueues
oc get events -n <project-namespace> --sort-by='.lastTimestamp'
```

Use active resource names from the cluster. Do not assume Deployment names if
the installed Red Hat build of Kueue Operator version differs.
