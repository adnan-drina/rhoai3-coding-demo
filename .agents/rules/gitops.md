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

Every stage's `deploy.sh` applies its Argo CD Applications as its first cluster-modifying action, pinned to one reviewed published commit:
```bash
python3 "$REPO_ROOT/scripts/shared/stage_apps.py" applications NNN --revision "$SHA" --repo-url "$GIT_REPO_URL" | oc apply -f -
```

Every GitOps stage (`stages/NNN-name/deploy.sh` present) MUST have:
1. `gitops/stages/NNN-name/<component>/` - one folder per Argo CD Application (its `source.path`)
2. `gitops/stages/NNN-name/kustomization.yaml` - the union of the component folders (validators and `check-static` read it)
3. `gitops/argocd/app-of-apps/NNN-name/<component>.yaml` - one Application per component, named `NNN-<component>`
4. `stages/NNN-name/deploy.sh` - applies the Applications
5. `stages/NNN-name/validate.sh` - verifies deployment
6. `stages/NNN-name/README.md` - educational narrative

Stage 070 still uses the earlier single-Application layout (`gitops/argocd/app-of-apps/070-advanced-app-platform.yaml` rendering `gitops/stages/070-advanced-app-platform/base/`); `validate-stage-flow.sh` accepts both.

### Component Applications

- Each Application carries the stage prefix and label (`demo.rhoai.io/stage: 'NNN'`) and exactly one of:
  - `demo.rhoai.io/deploy-order: '<n>'`: deployed by the stage `deploy.sh` with the other ordered components, all at one revision; validation requires each Synced and Healthy at that revision (`stage_apps.py status`).
  - `demo.rhoai.io/deploy-script: stages/NNN-name/<script>.sh`: deployed by that script with its own procedure and revision (for example the Stage 060 Applications and `010-sandbox-storage`).
- A component that reports another health state by design names it in `demo.rhoai.io/accepted-health`.
- Components are disjoint (one owner per object, including singletons). `scripts/shared/stage_apps.py check-static NNN` enforces this and that their union equals the stage kustomization; `validate-stage-flow.sh` runs it.
- Group by lifecycle: operators, data (Prune=false,Delete=false), fast-changing content (models, access policies) and shared configuration each get their own component.
- Moving objects between Applications, renaming one or changing its `source.path` never deletes them: use `scripts/platform/move-applications.py` (skill `gitops-move-applications`).

Workflow-only stages omit `deploy.sh` and have no Argo CD Application. `./scripts/platform/validate-stage-flow.sh` walks `stages/*/`, requires `validate.sh`, and checks every Application's name, stage label and source path.

**Never** apply manifests directly with `oc apply -k` for ArgoCD-managed resources.

## Repository Layout

```text
rhoai3-coding-demo/
|-- gitops/
|   |-- argocd/app-of-apps/NNN-name/<component>.yaml
|   |-- bootstrap/
|   `-- stages/NNN-name/
|       |-- kustomization.yaml          # union of the component folders
|       `-- <component>/                # one folder per Application
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
- A further unit inside a component (a Job with its RBAC, a dashboard generator, each operator of a multi-operator component) gets its own subfolder with its own `kustomization.yaml`.
- No `base/`-in-`base/` wrappers, no `aggregate/` layers, no placeholder values patched by an overlay: write the reviewed value (for example the Subscription channel) in the manifest.
- Add `overlays/<variant>/` only for a real variant, and `components/<feature>/` (Kustomize `kind: Component`) for an optional feature.
- Transformers (`labels`, `replacements`) belong in the component's `kustomization.yaml`, where they apply to the whole Application.
- Cluster-specific generated files live in their component folder (Stage 020 `gpu-machinesets/`, written by `generate-gpu-machineset.sh`).

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

- Argo CD uses the destination namespace only as the default for objects that omit one, and as the namespace in a cluster-scoped object's tracking id (`<app>:<group>/<Kind>:<destination>/<name>`). One fixed value keeps tracking ids predictable for scripts and the move tool; it is not where the workload runs.
- Changing an existing Application's destination re-keys the tracking ids of its cluster-scoped objects: do it with `scripts/platform/move-applications.py`, never by editing the live Application.
- `validate-stage-flow.sh` enforces both rules for component Applications (`stage_apps.CLUSTER_SCOPED` lists the cluster-scoped kinds that may omit a namespace). Stage 070's legacy Application is not yet covered.

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

**Do NOT use:** `ServerSideApply=true` or `Replace=true`.

### Server-Side Diff
Enable it with the Application annotation `argocd.argoproj.io/compare-options: ServerSideDiff=true` (accurate diff for CRDs, defaulted fields and admission mutations). A `ServerSideDiff=true` entry in `syncPolicy.syncOptions` does **not** enable it: Argo CD reads diff strategy only from this annotation or the global `controller.diff.server.side` setting, which this repository does not set. An Application that needs client-side comparison sets `ServerSideDiff=false` in the annotation with the reason in its commit (for example `060-openshell-runtime`, 30466007).

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

Stages 110, 120, and 130 are workflow-only: they have no Argo CD Application and no `deploy.sh`. Their `validate.sh` scripts validate against resources owned by the `070-advanced-app-platform` Argo CD Application.

Stage 070 is a multi-component owner managing: identity (platform RHBK), devspaces, pipelines, sonarqube, rhdh, mta, and coolstore resources.

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
- [OCP 4.20 - OpenShift GitOps](https://docs.redhat.com/en/documentation/openshift_container_platform/4.20/html/cicd/gitops)
- [Kubernetes Recommended Labels](https://kubernetes.io/docs/concepts/overview/working-with-objects/common-labels/)
- [Guidelines for Labels and Annotations for OpenShift Applications](https://github.com/redhat-developer/app-labels/blob/master/labels-annotation-for-openshift.adoc)
