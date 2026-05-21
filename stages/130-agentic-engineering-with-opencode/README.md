# Stage 130: Agents - Agentic Engineering With OpenCode

## Status

This is a planned developer workflow stage. It is not part of [`../../flows/default.yaml`](../../flows/default.yaml) and does not include deploy scripts, validate scripts, GitOps manifests, or an Argo CD Application.

## Why This Matters

Agentic engineering is not bigger prompting. It is a controlled workflow where agents read specs, use scoped skills, respect permissions, gather context through approved tools, run validation, and produce reviewable output.

Stage 130 switches from Continue to OpenCode to show a terminal-based agent workflow inside Red Hat OpenShift Dev Spaces. The developer still owns the result; the assistant operates with more explicit structure.

## What This Stage Adds

This planned stage adds the agents increment of the developer workflow.

- OpenCode as a model-neutral terminal agent inside Dev Spaces.
- Agent roles for planning, exploration, architecture, tests, documentation alignment, pipeline work, security review, and modernization.
- Skill usage based on the quality gates from Stage 120.
- Scoped tool permissions for editing, shell commands, and MCP-backed tools.
- A bounded first feature candidate for `coolstore-inventory-service`: `POST /api/inventory/{itemId}/reservations`.

## Platform Capabilities Consumed

- Stage 060 provides the MCP foundation.
- Stage 070 provides Dev Spaces and OpenCode tooling.
- Stage 100 verifies model selection and MaaS connectivity.
- Stage 110 provides accepted specs.
- Stage 120 provides skill candidates and quality gates.
- [`../../AGENTS.md`](../../AGENTS.md) and [`../../docs/AI_COLLABORATION.md`](../../docs/AI_COLLABORATION.md) define project accountability.

## Developer Workflow

The developer works in the `coolstore-inventory-service` workspace. OpenCode is configured to use an approved model path and must read project instructions before proposing edits.

Candidate agent roles:

| Agent | Purpose | Permission posture |
|-------|---------|--------------------|
| `plan` | Analyze before edits | Ask before file edits and shell commands |
| `explore` | Discover codebase context | Read-only |
| `quarkus-architect` | Plan package structure, dependencies, REST conventions, and module boundaries | Read-only or ask-before-edit |
| `test-engineer` | Add focused tests | Edit only in test paths |
| `doc-alignment-reviewer` | Compare README, API docs, tests, and implementation | Read-only |
| `pipeline-engineer` | Create Tekton or OpenShift Pipelines resources from approved templates | Ask-before-edit |
| `security-reviewer` | Check secrets, model-boundary issues, dependency risk, and deployment policy | Read-only |
| `migration-specialist` | Interpret MTA findings and propose remediation steps | Read-only or ask-before-edit |
| `mta-rule-engineer` | Draft and validate Konveyor/Kantra rule candidates | Read-only until rule output is reviewed |

Recommended skill candidates:

| Skill | Workflow |
|-------|----------|
| `review-enterprise-readiness` | Check tests, docs, secrets, dependency policy, build reproducibility, and deployment path |
| `prepare-human-pr` | Produce PR content with AI disclosure, validation, risk, rollback, and human review notes |
| `review-code-to-docs-alignment` | Compare diffs, README content, API docs, and tests before proposing docs changes |
| `create-tekton-pipeline` | Generate a pipeline from approved tasks and validation expectations |
| `scaffold-quarkus-service` | Create or extend a Quarkus service from approved standards |

## MCP Tool Scope Example

Scribe is a future candidate MCP service for Konveyor/Kantra rule generation. If adopted, expose it only to the rule-authoring agent by default:

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

## What To Notice And Why It Matters

The proof point is that agents make AI work more structured, not less accountable. The agent can help across files and tools, but it must read rules, follow specs, use selected skills, operate within permissions, and report validation evidence.

This matters because enterprise development needs repeatable controls for standards, deployment policy, security review, and PR discipline.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift Dev Spaces provides the controlled workspace where OpenCode runs. Red Hat OpenShift AI MaaS provides the approved model endpoint. MCP provides a standard pattern for approved context and tools. Project-local specs, rules, and skills define how the agent should work.

OpenCode is useful here because it is model-neutral and can run as a terminal workflow in Dev Spaces.

## Red Hat Products Used

- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** provides the cloud development environment.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides the model endpoint through MaaS.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides identity, runtime, and platform controls.

## Open Source Projects To Know

- [OpenCode](https://opencode.ai/) provides the terminal-based agent workflow.
- [Model Context Protocol](https://modelcontextprotocol.io/) provides a standard pattern for tool and context integration.
- [Continue](https://www.continue.dev/) remains the IDE assistant used in earlier stages.

## TODOs

- TODO: Add OpenCode configuration examples pinned to the demo version.
- TODO: Add agent definitions, rule files, and skills as reviewed project artifacts.
- TODO: Add permission examples for `bash`, `edit`, and MCP tool namespaces.
- TODO: Add eval-driven checks for expected-good prompts, known-bad prompts, CI, and cost or telemetry capture.
- TODO: Add MCP Gateway hardening before exposing shared write-capable tools.

## Deploy And Validate

This planned stage has no deploy or validate scripts. Static validation is documentation review only. Shared quality gates and evidence expectations live in [Developer Workflow Validation](../../docs/DEVELOPER_WORKFLOW_VALIDATION.md).

## References

- [OpenCode: A model-neutral AI coding assistant for OpenShift Dev Spaces](https://developers.redhat.com/articles/2026/04/22/opencode-model-neutral-ai-coding-assistant-openshift-dev-spaces)
- [OpenCode agents](https://opencode.ai/docs/agents/)
- [OpenCode rules](https://opencode.ai/docs/rules/)
- [OpenCode tools](https://opencode.ai/docs/tools/)
- [A guide to AI code assistants with Red Hat OpenShift Dev Spaces](https://developers.redhat.com/articles/2026/01/28/guide-ai-code-assistants-red-hat-openshift-dev-spaces)
- [Vibes, specs, skills, and agents: The four pillars of AI coding](https://developers.redhat.com/articles/2026/03/30/vibes-specs-skills-agents-ai-coding)
- [Eval-driven development: Build and evaluate AI agents](https://developers.redhat.com/articles/2026/03/23/eval-driven-development-build-evaluate-ai-agents)
- [What is AgentOps?](https://www.redhat.com/en/topics/ai/agentops)
- [Advanced authentication and authorization for MCP Gateway](https://developers.redhat.com/articles/2025/12/12/advanced-authentication-authorization-mcp-gateway)
- [sshaaf/scribe](https://github.com/sshaaf/scribe)
- [AI collaboration model](../../docs/AI_COLLABORATION.md)

## Next Stage

[Stage 140: Golden Path Quarkus Service](../140-golden-path-quarkus-service/README.md) applies the controlled agent workflow to a larger service scenario.
