---
name: rhdh-install-osd-gcp
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when installing Red Hat Developer Hub on OpenShift Dedicated on Google
  Cloud: Operator-based installation, Helm chart deployment, custom
  configuration (app-config, dynamic plugins, RBAC), Backstage CR authoring,
  and OSD-specific considerations (baseUrl requirement, clusterRouterBase).
  Do NOT use for vanilla GKE installation (use rhdh-install-gke), other
  platforms, or RHDH configuration beyond initial deployment.
---

# RHDH Install OSD on Google Cloud

Use this skill to ground Red Hat Developer Hub 1.10 installation on OpenShift
Dedicated on Google Cloud in official Red Hat documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority. This skill covers two installation
methods (Operator and Helm) for the OpenShift Dedicated on Google Cloud
platform.

## Installation Methods

### Operator-Based

On OpenShift Dedicated, the Operator and OLM framework are available natively:

1. Provision custom configuration:
   - Create a `app-config-rhdh` ConfigMap with `app-config.yaml` including
     `baseUrl` for `app`, `backend`, and `backend.cors.origin`.
   - Create a `my-rhdh-secrets` Secret with `BACKEND_SECRET`.
2. Author a `Backstage` CR or use the web console to create the instance.

### Helm Chart

1. Select Form view or YAML view in the Helm install wizard.
2. Configure `baseUrl` via `global.app.baseUrl`, `global.backend.baseUrl`,
   and `global.backend.cors.origin` in Helm values.
3. Alternatively, set `global.clusterRouterBase` to
   `apps.<clusterName>.com` and enable `global.auth.backend.enabled: true`.

## OSD-Specific Considerations

- **baseUrl**: Required for RHDH to function correctly. If not set, frontend
  and backend services cannot communicate properly.
- **Routes**: OpenShift Routes are available natively (no Ingress
  workaround needed).
- **Operator availability**: OLM and OperatorHub are built into OpenShift
  Dedicated, simplifying operator installation.
- **clusterRouterBase**: The Helm chart can use the OpenShift router hostname
  via `global.clusterRouterBase`.

## Key Resources

| Resource | apiVersion | Purpose |
|----------|-----------|---------|
| ConfigMap (`app-config-rhdh`) | `v1` | App configuration |
| Secret (`my-rhdh-secrets`) | `v1` | Backend auth secret |

## Custom Configuration

### app-config.yaml

```yaml
app:
  title: Red Hat Developer Hub
  baseUrl: https://<my_developer_hub_domain>
backend:
  auth:
    externalAccess:
        - type: legacy
          options:
            subject: legacy-default-config
            secret: "${BACKEND_SECRET}"
  baseUrl: https://<my_developer_hub_domain>
  cors:
    origin: https://<my_developer_hub_domain>
```

### Helm values (YAML view)

```yaml
global:
  auth:
    backend:
      enabled: true
  clusterRouterBase: apps.<clusterName>.com
```

### Helm values (Form view)

Navigate to Root Schema > global > Enable service authentication within
Backstage instance and paste the OpenShift router host.

## Verification

- Review the configuration, select deployment options, and click Create.
- Access Developer Hub via the URL in the OpenShift web console.
- For Helm: edit values if needed, click Create, wait for database and
  Developer Hub to start, then click the Open URL icon.

## Workflow

1. Confirm the RHDH version baseline.
2. Read `references/official-doc-extraction.md`.
3. Choose Operator or Helm based on requirements.
4. Follow the platform-specific steps for OSD on Google Cloud.
5. Verify access through the web console or URL.

## Related Skills

- Use `rhdh-install-aks` for AKS installation.
- Use `rhdh-install-eks` for EKS installation.
- Use `rhdh-install-gke` for GKE installation.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
