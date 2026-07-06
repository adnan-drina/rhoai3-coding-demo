# Validation Checklist

Use this checklist before accepting Kubeflow Spark Operator documentation,
GitOps manifests, Spark images, or runbooks.

## Source Alignment

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official Kubeflow Spark Operator guide is recorded when KSO behavior is
  introduced.
- API tier review is delegated to `rhoai-api-tiers`.
- General distributed workload workflows are delegated to
  `rhoai-distributed-workloads` and `rhoai-distributed-workload-workflows`.
- AI Pipelines and KFP workflows are delegated to `rhoai-ai-pipelines` and
  `rhoai-kfp-pipeline-authoring`.
- GitOps and manifest review are delegated to `project-gitops-authoring` and
  `project-manifest-review`.

## Activation Review

- OpenShift version is 4.19 or newer.
- The Red Hat OpenShift AI Operator is installed.
- KSO activation uses
  `DataScienceCluster.spec.components.kubeflowsparkoperator.managementState:
  Managed`.
- The active `DataScienceCluster` schema is verified before GitOps changes are
  accepted.
- Verification checks a Running pod in `redhat-ods-applications` with label
  `app.kubernetes.io/name=kubeflow-spark-operator`.

## API Tier Review

- `sparkoperator.k8s.io/v1beta2` is treated according to `rhoai-api-tiers`.
- Alpha API upgrade risk is documented in README or operations notes when used
  by active demo content.
- GitOps resources are scoped so they can be revised or removed during an
  upgrade without affecting unrelated demo stages.

## Spark Image Review

- Spark image includes Spark 4.0.1 or later.
- `SparkApplication.spec.sparkVersion` matches the runtime in the image.
- OpenShift `restricted-v2` SCC compatibility is reviewed.
- Required directories have appropriate group ownership and permissions for
  OpenShift random UID behavior.
- Image registry, tag, digest, and provenance are documented.
- Non-Red Hat images are explicitly recorded as source-backed exceptions and
  reviewed with project image provenance rules.

## SparkApplication Review

- `apiVersion` and `kind` match active CRD and official docs.
- Namespace is intentional and has required RBAC.
- `spec.type`, `spec.mode`, `spec.image`, `spec.mainApplicationFile`,
  `spec.sparkVersion`, `spec.restartPolicy`, driver, and executor settings are
  explicitly reviewed.
- Driver and executor CPU/memory values fit the target demo cluster.
- `serviceAccount` exists in the namespace.
- PVC volumes and volumeMounts refer to existing storage and access modes.
- Imported examples do not contain `runAsUser` or `runAsGroup`.
- Driver and executor pod status is checked after submission.

## Custom Namespace Review

- If using a custom namespace, copied `ServiceAccount`, `Role`, and
  `RoleBinding` resources are reviewed from `redhat-ods-applications`.
- Namespace fields are updated correctly in copied resources.
- `RoleBinding` namespace references are updated in both required places.
- Resources are applied to the custom namespace before creating
  `SparkApplication` resources there.
- Cross-namespace assumptions are not used as a substitute for explicit RBAC.

## Optional Read-Only Checks

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get datasciencecluster -A
oc get pods -n redhat-ods-applications -l app.kubernetes.io/name=kubeflow-spark-operator
oc get crd sparkapplications.sparkoperator.k8s.io
oc explain sparkapplication.spec
oc get serviceaccount spark-operator-spark -n redhat-ods-applications -o yaml
oc get role spark-operator-role -n redhat-ods-applications -o yaml
oc get rolebinding spark-operator-rolebinding -n redhat-ods-applications -o yaml
oc get sparkapplication -A
```

## Fail Conditions

Stop and correct the work if any of these are true:

- KSO activation uses guessed `DataScienceCluster` fields.
- `SparkApplication` fields are invented or copied without schema review.
- A non-Red Hat image is committed without documented provenance and review.
- `spec.sparkVersion` does not match the Spark runtime image.
- `runAsUser` or `runAsGroup` remains in imported Spark example YAML.
- A custom namespace lacks copied and reviewed Spark Operator RBAC.
- Alpha API upgrade risk is not documented for active demo GitOps resources.
