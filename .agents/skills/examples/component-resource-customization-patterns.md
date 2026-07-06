# Component Resource Customization Patterns

These examples are review patterns for Red Hat OpenShift AI component
Deployments. Follow the OpenShift safety guard before running live commands.

## Discover The Target Deployment

```bash
oc get deployment -n redhat-ods-applications
oc get deployment rhods-dashboard -n redhat-ods-applications -o yaml
```

Record the current resources before changing them:

```bash
oc get deployment rhods-dashboard -n redhat-ods-applications \
  -o jsonpath='{.spec.template.spec.containers[*].resources}'
```

## Resource Block Shape

The official chapter changes
`.spec.template.spec.containers.resources` on the component Deployment.

```yaml
spec:
  template:
    spec:
      containers:
        - name: <verified-container-name>
          resources:
            limits:
              cpu: "2"
              memory: 500Mi
            requests:
              cpu: "1"
              memory: 1Gi
```

Verify the actual container name before patching. Do not apply this as a full
Deployment replacement unless full ownership of the Operator-created Deployment
has been explicitly approved.

## Disable Customization And Restore Defaults

Adding this annotation disables customization and lets the Operator restore
defaults:

```yaml
metadata:
  annotations:
    opendatahub.io/managed: true
```

Use only when restoring Operator defaults is the intended outcome.

## Re-Enable Customization

Do not remove `opendatahub.io/managed` manually and do not set it to `false`.
The official workflow is to delete the Deployment and let the controller
redeploy it with default settings.

Review checklist before live use:

```text
1. Confirm the user explicitly approved deleting the Deployment.
2. Confirm current OpenShift context and expected cluster.
3. Record current Deployment YAML.
4. Delete only the intended Deployment.
5. Verify the controller pod redeploys.
6. Re-apply resource customization only after the annotation is absent.
```

## Common Deployment Names

```text
kserve-controller-manager
odh-model-controller
kuberay-operator
kueue-controller-manager
notebook-controller-deployment
odh-notebook-controller-manager
rhods-dashboard
modelmesh-controller
model-registry-operator-controller-manager
data-science-pipelines-operator-controller-manager
kubeflow-training-operator
```

Check the active installation before assuming a component is present.
