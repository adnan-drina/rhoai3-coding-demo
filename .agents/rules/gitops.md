---
name: gitops
skill-group: GitOps & Manifests
skill-prefix: gitops-
applies-to:
  - gitops/**
  - "**/kustomization.yaml"
  - "**/kustomization.yml"
  - "gitops/**/*.yaml"
  - "gitops/**/*.yml"
---

# GitOps, Manifests, and Labels

Use the GitOps-related skills for work that changes manifests, Kustomize structure, Argo CD applications, or Kubernetes labels:

- `.agents/skills/review-gitops-change/SKILL.md`
- `.agents/skills/gitops-move-applications/SKILL.md` (split, rename or re-point live Applications)
- `.agents/skills/validate-demo-step/SKILL.md`

## Golden Rule

Every GitOps stage must be reproducible from `gitops/` and operated through `deploy.sh` / `validate.sh`. Workflow-only stages are operated through `validate.sh` only. The README explains the demo value; `docs/OPERATIONS.md` explains operational usage.

## Mandatory: Argo CD Applications in Every deploy.sh

Every stage's `deploy.sh` applies its Argo CD Applications as its first cluster-modifying action, pinned to one reviewed published commit, through the shared flow:
```bash
source "$REPO_ROOT/scripts/lib.sh"; load_env; check_oc_logged_in        # cluster guard
SHA=$("$REPO_ROOT/scripts/stage-apps.sh" select NNN --ref "${GIT_REPO_BRANCH:-HEAD}" --repo-url "$GIT_REPO_URL" [--extra PATH ...])
# stage-specific read-only preflight here
"$REPO_ROOT/scripts/stage-apps.sh" deploy NNN --revision "$SHA" --repo-url "$GIT_REPO_URL"
```
- `select` refuses a checkout whose stage source differs from the commit, untracked stage files, and a commit `GIT_REPO_URL` does not advertise. Never hand-write the publish check.
- `deploy` applies every deploy-order component, starts a sync only where this source has not been synced yet (carrying the Application's own `syncOptions` and prune), and waits for each to be Synced and Healthy. A stage whose own setup must run before its components can become healthy uses `--no-wait`, runs the setup, then `stage-apps.sh wait`. Components that declare `demo.rhoai.io/deploy-mode: sequential` deploy one order group at a time (Stage 070). `--resync` re-runs every hook. A cluster-specific value reaches one component as a Kustomize patch on its Application (`--kustomize-patches FILE`, Stage 040 Gateway hostnames), so Git stays cluster-neutral.
- A `deploy-script` component is deployed by `stages/NNN-name/deploy.sh --component NAME` with the same commands for one component: `select`, `stage-apps.sh preflight NNN --app NAME` and its own read-only checks, `stage-apps.sh apply NNN --app NAME`, `sync NNN --app NAME`, `wait NNN --app NAME`. No script calls the `argocd` CLI.
- Each stage takes `deploy.sh [--revision REF]`; the default is `GIT_REPO_BRANCH`, then `HEAD`. No default repository URL in scripts.
- `validate.sh` checks its Applications with `check_stage_applications NNN [SHA]` (`scripts/lib.sh`, which calls `stage-apps.sh status`): every component, never a subset. Exit 0 pass, 1 fail, 2 warnings or pending.

Every GitOps stage (`stages/NNN-name/deploy.sh` present) MUST have:
1. `gitops/stages/NNN-name/NNN-<component>/` - one folder per Argo CD Application (its `source.path`), named exactly like the Application, with the component README beside its `kustomization.yaml`; nested folders inside it are not prefixed
2. `gitops/stages/NNN-name/kustomization.yaml` - the union of the component folders (validators and `check-static` read it)
3. `gitops/applications/NNN-<component>.yaml` - one Application per component in one flat directory; the file name is exactly `metadata.name` + `.yaml`
4. `stages/NNN-name/deploy.sh` - applies the Applications
5. `stages/NNN-name/validate.sh` - verifies deployment
6. `stages/NNN-name/README.md` - educational narrative


### Component Applications

- Each Application carries the stage prefix and label (`demo.rhoai.io/stage: 'NNN'`) and exactly one of:
  - `demo.rhoai.io/deploy-order: '<n>'`: deployed by the stage `deploy.sh` with the other ordered components, all at one revision; validation requires each Synced and Healthy at that revision (`stage-apps.sh status`).
  - `demo.rhoai.io/deploy-script: stages/NNN-name/deploy.sh --component NAME`: deployed by that mode of the stage script with its own procedure and revision (the Stage 060 Applications, `010-sandbox-storage`, `010-console-observability`). Validation still checks it (`stage-apps.sh status` covers every component).
- A component that reports another health state by design names it in `demo.rhoai.io/accepted-health`.
- Components are disjoint (one owner per object, including singletons). `scripts/stage-apps.sh check-static NNN` enforces this and that their union equals the stage kustomization; `validate-stage-flow.sh` runs it.
- Group by lifecycle: operators, data (Prune=false,Delete=false), fast-changing content (models, access policies) and shared configuration each get their own component.
- Moving objects between Applications, renaming one or changing its `source.path` never deletes them: follow the skill `gitops-move-applications` (non-cascading Application deletion, then the new owner adopts the objects at their exact tracking ids).

Workflow-only stages omit `deploy.sh` and have no Argo CD Application. `scripts/validate-stage-flow.sh` walks `stages/*/`, requires `validate.sh` (and nothing else but `deploy.sh` as a top-level script), and checks every Application's name, stage label, source path, destination and component README.

**Never** apply manifests directly with `oc apply -k` for ArgoCD-managed resources.

## Repository Layout

```text
rhoai3-coding-demo/
|-- gitops/
|   |-- applications/NNN-<component>.yaml  # flat; file name = Application name
|   |-- bootstrap/
|   `-- stages/NNN-name/
|       |-- kustomization.yaml          # union of the component folders
|       `-- NNN-<component>/            # one folder per Application, named like it
|           |-- kustomization.yaml
|           |-- *.yaml                  # the component's main manifests, flat
|           |-- <unit>/                 # optional: a further unit (a Job with its RBAC, a second operator, a generator)
|           `-- components/<feature>/   # optional: Kustomize Components switched on in kustomization.yaml
|-- stages/NNN-name/{deploy.sh,validate.sh,README.md}
|-- scripts/
|-- docs/
`-- README.md
```

## Kustomize Structure

Follows the Kustomize and Red Hat `odh-gitops` conventions: plain manifests in one folder per deployable unit, no wrapper layers.

- One folder per Application. Its main manifests sit flat in the folder (an operator's `namespace.yaml`, `operator-group.yaml`, `subscription.yaml` and its instance CR together).
- Every component folder has a `README.md` with the headings `## Why`, `## What`, `## How`, `## Validation`, `## Alignment with official guidance` and `## References`, in that order: purpose, object inventory, configuration choices with reasons, checks, a status table against the installed version's Red Hat documentation, and verified sources. Update it in the same change as the manifests. `validate-stage-flow.sh` enforces presence and headings.
- A further unit inside a component (a Job with its RBAC, a dashboard generator, each operator of a multi-operator component) gets its own subfolder with its own `kustomization.yaml`.
- No `base/`-in-`base/` wrappers, no `aggregate/` layers, no placeholder values patched by an overlay: write the reviewed value (for example the Subscription channel) in the manifest.
- Add `overlays/<variant>/` only for a real variant, and `components/<feature>/` (Kustomize `kind: Component`) for an optional feature.
- Transformers (`labels`, `replacements`) belong in the component's `kustomization.yaml`, where they apply to the whole Application.
- Cluster-specific generated files live in their component folder (Stage 020 `020-gpu-machinesets/`, written by `stages/020-gpu-infrastructure-private-ai/machinesets/generate.sh`).

### Operator Deployment and CRD Timing

1. Phase 1: Apply operator Subscriptions
2. Wait/retry: Use Argo CD retry/backoff, sync waves, `SkipDryRunOnMissingResource=true`
3. Phase 2: Sync CRs using `sync-wave` annotations

## Argo CD Application Standards

### AppProject
All Applications MUST use `project: rhoai-demo` - never `default`.

### Required Metadata
```yaml
metadata:
  labels:
    app.kubernetes.io/part-of: rhoai3-coding-demo
    demo.rhoai.io/stage: "NNN"
  annotations:
    argocd.argoproj.io/sync-wave: "<stage-order>"
    argocd.argoproj.io/manifest-generate-paths: gitops/stages/NNN-name
```

### Destination
Every Application MUST use `destination: {server: https://kubernetes.default.svc, namespace: openshift-gitops}`, and every namespaced object MUST set its own `metadata.namespace`.

- Argo CD uses the destination namespace only as the default for objects that omit one, and as the namespace in a cluster-scoped object's tracking id (`<app>:<group>/<Kind>:<destination>/<name>`). One fixed value keeps tracking ids predictable for scripts and moves; it is not where the workload runs.
- Changing an existing Application's destination re-keys the tracking ids of its cluster-scoped objects: do it as a move (skill `gitops-move-applications`), never by editing the live Application.
- `validate-stage-flow.sh` enforces both rules for component Applications (`CLUSTER_SCOPED` in `scripts/stage-apps.sh` lists the cluster-scoped kinds that may omit a namespace). All 39 component Applications, Stage 070's eight included, are covered.

### No Destructive Finalizers
**NEVER** add `resources-finalizer.argocd.argoproj.io` to Application metadata.

### Required syncPolicy

| Setting | Value | Why |
|---------|-------|-----|
| `automated.prune` | `true` | Remove resources deleted from Git |
| `automated.selfHeal` | `true` (default) | Revert imperative changes |
| `retry.limit` | `10` | Operators need time to install CRDs |
| `retry.backoff` | `5s / factor 2 / max 3m` | Exponential backoff |
| `SkipDryRunOnMissingResource` | `true` | CRDs may not exist at first sync |
| `RespectIgnoreDifferences` | `true` | Sync also skips the ignored fields, not only the diff |

Exception: the five Stage 060 Applications have no `automated` policy. A runtime sync gate (`openshell-runtime-prerequisites`) needs per-revision values that `stages/060-agent-runtime-and-agentops/deploy.sh --component 060-openshell-runtime` stamps during the sync, and an automatic sync of a new commit on `main` would start the agent runtime rollout unattended. Their scripts start each sync explicitly at the selected SHA.

**Do NOT use:** `ServerSideApply=true` or `Replace=true`.

### Server-Side Diff
Enable it with the Application annotation `argocd.argoproj.io/compare-options: ServerSideDiff=true` (accurate diff for CRDs, defaulted fields and admission mutations). A `ServerSideDiff=true` entry in `syncPolicy.syncOptions` does **not** enable it: Argo CD reads diff strategy only from this annotation or the global `controller.diff.server.side` setting, which this repository does not set. An Application that needs client-side comparison sets `ServerSideDiff=false` in the annotation and records the reason in its component README. None does today: `060-openshell-runtime` was re-tested with server-side diff on 2026-10-14 (Synced, no resource out of sync) and switched back.

### Removing an ignore rule

With `RespectIgnoreDifferences=true` Argo CD copies the live values of ignored fields into what it applies, so client-side apply records them in `kubectl.kubernetes.io/last-applied-configuration`. Drop the rule (or move the object to an Application without it) and the next apply deletes every recorded key the manifest does not declare, including keys other controllers own. On 2026-10-14 dropping the Namespace `/metadata/annotations` rule deleted OpenShift's `openshift.io/sa.scc.*` allocations from the Stage 070 namespaces, and they were reallocated.

- Never ignore all of `/metadata/annotations` or `/metadata/labels`: it also hides `argocd.argoproj.io/tracking-id`, so no other Application can take the object over. With `ServerSideDiff=true`, keys other field managers add are not drift and need no rule.
- Before removing such a rule, compare each object's last-applied labels and annotations with the manifest; a move must not delete recorded keys unless that removal was reviewed.

### Delegated fields on shared singletons
`010-rhoai-platform` owns the `DataScienceCluster` and `OdhDashboardConfig`. A later stage that switches on its feature does so from a hook Job that patches only its own fields, after its prerequisites are ready, and declares them in the Job annotation `demo.rhoai.io/writes-delegated` (comma-separated `Kind:/json/pointer`). Each such field is listed in `010-rhoai-platform` `ignoreDifferences`. `stage-apps.sh check-delegations` (run by `validate-stage-flow.sh`) fails on a written field that is not delegated, a delegated field with no writer, a field with two writers, or a Job that patches these objects without the annotation.

### Hook Jobs
Every Job that runs as an Argo CD hook (or is created by a deploy script) follows these rules; reviews check them:
- `activeDeadlineSeconds` and a small `backoffLimit`, so a hook cannot block a sync indefinitely; `oc` calls use `--request-timeout`.
- Images pinned by digest.
- A restricted `securityContext` (no privilege escalation, all capabilities dropped, non-root, `RuntimeDefault` seccomp) and `resources`; size memory for the `oc` client (256Mi request, 1Gi limit for `ose-cli`).
- TLS verification may be skipped for cluster and demo endpoints (self-signed certificates; `.agents/rules/env.md`). Downloads from the internet still verify a pinned checksum (below).
- Secrets are written with the component's `secret_writer.py` (create, or merge-patch when it exists), never `oc apply -f` of a rendered Secret: client-side apply copies every value into the `kubectl.kubernetes.io/last-applied-configuration` annotation.
- RBAC: a namespaced Role with the verbs the Job uses is enough; prefer it over a ClusterRole. Naming objects (`resourceNames`) is optional (demo posture, `.agents/rules/env.md`).
- `hook-delete-policy: BeforeHookCreation,HookSucceeded` unless the completed Job is kept as evidence (say so in a comment).
- No remote installer piped into a shell; download a pinned release and verify its published checksum.

### Resource Tracking
`resourceTrackingMethod: annotation` only. Never `annotation+label` or `label`.

## YAML Formatting

- Use 2-space indentation; never tabs
- Use `.yaml` extension (not `.yml`)
- One resource per file
- Order keys: `apiVersion` > `kind` > `metadata` > `spec` > `data`/`stringData`
- End files with a single newline
- Use `true`/`false` for booleans; never `yes`/`no`

## YAML Comment Hygiene

Comments must explain **why**, never restate **what**.

Do NOT add:
- Title comments that restate the `kind`
- Decorative section headers
- Field narration for obvious fields

DO add:
- Why / design decisions
- Ref links: `# Ref: https://docs.redhat.com/...`
- Warnings: `# DEMO VALUES ONLY`, `# IMPORTANT:`
- Constraints that will break if changed

## Cross-Resource Consistency

When creating or modifying manifests, verify:
- Selector labels match Pod template labels
- ConfigMap/Secret name references resolve
- Service `targetPort` matches container port
- Namespace consistency across related resources
- ServiceAccount and RBAC chain is traceable

## Kubernetes and OpenShift Labeling Standards

### Required Labels
| Label | Purpose | Example |
|-------|---------|---------|
| `app.kubernetes.io/part-of` | Groups by platform capability | `maas` |
| `app.kubernetes.io/name` | Component name | `rhods-operator` |
| `app.kubernetes.io/component` | Component role | `operator` |
| `app.kubernetes.io/managed-by` | Managing tool | `argocd` |

### Values for `app.kubernetes.io/part-of`
| Group | Value |
|-------|-------|
| RHOAI Platform | `rhoai-platform` |
| GPU Infrastructure | `gpu-infra` |
| LLM Serving | `llm-serving` |
| Model-as-a-Service | `maas` |
| Dev Spaces | `devspaces` |
| MTA Modernization | `mta-modernization` |
| Developer Hub | `developer-hub` |
| Identity | `identity` |
| Observability | `observability` |
| GitOps | `gitops` |

### OpenShift Topology Labels
| Label/Annotation | Purpose |
|------------------|---------|
| `app.openshift.io/runtime` | Runtime icon in Topology |
| `app.openshift.io/connects-to` | Dependency arrows |
| `app.openshift.io/vcs-uri` | Source code link |

## Workflow-Only Stages

Stages 110, 120, and 130 are workflow-only: they have no Argo CD Application and no `deploy.sh`. Their `validate.sh` scripts validate against resources owned by the Stage 070 component Applications (`scripts/stage-apps.sh names 070`).

Stage 070 deploys its components one at a time in deploy order (namespaces, identity, devspaces, pipelines, sonarqube, mta, gitlab, rhdh): its GitLab integration hook and Developer Hub catalog hook depend on the earlier components, and sync waves order hooks only inside one Application. `stage-apps.sh deploy 070` keeps that order.

## MaaS and Model Access

Model consumers should go through MaaS, not directly to scattered endpoints. Preserve the distinction between:
- Private local models on OpenShift
- Governed external models through MaaS
- MCP/tool integrations with separate data boundaries

## Workaround Awareness

Before modifying MaaS, gateway, RHOAI, or model-serving behavior, check `BACKLOG.md` for known workarounds. Do not remove workaround code only because it looks redundant.

## Static Validation

When available locally:
- **kube-linter** - best practices + security checks
- **kubeconform** - Kubernetes schema validation
- **`oc apply --dry-run=server`** - validates against live cluster including CRDs

## References

- [How to manage RHOAI dependencies with Kustomize and Argo CD](https://developers.redhat.com/articles/2026/03/13/manage-openshift-ai-dependencies-kustomize-argo-cd)
- [odh-gitops repository](https://github.com/opendatahub-io/odh-gitops)
- [Red Hat OpenShift GitOps 1.21 documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/1.21) (version per `.agents/references/red-hat-doc-map.yaml`)
- [Kubernetes Recommended Labels](https://kubernetes.io/docs/concepts/overview/working-with-objects/common-labels/)
- [Guidelines for Labels and Annotations for OpenShift Applications](https://github.com/redhat-developer/app-labels/blob/master/labels-annotation-for-openshift.adoc)
