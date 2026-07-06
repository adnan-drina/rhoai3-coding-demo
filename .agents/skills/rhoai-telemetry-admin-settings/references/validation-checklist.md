# Validation Checklist

Use this checklist before finalizing telemetry content.

## Usage Data Collection

- The desired collection state is explicit.
- Disconnected-environment behavior is not misstated.
- Dashboard instructions point to Settings -> Cluster settings.
- `disableTracking` semantics are not reversed.

## MaaS Telemetry

- MaaS telemetry is not confused with the central observability stack.
- `Tenant` custom resource fields are verified before use.
- Usage dashboard output is described as showback, not billing-grade metering.
- Technology Preview posture is labeled where MaaS observability dashboard is
  discussed.

## Live Checks

Run only after the OpenShift safety guard passes:

```bash
oc get odhdashboardconfig -n redhat-ods-applications odh-dashboard-config -o yaml
oc explain tenant.spec
oc get tenant -n models-as-a-service
```
