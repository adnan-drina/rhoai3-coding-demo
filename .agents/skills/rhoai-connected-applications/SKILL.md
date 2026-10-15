---
name: rhoai-connected-applications
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when a user works with OpenShift AI connected applications in this demo:
  the Applications Explore and Enabled pages, enabling a SaaS application tile,
  removing a disabled tile, or the user side of the Start basic workbench tile
  (start, notebooks, Git, packages, restart to change settings, stop). No
  connected application beyond the built-in tiles is added in Git. Do NOT use
  for administrator tile management or hiding the basic workbench tile (use
  rhoai-dashboard-applications), administrator control of basic workbenches
  (use rhoai-basic-workbenches) or project workbenches (use rhoai-project-workflows).
---

# RHOAI Connected Applications

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections.

**No connected application is added in this demo.** Git holds no
`OdhApplication` or other tile resources; Explore shows only what OpenShift AI
ships. The Start basic workbench tile is not hidden by
`gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/odhdashboardconfig.yaml`.

## When to use

- A user asks what an Explore or Enabled tile does, or how to enable one.
- A user starts a basic workbench instead of a project workbench.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Notebook and data work runs in project workbenches in `demo-sandbox`, code in Dev Spaces (Stage 070); the basic workbench is not part of any stage flow | `gitops/stages/010-openshift-ai-platform-foundation/010-access/README.md`, `stages/070-advanced-app-platform/README.md` | [Use basic workbenches][basic] |
| Basic workbenches run in `rhods-notebooks` (DSC `workbenchNamespace`) and get no repo S3 connection; those exist only in project namespaces | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/datasciencecluster.yaml`, `gitops/stages/010-openshift-ai-platform-foundation/010-sandbox-storage/` | [Start a basic workbench][start] |
| Dashboard access only for `rhods-admins` and `rhoai-developers` | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/auth.yaml` | [View connected applications][view] |

## Procedure

1. Tiles: [view][view], [enable][enable] (SaaS keys typed in the dashboard,
   never committed), [remove a disabled tile][remove].
2. Basic workbench: [start][start], then notebooks, Git and packages as in the
   linked sections; IDE details are in `rhoai-data-science-ide-workflows`.
   Change the image or size by [restarting with new settings][restart];
   [stop][stop] when done.
3. Read-only checks after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   oc get odhapplications -n redhat-ods-applications
   oc get notebooks.kubeflow.org -n rhods-notebooks
   ```

## Pitfalls

- An enabled tile does not prove the backing service works; it is a dashboard entry.
- A basic workbench is per user and outside projects: no project connections,
  storage or pipelines. Move work that needs them to `demo-sandbox`.
- A basic workbench with a Kueue profile may wait for a LocalQueue that does
  not exist in `rhods-notebooks` (see `rhoai-basic-workbenches`).

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Tiles | [View][view], [Enable][enable], [Remove disabled][remove] |
| Basic workbench | [Use basic workbenches][basic], [Start][start], [Notebooks][nb], [Git][git], [Packages][pkg], [Restart with new settings][restart], [Stop][stop] |
| Administrator side | [Hide the basic workbench tile][hide], [Disable connected applications][disable] |

## Related skills

`rhoai-dashboard-applications`, `rhoai-basic-workbenches`,
`rhoai-data-science-ide-workflows`, `rhoai-project-workflows`,
`rhoai-users-groups-access`.

[view]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_connected_applications/index#viewing-connected-applications_connected-apps
[enable]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_connected_applications/index#enabling-applications-connected_connected-apps
[remove]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_connected_applications/index#removing-disabled-applications_connected-apps
[basic]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_connected_applications/index#using-basic-workbenches_connected-apps
[start]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_connected_applications/index#starting-a-basic-workbench_connected-apps
[nb]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_connected_applications/index#creating-and-importing-jupyter-notebooks_connected-apps
[git]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_connected_applications/index#collaborating-on-jupyter-notebooks-by-using-git_connected-apps
[pkg]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_connected_applications/index#managing-python-packages_connected-apps
[restart]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_connected_applications/index#updating-workbench-settings-by-restarting-your-workbench_connected-apps
[stop]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/working_with_connected_applications/index#stopping-basic-workbenches_connected-apps
[hide]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#hiding-the-default-basic-workbench-application_dashboard
[disable]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#disabling-applications-connected_dashboard
