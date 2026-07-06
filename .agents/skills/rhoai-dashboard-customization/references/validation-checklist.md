# Validation Checklist

Use this checklist before accepting OpenShift AI dashboard customization
changes.

## Source Review

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official chapter URL uses the active `/3.4/` baseline path.
- The change is about `OdhDashboardConfig`, not `OdhApplication` tiles.
- Fields are from the official chapter or verified through active CRD schema.
- Technology Preview and Developer Preview flags are labeled in user-facing
  docs when enabled for a demo.
- Deprecated, no-effect, or read-only fields are not used for new behavior.

## Resource Review

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc explain odhdashboardconfig.spec
oc explain odhdashboardconfig.spec.dashboardConfig
oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o yaml
```

Check:

- resource name is `odh-dashboard-config`
- namespace is the active OpenShift AI application namespace
- existing fields are preserved when applying a change
- absent fields intentionally use documented defaults
- changed fields are under the correct `spec` section

## Feature Flag Review

- `disable*` fields are handled with inverted semantics.
- Positive feature flags such as `genAiStudio`, `modelAsService`, `mlflow`,
  `mcpCatalog`, and `observabilityDashboard` are enabled only with clear scope.
- `disableKueue: false` is paired with Kueue component and queue-management
  readiness when users need Kueue-enabled hardware profiles.
- `disableFeatureStore: false` is not treated as Feature Store deployment.
- `observabilityDashboard: true` is paired with observability-stack readiness.
- `modelAsService: true` is paired with the MaaS governance skill when used.
- `mlflow: true` is paired with `rhoai-mlflow` coverage.
- `mcpCatalog: true` is paired with MCP catalog support posture and source
  validation.

## UX Verification

After applying a change:

- reload the dashboard or reopen the relevant page
- verify the expected navigation item appears or disappears
- verify restricted menus are hidden from users who should not see them
- verify administrator settings still remain reachable when needed
- verify component workflows are backed by installed and validated components

## GitOps Review

- Long-lived `OdhDashboardConfig` changes are managed through ArgoCD once the
  active GitOps implementation exists.
- GitOps patches are narrow and preserve unrelated fields.
- README claims match visible dashboard behavior and implemented components.
- Operations docs record any intentional dashboard profile choices.
- Rollback is a small field change, not a full resource replacement.

## Fail Conditions

- A menu item is exposed before the underlying component is installed or ready.
- A Technology Preview or Developer Preview item is presented as production
  SLA-backed.
- `spec.groupsConfig` is used to configure access.
- `disableFineTuning` is used for new behavior.
- Existing dashboard config fields are removed by a broad replacement.
- Unknown fields are added without official source or schema verification.
