# Official Documentation Extraction

This extraction is derived from the official RHOAI 3.4 chapter captured in
`source-capture.md`.

## Configuration Resource

- The OpenShift AI dashboard is configured by the `OdhDashboardConfig` custom
  resource.
- The documented instance name is `odh-dashboard-config`.
- The default OpenShift AI application namespace is `redhat-ods-applications`.
- Administrators can edit the resource from the OpenShift console API Explorer.
- If a dashboard configuration option is absent, the documented default value
  is used.

Official console path:

```text
OpenShift console -> Administrator perspective -> Home -> API Explorer
```

Procedure summary:

1. Search for `OdhDashboardConfig`.
2. Select the OpenShift AI application namespace.
3. Open the `odh-dashboard-config` instance.
4. Edit YAML.
5. Save and reload to synchronize changes to the cluster.

## Boolean Behavior

Most `spec.dashboardConfig.disable*` fields use inverted behavior:

- `false` shows or enables the feature.
- `true` hides or disables the feature.

Some feature flags use positive behavior:

- `true` shows or enables the feature.
- `false` hides or disables the feature.

Review the specific field before changing it.

## Dashboard Configuration Fields

| Field | Default | Official behavior summary |
|-------|---------|---------------------------|
| `spec.dashboardConfig.aiAssetCustomEndpoints` | `false` | Shows Gen AI Studio AI asset endpoint creation when enabled |
| `spec.dashboardConfig.deploymentWizardYAMLViewer` | `false` | Shows YAML preview for `LLMInferenceService` resources when enabled |
| `spec.dashboardConfig.disableAdminConnectionTypes` | `false` | Hides Settings -> Environment setup -> Connection types when `true` |
| `spec.dashboardConfig.disableBYONImageStream` | `false` | Hides Settings -> Environment setup -> Workbench images when `true` |
| `spec.dashboardConfig.disableClusterManager` | `false` | Hides Settings -> Cluster settings when `true` |
| `spec.dashboardConfig.disableCustomServingRuntimes` | `false` | Hides Settings -> Model resources and operations -> Serving runtimes when `true` |
| `spec.dashboardConfig.disableDistributedWorkloads` | `false` | Hides Workload metrics under Observe and monitor when `true` |
| `spec.dashboardConfig.disableFeatureStore` | `false` | Hides Feature store navigation when `true` |
| `spec.dashboardConfig.disableFineTuning` | no longer used | Deprecated and has no effect |
| `spec.dashboardConfig.disableKueue` | `true` | Hides Kueue-related dashboard options when `true`; set `false` to enable Kueue options |
| `spec.dashboardConfig.disableLMEval` | `true` | Technology Preview; hides evaluation features when `true` |
| `spec.dashboardConfig.disableHome` | `false` | Hides Home when `true` |
| `spec.dashboardConfig.disableInfo` | `false` | Hides application information panels when `true` |
| `spec.dashboardConfig.disableISVBadges` | `false` | Hides application support-level labels when `true` |
| `spec.dashboardConfig.disableKServe` | `false` | Disables selecting KServe as a model-serving platform when `true` |
| `spec.dashboardConfig.disableKServeAuth` | `false` | Disables KServe authentication UI when `true` |
| `spec.dashboardConfig.disableKServeMetrics` | `false` | Disables KServe metrics visibility when `true` |
| `spec.dashboardConfig.disableKServeRaw` | `false` | Controls whether the model serving platform default deployment mode list is shown |
| `spec.dashboardConfig.disableLLMd` | `false` | Controls distributed inference with llm-d toggle and wizard option |
| `spec.dashboardConfig.disableModelCatalog` | `false` | Hides AI hub -> Catalog when `true` |
| `spec.dashboardConfig.disableModelRegistry` | `false` | Hides AI hub -> Registry and AI registry settings when `true` |
| `spec.dashboardConfig.disableModelRegistrySecureDB` | `false` | Hides CA certificate controls for secure model registry database connections when `true` |
| `spec.dashboardConfig.disableModelServing` | `false` | Hides AI hub -> Deployments and project Deployments tab when `true` |
| `spec.dashboardConfig.disableNIMModelServing` | `false` | Disables NVIDIA NIM model-serving platform selection when `true` |
| `spec.dashboardConfig.disablePerformanceMetrics` | `false` | Hides Endpoint Performance on Deployments when `true` |
| `spec.dashboardConfig.disablePipelines` | `false` | Hides Develop and train navigation when `true` |
| `spec.dashboardConfig.disableProjects` | `false` | Hides Projects navigation when `true` |
| `spec.dashboardConfig.projectRBAC` | `true` | Technology Preview; enables enhanced RBAC Permissions tab when `true` |
| `spec.dashboardConfig.disableProjectScoped` | `false` | Hides global versus project-scoped distinction when `true` |
| `spec.dashboardConfig.disableProjectSharing` | `false` | Prevents users from sharing projects when `true` |
| `spec.dashboardConfig.disableServingRuntimeParams` | `false` | Hides configuration parameters in model deployment dialogs when `true` |
| `spec.dashboardConfig.disableStorageClasses` | `false` | Hides Settings -> Cluster settings -> Storage classes when `true` |
| `spec.dashboardConfig.disableSupport` | `false` | Hides Support from the dashboard Help menu when `true` |
| `spec.dashboardConfig.disableTracking` | `false` | Enables Red Hat usage-data collection when `false`; set `true` to disable |
| `spec.dashboardConfig.disableTrustyBiasMetrics` | `false` | Hides the Model Bias tab when `true` |
| `spec.dashboardConfig.disableUserManagement` | `false` | Hides Settings -> User management when `true` |
| `spec.dashboardConfig.enablement` | `true` | Allows administrators to add applications to the dashboard when `true` |
| `spec.dashboardConfig.externalVectorStores` | `false` | Developer Preview; shows Vector stores on AI asset endpoints when enabled |
| `spec.dashboardConfig.genAiStudio` | `false` | Technology Preview; shows Gen AI Studio when `true` |
| `spec.dashboardConfig.llmGatewayField` | `false` | Technology Preview; shows gateway selection in model deployment advanced settings |
| `spec.dashboardConfig.mcpCatalog` | `false` | Developer Preview; enables MCP server catalog browsing and deployment |
| `spec.dashboardConfig.mlflow` | `false` | Developer Preview; shows MLflow tile on Applications -> Explore when `true` |
| `spec.dashboardConfig.modelAsService` | `false` | Technology Preview; shows Model as a service on AI asset endpoints when `true` |
| `spec.dashboardConfig.observabilityDashboard` | `false` | Technology Preview; shows Observe and monitor -> Dashboard when `true` |
| `spec.dashboardConfig.promptManagement` | `false` | Technology Preview; enables prompt management in Gen AI Studio Chat Playground |
| `spec.dashboardConfig.trainingJobs` | `true` | Technology Preview; shows Develop and train -> Training jobs when `true` |
| `spec.dashboardConfig.vLLMDeploymentOnMaaS` | `false` | Technology Preview; enables the new vLLM on MaaS deployment option |

## Gen AI Studio Endpoint Settings

Additional endpoint settings live under:

```text
spec.genAiStudioConfig.aiAssetCustomEndpoints
```

Documented fields:

| Field | Default | Official behavior summary |
|-------|---------|---------------------------|
| `clusterDomains` | `[]` | Internal domains in addition to `.svc.cluster.local` |
| `externalProviders` | `false` | Allows external third-party provider endpoints when `true`; also requires `spec.dashboardConfig.aiAssetCustomEndpoints: true` |

## Other Dashboard Config Sections

| Field | Default | Official behavior summary |
|-------|---------|---------------------------|
| `spec.groupsConfig` | no longer used | Read-only; use `spec.adminGroups` and `spec.allowedGroups` in the OpenShift `Auth` resource in the `services.platform.opendatahub.io` API group |
| `spec.modelServerSizes` | `Small`, `Medium`, `Large` | Customizes names and resources for model servers |
| `spec.notebookController.enabled` | `true` | Shows the Start basic workbench tile and button when `true` |
| `spec.notebookSizes` | `Small`, `Medium`, `Large`, `X Large` | Customizes names and resources for workbenches; requests must be smaller than limits |
| `spec.templateOrder` | `[]` | Specifies custom Serving Runtime template order |

## Support Posture

Fields marked Technology Preview or Developer Preview must be documented with
their support posture before they are used in demo README content or operations
runbooks. Do not present those features as production SLA-backed capabilities.

## Out Of Scope For This Chapter

This chapter does not define:

- how to install the underlying components exposed by dashboard flags
- full CRD schema for every field
- GitOps ownership of `OdhDashboardConfig`
- complete model server or notebook size examples
- operational validation for KServe, Kueue, Feature Store, observability,
  MLflow, MaaS, MCP, Gen AI Studio, or training jobs

Use component-specific skills and active schema checks before implementing
those areas.
