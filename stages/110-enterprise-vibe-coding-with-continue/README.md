# Stage 110: Enterprise Vibe Coding With Continue

## Why This Matters

Vibe coding is valuable because it makes software work more accessible. A developer can ask for explanations, tests, documentation, and small changes without leaving the IDE. In an enterprise setting, that productivity gain only helps if the assistant runs inside approved model, workspace, and review boundaries.

This planned stage shows the useful side of AI-assisted IDE work while keeping the limits visible. Continue runs in Red Hat OpenShift Dev Spaces and uses a MaaS-published model endpoint, preferably a private model for source-code context.

## Story Goal

Show a realistic first productivity win: the developer uses Continue to understand an existing Java or Quarkus application, generate or improve a test, review README alignment, and draft documentation. The output is useful, but it becomes trusted only after human review and validation.

## Platform Capabilities Consumed

- Stage 030 provides private model serving for sensitive source-code tasks.
- Stage 040 provides MaaS access to approved model endpoints.
- Stage 070 provides Dev Spaces and Continue tooling.
- Stage 100 defines the model path and evidence expectations for the developer workflow.

## What This Stage Adds

This planned stage adds the first hands-on AI coding exercise.

- A Continue prompt pack for explanation, test creation, README alignment, and documentation drafting.
- A Code-to-Docs style review pattern where the assistant proposes documentation changes from implementation diffs and the developer approves them explicitly.
- A model evaluation scorecard for private and approved external model comparison when policy allows.
- A human review checklist for generated code and documentation.
- A record of which model was used for which task.
- A transition point toward the quality-bar exercise in Stage 120.

## Developer Workflow

### Starting Point

The developer is in the controlled Dev Spaces workspace with Continue configured for a MaaS endpoint. The repository direction is now selected: `adnan-drina/coding-exercises` should be renamed to `coolstore-inventory-service` after the direction is accepted, then reshaped into the service repository. The exact hands-on task for this stage is the README, API, and test-plan alignment review once the Quarkus scaffold or source slice exists.

### AI-Assisted Task

Use Continue for short, bounded tasks:

- explain the current service or endpoint;
- identify the safest small change to make;
- write a unit or integration test using project conventions;
- compare the README with the implementation;
- produce a README-vs-code or spec-vs-code gap list before editing documentation;
- draft documentation for a new or changed endpoint.

The developer should keep each request small enough to review.

### Prompts Or Agent Instructions

Recommended starter prompts:

```text
Explain this service in terms of inputs, outputs, dependencies, and the safest small behavior to test first. Do not edit files.
```

```text
Write a unit or integration test for this endpoint using the conventions already present in the project. Explain the behavior the test proves.
```

```text
Review the README against the implementation and list mismatches. Do not rewrite the README until I confirm which mismatches matter.
```

```text
Draft documentation for this endpoint. Include only behavior that is visible in the implementation or tests.
```

### Expected Developer Actions

- Select the source file or test file intentionally.
- Ask Continue for a plan before accepting code changes.
- Review the generated diff.
- Run the relevant test command once the exact hands-on task is chosen.
- Update documentation only for behavior that is actually implemented.
- Record model name, task type, prompt summary, and validation outcome.

### Review And Quality Gates

- Generated tests must compile and pass in the selected project.
- Documentation changes must start as proposed gaps, not silent rewrites.
- Documentation updates must match implemented behavior.
- No unsupported dependency or version change is accepted without review.
- No credentials, keys, or private URLs are introduced.
- The developer owns the final diff and can explain it without relying on the assistant transcript.

### Evidence To Capture

- Prompt summary and model path.
- Files changed by the assistant.
- Test command and result.
- README alignment findings and which ones were accepted.
- Accepted and rejected documentation changes from the gap list.
- Human review notes explaining why the output was accepted or rejected.

## What To Notice And Why It Matters

The proof point is that vibe coding can be useful without being unmanaged. Continue gives the developer quick feedback inside the IDE, while Dev Spaces, MaaS, and project review rules keep the workflow inside a controlled platform boundary.

This matters because enterprises should not reject AI-assisted coding only because free-form prompting is risky. The better pattern is to make the useful tasks visible, bounded, and verifiable.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift Dev Spaces provides a reproducible workspace where the assistant runs close to the source and tooling. Red Hat OpenShift AI and MaaS provide the approved model endpoint. Continue provides the open source IDE assistant experience and can connect to OpenAI-compatible endpoints.

The result is a familiar developer workflow where model access is supplied by the platform instead of by personal provider keys.

Red Hat's Code-to-Docs pattern adds a useful discipline for this stage: let AI inspect diffs and propose documentation updates, but require humans to approve which documentation changes are true. That makes README alignment a reviewable engineering task instead of a free-form rewrite.

## Trust Boundaries

Source-code prompts should use the private model path unless the organization explicitly approves the data classification for external processing. MaaS can centralize access to both private and approved external models, but it does not make provider-side processing private.

## Red Hat Products Used

- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** provides the IDE workspace.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides governed model serving and MaaS access.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides the platform identity and runtime boundary.

## Open Source Projects To Know

- [Continue](https://www.continue.dev/) provides the IDE AI assistant workflow.
- [Eclipse Che](https://www.eclipse.org/che/) and DevWorkspace provide the cloud workspace foundation.
- [KServe](https://kserve.github.io/website/) and [vLLM](https://docs.vllm.ai/) are part of the private inference path introduced earlier in the platform story.

## Future Implementation Notes

- Use the first Continue exercise inside the renamed `coolstore-inventory-service` repository for README, API, and test-plan alignment after the Quarkus scaffold or source slice exists.
- Add the Continue prompt pack as versioned demo content.
- Add expected test commands and README alignment examples.
- Add a Code-to-Docs prompt that produces a gap list before applying any README change.
- Define a simple scorecard for private model versus approved external model behavior when policy allows comparison.

## Deploy And Validate

This planned workflow stage does not yet include deploy or validate scripts. Static validation for this iteration is documentation review only.

## References

- [A guide to AI code assistants with Red Hat OpenShift Dev Spaces](https://developers.redhat.com/articles/2026/01/28/guide-ai-code-assistants-red-hat-openshift-dev-spaces)
- [AI-powered documentation updates: From code diff to docs PR in one comment](https://developers.redhat.com/articles/2026/04/21/ai-powered-documentation-updates-code-diff-docs-pr-one-comment)
- [Red Hat OpenShift Dev Spaces documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_dev_spaces/)
- [What is Model-as-a-Service?](https://www.redhat.com/en/topics/ai/what-is-models-as-a-service)
- [Continue](https://www.continue.dev/)

## Next Stage

[Stage 120: Quality Bar Breakpoint](../120-quality-bar-breakpoint/README.md) turns the same productivity story into a controlled example of why AI output still needs professional engineering review.
