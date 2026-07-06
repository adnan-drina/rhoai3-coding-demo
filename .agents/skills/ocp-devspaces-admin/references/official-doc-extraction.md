# Official Doc Extraction

Use this extraction to keep Dev Spaces administration content grounded in the
official Red Hat OpenShift Dev Spaces 3.28 Administration Guide. When
implementation needs exact CheCluster CR fields, storage configuration, RBAC,
networking, or monitoring setup, verify against the official documentation and
the active cluster schema before authoring manifests.

## CheCluster Custom Resource

### Minimal CR

```yaml
apiVersion: org.eclipse.che/v2
kind: CheCluster
metadata:
  name: devspaces
  namespace: openshift-devspaces
spec:
  components: {}
  devEnvironments: {}
  networking: {}
```

### Editing the CR

```bash
# Interactive edit
oc edit checluster/devspaces -n openshift-devspaces

# Patch a specific field
oc patch checluster/devspaces -n openshift-devspaces \
  --type='merge' -p '{"spec":{"devEnvironments":{"maxNumberOfWorkspacesPerUser": 5}}}'

# Verify a configured property
oc get configmap che -o jsonpath='{.data.<configured_property>}' \
  -n openshift-devspaces
```

### Key spec.devEnvironments Fields

| Field | Description | Default |
|-------|-------------|---------|
| `maxNumberOfWorkspacesPerUser` | Total workspaces (stopped+running) per user | -1 (unlimited) |
| `maxNumberOfRunningWorkspacesPerUser` | Concurrent running workspaces per user | 1 |
| `maxNumberOfRunningWorkspacesPerCluster` | Cluster-wide concurrent running limit | -1 (unlimited) |
| `defaultEditor` | Default editor (plugin ID or URI) | — |
| `defaultNamespace.template` | Namespace name template | `<username>-che` |
| `defaultNamespace.autoProvision` | Auto-create user namespaces | true |
| `deploymentStrategy` | Workspace pod deployment strategy | `Recreate` |
| `imagePullPolicy` | Image pull policy for workspace containers | — |
| `containerResourceCaps` | Max resource limits enforced on containers | — |
| `defaultContainerResources` | Default resources for unspecified containers | — |
| `disableContainerBuildCapabilities` | Disable container build capabilities | false |
| `disableContainerRunCapabilities` | Disable container run capabilities | true |
| `persistUserHome.enabled` | Persist `/home/user` across restarts | true |
| `ignoredUnrecoverableEvents` | K8s events to ignore during startup | `["FailedScheduling"]` |
| `nodeSelector` | Node selector for workspace pods | — |

### Key spec.components Fields

| Field | Description |
|-------|-------------|
| `cheServer.clusterRoles` | ClusterRoles delegated to the che service account |
| `cheServer.extraProperties` | Extra env vars for the che server (e.g., `CHE_LOGGER_CONFIG`) |
| `cheServer.proxy` | Proxy configuration (url, port, nonProxyHosts, credentialsSecretName) |
| `metrics.enable` | Enable JVM metrics on port 8087 |
| `dashboard` | Dashboard component configuration |
| `pluginRegistry` | Plugin registry component configuration |
| `devfileRegistry` | Devfile registry component configuration |
| `imagePuller` | Kubernetes Image Puller configuration |

### Key spec.networking Fields

| Field | Description |
|-------|-------------|
| `hostname` | Custom hostname for Dev Spaces |
| `tlsSecretName` | TLS secret for the Dev Spaces route |
| `domain` | DNS domain for Router Sharding |
| `labels` | Labels for route filtering (Router Sharding) |
| `annotations` | Annotations on routes |
| `auth.advancedAuthorization` | Allow/deny users and groups |

## Storage Configuration

### Storage Strategies

```yaml
spec:
  devEnvironments:
    storage:
      pvc:
        pvcStrategy: 'per-user'       # or 'per-workspace' or 'ephemeral'
```

- **per-user**: single PVC shared across all user workspaces; requires
  ReadWriteMany (RWX); default size 10Gi
- **per-workspace**: each workspace gets its own PVC; default size 5Gi
- **ephemeral**: no persistent storage; local changes lost on stop

All workspace storage must use `volumeMode: FileSystem`.

### Storage Classes and Sizes

```yaml
spec:
  devEnvironments:
    storage:
      perUserStrategyPvcConfig:
        claimSize: 10Gi
        storageClass: my-rwx-storage-class
      perWorkspaceStrategyPvcConfig:
        claimSize: 5Gi
        storageClass: my-rwo-storage-class
      pvcStrategy: per-user
```

Verification:

```bash
# Check PVC storage class
oc get pvc -n <user_namespace> -o jsonpath='{.items[*].spec.storageClassName}'

# Check PVC size
oc get pvc -n <user_namespace> -o jsonpath='{.items[*].spec.resources.requests.storage}'

# Verify storage strategy
oc get checluster devspaces -n openshift-devspaces \
  -o jsonpath='{.spec.devEnvironments.storage.pvc.pvcStrategy}'
```

### Per-User Storage Backend Considerations

Generic NFS supports RWX but has limitations:
- Quota enforcement: Kubernetes PVCs cannot reliably enforce quotas on generic
  NFS volumes
- Data integrity: generic NFS may lack locking and cache coherency for
  concurrent multi-node access

Use a certified clustered or managed storage solution with a CSI driver that
enforces quota limits and provides high-performance RWX file access.

### Persistent User Home

Enabled by default. Creates a PVC mounted at `/home/user` for the tools
container. To disable:

```yaml
spec:
  devEnvironments:
    persistUserHome:
      enabled: false
```

## Workspace Limits and Quotas

### Limit Workspaces Per User

```bash
oc patch checluster/devspaces -n openshift-devspaces \
  --type='merge' -p \
  '{"spec":{"devEnvironments":{"maxNumberOfWorkspacesPerUser": 5}}}'

# Verify
oc get checluster devspaces -n openshift-devspaces \
  -o jsonpath='{.spec.devEnvironments.maxNumberOfWorkspacesPerUser}'
```

### Limit Cluster-Wide Running Workspaces

```bash
oc patch checluster/devspaces -n openshift-devspaces \
  --type='merge' -p \
  '{"spec":{"devEnvironments":{"maxNumberOfRunningWorkspacesPerCluster": 50}}}'

# Verify
oc get checluster devspaces -n openshift-devspaces \
  -o jsonpath='{.spec.devEnvironments.maxNumberOfRunningWorkspacesPerCluster}'
```

### Enable Multiple Concurrent Workspaces Per User

```bash
oc patch checluster/devspaces -n openshift-devspaces \
  --type='merge' -p \
  '{"spec":{"devEnvironments":{"maxNumberOfRunningWorkspacesPerUser": -1}}}'
```

Note: with `per-user` storage and multi-node clusters, concurrent workspaces
may experience issues if pods are distributed across nodes.

### Override Default Memory Limit

```yaml
spec:
  components:
    cheServer:
      extraProperties:
        CHE_WORKSPACE_DEFAULT__MEMORY__LIMIT__MB: "4096"
```

## Project and Namespace Configuration

### Configure Namespace Template

```yaml
spec:
  devEnvironments:
    defaultNamespace:
      template: <username>-devspaces
```

Template placeholders:
- `<username>` — the user's name
- `<userid>` — 14-character user ID with 6-character random suffix

OpenShift limits namespace length to 49 characters.

### Disable Auto-Provisioning

```yaml
spec:
  devEnvironments:
    defaultNamespace:
      autoProvision: false
```

With auto-provisioning disabled, administrators must manually create namespaces
for each user.

### Pre-Provision Namespaces

Label pre-provisioned namespaces so Dev Spaces recognizes them:

```bash
oc label namespace <namespace> \
  app.kubernetes.io/component=workspaces-namespace \
  app.kubernetes.io/part-of=che.eclipse.org
```

## Identity, RBAC, and Authorization

### Default RBAC

The Operator creates two ClusterRoles:
- `<namespace>-cheworkspaces-clusterrole`
- `<namespace>-cheworkspaces-devworkspace-clusterrole`

RoleBindings are created in `<username>-devspaces` on first user access.

Default user permissions in their namespace include: pods (CRUD), pods/exec,
pods/log, configmaps, secrets, services, routes, PVCs, deployments,
replicasets, devworkspace, devworkspacetemplates.

### Add Custom Cluster Roles

```bash
# Create the ClusterRole
oc apply -f - <<EOF
kind: ClusterRole
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: custom-devspaces-role
  labels:
    app.kubernetes.io/part-of: che.eclipse.org
rules:
  - verbs: ["get", "list"]
    apiGroups: [""]
    resources: ["nodes"]
EOF

# Bind to the Operator service account
oc apply -f - <<EOF
kind: ClusterRoleBinding
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: custom-devspaces-role
  labels:
    app.kubernetes.io/part-of: che.eclipse.org
subjects:
  - kind: ServiceAccount
    name: devspaces-operator
    namespace: openshift-devspaces
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: custom-devspaces-role
EOF

# Delegate to che service account
oc patch checluster devspaces \
  --patch '{"spec": {"components": {"cheServer": {"clusterRoles": ["custom-devspaces-role"]}}}}' \
  --type=merge -n openshift-devspaces

# Delegate to users
oc patch checluster devspaces \
  --patch '{"spec": {"devEnvironments": {"user": {"clusterRoles": ["custom-devspaces-role"]}}}}' \
  --type=merge -n openshift-devspaces
```

### Advanced Authorization (Allow/Deny Users and Groups)

```yaml
spec:
  networking:
    auth:
      advancedAuthorization:
        allowUsers:
          - user1
          - user2
        allowGroups:
          - devspaces-users
        denyUsers:
          - blocked-user
        denyGroups:
          - external-contractors
```

Evaluation order: denyUsers/denyGroups take precedence over
allowUsers/allowGroups.

### GDPR User Data Removal

Use the Dev Spaces server API to remove user data for GDPR compliance. The
server provides an endpoint for administrators to delete user-specific data.

## Networking Configuration

### Custom Hostname

```yaml
spec:
  networking:
    hostname: devspaces.example.com
```

### TLS Secret

```yaml
spec:
  networking:
    tlsSecretName: devspaces-tls
```

### Import Untrusted TLS Certificates

```bash
# Concatenate CA chain PEM files
cat ca-cert-for-devspaces-*.pem | tr -d '\r' > custom-ca-certificates.pem

# Create ConfigMap
oc create configmap custom-ca-certificates \
  --from-file=custom-ca-certificates.pem \
  --namespace=openshift-devspaces

# Label it for Dev Spaces CA bundle
oc label configmap custom-ca-certificates \
  app.kubernetes.io/component=ca-bundle \
  app.kubernetes.io/part-of=che.eclipse.org \
  --namespace=openshift-devspaces
```

On OpenShift, the Operator automatically adds RHCOS trust bundle into mounted
certificates.

Verification:

```bash
# Check CA bundle ConfigMap
oc get configmap \
  --namespace=openshift-devspaces \
  --output='jsonpath={.items[0:].data.custom-ca-certificates\.pem}' \
  --selector=app.kubernetes.io/component=ca-bundle,app.kubernetes.io/part-of=che.eclipse.org

# Check server logs for imported certificates
oc logs deploy/devspaces --namespace=openshift-devspaces | grep tls-ca-bundle.pem
```

### Network Policies

Required NetworkPolicies for the `openshift-devspaces` namespace:

```yaml
# Allow from OpenShift API server to webhook
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-openshift-apiserver
  namespace: openshift-devspaces
spec:
  podSelector:
    matchLabels:
      app.kubernetes.io/name: devworkspace-webhook-server
  ingress:
    - from:
        - podSelector: {}
          namespaceSelector:
            matchLabels:
              kubernetes.io/metadata.name: openshift-apiserver
  policyTypes:
    - Ingress
```

```yaml
# Allow from workspace namespaces
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-from-workspaces-namespaces
  namespace: openshift-devspaces
spec:
  podSelector: {}
  ingress:
    - from:
        - podSelector: {}
          namespaceSelector:
            matchLabels:
              app.kubernetes.io/component: workspaces-namespace
  policyTypes:
    - Ingress
```

### Router Sharding

```yaml
spec:
  networking:
    labels:
      router: devspaces
    domain: devspaces.apps.example.com
    annotations:
      route.openshift.io/termination: edge
```

### Proxy Configuration

On OpenShift, the Operator automatically uses the cluster-wide proxy. To
override:

```bash
# Create proxy credentials secret
oc apply -f - <<EOF
kind: Secret
apiVersion: v1
metadata:
  name: devspaces-proxy-credentials
  namespace: openshift-devspaces
  labels:
    app.kubernetes.io/part-of: che.eclipse.org
type: Opaque
stringData:
  user: proxy-user
  password: proxy-pass
EOF

# Patch CheCluster with proxy settings
oc patch checluster/devspaces \
  --namespace openshift-devspaces \
  --type='merge' -p \
  '{"spec":{"components":{"cheServer":{"proxy":{"credentialsSecretName":"devspaces-proxy-credentials","nonProxyHosts":[".svc","localhost"],"port":"3128","url":"http://proxy.example.com"}}}}}'
```

## Monitoring and Observability

### Dev Workspace Operator Metrics

Exposed on port 8443 at `/metrics` on the
`devworkspace-controller-metrics` Service.

| Metric | Type | Description |
|--------|------|-------------|
| `devworkspace_started_total` | Counter | Dev Workspace starting events |
| `devworkspace_started_success_total` | Counter | Successful starts (Running phase) |
| `devworkspace_fail_total` | Counter | Failed Dev Workspaces |
| `devworkspace_startup_time` | Histogram | Startup time in seconds |

Labels: `source` (devworkspace-source label), `routingclass`
(basic/cluster/cluster-tls/web-terminal), `reason` (BadRequest/
InfrastructureFailure/Unknown).

### ServiceMonitor for Dev Workspace Operator

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: devworkspace-controller
  namespace: openshift-devspaces
spec:
  endpoints:
    - bearerTokenFile: /var/run/secrets/kubernetes.io/serviceaccount/token
      interval: 10s
      port: metrics
      scheme: https
      tlsConfig:
        insecureSkipVerify: true
  namespaceSelector:
    matchNames:
      - openshift-operators
  selector:
    matchLabels:
      app.kubernetes.io/name: devworkspace-controller
```

```bash
# Enable namespace monitoring for Prometheus
oc label namespace openshift-devspaces openshift.io/cluster-monitoring=true
```

### Dev Spaces Server JVM Metrics

Enable via CheCluster CR:

```yaml
spec:
  components:
    metrics:
      enable: true
```

Exposed on port 8087 of the `che-host` Service. Includes JVM memory, class
loading, garbage collection, and buffer pool metrics.

### ServiceMonitor for Server JVM Metrics

```yaml
apiVersion: monitoring.coreos.com/v1
kind: ServiceMonitor
metadata:
  name: che-host
  namespace: openshift-devspaces
spec:
  endpoints:
    - interval: 10s
      port: metrics
      scheme: http
  namespaceSelector:
    matchNames:
      - openshift-devspaces
  selector:
    matchLabels:
      app.kubernetes.io/name: devspaces
```

Requires a Role and RoleBinding for `prometheus-k8s` service account:

```yaml
kind: Role
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: prometheus-k8s
  namespace: openshift-devspaces
rules:
  - verbs: ["get", "list", "watch"]
    apiGroups: [""]
    resources: ["services", "endpoints", "pods"]
---
kind: RoleBinding
apiVersion: rbac.authorization.k8s.io/v1
metadata:
  name: view-devspaces-openshift-monitoring-prometheus-k8s
  namespace: openshift-devspaces
subjects:
  - kind: ServiceAccount
    name: prometheus-k8s
    namespace: openshift-monitoring
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: Role
  name: prometheus-k8s
```

### Server Logging

Configure individual logger levels:

```yaml
spec:
  components:
    cheServer:
      extraProperties:
        CHE_LOGGER_CONFIG: "org.eclipse.che.api.workspace.server.WorkspaceManager=DEBUG"
```

Log HTTP traffic between server and API server:

```yaml
spec:
  components:
    cheServer:
      extraProperties:
        CHE_LOGGER_CONFIG: "che.infra.request-logging=TRACE"
```

### Web Console Dashboards

Dev Workspace Operator dashboard:

```bash
oc create configmap grafana-dashboard-dwo \
  --from-literal=dwo-dashboard.json="$(curl https://raw.githubusercontent.com/devfile/devworkspace-operator/main/docs/grafana/openshift-console-dashboard.json)" \
  -n openshift-config-managed

oc label configmap grafana-dashboard-dwo console.openshift.io/dashboard=true \
  -n openshift-config-managed
```

Dev Spaces Server JVM dashboard:

```bash
oc create configmap grafana-dashboard-devspaces-server \
  --from-literal=devspaces-server-dashboard.json="$(curl https://raw.githubusercontent.com/eclipse-che/che-server/main/docs/grafana/openshift-console-dashboard.json)" \
  -n openshift-config-managed

oc label configmap grafana-dashboard-devspaces-server console.openshift.io/dashboard=true \
  -n openshift-config-managed
```

## Server Component Configuration

### Mount Secret or ConfigMap as File

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: custom-data
  namespace: openshift-devspaces
  annotations:
    che.eclipse.org/mount-as: file
    che.eclipse.org/mount-path: /data
  labels:
    app.kubernetes.io/part-of: che.eclipse.org
    app.kubernetes.io/component: devspaces-secret
data:
  ca.crt: <base64-encoded-data>
```

Target deployments for the component label:
- `devspaces-secret` or `devspaces-configmap`
- `devspaces-dashboard-secret` or `devspaces-dashboard-configmap`
- `devfile-registry-secret` or `devfile-registry-configmap`
- `plugin-registry-secret` or `plugin-registry-configmap`

### Mount as Environment Variable

```yaml
apiVersion: v1
kind: Secret
metadata:
  name: custom-env
  namespace: openshift-devspaces
  annotations:
    che.eclipse.org/mount-as: env
  labels:
    app.kubernetes.io/part-of: che.eclipse.org
    app.kubernetes.io/component: devspaces-secret
stringData:
  MY_ENV_VAR: my-value
```

## Autoscaling

### HPA for Dev Spaces Operands

```yaml
apiVersion: autoscaling/v2
kind: HorizontalPodAutoscaler
metadata:
  name: devspaces-scaler
  namespace: openshift-devspaces
spec:
  scaleTargetRef:
    apiVersion: apps/v1
    kind: Deployment
    name: devspaces
  minReplicas: 2
  maxReplicas: 5
  metrics:
    - type: Resource
      resource:
        name: cpu
        target:
          type: Utilization
          averageUtilization: 75
```

Eligible deployments: `devspaces`, `che-gateway`, `devspaces-dashboard`,
`plugin-registry`, `devfile-registry`.

### Machine Autoscaler Integration

Set workspace startup timeout and pod annotations to handle autoscaler node
additions. Configure `startTimeoutSeconds` in the CheCluster CR. Add
`cluster-autoscaler.kubernetes.io/safe-to-evict: "false"` annotation to
workspace pods to prevent eviction during scale-down.

## Troubleshooting

### Workspace Startup Failure Error Messages

| Error | Resolution |
|-------|-----------|
| `FailedScheduling: insufficient cpu/memory` | Free resources or add nodes |
| `unbound immediate PersistentVolumeClaims` | Verify StorageClass and available PVs |
| `node(s) didn't match Pod's node affinity/selector` | Check nodeSelector in CheCluster CR |
| `ErrImagePull` / `ImagePullBackOff` | Verify image name, existence, and pull secrets |
| `x509: certificate signed by unknown authority` | Import registry CA certificate |
| `DevWorkspace timed out` | Increase `startTimeoutSeconds` or investigate pod events |
| `admission webhook denied the request` | Check DevWorkspace Operator webhook status |
| `resource quota exceeded` | Increase ResourceQuota or reduce workspace resource requests |

### OAuth Configuration Errors

- OAuth application errors: verify callback URL, client ID, and client secret
  match the Git provider configuration
- Token refresh errors: force a refresh of the personal access token using
  `oc delete secret` for the user's token secret in their namespace

### Diagnostic Commands

```bash
# Check CheCluster status
oc get checluster devspaces -n openshift-devspaces -o yaml

# Check Dev Spaces server logs
oc logs deploy/devspaces -n openshift-devspaces

# Check DevWorkspace Operator logs
oc logs deploy/devworkspace-controller-manager -n openshift-operators

# Check workspace pod events
oc get events -n <user_namespace> --sort-by='.lastTimestamp'

# Check DevWorkspace status
oc get devworkspace -n <user_namespace> -o yaml

# Verify metrics endpoint
oc get service che-host -n openshift-devspaces \
  -o jsonpath='{.spec.ports[?(@.port==8087)]}'

# Collect logs with dsc
dsc server:logs
```
