# Official Doc Extraction

## Namespace Model

- The predefined operator namespace is `redhat-ods-operator`.
- The predefined applications namespace is `redhat-ods-applications`.
- The predefined basic workbench namespace is `rhods-notebooks`.
- If custom namespaces are used, create and label them before installing the
  OpenShift AI Operator.
- Do not rename OpenShift AI system namespaces; official docs warn that
  namespaces created by OpenShift AI typically include `openshift` or `redhat`
  and are required for the product to function.
- The workbench namespace cannot be changed after the OpenShift AI Operator has
  been installed.

## DataScienceCluster

- Installing OpenShift AI components by CLI or console requires creating and
  configuring a `DataScienceCluster` object.
- Official examples use:

  ```yaml
  apiVersion: datasciencecluster.opendatahub.io/v2
  kind: DataScienceCluster
  metadata:
    name: default-dsc
  ```

- Component installation intent is expressed under `spec.components`.
- `managementState: Managed` means the Operator actively manages, installs,
  and keeps the component active, upgrading it only when safe.
- `managementState: Removed` means the Operator actively manages the component
  but does not install it; if already installed, the Operator tries to remove
  it.
- If a component appears as `component-name: {}` in `spec.components`, the
  component is not installed.

## DSCInitialization

- DSCI is used for shared platform initialization and settings that are not
  per-component DSC installation state.
- The observability chapter configures the observability stack in
  `DSCInitialization` under `spec.monitoring`.
- DSCI monitoring can enable Prometheus, Alertmanager, OpenTelemetry Collector,
  and Tempo-related configuration; use `rhoai-observability` for detailed
  monitoring behavior.

## Validation Signals

Readonly checks after the OpenShift safety guard passes:

```bash
oc get datasciencecluster -n redhat-ods-operator
oc get dscinitialization -n redhat-ods-operator
oc get pods -n redhat-ods-applications
oc get datasciencecluster default-dsc -n redhat-ods-operator -o yaml
```

Expected signals:

- `DataScienceCluster` status reaches `Phase: Ready`.
- `status.installedComponents` marks installed components as `true`.
- There is at least one running pod for each installed component in the
  applications namespace.
