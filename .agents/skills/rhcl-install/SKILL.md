---
name: rhcl-install
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhcl"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "OpenShift Platform"
description: >
  Install Red Hat Connectivity Link 1.3 on single or multiple OpenShift
  Container Platform clusters, including the RHCL Operator, Kuadrant CR,
  Istio/Envoy gateway controller configuration, DNS provider credentials, Redis
  storage for rate limiting, and the console dynamic plugin. Use when deploying
  Connectivity Link for the first time or adding it to additional clusters. Do
  NOT use for policy configuration (use rhcl-configure); do NOT use for MCP
  gateway installation (use rhcl-install-mcp).
---

# Red Hat Connectivity Link 1.3 — Installation

## When to use

- Installing RHCL Operator via OLM (web console or CLI)
- Creating the Kuadrant CR to activate Connectivity Link
- Configuring Istio as an alternative gateway controller
- Setting up DNS provider credentials (AWS, GCP, Azure)
- Configuring Redis storage for rate-limit counters
- Enabling the Connectivity Link console dynamic plugin
- Setting up CoreDNS for on-premise DNS

## Key facts

- Operator: `rhcl-operator`, channel: `stable`, source: `redhat-operators`
- Demo pins: `rhcl-operator.v1.3.4`
- Namespace: `kuadrant-system` (default)
- Kuadrant CR: `apiVersion: kuadrant.io/v1beta1`, kind: `Kuadrant`
- Default gateway controller: OpenShift Cluster Ingress Operator
- Alternative: Istio (via `ISTIO_GATEWAY_CONTROLLER_NAMES` env on Subscription)
- Supported OCP: 4.19, 4.20, 4.21
- Required companion: cert-manager Operator for Red Hat OpenShift 1.18
- Optional: OpenShift Service Mesh 3.2 (auto-detected if present)

## Supported configurations

| Component | RHCL 1.3 version |
|-----------|------------------|
| OCP | 4.19, 4.20, 4.21 |
| OpenShift Service Mesh | 3.2 |
| cert-manager Operator | 1.18 |
| Red Hat build of Keycloak | 26.4 |
| Redis datastores | latest (Redis Enterprise, ElastiCache, Dragonfly) |

## Installation — CLI (OCP Ingress controller)

```yaml
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
```

## Installation — CLI (Istio gateway controller)

Add `config.env` to Subscription spec:

```yaml
spec:
  config:
    env:
    - name: ISTIO_GATEWAY_CONTROLLER_NAMES
      value: istio.io/gateway-controller
```

## Kuadrant CR

```yaml
apiVersion: kuadrant.io/v1beta1
kind: Kuadrant
metadata:
  name: kuadrant
  namespace: kuadrant-system
```

## Validation

```bash
oc wait kuadrant/kuadrant --for="condition=Ready=true" \
  -n kuadrant-system --timeout=300s
```

Component operators installed:
- Authorino Operator (auth)
- DNS Operator (north-south traffic)
- Limitador Operator (rate limiting)

## DNS provider secrets

Secrets must reside in the same namespace as the Gateway.

| Provider | Secret type |
|----------|-------------|
| AWS | `kuadrant.io/aws` |
| GCP | `kuadrant.io/gcp` |
| Azure | `kuadrant.io/azure` |
| CoreDNS | `kuadrant.io/coredns` |

## Redis for rate limiting

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

## Console dynamic plugin

Enable `kuadrant-console-plugin` via Administrator > Home > Overview >
Dynamic Plugins > kuadrant-console-plugin > Enable.

## References

- `references/source-capture.md` — source provenance
- `references/official-doc-extraction.md` — full extraction
- Official: https://docs.redhat.com/en/documentation/red_hat_connectivity_link/1.3/html-single/installing_connectivity_link/index
