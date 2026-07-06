# Validation Checklist

Use this checklist before approving OpenShift AI dashboard application changes.

## Source Review

- Product links use the active baseline in `docs/PLATFORM_BASELINE.md`.
- `OdhApplication` and `OdhDashboardConfig` fields are based on official docs
  or active CRD verification.
- Application tiles represent implemented and reachable capabilities.
- Support category labels are accurate: Red Hat managed, Partner managed, or
  Self-managed.
- Operator uninstall guidance includes the CRD/managed-resource/off-cluster
  cleanup boundary.
- No credentials, private URLs, or internal tokens are embedded in dashboard
  links or markdown.

## OdhApplication Review

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc explain odhapplication.spec
oc get odhapplication -n redhat-ods-applications
oc describe odhapplication <name> -n redhat-ods-applications
oc get route <route-name> -n <route-namespace>
```

Check:

- resource namespace matches the OpenShift AI application namespace
- labels include `app: odh-dashboard` and
  `app.kubernetes.io/part-of: odh-dashboard`
- route and route namespace point to an existing application route
- display name, provider, support text, category, docs link, and description
  are accurate
- SVG icon is small, valid, and safe for dashboard display
- `enable.validationConfigMap` references the intended ConfigMap when used
- tile appears in Applications Explore and can be enabled
- enabled tile appears in Applications Enabled

## Dashboard Configuration Review

Run only after following the OpenShift safety guard in `AGENTS.md`:

```bash
oc explain odhdashboardconfig.spec.dashboardConfig
oc explain odhdashboardconfig.spec.notebookController
oc get odhdashboardconfig odh-dashboard-config -n redhat-ods-applications -o yaml
```

Check:

- `spec.dashboardConfig.enablement` is `true` when dashboard users should be
  allowed to add applications.
- `spec.dashboardConfig.enablement` is `false` when adding applications should
  be disabled.
- `spec.dashboardConfig.disableInfo` matches the desired information-panel
  behavior.
- `spec.dashboardConfig.disableISVBadges` matches the desired support-label
  behavior.
- notebook controller `enabled` is set to `false` only when the default Start
  basic workbench tile should be hidden.
- GitOps changes preserve unrelated dashboard configuration fields.

## Disabling Applications Review

Before uninstalling an Operator or disabling a connected application:

- confirm explicit user approval for destructive work
- list Operator-owned CRs and resources
- decide whether CRDs should remain or be removed
- identify application workloads that might continue after Operator uninstall
- identify off-cluster resources that require manual cleanup
- define rollback or reinstall expectations

Readonly checks:

```bash
oc get operators -n redhat-ods-applications
oc get csv -n redhat-ods-applications
oc get crd | rg '<operator-or-application-keyword>'
oc get all -A | rg '<application-keyword>'
```

## GitOps Review

- Long-lived `OdhApplication`, `OdhDashboardConfig`, route, ConfigMap, and
  related RBAC resources are managed through ArgoCD.
- Sync waves ensure the target application route exists before the dashboard
  tile is promoted.
- Documentation explains why the tile exists and whether it is Red Hat managed,
  Partner managed, or Self-managed.
- README claims do not imply a dashboard application is available until the
  route and tile are implemented.

## Fail Conditions

- A dashboard tile points to a missing or private route.
- The support category overstates Red Hat support.
- `enablement: false` is set while expecting users to add applications through
  the dashboard.
- Operator uninstall is treated as complete cleanup.
- The default basic workbench tile is hidden without checking whether the demo
  still needs the basic workbench workflow.
- Unknown `OdhApplication` or `OdhDashboardConfig` fields are added without CRD
  verification.
