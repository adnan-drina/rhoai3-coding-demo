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
  deleting or recreating any object they manage, using scripts/stage-apps.sh and plain oc.
  Use when a change moves objects to another Application, renames an Application, or moves a
  component's folder under gitops/stages/. Do NOT use for ordinary stage deploys at a new
  revision with unchanged names and paths (use the stage deploy.sh) or for layout rules
  (see .agents/rules/gitops.md).
---

# Move Objects Between Argo CD Applications

The Applications have no `resources-finalizer`, and tracking is by annotation: an Application takes an object over by rewriting its `argocd.argoproj.io/tracking-id`. Nothing is created or deleted when this is done in the right order. The steps below do it with `scripts/stage-apps.sh` and plain `oc`. The former helper `scripts/platform/move-applications.py` that automated them was retired; its last version is in git history at `82092e01`.

## When to invoke

- Splitting one Application into stage components (`040-governed-models-as-a-service` became eight `040-*` Applications; `070-advanced-app-platform` became eight `070-*` Applications, moved one Application at a time).
- Renaming an Application (`agent-console` became `060-agent-console`).
- Moving a component's folder, which changes `spec.source.path` (the one-folder-per-Application layout).

## Before the move (in Git)

1. Write the new Application manifests as `gitops/applications/<NNN>-<component>.yaml` (file name = `metadata.name` + `.yaml`) and the folders they render (`.agents/rules/gitops.md`).
2. Prove the renders: every new Application renders exactly the objects the old one did, or every difference is intended and listed in the commit message. `scripts/stage-apps.sh check-static NNN` and `scripts/validate-stage-flow.sh` must pass.
3. Update every place that names an Application or a path, not only the manifests:
   - exact tracking-id checks (`'<app>:'+...`) in deploy, validate and setup scripts;
   - in-cluster references: RBAC `resourceNames` on `applications.argoproj.io`, hook scripts that `oc get application <name>`;
   - hook Jobs that check a target's tracking-id prefix;
   - `managed-by` label values are object labels, not Application names: leave them.
4. Push the commit. Every Application is pinned to that full SHA.

## Run

```bash
NS=openshift-gitops R=<full pushed sha> U=<GIT_REPO_URL>
# 1. Read-only: objects the new Applications will take over (reported as lacking their tracking id)
scripts/stage-apps.sh preflight NNN --repo-url "$U" --app NEW [--app NEW ...]
#    Record each object's tracking id and UID before the move
oc get <kind> <name> [-n <ns>] -o jsonpath='{.metadata.annotations.argocd\.argoproj\.io/tracking-id} {.metadata.uid}{"\n"}'
# 2. Stop automated sync on every old Application (split or rename only)
oc patch applications.argoproj.io OLD -n "$NS" --type json -p '[{"op":"remove","path":"/spec/syncPolicy/automated"}]'
# 3. Apply the new (or re-pointed) Applications at the revision, start one sync each, wait
scripts/stage-apps.sh apply NNN --app NEW [--app NEW ...] --revision "$R" --repo-url "$U" [--kustomize-patches FILE]
scripts/stage-apps.sh sync NNN --app NEW [--app NEW ...]
scripts/stage-apps.sh wait NNN --revision "$R" --repo-url "$U" --app NEW [--app NEW ...]
# 4. Check every recorded object: owner, tracking id and UID unchanged except the Application name
scripts/stage-apps.sh owner NNN <Kind> <name> [<namespace>] [--group G]
# 5. Only then delete the old Applications without cascade
oc delete applications.argoproj.io OLD -n "$NS" --cascade=orphan
```

- Split or rename: the old Application(s) are retired in steps 2 and 5. Re-point only: skip steps 2 and 5; the names stay and only the source path changes.
- Apply, sync and wait one Application at a time in deploy order (`scripts/stage-apps.sh names NNN --all`) when a component's hooks need another component's hooks to have run at the new revision (Stage 070: the GitLab integration hub needs the earlier components, Developer Hub's catalog hook needs the GitLab mirror).
- Objects that no new Application renders stay tracked by the old Application; review that list before deleting any of them by hand.
- Re-running after a failure is safe as long as the UIDs from step 1 are kept.
- `scripts/stage-apps.sh sync` starts one hook-strategy sync per Application that has not yet synced the new source (automated sync does not run one when the render is unchanged), carrying the Application's own `syncOptions` and `prune`.

## Rules (and why)

- **Stop automated sync on the old Application first.** Otherwise both Applications reconcile the same objects and the old one rewrites the tracking ids back.
- **Manual-sync Applications (all of Stage 060) need one explicit sync, carrying their own `syncOptions`.** A bare `operation.sync` drops them, so `RespectIgnoreDifferences` is not applied and delegated data is overwritten (the 2026-10-13 MCP list wipe). Use `scripts/stage-apps.sh sync`, never a hand-written sync patch.
- **Sync gates.** `060-openshell-runtime` waits in its `openshell-runtime-prerequisites` hook for `stages/060-agent-runtime-and-agentops/deploy.sh --revision <sha>` to stamp `openshell-runtime-ready`. The stamp must be written after this sync applied the ConfigMap; written earlier, the sync's own apply puts the old value back. Run the gate between `sync` and `wait` for that Application, and do the same for any new Application whose hook waits for a runtime step.
- **Sync hooks with `BeforeHookCreation` get a new UID on every sync.** Only their owner is checked.
- **Cluster-specific Application settings live only on the cluster** (Stage 040 Gateway hostname `source.kustomize` patch, Stage 020 MachineSet replica `ignoreDifferences`). Read them from the Application that currently owns the objects and carry them over: `--kustomize-patches` for `source.kustomize`, as Stage 040 `deploy.sh` does; the Stage 020 delegation by re-running its `deploy.sh`.
- **No apply may delete keys only `last-applied-configuration` still records.** An ignore rule under `RespectIgnoreDifferences` copies live fields (controller-owned annotations included) into last-applied; the first apply without the rule deletes them. Compare the live objects' `kubectl.kubernetes.io/last-applied-configuration` with the new render before step 3 and stop if keys would be removed. On 2026-10-14 this deleted OpenShift's `openshift.io/sa.scc.*` allocations from the Stage 070 namespaces (`.agents/rules/gitops.md` "Removing an ignore rule").
- **Carried ignore rules must still select a rendered object.** Only cluster-specific rules for objects the Application keeps are carried; a rule for an object that moved away is dropped.
- **Never `oc apply` a hand-edited JSON copy of a live Application**; never add `resources-finalizer.argocd.argoproj.io`.

## After the move

1. Run the stage `validate.sh` (and the component validators for script-deployed Applications) from the moved revision.
2. Merge the branch into `main` with a merge commit so the pinned SHA stays reachable.

## Rollback

Re-create the previous Application at its last revision with automated sync off, sync it so it takes the objects back, delete the new Applications (no cascade), then turn automated sync on again.
