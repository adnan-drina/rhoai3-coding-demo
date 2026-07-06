# Project-Scoped Resource Patterns

These examples show review patterns, not complete production manifests. Copy
full resource YAML from official docs, a reviewed GitOps source, or an existing
verified resource, then adjust only the project-scoping fields described here.

## Enable Project-Scoped Resources In Dashboard Configuration

Verify the exact `OdhDashboardConfig` schema before authoring.

```yaml
apiVersion: dashboard.opendatahub.io/v1
kind: OdhDashboardConfig
metadata:
  name: odh-dashboard-config
  namespace: redhat-ods-applications
spec:
  dashboardConfig:
    disableProjectScoped: false
```

Do not apply this as a full replacement unless the existing dashboard
configuration has been reviewed and unrelated fields are preserved.

## Project-Scoped Workbench Image Review Fragment

```yaml
apiVersion: image.openshift.io/v1
kind: ImageStream
metadata:
  name: team-workbench-image
  namespace: team-project
  annotations:
    opendatahub.io/notebook-image-name: Team Workbench Image
```

Add the full ImageStream tags, labels, and dashboard annotations from
`rhoai-workbenches-custom-images` or a trusted existing ImageStream.

## Project-Scoped Hardware Profile Review Fragment

```yaml
apiVersion: <verify-active-api-version>
kind: HardwareProfile
metadata:
  name: team-gpu-profile
  namespace: team-project
spec:
  displayName: Team GPU Profile
```

Use `rhoai-nvidia-gpu-accelerators` and active CRD verification for the full
hardware profile schema.

## Project-Scoped Serving Runtime Template Review Fragment

```yaml
apiVersion: template.openshift.io/v1
kind: Template
metadata:
  name: team-serving-runtime-template
  namespace: team-project
objects:
  - apiVersion: <verify-serving-runtime-api-version>
    kind: ServingRuntime
    metadata:
      name: team-serving-runtime
      annotations:
        openshift.io/display-name: Team Serving Runtime
```

Use official KServe/RHOAI serving documentation and active CRD verification for
the complete embedded `ServingRuntime` object.

## Readonly Discovery Commands

Follow the OpenShift safety guard before running live commands.

```bash
oc get imagestream -n redhat-ods-applications
oc get hardwareprofile -A
oc get template -A -o yaml | rg 'kind: ServingRuntime'
oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o yaml
```
