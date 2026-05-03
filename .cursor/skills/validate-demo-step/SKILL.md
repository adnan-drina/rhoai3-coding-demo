---
name: validate-demo-step
metadata:
  author: rhoai3-coding-demo
  version: 1.1.0
description: >
  Validate a demo stage after changes. Use when a stage's deploy script,
  validate script, GitOps manifests, or Argo CD application changes. Produces
  static validation commands, stage-specific checks, and a clear statement of
  what was or was not validated against a live cluster. Do NOT use for
  troubleshooting failures (use rhoai-troubleshoot) or reviewing manifest
  quality (use manifest-reviewer agent or review-gitops-change skill).
---

# Validate Demo Stage

Use this skill after changing a demo stage to verify the change is correct
and complete.

## When to invoke

- A stage's `deploy.sh` or `validate.sh` changes
- GitOps manifests under `gitops/stages/NNN-name/` change
- The stage's Argo CD application definition changes
- A stage README claims new behavior that needs verification

## Inputs needed

- Stage number (010-090)
- List of changed files
- Whether a live OpenShift cluster is available

## Validation workflow

### Phase 1: Static validation (always possible)

```bash
# Script syntax check
bash -n stages/NNN-name/deploy.sh
bash -n stages/NNN-name/validate.sh
./scripts/validate-stage-flow.sh

# Kustomize render check
kustomize build gitops/stages/NNN-name/base/

# Dry-run against cluster (requires oc login)
kustomize build gitops/stages/NNN-name/base/ | oc apply --dry-run=server -f -
```

### Phase 2: Stage-specific validation (requires live cluster)

| Stage | Validation script | Key checks |
|------|-------------------|------------|
| 010 | `./stages/010-openshift-ai-platform-foundation/validate.sh` | RHOAI operator, DSC, DSCI, dashboard |
| 020 | `./stages/020-gpu-infrastructure-private-ai/validate.sh` | GPU nodes, NFD, NVIDIA operator |
| 030 | `./stages/030-private-model-serving/validate.sh` | Local model serving resources |
| 040 | `./stages/040-governed-models-as-a-service/validate.sh` | MaaS API, local model refs, gateway, governance |
| 050 | `./stages/050-approved-external-model-access/validate.sh` | ExternalModel resources and external subscriptions |
| 060 | `./stages/060-mcp-context-integrations/validate.sh` | MCP server registrations and credential-gated runtimes |
| 070 | `./stages/070-controlled-developer-workspaces/validate.sh` | Dev Spaces operator, workspaces, coding tools |
| 080 | `./stages/080-ai-assisted-application-modernization/validate.sh` | MTA operator, Tackle, Developer Lightspeed |
| 090 | `./stages/090-developer-portal-self-service/validate.sh` | RHDH operator, Backstage CR, catalog |

### Phase 3: Cross-stage verification

- Does this change affect downstream stages?
- Are Argo CD sync waves still ordered correctly?
- Does the stage table in `README.md` still match?

## Completeness checklist

After validation, verify:

- [ ] `deploy.sh` applies the Argo CD Application as its first cluster-modifying action
- [ ] `validate.sh` uses `validate-lib.sh` with `check` and `validation_summary`
- [ ] Argo CD Application has `project: rhoai-demo`
- [ ] Argo CD Application has required labels and annotations
- [ ] `kustomization.yaml` lists all resource files
- [ ] No orphaned manifests in the directory
- [ ] README explains the stage's value in the project storyline, not just commands
- [ ] README's `What This Stage Adds` section uses one short capability sentence plus roughly four to six bullets
- [ ] README's `What This Stage Adds` section is concise, capability-oriented, and not a manifest inventory, deployment trace, or workaround ledger
- [ ] README's `What This Stage Adds` section avoids per-bullet manifest links, YAML field paths, probe timings, patch jobs, sync hooks, generated resource names, and low-level operational caveats
- [ ] README's `How Red Hat And Open Source Make It Work` section is concise, product-oriented, and does not duplicate the product or open source inventory lists
- [ ] README's `How Red Hat And Open Source Make It Work` section preserves important support-posture or demo-deviation notes without turning into operational detail
- [ ] README follows the stage README section order, with `What To Notice And Why It Matters` after `What This Stage Adds`
- [ ] README carries stage continuity through the narrative, architecture diagram, trust boundary, and `Next Stage` link instead of a dedicated `Where This Fits In The Full Platform` section
- [ ] README places `Trust Boundaries`, when present, before `Red Hat Products Used`
- [ ] README's `What To Notice And Why It Matters` section is concise, architect-friendly, and grounded in relevant Red Hat references
- [ ] README's `What To Notice And Why It Matters` section emphasizes enterprise significance, privacy, sovereignty, and trust boundaries where relevant
- [ ] README avoids over-emphasizing later-stage plans when a general enterprise use case would be clearer
- [ ] README uses external Red Hat blogs/docs as alignment and references, not as the opening narrative voice
- [ ] README's `Trust Boundaries` section, when present, is one focused paragraph
- [ ] README's trust-boundary language distinguishes private model, governed external model, and MCP/tool-context boundaries where relevant
- [ ] README's EU AI Act language is framed as readiness/supporting controls, not compliance
- [ ] `docs/OPERATIONS.md` reflects any new operational behavior
- [ ] `docs/TROUBLESHOOTING.md` covers new failure modes if applicable

## Output format

```markdown
## Stage validation: NNN-name

### Static validation
- bash -n: [PASS/FAIL]
- kustomize build: [PASS/FAIL]
- dry-run: [PASS/FAIL/SKIPPED — no cluster]

### Stage validation script
- [PASS/FAIL/SKIPPED — no cluster]

### Completeness
- [checklist results]

### Live cluster status
- [Validated against live cluster / Not validated — static review only]

### Issues found
- [list, or "None"]
```

## Honesty requirement

If a live OpenShift cluster is required and not available, say:

> Not validated against a live OpenShift cluster. Static review only.

Do not claim validation passed based on static checks alone when the change
involves runtime behavior (model serving, operator reconciliation, gateway
routing, workspace creation).
