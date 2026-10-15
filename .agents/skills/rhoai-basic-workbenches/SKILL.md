---
name: rhoai-basic-workbenches
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when an OpenShift AI administrator manages basic workbenches (Start basic
  workbench, namespace rhods-notebooks set by the Stage 010 DataScienceCluster):
  the Administration tab, starting, opening or stopping another user's basic
  workbench, the idle workbench timeout (notebook-controller-culler-config),
  workbench pod tolerations through hardware profiles, or the administrator
  troubleshooting cases (Jupyter 404, workbench does not start, disk full). Do
  NOT use for project workbenches (use rhoai-project-workflows), user IDE work
  (use rhoai-data-science-ide-workflows), the user-side Start basic workbench
  flow (use rhoai-connected-applications) or custom images (use
  rhoai-workbenches-custom-images).
---

# RHOAI Basic Workbenches

Thin skill: repo decisions and pitfalls here, product behavior in the linked
OpenShift AI 3.5 sections. Detailed record:
`gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/README.md`
(Workbenches component).

## When to use

- An administrator must start, open or stop a user's basic workbench, or stop
  all of them to free capacity before a demo or shutdown.
- A user gets a Jupyter 404, a workbench that does not start, or a disk-full error.
- Someone proposes an idle timeout or tolerations for workbench pods.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Workbenches component `Managed`, `workbenchNamespace: rhods-notebooks`; the operator creates that namespace | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/datasciencecluster.yaml` | [Manage basic workbenches][basic] |
| No basic workbench, idle timeout or culler ConfigMap in Git; the timeout is whatever an administrator sets in the dashboard | (not in Git) | [Stop idle workbenches][idle] |
| No workbench tolerations: in 3.5 tolerations come from hardware profiles, and the repo's Queue-type profiles carry none (Kueue ResourceFlavors place pods) | `gitops/stages/020-gpu-infrastructure-private-ai/020-gpu-quotas/hardware-profiles/` | [Workbench pod tolerations][tol] |
| Dashboard groups `rhods-admins` (admin) and `rhoai-developers` (user) in the `Auth` CR; membership from `setup-access.sh`, not Git | `gitops/stages/010-openshift-ai-platform-foundation/010-rhoai-platform/auth.yaml`, `stages/010-openshift-ai-platform-foundation/setup-access.sh` | [Jupyter 404][t404] |
| Demo work uses project workbenches (`demo-sandbox`) and Dev Spaces (Stage 070); basic workbenches are a support path only | `gitops/stages/010-openshift-ai-platform-foundation/010-access/README.md` | [Manage basic workbenches][basic] |

## Procedure

1. Administration tab: dashboard Applications, Enabled, Start basic workbench
   tile, Administration ([administration interface][admin]). Treat opening
   another user's workbench as a support action.
2. An idle timeout is a live dashboard setting (Settings, Cluster settings;
   [Stop idle workbenches][idle]); record any change in `docs/OPERATIONS.md`.
3. Read-only checks after the OpenShift safety guard in `AGENTS.md`:

   ```bash
   ./stages/010-openshift-ai-platform-foundation/validate.sh
   oc get notebooks.kubeflow.org -n rhods-notebooks
   oc get configmap notebook-controller-culler-config -n redhat-ods-applications
   oc get group rhods-admins rhoai-developers -o custom-columns=NAME:.metadata.name,USERS:.users
   ```

## Pitfalls

- A Jupyter 404 is usually missing group membership; fix it with
  `setup-access.sh` (persona names from `.env`), not by widening the `Auth`
  groups ([Jupyter 404][t404]).
- The `cpu-default` profile names LocalQueue `lq-cpu-default`, which Git
  declares only in `demo-sandbox` and `evaluated-models`, not in
  `rhods-notebooks`. A basic workbench that does not start with that profile
  is a queue problem before it is a sizing problem
  ([Workbench does not start][tstart]; `rhoai-hardware-profiles`).
  Unresolved: whether Kueue enforces in `rhods-notebooks`; check the pod events.
- Disk full: the workbench PVC is exhausted; back up and enlarge it
  ([Disk full][tdisk]; `rhoai-cluster-pvc-size`).
- Do not look for a cluster-wide toleration setting; hardware profiles replaced
  it ([Workbench pod tolerations][tol]).

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Administration | [Manage basic workbenches][basic], [Administration interface][admin] |
| Other users' workbenches | [Start][start], [Access][open], [Stop][stop], [Revoke access][revoke] |
| Idle timeout and tolerations | [Stop idle workbenches][idle], [Workbench pod tolerations][tol] |
| Troubleshooting | [Administrator reference][ts], [404][t404], [Does not start][tstart], [Disk full][tdisk] |

## Related skills

`rhoai-connected-applications`, `rhoai-project-workflows`,
`rhoai-data-science-ide-workflows`, `rhoai-users-groups-access`,
`rhoai-hardware-profiles`, `rhoai-cluster-pvc-size`,
`rhoai-dashboard-applications`, `rhoai-troubleshoot`.

[basic]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#managing-basic-workbenches_notebook-mgmt
[admin]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#accessing-the-administration-interface-for-basic-workbenches_notebook-mgmt
[start]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#starting-basic-workbenches-owned-by-other-users_notebook-mgmt
[open]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#accessing-basic-workbenches-owned-by-other-users_notebook-mgmt
[stop]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#stopping-basic-workbenches-owned-by-other-users_notebook-mgmt
[revoke]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_openshift_ai/index#revoking-user-access-to-basic-workbenches_managing-rhoai
[idle]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#stopping-idle-workbenches_notebook-mgmt
[tol]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#workbench-pod-tolerations-hardware-profiles_notebook-mgmt
[ts]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#troubleshooting-common-problems-in-workbenches-for-administrators_notebook-mgmt
[t404]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#a_user_receives_a_404_page_not_found_error_when_logging_in_to_jupyter
[tstart]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#a_users_workbench_does_not_start
[tdisk]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#the_user_receives_a_database_or_disk_is_full_error_or_a_no_space_left_on_device_error_when_they_run_notebook_cells
