# Source Capture

## Official Source

| Field | Value |
|-------|-------|
| Product family | Red Hat OpenShift Container Platform |
| Baseline source | `docs/PLATFORM_BASELINE.md` |
| Documentation category | Networking, Ingress and load balancing, Networking Operators |
| Official guide | Networking |
| Source URL | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/networking/index |
| Ingress and load balancing | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/ingress_and_load_balancing/index |
| Routes chapter | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/ingress_and_load_balancing/routes |
| Ingress traffic chapter | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/ingress_and_load_balancing/configuring-ingress-cluster-traffic |
| Ingress Operator chapter | https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/networking_operators/configuring-ingress |
| Capture date | 2026-06-10 |

## Captured Sections

- Routes
- Configuring ingress cluster traffic
- Methods for communicating from outside the cluster
- DNS management policies
- Gateway API with OpenShift Container Platform networking
- Gateway API implementation and limitations
- Gateway API getting-started flow for the Ingress Operator
- Ingress Operator, IngressController parameters, status, logs, and
  configuration

## Source Boundaries

This skill covers OCP platform external access primitives. It does not define
RHOAI-specific route names, model-serving Gateway API topology, MaaS governance
policy, or workbench custom-image behavior.

Gateway API behavior must be verified against the active OCP version and live
cluster CRDs. Do not assume third-party Gateway implementations behave like the
OpenShift Ingress Operator implementation.
