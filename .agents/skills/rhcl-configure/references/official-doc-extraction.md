# Official Doc Extraction — rhcl-configure

Source: Red Hat Connectivity Link 1.3 — Deploying Red Hat Connectivity Link

## Overview

This document explains how to add policies to Connectivity Link to secure,
protect, and connect an application API exposed by a Gateway object.

## Environment setup

```bash
export KUADRANT_GATEWAY_NS=api-gateway
export KUADRANT_GATEWAY_NAME=ingress-gateway
export KUADRANT_DEVELOPER_NS=toystore
export KUADRANT_AWS_ACCESS_KEY_ID=xxxx
export KUADRANT_AWS_SECRET_ACCESS_KEY=xxxx
export KUADRANT_ZONE_ROOT_DOMAIN=example.com
export KUADRANT_CLUSTER_ISSUER_NAME=self-signed
```

## DNS provider secret

```bash
oc create ns ${KUADRANT_GATEWAY_NS}
oc -n ${KUADRANT_GATEWAY_NS} create secret generic aws-credentials \
  --type=kuadrant.io/aws \
  --from-literal=AWS_ACCESS_KEY_ID=$KUADRANT_AWS_ACCESS_KEY_ID \
  --from-literal=AWS_SECRET_ACCESS_KEY=$KUADRANT_AWS_SECRET_ACCESS_KEY
```

## Gateway object

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: Gateway
metadata:
  name: ${KUADRANT_GATEWAY_NAME}
  namespace: ${KUADRANT_GATEWAY_NS}
  labels:
    kuadrant.io/gateway: "true"
spec:
  gatewayClassName: openshift-default
  listeners:
  - allowedRoutes:
      namespaces:
        from: All
    hostname: "api.${KUADRANT_ZONE_ROOT_DOMAIN}"
    name: api
    port: 443
    protocol: HTTPS
    tls:
      certificateRefs:
      - group: ""
        kind: Secret
        name: api-${KUADRANT_GATEWAY_NAME}-tls
      mode: Terminate
```

### Multicluster note

For DNS-based traffic balancing across clusters, use a shared hostname via
HTTPS listener with a wildcard hostname based on the root domain.

### Verification

```bash
oc get gateway ${KUADRANT_GATEWAY_NAME} -n ${KUADRANT_GATEWAY_NS} \
  -o=jsonpath='{.status.conditions[?(@.type=="Accepted")].message}{"\n"}{.status.conditions[?(@.type=="Programmed")].message}'
```

## TLS certificate issuer (ClusterIssuer)

```yaml
apiVersion: cert-manager.io/v1
kind: ClusterIssuer
metadata:
  name: ${KUADRANT_CLUSTER_ISSUER_NAME}
spec:
  selfSigned: {}
```

Verification:
```bash
oc wait clusterissuer/${KUADRANT_CLUSTER_ISSUER_NAME} --for=condition=ready=true
```

## TLSPolicy

```yaml
apiVersion: kuadrant.io/v1
kind: TLSPolicy
metadata:
  name: ${KUADRANT_GATEWAY_NAME}-tls
  namespace: ${KUADRANT_GATEWAY_NS}
spec:
  targetRef:
    name: ${KUADRANT_GATEWAY_NAME}
    group: gateway.networking.k8s.io
    kind: Gateway
  issuerRef:
    group: cert-manager.io
    kind: ClusterIssuer
    name: ${KUADRANT_CLUSTER_ISSUER_NAME}
```

Verification:
```bash
oc get tlspolicy ${KUADRANT_GATEWAY_NAME}-tls -n ${KUADRANT_GATEWAY_NS} \
  -o=jsonpath='{.status.conditions[?(@.type=="Accepted")].message}{"\n"}{.status.conditions[?(@.type=="Enforced")].message}'
```

## DNSPolicy

```yaml
apiVersion: kuadrant.io/v1
kind: DNSPolicy
metadata:
  name: ${KUADRANT_GATEWAY_NAME}-dnspolicy
  namespace: ${KUADRANT_GATEWAY_NS}
spec:
  healthCheck:
    failureThreshold: 3
    interval: 1m
    path: /health
  loadBalancing:
    defaultGeo: true
    geo: GEO-NA
    weight: 120
  targetRef:
    name: ${KUADRANT_GATEWAY_NAME}
    group: gateway.networking.k8s.io
    kind: Gateway
  providerRefs:
  - name: aws-credentials
```

Verification:
```bash
oc get dnspolicy ${KUADRANT_GATEWAY_NAME}-dnspolicy -n ${KUADRANT_GATEWAY_NS} \
  -o=jsonpath='{.status.conditions[?(@.type=="SubResourcesHealthy")].message}'
```

## AuthPolicy — gateway deny-all

```yaml
apiVersion: kuadrant.io/v1
kind: AuthPolicy
metadata:
  name: ${KUADRANT_GATEWAY_NAME}-auth
  namespace: ${KUADRANT_GATEWAY_NS}
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: Gateway
    name: ${KUADRANT_GATEWAY_NAME}
  defaults:
    when:
    - predicate: "request.path != '/health'"
    rules:
      authorization:
        deny-all:
          opa:
            rego: "allow = false"
      response:
        unauthorized:
          headers:
            "content-type":
              value: application/json
          body:
            value: |
              {
                "error": "Forbidden",
                "message": "Access denied by default by the gateway operator. If you are the administrator of the service, create a specific auth policy for the route."
              }
```

Verification:
```bash
oc get authpolicy ${KUADRANT_GATEWAY_NAME}-auth -n ${KUADRANT_GATEWAY_NS} \
  -o=jsonpath='{.status.conditions[?(@.type=="Accepted")].message}{"\n"}{.status.conditions[?(@.type=="Enforced")].message}'
```

## RateLimitPolicy — gateway default

```yaml
apiVersion: kuadrant.io/v1
kind: RateLimitPolicy
metadata:
  name: ${KUADRANT_GATEWAY_NAME}-rlp
  namespace: ${KUADRANT_GATEWAY_NS}
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: Gateway
    name: ${KUADRANT_GATEWAY_NAME}
  defaults:
    limits:
      "low-limit":
        rates:
        - limit: 1
          window: 10s
```

Verification:
```bash
oc get ratelimitpolicy ${KUADRANT_GATEWAY_NAME}-rlp -n ${KUADRANT_GATEWAY_NS} \
  -o=jsonpath='{.status.conditions[?(@.type=="Accepted")].message}{"\n"}{.status.conditions[?(@.type=="Enforced")].message}'
```

## Rate-limit headers

```bash
oc patch limitador limitador -n kuadrant-system --type=merge \
  -p '{"spec": {"rateLimitHeaders": "DRAFT_VERSION_03"}}'
```

Headers returned: `x-ratelimit-limit`, `x-ratelimit-remaining`, `x-ratelimit-reset`

## TokenRateLimitPolicy (LLM APIs)

```yaml
apiVersion: kuadrant.io/v1alpha1
kind: TokenRateLimitPolicy
metadata:
  name: llm-protection
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: Gateway
    name: ai-gateway
  limits:
    free-users:
      rates:
      - limit: 10000
        window: 24h
      when:
      - predicate: request.path == "/v1/chat/completions"
      - predicate: |
          auth.identity.groups.split(",").exists(g, g == "free")
      counters:
      - expression: auth.identity.userid
    pro-users:
      rates:
      - limit: 100000
        window: 24h
      when:
      - predicate: request.path == "/v1/chat/completions"
      - predicate: |
          auth.identity.groups.split(",").exists(g, g == "pro")
      counters:
      - expression: auth.identity.userid
```

### How it works

1. Request matches rules and predicates
2. Gateway monitors the response
3. Extracts `usage.total_tokens` from JSON response body
4. Sends RateLimitRequest to Limitador with token count as `hits_addend`
5. Limitador returns OK or OVER_LIMIT

### Integrates with AuthPolicy

Uses `auth.identity.*` claims for user-specific limits.

## Override policies — per-route AuthPolicy

```yaml
apiVersion: kuadrant.io/v1
kind: AuthPolicy
metadata:
  name: toystore-auth
  namespace: ${KUADRANT_DEVELOPER_NS}
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: toystore
  defaults:
    when:
    - predicate: "request.path != '/health'"
    rules:
      authentication:
        "api-key-users":
          apiKey:
            selector:
              matchLabels:
                app: toystore
          credentials:
            authorizationHeader:
              prefix: APIKEY
      response:
        success:
          filters:
            "identity":
              json:
                properties:
                  "userid":
                    selector: auth.identity.metadata.annotations.secret\.kuadrant\.io/user-id
```

## Override policies — per-user RateLimitPolicy

```yaml
apiVersion: kuadrant.io/v1
kind: RateLimitPolicy
metadata:
  name: toystore-rlp
  namespace: ${KUADRANT_DEVELOPER_NS}
spec:
  targetRef:
    group: gateway.networking.k8s.io
    kind: HTTPRoute
    name: toystore
  limits:
    "general-user":
      rates:
      - limit: 5
        window: 10s
      counters:
      - expression: auth.identity.userid
      when:
      - predicate: "auth.identity.userid != 'bob'"
    "bob-limit":
      rates:
      - limit: 2
        window: 10s
      when:
      - predicate: "auth.identity.userid == 'bob'"
```

## HTTPRoute for applications

```yaml
apiVersion: gateway.networking.k8s.io/v1
kind: HTTPRoute
metadata:
  name: toystore
  namespace: ${KUADRANT_DEVELOPER_NS}
  labels:
    deployment: toystore
    service: toystore
spec:
  parentRefs:
  - name: ${KUADRANT_GATEWAY_NAME}
    namespace: ${KUADRANT_GATEWAY_NS}
  hostnames:
  - api.${KUADRANT_ZONE_ROOT_DOMAIN}
  rules:
  - matches:
    - method: GET
      path:
        type: PathPrefix
        value: /cars
    - method: GET
      path:
        type: PathPrefix
        value: /health
    backendRefs:
    - name: toystore
      port: 80
```

## API key secrets for authentication

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: bob-key
  namespace: ${KUADRANT_SYSTEM_NS}
  labels:
    authorino.kuadrant.io/managed-by: authorino
    app: toystore
  annotations:
    secret.kuadrant.io/user-id: bob
stringData:
  api_key: IAMBOB
type: Opaque
```

## Policy hierarchy

1. Gateway-level `defaults` apply to all routes unless overridden
2. Route-level policies override gateway defaults for that route
3. Multiple AuthPolicy and RateLimitPolicy can attach to Gateway + HTTPRoute
