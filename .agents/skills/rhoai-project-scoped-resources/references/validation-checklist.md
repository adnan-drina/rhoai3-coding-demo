# Validation Checklist

Use this checklist before approving project-scoped OpenShift AI resources.

## Source Review

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- Resource type and display-name fields match the official chapter.
- Fields beyond the chapter are sourced from component-specific docs or active
  schema verification.
- Resource visibility is described as project-scoped, not global.
- The target user or group has access to the target project.
- Global versus project-scoped placement is intentional and documented.

## Dashboard Configuration Review

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc explain odhdashboardconfig.spec.dashboardConfig
oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o yaml
```

Check:

- `disableProjectScoped` is set to `false` when project-scoped resources must
  be available.
- Dashboard configuration changes preserve unrelated settings.
- If the field is absent, the active default is verified before assuming
  project-scoped resources are enabled.

## Resource Review

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get imagestream -n <target-project>
oc get hardwareprofile -n <target-project>
oc get template -n <target-project>
oc get template -n <target-project> -o yaml | rg 'kind: ServingRuntime'
```

Check:

- `metadata.namespace` is the target project.
- `metadata.name` is unique within the project.
- Workbench image display name uses
  `metadata.annotations.opendatahub.io/notebook-image-name`.
- Hardware profile display name uses `spec.displayName`.
- Serving runtime template display name uses
  `objects.metadata.annotations.openshift.io/display-name`.
- Resource content came from a trusted source: existing verified resource,
  official docs, or reviewed GitOps.
- Project-scoped resource does not accidentally duplicate a global resource
  with a confusing name.

## Component-Specific Review

For workbench images:

- apply `rhoai-workbenches-custom-images`
- verify dashboard discovery labels, annotations, image reference, and registry
  access

For hardware profiles:

- apply `rhoai-nvidia-gpu-accelerators`
- verify accelerator identifier and project hardware availability

For KServe serving runtime templates:

- apply `rhoai-model-serving-platform`
- verify the embedded `ServingRuntime` fields from official docs or active CRD
  schema before use

## GitOps Review

- Project-scoped resources are managed in the same stage as the target project
  or in a prerequisite stage.
- ArgoCD sync ordering creates the target project before project-scoped
  resources.
- README or operations notes explain why the resource is project-scoped.
- Resource names avoid collision with global names unless that is intentional
  and documented.
- Project-scoped resources do not claim availability in projects where they are
  not deployed.

## Fail Conditions

- `disableProjectScoped` is not enabled for project-scoped resource behavior.
- A resource is created in `redhat-ods-applications` when it was intended to be
  visible only in one target project.
- A resource is created in a target project but README or demo text describes
  it as global.
- A `Template` is treated as a serving runtime without confirming it contains a
  `ServingRuntime` object.
- Unknown `HardwareProfile`, `ImageStream`, `Template`, or `ServingRuntime`
  fields are added without official docs or schema verification.
