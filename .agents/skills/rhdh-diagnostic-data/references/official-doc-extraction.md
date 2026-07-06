# Official Documentation Extraction

Source: Red Hat Developer Hub 1.10 — Collect diagnostic data to streamline support resolution
Captured: 2026-07-06

---

## 1. Must-Gather on OpenShift

### Basic collection

```bash
oc adm must-gather \
  --image=registry.access.redhat.com/rhdh/rhdh-must-gather-rhel9:1.10
```

Output: `./must-gather.local.<timestamp>/`

Auto-detects and collects from all RHDH instances (Operator and Helm).

### Advanced flags

```bash
# Skip Helm-based deployments
oc adm must-gather \
  --image=registry.access.redhat.com/rhdh/rhdh-must-gather-rhel9:1.10 \
  -- /usr/bin/gather --without-helm

# Skip Operator-based deployments
oc adm must-gather \
  --image=registry.access.redhat.com/rhdh/rhdh-must-gather-rhel9:1.10 \
  -- /usr/bin/gather --without-operator
```

### Verification

```bash
ls must-gather.local.<timestamp>/
# Contains: operator/ and/or helm/ subdirectories
```

---

## 2. Must-Gather on Kubernetes

### Install, collect, extract, cleanup

```bash
# Install
helm upgrade --install my-rhdh-must-gather redhat-developer-hub-must-gather \
  --repo https://charts.openshift.io \
  --namespace rhdh-diagnostics \
  --create-namespace

# Wait for collection
kubectl wait --for=condition=ready pod \
  -l app.kubernetes.io/instance=my-rhdh-must-gather,app.kubernetes.io/component=gather \
  --timeout=3600s -n rhdh-diagnostics

# Extract data
kubectl exec deploy/my-rhdh-must-gather -c data-holder -n rhdh-diagnostics -- \
  tar czf - -C /must-gather . > rhdh-must-gather-output.tar.gz

# Clean up
helm uninstall my-rhdh-must-gather -n rhdh-diagnostics
```

### Helm values for limiting collection

```yaml
# Skip Helm-based deployments
gather:
  withHelm: false

# Skip Operator-based deployments
gather:
  withOperator: false
```

---

## 3. Air-Gapped Clusters

### Partially disconnected — direct mirror

```bash
skopeo copy \
  docker://registry.access.redhat.com/rhdh/rhdh-must-gather-rhel9:<version> \
  docker://<internal-registry>/rhdh/rhdh-must-gather:<version>
```

### Fully disconnected — disk transfer

```bash
# On internet-connected machine
skopeo copy \
  docker://registry.access.redhat.com/rhdh/rhdh-must-gather-rhel9:<version> \
  dir:./rhdh-must-gather-<version>

# Transfer to bastion, then push
skopeo copy \
  dir:./rhdh-must-gather-<version> \
  docker://<internal-registry>/rhdh/rhdh-must-gather:<version>
```

### Pull Helm chart for disconnected

```bash
helm pull redhat-developer-hub-must-gather --repo https://charts.openshift.io
```

### Kubernetes pull secret for internal registry

```bash
kubectl create secret docker-registry must-gather-pull-secret \
  --docker-server=<internal-registry> \
  --docker-username=<username> \
  --docker-password=<password> \
  -n rhdh-diagnostics
```

### Run with mirrored image

```bash
# OpenShift
oc adm must-gather --image=<internal-registry>/rhdh/rhdh-must-gather:<version>

# Kubernetes (partially disconnected)
helm upgrade --install my-rhdh-must-gather redhat-developer-hub-must-gather \
  --repo https://charts.openshift.io \
  --namespace rhdh-diagnostics \
  --create-namespace \
  --set image.registry=<internal-registry> \
  --set image.repository=rhdh/rhdh-must-gather \
  --set image.tag=<version> \
  --set imagePullSecrets[0].name=must-gather-pull-secret
```

---

## 4. Collectors

### Default-enabled

| Collector | Purpose | Disable flag |
|-----------|---------|--------------|
| platform | Cluster version and platform type | `--without-platform` |
| helm | Helm release information | `--without-helm` |
| operator | Operator logs and CRs | `--without-operator` |
| orchestrator | Orchestrator workflow data | `--without-orchestrator` |
| route-ingress | Routes (OCP) / Ingresses (K8s) | `--without-route` / `--without-ingress` |
| namespace-inspect | Namespace resources | `--without-namespace-inspect` |

### Opt-in

| Collector | Purpose | Enable flag |
|-----------|---------|-------------|
| cluster-info | Cluster-wide state (use only when support requests) | `--cluster-info` |
| heap-dumps | Node.js memory snapshots | `--with-heap-dumps` |

---

## 5. Heap Dump Collection

### Increase liveness probe — Operator

```yaml
apiVersion: rhdh.redhat.com/v1alpha1
kind: Backstage
metadata:
  name: my-rhdh
spec:
  deployment:
    patch:
      spec:
        template:
          spec:
            containers:
              - name: backstage-backend
                livenessProbe:
                  failureThreshold: 180
```

### Increase liveness probe — Helm

```yaml
upstream:
  backstage:
    livenessProbe:
      failureThreshold: 180
```

### SIGUSR2 method — Operator

```yaml
apiVersion: rhdh.redhat.com/v1alpha1
kind: Backstage
metadata:
  name: my-rhdh
spec:
  application:
    extraEnvs:
      - name: NODE_OPTIONS
        value: "--heapsnapshot-signal=SIGUSR2 --diagnostic-dir=/tmp"
```

### SIGUSR2 method — Helm

```yaml
upstream:
  backstage:
    extraEnvVars:
      - name: NODE_OPTIONS
        value: "--heapsnapshot-signal=SIGUSR2 --diagnostic-dir=/tmp"
```

### Collect with heap dumps

```bash
# OpenShift — inspector protocol (default)
oc adm must-gather \
  --image=registry.access.redhat.com/rhdh/rhdh-must-gather-rhel9:1.10 \
  -- /usr/bin/gather --with-heap-dumps

# OpenShift — SIGUSR2 method
oc adm must-gather \
  --image=registry.access.redhat.com/rhdh/rhdh-must-gather-rhel9:1.10 \
  -- /usr/bin/gather --with-heap-dumps --heap-dump-method sigusr2

# Kubernetes — inspector protocol
gather:
  heapDump:
    enabled: true
    method: "inspector"
```

### Increase heap dump timeout for large memory

```bash
# OpenShift
oc adm must-gather \
  --image=registry.access.redhat.com/rhdh/rhdh-must-gather-rhel9:1.10 \
  -- /usr/bin/env HEAP_DUMP_TIMEOUT=1800 /usr/bin/gather --with-heap-dumps

# Kubernetes
gather:
  heapDump:
    enabled: true
    timeout: "1800"
```

---

## 6. Command-Line Flags Reference

| Flag | Description | Default |
|------|-------------|---------|
| `--namespaces` | Comma-separated namespace list | All |
| `--cluster-info` | Include cluster-wide state | Not included |
| `--with-heap-dumps` | Collect heap snapshots | Not included |
| `--heap-dump-instances` | Specific RHDH instances for heap dumps | All |
| `--heap-dump-method` | `inspector` or `sigusr2` | `inspector` |
| `--without-operator` | Exclude Operator collector | Included |
| `--without-helm` | Exclude Helm collector | Included |
| `--without-orchestrator` | Exclude Orchestrator collector | Included |
| `--without-platform` | Exclude platform collector | Included |
| `--without-route` | Exclude OCP route collector | Included |
| `--without-ingress` | Exclude K8s ingress collector | Included |
| `--without-namespace-inspect` | Exclude namespace-inspect | Included |

---

## 7. Environment Variables Reference

| Variable | Description | Default | Helm Equivalent |
|----------|-------------|---------|-----------------|
| `LOG_LEVEL` | `debug`, `info`, `trace` | `info` | `gather.logLevel` |
| `CMD_TIMEOUT` | Command timeout (seconds) | `30` | `gather.cmdTimeout` |
| `MUST_GATHER_SINCE` | Relative time for logs (e.g., `1h`) | All logs | `gather.since` |
| `MUST_GATHER_SINCE_TIME` | Absolute RFC3339 timestamp | All logs | `gather.sinceTime` |
| `HEAP_DUMP_TIMEOUT` | Heap dump timeout per pod (seconds) | `600` | `gather.heapDump.timeout` |

---

## 8. Output Structure

### Top-level directories

| Path | Contents |
|------|----------|
| `version`, `must-gather.log` | Collection metadata |
| `sanitization-report.txt` | Data sanitization summary |
| `all-routes.txt` | All OCP routes cluster-wide |
| `all-ingresses.txt` | All K8s ingresses cluster-wide |
| `cluster-info/` | Cluster-wide info (opt-in) |
| `namespace-inspect/` | Deep namespace inspect data |
| `platform/` | Platform info |
| `helm/` | Helm deployment data |
| `orchestrator/` | Orchestrator data |
| `operator/` | Operator deployment data |

### Common diagnostic data locations

| Data | Location |
|------|----------|
| Backend pod logs | `namespace-inspect/namespaces/<ns>/pods/<pod>/backstage-backend/logs/current.log` |
| PostgreSQL config | `namespace-inspect/namespaces/<ns>/core/configmaps/<cm>.yaml` |
| Operator logs | `operator/ns=<ns>/logs.txt` |
| Backstage CR | `operator/backstage-crs/<cr>.yaml` |
| Routes/Ingresses | `all-routes.txt` or `all-ingresses.txt` |
| Helm release values | `helm/releases/ns=<ns>/<release>/values.yaml` |
| Deployment configs | `namespace-inspect/namespaces/<ns>/apps/deployments/<deploy>.yaml` |
| Platform/cluster version | `platform/platform.json` or `platform/platform.txt` |

### Heap dump file locations

- Helm releases: `helm/releases/ns=<ns>/<release>/deployment/heap-dumps/...`
- Helm standalone: `helm/standalone/ns=<ns>/<name>/deployment/heap-dumps/...`
- Operator: `operator/backstage-crs/ns=<ns>/<cr>/deployment/heap-dumps/...`

Analyze with Chrome DevTools, Node.js heap analysis tools, or memory profilers.
