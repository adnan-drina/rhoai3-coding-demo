# Source Capture

## Official Product Source

| Field | Value |
|-------|-------|
| Product baseline | `docs/PLATFORM_BASELINE.md` |
| Document title | Working in your data science IDE |
| Guide title | Use the Red Hat data science IDE images effectively |
| Guide URL | https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_in_your_data_science_ide/index |
| Documentation category | Develop / Working in your data science IDE |
| Retrieved date | 2026-06-10 |
| Sections used | Preface; 1 Accessing your workbench IDE; 2 Working in JupyterLab; 2.1 Creating and importing Jupyter notebooks; 2.1.1 Creating a Jupyter notebook; 2.1.2 Uploading an existing notebook file to JupyterLab from local storage; 2.2 Collaborating on Jupyter notebooks by using Git; 2.2.1 Uploading an existing notebook file from a Git repository by using JupyterLab; 2.2.2 Uploading an existing notebook file to JupyterLab from a Git repository by using the CLI; 2.2.3 Updating your project with changes from a remote Git repository; 2.2.4 Pushing project changes to a Git repository; 2.3 Managing Python packages; 2.3.1 Viewing Python packages installed on your workbench; 2.3.2 Installing Python packages on your workbench; 2.4 Troubleshooting common problems in workbenches for users; 3 Working in code-server; 3.1 Creating code-server workbenches; 3.1.1 Creating a workbench; 3.1.2 Uploading an existing notebook file to code-server from local storage; 3.2 Collaborating on workbenches in code-server by using Git; 3.2.1 Uploading an existing notebook file from a Git repository by using code-server; 3.2.2 Uploading an existing notebook file to code-server from a Git repository by using the CLI; 3.2.3 Updating your project in code-server with changes from a remote Git repository; 3.2.4 Pushing project changes in code-server to a Git repository; 3.3 Managing Python packages in code-server; 3.3.1 Viewing Python packages installed on your code-server workbench; 3.3.2 Installing Python packages on your code-server workbench; 3.4 Installing extensions with code-server |

## Related Official Sources

| Source | Role |
|--------|------|
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_on_projects/index | Project and workbench lifecycle, connections, storage, project access |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/creating_a_workbench/index | Dedicated workbench creation guidance |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html-single/working_with_data_in_an_s3-compatible_object_store/index | Notebook access to S3-compatible object storage |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_openshift_ai/creating-custom-workbench-images | Custom workbench image creation and support boundaries |
| https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.4/html/managing_resources/importing-a-custom-workbench-image_resource-mgmt | Dashboard import of existing workbench images |

## Supporting Project Sources

| Source | Role |
|--------|------|
| `docs/PLATFORM_BASELINE.md` | Active RHOAI/OCP baseline and source hierarchy |
| `AGENTS.md` | OpenShift safety guard and GitOps operating constraints |
| `.agents/skills/rhoai-project-workflows/SKILL.md` | Project and workbench lifecycle boundary |
| `.agents/skills/rhoai-workbenches-custom-images/SKILL.md` | Custom image and Notebook resource boundary |
| `.agents/skills/rhoai-s3-object-storage-data/SKILL.md` | S3-compatible notebook data workflow boundary |
| `.agents/skills/rhoai-kfp-pipeline-authoring/SKILL.md` | AI Pipelines and Elyra/KFP boundary |
| `.agents/skills/rhoai-users-groups-access/SKILL.md` | User group access boundary for 403 errors |
| `.agents/skills/rhoai-basic-workbenches/SKILL.md` | Administrator-side workbench troubleshooting boundary |

## Source Boundaries

- Product authority: the official Red Hat OpenShift AI 3.4 Working in your data
  science IDE guide above.
- The guide defines user-facing IDE workflows for running workbenches:
  accessing IDEs, creating/importing notebooks, using Git, managing packages,
  installing code-server extensions, and recognizing common user errors.
- It does not replace project/workbench provisioning, custom workbench image
  authoring, storage connection design, AI Pipelines implementation, global
  access administration, or administrator-side troubleshooting.
- Verification: workbench status, IDE browser access, notebook file visibility,
  Git repository visibility and remote changes, package list output,
  installed package imports, extension list visibility, and captured error
  messages for escalation.

## Unresolved Or Environment-Specific Items

- Active demo IDE selection for each step.
  Verification: document JupyterLab versus code-server selection in the step
  README and GitOps manifests once active steps are recreated.
- Active package dependency policy.
  Verification: decide per step whether dependencies live in
  `requirements.txt`, a notebook cell, or a custom workbench image.
- Git authentication method for workbench collaboration.
  Verification: define token/credential handling in `docs/OPERATIONS.md` when
  active notebook collaboration is implemented.
- code-server extension set.
  Verification: list only extensions installed and verified in the active
  workbench image and environment.
