# Telemetry Review Pattern

## Red Hat Usage Data Collection

Record the intended state:

```text
Usage data collection: enabled | disabled
Source: RHOAI 3.4 managing resources, Chapter 9
Dashboard path: Settings -> Cluster settings -> Usage data collection
GitOps field: verify current OdhDashboardConfig schema before authoring
```

## MaaS Usage Telemetry

Record the intended state:

```text
MaaS telemetry: enabled | disabled
Source: RHOAI 3.4 Govern LLM access with Models-as-a-Service
CR owner: Tenant in models-as-a-service namespace
Posture: Technology Preview for the MaaS observability dashboard in RHOAI 3.4
Boundary: showback and usage tracking only, not billing-grade metering
```
