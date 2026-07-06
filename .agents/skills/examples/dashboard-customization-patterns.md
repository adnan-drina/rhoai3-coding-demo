# Dashboard Customization Patterns

These examples are review patterns for `OdhDashboardConfig`. They are not
active GitOps manifests until copied into the clean-slate implementation and
validated against the target cluster schema.

## Minimal Visibility Fragment

```yaml
apiVersion: dashboard.opendatahub.io/v1
kind: OdhDashboardConfig
metadata:
  name: odh-dashboard-config
  namespace: redhat-ods-applications
spec:
  dashboardConfig:
    disableFeatureStore: false
    disableModelRegistry: false
    disableModelServing: false
    disableProjects: false
    disableUserManagement: false
```

Review points:

- Preserve existing fields in the active resource.
- A visible menu does not prove the underlying component is ready.
- Use component-specific validation before documenting an end-to-end workflow.

## Hide Unused Demo Navigation

```yaml
spec:
  dashboardConfig:
    disableAdminConnectionTypes: true
    disableClusterManager: true
    disableStorageClasses: true
    disableSupport: true
```

Review points:

- Hiding administrator menus can make operations harder during demos.
- Keep access to required Settings pages for the operators running the demo.
- Document intentional dashboard simplification in operations notes.

## Enable Kueue Dashboard Controls

```yaml
spec:
  dashboardConfig:
    disableKueue: false
```

Review points:

- The documented default is `true`, which hides Kueue options.
- Setting this to `false` exposes Kueue dashboard behavior.
- Pair with `rhoai-kueue-workload-management` and queue validation.

## Technology Preview And Developer Preview Flags

```yaml
spec:
  dashboardConfig:
    genAiStudio: true
    modelAsService: true
    observabilityDashboard: true
    mcpCatalog: true
```

Review points:

- `genAiStudio`, `modelAsService`, and `observabilityDashboard` are Technology
  Preview in the captured chapter.
- `mcpCatalog` is Developer Preview in the captured chapter.
- User-facing material must label support posture before demoing these flags.

## Gen AI Studio External Provider Endpoint Controls

```yaml
spec:
  dashboardConfig:
    aiAssetCustomEndpoints: true
  genAiStudioConfig:
    aiAssetCustomEndpoints:
      clusterDomains:
      - apps.demo.example.com
      externalProviders: true
```

Review points:

- `externalProviders: true` also requires
  `spec.dashboardConfig.aiAssetCustomEndpoints: true`.
- Validate endpoint security, credential handling, and allowed providers before
  enabling in a shared environment.

## Basic Workbench Tile Control

```yaml
spec:
  notebookController:
    enabled: false
```

Review points:

- Setting `enabled` to `false` hides the Start basic workbench tile and button.
- Do not hide it if the demo still depends on basic workbench flows.

## Size Profile Shape

```yaml
spec:
  modelServerSizes:
  - name: Small
    resources:
      requests:
        cpu: "1"
        memory: 4Gi
      limits:
        cpu: "2"
        memory: 8Gi
  notebookSizes:
  - name: Medium
    resources:
      requests:
        cpu: "2"
        memory: 8Gi
      limits:
        cpu: "4"
        memory: 16Gi
```

Review points:

- Verify the active CRD schema before adding size profiles.
- Requests must be smaller than limits.
- Align sizes with actual demo cluster capacity.
