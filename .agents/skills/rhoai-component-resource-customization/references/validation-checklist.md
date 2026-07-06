# Validation Checklist

Use this checklist before approving OpenShift AI component Deployment resource
customizations.

## Source Review

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- Target Deployment is one of the documented OpenShift AI component
  Deployments or is verified from the active installation.
- The target namespace is `redhat-ods-applications`.
- CPU and memory settings are intentional and documented.
- Technology Preview support boundaries are preserved when applicable.
- The change is clearly distinguished from user workload sizing, quotas,
  autoscaling, hardware profiles, or Kueue queue design.

## Readonly Discovery

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc get deployment -n redhat-ods-applications
oc get deployment <deployment-name> -n redhat-ods-applications -o yaml
oc get pods -n redhat-ods-applications -l app=<label-if-known>
```

Check:

- target Deployment exists
- target container name is verified
- current `resources` block is recorded before changes
- `opendatahub.io/managed: true` is absent when customization should persist
- rollout status is healthy before changing resources

## Customization Review

Before changing resources:

- confirm cluster administrator privileges
- identify the exact Deployment and container to change
- set both requests and limits deliberately
- avoid reducing memory/CPU below observed operational needs
- plan rollback to the previous resource block
- record why the component needs tuning for the demo

Readonly verification after change:

```bash
oc rollout status deployment/<deployment-name> -n redhat-ods-applications
oc get deployment <deployment-name> -n redhat-ods-applications -o jsonpath='{.spec.template.spec.containers[*].resources}'
```

## Managed Annotation Review

To disable customization and restore defaults:

- add `opendatahub.io/managed: true` only when that is the explicit intent
- verify the annotation appears in Deployment YAML
- confirm the Operator restores default resource values

To re-enable customization:

- do not remove the annotation manually
- do not set the annotation to `false`
- delete the Deployment only with explicit approval
- verify the controller pod redeploys with default settings

## GitOps Review

- Avoid making ArgoCD own the full Operator-created Deployment unless that
  design is explicitly approved.
- Prefer a scoped patch or documented post-install operation when automation is
  needed.
- Preserve unrelated Deployment fields and annotations.
- Ensure patches target the correct active container name.
- Do not let ArgoCD repeatedly fight the OpenShift AI Operator reconciliation.

## Fail Conditions

- `opendatahub.io/managed: true` is added accidentally while expecting custom
  values to persist.
- The annotation is manually removed or set to `false`.
- A full Operator-created Deployment manifest is imported into GitOps without
  explicit ownership approval.
- Resource values are changed without recording the previous values and rollback
  path.
- A component is tuned to work around user workload sizing that should instead
  be handled by hardware profiles, model runtime resources, quotas, Kueue, or
  cluster capacity.
