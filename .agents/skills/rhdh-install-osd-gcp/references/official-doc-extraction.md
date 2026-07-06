# Official Doc Extraction

Use this extraction to keep Red Hat Developer Hub OpenShift Dedicated on Google
Cloud installation content grounded in official Red Hat sources.

## Operator-Based Installation

### Prerequisites

- Valid Google Cloud account.
- OpenShift Dedicated cluster running on Google Cloud.
- Administrator access to OpenShift Dedicated cluster and Google Cloud project.
- System meets minimum sizing requirements.

### Provision Custom Configuration

Create a ConfigMap named `app-config-rhdh` and a Kubernetes Secret containing
the `BACKEND_SECRET`. These resources are used by the Developer Hub instance
for authentication and application settings.

ConfigMap with `app-config.yaml`:

```yaml
apiVersion: v1
kind: ConfigMap
metadata:
  name: app-config-rhdh
data:
  "app-config.yaml": |
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

Secret with `BACKEND_SECRET`:

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: my-rhdh-secrets
stringData:
  BACKEND_SECRET: "xxx"
```

The `baseUrl` is **required** for the Red Hat Developer Hub to function
correctly. If not set, frontend and backend services cannot communicate
properly, and features may not work as expected.

### Verification

- Review the configuration, select deployment options, and click Create.
- Access Developer Hub via the URL provided in the OpenShift web console.

## Helm Chart Installation

### Prerequisites

- Valid Google Cloud account.
- OpenShift Dedicated cluster running on Google Cloud.
- Helm 3 or the latest installed.
- System meets minimum sizing requirements.

### Configuration via Form View

Navigate to Root Schema > global > Enable service authentication within
Backstage instance and paste the OpenShift Container Platform router host.

### Configuration via YAML View

Set the `global.clusterRouterBase` parameter:

```yaml
global:
  auth:
    backend:
      enabled: true
  clusterRouterBase: apps.<clusterName>.com
```

Alternatively, configure `baseUrl` explicitly:

```yaml
global:
  app:
    baseUrl: https://<your-developer-hub-link>
  backend:
    baseUrl: https://<your-developer-hub-link>
    cors:
      origin: https://<your-developer-hub-link>
```

You can also define additional secrets, plugins, and advanced configuration in
your `values.yaml` file.

### Verification

- Edit other values if needed, then click Create and wait for the database and
  Developer Hub to start.
- Access Developer Hub by clicking the Open URL icon.

## Additional Resources

- Configuring Red Hat Developer Hub
- Customizing Red Hat Developer Hub
- Provisioning your custom Red Hat Developer Hub configuration
