# Distributed Tracing Review Patterns

These examples are review patterns and small schema reminders, not complete
deployment manifests. Verify Red Hat docs and active CRDs before committing
resources.

## Source Boundary Review

Use this decision flow:

| Task | Skill |
|------|-------|
| Explain the broad OCP observability model | `ocp-observability` |
| Install or configure Tempo Operator | `ocp-distributed-tracing` |
| Configure `TempoStack`, tenants, storage, Jaeger UI, or query RBAC | `ocp-distributed-tracing` |
| Configure `TempoMonolithic` for a demo | `ocp-distributed-tracing` with Technology Preview labeling |
| Configure Collector pipelines to send traces to Tempo | `ocp-opentelemetry` |
| Interpret RHOAI guardrails spans or detector metrics | `rhoai-guardrails-safety` |
| Review RHOAI observability dashboard behavior | `rhoai-observability` |
| Author GitOps manifests | `project-gitops-authoring` |
| Review manifest correctness and security posture | `project-manifest-review` |
| Deploy or troubleshoot against a live cluster | relevant `env-*` skill plus the OpenShift safety guard |

## TempoStack Shape

The captured docs use this resource shape:

```yaml
apiVersion: tempo.grafana.com/v1alpha1
kind: TempoStack
metadata:
  name: simplest
  namespace: <permitted_project_of_tempostack_instance>
spec:
  storage:
    secret:
      name: <secret_name>
      type: <secret_provider>
  tenants:
    mode: openshift
    authentication:
      - tenantName: dev
        tenantId: "<unique_tenant_id>"
```

Review points:

- Object storage is required for `TempoStack`.
- Tenant IDs must be unique through the lifecycle of the deployment.
- Read and write RBAC must match the claimed tenant access.
- Keep storage credentials in Secrets and out of Git.
- Verify every field with Red Hat docs or `oc explain` before committing.

## Demo Storage Decision

| Need | Preferred path |
|------|----------------|
| Reusable demo tracing backend | `TempoStack` with supported object storage |
| Small demonstration or proof of concept | `TempoMonolithic`, clearly labeled Technology Preview |
| Non-persistent throwaway traces | `TempoMonolithic` in-memory storage, demo/test only |
| Horizontal scale | `TempoStack`, not `TempoMonolithic` |
| AWS-hosted demo with S3 STS | Technology Preview labeling and explicit approval |

## Troubleshooting Pattern

Use read-only checks first:

```bash
oc get tempostack -A
oc get tempomonolithic -A
oc get pods -n openshift-tempo-operator
oc get pods -n <tempo_instance_namespace>
oc get routes -A | grep -Ei 'tempo|jaeger'
```

Use must-gather only after the OpenShift safety guard confirms the target
cluster:

```bash
oc adm must-gather --image=ghcr.io/grafana/tempo-operator/must-gather -- \
  /usr/bin/must-gather --operator-namespace openshift-tempo-operator
```
