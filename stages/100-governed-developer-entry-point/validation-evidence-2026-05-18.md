# Stage 100 Validation Evidence

## Stage

100 - Governed Developer Entry Point

## Date

2026-05-18

## Environment

- Platform repository branch: `feature/vibe-agentic-workflow-readmes`
- Inventory repository branch: `feature/coolstore-inventory-service-plan`
- Inventory repository checkpoint: `246601d`
- Cluster: `cluster-t977r`
- Validation mode: live cluster plus static repository checks
- Route hostnames, credentials, tokens, API keys, and kubeconfigs: omitted

## Branch Checkpoint

The Stage 070 and Stage 090 Argo CD applications are synced from
`feature/vibe-agentic-workflow-readmes` in the sandbox cluster only. The branch
has not been merged to `main`, and Stage 100 has not been added to
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
./scripts/validate-stage-flow.sh
Stage flow static validation passed

bash -n scripts/*.sh
passed

bash -n stages/*/*.sh
passed

git diff -- flows/default.yaml
no diff
```

```text
./stages/070-controlled-developer-workspaces/validate.sh
VALIDATION: 30 passed, 0 warnings, 0 failed

./stages/090-developer-portal-self-service/validate.sh
VALIDATION: 19 passed, 0 warnings, 0 failed
```

## Developer Hub Evidence

- Developer Hub route reachable: yes, hostname omitted
- Stage 090 Argo CD application: `Synced` and `Healthy`
- Runtime catalog generated from the feature branch: yes
- Runtime catalog contains:
  - `System:default/coolstore`
  - `Component:default/getting-started-ai-coding`
  - `Component:default/coolstore`
  - `Component:default/coolstore-inventory-service`
  - `Resource:default/maas-private-code-model-nemotron`
- Component link cards contain only:
  - `Source Repo`
  - `Dev Spaces`
  - `Getting Started`
- Component source mappings:
  - `getting-started-ai-coding`: `adnan-drina/getting-started-ai-coding`
  - `coolstore`: `rhpds/mca-coolstore`
  - `coolstore-inventory-service`: `adnan-drina/coolstore-inventory-service`
- Component Dev Spaces links target single-repository factory URLs. The live
  Dev Spaces route hostname is generated at runtime and is not committed.

## Dev Spaces Evidence

- Dev Spaces route reachable: yes, hostname omitted
- Stage 070 Argo CD application: `Synced` and `Healthy`
- CheCluster phase: `Active`
- `wksp-ai-developer/getting-started-ai-coding` phase: `Running`
- `wksp-ai-developer/coolstore-inventory-service` phase: `Stopped`
- `wksp-ai-developer/mca-coolstore` phase: `Stopped`
- All three workspaces exist and none are failed.
- GitOps workspace definitions contain exactly one project each:
  - `getting-started-ai-coding`
  - `coolstore-inventory-service`
  - `mca-coolstore`
- Running onboarding workspace project directories:
  - `/projects/getting-started-ai-coding`
- Continue local config present: yes
- OpenCode local config present: yes
- OpenCode compatibility path present: yes
- Continue config contains MCP/OpenShift references: yes
- OpenCode config contains MCP/OpenShift references: yes

## Model Path Evidence

- Selected source-code model: `nemotron-3-nano-30b-a3b`
- GPU MachineSet: desired `2`, ready `2`
- GPU nodes: two nodes ready
- Private model pods:
  - `gpt-oss-20b`: `2/2 Running`
  - `nemotron-3-nano-30b-a3b`: `2/2 Running`
- `LLMInferenceService` Ready condition:
  - `gpt-oss-20b`: `False`, reason `SchedulerReconcileError`
  - `nemotron-3-nano-30b-a3b`: `False`, reason
    `SchedulerReconcileError`
- Observed controller message: scheduler reconciliation failed while validating
  generated `InferencePool.spec.endpointPickerRef`, reporting that `port` is
  required for a Service endpoint picker reference.
- Live `InferencePool` objects currently include endpoint picker port `9002`
  and target port `8000`, so the failure appears to be a controller
  reconciliation/status issue rather than missing running model pods.
- Continue template default path: MaaS endpoint for
  `nemotron-3-nano-30b-a3b`
- OpenCode template default model: `nemotron/nemotron-3-nano-30b-a3b`
- Secrets committed: no

## Client Verification Status

The current refreshed onboarding workspace contains placeholder MaaS values in
both local client configuration files:

- `~/.continue/config.yaml`
- `~/.config/opencode/opencode.json`

This is expected after workspace recreation because the templates do not contain
live routes or API keys. The developer must re-enter the MaaS route and API key
inside the workspace and rerun the harmless model and MCP prompts before Stage
100 can be marked green.

## Result

Yellow.

The governed platform entry path is validated: Developer Hub exposes the three
demo components, each component has a single-repository Dev Spaces link, the
workspace definitions are GitOps-managed, and the private model pods are
running on GPU nodes.

The remaining gates are:

- restore or explain the `LLMInferenceService` Ready condition for both private
  models;
- re-enter local MaaS credentials in the refreshed workspace configs;
- verify Continue and OpenCode with the harmless MaaS model prompt;
- verify Continue and OpenCode with the read-only OpenShift MCP prompt.

## Risks Or Gaps

- Live UI screenshots were not committed to avoid storing route hostnames or
  session details.
- Developer Hub and Dev Spaces route hostnames were observed but omitted from
  evidence.
- The current validation intentionally did not print or inspect API keys,
  tokens, or live route values from client config files.

## Next Gate

Before Stage 110 starts, resolve the private model status discrepancy, then
reconfigure the refreshed `getting-started-ai-coding` workspace local client
files with the MaaS route and API key and verify:

- Continue harmless MaaS prompt: pass/fail
- OpenCode harmless MaaS prompt: pass/fail
- Continue read-only OpenShift MCP prompt: pass/fail
- OpenCode read-only OpenShift MCP prompt: pass/fail

Stage 110 can start after those four client checks are green.
