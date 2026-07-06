# Validation Checklist

Use this checklist when reviewing Red Hat OpenShift distributed tracing
platform documentation, GitOps manifests, or live operations.

## Source And Baseline

- The task references `docs/PLATFORM_BASELINE.md`.
- Distributed tracing claims are tied to the pinned 3.9 official docs or
  active cluster schema.
- OpenTelemetry Collector and workload instrumentation configuration are
  handled by `ocp-opentelemetry`.
- Broad OCP observability claims are handled by `ocp-observability`.
- Upstream Grafana Tempo docs are not used as Red Hat product authority.

## Manifest Review

- Tempo Operator installation uses verified namespace, `OperatorGroup`,
  `Subscription`, channel, install approval, source, and source namespace.
- `TempoStack` and `TempoMonolithic` resources use verified API versions and
  fields.
- Instance namespaces do not begin with the `openshift-` prefix.
- Object storage is configured before `TempoStack` is deployed.
- Storage secret keys and provider type are verified from Red Hat docs or
  active schema.
- Real object storage credentials, cloud keys, role ARNs, and trace samples are
  not committed.
- Tenants are defined before claiming the instance is usable.
- Read and write RBAC is configured for every claimed tenant access path.
- `gateway.enabled`, `jaegerQuery.enabled`, route exposure, query RBAC, and UI
  plugin behavior are reviewed as access-control surfaces.
- `TempoMonolithic` use is explicitly labeled Technology Preview.
- STS storage modes are explicitly labeled Technology Preview where used.
- Receiver TLS, service-serving certificates, monitoring, alerts, taints, and
  tolerations are verified before authoring fields.
- OpenTelemetry forwarding is reviewed with `ocp-opentelemetry`.

## Read-Only Cluster Checks

Run only after the repo environment guard confirms the target cluster:

```bash
oc get clusterversion
oc get subscription -A | grep -Ei 'tempo|distributed'
oc get csv -A | grep -Ei 'tempo|distributed'
oc get pods -n openshift-tempo-operator
oc api-resources | grep -Ei 'tempo|tracing'
oc get crd | grep -Ei 'tempo|tracing'
oc get tempostack -A
oc get tempomonolithic -A
oc get clusterrole | grep -Ei 'tempo|trace'
oc get clusterrolebinding | grep -Ei 'tempo|trace'
oc get routes -A | grep -Ei 'tempo|jaeger'
```

For schema verification:

```bash
oc explain tempostack.spec
oc explain tempostack.spec.tenants
oc explain tempostack.spec.storage
oc explain tempomonolithic.spec
```

For instance health:

```bash
oc get tempostacks.tempo.grafana.com -A -o yaml
oc get tempomonolithic.tempo.grafana.com -A -o yaml
oc get pods -n <tempo_instance_namespace>
```

For must-gather, use only after confirming the target cluster and output path:

```bash
oc adm must-gather --image=ghcr.io/grafana/tempo-operator/must-gather -- \
  /usr/bin/must-gather --operator-namespace openshift-tempo-operator
```

## Live Operation Review

- The repo-local OpenShift safety guard is used before any `oc` or `kubectl`
  command that touches the cluster.
- Operator installation, Tempo instance creation, storage secret changes,
  tenant changes, RBAC changes, route exposure, TLS changes, UI plugin changes,
  monitoring changes, and removal operations have explicit user approval.
- Argo CD-managed resources are not also managed with direct `oc apply -k`
  unless the exception is documented.
- Trace data is not sent to an unapproved backend or external location.
- Object storage cost, retention, and deletion behavior are documented before
  enabling persistent trace storage.

## Fail Conditions

Stop and ask for verification if:

- the distributed tracing documentation version does not match
  `docs/PLATFORM_BASELINE.md`
- a manifest includes unverified `tempo.grafana.com` fields
- a `TempoStack` lacks object storage, tenants, or RBAC
- `TempoMonolithic` or STS storage is presented as production-ready
- object storage credentials, cloud role details, customer data, or trace
  payloads would be committed
- route, gateway, or Jaeger UI exposure lacks a tenant access review
- the target cluster has no Tempo CRDs installed and the task requires
  schema-accurate manifests
