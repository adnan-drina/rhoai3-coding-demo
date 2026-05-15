# Developer Workflow Stage Validation Runbook

This runbook prepares the planned developer workflow stages for staged testing without
promoting them into the executable platform flow.

Stages `100-170` are still documentation-only. Do not add them to
`flows/default.yaml`, do not create executable `stages/100-*` directories, and do
not register GitOps or Argo CD applications for these stages until the related
artifacts have been implemented and validated.

## Validation Goal

Validate the new developer workflow one stage at a time, preserving a clear line
between:

- platform stages `010-090`, which remain the executable demo foundation;
- planned workflow stages `100-170`, which are currently manual, static, or
  lab-driven validation exercises;
- the application repository, currently
  `/Users/adrina/Sandbox/coding-exercises`, which is the future
  `coolstore-inventory-service` source repository.

Each stage should produce enough evidence to answer four questions:

1. What was tested?
2. Which sources, prompts, tools, and cluster resources were used?
3. What passed, failed, or remained static-only?
4. What must be true before the next stage can be treated as live demo content?

## Global Guardrails

- Use only the `rhoai3-coding-demo` environment and the `cluster-t977r` OpenShift
  cluster for this workflow.
- Do not use the parallel `rhoai3-demo` environment or `cluster-v2zvn` cluster.
- Do not commit kubeconfigs, tokens, passwords, screenshots with secrets, model
  API keys, or private source content.
- Keep stages `100-170` out of `flows/default.yaml`.
- Keep app-local delivery assets in the application repository, not in the
  platform stage flow.
- Record static-only validation explicitly as:
  `Not validated against a live cluster. Static review only.`
- Stop when a stage fails in a way that downstream stages depend on.

## Baseline Preflight

Run these checks before starting stage validation.

### Platform Repository

From `/Users/adrina/Sandbox/rhoai3-coding-demo`:

```bash
git status --short --branch
git diff -- flows/default.yaml
./scripts/validate-stage-flow.sh
bash -n scripts/*.sh
bash -n stages/*/*.sh
```

Expected result:

- the working branch is the developer workflow planning branch;
- `flows/default.yaml` has no diff;
- existing platform stage validation still covers only `010-090`;
- shell syntax checks pass.

### Cluster Context

Confirm the active OpenShift context before running live checks:

```bash
oc whoami --show-server
oc whoami
./scripts/resume-gpu-demo.sh status
```

Expected result:

- the API server is the `cluster-t977r` environment;
- the authenticated user has enough access for validation;
- GPU nodes and model serving status are visible when model-backed stages are
  being tested.

When the GPU/model stages are needed, validate the foundation first:

```bash
./stages/020-gpu-infrastructure-private-ai/validate.sh
./stages/030-private-model-serving/validate.sh
```

### Application Repository

From `/Users/adrina/Sandbox/coding-exercises`:

```bash
git status --short --branch
./mvnw -B test
./mvnw -B package
git diff --check
oc kustomize gitops/overlays/dev
```

Expected result:

- the working branch is the `coolstore-inventory-service` planning branch;
- the Quarkus service builds and tests locally;
- app-local GitOps renders without requiring Argo CD registration;
- no live deployment is implied by static rendering.

## Evidence Format

For each stage, capture a short note with these fields:

```markdown
## Stage
## Date
## Environment
## Sources Reviewed
## Validation Mode
## Commands Or Actions
## Evidence
## Result
## Risks Or Gaps
## Next Gate
```

Evidence can include command output summaries, PR links, PipelineRun names,
rendered manifest summaries, image digests, model endpoint names, prompt packets,
and human review notes. Do not store raw credentials or private tokens.

## Validation Modes

Use the lightest mode that proves the stage claim.

- **Static**: documentation, configuration, YAML, JSON, and local build checks.
- **Assisted workflow dry run**: a human runs the prompt or agent task and reviews
  the proposed diff before accepting it.
- **Live cluster**: OpenShift, Dev Spaces, Developer Hub, model serving, MTA,
  Pipelines, or other cluster-backed resources are exercised directly.
- **Evidence review**: supply-chain, modernization, or agentic-control claims are
  evaluated from generated reports and review decisions.

## Stage 100: Governed Developer Entry Point

Stage 100 validates the entry point from the platform into a governed developer
workflow.

### Analysis Gate

Review:

- `docs/developer-workflow/100-governed-developer-entry-point.md`
- `docs/developer-workflow/coding-exercises-app-repo-plan.md`
- `docs/developer-workflow/readme-completion-alignment-review.md`
- Stage `070` Dev Spaces documentation and validation output
- Stage `090` Developer Hub documentation and validation output
- current app repository README and `catalog-info.yaml`

### Validation

Check that:

- the target repository is described as the future
  `coolstore-inventory-service`;
- the service identity, owner, lifecycle, and system metadata are clear;
- the developer path starts from approved platform entry points;
- any Developer Hub catalog registration is labeled as pending unless it exists;
- Dev Spaces and model endpoint references use governed platform routes.

Live validation requires Developer Hub and Dev Spaces to be reachable. If catalog
registration has not been performed, record this stage as static-only.

### Evidence

Capture:

- Developer Hub route or static registration blocker;
- catalog entity details or planned metadata;
- Dev Spaces workspace URL or launch blocker;
- selected model path and access pattern.

## Stage 110: Enterprise Vibe Coding With Continue

Stage 110 validates README, API, and test-plan alignment through Continue while
keeping human review in control.

### Analysis Gate

Review:

- `docs/developer-workflow/110-enterprise-vibe-coding-with-continue.md`
- app repository README and service API docs
- app repository Continue task documentation
- model endpoint and MaaS access notes from stages `030-050`
- Dev Spaces and Continue setup notes

### Validation

Check that:

- Continue uses the governed model endpoint selected for the demo;
- the prompt is bounded to README, API, and test-plan alignment;
- no credentials or private cluster tokens are pasted into the prompt;
- output is treated as a proposed review artifact, not automatically accepted.

Run the Continue alignment task in the app repository when the workspace is
available. Capture the proposed gaps or diff, then run local validation before
accepting any change.

### Evidence

Capture:

- prompt packet used;
- selected model endpoint;
- generated review notes or diff summary;
- local validation commands and results;
- human accept/reject decision.

## Stage 120: Quality Bar Breakpoint

Stage 120 demonstrates where broad AI assistance is insufficient without an
enterprise quality bar.

### Analysis Gate

Review:

- `docs/developer-workflow/120-quality-bar-breakpoint.md`
- Continue output from Stage 110
- app repository test plan
- service README and API contract
- known quality gates in `AGENTS.md`

### Validation

Check that:

- a plausible but flawed AI-generated change is identified;
- the failure is caught by tests, documentation review, API review, or human
  review;
- the reason for rejection is documented in enterprise engineering terms.

The goal is not to create a broken commit. Keep the failure as a review note or
throwaway branch unless explicitly asked to preserve it.

### Evidence

Capture:

- the near-miss prompt or proposed change summary;
- the quality gate that caught it;
- the human review decision;
- the rule or test that should prevent recurrence.

## Stage 130: Agentic Engineering With OpenCode

Stage 130 validates bounded agentic engineering using repo-local instructions,
skills, and path boundaries.

### Analysis Gate

Review:

- `docs/developer-workflow/130-agentic-engineering-with-opencode.md`
- app repository `AGENTS.md`
- app repository `.opencode/` configuration
- planned OpenCode reservation endpoint task
- Stage 120 quality decision

### Validation

Check that:

- OpenCode reads and follows app repository rules;
- the task is bounded to `POST /api/inventory/{itemId}/reservations`;
- expected file paths and write boundaries are explicit;
- the agent produces a plan before editing;
- tests and README/API alignment are updated together.

Run this as an assisted workflow dry run first. Only keep changes after human
review and local validation.

### Evidence

Capture:

- OpenCode task prompt;
- proposed plan;
- changed file summary;
- `./mvnw -B test` result;
- human review notes.

## Stage 140: Golden Path Quarkus Service

Stage 140 validates the Quarkus service scaffold and baseline API contract.

### Analysis Gate

Review:

- `docs/developer-workflow/140-golden-path-quarkus-service.md`
- `docs/developer-workflow/quarkus-target-service-options.md`
- app repository `pom.xml`
- app repository source and test layout
- app repository README

### Validation

Check that:

- the service uses Red Hat build of Quarkus `3.27.x` and Java 21;
- the package is `com.redhat.coolstore.inventory`;
- initial APIs exist:
  - `GET /api/inventory`
  - `GET /api/inventory/{itemId}`
  - `GET /api/inventory/{itemId}/availability`
- no PostgreSQL runtime dependency is claimed in this slice;
- tests and packaging pass locally.

Commands:

```bash
./mvnw -B test
./mvnw -B package
```

Optional local smoke test:

```bash
./mvnw quarkus:dev
curl -s http://localhost:8080/api/inventory
curl -s http://localhost:8080/api/inventory/329299/availability
```

### Evidence

Capture:

- Quarkus and Java baseline;
- command results;
- endpoint smoke output summary when run;
- README/API/test-plan alignment status.

## Stage 150: Governed Pipeline And Deployment

Stage 150 validates the selected delivery path: Pipelines-as-Code, Buildah,
OpenShift internal registry, and app-local GitOps.

### Analysis Gate

Review:

- `docs/developer-workflow/150-governed-pipeline-and-deployment.md`
- `docs/developer-workflow/delivery-path-decision-record.md`
- app repository `.tekton/pull-request.yaml`
- app repository `Containerfile`
- app repository `gitops/base`
- app repository `gitops/overlays/dev`

### Validation

Static checks:

```bash
git diff --check
oc kustomize gitops/overlays/dev
```

Parse `.tekton/pull-request.yaml` as YAML with the available local tooling.

Live checks require OpenShift Pipelines and Pipelines-as-Code to be installed and
configured. When available, validate:

- a `Repository` custom resource exists for the app repo in
  `coolstore-inventory-dev`;
- pull requests to `main` trigger the PipelineRun;
- the pipeline runs `./mvnw -B test package`;
- Buildah pushes to the OpenShift internal registry;
- the pipeline does not deploy the application in this first slice.

### Evidence

Capture:

- rendered GitOps summary;
- PipelineRun name and URL when live;
- image reference and digest when produced;
- PaC setup blocker when live validation is unavailable.

## Stage 155: Red Hat Trusted Software Supply Chain

Stage 155 validates the evidence model for supply-chain decisions.

### Analysis Gate

Review:

- `docs/developer-workflow/155-red-hat-trusted-software-supply-chain.md`
- app repository evidence docs
- Stage 150 PipelineRun and image evidence
- Trusted Software Supply Chain, Quay, ACS, Tekton Chains, Trusted Artifact
  Signer, and Trusted Profile Analyzer references selected for the demo

### Validation

Check that the evidence bundle identifies:

- source commit;
- build result;
- image reference and digest;
- SBOM status;
- vulnerability scan status;
- signature or attestation status;
- provenance status;
- promotion decision and human approver.

Until a real PipelineRun and image digest exist, mark generated evidence fields
as pending.

### Evidence

Capture:

- evidence bundle path;
- pending vs real evidence fields;
- promotion decision status;
- controls that are advisory in the first slice versus controls that will become
  blocking later.

## Stage 160: Modernization At Scale With MTA And Developer Lightspeed

Stage 160 validates modernization analysis using `rhpds/mca-coolstore`, MTA, and
Developer Lightspeed.

### Analysis Gate

Review:

- `docs/developer-workflow/160-modernization-at-scale-with-mta-and-developer-lightspeed.md`
- `docs/developer-workflow/mca-coolstore-candidate-assessment.md`
- Stage `080` modernization documentation and validation output
- current MTA and Developer Lightspeed product docs selected for the demo
- corporate standards corpus or sample standards document for custom rules

### Validation

Check that:

- `rhpds/mca-coolstore` remains the brownfield source;
- MTA analysis can be run or the live blocker is documented;
- Developer Lightspeed suggestions are reviewed against an explicit rubric;
- a custom MTA rule exercise is defined from standards documentation;
- false positives and rule scope are reviewed.

### Evidence

Capture:

- MTA analysis report or blocker;
- Developer Lightspeed suggestion and accept/reject rationale;
- custom rule source standard;
- rule test result;
- migration decision notes.

## Stage 170: Agent Mesh Modernization Pattern

Stage 170 validates the architecture concept for coordinated modernization
agents. It is not a claim that a live agent mesh exists.

### Analysis Gate

Review:

- `docs/developer-workflow/170-agent-mesh-modernization-pattern.md`
- outputs from stages `130`, `155`, and `160`
- agent handoff, tool, trace, and evaluation requirements selected for the demo
- Agent Hermes or related agent-mesh notes selected as concept references

### Validation

Check that:

- agents, skills, MCP tools, and human approval points are mapped clearly;
- modernization, delivery, and evidence responsibilities are separated;
- traceability requirements are explicit;
- the concept does not imply production readiness without a prototype.

### Evidence

Capture:

- agent responsibility map;
- handoff and approval points;
- trace/evaluation requirements;
- risks before live implementation.

## Stop And Continue Criteria

Use these statuses at the end of each stage.

- **Green**: required evidence exists and downstream stages can rely on it.
- **Yellow**: static-only or partially validated; downstream stages may proceed
  only if they do not depend on missing live evidence.
- **Red**: blocker found; stop before validating dependent stages.

## Recommended First Pass

Validate in story order. The point of the extension is to build the developer
journey from governed entry point to agentic engineering and then modernization
at scale, so the default validation sequence is numeric:

1. Baseline platform and cluster preflight.
2. Stage 100 governed developer entry point.
3. Stage 110 enterprise vibe coding with Continue.
4. Stage 120 quality bar breakpoint.
5. Stage 130 agentic engineering with OpenCode.
6. Stage 140 golden path Quarkus service.
7. Stage 150 governed pipeline and deployment.
8. Stage 155 trusted software supply-chain evidence.
9. Stage 160 modernization at scale with MTA and Developer Lightspeed.
10. Stage 170 agent mesh modernization pattern.

Stage 140 and Stage 150 have more concrete assets today, so they can be checked
opportunistically when those assets are touched. They are not the first demo
checkpoint. The demo validation path starts with Stage 100 and only advances when
the story evidence for the current stage is clear.

## Immediate Next Actions

1. Run the baseline preflight in the platform repository.
2. Start the Stage 100 analysis gate and evidence note.
3. Validate whether Developer Hub, Dev Spaces, model access, and app repository
   metadata can support the governed developer entry-point story.
4. Record Stage 100 as green, yellow, or red before moving to Stage 110.
