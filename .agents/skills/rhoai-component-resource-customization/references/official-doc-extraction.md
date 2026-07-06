# Official Doc Extraction

This extraction is derived from the official RHOAI 3.4 chapter captured in
`source-capture.md`.

## Resource Customization Model

OpenShift AI allows cluster administrators to customize deployment resources
related to the Red Hat OpenShift AI Operator, including CPU and memory requests
and limits.

For customizations to persist without being overwritten by the Operator, the
component Deployment YAML must not include:

```yaml
opendatahub.io/managed: true
```

The annotation is absent by default.

## Documented Deployment Names

The official chapter lists component Deployments in the
`redhat-ods-applications` namespace.

| Component | Deployment name |
|-----------|-----------------|
| KServe | `kserve-controller-manager` |
| KServe | `odh-model-controller` |
| Ray | `kuberay-operator` |
| Kueue | `kueue-controller-manager` |
| Workbenches | `notebook-controller-deployment` |
| Workbenches | `odh-notebook-controller-manager` |
| Dashboard | `rhods-dashboard` |
| Model serving | `modelmesh-controller` |
| Model serving | `odh-model-controller` |
| Model registry | `model-registry-operator-controller-manager` |
| AI pipelines | `data-science-pipelines-operator-controller-manager` |
| Training Operator | `kubeflow-training-operator` |

The official table can mark some components as Technology Preview. Preserve the
support boundary when documenting or changing those components.

## Customizing Component Resources

Prerequisite:

- cluster administrator privileges for the OpenShift cluster

Official console workflow:

1. Log in to the OpenShift console as cluster administrator.
2. Open Administrator perspective -> Workloads -> Deployments.
3. Select the `redhat-ods-applications` project.
4. Open the target component Deployment.
5. Open the YAML tab.
6. Find `.spec.template.spec.containers.resources`.
7. Update the desired resource value, such as CPU or memory requests/limits.
8. Save and reload.

Example resource shape from the chapter:

```yaml
containers:
  - resources:
      limits:
        cpu: "2"
        memory: 500Mi
      requests:
        cpu: "1"
        memory: 1Gi
```

Verification:

- log in to OpenShift AI and confirm the resource changes apply

## Disabling Customization

To disable customization of component Deployment resources and restore default
values, add this annotation to the component Deployment YAML:

```yaml
metadata:
  annotations:
    opendatahub.io/managed: true
```

Prerequisite:

- cluster administrator privileges for the OpenShift cluster

Verification:

- the annotation is visible in the component Deployment YAML

Important behavior:

- after manually adding `opendatahub.io/managed: true`, do not manually remove
  it or set it to `false`
- doing so can cause unexpected cluster issues
- use the re-enable workflow instead

## Re-Enabling Customization

To re-enable customization after disabling it:

1. Open the component Deployment in `redhat-ods-applications`.
2. Delete the Deployment.
3. Wait for the controller pod for the Deployment to automatically redeploy
   with default settings.

Verification:

- the controller pod redeploys with default settings

Treat this workflow as disruptive. It deletes an Operator-related Deployment so
it requires explicit approval in this repo before live use.

## Unresolved Items

This chapter does not define:

- exact resource recommendations for each component
- full list of every container name in each Deployment
- GitOps-native patching mechanism
- expected rollout timing or readiness probes for every component
- when to tune component Deployments versus user workload resources

Use active Deployment inspection, component-specific docs, and repo operations
policy before implementing those areas.
