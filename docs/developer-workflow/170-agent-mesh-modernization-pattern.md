# Stage 170: Agent Mesh Modernization Pattern

## Why This Matters

After a team proves governed AI development for one developer and one application, the next question is scale. Enterprise modernization involves many applications, many findings, many validation steps, and many roles. One assistant in one workspace is not enough.

This planned stage closes the story with the Red Hat agent mesh pattern: specialized agentic harnesses coordinating modernization, testing, security review, documentation, and deployment validation on top of OpenShift AI.

## Story Goal

Show how the local workflow from stages `100-160` maps to a portfolio-scale architecture. The developer-facing OpenCode agents become local task agents. MTA and Developer Lightspeed form the modernization harness. Adjacent harnesses can coordinate testing, security review, documentation, and deployment validation.

## Platform Capabilities Consumed

- Stage 030 provides private model serving and efficient inference patterns.
- Stage 040 provides governed MaaS access.
- Stage 060 provides MCP context integration.
- Stage 130 provides local agent and skill patterns.
- Stage 155 provides the trusted software supply-chain evidence model for application and AI artifacts.
- Stage 160 provides modernization analysis and remediation evidence.

## What This Stage Adds

This planned stage adds the architectural close.

- Mapping from local project agents to portfolio-level harnesses.
- Agent mesh narrative tied to Red Hat AI and OpenShift AI.
- Brownfield modernization KPI model.
- Traceability model across prompts, source, findings, agent output, tests, and deployment evidence.
- AgentOps and tracing model across prompts, model calls, tool calls, MCP invocations, token usage, and human approval points.
- Eval-driven development model for testing harness behavior and modernization recommendations over time.
- Horizon placement for Bring Your Own Agent, OpenClaw, and Kagenti-style agent lifecycle management.
- Supply-chain governance model for agent images, MCP servers, skills, models, and modernization artifacts.
- Scribe as a candidate domain tool used by a modernization harness to draft and validate custom Konveyor rules.
- A future path for multiple harnesses exchanging state or evidence.

## Developer Workflow

### Starting Point

The team has demonstrated a single developer workflow: governed entry point, Continue assistance, quality gates, OpenCode agents, Quarkus golden path, delivery controls, and MTA modernization.

This final stage is documentation and architecture first. It does not require a live multi-agent mesh implementation in the first iteration.

The first Stage 160 exercise packet provides the single-application evidence that a future mesh would consume:

- MTA analysis inputs and findings from [`MTA Coolstore Analysis Exercise`](mta-coolstore-analysis-exercise.md);
- suggested remediation decisions from [`Developer Lightspeed Evaluation Rubric`](developer-lightspeed-evaluation-rubric.md);
- reviewed custom rule intent from [`MTA Custom Rule Exercise`](mta-custom-rule-exercise.md).

### AI-Assisted Task

The team maps the local workflow into a larger modernization operating model:

- coding agents handle focused source changes;
- non-coding agents handle planning, dependency reasoning, progress tracking, and review support;
- testing harnesses validate functional equivalence;
- security harnesses review policy and dependency risk;
- documentation harnesses update technical docs;
- deployment harnesses validate delivery evidence.
- AgentOps records prompts, tool calls, model calls, token use, MCP invocations, and approval points.
- BYOA-style platform services manage agent lifecycle, identity, sandboxing, RBAC, NetworkPolicy, and human approval patterns.
- Trusted supply-chain controls govern the agent images, MCP server images, model artifacts, and skill bundles used by the mesh.
- Modernization harnesses can call Scribe as a scoped MCP tool, but generated rules still require validation, false-positive review, and human approval.

### Prompts Or Agent Instructions

Recommended architecture prompt:

```text
Map the local OpenCode agents and MTA modernization workflow to a portfolio-level agent mesh. Identify each harness, the evidence it consumes, the evidence it produces, and the human approval point.
```

Recommended KPI prompt:

```text
Create a brownfield modernization scorecard that separates correctness, maintainability, developer ownership, and velocity. Do not treat speed alone as success.
```

### Expected Developer Actions

- Review the Red Hat agent mesh concept.
- Map local stage artifacts to harness-level responsibilities.
- Identify which evidence must be exchanged between harnesses.
- Define human approval points.
- Define brownfield modernization KPIs.
- Decide which part of the mesh should be implemented first in a later iteration.

### Review And Quality Gates

- The architecture does not claim autonomous modernization without human review.
- Agent outputs are traceable to source context, MTA findings, tests, and decisions.
- Brownfield KPIs prioritize correctness and maintainability before velocity.
- External service dependencies are documented.
- Disconnected or private operation requirements are treated as first-class constraints when relevant.
- Tracing, evals, and supply-chain evidence are described as required controls, not optional observability extras.
- Preview or horizon technologies are labeled as future implementation candidates, not current demo dependencies.

### Evidence To Capture

- Agent-to-harness mapping.
- Evidence flow diagram.
- AgentOps trace and evaluation checkpoints.
- Human approval points.
- Supply-chain evidence boundaries for shared agent and MCP artifacts.
- Brownfield KPI scorecard.
- Candidate first harness integration for later implementation.
- Open questions about model selection, context limits, and inference capacity.

## What To Notice And Why It Matters

The proof point is that the same principles scale up. Vibe coding is one developer asking for help. Agentic engineering is one developer coordinating specialized agents inside a governed workflow. Agent mesh is the enterprise-scale version: multiple specialized harnesses coordinating work across a software estate.

This matters because modernization programs fail when speed outruns correctness. The agent mesh story keeps the emphasis on traceability, repeatable evidence, platform-owned inference, and human oversight.

## How Red Hat And Open Source Make It Work

The Red Hat agent mesh blog describes an agentic harness running on OpenShift AI with vLLM-backed inference, specialized coding and non-coding agents, and a path toward multiple harnesses coordinating adjacent workflows. OpenShift AI provides model serving, observability, and a containerized platform substrate. MaaS and MCP patterns can help make model and tool access governable.

Open source agents such as OpenCode can participate as replaceable components when their responsibilities, permissions, and outputs are made explicit.

Red Hat's AgentOps and OpenTelemetry guidance adds the operational control plane for this horizon: traces should show what each harness asked, which model and tool calls were made, which MCP services were invoked, what each call cost, and where humans approved or rejected work. Eval-driven development provides the method for continuously testing those harnesses against predefined conversations, generated tests, expected-good cases, and known-bad cases.

The BYOA, OpenClaw, and Kagenti material fits as a future platform pattern for bringing externally developed agents into governed OpenShift environments. The relevant concepts are lifecycle management, identity, sandboxing, RBAC, NetworkPolicy, runtime isolation, and human approval. Red Hat Trusted Software Supply Chain then governs the artifacts those agents depend on: images, models, MCP servers, skills, and generated application changes.

## Trust Boundaries

The trust boundary expands from a single prompt to an ecosystem of agents, tools, models, MCP servers, registries, policies, and evidence stores. Every harness must make its inputs, outputs, permissions, supply-chain posture, and human approval points inspectable. Model inference can be private, but agent decisions still require traceability, evaluation, review, and artifact verification.

## Red Hat Products Used

- **[Red Hat AI](https://www.redhat.com/en/products/ai)** provides the broader AI platform context.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides model serving and AI workload lifecycle capabilities.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides the container platform for modular harnesses and agents.
- **[Migration Toolkit for Applications](https://developers.redhat.com/products/mta)** provides the modernization analysis foundation.
- **[Red Hat Trusted Software Supply Chain](https://developers.redhat.com/products/trusted-software-supply-chain)** provides artifact trust patterns for agent, MCP, model, and application supply chains.

## Open Source Projects To Know

- [vLLM](https://docs.vllm.ai/) provides efficient model inference.
- [OpenCode](https://opencode.ai/) can act as a local agentic coding tool.
- [Konveyor](https://www.konveyor.io/) provides the modernization foundation behind MTA.
- [Model Context Protocol](https://modelcontextprotocol.io/) provides a pattern for governed context and tool access.

## Future Implementation Notes

- Add an agent mesh diagram after the local stages are implemented.
- Define the minimum evidence exchange between two harnesses.
- Add brownfield modernization KPI templates.
- Treat the Stage 160 exercise packet as the first evidence contract between the modernization harness, review harness, and future test-validation harness.
- Add AgentOps trace examples and eval checkpoints for each harness.
- Add an artifact trust model for agent images, MCP servers, skills, model containers, and generated application images.
- Decide whether a future modernization harness calls Scribe directly, through MCP Gateway, or through a reviewed ruleset service.
- Decide which harness pair to prototype first, such as modernization plus test validation.
- Keep the stage positioned as a horizon until there is real implementation evidence.

## Deploy And Validate

This planned workflow stage does not yet include deploy or validate scripts. Static validation for this iteration is documentation review only.

## References

- [Refactoring at the speed of mission: An agent mesh approach to legacy system modernization with Red Hat AI](https://www.redhat.com/en/blog/refactoring-speed-mission-agent-mesh-approach-legacy-system-modernization-red-hat-ai)
- [Red Hat AI](https://www.redhat.com/en/products/ai)
- [Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)
- [Migration Toolkit for Applications](https://developers.redhat.com/products/mta)
- [What is AgentOps?](https://www.redhat.com/en/topics/ai/agentops)
- [Distributed tracing for agentic workflows with OpenTelemetry](https://developers.redhat.com/articles/2026/04/06/distributed-tracing-agentic-workflows-opentelemetry)
- [Eval-driven development: Build and evaluate AI agents](https://developers.redhat.com/articles/2026/03/23/eval-driven-development-build-evaluate-ai-agents)
- [Operationalizing Bring Your Own Agent on Red Hat AI: OpenClaw edition](https://www.redhat.com/en/blog/operationalizing-bring-your-own-agent-red-hat-ai-openclaw-edition)
- [Build resilient guardrails for OpenClaw AI agents on Kubernetes](https://developers.redhat.com/articles/2026/04/09/build-resilient-guardrails-openclaw-ai-agents-kubernetes)
- [Using containers to bring software engineering rigor to AI workloads](https://www.redhat.com/en/blog/using-containers-bring-software-engineering-rigor-ai-workloads)
- [Red Hat Trusted Software Supply Chain](https://developers.redhat.com/products/trusted-software-supply-chain)
- [sshaaf/scribe](https://github.com/sshaaf/scribe)

## Next Stage

This is the final planned stage in the developer workflow extension. Later iterations should choose the first concrete implementation slice and promote selected pages into executable stage directories.
