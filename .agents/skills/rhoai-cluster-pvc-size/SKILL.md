---
name: rhoai-cluster-pvc-size
metadata:
  author: rhoai3-coding-demo
  version: 2.0.0
  product: rhoai
  docs-version: "3.5"
  skill-group: "RHOAI Platform"
description: >
  Use when someone wants to change or restore the OpenShift AI cluster default
  PVC size (Settings > Cluster settings > PVC size) for new workbench storage
  in this demo, or asks why new workbench PVCs have a given size. Do NOT use
  for which storage class backs the PVC (use rhoai-storage-classes), resizing
  or migrating existing project storage (use rhoai-project-workflows), or
  Prometheus and database volumes (see the owning stage README).
---

# RHOAI cluster PVC size

Thin skill. Not customized in this demo: the cluster default PVC size is left
at the product default, set by no GitOps object. Product behavior is in the
linked OpenShift AI 3.5 sections.

## When to use

- A demo workbench runs out of disk and a larger default is proposed.
- Someone changed the size in the dashboard and asks whether Git tracks it.

## Repo decisions

| Decision | Where in Git | Official section |
|---|---|---|
| Default PVC size not set; the 3.5 default is 20GiB ("Restore Default") | none under `gitops/` | [Configure the default PVC size][configure], [Restore the default PVC size][restore] |
| No workbench or workbench PVC is in Git; personas create workbenches in `demo-sandbox` (`rhoai-developers` have `edit` there), so a per-workbench size can be chosen at creation | `gitops/stages/010-openshift-ai-platform-foundation/010-access/README.md` | see `rhoai-basic-workbenches` |

## Procedure

1. Prefer a per-workbench size in the workbench form for a one-off need.
2. If the cluster default must change, follow
   [Configure the default PVC size][configure] as an admin persona, then
   record the value and the date in `docs/OPERATIONS.md` (the setting is not in
   Git, so a rebuilt cluster returns to the default).
3. Check that a new PVC has the size, after the OpenShift safety guard in
   `AGENTS.md`:

   ```bash
   oc get pvc -n demo-sandbox -o custom-columns=NAME:.metadata.name,SIZE:.spec.resources.requests.storage,CLASS:.spec.storageClassName
   ```

## Pitfalls

- Changing the setting restarts the workbench pod and makes it unavailable for
  up to 30 seconds ([Configure][configure]); do not change it during a demo.
- The setting applies to new PVCs; existing PVCs keep their size.

## Official documentation (OpenShift AI 3.5)

| Topic | Section |
|---|---|
| Chapter | [Manage cluster PVC size][chapter] |
| Procedures | [Configure the default PVC size][configure], [Restore the default PVC size][restore] |

## Related skills

`rhoai-storage-classes`, `rhoai-basic-workbenches`, `rhoai-project-workflows`,
`ocp-storage`.

[chapter]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#managing-cluster-pvc-size
[configure]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#configuring-the-default-pvc-size-for-your-cluster_resource-mgmt
[restore]: https://docs.redhat.com/en/documentation/red_hat_openshift_ai_self-managed/3.5/html-single/managing_resources/index#restoring-the-default-pvc-size-for-your-cluster_resource-mgmt
