# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Working with AI pipelines |
| Guide title | Build, schedule, and track machine learning pipelines |
| Guide URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_ai_pipelines/index |
| Documentation category | Develop / Working with AI pipelines |
| Retrieved date | 2026-06-10 |
| Sections used | Preface; 1 Managing AI pipelines; 1.1 Configuring a pipeline server; 1.1.1 Configuring a pipeline server with an external Amazon RDS database; 1.2 Defining a pipeline; 1.2.1 Compiling the pipeline YAML with the Kubeflow Pipelines SDK; 1.2.2 Compiling Kubernetes-native manifests with the Kubeflow Pipelines SDK; 1.2.3 Authenticating the Kubeflow Pipelines SDK with a pipeline server; 1.2.4 Defining a pipeline by using the Kubernetes API; 1.2.5 Migrating pipelines from database to Kubernetes API storage; 1.3 Importing a pipeline; 1.4 Deleting a pipeline; 1.5 Deleting a pipeline server; 1.6 Viewing the details of a pipeline server; 1.7 Viewing existing pipelines; 1.8 Overview of pipeline versions; 1.9 Uploading a pipeline version; 1.10 Deleting a pipeline version; 1.11 Viewing the details of a pipeline version; 1.12 Downloading a pipeline version; 1.13 Overview of pipelines caching; 2 Managing pipeline experiments; 3 Managing pipeline runs; 4 Working with pipeline logs; 5 Working with pipelines in JupyterLab; 6 Troubleshooting DSPA component errors |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_on_projects/index | Project, workbench, connection, and cluster storage context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_in_your_data_science_ide/index | JupyterLab and IDE workflow context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_data_in_an_s3-compatible_object_store/index | S3-compatible object storage workflow context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/installing_and_uninstalling_openshift_ai_self-managed/working-with-certificates_certs | DSCI trusted CA bundle behavior |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/managing-storage-classes | Storage class behavior for pipeline workspaces |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_machine_learning_features/index | ML feature workflows that can consume pipeline outputs |

## Red Hat Narrative And Implementation Sources

| Source | Role |
|--------|------|
| https://developers.redhat.com/articles/2026/06/03/build-modular-ai-pipelines-openshift-ai-and-reusable-components | Red Hat Developer guidance for modular AI pipelines, reusable KFP components, component catalog selection, repository structure, and contribution quality practices |
| https://github.com/kubeflow/pipelines-components | Primary upstream catalog for generic reusable Kubeflow components and pipelines |
| https://github.com/red-hat-data-services/pipelines-components | Red Hat/OpenShift AI-aligned component catalog for components with Red Hat Data Services dependencies or OpenShift AI release alignment |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-kfp-pipeline-authoring/SKILL.md` | Repo-specific KFP code authoring boundary |
| `.agents/skills/rhoai-project-workflows/SKILL.md` | Project, workbench, connection, and cluster storage boundary |
| `.agents/skills/rhoai-data-science-ide-workflows/SKILL.md` | Non-pipeline IDE workflow boundary |
| `.agents/skills/rhoai-s3-object-storage-data/SKILL.md` | Notebook S3 data access boundary |
| `.agents/skills/rhoai-certificate-management/SKILL.md` | DSCI trusted CA bundle boundary |
| `.agents/skills/rhoai-storage-classes/SKILL.md` | Storage class administration boundary |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Working with AI
  pipelines guide above.
- The guide defines AI Pipelines product workflows: pipeline server
  configuration, KFP 2.0 pipeline definition, Kubernetes API storage,
  dashboard lifecycle, experiments, runs, schedules, logs, Elyra, workspaces,
  and DSPA troubleshooting.
- It does not replace repo-specific KFP implementation standards, project or
  workbench provisioning, non-pipeline IDE usage, object storage data
  operations, certificate bundle implementation, or storage class
  administration.
- Verification: pipeline server readiness, Import pipeline availability,
  Pipeline/PipelineVersion resources, KFP SDK compile output, authenticated
  KFP client list calls, dashboard pipeline/version visibility, cache markers,
  experiment/run state, logs, workspace task output, and DSPA conditions.
- The reusable-components blog and component repositories do not override the
  official OpenShift AI pipeline server, storage, run, experiment, log, or
  dashboard lifecycle. Use them as implementation guidance for composing and
  authoring reusable KFP components, then validate runtime behavior through the
  official AI Pipelines guide.

## Unresolved Or Environment-Specific Items

- Active pipeline server database choice.
  Verification: document whether a demo stage uses the default development
  database or an external MySQL/MariaDB database.
- Active object storage provider and bucket layout.
  Verification: record bucket, endpoint, region, and credential ownership in
  `docs/OPERATIONS.md` when implemented.
- Active pipeline definition storage mode.
  Verification: prefer Kubernetes API storage for GitOps-backed demo content
  unless a step explicitly needs internal database storage.
- Active KFP SDK version in workbenches or local tooling.
  Verification: check installed `kfp` version before compiling or submitting.
- Active Elyra workbench image.
  Verification: choose a supported JupyterLab image with Elyra before
  documenting JupyterLab pipeline editor workflows.
