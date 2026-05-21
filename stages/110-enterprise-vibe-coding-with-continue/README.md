# Stage 110: Specs - Spec-Driven AI Coding With Continue

## Status

This is a planned developer workflow stage. It is not part of [`../../flows/default.yaml`](../../flows/default.yaml) and does not include deploy scripts, validate scripts, GitOps manifests, or an Argo CD Application.

## Why This Matters

Vibes are useful for orientation, but enterprise engineering needs instructions that survive a chat session. Specs capture what to build, how this organization expects it to be built, and how success will be verified.

Stage 110 shows how a developer uses Continue inside Dev Spaces to turn exploratory intent into compact, reviewable specifications for README content, API behavior, tests, and implementation constraints.

## What This Stage Adds

This planned stage adds the specs increment of the developer workflow.

- A move from broad prompts to small, authoritative Markdown instructions.
- A clear split between the `what` and the `how`.
- README, API, standards, and test-plan alignment checks.
- Gap lists before documentation or code edits.
- A reviewable handoff for later skills and agents.

## Platform Capabilities Consumed

- Stage 030 provides private model serving.
- Stage 040 provides MaaS access.
- Stage 070 provides Dev Spaces and Continue tooling.
- Stage 100 verifies the governed Continue path.

## Developer Workflow

The developer works in the `coolstore-inventory-service` Dev Spaces workspace after Stage 100 has verified Continue connectivity to the private MaaS model.

Use Continue for:

- explaining the current service in terms of inputs, outputs, dependencies, and behavior;
- separating user-visible behavior from implementation constraints;
- comparing README, API descriptions, tests, and implementation;
- producing a gap list before editing;
- drafting concise specs for accepted behavior and validation.

Do not rely on Continue terminal execution for validation unless it returns captured output. For shell evidence, use `Terminal > New Terminal (Select a Container) > tooling-container`.

## Starter Prompts

```text
Explain this service in terms of inputs, outputs, dependencies, and observable behavior. Separate what the service should do from how this repository should implement it. Do not edit files.
```

```text
Review the README, API description, and tests. List gaps between documented behavior, implemented behavior, and missing verification. Do not rewrite files yet.
```

```text
Draft a compact spec for the inventory availability API. Include the user-visible behavior, expected test cases, and implementation constraints. Do not add code.
```

```text
Given this accepted spec, propose the smallest README or test-plan update. Include only behavior that is visible in implementation, tests, or the accepted spec.
```

## What To Notice And Why It Matters

The proof point is that useful prompts become shared instructions. A spec gives developers, reviewers, and later agents a stable source of truth instead of asking the model to infer standards from a broad request.

This matters because enterprises should not treat free-form prompting as the final workflow. AI-assisted work becomes easier to review when intent, constraints, tests, and documentation expectations are visible before code changes are accepted.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift Dev Spaces provides a reproducible workspace near the source and tools. Red Hat OpenShift AI MaaS provides the approved model endpoint. Continue provides the IDE assistant experience and can consume OpenAI-compatible endpoints.

The Code-to-Docs pattern is useful here: let AI inspect diffs and propose documentation updates, but require humans to approve which documentation changes are true.

## Red Hat Products Used

- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** provides the IDE workspace.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides governed model serving and MaaS access.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides platform identity and runtime boundaries.

## Open Source Projects To Know

- [Continue](https://www.continue.dev/) provides the IDE assistant workflow.
- [Eclipse Che](https://www.eclipse.org/che/) and DevWorkspace provide the cloud workspace foundation.
- [KServe](https://kserve.github.io/website/) and [vLLM](https://docs.vllm.ai/) are part of the private inference path introduced earlier.

## TODOs

- TODO: Add the first Continue prompt pack as versioned demo content.
- TODO: Add expected test commands and README alignment examples for `coolstore-inventory-service`.
- TODO: Define a simple scorecard for private model versus approved external model behavior when policy allows comparison.

## Deploy And Validate

This planned stage has no deploy or validate scripts. Static validation is documentation review only. Shared quality gates and evidence expectations live in [Developer Workflow Validation](../../docs/DEVELOPER_WORKFLOW_VALIDATION.md).

## References

- [A guide to AI code assistants with Red Hat OpenShift Dev Spaces](https://developers.redhat.com/articles/2026/01/28/guide-ai-code-assistants-red-hat-openshift-dev-spaces)
- [AI-powered documentation updates: From code diff to docs PR in one comment](https://developers.redhat.com/articles/2026/04/21/ai-powered-documentation-updates-code-diff-docs-pr-one-comment)
- [Vibes, specs, skills, and agents: The four pillars of AI coding](https://developers.redhat.com/articles/2026/03/30/vibes-specs-skills-agents-ai-coding)
- [Red Hat OpenShift Dev Spaces documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/)
- [What is Model-as-a-Service?](https://www.redhat.com/en/topics/ai/what-is-models-as-a-service)
- [Red Hat's enterprise guide to AI-assisted app dev](https://www.redhat.com/en/resources/ai-assisted-app-dev-enterprise-ebook)
- [Continue](https://www.continue.dev/)

## Next Stage

[Stage 120: Skills - Reusable Quality Gates](../120-quality-bar-breakpoint/README.md) turns accepted specs and review rules into reusable skill packets.
