---
name: rhdh-install-eks
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when installing Red Hat Developer Hub on Amazon Elastic Kubernetes
  Service (EKS): Operator-based installation via OLM, Helm chart deployment,
  pull secret provisioning, custom configuration (app-config, dynamic plugins,
  RBAC), Backstage CR authoring, Ingress exposure with AWS Application Load
  Balancer (ALB), certificate ARN, and EKS-specific considerations (EBS
  storage, NodePort service type). Do NOT use for OpenShift-based RHDH
  installation or RHDH configuration beyond initial deployment.
---

# RHDH Install EKS

Use this skill to ground Red Hat Developer Hub 1.10 installation on Amazon
Elastic Kubernetes Service (EKS) in official Red Hat documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers two installation
methods (Operator and Helm) and EKS-specific platform considerations.

## Installation Methods

### Operator-Based (OLM)

On EKS the OLM framework and Red Hat Container Registry are not built-in:

1. Create the `rhdh-operator` namespace.
2. Create a pull secret for `registry.redhat.io` in that namespace.
3. Create a `CatalogSource` pointing to
   `registry.redhat.io/redhat/redhat-operator-index:v4.21`.
4. Create an `OperatorGroup` and `Subscription` (channel: `fast`,
   startingCSV: `rhdh-operator.v1.10.1`).
5. Patch the Operator deployment to include the pull secret.
6. Provision custom configuration (app-config ConfigMap, secrets, dynamic
   plugins ConfigMap).
7. Create a pull secret in the RHDH instance namespace and patch the default
   ServiceAccount.
8. Author a `Backstage` CR (`apiVersion: rhdh.redhat.com/v1alpha5`).
9. Create a Kubernetes Ingress with `ingressClassName: alb` and ALB
   annotations (certificate ARN, SSL redirect, scheme).

### Helm Chart

1. Add the Helm repo: `helm repo add openshift-helm-charts https://charts.openshift.io/`
2. Create a pull secret for `registry.redhat.io`.
3. Author `values.yaml` with EKS-specific settings (ALB ingress annotations,
   fsGroup, NodePort service, pull secrets, route disabled).
4. Install:
   `helm install rhdh openshift-helm-charts/redhat-developer-hub [--version 1.10.1] --values values.yaml`

## EKS-Specific Considerations

- **Ingress**: Use AWS Application Load Balancer (ALB) with
  `ingressClassName: alb`. Requires ALB add-on installed on the cluster.
- **Certificate**: Provide a certificate ARN from AWS Certificate Manager via
  `alb.ingress.kubernetes.io/certificate-arn`.
- **Service type**: Use `NodePort` for ALB to route to the Service.
- **Pull secrets**: Not managed globally; must be provisioned in both the
  operator and instance namespaces.
- **fsGroup**: Set `podSecurityContext.fsGroup` to avoid permission errors.
- **Storage**: Requires a working default storage class such as the EBS
  storage add-on.
- **DNS**: Configure domain via Route 53 or external DNS with
  `external-dns.alpha.kubernetes.io/hostname` annotation.

## Key Resources

| Resource | apiVersion | Purpose |
|----------|-----------|---------|
| Backstage CR | `rhdh.redhat.com/v1alpha5` | RHDH instance lifecycle |
| CatalogSource | `operators.coreos.com/v1alpha1` | Red Hat operator catalog |
| Subscription | `operators.coreos.com/v1alpha1` | Operator install |
| Ingress | `networking.k8s.io/v1` | External access via ALB |

## Custom Configuration

Custom configuration uses two ConfigMaps and a Secret:

- `app-config-rhdh` ConfigMap: contains `app-config.yaml` with `baseUrl`
  settings for `app`, `backend`, and `backend.cors.origin`.
- `dynamic-plugins-rhdh` ConfigMap: contains `dynamic-plugins.yaml`.
- `my-rhdh-secrets` Secret: contains `BACKEND_SECRET` and other auth secrets.

## Verification

```shell
kubectl get deployment -n rhdh-operator
kubectl get deploy <name> -n <namespace>
```

## Workflow

1. Confirm the RHDH version baseline.
2. Read `references/official-doc-extraction.md`.
3. Choose Operator or Helm based on requirements.
4. Follow the platform-specific steps for EKS.
5. Verify with the commands above.

## Related Skills

- Use `rhdh-install-aks` for AKS installation.
- Use `rhdh-install-gke` for GKE installation.
- Use `rhdh-install-osd-gcp` for OpenShift Dedicated on Google Cloud.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
