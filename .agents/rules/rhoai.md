---
name: rhoai
skill-group: RHOAI Platform
skill-prefix: rhoai-
applies-to:
  - docs/PLATFORM_BASELINE.md
  - docs/rhoai-*/**
  - gitops/**
  - stage-*/**/*.py
  - stage-*/**/*.ipynb
  - stage-*/**/kfp/**
---

# RHOAI Platform

Use the `rhoai-*` skills as the source of truth for RHOAI component behavior,
configuration, pipelines, chatbot behavior, and evaluation workflows:

- `.agents/skills/rhoai-chatbot-customization/SKILL.md`
- `.agents/skills/rhoai-architecture-overview/SKILL.md`
- `.agents/skills/rhoai-release-and-support-posture/SKILL.md`
- `.agents/skills/rhoai-platform-planning/SKILL.md`
- `.agents/skills/rhoai-api-tiers/SKILL.md`
- `.agents/skills/rhoai-update-channels/SKILL.md`
- `.agents/skills/rhoai-self-managed-installation/SKILL.md`
- `.agents/skills/rhoai-dsci-dsc-configuration/SKILL.md`
- `.agents/skills/rhoai-distributed-workloads/SKILL.md`
- `.agents/skills/rhoai-kueue-workload-management/SKILL.md`
- `.agents/skills/rhoai-distributed-workload-operations/SKILL.md`
- `.agents/skills/rhoai-distributed-workload-workflows/SKILL.md`
- `.agents/skills/rhoai-kubeflow-spark-operator/SKILL.md`
- `.agents/skills/rhoai-nvidia-gpu-accelerators/SKILL.md`
- `.agents/skills/rhoai-hardware-profiles/SKILL.md`
- `.agents/skills/rhoai-certificate-management/SKILL.md`
- `.agents/skills/rhoai-observability/SKILL.md`
- `.agents/skills/rhoai-logs-and-audit-records/SKILL.md`
- `.agents/skills/rhoai-installation-troubleshooting/SKILL.md`
- `.agents/skills/rhoai-uninstallation/SKILL.md`
- `.agents/skills/rhoai-users-groups-access/SKILL.md`
- `.agents/skills/rhoai-access-group-selection/SKILL.md`
- `.agents/skills/rhoai-central-authentication-service/SKILL.md`
- `.agents/skills/rhoai-dashboard-applications/SKILL.md`
- `.agents/skills/rhoai-connected-applications/SKILL.md`
- `.agents/skills/rhoai-dashboard-customization/SKILL.md`
- `.agents/skills/rhoai-cluster-pvc-size/SKILL.md`
- `.agents/skills/rhoai-storage-classes/SKILL.md`
- `.agents/skills/rhoai-connection-types/SKILL.md`
- `.agents/skills/rhoai-s3-object-storage-data/SKILL.md`
- `.agents/skills/rhoai-project-workflows/SKILL.md`
- `.agents/skills/rhoai-data-science-ide-workflows/SKILL.md`
- `.agents/skills/rhoai-project-scoped-resources/SKILL.md`
- `.agents/skills/rhoai-component-resource-customization/SKILL.md`
- `.agents/skills/rhoai-telemetry-admin-settings/SKILL.md`
- `.agents/skills/rhoai-feature-store/SKILL.md`
- `.agents/skills/rhoai-automl/SKILL.md`
- `.agents/skills/rhoai-basic-workbenches/SKILL.md`
- `.agents/skills/rhoai-workbenches-custom-images/SKILL.md`
- `.agents/skills/rhoai-workbench-image-import/SKILL.md`
- `.agents/skills/rhoai-workbench-gateway-api-migration/SKILL.md`
- `.agents/skills/rhoai-model-serving-platform/SKILL.md`
- `.agents/skills/rhoai-model-deployment/SKILL.md`
- `.agents/skills/rhoai-maas-governance/SKILL.md`
- `.agents/skills/rhoai-distributed-inference-llmd/SKILL.md`
- `.agents/skills/rhoai-model-management-monitoring/SKILL.md`
- `.agents/skills/rhoai-monitoring-trustyai/SKILL.md`
- `.agents/skills/rhoai-model-catalog-sources/SKILL.md`
- `.agents/skills/rhoai-model-catalog-workflows/SKILL.md`
- `.agents/skills/rhoai-gen-ai-playground/SKILL.md`
- `.agents/skills/rhoai-autorag/SKILL.md`
- `.agents/skills/rhoai-enterprise-rag/SKILL.md`
- `.agents/skills/rhoai-model-registry/SKILL.md`
- `.agents/skills/rhoai-model-registry-workflows/SKILL.md`
- `.agents/skills/rhoai-llama-stack/SKILL.md`
- `.agents/skills/rhoai-ai-pipelines/SKILL.md`
- `.agents/skills/rhoai-mlflow/SKILL.md`
- `.agents/skills/rhoai-model-customization-training/SKILL.md`
- `.agents/skills/rhoai-evaluation/SKILL.md`
- `.agents/skills/rhoai-guardrails-safety/SKILL.md`
- `.agents/skills/rhoai-model-evaluation/SKILL.md`
- `.agents/skills/rhoai-kfp-pipeline-authoring/SKILL.md`

Official Red Hat documentation for the active baseline in
`docs/PLATFORM_BASELINE.md` is the product source of truth. Use Red Hat articles
and `rh-brain` examples only as supporting implementation evidence.
Use `.agents/references/red-hat-doc-map.yaml` to route RHOAI documentation by
category, book, and chapter topic to the matching flat `rhoai-*` skill. If an
official RHOAI source is not mapped yet, use
`project-red-hat-doc-skill-authoring` to update the map and create or update
the relevant flat skill; do not create nested skill folders that mirror Red Hat
documentation categories.

The active implementation is being rewritten. RHOAI manifests, notebooks,
pipelines, chatbot code, and evaluation workflows under
`backup/legacy-implementation-2026-06-09/` are legacy references only until
corresponding active content is recreated under `gitops/`, root-level
`stage-YXX-slug/` folders, or `scripts/`.

When a README introduces a RHOAI capability, pair the concept narrative with an
official documentation link for each technical component used. When a manifest
introduces images or model artifacts, verify Red Hat registry, validated model,
or explicitly documented demo-exception provenance before treating it as
aligned.

RHOAI controllers and prerequisite operators can generate product-owned
operands such as monitoring resources, KServe resources, MaaS gateway
resources, model-serving controllers, or dashboard-backed resources. Do not
patch generated operand image fields, generated datasources, or
operator-created Deployments as durable fixes. Use the matching `rhoai-*`
skill plus `project-red-hat-operator-gitops` to decide whether the fix belongs
in `DataScienceCluster`/`DSCInitialization` configuration, Subscription
lifecycle policy, product baseline alignment, or a documented product wait.

Use `rhoai-api-tiers` to classify API support posture before treating an API as
durable demo contract. Do not invent CR fields, API versions, annotations, or
operator settings. If a field is uncertain, verify it through official docs or
schema inspection.
