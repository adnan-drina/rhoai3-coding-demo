# Official Doc Extraction

This extraction is derived from the official RHOAI 3.4 chapter captured in
`source-capture.md`.

## Recommended Uninstall Surface

Red Hat recommends using the OpenShift CLI (`oc`) to uninstall OpenShift AI
Self-Managed. Depending on the OpenShift version, uninstalling through the web
console might not prompt for all associated components and can leave the final
cluster state unclear.

The official procedure removes the Red Hat OpenShift AI Operator and any
OpenShift AI components installed and managed by the Operator.

Prerequisites:

- cluster administrator privileges
- OpenShift CLI installed
- persistent disks or volumes used by PVCs are backed up

## Resources Removed By Uninstall

Uninstalling OpenShift AI removes these resources:

- `DataScienceCluster` custom resource instance and component custom resource
  instances it created
- `DSCInitialization` custom resource instance
- `Auth` custom resource instance created during or after installation
- `FeatureTracker` custom resource instances created during or after
  installation
- `ServiceMesh` custom resource instance created by the Operator during or
  after installation
- `KNativeServing` custom resource instance created by the Operator during or
  after installation
- `redhat-ods-applications`, `redhat-ods-monitoring`, and `rhods-notebooks`
  namespaces created by the Operator
- workloads in the `rhods-notebooks` namespace
- `Subscription`, `ClusterServiceVersion`, and `InstallPlan` objects
- `KfDef` object for version 1 Operator only

## Resources Retained By Uninstall

Uninstalling OpenShift AI retains these resources:

- projects created by users
- custom resource instances created by users
- custom resource definitions created by users or by the Operator

These retained resources might remain but not be functional after uninstall.
Red Hat recommends reviewing projects and custom resources after uninstall and
deleting anything no longer in use. Examples of retained resources that can
become problematic include pipelines that cannot run, notebooks that cannot be
undeployed, or models that cannot be undeployed.

## Official CLI Procedure

The official CLI flow:

1. Log in to OpenShift as a cluster administrator.
2. Create the deletion ConfigMap in `redhat-ods-operator`.
3. Label the ConfigMap with
   `api.openshift.com/addon-managed-odh-delete=true`.
4. Wait for `redhat-ods-applications` to be deleted.
5. Delete the `redhat-ods-operator` namespace.

Official verification:

- `rhods-operator` Subscription no longer exists.
- these projects no longer exist:
  - `redhat-ods-applications`
  - `redhat-ods-monitoring`
  - `redhat-ods-operator`
  - `rhods-notebooks`, only if workbenches were installed

## GitOps Implication

If ArgoCD still manages RHOAI install resources, it can recreate the same
resources the uninstall flow is deleting. In this repo, uninstall planning must
include ArgoCD Application suspension, deletion, or source retargeting before
the official uninstall procedure is run.

## Unresolved Items

This chapter does not define:

- backup implementation for PVC data
- how to decide which retained user resources should be deleted
- ArgoCD-specific decommissioning commands
- how to clean up external cloud resources such as GPU MachineSets
- reinstall procedure after uninstall

Use the relevant project environment skills and official documentation before
performing those steps.
