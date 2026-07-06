# Official Doc Extraction

Use this extraction to keep Red Hat OpenShift distributed tracing platform
content grounded in official Red Hat documentation. Before authoring manifests,
verify the active cluster CRDs and installed Operator version.

## Product Definition

The official About guide explains distributed tracing as recording the path of
a request through microservices and presenting that path as a trace. A trace is
a data or execution path through the system and contains one or more spans.

A span represents a logical unit of work. The captured docs describe a span as
having an operation name, start time, duration, and potentially tags and logs.
Spans can be nested and ordered to model causal relationships.

The captured use cases include:

- monitoring distributed transactions
- optimizing performance and latency
- root cause analysis

The captured related components are:

- Red Hat build of OpenTelemetry for forwarding traces to `TempoStack`
- distributed tracing UI plugin of the Cluster Observability Operator

The captured features include Kiali integration when configured, scalable back
end behavior, distributed context propagation, and Zipkin-compatible APIs. The
docs state that Zipkin compatibility is not supported in this release.

The 3.9 release notes state that only supported features are documented and
undocumented features are unsupported. Use that as the default boundary when an
upstream Tempo feature is not present in Red Hat documentation for the active
baseline.

## Tempo Operator Installation

The install guide states that distributed tracing installation starts with the
Tempo Operator. After setting up supported object storage and creating a
storage secret, tenants and permissions must also be configured.

The captured default web console presets are:

- update channel: `stable`
- installation mode: all namespaces on the cluster
- installed namespace: `openshift-tempo-operator`
- update approval: `Automatic`

The captured CLI install example uses:

- project namespace: `openshift-tempo-operator`
- namespace labels:
  - `kubernetes.io/metadata.name: openshift-tempo-operator`
  - `openshift.io/cluster-monitoring: "true"`
- `OperatorGroup` in `openshift-tempo-operator`
- `Subscription` named `tempo-product`
- channel: `stable`
- install plan approval: `Automatic`
- source: `redhat-operators`
- source namespace: `openshift-marketplace`

## Object Storage

The install guide states that object storage is required and not included with
distributed tracing. You must choose and set up object storage by a supported
provider before installing distributed tracing.

The captured object storage setup includes secret parameters and examples for
providers such as Red Hat OpenShift Data Foundation, MinIO, IBM Cloud Object
Storage, Amazon S3, Azure Blob Storage, and Google Cloud Platform Storage.

Amazon S3 with Security Token Service and Azure storage with Security Token
Service are captured as Technology Preview.

Do not deploy `TempoStack` without storage. Do not commit real storage
credentials.

## Tenants And RBAC

Before installing `TempoStack` or `TempoMonolithic`, the docs require one or
more tenants and read/write access configuration.

Tenant access is global: granting access to a tenant applies to all
`TempoStack` and `TempoMonolithic` instances whose configuration includes that
tenant.

By default, no users are granted read or write permissions. The captured model
uses Kubernetes RBAC with `ClusterRole` and `ClusterRoleBinding`.

The captured tenant model includes:

- `tenants.mode: openshift`
- `tenants.authentication[].tenantName`
- `tenants.authentication[].tenantId`
- tenant names used as the `X-Scope-OrgId` HTTP header
- tenant IDs that must be unique throughout the lifecycle of the deployment

## TempoStack

The install guide supports creating multiple `TempoStack` instances in
separate projects. Project names beginning with the `openshift-` prefix are
not permitted.

The captured `TempoStack` examples use:

- API version: `tempo.grafana.com/v1alpha1`
- kind: `TempoStack`
- `spec.storage.secret.name`
- `spec.storage.secret.type`
- `spec.storageSize`
- `spec.resources.total.limits`
- `spec.tenants.mode`
- `spec.tenants.authentication`
- `spec.template.gateway.enabled`
- `spec.template.queryFrontend.jaegerQuery.enabled`

The docs state that `TempoStack` is configured to receive Jaeger Thrift over
HTTP and OpenTelemetry Protocol (OTLP). Red Hat supports only the custom
resource options available in the distributed tracing documentation.

The captured storage secret type values are:

- `azure` for Azure Blob Storage
- `gcs` for Google Cloud Platform Storage
- `s3` for Amazon S3, MinIO, or Red Hat OpenShift Data Foundation

The captured validation commands include checking the `TempoStack` status and
conditions and checking that all component pods are running.

## TempoMonolithic

The install guide captures `TempoMonolithic` as Technology Preview. Red Hat
does not recommend Technology Preview features in production.

The docs state that `TempoMonolithic` creates a Tempo deployment in monolithic
mode with Tempo components in a single container. It does not scale
horizontally. If horizontal scaling is required, use `TempoStack`.

The captured `TempoMonolithic` storage options include in-memory storage,
persistent volume, or object storage. In-memory storage is appropriate only for
development, testing, demonstrations, and proof-of-concept environments
because data does not persist when the pod shuts down.

## Configuration

The configuration guide covers:

- Tempo Operator configuration through the OLM `Subscription`
- back-end storage
- `TempoStack` configuration parameters
- deployment sizing
- query configuration options
- distributed tracing UI plugin
- Monitor tab in Jaeger UI
- receiver TLS
- query RBAC
- taints and tolerations
- monitoring and alerts

The configuration guide states that the Tempo Operator uses CRDs to define the
architecture and configuration settings for creating and deploying distributed
tracing resources.

The captured examples include `createPrometheusRules: true` for metrics and
alerts, receiver TLS under Tempo distributor or ingestion settings, and query
RBAC for tenant access. Use exact Red Hat docs or active `oc explain` output
before authoring these fields.

## Troubleshooting

The troubleshooting source states that you can diagnose and fix issues in
`TempoStack` or `TempoMonolithic` instances through troubleshooting methods.

The captured must-gather command uses:

```bash
oc adm must-gather --image=ghcr.io/grafana/tempo-operator/must-gather -- \
  /usr/bin/must-gather --operator-namespace <operator_namespace>
```

The default Operator namespace is `openshift-tempo-operator`.

## Demo-Specific Handoff

The following are project constraints, not claims extracted from the
distributed tracing docs:

- Use GitOps for active Tempo Operator, `TempoStack`, `TempoMonolithic`, RBAC,
  tenant, storage, route, TLS, and monitoring resources.
- Prefer `TempoStack` for reusable demo infrastructure.
- Use `TempoMonolithic` only when the Technology Preview and demo/test
  boundaries are explicit.
- Use `ocp-opentelemetry` for Collector and instrumentation resources that
  send traces to Tempo.
- Use `rhoai-guardrails-safety` for guardrails-specific trace semantics.

Use `project-gitops-authoring` and `project-manifest-review` for repo-specific
implementation and review rules.
