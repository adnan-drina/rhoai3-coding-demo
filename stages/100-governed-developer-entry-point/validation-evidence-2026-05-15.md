# Stage 100 Validation Evidence

> Superseded note: this evidence records the earlier shared `exercises`
> workspace validation. The current Stage 100 design uses three separate
> single-repository Developer Hub components and Dev Spaces workspaces:
> `getting-started-ai-coding`, `coolstore-inventory-service`, and
> `mca-coolstore`.

## Stage

100 - Governed Developer Entry Point

## Date

2026-05-15

## Environment

- Repository branch: `feature/vibe-agentic-workflow-readmes`
- Application repository branch: `feature/coolstore-inventory-service-plan`
- Cluster: `cluster-t977r`
- Validation mode: live cluster
- Route hostnames, credentials, tokens, and API keys: omitted

## Branch Checkpoint

The Stage 070 and Stage 090 Argo CD applications were validated from
`feature/vibe-agentic-workflow-readmes` in the sandbox cluster only. The branch
was not merged to `main`, and Stage 100 was not added to
`../../flows/default.yaml`.

Rollback to `main`:

```bash
oc patch application 070-controlled-developer-workspaces -n openshift-gitops --type=merge -p '{"spec":{"source":{"targetRevision":"main"}}}'
oc patch application 090-developer-portal-self-service -n openshift-gitops --type=merge -p '{"spec":{"source":{"targetRevision":"main"}}}'
oc annotate application 070-controlled-developer-workspaces -n openshift-gitops argocd.argoproj.io/refresh=hard --overwrite
oc annotate application 090-developer-portal-self-service -n openshift-gitops argocd.argoproj.io/refresh=hard --overwrite
```

## Commands And Results

```text
./stages/090-developer-portal-self-service/validate.sh
VALIDATION: 17 passed, 0 warnings, 0 failed

./stages/070-controlled-developer-workspaces/validate.sh
VALIDATION: 17 passed, 1 warnings, 0 failed
```

The Stage 070 warning is expected for this validation pass because
`wksp-ai-developer/exercises` was started for the Stage 100 flow. The warning
reported `Running` instead of the default stopped workspace state, with no
failed checks.

```text
./scripts/resume-gpu-demo.sh status
GPU MachineSets: desired 2, ready 2
Private models ready: gpt-oss-20b, nemotron-3-nano-30b-a3b

./scripts/validate-stage-flow.sh
Stage flow static validation passed
```

## Developer Hub Evidence

- Developer Hub route reachable: yes, hostname omitted
- Frontend catalog entity routes returned HTTP 200:
  - `System:default/coolstore`
  - `Component:default/coolstore`
  - `Component:default/coolstore-inventory-service`
  - `Resource:default/maas-private-code-model-nemotron`
- Catalog backend contained all four expected entity refs:
  - `system:default/coolstore`
  - `component:default/coolstore`
  - `component:default/coolstore-inventory-service`
  - `resource:default/maas-private-code-model-nemotron`
- Unauthenticated catalog API requests returned HTTP 401, which is expected
  because Developer Hub is configured with OIDC sign-in.
- Developer Hub logs no longer showed the raw GitHub catalog allow-list error
  after adding `backend.reading.allow` for `raw.githubusercontent.com`.

## Dev Spaces Evidence

- Dev Spaces route reachable: yes, hostname omitted
- `wksp-ai-developer/exercises` phase: `Running`
- Workspace pod state: running
- Workspace project directories observed:
  - `/projects/mca-coolstore`
  - `/projects/coolstore-inventory-service`
- Continue configuration present at `~/.continue/config.yaml`
- OpenCode configuration present at `~/.config/opencode/opencode.json`
- OpenCode compatibility path present at `~/.opencode/opencode.json`
- Follow-up client check: Stage 100 now requires both Continue and OpenCode to
  complete a harmless MaaS verification prompt after the developer inserts the
  MaaS route and API key into the local workspace configs. The running workspace
  configs still contained placeholders when this follow-up check was added, so
  no client request was marked as passed.
- Older `/projects/coolstore` and `/projects/coding-exercises` directories
  from the persistent workspace volume were removed after validation so the
  workspace now shows only the current `mca-coolstore` and
  `coolstore-inventory-service` projects. The stale `coding-exercises`
  directory was archived locally before removal because it contained
  uncommitted workspace edits.

## Model Path Evidence

- Selected source-code model: `nemotron-3-nano-30b-a3b`
- Private MaaS model readiness: ready
- Continue template default path: MaaS endpoint for `nemotron-3-nano-30b-a3b`
- OpenCode template default model: `nemotron/nemotron-3-nano-30b-a3b`
- Secrets committed: no

## Result

Yellow under the updated Stage 100 client-verification bar.

The Developer Hub to Dev Spaces entry path is validated: Developer Hub exposes
the Coolstore system, brownfield source, target service, and private MaaS model
resource; the governed Dev Spaces workspace opens; and the private MaaS model
path is selected for source-code work.

The remaining Stage 100 gate is client-level verification: after the developer
places the MaaS route and API key into the local workspace config files,
Continue and OpenCode must each complete a harmless prompt against
`nemotron-3-nano-30b-a3b` through MaaS.

## Risks Or Gaps

- The validation used backend catalog state and frontend route reachability
  rather than committing screenshots, to avoid storing route hostnames or
  session details.
- Developer Hub component links are intentionally limited to source repository,
  Dev Spaces, and one getting started guide. The live Dev Spaces URL is
  generated into the runtime catalog from the cluster route and is not committed
  to Git.
- Human UI validation confirmed that both Coolstore component link cards show
  only `Source Repo`, `Dev Spaces`, and `Getting Started`, and that the
  `Dev Spaces` link opens the workspace path.

## Next Gate

The Stage 100 vibe-coding exercise can continue after the developer configures
the running workspace clients, verifies them with a harmless MaaS prompt, and
uses the private MaaS model for bounded README/API/test alignment work.
