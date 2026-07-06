# Migration Plan: Foundation Stages from rhoai3-demo (rhoai34-refactoring)

Status: DRAFT — awaiting decisions on cleanup depth, numbering, models, extras.
Working doc for the 2026-07 pivot; delete after migration completes.

## Why

The rhoai3-coding-demo stages 010–060 were re-implemented in parallel with
rhoai3-demo. The rhoai3-demo `rhoai34-refactoring` branch has the same
foundational scope already implemented and validated, including fixes for
issues we hit live on cluster-j98ml (notably the RHOAI 3.4 / COO 1.5 Perses
datasource incompatibility, solved there by an install-time COO v1.4.0
lifecycle pin). Both demos share the same foundation up to RAG (their 230).

## Source → target mapping

| rhoai3-demo (source) | Covers | rhoai3-coding-demo (target) |
|---|---|---|
| stage-110-rhoai-base-platform | GitOps bootstrap, ODF/MCG object storage, observability operators (COO 1.4 pin), RHOAI operator, DSCI/DSC, access | replaces 010 |
| stage-120-gpu-as-a-service | GPU MachineSet, NFD, GPU operator, Kueue, KEDA | replaces 020 |
| stage-210-model-serving-foundation | DSC serving config, benchmark data, monitoring, Grafana | replaces 030 |
| stage-220-models-as-a-service | Gateway/Kuadrant governance, tenant, local models (nemotron), external models (gpt-4o-mini), MCP (openshift-mcp), policies, database | replaces 040 + 050 + 060 |

Their layout: `stage-XXX-name/` (deploy.sh, validate.sh, README, PLAN) +
`gitops/stage-XXX-name/` + `gitops/argocd/app-of-apps/` + `gitops/bootstrap/`.
deploy.sh sets Argo repoURL/targetRevision from .env (GIT_REPO_URL/BRANCH) —
more flexible than our sed-based fork handling; adopt it.

## Environment cleanup (current cluster-j98ml)

Deployed so far: GitOps operator + Argo (bootstrap), stage 010 (RHOAI 3.4.2,
monitoring w/ COO 1.5.1, users, registry), stage 020 (NFD, GPU operator,
Kueue, KEDA, LWS, 2x g6e.2xlarge GPU nodes), stage 030 partial (nemotron
serving, qwen pulling), plus live workaround objects (tempo-datasource).

Two options:
- A. Fresh RHDP sandbox (RECOMMENDED): the rhoai3-demo design assumes COO
  v1.4.0 from clean install; the current cluster already has COO 1.5.1 CSV
  and CRDs (downgrade unsupported). Surgical RHOAI+COO+GitOps uninstall is
  slow and error-prone. Immediate cost action either way: scale the GPU
  MachineSet to 0.
- B. Surgical uninstall: delete stage Argo apps (030, 020, 010 in reverse),
  GPU MachineSet, DSC/DSCI, RHOAI operator+namespaces, COO/OTel/Tempo
  operators + CRDs, Kueue/KEDA/NFD/GPU/LWS operators, GitOps operator, OAuth
  IdP entry, groups. Higher residual-state risk.

## Repo migration steps (after decisions)

1. Snapshot current state: branch `pre-foundation-migration` at current main.
2. Copy from rhoai3-demo@rhoai34-refactoring:
   - `gitops/bootstrap/` → ours (replaces scripts/bootstrap.sh logic)
   - `gitops/argocd/` app-of-apps + projects for the four stages
   - `gitops/stage-110..220/` → target gitops dirs (renumbered per decision)
   - `stage-110..220/` scripts+README → target stages/ dirs
3. Adapt copied content:
   - repoURL default → rhoai3-coding-demo.git (their deploy.sh reads .env)
   - stage names/numbers per numbering decision; flows/default.yaml rewrite
   - keep our AGENTS.md validation conventions (validate-lib.sh exit codes)
     if their validate.sh differs — reconcile in step 5
4. Retire replaced content: delete old gitops/stages/010–060, stages/010–060,
   old app-of-apps entries; keep git history (snapshot branch).
5. Coding-demo deltas to port on top (per decisions):
   - Qwen3.6-35B-A3B FP8-dynamic as second local model + MaaS ref/policies
     (pattern-copy their nemotron files)
   - model registry + rich model-card seed job (our 030 asset)
   - demo users ai-admin/ai-developer if their `access/` differs
   - Slack/BrightData optional MCP components (our 060 asset)
   - coding-assistant namespace + GenAI playground MCP discovery
6. Reconcile consumers (unchanged stages 070–100): MaaS endpoint/base URLs,
   model names in key provisioning + Continue/OpenCode configs, MTA kai
   config, validation scripts, DEVELOPER_WORKSPACE_GUIDE.
7. Docs: README stage table, OPERATIONS, TROUBLESHOOTING (carry over their
   known-issues sections; keep ours that still apply), BACKLOG merge,
   AGENTS.md stage list, skills (manage-resources, resume-gpu-demo,
   rhoai-troubleshoot reference stage paths).
8. Validate: bash -n, validate-stage-flow.sh (adapt to new layout), then
   fresh-environment deploy 010→…→100 with per-stage validation.

## Open decisions (blocking)

1. Cleanup: fresh sandbox vs surgical uninstall of cluster-j98ml.
2. Numbering: renumber their stages into our 010/020/030/040 slots
   (050/060 retire, 070–100 unchanged) vs adopt their 110/120/210/220.
3. Models: keep Qwen3.6 as the coding-demo second local model, or match
   rhoai3-demo exactly (nemotron-only) first and add Qwen later.
4. Extras: which coding-demo-specific assets to port in the same pass
   (registry model cards, Slack/BrightData MCP, demo personas).
