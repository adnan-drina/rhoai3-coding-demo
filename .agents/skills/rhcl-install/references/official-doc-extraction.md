# Official Doc Extraction — rhcl-install

Source: Red Hat Connectivity Link 1.3 — Installing Connectivity Link

## Prerequisites

- Red Hat account with RHCL + OCP subscriptions
- OCP 4.19+ (4.19, 4.20, 4.21 supported)
- cert-manager Operator for Red Hat OpenShift 1.18
- cluster-admin privileges
- OpenShift CLI (`oc`)

### Important notes

- OCP 4.19+: GatewayClass `openshift-default` with controllerName
  `openshift.io/gateway-controller/v1` must exist
- OCP 4.18 or older: requires OpenShift Service Mesh as Gateway API provider
- OpenShift Service Mesh 3.2 is auto-detected; no separate install required
- `kuadrant.io/*` labels must not be removed from cluster resources

## Installation via CLI — OCP Ingress controller (default)

```bash
oc create ns kuadrant-system

oc apply -f - <<EOF
apiVersion: operators.coreos.com/v1alpha1
kind: Subscription
metadata:
  name: rhcl-operator
  namespace: kuadrant-system
spec:
  channel: stable
  installPlanApproval: Automatic
  name: rhcl-operator
  source: redhat-operators
  sourceNamespace: openshift-marketplace
---
kind: OperatorGroup
apiVersion: operators.coreos.com/v1
metadata:
  name: kuadrant
  namespace: kuadrant-system
spec:
  upgradeStrategy: Default
EOF
```

### Verify operator install

```bash
oc wait --for=jsonpath={.status.installPlanRef.name} subscription rhcl-operator --timeout=10s
ip=$(oc get subscription rhcl-operator -o=jsonpath={.status.installPlanRef.name})
oc wait --for=condition=Installed installplan ${ip} --timeout=60s
```

### Create Kuadrant CR

```bash
oc apply -f - <<EOF
apiVersion: kuadrant.io/v1beta1
kind: Kuadrant
metadata:
  name: kuadrant
  namespace: kuadrant-system
EOF
```

### Verify Kuadrant ready

```bash
oc wait kuadrant/kuadrant --for="condition=Ready=true" -n kuadrant-system --timeout=300s
```

## Installation via CLI — Istio gateway controller

Same as above but add env to Subscription spec:

```yaml
spec:
  config:
    env:
    - name: ISTIO_GATEWAY_CONTROLLER_NAMES
      value: istio.io/gateway-controller
```

Requires OpenShift Service Mesh pre-installed.

## Component operators installed

| Operator | Function |
|----------|----------|
| Authorino Operator | Authentication and authorization for gateways |
| DNS Operator | North-south traffic balancing to gateways |
| Limitador Operator | Rate limiting for gateways |

## DNS provider credential secrets

Must reside in the same namespace as the Gateway.

### AWS

```bash
oc create secret generic aws-credentials \
  --namespace=api-gateway \
  --type=kuadrant.io/aws \
  --from-literal=AWS_ACCESS_KEY_ID=$AWS_ACCESS_KEY_ID \
  --from-literal=AWS_SECRET_ACCESS_KEY=$AWS_SECRET_ACCESS_KEY \
  --from-literal=AWS_REGION=$AWS_REGION
```

### Google Cloud

```bash
oc create secret generic test-gcp-credentials \
  --namespace=api-gateway \
  --type=kuadrant.io/gcp \
  --from-literal=PROJECT_ID=$PROJECT_ID \
  --from-file=GOOGLE=$GOOGLE
```

### Azure

```bash
oc create secret generic test-azure-credentials \
  --namespace=api-gateway \
  --type=kuadrant.io/azure \
  --from-file=azure.json=/local/path/to/azure.json
```

## Redis for rate limiting (multicluster)

```bash
oc -n kuadrant-system create secret generic redis-config \
  --from-literal=URL=$REDIS_URL

oc patch limitador limitador --type=merge -n kuadrant-system -p '
spec:
  storage:
    redis:
      configSecretRef:
        name: redis-config
'
```

URI schemes: `rediss://` (secure), `redis://` (standard)

## Console dynamic plugin

1. Administrator > Home > Overview > Dynamic Plugins
2. Find `kuadrant-console-plugin` > Enable > Save
3. Wait for status: Loaded
4. New menu item: Connectivity Link in navigation sidebar

## CoreDNS on-premise DNS

### Key resources

- CoreDNS manifests: extracted from `registry.redhat.io/rhcl-1/dns-operator-bundle:rhcl-1.3.0`
- Provider secret type: `kuadrant.io/coredns`
- Namespace: `kuadrant-coredns`
- Zone configured via ConfigMap with `kuadrant` plugin

### Single cluster setup

```bash
podman create --name bundle registry.redhat.io/rhcl-1/dns-operator-bundle:rhcl-1.3.0
podman cp bundle:/coredns/manifests.yaml ./coredns-manifests.yaml
podman rm bundle
oc apply -f ./coredns-manifests.yaml

oc create secret generic coredns-credentials \
  --namespace=kuadrant-system \
  --type=kuadrant.io/coredns \
  --from-literal=ZONES="${KUADRANT_SUBDOMAIN}.${ONPREM_DOMAIN}"
```

### Validation

```bash
oc get dnsrecord <name> -n <namespace> -o jsonpath='{.status.conditions[?(@.type=="Ready")]}'
```

## Supported configurations matrix

| RHCL | OCP | Service Mesh | cert-manager | Keycloak |
|------|-----|--------------|--------------|----------|
| 1.3 | 4.19, 4.20, 4.21 | 3.2 | 1.18 | 26.4 |
| 1.2 | 4.18, 4.19, 4.20 | 3.1 | 1.17 | 26.4 |
| 1.1 | 4.17, 4.18, 4.19 | 3.0 | 1.15 | 26.2 |

## Cloud DNS providers supported

- Amazon Route 53
- Google Cloud Platform DNS
- Microsoft Azure DNS

## On-premise DNS

- CoreDNS (single cluster and multicluster)
