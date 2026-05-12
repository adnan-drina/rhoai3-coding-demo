# Stage 100: Governed Developer Entry Point

## Why This Matters

The developer workflow should begin from the platform, not from a private collection of local tools, personal API keys, and undocumented model choices. A governed AI development experience needs a clear entry point where the developer can discover the application, workspace, model options, modernization context, and expected review process.

This planned stage starts the hands-on story after the current platform setup stages. The developer enters through Red Hat Developer Hub, uses the Software Catalog and TechDocs to understand the application and approved AI assets, opens a controlled Red Hat OpenShift Dev Spaces workspace, and confirms that Continue and OpenCode will use MaaS-published model endpoints instead of unmanaged provider credentials.

## Story Goal

Show that an enterprise Java developer can start AI-assisted work from a supported platform path. The developer should understand which model path is approved for source-code work, where the workspace comes from, and what evidence must be captured before any AI-assisted change is trusted.

## Platform Capabilities Consumed

- Stage 040 provides governed Models-as-a-Service access.
- Stage 050 can provide approved external models for non-sensitive tasks when policy allows.
- Stage 060 provides the MCP context integration foundation.
- Stage 070 provides Red Hat OpenShift Dev Spaces with Continue and OpenCode tooling.
- Stage 090 provides Red Hat Developer Hub as the portal and catalog entry point.

## What This Stage Adds

This planned stage adds the developer journey map for the workflow extension.

- A start-from-portal path for the `ai-developer` persona.
- A Developer Hub catalog model for application components, AI model servers, model resources, APIs, and TechDocs.
- A model and data classification decision table for private versus approved external model use.
- A checklist for connecting Dev Spaces, Continue, OpenCode, MaaS, and the selected exercise repository.
- A repeatable evidence list for later stage validation.
- A clear boundary between implemented platform setup and planned developer exercises.

## Developer Workflow

### Starting Point

The platform stages `010-090` have been deployed in a future live environment. The developer signs in as `ai-developer`, opens Red Hat Developer Hub, and finds the application or learning component that points to the AI development workflow.

The planned Developer Hub entry should expose:

- a component for the brownfield `mca-coolstore` source application;
- a component for the `coolstore-inventory-service` repository, currently planned by renaming `adnan-drina/coding-exercises`;
- component links for the service source, app-local GitOps directory, pipeline directory, rollout notes, promotion notes, and rollback evidence once those paths exist;
- TechDocs for workflow instructions and model-use policy;
- links to Dev Spaces, source, CI/CD, GitOps, MTA, and OpenShift resources when they exist;
- model-server, AI model, and API catalog entries when OpenShift AI model metadata is available through the platform.

For this documentation iteration, the live portal links and workspace launch buttons are not implemented. The planned path is captured so the demo can later be wired to real Developer Hub catalog entities.

### AI-Assisted Task

The developer does not ask the AI to write code yet. The first task is orientation:

- identify the application or exercise repository;
- open the governed Dev Spaces workspace;
- confirm the available model endpoints;
- select the private MaaS model path for source-code work;
- record which model path is being used and why.

### Prompts Or Agent Instructions

The first prompts are diagnostic and policy-oriented. If the Developer Hub MCP catalog or TechDocs tools are available later, these prompts should prefer read-only catalog and documentation lookup before relying on model memory:

```text
Explain which model endpoint this workspace is configured to use, what data boundary it represents, and which tasks are appropriate for this model path.
```

```text
Review the project instructions and summarize the human review, validation, and PR disclosure requirements for AI-assisted work.
```

These prompts should be used only after the workspace and model configuration are in place. They are not a substitute for reviewing the project documentation.

### Expected Developer Actions

- Open the platform entry point in Developer Hub.
- Review the catalog component, ownership metadata, TechDocs, and model/API links.
- Open the controlled Dev Spaces workspace.
- Verify Continue and OpenCode can be configured with MaaS-published OpenAI-compatible endpoints.
- Keep model API keys out of git.
- Choose the private model path for source-code exercises.
- Record model choice, task type, and data classification in the exercise notes.

### Review And Quality Gates

- No API keys, tokens, kubeconfigs, or provider credentials are committed.
- The selected model path is appropriate for source-code context.
- External model use is clearly separated from private model use.
- The developer can explain where prompts and code are processed.
- The workspace source, tool configuration, and project instructions are reviewable.

### Evidence To Capture

- Developer Hub component, TechDocs, model-server resource, or planned catalog entry used to start the journey.
- Workspace name or Dev Spaces URL.
- Model endpoint class: private MaaS model or approved external MaaS model.
- Confirmation that no model credentials are stored in the repository.
- Notes on why the private model path was selected for source-code work.

## What To Notice And Why It Matters

The important proof point is that the developer starts from a governed platform contract. Red Hat Developer Hub makes the path discoverable through catalog entities, software templates, and TechDocs. Dev Spaces makes the workspace reproducible, MaaS centralizes model access, and the project rules define how AI assistance is reviewed.

This matters because enterprise AI development starts before the first prompt. If the entry point is uncontrolled, every later claim about model governance, source-code boundaries, and auditability becomes weaker.

## How Red Hat And Open Source Make It Work

Red Hat Developer Hub provides the catalog and self-service entry point. Its Software Catalog can model application components, APIs, resources, model servers, AI models, and documentation. Software Templates can later turn the entry point into a scaffolded golden path, while TechDocs can publish workflow instructions and model-use guidance next to the service.

Red Hat OpenShift Dev Spaces provides the cloud development environment. Red Hat OpenShift AI and MaaS provide the governed model endpoint pattern. The same OpenAI-compatible model interface can be consumed by open source tools such as Continue and OpenCode when the platform publishes approved endpoints.

Developer Hub MCP plug-ins are a strong future fit for this stage because they can expose catalog and TechDocs lookup as read-only tools for AI assistants. That keeps the assistant grounded in the portal's source of truth without granting it write access to platform resources.

The open source pieces matter because the developer workflow can remain tool-flexible while the enterprise controls remain platform-owned.

## Trust Boundaries

The first trust boundary is model path selection. Private source-code work should use a private model endpoint through MaaS. Approved external model use can still be governed by MaaS, but prompts are processed by the provider and must be limited to tasks and data classifications approved by policy.

## Red Hat Products Used

- **[Red Hat Developer Hub](https://www.redhat.com/en/technologies/cloud-computing/developer-hub)** provides the developer portal entry point.
- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** provides controlled cloud workspaces.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides governed model access through MaaS.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides identity, routing, RBAC, and platform runtime controls.

## Open Source Projects To Know

- [Backstage](https://backstage.io/) is the upstream foundation for Developer Hub.
- [Eclipse Che](https://www.eclipse.org/che/) and DevWorkspace provide the cloud workspace foundation behind Dev Spaces.
- [Continue](https://www.continue.dev/) and [OpenCode](https://opencode.ai/) are open source AI coding tools that can consume OpenAI-compatible endpoints.
- [Model Context Protocol](https://modelcontextprotocol.io/) can expose read-only Developer Hub catalog and TechDocs context to approved clients.

## Future Implementation Notes

- Add Developer Hub catalog links for Dev Spaces, MaaS guidance, MTA, model servers, AI models, APIs, and the exercise repository.
- Add TechDocs pages for model-use policy, workflow instructions, and validation evidence.
- Decide whether the OpenShift AI connector for Developer Hub should populate model assets automatically or whether the demo should use static catalog-info examples.
- Decide whether Developer Hub MCP catalog and TechDocs tools become part of the later agentic workflow.
- Add a model and data classification decision table.
- Add a workspace readiness checklist.
- Add a model selection evidence template for later demo runs.

## Deploy And Validate

This planned workflow stage does not yet include deploy or validate scripts. Static validation for this iteration is documentation review only.

## References

- [Red Hat Developer Hub documentation](https://docs.redhat.com/en/documentation/red_hat_developer_hub/1.9)
- [Red Hat Developer Hub background and concepts](https://developers.redhat.com/articles/2026/01/12/red-hat-developer-hub-background-and-concepts)
- [LLMs and Red Hat Developer Hub: How to catalog AI assets](https://developers.redhat.com/articles/2024/11/12/llms-developer-hub-catalog-ai-assets)
- [OpenShift AI connector for Red Hat Developer Hub](https://developers.redhat.com/articles/2025/11/10/openshift-ai-connector-red-hat-developer-hub)
- [MCP in Red Hat Developer Hub: Chat with your catalog](https://developers.redhat.com/articles/2025/11/10/mcp-red-hat-developer-hub-chat-your-catalog)
- [Build an AI agent to automate TechDocs in Red Hat Developer Hub](https://developers.redhat.com/articles/2025/05/30/build-ai-agent-automate-techdocs-red-hat-developer-hub)
- [Red Hat OpenShift Dev Spaces documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/)
- [What is Model-as-a-Service?](https://www.redhat.com/en/topics/ai/what-is-models-as-a-service)
- [A guide to AI code assistants with Red Hat OpenShift Dev Spaces](https://developers.redhat.com/articles/2026/01/28/guide-ai-code-assistants-red-hat-openshift-dev-spaces)

## Next Stage

[Stage 110: Enterprise Vibe Coding With Continue](110-enterprise-vibe-coding-with-continue.md) uses the governed workspace and model path for the first AI-assisted coding tasks.
