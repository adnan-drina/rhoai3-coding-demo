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
- component links for source repository, Dev Spaces, and one getting started guide;
- TechDocs for workflow instructions and model-use policy;
- model-server, AI model, and API catalog entries when OpenShift AI model metadata is available through the platform.

For the first Stage 100 implementation pass, the Developer Hub catalog is extended
through the existing Stage 090 catalog source. The live portal should expose the
Coolstore brownfield component, the `coolstore-inventory-service` target
component, the `coolstore` system, and the private MaaS model resource. Direct
Dev Spaces links are generated into the runtime catalog during Stage 090 sync so
the live portal can point at the current cluster route without committing that
route to Git.

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

### Model And Data Classification

| Task type | Data classification | Default model path | Stage 100 decision |
|-----------|---------------------|--------------------|--------------------|
| Source-code explanation, README/API alignment, tests, and bounded implementation planning | Private source-code context | Private MaaS model | Use `nemotron-3-nano-30b-a3b` through MaaS. |
| General product documentation lookup or public Red Hat documentation review | Public documentation | Private MaaS model by default; approved external MaaS model only when policy allows | Prefer the private path during the demo to keep the story simple. |
| Corporate standards, internal policies, customer code, credentials, or private architecture notes | Sensitive internal context | Private MaaS model only | Do not use approved external models. Do not paste secrets. |
| Non-sensitive comparison of public model behavior | Public or synthetic content | Approved external MaaS model when explicitly allowed | Keep separate from source-code exercises and record the reason. |

### Live Validation Checklist

Stage 100 is green only when all of these are true:

- Red Hat Developer Hub is reachable through the Stage 090 route.
- The Developer Hub catalog exposes:
  - `System:default/coolstore`
  - `Component:default/coolstore`
  - `Component:default/coolstore-inventory-service`
  - `Resource:default/maas-private-code-model-nemotron`
- The `coolstore` component points to `rhpds/mca-coolstore`.
- The `coolstore-inventory-service` component points to the current
  `adnan-drina/coding-exercises` planning branch and exposes only the source
  repository, Dev Spaces, and getting started links.
- Red Hat OpenShift Dev Spaces is reachable.
- The `wksp-ai-developer/exercises` workspace opens without a failed phase.
- The workspace contains the `mca-coolstore` and `coding-exercises` projects.
- The selected source-code model is `nemotron-3-nano-30b-a3b` through MaaS.
- No live cluster route hostnames, API keys, kubeconfigs, or model tokens are
  committed as evidence.

### Live Branch Validation And Rollback

During branch validation, patch only the Stage 070 and Stage 090 Argo CD
applications in the sandbox cluster to this feature branch. Do not merge the
branch to `main` and do not add Stage 100 to the default flow.

Rollback to the stable platform branch:

```bash
oc patch application 070-controlled-developer-workspaces -n openshift-gitops --type=merge -p '{"spec":{"source":{"targetRevision":"main"}}}'
oc patch application 090-developer-portal-self-service -n openshift-gitops --type=merge -p '{"spec":{"source":{"targetRevision":"main"}}}'
oc annotate application 070-controlled-developer-workspaces -n openshift-gitops argocd.argoproj.io/refresh=hard --overwrite
oc annotate application 090-developer-portal-self-service -n openshift-gitops argocd.argoproj.io/refresh=hard --overwrite
```

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

- Add the official RHDH Topology source-code editor integration when the
  `coolstore-inventory-service` workload exists and can carry the documented
  OpenShift Git annotations.
- Add TechDocs pages for model-use policy, workflow instructions, and validation evidence.
- Decide whether the OpenShift AI connector for Developer Hub should populate model assets automatically or whether the demo should use static catalog-info examples.
- Decide whether Developer Hub MCP catalog and TechDocs tools become part of the later agentic workflow.
- Add a workspace readiness checklist.
- Use [`stage-100-evidence-template.md`](stage-100-evidence-template.md) for sanitized validation notes.
- Latest sanitized validation evidence:
  [`stage-100-validation-evidence-2026-05-15.md`](stage-100-validation-evidence-2026-05-15.md).

## Deploy And Validate

This planned workflow stage does not yet include deploy or validate scripts. Live
validation uses the existing Stage 070 and Stage 090 platform assets plus manual
Developer Hub and Dev Spaces checks. Do not add this stage to
[`../../flows/default.yaml`](../../flows/default.yaml) until a real executable
stage structure exists.

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
