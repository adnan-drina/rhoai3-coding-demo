# Official Doc Extraction

Use this extraction to keep RHCL installation content grounded in official
sources. Verify exact fields with `oc explain` before writing manifests.

## Operator Installation (CLI)

Create namespace, Subscription, and OperatorGroup:

```yaml
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: rhcl-operator
  namespace: <kuadrant_system>
spec:
  channel: stable
  installPlanApproval: Automatic
  name: rhcl-operator
  source: redhat-operators
  sourceNamespace: openshift-marketplace
---
apiVersion: operators.coreos.com/v1
kind: OperatorGroup
metadata:
  name: kuadrant
  namespace: <kuadrant_system>
spec:
  upgradeStrategy: Default
```

For disconnected environments, replace `spec.source` with the CatalogSource
created by `oc-mirror`.

## Verifying Installation

```bash
oc wait --for=jsonpath={.status.installPlanRef.name} subscription rhcl-operator --timeout=10s
ip=$(oc get subscription rhcl-operator -o=jsonpath={.status.installPlanRef.name})
oc wait --for=condition=Installed installplan ${ip} --timeout=60s
```

## Kuadrant CR

```yaml
apiVersion: kuadrant.io/v1beta1
kind: Kuadrant
metadata:
  name: kuadrant
  namespace: <kuadrant_system>
spec: {}
```

Verify readiness:

```bash
oc wait kuadrant/kuadrant --for="condition=Ready=true" -n <kuadrant_system> --timeout=300s
```

Expected pods after install:

- `authorino-operator-controller-manager`
- `dns-operator-controller-manager`
- `kuadrant-operator-controller-manager`
- `limitador-operator-controller-manager`

## Istio Gateway Controller Variant

When using OpenShift Service Mesh as the Gateway API provider, add an env var
to the Subscription:

```yaml
spec:
  config:
    env:
    - name: ISTIO_GATEWAY_CONTROLLER_NAMES
      value: istio.io/gateway-controller
```

No separate OpenShift Service Mesh install is required with RHCL 1.3+. If OSSM
is present, RHCL auto-detects it.

## Supported Configurations

| RHCL | OCP | Service Mesh | cert-manager |
|------|-----|-------------|-------------|
| 1.4 | 4.18–4.21 | 3.2 | 1.18 |
| 1.3 | 4.18–4.21 | 3.2 | 1.18 |

Supported cloud providers: AWS, GCP, Azure.
Supported DNS providers: Route 53, GCP DNS, Azure DNS.
Supported rate-limit stores: Redis Enterprise/Cloud, ElastiCache, Dragonfly.
Supported IAM: API keys, Red Hat build of Keycloak v26.4.

## OCP 4.19+ GatewayClass Requirement

When using Gateway API CRDs provided by OCP 4.19+, create a GatewayClass
named `openshift-default` with controllerName
`openshift.io/gateway-controller/v1`.

## DNS Provider Credentials

AWS example:

```bash
oc -n ${KUADRANT_GATEWAY_NS} create secret generic aws-credentials \
  --type=kuadrant.io/aws \
  --from-literal=AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  --from-literal=AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY
```

Google Cloud uses type `kuadrant.io/gcp` with a `GOOGLE` key containing
the service account JSON.

Azure uses type `kuadrant.io/azure` with keys for `AZURE_SUBSCRIPTION_ID`,
`AZURE_TENANT_ID`, `AZURE_CLIENT_ID`, `AZURE_CLIENT_SECRET`.

## Multicluster

For multicluster, repeat the full installation on each cluster. DNS-based
traffic balancing requires a shared root domain and DNSPolicy with geo
load-balancing configuration.

## Warning: RHCL 1.4.0 Deprecation

RHCL 1.4.0 is deprecated. Official guidance: new customers should not install
1.4.0; upgrade customers should pin to 1.3.z. The demo follows this guidance.
