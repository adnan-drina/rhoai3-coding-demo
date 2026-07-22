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
- `.agents/skills/validate-demo-step/SKILL.md`

## Golden Rule

Every implemented demo stage must be reproducible from `gitops/` and operated through `deploy.sh` / `validate.sh` scripts. The README explains the demo value; `docs/OPERATIONS.md` explains operational usage.

## Mandatory: ArgoCD Application in Every deploy.sh

Every stage's `deploy.sh` MUST apply its ArgoCD Application as its first cluster-modifying action:
```bash
oc apply -f "$REPO_ROOT/gitops/argocd/app-of-apps/$STAGE_NAME.yaml"
```

Every stage MUST have:
1. `gitops/stages/NNN-name/base/` - Kustomize manifests
2. `gitops/argocd/app-of-apps/NNN-name.yaml` - ArgoCD Application
3. `stages/NNN-name/deploy.sh` - applies the ArgoCD Application
4. `stages/NNN-name/validate.sh` - verifies deployment
5. `stages/NNN-name/README.md` - educational narrative

**Never** apply manifests directly with `oc apply -k` for ArgoCD-managed resources.

## Repository Layout

```text
rhoai3-coding-demo/
|-- gitops/
|   |-- argocd/
|   |   `-- app-of-apps/
|   `-- stages/
|       `-- NNN-descriptive-name/
|           `-- base/
|-- stages/
|   `-- NNN-descriptive-name/
|       |-- deploy.sh
|       |-- validate.sh
|       `-- README.md
|-- scripts/
|-- docs/
`-- README.md
```

## Kustomize Structure

- Prefer `base/` + `overlays/<env-or-purpose>/` within each stage.
- Keep `base/` environment-agnostic; put deltas in overlays.
- Avoid duplicating full resources across overlays; use patches.
- Use `components:` for optional/selectable operators (not `resources:`).

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
| `ServerSideDiff` | `true` | Accurate diff for custom CRDs |
| `RespectIgnoreDifferences` | `true` | Enables ignoreDifferences with ServerSideDiff |

**Do NOT use:** `ServerSideApply=true` or `Replace=true`.

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

Stages 060, 070, and 080 are workflow-only: they have no Argo CD Application and no `deploy.sh`. Their `validate.sh` scripts validate against resources owned by the `050-advanced-app-platform` Argo CD Application.

Stage 050 is a multi-component owner managing: devspaces, pipelines, sonarqube, rhdh, migiq (MTA), and coolstore resources.

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
