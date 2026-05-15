# Stage 130: Agentic Engineering With OpenCode

## Why This Matters

Agentic engineering is not bigger prompting. It is the move from free-form assistance to controlled workflows where agents read project rules, use scoped skills, respect permissions, gather context through approved tools, run validation, and produce reviewable output.

This planned stage switches from Continue to OpenCode to show a terminal-based agent workflow inside Red Hat OpenShift Dev Spaces. The developer still owns the result, but the assistant now operates with more explicit structure.

## Story Goal

Show how agents, skills, model configuration, MCP context, and project instructions can help preserve enterprise coding standards while still accelerating a developer. The audience should see that the assistant is constrained by the same engineering system that human contributors follow.

## Platform Capabilities Consumed

- Stage 060 provides the MCP foundation.
- Stage 070 provides Dev Spaces and OpenCode tooling.
- Stage 100 defines model selection and evidence capture.
- Stage 120 defines the quality-bar problem that agentic workflows need to address.
- `AGENTS.md` and `docs/AI_COLLABORATION.md` define project accountability and validation expectations.

## What This Stage Adds

This planned stage adds the controlled agent workflow design.

- Project-local OpenCode configuration examples.
- Specialized OpenCode primary agents and subagents for architecture, tests, documentation, security, pipelines, and migration.
- Skills for repeatable enterprise workflows.
- Permissions guidance that separates planning, reviewing, command execution, and file editing.
- MCP context usage for approved platform and engineering standards context.
- Eval-driven checks for non-deterministic agent output.
- AgentOps and tracing expectations for prompts, model calls, tool calls, MCP calls, token usage, and human approval points.
- MCP security guidance for identity-based tool access, least privilege, and gateway-mediated integrations.

## Developer Workflow

### Starting Point

The developer is in the same controlled Dev Spaces workspace used in previous stages. OpenCode is available in the terminal and configured to use an approved model path. The repository includes project instructions in `AGENTS.md`, which OpenCode can load as project-specific rules.

### AI-Assisted Task

Use OpenCode for a controlled engineering task that is larger than a single IDE prompt. Candidate tasks include:

- plan a Quarkus service extension;
- add tests in the appropriate test paths;
- review README alignment before editing docs;
- generate a pipeline from approved templates;
- inspect MTA findings and propose remediation steps.

For this documentation iteration, the repository target and first task are selected. OpenCode should operate in the renamed `coolstore-inventory-service` repository once `adnan-drina/coding-exercises` is reshaped. The first bounded feature task is the reservation endpoint, `POST /api/inventory/{itemId}/reservations`, after Continue has completed the README, API, and test-plan alignment pass.

### Prompts Or Agent Instructions

Recommended agent roles:

| Agent | Purpose | Permission posture |
|-------|---------|--------------------|
| `plan` | Use OpenCode's planning mode for analysis before edits | Ask before file edits and bash commands |
| `explore` | Use OpenCode's read-only exploration behavior for codebase discovery | Read-only |
| `quarkus-architect` | Plan package structure, versions, dependencies, REST/API conventions, and module boundaries | Read-only or ask-before-edit |
| `test-engineer` | Add focused tests and identify missing verification | Edit only in test paths |
| `doc-alignment-reviewer` | Compare README, API docs, and implementation | Read-only |
| `pipeline-engineer` | Create Tekton or OpenShift Pipelines resources from approved templates | Ask-before-edit |
| `security-reviewer` | Check secrets, model-boundary issues, dependency risk, and deployment policy | Read-only |
| `migration-specialist` | Interpret MTA findings and propose controlled remediation steps | Read-only or ask-before-edit |
| `mta-rule-engineer` | Use standards context and Scribe MCP tools to draft and validate Konveyor/Kantra rules | Read-only until rule output is reviewed |

Recommended skills:

| Skill | Workflow |
|-------|----------|
| `review-enterprise-readiness` | Check tests, docs, secrets, dependency policy, build reproducibility, and deployment path |
| `prepare-human-pr` | Produce PR summary content with AI disclosure, validation, risk, rollback, and human review notes |
| `review-code-to-docs-alignment` | Compare diffs, README content, API docs, and tests, then propose documentation changes for human approval |
| `create-tekton-pipeline` | Generate a pipeline from approved tasks and validation expectations |
| `scaffold-quarkus-service` | Create or extend a Quarkus service from approved project standards |

Candidate Scribe MCP configuration for OpenCode:

```json
{
  "$schema": "https://opencode.ai/config.json",
  "mcp": {
    "scribe": {
      "type": "remote",
      "url": "http://localhost:8080/mcp/sse",
      "enabled": true,
      "timeout": 30000
    }
  },
  "tools": {
    "scribe_*": false
  },
  "agent": {
    "mta-rule-engineer": {
      "tools": {
        "scribe_*": true
      }
    }
  }
}
```

This keeps Scribe available to the rule-authoring agent without exposing rule-generation tools to every agent by default.

### Expected Developer Actions

- Start OpenCode from the Dev Spaces terminal.
- Confirm it reads project instructions.
- Ask for a plan before edits.
- Use read-only exploration before asking an editing agent to change files.
- Select the appropriate agent or skill for the task.
- Keep permissions scoped to the task.
- Review the diff and validation evidence before accepting output.

### Review And Quality Gates

- Planning and review agents do not edit files.
- Bash and edit tools require explicit approval for sensitive tasks.
- Editing agents are limited to appropriate paths.
- Skills include inputs, steps, expected outputs, and validation.
- MCP context is approved for the task and data classification.
- MCP tools are filtered by user identity, task purpose, and least-privilege access where gateway support exists.
- Agent output is checked against the Stage 120 evaluation set, including expected-good and known-bad cases.
- Tool calls, approval points, and validation results are captured as traceable evidence when tracing is available.
- PR summary includes AI assistance disclosure and validation notes.

### Evidence To Capture

- OpenCode model path and configuration summary.
- Agent or skill used.
- Plan produced before edits.
- Tool-call and MCP-call summary.
- Human approval points.
- Files changed.
- Validation command and result.
- Human review notes.

## What To Notice And Why It Matters

The proof point is that agentic engineering makes AI work more structured, not less accountable. The agent can help across files and tools, but it should still read the repo rules, use approved context, operate within scoped permissions, and produce evidence.

This matters because enterprise development needs repeatability. A one-off prompt cannot encode corporate standards, deployment policy, security review, and PR discipline as reliably as reusable rules and skills.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift Dev Spaces provides the controlled workspace where OpenCode runs. Red Hat OpenShift AI and MaaS provide the approved model endpoint. MCP gives a standard way to expose approved context and tools, while project-local rules and skills define how the agent should work inside this repository.

OpenCode is useful in this story because it is model-neutral and can run as a terminal-based workflow in Dev Spaces. That makes it a good bridge between open source assistant tooling and enterprise model governance.

OpenCode's project rules, agents, and tool permissions make the stage more concrete. `AGENTS.md` carries the project instructions, planning and exploration modes support review-before-edit workflows, and tool permissions can require approval for file edits, shell commands, or MCP-backed tools.

The Red Hat AgentOps and distributed tracing guidance adds the observability side of the story. An enterprise agent workflow should be able to explain which prompt, model, tool, MCP service, token budget, and approval produced an output. Eval-driven development then turns those traces into a feedback loop by testing agents against repeatable conversations, known-bad cases, generated tests, and CI checks.

The Red Hat MCP security guidance adds the integration boundary. MCP tools should be exposed through authenticated and authorized paths, ideally with identity-based tool filtering, OAuth or OIDC token exchange, network isolation, runtime limits, and auditable gateway policy.

## Trust Boundaries

Agent tool access is its own trust boundary. An agent that can read context, edit files, run commands, or call MCP tools must be scoped to the task and reviewed by the developer. Model governance through MaaS does not replace file permissions, tool permissions, MCP Gateway policy, or human diff review.

## Red Hat Products Used

- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** provides the cloud development environment.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides the model endpoint through MaaS.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides identity, runtime, and platform controls.

## Open Source Projects To Know

- [OpenCode](https://opencode.ai/) provides the terminal-based agent workflow.
- [Model Context Protocol](https://modelcontextprotocol.io/) provides a standard pattern for tool and context integration.
- [Continue](https://www.continue.dev/) remains the IDE assistant used in the earlier vibe-coding stages.

## Future Implementation Notes

- Add OpenCode configuration examples pinned to the demo version.
- Add agent definitions, rule files, and skills as reviewed project artifacts.
- Add permission examples for `bash`, `edit`, and MCP tool namespaces.
- Add an enterprise readiness skill derived from the Stage 120 quality rubric.
- Add a Code-to-Docs alignment skill that proposes doc changes from diffs before editing README or API docs.
- Add eval-driven checks for expected-good prompts, known-bad prompts, generated tests, CI integration, and cost or telemetry capture.
- Add OpenTelemetry-based traces for prompts, tool calls, model calls, MCP invocations, and human approval points once an implementation target exists.
- Add MCP Gateway hardening patterns using identity-based tool filtering, OAuth or OIDC, Keycloak, Kuadrant `AuthPolicy`, Authorino, network isolation, and runtime limits.
- Add a Scribe-backed `mta-rule-engineer` agent only after the Scribe endpoint, rule-review rubric, and Stage 160 ruleset workflow are selected.
- Add an MCP-backed or RAG-backed standards lookup only when the source standards docs are selected and processed.

## Deploy And Validate

This planned workflow stage does not yet include deploy or validate scripts. Static validation for this iteration is documentation review only.

## References

- [OpenCode: A model-neutral AI coding assistant for OpenShift Dev Spaces](https://developers.redhat.com/articles/2026/04/22/opencode-model-neutral-ai-coding-assistant-openshift-dev-spaces)
- [OpenCode agents](https://opencode.ai/docs/agents/)
- [OpenCode rules](https://opencode.ai/docs/rules/)
- [OpenCode tools](https://opencode.ai/docs/tools/)
- [A guide to AI code assistants with Red Hat OpenShift Dev Spaces](https://developers.redhat.com/articles/2026/01/28/guide-ai-code-assistants-red-hat-openshift-dev-spaces)
- [Engineering an AI-ready code base: Governance lessons from the Red Hat Hybrid Cloud Console](https://developers.redhat.com/articles/2026/04/15/governance-lessons-red-hat-hybrid-cloud-console)
- [Eval-driven development: Build and evaluate AI agents](https://developers.redhat.com/articles/2026/03/23/eval-driven-development-build-evaluate-ai-agents)
- [What is AgentOps?](https://www.redhat.com/en/topics/ai/agentops)
- [Distributed tracing for agentic workflows with OpenTelemetry](https://developers.redhat.com/articles/2026/04/06/distributed-tracing-agentic-workflows-opentelemetry)
- [AI-powered documentation updates: From code diff to docs PR in one comment](https://developers.redhat.com/articles/2026/04/21/ai-powered-documentation-updates-code-diff-docs-pr-one-comment)
- [Advanced authentication and authorization for MCP Gateway](https://developers.redhat.com/articles/2025/12/12/advanced-authentication-authorization-mcp-gateway)
- [MCP security: Containerization and Red Hat OpenShift integration](https://www.redhat.com/en/blog/mcp-security-containerization-and-red-hat-openshift-integration)
- [Deploy an enterprise RAG chatbot on Red Hat OpenShift AI](https://developers.redhat.com/articles/2026/01/29/deploy-enterprise-rag-chatbot-red-hat-openshift-ai)
- [sshaaf/scribe](https://github.com/sshaaf/scribe)
- [AI collaboration model](../../docs/AI_COLLABORATION.md)

## Next Stage

[Stage 140: Golden Path Quarkus Service](../140-golden-path-quarkus-service/README.md) applies the controlled agent workflow to a larger enterprise service scenario.
