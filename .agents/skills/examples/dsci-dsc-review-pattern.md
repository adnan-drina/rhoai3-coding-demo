# DSCI And DSC Review Pattern

Use this pattern for review. Verify the live CRD schema before committing
active GitOps manifests.

```yaml
apiVersion: datasciencecluster.opendatahub.io/v2
kind: DataScienceCluster
metadata:
  name: default-dsc
spec:
  components:
    dashboard:
      managementState: Managed
    kserve:
      managementState: Managed
    workbenches:
      managementState: Managed
      workbenchNamespace: rhods-notebooks
```

Review checklist:

- Does each component have explicit intent?
- Is the component supported on the active RHOAI/OCP baseline?
- Are component prerequisites installed first?
- Is `workbenchNamespace` still an install-time decision?
- Does the relevant component skill approve any nested fields?
