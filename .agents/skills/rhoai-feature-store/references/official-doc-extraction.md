# Official Documentation Extraction

This extraction summarizes the official Red Hat OpenShift AI 3.4 Feature Store
guide for reusable project work. Re-check the source guide when the active
baseline changes.

## Concept Model

- A machine learning feature is an input signal or measurable attribute used by
  a predictive model.
- Feature engineering transforms raw data into features suitable for training
  and inference.
- Feature Store is a Red Hat OpenShift AI component, based on Feast, that
  centralizes feature storage, management, and serving.
- Feature Store supports reuse across teams by registering curated features and
  serving them consistently for offline training and online inference.

## Personas

- ML platform and MLOps teams deploy and operate the feature platform.
- Data scientists define, store, and retrieve features for development and
  model deployment.
- Data engineers manage feature definitions, catalogs, and backing data stores.
- AI engineers integrate richer feature data into AI applications and model
  workflows.

## Key Components

| Component | Official role |
|-----------|---------------|
| Registry | Catalog of feature definitions and metadata; supports apply, list, retrieve, and delete operations |
| Offline store | Historical time-series feature data for training, batch scoring, and materialization |
| Online store | Low-latency feature retrieval for real-time inference |
| Online feature server | HTTP/JSON endpoint for online feature access |
| Offline feature server | Apache Arrow Flight/gRPC endpoint wrapping offline-store calls |
| Registry server | gRPC server for registry access |
| UI | Dashboard access for Feature Store discovery and workbench integration |
| Python SDK | Define feature repositories and read/write feature values |
| CLI | `feast` commands for managing repositories and deployments |

## Enablement Workflow

1. Install OpenShift AI.
2. Enable the Feature Store component in the `DataScienceCluster`:

   ```yaml
   spec:
     components:
       feastoperator:
         managementState: Managed
   ```

3. Verify the Feast Operator controller manager pod in
   `redhat-ods-applications`.
4. Create the target data science project.
5. Create a `FeatureStore` custom resource in the project.
6. Configure data stores, registry, auth, UI, and feature repository source.
7. Give users access through project permissions, RBAC, OIDC, or workbench
   configuration as appropriate.

## Core FeatureStore Resource

Official examples use:

```yaml
apiVersion: feast.dev/v1
kind: FeatureStore
metadata:
  name: sample
  labels:
    feature-store-ui: enabled
spec:
  feastProject: my_feast_project
```

Important details:

- `metadata.name` drives the `feast-<name>` pod naming pattern.
- `spec.feastProject` is the Feast project namespace, not the OpenShift
  project.
- Creating a minimal `FeatureStore` starts a remote online feature server and
  uses the local provider defaults.
- Local provider defaults include a SQL or local-file registry, Parquet-backed
  offline store, and SQLite online store.
- `feature-store-ui: enabled` is required when the instance should appear in
  Feature Store UI workflows.

## Feature Repository From Git

The guide shows `spec.feastProjectDir.git` for loading a feature repository:

```yaml
apiVersion: feast.dev/v1
kind: FeatureStore
metadata:
  name: sample-git
  labels:
    feature-store-ui: enabled
spec:
  feastProject: credit_scoring_local
  feastProjectDir:
    git:
      url: https://github.com/feast-dev/feast-credit-score-local-tutorial
      ref: 598a270
  services:
    registry:
      local:
        server:
          restAPI: true
```

For this repo, replace public tutorial repositories with reviewed demo
repositories or custom images once active GitOps implementation exists.

## Stores And Persistence

Offline stores:

- Used for training datasets, batch scoring, and materialization into online
  stores.
- Only one offline store is used at a time.
- Examples include Dask, Snowflake, BigQuery, Redshift, and DuckDB.

Online stores:

- Used for low-latency inference-time retrieval.
- Examples include Redis, PostgreSQL, MongoDB, Cassandra, ScyllaDB, GCP
  Datastore, and DynamoDB depending on provider support.
- Official examples configure PostgreSQL through
  `services.onlineStore.persistence.store.type: postgres` and a `secretRef`.

Registry:

- Minimal configurations use SQLite or local files.
- Production-style configurations should use SQL-backed registry persistence.
- S3, GCS, SQL, Snowflake, and local registry options are referenced.
- Registry REST API can be enabled with
  `services.registry.local.server.restAPI: true`.

PVCs:

- Official examples attach PVC-backed file persistence to online store, offline
  store, and registry paths.
- File-backed PVC examples are useful for development but not for multi-replica
  serving.

## Scaling And Availability

- Single replica is the default and is limited for production.
- Static replicas can be set with `spec.replicas`.
- HPA can be configured with `services.scaling.autoscaling`.
- Static replicas and autoscaling require database-backed persistence for all
  enabled services.
- File-backed SQLite, DuckDB, and local `registry.db` storage must not be used
  with multiple replicas.
- HPA is mutually exclusive with `spec.replicas > 1`.
- The Operator owns created HPA and PDB resources and removes them when the
  scaling configuration is removed.
- When scaling is enabled, the Operator adds soft pod anti-affinity and
  topology spread constraints.

## Monitoring And Performance

- Metrics are enabled for the online store server with:

  ```yaml
  services:
    onlineStore:
      server:
        metrics: true
  ```

- When Prometheus Operator APIs are available, the Operator creates service
  monitor resources for metric discovery.
- Feature Store exposes metrics for CPU, memory, request count, request
  latency, online-store reads, transformations, pushes, materialization, and
  freshness.
- Worker settings live under `services.onlineStore.server.workerConfigs` and
  include `workers`, `workerConnections`, `maxRequests`,
  `maxRequestsJitter`, `keepAliveTimeout`, and `registryTTLSeconds`.
- Connection budgets must account for replicas, workers per pod, and backend
  store connection limits.

## Registry Cache

- `registryTTLSeconds` in the `FeatureStore` CR controls how often the online
  server refreshes its registry cache.
- SQL-backed registry secrets can include cache settings such as `cache_mode`
  and `cache_ttl_seconds`.
- Longer cache TTLs reduce latency and backend load; shorter TTLs improve
  freshness when schema changes frequently.

## On-Demand Feature View Optimization

- Use `mode="python"` for production online serving unless pandas-specific
  behavior is required.
- `mode="pandas"` is higher latency and limited to offline batch retrieval.
- Use `singleton=True` for one-entity online requests when the transformation
  uses `mode="python"`.
- `write_to_online_store=True` can remove read-path transformation latency but
  introduces freshness dependence on materialization cadence.

## Auth And Access

- `feature_store.yaml` supports auth values such as `no_auth`, `kubernetes`,
  and `oidc`.
- Kubernetes authorization is configured in the `FeatureStore` auth section and
  combined with project permissions and config maps.
- Workbench Feature Store selection displays only instances the user is
  authorized to access.
- The Red Hat guide states that group-based and namespace/data-science-project
  authorization policies are supported; upstream role-based policies are not
  supported in this context.
- OIDC authorization can use:

  ```yaml
  spec:
    authz:
      oidc: {}
  ```

- If the provider is outside the Gateway API integration, specify `issuerUrl`.
- If client-role access is needed, reference a Secret containing `client_id`
  through `authz.oidc.secretRef`.

## Workbench Integration

- Workbenches can connect to one or more authorized Feature Store instances
  during create or edit flows.
- Feature Store configuration files are mounted into the workbench.
- The guide references a mounted configuration path and `FeatureStore` Python
  object initialization through `fs_yaml_file`.
- Feast SDK is available in all workbench images except minimal.
- User access depends on project permissions and valid auth tokens.

## Feature Definitions

- Define Feature Store objects with the Feast Python SDK.
- Specify batch data sources for offline stores and online backends for
  inference use cases.
- Organize related features with entities, which act like primary keys for
  feature retrieval.
- Define feature views with schema, source, TTL, and transformation behavior.
- Choose data types based on backend support and performance.
- Supported data type categories include primitive, array, JSON, map, set, and
  struct types.

## Retrieval

- `get_historical_features()` retrieves point-in-time training datasets.
- `get_online_features()` retrieves low-latency online features for inference.
- Client configuration must be complete before retrieval from a workbench.
- Materialization loads features into the online store for serving.

## Compute Engines

- Compute engines execute materialization and historical retrieval tasks.
- Supported engine families include Spark, Ray, and local execution.
- Ray supports distributed transformations, joins, aggregations, and
  materialization.
- Configure Ray in `feature_store.yaml` with `batch_engine.type: ray.engine`.
- Ray execution mode detection order is environment variables, `kuberay_conf`,
  `ray_address`, then local mode.
- The guide recommends KubeRay mode when using Ray.
- Spark is positioned for large-scale materialization tasks.

## CLI

- The `feast` CLI is bundled with the Feature Store Python package and can run
  in a workbench.
- General form:

  ```bash
  feast [OPTIONS] COMMAND [ARGS]...
  ```

- Common commands include `apply`, `configuration`, `delete`, `entities`,
  `feature-views`, `init`, `materialize`, `materialize-incremental`,
  `registry-dump`, `teardown`, and `version`.
- `feast apply` validates feature definitions, synchronizes metadata, and
  provisions required infrastructure for the selected provider.

## Disconnected Environments

- External Git clone and init-container behavior must be avoided when the
  cluster cannot reach external repositories.
- The guide uses `services.disableInitContainers: true` for disconnected
  patterns.
- Custom service images can be set through per-service `image` fields and
  `imagePullPolicy: IfNotPresent`.
- Registry population should happen through controlled CI/CD or the Operator
  CronJob when init containers are disabled.
