# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Working with AutoML |
| Guide URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_automl/index |
| Documentation category | Develop / Working with AutoML |
| Retrieved date | 2026-06-10 |
| Sections used | Preface; 1 AutoML overview; 1.1 AutoML workflow; 1.2 Supported task types; 1.3 Technology Preview limitations; 1.4 Viewing externally created runs; 2 Create an AutoML optimization run; 3 Evaluate AutoML results; 4 Run predictions with an AutoML model; 5 Deploy an AutoML model for inference; 6 AutoML evaluation metrics; 6.1 Optimized metrics by task type; 6.2 Model detail views; 7 AutoML configuration parameters; 7.1 Common parameters; 7.2 Tabular task parameters; 7.3 Time series task parameters; 7.4 Auto-selected parameters |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_ai_pipelines/index | AI Pipelines server, pipeline import, pipeline run lifecycle, and DSPA troubleshooting context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_data_in_an_s3-compatible_object_store/index | S3-compatible object storage and workbench data access context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/working_on_projects | Project, workbench, and connection lifecycle context |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_in_your_data_science_ide/index | Saved notebook execution in a workbench |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_model_registries/index | Registering and deploying model versions from the registry |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/configuring_your_model-serving_platform | Serving runtime and model-serving platform context |
| https://access.redhat.com/support/offerings/techpreview | Technology Preview support scope |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-ai-pipelines/SKILL.md` | AI Pipelines prerequisite and run lifecycle boundary |
| `.agents/skills/rhoai-s3-object-storage-data/SKILL.md` | S3-compatible data boundary |
| `.agents/skills/rhoai-project-workflows/SKILL.md` | Project, workbench, and connection boundary |
| `.agents/skills/rhoai-data-science-ide-workflows/SKILL.md` | Saved notebook execution boundary |
| `.agents/skills/rhoai-model-registry-workflows/SKILL.md` | Model registry handoff boundary |
| `.agents/skills/rhoai-model-serving-platform/SKILL.md` | AutoGluon serving runtime review boundary |
| `.agents/skills/rhoai-api-tiers/SKILL.md` | KServe API support posture review |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Working with AutoML
  guide above.
- The guide defines dashboard workflows for AutoML optimization runs,
  leaderboard review, model registry registration, saved prediction notebooks,
  and deployment through an AutoGluon serving runtime.
- AutoML is Technology Preview in the captured guide.
- The guide does not replace the AI Pipelines guide, S3 object storage guide,
  workbench guide, model registry guide, or model-serving platform guide.
- Verification: AutoML page run status, completed leaderboard, model details,
  registered model visibility, saved notebook execution, deployment readiness,
  and task-specific metrics.

## Unresolved Or Environment-Specific Items

- Active demo data set and task type.
  Verification: define in the future demo step README and verify CSV schema
  before creating the run.
- Active AI Pipelines server storage and database configuration.
  Verification: use `rhoai-ai-pipelines` and project-scoped connection review.
- AutoGluon `ServingRuntime` lifecycle ownership.
  Verification: decide whether the runtime is cluster-wide GitOps desired
  state or a runbook prerequisite when the active implementation is rebuilt.
- AutoML pipeline version strings for imported pipeline workflows.
  Verification: align imported pipeline version names with the active RHOAI
  product version in `docs/PLATFORM_BASELINE.md`.
- Cluster capacity for AutoML runs.
  Verification: check schedulable CPU and memory in the target environment
  before live execution.
