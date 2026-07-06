# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Guide title | Deliver consistent ML features to models with Feature Store |
| Guide URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_machine_learning_features/index |
| Documentation category | Develop / Feature Store guide |
| Retrieved date | 2026-06-10 |
| Sections used | Chapter 1 Overview of machine learning features and Feature Store; Chapter 2 Configuring Feature Store; Chapter 3 Defining machine learning features; Chapter 4 Retrieving features for model training; Chapter 5 Feature Store integration with workbenches; Chapter 6 Understanding compute engines in Feature Store; Chapter 7 Feature Store command line interface reference |

## Supporting Red Hat Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active product baseline and documentation category index |
| Red Hat OpenShift AI workbench documentation | Adjacent workbench behavior and user workflow |
| Red Hat OpenShift AI distributed workload documentation | Adjacent Ray/Kueue context when compute engines depend on distributed processing |
| Red Hat OpenShift AI centralized authentication documentation | OIDC prerequisites for Feature Store OIDC authorization |

## Supplemental Sources Linked From The Guide

| Source | Role |
|--------|------|
| Feast project documentation | Supplemental API and provider reference only |
| Feast Operator examples | Supplemental examples for database-backed stores and RBAC patterns |
| Kubernetes and Prometheus documentation | Supplemental behavior for HPA, PodDisruptionBudget, and ServiceMonitor resources |

## Source Boundaries

- Product configuration truth: the Red Hat OpenShift AI 3.4 Feature Store guide
  above.
- Supplemental behavior: upstream Feast, Kubernetes, and Prometheus references
  linked from the official guide.
- Demo policy: GitOps-managed resources and clean-slate repository sequencing
  are project decisions, not product requirements.
- Verification: cluster schema checks such as `oc explain featurestore.spec`
  and read-only `oc get` commands confirm target-cluster availability.

## Unresolved Or Environment-Specific Items

- Whether the demo will introduce Feature Store at all, and which step owns it.
  Verification: add a docs/GitOps/scripts/validation bundle when the step is
  designed.
- Database, object-storage, Redis, PostgreSQL, Spark, Ray, and OIDC endpoints.
  Verification: record approved services and secret names during active GitOps
  implementation.
- Shared registry versus project-local registry topology.
  Verification: choose project-local by default unless a multi-team feature
  reuse story is required.
- Disconnected Feature Store image source and mirroring process.
  Verification: use the disconnected-environment section only if the demo
  environment requires it.
