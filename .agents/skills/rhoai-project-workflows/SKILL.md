---
name: rhoai-project-workflows
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when working with OpenShift AI projects of this demo (demo-sandbox "AI
  Coding Sandbox", evaluated-models, internal-models and the other
  dashboard-labelled namespaces): creating or reviewing a project in Git,
  project workbench create/start/stop/update/delete, attaching connections and
  the connections API annotations, cluster storage, Kueue scheduling status, and
  project access (Contributor = edit, Admin = admin RoleBindings). Do NOT use for
  dashboard group membership (use rhoai-users-groups-access), connection type
  templates (use rhoai-connection-types), S3 calls from a notebook (use
  rhoai-s3-object-storage-data), IDE usage (use rhoai-data-science-ide-workflows)
  or project-scoped images, profiles and runtimes (use rhoai-project-scoped-resources).
---

# RHOAI Project Workflows

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/010-openshift-ai-platform-foundation/010-access/README.md`.

## When to use

- Adding a project, or changing who can use one.
- A user creates or troubleshoots a project workbench, connection or cluster storage.
- A model or workbench manifest must reference a connection.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Projects are Namespaces in Git with label `opendatahub.io/dashboard: "true"` and a display name: `demo-sandbox`, `internal-models`, `external-models`, `models-as-a-service`, `evaluated-models`, `ai-curated-prompts`, `mcp-servers`, `ai-agents` | `gitops/stages/010-openshift-ai-platform-foundation/010-access/namespace-demo-sandbox.yaml`; the other stages' `namespace*.yaml` (Stages 040, 050, 060) | [Use projects][projects] |
| `demo-sandbox`: `rhoai-developers` get `edit` (Contributor), `rhods-admins` get `admin`; `evaluated-models` is admins only | `gitops/stages/010-openshift-ai-platform-foundation/010-access/rolebinding-*.yaml`, `gitops/stages/050-model-evaluation/050-model-qualification/access.yaml` | [Manage access][access], [Default project roles][roles] |
| No workbench and no custom workbench role in Git; users create workbenches in the dashboard | (not in Git) | [Create a workbench][wb-create] |
| `demo-sandbox`, `internal-models`, `models-as-a-service` and `evaluated-models` carry `kueue.openshift.io/managed: "true"`; workbenches need a profile whose LocalQueue exists in the project (`lq-cpu-default` in `demo-sandbox` and `evaluated-models`) | `namespace-demo-sandbox.yaml`, `gitops/stages/020-gpu-infrastructure-private-ai/020-gpu-quotas/queues/` | [Kueue scheduling status][kueue] |
| Connections are Git-declared Secret skeletons filled by hook Jobs (see `rhoai-s3-object-storage-data`) | `gitops/stages/010-openshift-ai-platform-foundation/010-sandbox-storage/`, `gitops/stages/050-model-evaluation/050-model-qualification/storage/` | [Connections API][api] |
| Models do not use the `opendatahub.io/connections` annotation; the Stage 050 candidate pulls `hf://` directly | `gitops/stages/050-model-evaluation/050-model-qualification/candidate-qwen3-8-27b-nvfp4.yaml` | [Annotations by workload type][annot] |
| `evaluated-models` cluster storage: PVC `evaluated-models-storage` (20 Gi `gp3-csi`) created by a hook, not tracked by Argo CD | `gitops/stages/050-model-evaluation/050-model-qualification/storage/connection-job.yaml` | [Add cluster storage][storage-add] |

## Procedure

1. New project: add a Namespace with the dashboard label in its stage
   component, RoleBindings like `010-access`, and a LocalQueue per hardware
   profile it will use (`rhoai-hardware-profiles`). Do not create projects in
   the dashboard for anything a stage depends on.
2. Workbench: create, start, stop and delete follow [Use project
   workbenches][workbenches]; attach the project's S3 connection at creation.
3. Validate after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   ./stages/010-openshift-ai-platform-foundation/validate.sh
   oc get ns -l opendatahub.io/dashboard=true
   oc get notebooks.kubeflow.org,pvc -n demo-sandbox
   oc auth can-i create notebooks.kubeflow.org -n demo-sandbox --as=<developer> --as-group=rhoai-developers
   ```

## Pitfalls

- Resource names are fixed at creation; only display names and descriptions change.
- Deleting a project or cluster storage deletes its data; the OBC-backed
  connections and buckets are `Prune=false,Delete=false` but PVCs are not.
- Connection changes reach a workbench only after restart ([Connections API][api]).
- Connections cannot be used across namespaces; a Notebook lists them as
  `namespace/name`, an InferenceService or LLMInferenceService by plain name
  ([Annotations by workload type][annot]).
- Developers have `edit`, so they cannot change RoleBindings; access changes go through Git.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Projects | [Use projects][projects], [Create][p-create], [Delete][p-delete] |
| Workbenches | [Use project workbenches][workbenches], [Create][wb-create], [Env vars][env], [Kueue status][kueue], [Stop (CLI)][wb-stop] |
| Connections | [Use connections][conn], [Connections API][api], [Annotations][annot] |
| Storage | [Configure cluster storage][storage], [Add][storage-add] |
| Access | [Manage access][access], [Default project roles][roles], [Custom workbench roles][custom-roles] |

## Related skills

`rhoai-users-groups-access`, `rhoai-connection-types`,
`rhoai-s3-object-storage-data`, `rhoai-data-science-ide-workflows`,
`rhoai-project-scoped-resources`, `rhoai-hardware-profiles`,
`rhoai-storage-classes`, `rhoai-cluster-pvc-size`, `rhoai-ai-pipelines`.

[projects]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_on_projects/index#using-projects_projects
[p-create]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_on_projects/index#creating-a-project_projects
[p-delete]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_on_projects/index#deleting-a-project_projects
[workbenches]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_on_projects/index#using-project-workbenches_projects
[wb-create]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_on_projects/index#creating-a-project-workbench_projects
[env]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_on_projects/index#configure-environment-variables_projects
[kueue]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_on_projects/index#kueue-workbench-scheduling-status_projects
[wb-stop]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_on_projects/index#stopping-a-project-workbench-cli_projects
[conn]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_on_projects/index#using-connections_projects
[api]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_on_projects/index#using-connections-api_projects
[annot]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_on_projects/index#using_connection_annotations_based_on_workload_type
[storage]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_on_projects/index#configuring-cluster-storage_projects
[storage-add]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_on_projects/index#adding-cluster-storage-to-your-project_projects
[access]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_on_projects/index#managing-access-to-projects_projects
[roles]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_on_projects/index#default_project_roles
[custom-roles]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_on_projects/index#workbench-custom-roles-overview_projects
