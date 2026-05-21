# Stage 170: Agent Mesh Modernization Pattern

## Status

This is a planned developer workflow stage. It is not part of [`../../flows/default.yaml`](../../flows/default.yaml) and does not include deploy scripts, validate scripts, GitOps manifests, or an Argo CD Application.

## Why This Matters

After a team proves governed AI development for one developer and one application, the next question is scale. Enterprise modernization involves many applications, findings, validation steps, and roles. One assistant in one workspace is not enough.

Stage 170 closes the planned story by mapping the local workflow from stages 100-160 to a portfolio-scale agent mesh modernization pattern.

## What This Stage Adds

This planned stage adds an architecture mapping, not a live multi-agent implementation.

- Local OpenCode agents mapped to portfolio-scale harnesses.
- Modernization, testing, security review, documentation, and deployment-validation harness concepts.
- Evidence flow from MTA findings, Developer Lightspeed suggestions, custom rules, tests, and human decisions.
- AgentOps trace expectations for prompts, tool calls, model calls, token use, MCP invocations, and approvals.
- Trusted supply-chain boundaries for agent images, MCP server images, model artifacts, skills, and generated application changes.

## Platform Capabilities Consumed

- Stage 030 provides private model serving.
- Stage 040 provides governed MaaS access.
- Stage 060 provides MCP context integration.
- Stage 130 provides local agent and skill patterns.
- Stage 155 provides the trusted software supply-chain evidence model.
- Stage 160 provides modernization analysis and remediation evidence.

## Developer Workflow

The team maps the single-developer workflow into a larger modernization operating model:

- coding agents handle focused source changes;
- non-coding agents handle planning, dependency reasoning, progress tracking, and review support;
- testing harnesses validate functional equivalence;
- security harnesses review policy and dependency risk;
- documentation harnesses update technical docs;
- deployment harnesses validate delivery evidence;
- modernization harnesses can call scoped MCP tools such as Scribe after rule intent is reviewed.

The first Stage 160 exercise packet provides the evidence a future mesh would consume:

- [`MTA Coolstore Analysis Exercise`](../160-modernization-at-scale-with-mta-and-developer-lightspeed/mta-coolstore-analysis-exercise.md)
- [`Developer Lightspeed Evaluation Rubric`](../160-modernization-at-scale-with-mta-and-developer-lightspeed/developer-lightspeed-evaluation-rubric.md)
- [`MTA Custom Rule Exercise`](../160-modernization-at-scale-with-mta-and-developer-lightspeed/mta-custom-rule-exercise.md)

## Starter Prompts

```text
Map the local OpenCode agents and MTA modernization workflow to a portfolio-level agent mesh. Identify each harness, the evidence it consumes, the evidence it produces, and the human approval point.
```

```text
Create a brownfield modernization scorecard that separates correctness, maintainability, developer ownership, and velocity. Do not treat speed alone as success.
```

## What To Notice And Why It Matters

The proof point is that the same principles scale up. Vibe coding is one developer asking for help. Agentic engineering is one developer coordinating specialized agents inside a governed workflow. Agent mesh is the portfolio-scale version, where multiple harnesses coordinate work across a software estate.

This matters because modernization programs fail when speed outruns correctness. The agent mesh story keeps the emphasis on traceability, evidence, platform-owned inference, and human oversight.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift AI provides model serving, observability, and the AI workload platform. MaaS governs model access. MCP patterns govern tool and context access. Red Hat OpenShift provides the container platform for modular harnesses and agents. MTA provides modernization analysis.

Open source agents such as OpenCode can participate as replaceable components when responsibilities, permissions, and outputs are explicit. AgentOps, OpenTelemetry, and eval-driven development add traceability and feedback loops for agent behavior.

## Red Hat Products Used

- **[Red Hat AI](https://www.redhat.com/en/products/ai)** provides the broader AI platform context.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides model serving and AI workload lifecycle capabilities.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides the container platform for modular harnesses and agents.
- **[Migration Toolkit for Applications](https://developers.redhat.com/products/mta)** provides the modernization analysis foundation.
- **[Red Hat Trusted Software Supply Chain](https://developers.redhat.com/products/trusted-software-supply-chain)** provides artifact trust patterns.

## Open Source Projects To Know

- [vLLM](https://docs.vllm.ai/) provides efficient model inference.
- [OpenCode](https://opencode.ai/) can act as a local agentic coding tool.
- [Konveyor](https://www.konveyor.io/) provides the modernization foundation behind MTA.
- [Model Context Protocol](https://modelcontextprotocol.io/) provides a pattern for governed context and tool access.

## TODOs

- TODO: Add an agent mesh diagram after the local stages are implemented.
- TODO: Define the minimum evidence exchange between two harnesses.
- TODO: Add AgentOps trace examples and eval checkpoints.
- TODO: Add an artifact trust model for agent images, MCP servers, skills, model containers, and generated application images.
- TODO: Decide which harness pair to prototype first, such as modernization plus test validation.

## Deploy And Validate

This planned stage has no deploy or validate scripts. Static validation is documentation review only. Shared quality gates and evidence expectations live in [Developer Workflow Validation](../../docs/DEVELOPER_WORKFLOW_VALIDATION.md).

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

This is the final planned stage in the developer workflow extension. Later iterations should choose the first concrete implementation slice before promoting it into the executable stage flow.
