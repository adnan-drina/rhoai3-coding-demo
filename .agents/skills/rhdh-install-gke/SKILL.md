---
name: rhdh-install-gke
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when installing Red Hat Developer Hub on Google Kubernetes Engine (GKE):
  Operator-based installation via OLM, Helm chart deployment, pull secret
  provisioning, custom configuration (app-config, dynamic plugins, RBAC),
  Backstage CR authoring, Ingress exposure with GCE ingress class,
  ManagedCertificate, FrontendConfig HTTPS redirect, static IP reservation,
  and GKE-specific considerations (gcloud CLI, Autopilot vs Standard). Do NOT
  use for OpenShift Dedicated on Google Cloud (use rhdh-install-osd-gcp) or
  RHDH configuration beyond initial deployment.
---

# RHDH Install GKE

Use this skill to ground Red Hat Developer Hub 1.10 installation on Google
Kubernetes Engine (GKE) in official Red Hat documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers two installation
methods (Operator and Helm) and GKE-specific platform considerations.

## Installation Methods

### Operator-Based (OLM)

On GKE the OLM framework and Red Hat Container Registry are not built-in:

1. Connect to the GKE cluster:
   `gcloud container clusters get-credentials <name> --location=<location>`
2. Create the `rhdh-operator` namespace.
3. Create a pull secret for `registry.redhat.io` in that namespace.
4. Create a `CatalogSource` pointing to
   `registry.redhat.io/redhat/redhat-operator-index:v4.21`.
5. Create an `OperatorGroup` and `Subscription` (channel: `fast`,
   startingCSV: `rhdh-operator.v1.10.1`).
6. Patch the Operator deployment to include the pull secret.
7. Provision custom configuration (app-config ConfigMap, secrets, dynamic
   plugins ConfigMap).
8. Create a pull secret in the RHDH instance namespace and patch the default
   ServiceAccount.
9. Author a `Backstage` CR (`apiVersion: rhdh.redhat.com/v1alpha5`).
10. Create a `ManagedCertificate`, `FrontendConfig` (HTTPS redirect), and
    Kubernetes Ingress with `ingressClassName: gce`.

### Helm Chart

1. Add the Helm repo: `helm repo add openshift-helm-charts https://charts.openshift.io/`
2. Create a pull secret for `registry.redhat.io`.
3. Create a `ManagedCertificate` and `FrontendConfig`.
4. Author `values.yaml` with GKE-specific settings (gce ingress class, static
   IP, managed certificate, frontend config, fsGroup, NodePort, pull secrets).
5. Install:
   `helm -n <ns> install -f values.yaml <name> openshift-helm-charts/redhat-developer-hub --version 1.10.1`

## GKE-Specific Considerations

- **Ingress**: Use GCE ingress class (`ingressClassName: gce`). Requires a
  reserved static external Premium IPv4 Global IP address.
- **TLS**: Use a Google-managed certificate (`ManagedCertificate` CR,
  `apiVersion: networking.gke.io/v1`). Provisioning can take a couple hours.
- **HTTPS redirect**: Use a `FrontendConfig` CR
  (`apiVersion: networking.gke.io/v1beta1`) with `redirectToHttps.enabled: true`.
- **DNS**: Create an `A` record pointing to the reserved IP. Propagation can
  take up to one hour.
- **Pull secrets**: Not managed globally; must be provisioned in both the
  operator and instance namespaces.
- **fsGroup**: Set `podSecurityContext.fsGroup` to avoid permission errors.
- **Service type**: Use `NodePort` for GCE ingress.
- **Cluster types**: Supports both GKE Autopilot and GKE Standard clusters.

## Key Resources

| Resource | apiVersion | Purpose |
|----------|-----------|---------|
| Backstage CR | `rhdh.redhat.com/v1alpha5` | RHDH instance lifecycle |
| CatalogSource | `operators.coreos.com/v1alpha1` | Red Hat operator catalog |
| Subscription | `operators.coreos.com/v1alpha1` | Operator install |
| ManagedCertificate | `networking.gke.io/v1` | Google-managed TLS cert |
| FrontendConfig | `networking.gke.io/v1beta1` | HTTPS redirect policy |
| Ingress | `networking.k8s.io/v1` | External access via GCE |

## Verification

```shell
kubectl get deployment -n rhdh-operator
kubectl get deploy <name>-developer-hub -n <namespace>
kubectl get service -n <namespace>
kubectl get ingress -n <namespace>
```

## Workflow

1. Confirm the RHDH version baseline.
2. Read `references/official-doc-extraction.md`.
3. Choose Operator or Helm based on requirements.
4. Follow the platform-specific steps for GKE.
5. Wait for ManagedCertificate provisioning (can take hours).
6. Verify with the commands above.

## Related Skills

- Use `rhdh-install-aks` for AKS installation.
- Use `rhdh-install-eks` for EKS installation.
- Use `rhdh-install-osd-gcp` for OpenShift Dedicated on Google Cloud.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
