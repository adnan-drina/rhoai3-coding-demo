---
name: gitops-move-applications
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "rhoai"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "GitOps & Manifests"
description: >
  Split, rename or re-point (new source.path) Argo CD Applications on a live cluster without
  deleting or recreating any object they manage, using scripts/platform/move-applications.py.
  Use when a change moves objects to another Application, renames an Application, or moves a
  component's folder under gitops/stages/. Do NOT use for ordinary stage deploys at a new
  revision with unchanged names and paths (use the stage deploy.sh) or for layout rules
  (see .agents/rules/gitops.md).
---

# Move Objects Between Argo CD Applications

The Applications have no `resources-finalizer`, and tracking is by annotation: an Application takes an object over by rewriting its `argocd.argoproj.io/tracking-id`. Nothing is created or deleted when this is done in the right order. `scripts/platform/move-applications.py` does it in that order and checks every object.

## When to invoke

- Splitting one Application into stage components (`040-governed-models-as-a-service` became eight `040-*` Applications; `070-advanced-app-platform` became eight `070-*` Applications, moved with `--sequential`).
- Renaming an Application (`agent-console` became `060-agent-console`).
- Moving a component's folder, which changes `spec.source.path` (the one-folder-per-Application layout).

## Before the move (in Git)

1. Write the new Application manifests in `gitops/argocd/app-of-apps/<NNN-stage>/<component>.yaml` and the folders they render (`.agents/rules/gitops.md`).
2. Prove the renders: every new Application renders exactly the objects the old one did, or every difference is intended and listed in the commit message. `python3 scripts/shared/stage_apps.py check-static NNN` and `./scripts/platform/validate-stage-flow.sh` must pass.
3. Update every place that names an Application or a path, not only the manifests:
   - exact tracking-id checks (`'<app>:'+...`) in deploy, validate and setup scripts;
   - in-cluster references: RBAC `resourceNames` on `applications.argoproj.io`, hook scripts that `oc get application <name>`;
   - hook Jobs that check a target's tracking-id prefix;
   - `managed-by` label values are object labels, not Application names: leave them.
4. Push the commit. The tool pins every Application to that full SHA.

## Run

```bash
# Read-only preflight: render differences, recorded objects, carried cluster-specific settings
python3 scripts/platform/move-applications.py --stage NNN --revision <sha> [--app NAME ...] [--from OLD ...] --dry-run
# The move
python3 scripts/platform/move-applications.py --stage NNN --revision <sha> [--app NAME ...] [--from OLD ...]
```

- Split or rename: `--from` names the old Application(s) to retire; `--app` limits the targets (default: the whole stage).
- Re-point only: no `--from`; the names stay and only the source path changes.
- `--sequential` applies, syncs and waits for one Application at a time in deploy order. Use it when a component's hooks need another component's hooks to have run at the new revision (Stage 070: the GitLab integration hub needs the earlier components, Developer Hub's catalog hook needs the GitLab mirror). Without it every new Application syncs at once.
- Objects that no new Application renders are reported; `--delete-leftovers` deletes those still tracked by a `--from` Application, after you reviewed the list.
- The tool is safe to re-run after a failure: it keeps the UIDs recorded on the first run in `~/.local/state/rhoai3-coding-demo/move-applications/`.

The tool stops automated sync on the old Applications, applies the new ones, starts one sync for each Application that has not yet synced the new source (automated sync does not run one when the render is unchanged), waits until each is Synced, Healthy and successfully synced at the revision, checks every recorded object's tracking id and UID, and only then deletes the old Applications (no cascade).

## Rules the tool encodes (and why)

- **Stop automated sync on the old Application first.** Otherwise both Applications reconcile the same objects and the old one rewrites the tracking ids back.
- **Manual-sync Applications (all of Stage 060) need one explicit sync, carrying their own `syncOptions`.** A bare `operation.sync` drops them, so `RespectIgnoreDifferences` is not applied and delegated data is overwritten (the 2026-10-13 MCP list wipe).
- **Sync gates.** `060-openshell-runtime` waits in its `openshell-runtime-prerequisites` hook for `setup-runtime.py --revision <sha>` to stamp `openshell-runtime-ready`. The stamp must be written after this sync applied the ConfigMap; written earlier, the sync's own apply puts the old value back. `SYNC_GATES` in the tool holds this; add an entry for any new Application whose hook waits for a runtime step.
- **Sync hooks with `BeforeHookCreation` get a new UID on every sync.** Only their owner is checked.
- **Cluster-specific Application settings live only on the cluster** (Stage 040 Gateway hostname `source.kustomize` patch, Stage 020 MachineSet replica `ignoreDifferences`). The tool carries them from the Application that currently owns the objects and says so.
- **No apply may delete keys only `last-applied-configuration` still records.** An ignore rule under `RespectIgnoreDifferences` copies live fields (controller-owned annotations included) into last-applied; the first apply without the rule deletes them. The preflight refuses such a move and lists the keys; `--allow-field-removal` accepts them after review. On 2026-10-14 this deleted OpenShift's `openshift.io/sa.scc.*` allocations from the Stage 070 namespaces (`.agents/rules/gitops.md` "Removing an ignore rule").
- **Carried ignore rules must still select a rendered object.** Only cluster-specific rules for objects the Application keeps are carried; a rule for an object that moved away is dropped.
- **Never `oc apply` a hand-edited JSON copy of a live Application**; never add `resources-finalizer.argocd.argoproj.io`.

## After the move

1. Run the stage `validate.sh` (and the component validators for script-deployed Applications) from the moved revision.
2. Merge the branch into `main` with a merge commit so the pinned SHA stays reachable.

## Rollback

Re-create the previous Application at its last revision with automated sync off, sync it so it takes the objects back, delete the new Applications (no cascade), then turn automated sync on again.
