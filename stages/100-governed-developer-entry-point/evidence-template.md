# Stage 100 Evidence Template

Use this template when validating Stage 100. Do not paste credentials, API keys,
kubeconfigs, model tokens, or full private cluster route hostnames into this
file.

## Stage

100 - Governed Developer Entry Point

## Date

YYYY-MM-DD

## Environment

- Repository branch: `feature/vibe-agentic-workflow-readmes`
- Application repository branch: `feature/coolstore-inventory-service-plan`
- Cluster: `cluster-t977r`
- Validation mode: live cluster

## Sources Reviewed

- `stages/100-governed-developer-entry-point/README.md`
- `stages/070-controlled-developer-workspaces/README.md`
- `stages/090-developer-portal-self-service/README.md`
- `docs/DEVELOPER_WORKSPACE_GUIDE.md`
- `gitops/stages/090-developer-portal-self-service/base/catalog/all.yaml`
- `gitops/stages/070-controlled-developer-workspaces/base/devspaces/workspaces.yaml`
- `/Users/adrina/Sandbox/coolstore-inventory-service/catalog-info.yaml`

## Commands Or Actions

```bash
./stages/090-developer-portal-self-service/validate.sh
./stages/070-controlled-developer-workspaces/validate.sh
./scripts/resume-gpu-demo.sh status
oc get devworkspace exercises -n wksp-ai-developer
```

Manual actions:

- Open Red Hat Developer Hub from the OpenShift console launcher or known route.
- Confirm the Coolstore system, brownfield component, target service component,
  and private MaaS model resource are visible.
- Open Red Hat OpenShift Dev Spaces.
- Start or open `wksp-ai-developer/exercises`.
- Confirm the workspace includes `mca-coolstore` and `coolstore-inventory-service`.
- Confirm the private source-code model path is `nemotron-3-nano-30b-a3b`
  through MaaS.

## Evidence

- Developer Hub route reachable: yes/no, hostname omitted
- Catalog entities visible:
  - `System:default/coolstore`: yes/no
  - `Component:default/coolstore`: yes/no
  - `Component:default/coolstore-inventory-service`: yes/no
  - `Resource:default/maas-private-code-model-nemotron`: yes/no
- Dev Spaces route reachable: yes/no, hostname omitted
- `wksp-ai-developer/exercises` phase:
- Private models ready:
  - `nemotron-3-nano-30b-a3b`: yes/no
  - `gpt-oss-20b`: yes/no
- Secrets committed: no

## Result

Green/yellow/red:

## Risks Or Gaps

- 

## Next Gate

Stage 110 can start only after the developer has a working governed workspace
and a recorded private model choice for source-code work.
