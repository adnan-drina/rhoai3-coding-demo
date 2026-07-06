---
name: rhdh-diagnostic-data
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhdh"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Developer Hub"
description: >
  Use when collecting diagnostic data to streamline support case resolution
  for Red Hat Developer Hub 1.10. Covers the must-gather tool on OpenShift
  and Kubernetes, air-gapped mirroring, heap dump collection, collector
  configuration, command-line flags, environment variables, Helm chart
  values, and output structure. Do NOT use for Scorecard configuration
  (use rhdh-scorecards), Orchestrator workflows (use rhdh-orchestrator),
  or general RHDH installation.
---

# RHDH Diagnostic Data

Use this skill to collect diagnostic data from Red Hat Developer Hub 1.10
deployments using the must-gather tool, grounded in official product
documentation.

## Source Grounding

Read `references/source-capture.md` before using product behavior. Official Red
Hat documentation is product authority.

## Support Posture

The must-gather diagnostic data collection is **Technology Preview** — not
supported with Red Hat production SLAs. Use when opening support tickets,
troubleshooting deployment issues, or capturing state before upgrades.

## Key Capabilities

1. **OpenShift collection** — `oc adm must-gather` with the RHDH must-gather
   image; auto-detects Operator and Helm deployments.
2. **Kubernetes collection** — Helm-based install via
   `redhat-developer-hub-must-gather` chart with `kubectl` workflow.
3. **Air-gapped support** — mirror the must-gather image to internal
   registries using `skopeo`; supports partially and fully disconnected
   environments.
4. **Heap dump collection** — Node.js heap snapshots via inspector protocol
   or SIGUSR2 signal; requires liveness probe timeout increase.
5. **Collector control** — default-enabled collectors (platform, helm,
   operator, orchestrator, route/ingress, namespace-inspect) and opt-in
   collectors (cluster-info, heap-dumps).
6. **Configuration** — CLI flags, environment variables, and Helm chart values
   for namespace filtering, log levels, timeouts, and retention.
7. **Output organization** — structured by collector type, namespace, and
   resource type with known file locations for common diagnostics.

## Must-Gather Image

```
registry.access.redhat.com/rhdh/rhdh-must-gather-rhel9:1.10
```

## Quick Reference — OpenShift

```bash
oc adm must-gather \
  --image=registry.access.redhat.com/rhdh/rhdh-must-gather-rhel9:1.10
```

Output: `./must-gather.local.<timestamp>/`

### Advanced flags

```bash
# Skip Helm-based deployments
-- /usr/bin/gather --without-helm

# Skip Operator-based deployments
-- /usr/bin/gather --without-operator

# Collect heap dumps
-- /usr/bin/gather --with-heap-dumps

# Specific namespaces only
-- /usr/bin/gather --namespaces rhdh-prod,rhdh-plugins
```

## Quick Reference — Kubernetes

```bash
helm upgrade --install my-rhdh-must-gather redhat-developer-hub-must-gather \
  --repo https://charts.openshift.io \
  --namespace rhdh-diagnostics \
  --create-namespace

kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/instance=my-rhdh-must-gather,app.kubernetes.io/component=gather \
  --timeout=3600s -n rhdh-diagnostics

kubectl exec deploy/my-rhdh-must-gather -c data-holder -n rhdh-diagnostics -- \
  tar czf - -C /must-gather . > rhdh-must-gather-output.tar.gz

helm uninstall my-rhdh-must-gather -n rhdh-diagnostics
```

## Heap Dump Collection

Requires liveness probe timeout increase (e.g., `failureThreshold: 180`) to
prevent pod restarts. RHDH stops responding during collection.

Methods:
- **Inspector protocol** — default, works out of the box
- **SIGUSR2** — requires `NODE_OPTIONS: "--heapsnapshot-signal=SIGUSR2 --diagnostic-dir=/tmp"`

Typical sizes: 50 MB to 500 MB per heap dump file.

## Output Structure

| Path | Contents |
|------|----------|
| `version`, `must-gather.log` | Collection metadata |
| `sanitization-report.txt` | Data sanitization summary |
| `platform/` | Platform and infrastructure info |
| `helm/` | Helm deployment data |
| `operator/` | Operator deployment data |
| `orchestrator/` | Orchestrator data |
| `namespace-inspect/` | Deep namespace inspect data |

### Common diagnostic data locations

| Data | Location |
|------|----------|
| Backend pod logs | `namespace-inspect/namespaces/<ns>/pods/<pod>/backstage-backend/logs/current.log` |
| Operator logs | `operator/ns=<ns>/logs.txt` |
| Helm release values | `helm/releases/ns=<ns>/<release>/values.yaml` |
| Heap dumps | `helm/releases/ns=<ns>/<release>/deployment/heap-dumps/` or `operator/backstage-crs/ns=<ns>/<cr>/deployment/heap-dumps/` |

## Security Note

Output may contain sensitive information (configuration values, environment
variables, logs). The tool automatically sanitizes known secret types, but
review output before sharing with support.

## Workflow

1. Read `references/official-doc-extraction.md` for exact commands and YAML.
2. Identify platform: OpenShift (`oc adm must-gather`) or Kubernetes (Helm).
3. Determine collection scope: default collectors, heap dumps, or specific
   namespaces.
4. For air-gapped: mirror the image first, configure pull secrets.
5. For heap dumps: increase liveness probe timeout, plan maintenance window.
6. Verify output contains expected directories and files.
7. Review output for sensitive data before sharing.

## Related Skills

- `rhdh-scorecards` — Project Health Scorecards
- `rhdh-orchestrator` — Orchestrator serverless workflows

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
