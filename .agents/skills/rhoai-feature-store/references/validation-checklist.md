# Validation Checklist

Use this checklist before accepting Feature Store GitOps, documentation, or
runbook changes.

## Source And Scope

- The work references the active baseline in `docs/PLATFORM_BASELINE.md`.
- The official guide URL uses the active `/3.4/` baseline path.
- The change is about Feature Store, not KServe serving, AI Pipelines, MLflow,
  Model Registry, or generic workbench behavior.
- Upstream Feast examples are marked as supplemental when used.
- Any fields not captured from the official guide are backed by a schema check
  such as `oc explain featurestore.spec`.

## Component Enablement

- `DataScienceCluster.spec.components.feastoperator.managementState` is
  `Managed` when Feature Store is enabled.
- Feast Operator controller manager status is verified in
  `redhat-ods-applications`.
- The target OpenShift project exists before the `FeatureStore` resource is
  created.
- Active GitOps applies the RHOAI component and project resources through Argo
  CD once the clean-slate implementation exists.

## FeatureStore Resource Review

- `apiVersion` is `feast.dev/v1`.
- `kind` is `FeatureStore`.
- `metadata.name` is stable and DNS-safe.
- `spec.feastProject` is present and treated as the Feast project namespace.
- `feature-store-ui: enabled` is present only when UI or workbench selection is
  required.
- Public tutorial Git repositories are not used as active demo dependencies
  unless they are intentionally documented as temporary examples.
- `services.registry.local.server.restAPI: true` is set when REST registry
  access is required.
- No real credentials or connection strings are committed.

## Persistence And Scaling

- Online store, offline store, and registry choices match the intended use
  case.
- Database or object-storage backing services exist before the resource points
  to them.
- Multi-replica serving uses database-backed persistence for all enabled
  services.
- SQLite, DuckDB, and local `registry.db` file storage are not used with
  `spec.replicas > 1` or HPA.
- HPA configuration uses `services.scaling.autoscaling`.
- HPA is not combined with `spec.replicas > 1`.
- PodDisruptionBudget configuration uses exactly one of `minAvailable` or
  `maxUnavailable`.
- Worker settings account for backend connection capacity and replica count.

## Auth And Access

- Kubernetes or OIDC authorization is selected intentionally.
- OIDC configuration is used only after the cluster-level OIDC or Gateway API
  prerequisites are documented.
- OIDC client IDs are stored in Secrets, not plain manifests.
- Workbench visibility is validated with a user that should see the instance
  and a user that should not.
- Group and namespace/data-science-project authorization policies are preferred
  over unsupported upstream role policy assumptions.
- Feature Store client ConfigMaps are present and labeled for client use when
  workbench integration is documented.

## Workbench And Feature Definition Review

- Workbench examples use a non-minimal image that includes the Feast SDK.
- Mounted Feature Store configuration paths are documented.
- Feature definitions include data sources, entities, and feature views.
- Feature schemas use supported data type categories and account for backend
  support.
- Historical retrieval uses `get_historical_features()`.
- Online retrieval uses `get_online_features()`.
- Materialization cadence and freshness expectations are documented when online
  serving is claimed.

## Compute Engine Review

- Ray or Spark use is tied to documented prerequisites and component skills.
- Ray configuration uses `batch_engine.type: ray.engine`.
- KubeRay mode is preferred when Ray is used on OpenShift.
- `ray_address`, `kuberay_conf`, and environment-variable precedence are not
  mixed without an explicit reason.
- Spark examples are treated as large-scale materialization patterns and not
  as a default lightweight demo path.

## Monitoring And Operations

- `services.onlineStore.server.metrics: true` is set before metrics visibility
  is claimed.
- ServiceMonitor creation depends on Prometheus Operator APIs being available.
- Registry cache TTL and worker settings are intentional for the latency and
  freshness target.
- Disconnected deployments disable external init-container behavior and use
  mirrored images or approved internal registries.
- Validation commands check `FeatureStore` readiness, pods with the `feast-`
  prefix, and relevant auth status conditions.

## Static Checks

Run the repo whitespace check and a focused stale-marker search against this
skill directory before finishing.
