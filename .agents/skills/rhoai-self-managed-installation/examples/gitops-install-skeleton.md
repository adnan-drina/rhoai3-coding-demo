# GitOps Install Skeleton

This is a shape example for the reimplementation. Verify package, channel,
source, and component choices from official docs and the active OLM catalog
before committing real manifests.

## Suggested Layout

```text
gitops/
  platform/rhoai-operator/base/
    namespace.yaml
    operatorgroup.yaml
    subscription.yaml
    kustomization.yaml
  platform/rhoai-components/base/
    datasciencecluster.yaml
    kustomization.yaml
  argocd/app-of-apps/
    rhoai-operator.yaml
    rhoai-components.yaml
```

## Subscription Skeleton

```yaml
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: rhods-operator
  namespace: redhat-ods-operator
spec:
  name: rhods-operator
  channel: <verified-channel>
  installPlanApproval: Automatic
  source: redhat-operators
  sourceNamespace: openshift-marketplace
```

Project policy:

- Use `rhoai-update-channels` to select `<verified-channel>`.
- Omit `startingCSV` unless a pinned install is required.
- Use `Automatic` when installing latest available RHOAI in the verified
  feature-forward channel.

## DataScienceCluster Skeleton

```yaml
apiVersion: datasciencecluster.opendatahub.io/v2
kind: DataScienceCluster
metadata:
  name: default-dsc
spec:
  components:
    dashboard:
      managementState: Managed
    workbenches:
      managementState: Managed
      workbenchNamespace: rhods-notebooks
    kserve:
      managementState: Managed
    modelregistry:
      managementState: Removed
      registriesNamespace: rhoai-model-registries
```

Project policy:

- Enable only components with planned prerequisites.
- Keep component-specific configuration in later GitOps layers or component
  skills.
- Validate `status.phase` and `status.installedComponents` after ArgoCD sync.
