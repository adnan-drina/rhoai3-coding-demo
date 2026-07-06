---
name: rhoai-data-science-ide-workflows
metadata:
  author: rhoai3-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "RHOAI Platform"
description: >
  Use when documenting, reviewing, or operating Red Hat OpenShift AI data
  science IDE workflows from the Working in your data science IDE guide:
  accessing a workbench IDE; using JupyterLab to create, upload, clone, pull,
  push, and package notebooks; using code-server to work with notebooks, Git,
  Python packages, and extensions; handling user-facing Jupyter/workbench
  errors such as 403, startup failures, and no-space errors; and deciding when
  code-server is inappropriate for Elyra-based pipelines. Do NOT use for
  project/workbench lifecycle provisioning (use rhoai-project-workflows),
  custom workbench image authoring (use rhoai-workbenches-custom-images),
  dashboard import of workbench images (use rhoai-workbench-image-import),
  S3-compatible object operations from notebooks (use
  rhoai-s3-object-storage-data), AI Pipelines authoring (use
  rhoai-kfp-pipeline-authoring), or live cluster changes without the OpenShift
  safety guard.
---

# RHOAI Data Science IDE Workflows

Use this skill for user-facing OpenShift AI IDE workflows inside running
workbenches on the active product baseline in `docs/PLATFORM_BASELINE.md`.

## Source Grounding

Read `references/source-capture.md` before using product workflow details.
Official Red Hat documentation is product authority. This skill adapts the
official Working in your data science IDE guide to this repo's demo workflow
and documentation model.

## Scope

This skill covers:

- accessing a running workbench IDE from the OpenShift AI dashboard
- JupyterLab notebook creation and local notebook upload
- JupyterLab Git workflows: clone, pull, commit, and push
- JupyterLab Python package inspection and `requirements.txt` installation
- user-facing JupyterLab and workbench troubleshooting signals
- code-server notebook upload and Git workflows
- code-server Python package inspection and `requirements.txt` installation
- code-server extension installation
- IDE support boundaries, including RStudio Server Technology Preview and
  code-server lack of Elyra-based pipeline support

Use other skills for adjacent work:

- `rhoai-project-workflows` for project and workbench creation, update,
  deletion, connections, and cluster storage
- `rhoai-connected-applications` for Start basic workbench access from
  Applications -> Enabled and connected application endpoint handling
- `rhoai-workbenches-custom-images` for custom workbench image design and
  image-stream-backed workbench manifests
- `rhoai-workbench-image-import` for dashboard import of existing custom images
- `rhoai-s3-object-storage-data` for notebook access to S3-compatible object
  storage
- `rhoai-ai-pipelines` for AI Pipelines product workflows, Elyra runtime
  configuration, pipeline runs, exports, and logs
- `rhoai-automl` for saved AutoML prediction notebooks and AutoML-specific
  workbench handoff
- `rhoai-autorag` for generated AutoRAG indexing and inference notebooks in a
  workbench
- `rhoai-mlflow` for MLflow SDK installation, authentication, and experiment
  tracking from notebooks or pods
- `rhoai-model-customization-training` for model customization workbench setup,
  Red Hat Python index package use, Docling, SDG Hub, Training Hub, and ITS
  notebooks
- `rhoai-kfp-pipeline-authoring` for repo-specific KFP Python and runner code
- `rhoai-users-groups-access` for OpenShift AI user group membership issues
- `rhoai-basic-workbenches` and `env-troubleshoot` for administrator-side
  workbench and cluster troubleshooting

## Demo Policy

For this repo:

- Use Git as the durable collaboration path for notebooks, prompts, scripts,
  requirements, and examples. Treat local upload as a demo convenience, not a
  source-of-truth workflow.
- Prefer `requirements.txt` with exact package versions for reproducible IDE
  demos. If packages are required across many workbenches, move the dependency
  into a custom workbench image workflow.
- Do not commit Git credentials, tokens, storage credentials, or generated
  notebook outputs that expose secrets.
- Use JupyterLab when the demo depends on notebook-native or Elyra-based
  pipeline workflows.
- Use code-server when the demo benefits from a VS Code-like editor,
  extensions, terminal-centric work, or multi-file application development.
- Label RStudio Server as Technology Preview and do not rely on it for
  disconnected environment demos.
- User-facing troubleshooting should capture the visible symptom, then hand
  off admin-side checks to `rhoai-basic-workbenches`, `env-troubleshoot`, or
  `rhoai-users-groups-access` as appropriate.

## Workflow

1. Confirm the active baseline in `docs/PLATFORM_BASELINE.md`.
2. Read `references/source-capture.md` and
   `references/official-doc-extraction.md`.
3. Decide whether the task is:
   - accessing a workbench IDE
   - JupyterLab notebook, Git, package, or troubleshooting workflow
   - code-server notebook, Git, package, extension, or troubleshooting workflow
   - IDE support-boundary review
4. Use `examples/ide-workflow-patterns.md` for focused review patterns.
5. For live cluster work, follow the OpenShift safety guard in `AGENTS.md`.
6. Validate with `references/validation-checklist.md`.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/validation-checklist.md`
- `examples/ide-workflow-patterns.md`
