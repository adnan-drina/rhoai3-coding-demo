# Official Doc Extraction

Use this extraction to keep ingress, routes, and Gateway API content grounded
in official OCP sources. Verify exact fields with `oc explain` before writing
manifests.

## Routes And Ingress

OpenShift exposes application traffic through platform ingress components and
OpenShift `Route` resources. Route configuration can include TLS termination,
hostnames, wildcard behavior, and route admission behavior. The Ingress
Operator manages the cluster ingress controller lifecycle and exposes status,
logs, and configuration points for cluster administrators.

For demo implementation:

- Prefer existing cluster ingress unless a specific capability requires custom
  ingress.
- Treat router certificates, wildcard route admission, apps domain changes, and
  IngressController scaling as cluster-level operations.
- Keep Route authoring close to the product component that requires the route.

## Gateway API

OCP 4.20 includes Gateway API support through the Ingress Operator. The
OpenShift implementation uses `gateway.networking.k8s.io/v1` for key resources
such as `Gateway`, `GatewayClass`, `HTTPRoute`, and `GRPCRoute`, with
`ReferenceGrant` for cross-namespace references.

Important implementation points:

- Gateway API does not support user-defined networks.
- Gateway API CRDs are maintained by the Ingress Operator.
- Third-party implementations must conform to the OpenShift-supported Gateway
  API version.
- The OpenShift Gateway API implementation relies on the Cluster Ingress
  Operator installing required OpenShift Service Mesh 3.x components in
  `openshift-ingress`.
- A conflicting OpenShift Service Mesh 2.x subscription can prevent Gateway
  API provisioning and degrade the ingress ClusterOperator.
- The `GatewayClass.spec.controllerName` for the OpenShift implementation must
  be `openshift.io/gateway-controller/v1`.

Do not enable Gateway API by creating a GatewayClass unless the implementation
needs it and the environment has been checked for Service Mesh conflicts.

## Architecture Handoff

READMEs should describe external access at the capability level: which
components become externally reachable, which platform primitive enables that
access, and which architecture delta is introduced. Operational commands,
certificate rotation, and live troubleshooting belong in `docs/OPERATIONS.md`
or `docs/TROUBLESHOOTING.md`.

## Validation Signals

Healthy external access work should verify:

- ingress ClusterOperator health
- IngressController availability
- route hostnames and TLS termination mode
- router service and endpoints
- Gateway API CRDs and GatewayClass state, if used
- HTTPRoute and backend references, if used
- DNS and certificate ownership boundaries
