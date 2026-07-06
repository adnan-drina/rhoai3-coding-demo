# Validation Checklist

Use this checklist before accepting ingress, route, or Gateway API guidance.

## Source Validation

- The active OCP baseline is read from `docs/PLATFORM_BASELINE.md`.
- The source URL uses the pinned OCP documentation version.
- Route, Ingress, IngressController, Gateway, GatewayClass, HTTPRoute,
  GRPCRoute, and ReferenceGrant fields are verified from official docs or
  cluster schema.
- Gateway API guidance includes OCP 4.20 prerequisites and OSSM conflict
  checks when applicable.
- RHOAI-specific routing behavior is handed off to the relevant RHOAI skill.

## Manifest Review

- `route.openshift.io/v1` is used for OpenShift Routes.
- Gateway API manifests use the active cluster-supported API version.
- Gateway resources are placed in the namespace required by the selected
  topology and official docs.
- TLS certificate references are explicit and secrets are not committed.
- DNS, apps domain, and wildcard behavior are not assumed.

## Discovery Commands

Run only after the OpenShift safety guard confirms the target cluster:

```sh
oc get clusteroperator ingress -o yaml
oc get ingresscontroller -n openshift-ingress-operator
oc get ingress.config.openshift.io cluster -o yaml
oc get route -A
oc get services,endpoints -n openshift-ingress
oc get gatewayclass,gateway,httproute,grpcroute,referencegrant -A
```

For schema checks:

```sh
oc explain route.spec
oc explain ingresscontroller.operator.openshift.io.spec
oc explain gatewayclass.spec
oc explain gateway.spec
oc explain httproute.spec
```
