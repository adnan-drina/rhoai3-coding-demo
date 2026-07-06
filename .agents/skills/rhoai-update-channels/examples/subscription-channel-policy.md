# Subscription Channel Policy Example

This example shows where channel policy belongs in an Operator Subscription.
Do not copy it directly into GitOps without replacing placeholders from the
official install chapter or OLM catalog checks.

## Feature-Forward Demo Preference

```yaml
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: <rhoai-operator-subscription>
  namespace: <rhoai-operator-namespace>
spec:
  channel: fast-3.x
  installPlanApproval: Automatic
  name: <verified-rhoai-operator-package>
  source: <verified-catalog-source>
  sourceNamespace: openshift-marketplace
```

Review notes required before committing:

- `fast-3.x` was verified in the active OLM catalog.
- Automatic approval is intentional because the demo prioritizes latest product
  features.
- Any Technology Preview or Developer Preview components enabled by later
  steps are documented separately.

## Fallback If Fast Is Not Available

If the catalog does not expose `fast-3.x`, do not invent the channel. Choose the
latest supported documented channel from the active catalog, for example:

```yaml
spec:
  channel: stable-3.x
  installPlanApproval: Automatic
```

Record why the fallback was selected in the README or operations notes.
