# External Access Review Pattern

Use this pattern when reviewing planned external access changes:

1. Identify whether the component needs a Route, Kubernetes Ingress, or Gateway
   API resource.
2. Confirm the active ingress domain with
   `oc get ingress.config.openshift.io cluster -o yaml`.
3. Verify ingress ClusterOperator and IngressController health.
4. For Gateway API, check for existing OSSM v2 subscriptions before creating a
   GatewayClass.
5. Keep certificates and DNS ownership explicit.
6. Move operational recovery notes to `docs/TROUBLESHOOTING.md`.
