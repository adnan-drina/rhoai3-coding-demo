# Model Registry Patterns

## Component Enablement Snippet

Use this as the documented shape for enabling model registry support in the
DataScienceCluster. Confirm the surrounding resource and fields against the
active baseline before turning it into GitOps content.

```yaml
spec:
  components:
    modelregistry:
      managementState: Managed
      registriesNamespace: rhoai-model-registries
```

## Dashboard Paths

```text
OpenShift AI dashboard -> Settings -> Model resources and operations -> Model registry settings
OpenShift AI dashboard -> Settings -> Model resources and operations -> AI registry settings
```

Use Model registry settings for create/edit workflows. Use AI registry settings
for permissions and deletion workflows.

## External Database Host Examples

Same namespace as the registry service:

```text
model-registry-db
```

Different namespace:

```text
model-registry-db.data-services.svc.cluster.local
```

## Permission Review Worksheet

```text
Registry: acme-model-registry
Generated group: acme-model-registry-users
Generated role: registry-users-acme-model-registry
Access model:
- group: acme-data-scientists
- project service accounts: acme-model-serving
Avoided:
- system:authenticated
Verification:
- users/groups visible on the Permissions tab
- project visible on the Projects tab
```

## Read-Only Verification Commands

Run live commands only after the repo OpenShift safety guard is satisfied.

```bash
oc get namespace rhoai-model-registries
oc get deployment model-registry-operator-controller-manager -n redhat-ods-applications
oc get pods -n redhat-ods-applications | rg 'model-registry-operator-controller-manager'
oc api-resources | rg -i 'model.*registr'
```

For direct custom resources, verify the exact resource name and schema before
writing manifests:

```bash
oc api-resources --api-group=modelregistry.opendatahub.io
oc explain <resource-name> --api-version=modelregistry.opendatahub.io/v1beta1 --recursive
```
