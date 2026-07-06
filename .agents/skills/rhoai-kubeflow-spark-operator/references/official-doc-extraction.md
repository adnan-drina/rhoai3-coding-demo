# Official Doc Extraction

Extract only behavior supported by the official Kubeflow Spark Operator guide
and active-baseline linked Red Hat docs.

## Purpose And Supported Capabilities

- The Kubeflow Spark Operator lets users run Spark data processing applications
  in a distributed environment on Red Hat OpenShift AI.
- Users create custom resources to specify, run, and surface Spark
  applications.
- KSO for Apache Spark currently supports:
  - Spark versions 4.0.1 and above
  - creation of a `spark-submit` job when a `SparkApplication` custom resource
    is created
  - native Cron support for scheduled applications
  - Spark pod customization, including ConfigMap/volume mounts and pod
    affinity
  - automatic application restart with custom policies
  - application and driver metrics collection/export to Prometheus

## Architecture

- KSO includes a `SparkApplication` Controller that watches create, update, and
  delete events in `SparkApplication` resources.
- The Submission Runner creates and runs a `spark-submit` job that starts
  Spark driver and executor pods.
- The Spark Pod Monitor observes driver and executor pods and updates the
  `.status` field of the `SparkApplication` custom resource.
- The Mutating Admission Webhook intercepts pod creation requests and injects
  ConfigMap mounts or volumes into driver and executor pods before scheduling.

## Activation

- Activate KSO by setting `managementState: Managed` for
  `spec.components.kubeflowsparkoperator` in the OpenShift AI
  `DataScienceCluster` custom resource.
- Prerequisites in the official guide:
  - OpenShift 4.19 or newer
  - cluster administrator privileges
  - OpenShift CLI installed
  - Red Hat OpenShift AI Operator installed
  - an existing Spark image that can be imported to the OpenShift AI cluster
- Verification: in `redhat-ods-applications`, a pod with label
  `app.kubernetes.io/name=kubeflow-spark-operator` is displayed and Running.

## Spark Image

- The official guide shows a custom Spark image based on `apache/spark:4.0.1`.
- The example adds permissions compatible with OpenShift `restricted-v2` SCC:
  group ownership for `/opt/spark`, work directories, logs, `/home/spark`,
  and writable `/tmp`.
- The image is built with `podman build` and pushed to a registry.
- The `SparkApplication.spec.sparkVersion` value must match the Spark runtime
  included in the image.
- This repo must review image provenance before committing a demo image. The
  official example is a source-backed pattern, not a blanket approval for any
  upstream image.

## SparkApplication Custom Resource

- The official example uses:
  - `apiVersion: sparkoperator.k8s.io/v1beta2`
  - `kind: SparkApplication`
  - `spec.type: Scala`
  - `spec.mode: cluster`
  - `spec.image`
  - `spec.imagePullPolicy`
  - `spec.mainClass`
  - `spec.mainApplicationFile`
  - `spec.arguments`
  - `spec.sparkVersion`
  - `spec.restartPolicy.type`
  - `spec.driver`
  - `spec.executor`
- `mode` can include `cluster` or `client`; in cluster mode, the driver runs
  in a pod.
- `image` must contain the Spark runtime.
- `mainApplicationFile` is the application entry point.
- `restartPolicy` examples include `Never`, `OnFailure`, and `Always`.
- Driver and executor sections include resource requests such as cores and
  memory, labels, service accounts, and security contexts.
- Volumes and volumeMounts can reference PVCs for input and output data.
- The `spark-operator-spark` service account is automatically created by the
  Spark Operator installation and includes RBAC for Spark drivers to create and
  manage executor pods.
- When using Spark example YAMLs in OpenShift AI, remove `runAsGroup` and
  `runAsUser`; the official guide says these parameters can cause jobs to
  crash.

## Custom Namespace

- Spark applications can run in a custom namespace.
- The official guide instructs users to inspect the default resources in
  `redhat-ods-applications` and copy them into the custom namespace:
  - `ServiceAccount` named `spark-operator-spark`
  - `Role` named `spark-operator-role`
  - `RoleBinding` named `spark-operator-rolebinding`
- Update the `namespace:` field on the copied resources.
- For `RoleBinding`, update both namespace fields as needed.
- Apply the copied resources to the custom namespace before running
  `SparkApplication` there.

## API Tier And Support Posture

- Use `rhoai-api-tiers` before treating `sparkoperator.k8s.io/v1beta2` as a
  stable contract.
- In the active API tier skill, `sparkoperator.k8s.io/v1beta2` is recorded as
  Alpha.
- Alpha APIs have no backward compatibility guarantees. Demo GitOps that uses
  this API must be easy to revise during upgrades.

## Do Not Infer

- Do not invent `SparkApplication` fields beyond official docs or active CRD
  schema.
- Do not assume all upstream Spark images are valid for this demo.
- Do not assume the default Spark Operator service account works in custom
  namespaces without copied RBAC.
- Do not leave `runAsUser` or `runAsGroup` in imported examples.
- Do not treat Spark Operator as equivalent to Kueue/Ray/Training Operator or
  AI Pipelines.
- Do not treat Alpha API resources as stable long-term contracts.
