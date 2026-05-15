# Planned Developer Workflow Extension

This directory drafts the planned `100-170` developer workflow extension for the `rhoai3-coding-demo` project.

The current implemented workshop stages, `010-090`, build and publish the platform capabilities: Red Hat OpenShift AI, private model serving, governed MaaS access, MCP context integrations, Red Hat OpenShift Dev Spaces, Migration Toolkit for Applications, Red Hat Developer Lightspeed, and Red Hat Developer Hub.

The planned `100-170` stages show what an enterprise developer does with those capabilities. They are documentation-only in this iteration and are not registered in [`../../flows/default.yaml`](../../flows/default.yaml).

## Storyline

The extension follows the story "From Vibe Coding to Agentic Engineering":

- Vibe coding raises the floor by letting a developer ask for explanations, tests, code, and documentation from a familiar IDE.
- Agentic engineering preserves the professional quality bar by constraining AI assistance with project rules, skills, model policy, MCP context boundaries, validation, and human review.
- Agent mesh is the portfolio-scale horizon where multiple specialized agentic harnesses coordinate modernization, testing, security review, documentation, and deployment validation.

The demo message is not that AI writes enterprise software by itself. The message is that Red Hat platforms let teams use open source AI tools and models without bypassing identity, source-code boundaries, model governance, development standards, and delivery controls.

## Source Posture

The knowledge base now has stronger source coverage for the developer workflow extension:

- Developer Hub can support the entry point through the Software Catalog, Software Templates, TechDocs, and AI asset catalog patterns.
- Golden paths are now backed by Red Hat guidance that describes repository templates, CI pipelines, deployment manifests, observability defaults, GitOps, Tekton, and transparent extension points.
- Quarkus is now backed by Red Hat and Quarkus sources for Kubernetes-native Java and OpenShift deployment options.
- Pipeline and deployment stages are now backed by Red Hat Developer Hub software-template examples that include Quarkus, Tekton, Argo CD, GitOps, TechDocs, and trusted-application-pipeline references.
- Red Hat Trusted Software Supply Chain now has a dedicated planned stage for SBOMs, VEX, signing, provenance, registry scanning, policy gates, and AI artifact governance.
- AI-ready codebase governance and eval-driven development now strengthen the transition from Stage 120 to Stage 130.
- AgentOps and distributed tracing now strengthen Stage 130 and Stage 170 with observable prompts, model calls, tool calls, MCP calls, token usage, and human approval points.
- MCP security and MCP Gateway sources now strengthen Stage 060, Stage 130, and Stage 150 with identity-based tool filtering, OAuth or OIDC, gateway authorization, network isolation, and runtime limits.
- Code-to-Docs guidance now strengthens Stage 110 through Stage 130 with README alignment and documentation quality gates.
- Enterprise RAG, document processing, and RAG evaluation now strengthen Stage 160 by grounding MTA rule generation in corporate standards.
- BYOA, OpenClaw, and Kagenti-style material is treated as a Stage 170 horizon for agent lifecycle, identity, sandboxing, RBAC, NetworkPolicy, and human approval.
- The [`dls-devspaces` stage map](dls-devspaces-stage-map.md) now captures how the `rhpds/mca-devspaces` project can inform the Dev Spaces and Developer Lightspeed for MTA portions of the demo.
- The [`scribe` MCP stage map](scribe-mcp-stage-map.md) now captures how a Konveyor rule-generation MCP server can be loaded into OpenCode or another MCP-capable agent.
- The [`mca-coolstore` candidate assessment](mca-coolstore-candidate-assessment.md) recommends `rhpds/mca-coolstore` as the primary brownfield modernization source while keeping a smaller Quarkus target service for pipeline and deployment stages.
- The [`Quarkus target service options`](quarkus-target-service-options.md) assessment recommends a demo-owned Coolstore Inventory Quarkus service for Stages 140-155.
- The [`coding-exercises` application repository plan](coding-exercises-app-repo-plan.md) records the accepted first-demo repository shape: rename `adnan-drina/coding-exercises` to `coolstore-inventory-service`, then keep Quarkus source, app-local GitOps state, `.tekton/` Pipelines-as-Code assets, rollout notes, promotion notes, and rollback evidence in that single service repository.
- The [`Item 7 modernization analysis`](item-7-modernization-at-scale-analysis.md) records the Stage 160 source review and adds the first MTA analysis exercise, Developer Lightspeed evaluation rubric, and standards-grounded custom rule exercise.

Remaining gaps are implementation choices rather than storyline gaps: the frontend standard, the first eval set, the standards corpus for RAG-backed MTA rules, and live cluster validation still need to be chosen in a later branch. The repository name, first repository boundary, Quarkus baseline, PostgreSQL path, first Continue/OpenCode task pair, and first `.tekton/` plus app-local GitOps delivery path are now decided.

## Planned Stages

| Stage | Planned workflow | Status |
|-------|------------------|--------|
| [100 - Governed Developer Entry Point](100-governed-developer-entry-point.md) | Start from Developer Hub, discover catalog entities, TechDocs, model assets, Dev Spaces links, and governed MaaS model access, then choose the private model path for source-code work | Planned documentation |
| [110 - Enterprise Vibe Coding With Continue](110-enterprise-vibe-coding-with-continue.md) | Use Continue in Dev Spaces to explain code, draft tests, review README alignment, and evaluate model usefulness | Planned documentation |
| [120 - Quality Bar Breakpoint](120-quality-bar-breakpoint.md) | Show a plausible AI-assisted near miss and catch it with tests, documentation review, dependency review, or policy checks | Planned documentation |
| [130 - Agentic Engineering With OpenCode](130-agentic-engineering-with-opencode.md) | Move from free-form IDE assistance to OpenCode agents, project rules, skills, permissions, and MCP-backed context | Planned documentation |
| [140 - Golden Path Quarkus Service](140-golden-path-quarkus-service.md) | Use controlled agents with Developer Hub software-template and golden-path guidance to scaffold or extend a Quarkus service from enterprise standards | Planned documentation |
| [150 - Governed Pipeline And Deployment](150-governed-pipeline-and-deployment.md) | Generate an approved Tekton or OpenShift Pipelines path from golden-path templates and hand deployment back to GitOps or another approved platform route | Planned documentation |
| [155 - Red Hat Trusted Software Supply Chain](155-red-hat-trusted-software-supply-chain.md) | Add trusted software supply-chain evidence for AI-assisted application, model, MCP, skill, and agent artifacts before promotion | Planned documentation |
| [160 - Modernization At Scale With MTA And Developer Lightspeed](160-modernization-at-scale-with-mta-and-developer-lightspeed.md) | Analyze Coolstore with MTA, use Developer Lightspeed for MTA, and introduce custom rules from corporate standards | Planned documentation |
| [170 - Agent Mesh Modernization Pattern](170-agent-mesh-modernization-pattern.md) | Close with the Red Hat agent mesh pattern as the scaled version of governed agentic modernization | Planned documentation |

Supporting analysis:

- [`dls-devspaces-stage-map.md`](dls-devspaces-stage-map.md) maps the `rhpds/mca-devspaces` Developer Lightspeed for MTA workspace project to this demo's stages.
- [`scribe-mcp-stage-map.md`](scribe-mcp-stage-map.md) maps the `sshaaf/scribe` Konveyor rule-generation MCP server to this demo's stages and OpenCode configuration.
- [`mca-coolstore-candidate-assessment.md`](mca-coolstore-candidate-assessment.md) assesses `rhpds/mca-coolstore` as the main demo application candidate and recommends a two-track brownfield plus Quarkus-target story.
- [`quarkus-target-service-options.md`](quarkus-target-service-options.md) compares smaller Quarkus service candidates and selects the Coolstore Inventory service shape for the golden-path, pipeline, and supply-chain stages.
- [`coding-exercises-app-repo-plan.md`](coding-exercises-app-repo-plan.md) maps the `adnan-drina/coding-exercises` repository into the planned renamed `coolstore-inventory-service` repository with source, app-local GitOps, and `.tekton/` Pipelines-as-Code assets in one place for the first demo.
- [`readme-completion-alignment-review.md`](readme-completion-alignment-review.md) reviews current README completion, storyline alignment, repository-boundary clarity, and remaining implementation gaps.
- [`stage-validation-runbook.md`](stage-validation-runbook.md) defines the one-by-one validation path for planned stages `100-170` without adding them to the executable platform flow.
- [`item-7-modernization-at-scale-analysis.md`](item-7-modernization-at-scale-analysis.md) records the Stage 160 analysis gate.
- [`mta-coolstore-analysis-exercise.md`](mta-coolstore-analysis-exercise.md) defines the first MTA analysis workflow and evidence packet for `rhpds/mca-coolstore`.
- [`developer-lightspeed-evaluation-rubric.md`](developer-lightspeed-evaluation-rubric.md) defines how to evaluate Developer Lightspeed for MTA suggestions before accepting changes.
- [`mta-custom-rule-exercise.md`](mta-custom-rule-exercise.md) defines the standards-grounded custom rule workflow and review gate.

## Boundary With Implemented Stages

The planned workflow stages intentionally do not replace the existing platform stages.

- Stage 070 remains the developer workspace foundation.
- Stage 080 remains the modernization platform foundation.
- Stage 090 remains the portal foundation.
- The planned `100-170` stages add the hands-on developer exercises, prompt packs, OpenCode agent examples, skills, code examples, pipeline templates, supply-chain evidence, modernization exercises, and evaluation rubrics later.

## README Pattern

The planned stage pages use a hybrid README structure. They keep the educational stage narrative used by the implemented stages, but add a `Developer Workflow` section so each stage can later become a hands-on engineering exercise.

Each page includes:

- why the stage matters;
- the story goal;
- platform capabilities consumed from stages `010-090`;
- the developer workflow starting point, AI-assisted task, prompts or agent instructions, expected developer actions, quality gates, and evidence;
- trust boundaries;
- Red Hat products and open source projects;
- future implementation notes;
- static validation status.

## Implementation Policy

Do not add these stages to [`../../flows/default.yaml`](../../flows/default.yaml) until each stage has the full executable structure required by `./scripts/validate-stage-flow.sh`:

- a `stages/NNN-name/README.md` file;
- executable `deploy.sh` and `validate.sh` scripts;
- a GitOps base under `gitops/stages/NNN-name/base/`;
- an Argo CD Application under `gitops/argocd/app-of-apps/`;
- validation behavior that matches the stage documentation.

For this iteration, validation is static documentation review only.
