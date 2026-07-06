# Feature Store Patterns

These examples are snippets for skill use and review. They are not active
GitOps manifests until copied into the clean-slate implementation with project
names, secrets, and validation.

## Enable Feature Store In DataScienceCluster

```yaml
spec:
  components:
    feastoperator:
      managementState: Managed
```

Review points:

- Apply through the active RHOAI GitOps application when implementation exists.
- Verify the Feast Operator controller manager in `redhat-ods-applications`.

## Minimal Project FeatureStore

```yaml
apiVersion: feast.dev/v1
kind: FeatureStore
metadata:
  name: demo-feature-store
  labels:
    feature-store-ui: enabled
spec:
  feastProject: demo_features
```

Review points:

- `feastProject` is the Feast project namespace, not the OpenShift project.
- Use this shape for a first development instance only.
- Do not scale this shape above one replica without database-backed stores.

## Feature Repository From Git

```yaml
apiVersion: feast.dev/v1
kind: FeatureStore
metadata:
  name: demo-feature-store
  labels:
    feature-store-ui: enabled
spec:
  feastProject: demo_features
  feastProjectDir:
    git:
      url: https://example.com/your-reviewed-feature-repo.git
      ref: main
  services:
    registry:
      local:
        server:
          restAPI: true
```

Review points:

- Replace the URL and ref with a reviewed demo repository or internal source.
- Pin a commit or stable release ref for repeatable demos when possible.
- Avoid external Git access for disconnected environments.

## PostgreSQL-Backed Online Store

```yaml
apiVersion: feast.dev/v1
kind: FeatureStore
metadata:
  name: postgres-online-feature-store
  labels:
    feature-store-ui: enabled
spec:
  feastProject: demo_features
  services:
    onlineStore:
      persistence:
        store:
          type: postgres
          secretRef:
            name: feature-store-online-store
```

Review points:

- `feature-store-online-store` must already exist in the namespace.
- Keep connection details in the Secret, not the GitOps manifest.
- Size connection pools for replica and worker counts before scaling.

## Production-Style Scaling Fragment

```yaml
spec:
  feastProject: demo_features
  services:
    scaling:
      autoscaling:
        minReplicas: 2
        maxReplicas: 10
        metrics:
        - type: Resource
          resource:
            name: cpu
            target:
              type: Utilization
              averageUtilization: 70
    podDisruptionBudgets:
      maxUnavailable: 1
    onlineStore:
      persistence:
        store:
          type: redis
          secretRef:
            name: feature-store-online-store
      server:
        metrics: true
        workerConfigs:
          workers: 4
          registryTTLSeconds: 300
    registry:
      local:
        persistence:
          store:
            type: sql
            secretRef:
              name: feature-store-registry
```

Review points:

- Use database-backed persistence for every enabled service before enabling
  HPA.
- Do not set `spec.replicas > 1` together with HPA.
- Set exactly one PDB availability field.

## OIDC Authorization Fragment

```yaml
spec:
  feastProject: demo_features
  authz:
    oidc: {}
```

External issuer example:

```yaml
spec:
  authz:
    oidc:
      issuerUrl: https://keycloak.example.com/realms/demo
      secretRef:
        name: feast-oidc-secret
```

Review points:

- Use empty `oidc: {}` only when the platform Gateway API provides OIDC
  configuration.
- Put client IDs in a Secret and reference the Secret.
- Verify the `Authorization` status condition after applying.

## Ray Compute Engine In feature_store.yaml

```yaml
project: demo_features
registry: data/registry.db
provider: local
offline_store:
  type: ray
  storage_path: data/ray_storage
batch_engine:
  type: ray.engine
  max_workers: 4
  broadcast_join_threshold_mb: 100
  max_parallelism_multiplier: 2
  target_partition_size_mb: 64
  window_size_for_joins: "1H"
  ray_address: localhost
```

Review points:

- Prefer KubeRay mode on OpenShift when available.
- Use Ray for distributed materialization and historical retrieval, not as a
  default lightweight path.
- Pair active Ray usage with the distributed workload skills.

## Workbench Access Smoke Test

```python
from feast import FeatureStore

fs = FeatureStore(fs_yaml_file="/opt/app-root/src/feast-config/demo_features.yaml")
fs.list_feature_views()
```

Review points:

- Use the mounted configuration path from the active workbench.
- Confirm the user can see only authorized Feature Store instances in the
  dashboard selection flow.
- Use `get_historical_features()` for training datasets and
  `get_online_features()` for inference-time retrieval.

## CLI Checks

```bash
feast --help
feast apply
feast feature-views list
feast entities list
feast materialize-incremental "$(date -u +%Y-%m-%dT%H:%M:%SZ)"
feast version
```

Review points:

- Run CLI commands from a workbench or controlled automation with the correct
  feature repository context.
- Treat `feast apply` as a mutating operation.
- Use read/list commands for smoke tests when validating access.
