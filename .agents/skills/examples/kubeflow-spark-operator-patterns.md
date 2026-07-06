# Kubeflow Spark Operator Patterns

These examples are review patterns. Verify the active baseline, CRD schema,
namespace RBAC, image provenance, and cluster resources before turning them
into demo GitOps.

## DataScienceCluster Activation Pattern

```yaml
apiVersion: datasciencecluster.opendatahub.io/v1
kind: DataScienceCluster
metadata:
  name: default-dsc
spec:
  components:
    kubeflowsparkoperator:
      managementState: Managed
```

Review points:

- Verify the active `DataScienceCluster` name and schema.
- Keep activation in the platform layer.
- Verify the operator pod in `redhat-ods-applications` after deployment.

## Spark Image Review Pattern

```text
Base image: <spark-runtime-image>
Spark version: 4.0.1 or newer
Registry target: <registry>/<namespace>/<image>:<tag>
OpenShift compatibility: restricted-v2 SCC reviewed
Provenance: Red Hat image | official-doc-sourced exception | other reviewed exception
```

Review points:

- The official example uses `apache/spark:4.0.1` and adjusts permissions for
  OpenShift restricted-v2 SCC compatibility.
- Document non-Red Hat image use as an exception.
- Match `spec.sparkVersion` to the Spark runtime in the image.

## SparkApplication Pattern

```yaml
apiVersion: sparkoperator.k8s.io/v1beta2
kind: SparkApplication
metadata:
  name: <spark-application-name>
  namespace: <spark-namespace>
spec:
  type: Scala
  mode: cluster
  image: <your-custom-spark-image>
  imagePullPolicy: IfNotPresent
  mainClass: org.apache.spark.examples.SparkPi
  mainApplicationFile: local:///opt/spark/examples/jars/spark-examples.jar
  arguments:
    - "1000"
  sparkVersion: "4.0.1"
  restartPolicy:
    type: Never
  driver:
    cores: 1
    coreLimit: "1200m"
    memory: "512m"
    serviceAccount: spark-operator-spark
    securityContext: {}
  executor:
    cores: 1
    instances: 1
    memory: "512m"
    securityContext: {}
```

Review points:

- Confirm `sparkoperator.k8s.io/v1beta2` API tier and active CRD schema.
- Remove `runAsUser` and `runAsGroup` from imported examples.
- Confirm `spark-operator-spark` exists in the namespace.
- Size driver and executor resources for the demo cluster.

## Custom Namespace RBAC Pattern

```bash
oc get serviceaccount spark-operator-spark -n redhat-ods-applications -o yaml
oc get role spark-operator-role -n redhat-ods-applications -o yaml
oc get rolebinding spark-operator-rolebinding -n redhat-ods-applications -o yaml
```

Review points:

- Update `metadata.namespace` to the custom namespace.
- Update both namespace references in the copied `RoleBinding`.
- Apply reviewed copies before creating `SparkApplication` resources in the
  custom namespace.

## Verification Pattern

```bash
oc get pods -n redhat-ods-applications -l app.kubernetes.io/name=kubeflow-spark-operator
oc get sparkapplication -n <spark-namespace>
oc get pods -n <spark-namespace>
oc describe sparkapplication <spark-application-name> -n <spark-namespace>
```

Review points:

- The operator pod should be Running.
- Spark driver and executor pods should be created by the submission flow.
- Inspect `SparkApplication.status` and events before guessing failure causes.
