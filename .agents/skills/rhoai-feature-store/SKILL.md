---
name: rhoai-feature-store
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or rebuilding Red Hat OpenShift AI Feature
  Store capabilities from the official Feature Store guide: machine learning
  feature concepts, Feast Operator enablement, DataScienceCluster
  feastoperator state, FeatureStore custom resources, registry/offline/online
  stores, UI visibility, Kubernetes or OIDC authorization, workbench client
  configuration, feature definitions, entities, feature views, historical and
  online retrieval, Ray and Spark compute engines, monitoring, scaling, and the
  feast CLI. Do NOT use for model serving, AI Pipelines, MLflow, model registry,
  or live cluster deployment; use the matching rhoai-* or env-* skill instead.
---

# RHOAI Feature Store

Use this skill to ground Feature Store work in the active Red Hat OpenShift AI
baseline recorded in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product configuration details.
Official Red Hat documentation is product authority. Upstream Feast material
linked from the Red Hat guide is supplemental only.

## Scope

This skill covers Feature Store as a RHOAI platform capability:

- enabling the `feastoperator` component in the `DataScienceCluster`
- creating `FeatureStore` resources in data science projects
- configuring registry, offline store, online store, UI, auth, persistence,
  scaling, monitoring, and disconnected behavior
- defining data sources, entities, feature views, and supported data types
- connecting workbenches to Feature Store client configuration
- using Ray, Spark, and local compute engines for materialization and
  historical retrieval
- using `feast` CLI commands in workbenches or controlled automation

Use other skills for adjacent areas:

- `rhoai-workbenches-custom-images` for workbench image and Notebook behavior
- `rhoai-kueue-workload-management` and
  `rhoai-distributed-workload-operations` for Ray/Kueue operations
- `rhoai-kfp-pipeline-authoring` for Kubeflow Pipelines
- `rhoai-mlflow` for MLflow tracking, SDK authentication, experiments, and
  artifact storage behavior
- `env-deploy-and-evaluate` for live cluster deployment flow

## Demo Policy

For this repo:

- Treat Feature Store as an optional RHOAI capability until a demo step
  introduces it with docs, GitOps, scripts, and validation together.
- Use GitOps for `DataScienceCluster` and `FeatureStore` resources once active
  GitOps folders are recreated.
- Keep database credentials, OIDC client details, object-storage credentials,
  and registry connection strings out of Git.
- Prefer project-scoped `FeatureStore` resources unless a future architecture
  explicitly introduces a shared registry namespace.
- Do not scale Feature Store replicas above one while using file-backed
  SQLite, DuckDB, or local registry storage.
- Use database-backed persistence before enabling static replicas, HPA, or
  production-style availability.
- Validate `FeatureStore` schema on the target cluster before adding fields
  not already captured from the official guide.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Confirm OpenShift AI is installed and the target project exists.
4. Enable Feature Store by setting
   `DataScienceCluster.spec.components.feastoperator.managementState` to
   `Managed`.
5. Create a project-scoped `FeatureStore` custom resource with
   `apiVersion: feast.dev/v1`.
6. Add `feature-store-ui: enabled` only when the OpenShift AI dashboard should
   expose the Feature Store UI or workbench selection flow.
7. Configure registry, online store, offline store, auth, and persistence from
   official examples or verified cluster schema.
8. Add workbench access and RBAC/OIDC behavior before documenting user access.
9. Use compute engines only after Ray, Spark, or local execution prerequisites
   are documented.
10. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/feature-store-patterns.md`
