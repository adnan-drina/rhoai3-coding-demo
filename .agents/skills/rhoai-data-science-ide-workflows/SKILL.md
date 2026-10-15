---
name: rhoai-data-science-ide-workflows
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when a user works inside an OpenShift AI workbench IDE (JupyterLab or
  code-server) in demo-sandbox or evaluated-models: opening the IDE, Git
  clone/pull/push, installing Python packages, using the Workbench S3
  connection, calling a MaaS model from a notebook, or a user-side 403, start
  failure or no-space error; also R workflows after the 3.5 RStudio removal.
  Do NOT use for developer coding workspaces (use manage-devspaces), workbench
  creation and storage (use rhoai-project-workflows), custom images (use
  rhoai-workbenches-custom-images), or pipelines (use rhoai-ai-pipelines).
---

# RHOAI Data Science IDE Workflows

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/README.md`
(Workbenches component) and
`gitops/stages/010-openshift-ai-platform-foundation/sandbox-storage/README.md`.

## When to use

- A workbench user in a demo project needs Git, packages, data or a model
  endpoint from JupyterLab or code-server.
- A user reports a workbench IDE error and an administrator needs the handoff.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Workbenches component Managed with `workbenchNamespace: rhods-notebooks`; no workbench objects in Git (users create them) | `gitops/stages/010-openshift-ai-platform-foundation/rhoai-platform/datasciencecluster.yaml` | [Access your workbench IDE][access] |
| Developer coding happens in Dev Spaces (Stage 070), not in workbenches; workbenches serve notebook and data work | `stages/070-advanced-app-platform/README.md` | [Working in code-server][codeserver] |
| `demo-sandbox` gets S3 connections "Models" and "Workbench" with credentials written at runtime | `gitops/stages/010-openshift-ai-platform-foundation/sandbox-storage/` | [Access your workbench IDE][access] |
| `evaluated-models` has its own Models, Workbench and Pipelines connections | `gitops/stages/050-model-evaluation/model-qualification/storage/` | see `rhoai-ai-pipelines` |
| Developers are project Contributors (`edit`), administrators project Admins | `gitops/stages/010-openshift-ai-platform-foundation/access/` | [Troubleshooting for users][ts] |
| CPU workbenches use hardware profile `cpu-default` on non-preemptive `cq-cpu-default` (workbenches cannot be suspended) | `gitops/stages/020-gpu-infrastructure-private-ai/gpu-quotas/hardware-profiles/cpu-default.yaml` | see `rhoai-hardware-profiles` |
| Notebooks call governed models through MaaS with a personal API key, never a pod URL | `gitops/stages/040-governed-models-as-a-service/model-access/README.md` | see `rhoai-maas-governance` |

## Procedure

1. Open the IDE from the project in the dashboard (AI Coding Sandbox =
   `demo-sandbox`); attach the Workbench connection at creation so the S3
   variables are present.
2. Keep notebooks and `requirements.txt` in Git; pin versions. Packages
   needed by many workbenches belong in a custom image
   (`rhoai-workbenches-custom-images`).
3. For a MaaS model, create a personal key in the dashboard and use the
   OpenAI-compatible base `https://maas.<cluster-domain>/v1`; keep the key out
   of notebooks committed to Git.
4. Administrator checks after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   ./stages/010-openshift-ai-platform-foundation/validate.sh
   oc get notebooks.kubeflow.org -n demo-sandbox
   oc get events -n demo-sandbox --sort-by=.lastTimestamp | tail -20
   ```

## Pitfalls

- RStudio Server images are removed in 3.5; existing RStudio workbenches need
  the R alternatives ([R after RStudio removal][rstudio]).
- Elyra pipelines are not available in code-server; use JupyterLab
  ([Working in code-server][codeserver]).
- 403 on login, workbench not starting, no space left: the user-side list is
  [Troubleshooting for users][ts]; group membership comes from
  `stages/010-openshift-ai-platform-foundation/setup-access.sh`.
- Never commit Git tokens, S3 credentials or MaaS keys from notebook output.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Access the IDE | [Access your workbench IDE][access] |
| JupyterLab notebooks, Git, packages | [JupyterLab][jupyter], [Git][jgit], [Python packages][jpkg] |
| code-server Git, packages, extensions | [Working in code-server][codeserver], [Git][cgit], [Packages][cpkg], [Extensions][ext] |
| User troubleshooting | [Troubleshooting for users][ts] |
| R workflows | [R after RStudio removal][rstudio] |
| MaaS from a notebook | [Test MaaS models in a notebook][maasnb] |

## Related skills

`manage-devspaces`, `rhoai-project-workflows`, `rhoai-basic-workbenches`,
`rhoai-workbenches-custom-images`, `rhoai-s3-object-storage-data`,
`rhoai-ai-pipelines`, `rhoai-maas-governance`, `rhoai-users-groups-access`.

[access]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_in_your_data_science_ide/index#accessing-your-workbench-ide_ide
[jupyter]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_in_your_data_science_ide/index#working_in_jupyterlab
[jgit]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_in_your_data_science_ide/index#collaborating-on-jupyter-notebooks-by-using-git_ide
[jpkg]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_in_your_data_science_ide/index#managing-python-packages_ide
[ts]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_in_your_data_science_ide/index#troubleshooting-common-problems-in-workbenches-for-users_ide
[codeserver]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_in_your_data_science_ide/index#working_in_code_server
[cgit]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_in_your_data_science_ide/index#collaborating-on-workbenches-in-code-server-by-using-git_ide
[cpkg]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_in_your_data_science_ide/index#managing-python-packages-in-code-server_ide
[ext]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_in_your_data_science_ide/index#installing-extensions-with-code-server_ide
[rstudio]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_in_your_data_science_ide/index#r_language_workflows_after_rstudio_removal
[maasnb]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/govern_llm_access_with_models-as-a-service/index#test-maas-models-in-notebook_maas-user
