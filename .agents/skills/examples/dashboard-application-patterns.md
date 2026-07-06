# Dashboard Application Patterns

These examples are minimal review patterns. Verify active CRDs with `oc
explain` before promotion to GitOps.

## Dashboard Tile With OdhApplication

```yaml
apiVersion: dashboard.opendatahub.io/v1
kind: OdhApplication
metadata:
  name: demo-application
  namespace: redhat-ods-applications
  labels:
    app: odh-dashboard
    app.kubernetes.io/part-of: odh-dashboard
spec:
  displayName: Demo Application
  description: Demo application surfaced in the OpenShift AI dashboard.
  provider: rhoai3-demo
  support: Self-managed by the demo team
  category: Self-managed
  docsLink: https://example.com/docs
  getStartedLink: https://example.com/docs/get-started
  getStartedMarkDown: |-
    # Demo Application
    Use this application for the implemented demo workflow.
  img: |-
    <svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
      <rect width="24" height="24" fill="#ee0000"/>
    </svg>
  route: demo-application
  routeNamespace: demo-application
  kfdefApplications: []
  csvName: ""
  quickStart: ""
  enable:
    validationConfigMap: demo-application-enable
```

Review before use:

- route exists in `routeNamespace`
- docs and get-started links are reachable
- category does not overstate support
- validation ConfigMap behavior is understood for the target application

## Dashboard Configuration Fragment

This fragment shows documented fields. Preserve unrelated fields when patching
an existing `odh-dashboard-config` resource.

```yaml
apiVersion: dashboard.opendatahub.io/v1
kind: OdhDashboardConfig
metadata:
  name: odh-dashboard-config
  namespace: redhat-ods-applications
spec:
  dashboardConfig:
    enablement: true
    disableInfo: false
    disableISVBadges: false
  notebookController:
    enabled: true
```

Common demo choices:

```text
Allow dashboard application additions: spec.dashboardConfig.enablement=true
Hide application information panels: spec.dashboardConfig.disableInfo=true
Hide support-level badges: spec.dashboardConfig.disableISVBadges=true
Hide Start basic workbench: spec.notebookController.enabled=false
```

Do not apply this as a full replacement unless the active CRD and existing
resource content have been reviewed.
