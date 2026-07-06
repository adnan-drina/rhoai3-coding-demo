# Official Doc Extraction

## Usage Data Collection

- OpenShift AI administrators can choose whether Red Hat collects usage data
  about OpenShift AI usage in their cluster.
- Usage data collection lets Red Hat monitor and improve software and support.
- Usage data collection is enabled by default when OpenShift AI is installed
  except in disconnected environments.
- Administrators enable or disable collection from OpenShift AI dashboard
  Settings -> Cluster settings, in the Usage data collection section.
- The dashboard configuration option `spec.dashboardConfig.disableTracking`
  controls whether Red Hat usage data collection is allowed; setting it to
  `true` disables collection.

## Usage Data Notice

The usage data notice says collected metrics can include:

- applications enabled in the product dashboard,
- deployment sizes such as CPU and memory resources,
- documentation resources accessed from the dashboard,
- notebook image names,
- a random identifier generated during initial user login,
- usage information about components, features, and extensions.

The notice states Red Hat does not intend to collect personal information and
will delete inadvertently received personal information.

## MaaS Telemetry

- MaaS telemetry can be enabled in the `Tenant` custom resource to collect
  usage metrics from MaaS inference requests.
- MaaS telemetry generates Prometheus metrics about model usage, including
  token consumption, request counts, and model-specific usage patterns.
- Metrics are displayed in the MaaS observability dashboard.
- The MaaS observability dashboard can show token consumption, request counts,
  and rate-limit violations across subscriptions and users.
- Red Hat notes that the MaaS observability dashboard is intended for internal
  usage tracking and showback reporting, not billing-grade metering or
  external invoicing.

## Preview Boundary

RHOAI 3.4 release notes describe the MaaS observability dashboard as a
Technology Preview feature. Label demo content accordingly.
