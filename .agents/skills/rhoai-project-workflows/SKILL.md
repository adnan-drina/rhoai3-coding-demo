---
name: rhoai-project-workflows
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or operating Red Hat OpenShift AI project
  workflows from the Working on projects guide: creating, updating, and
  deleting data science projects; creating, starting, updating, and deleting
  project workbenches; adding, updating, and deleting project connections;
  using connection annotations with InferenceService and LLMInferenceService;
  adding, updating, migrating, and deleting project cluster storage; granting,
  updating, and removing project access; and handing off to project-scoped
  resources for workbench images, hardware profiles, and KServe serving
  runtimes. Do NOT use for global user/group access (use
  rhoai-users-groups-access), connection type template administration (use
  rhoai-connection-types), S3 data access from notebooks (use
  rhoai-s3-object-storage-data), data science IDE workflows inside a running
  workbench (use rhoai-data-science-ide-workflows), storage class administration (use
  rhoai-storage-classes), project-scoped resource schema details (use
  rhoai-project-scoped-resources), or live cluster changes without the
  OpenShift safety guard.
---

# RHOAI Project Workflows

Use this skill for OpenShift AI user workflows that organize data science work
inside projects on the active product baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product workflow details.
Official Red Hat documentation is product authority. This skill adapts the
official Working on projects guide to this repo's demo workflow and GitOps
review model.

## Scope

This skill covers:

- data science project lifecycle: create, update, and delete
- project workbench lifecycle: create, start, update, and delete
- workbench image and IDE selection boundaries
- project connections and connection API workload annotations
- project cluster storage lifecycle and storage migration workflow
- project-level access for users and groups
- handoff to project-scoped resources for project-local workbench images,
  hardware profiles, and KServe serving runtime templates

Use other skills for adjacent work:

- `rhoai-users-groups-access` and `rhoai-access-group-selection` for global
  OpenShift AI user/admin access
- `rhoai-connection-types` for administrator-managed connection type templates
- `rhoai-s3-object-storage-data` for Boto3 and S3-compatible object storage
  data operations from workbenches
- `rhoai-data-science-ide-workflows` for JupyterLab, code-server, Git, Python
  package, extension, and user-facing IDE troubleshooting workflows
- `rhoai-storage-classes` and `rhoai-cluster-pvc-size` for OpenShift AI
  storage administration and cluster default PVC size
- `rhoai-project-scoped-resources` for detailed project-scoped resource
  manifests and review rules
- `rhoai-workbenches-custom-images`, `rhoai-workbench-image-import`, and
  `rhoai-workbench-gateway-api-migration` for custom workbench images
- `rhoai-model-serving-platform` for KServe and vLLM serving details
- `rhoai-ai-pipelines` for AI Pipelines server, definition, experiment, run,
  schedule, log, and Elyra workflows
- `rhoai-mlflow` for MLflow workspace mapping, SDK authentication, RBAC, and
  project-specific artifact storage overrides
- `rhoai-kfp-pipeline-authoring` for repo-specific KFP Python and runner code

## Demo Policy

For this repo:

- Treat an OpenShift AI project as the clean boundary for a demo team,
  persona, or capability stage.
- Choose stable project and workbench resource names up front. Resource names
  are immutable after creation; only display names and descriptions can be
  edited later.
- Do not hard-code credentials in READMEs, notebooks, scripts, or manifests.
  Use project connections and Kubernetes secrets with least-privilege scope.
- Prefer `ReadWriteOnce` cluster storage for individual workbenches. Use
  `ReadWriteMany` only for explicit collaboration scenarios with documented
  data integrity, security, and backup expectations.
- Treat project deletion and cluster-storage deletion as destructive. They
  remove associated resources and data that cannot be recovered.
- Keep Technology Preview posture visible when selecting RStudio workbench
  images or hardware profiles.
- Do not claim that creating a project alone deploys pipelines, models,
  workbenches, or storage. Those capabilities require explicit resources.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - project lifecycle
   - workbench lifecycle
   - connection lifecycle or connection API annotations
   - cluster storage lifecycle or migration
   - project access management
   - project-scoped resource handoff
4. Use `examples/project-workflow-patterns.md` for review and authoring
   patterns.
5. For live cluster work, follow the OpenShift safety guard in `AGENTS.md`.
6. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/project-workflow-patterns.md`
