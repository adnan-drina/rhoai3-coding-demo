# Stage 120: Skills - Reusable Quality Gates

## Status

This is a planned developer workflow stage. It is not part of [`../../flows/default.yaml`](../../flows/default.yaml) and does not include deploy scripts, validate scripts, GitOps manifests, or an Argo CD Application.

## Why This Matters

Specs describe the desired outcome. Skills capture repeatable know-how: how to review README alignment, validate an OpenShift delivery path, check enterprise readiness, or prepare a PR summary.

Stage 120 uses a deliberate near miss to show why skills matter. The point is not to make a model look bad. The point is to show that tests, architecture judgment, conventions, policy, and human review still decide whether AI-assisted output is acceptable.

## What This Stage Adds

This planned stage adds the skills increment of the developer workflow.

- A near-miss exercise that exposes a real review, policy, test, or documentation gap.
- A reusable quality gate derived from the review procedure.
- A first skill candidate, currently `review-enterprise-readiness`.
- Evidence showing which checklist item caught the issue and how the corrected output was validated.

## Platform Capabilities Consumed

- Stage 070 provides the controlled Dev Spaces workspace.
- Stage 110 provides accepted specs and alignment expectations.
- [`../../AGENTS.md`](../../AGENTS.md) and [`../../docs/AI_COLLABORATION.md`](../../docs/AI_COLLABORATION.md) provide human accountability and validation expectations.

## Developer Workflow

The developer starts with an accepted spec from Stage 110, then asks for a change that is tempting to accept quickly but likely to expose a quality gap.

Possible near misses:

- adding a dependency without checking approved versions;
- updating README content without verifying implementation behavior;
- generating deployment YAML that bypasses GitOps;
- proposing an external model path for sensitive source-code context;
- producing code that compiles but violates package, naming, or test conventions.

The review procedure that catches the issue becomes a skill candidate with purpose, when to use it, inputs, steps, constraints, validation commands, and expected output.

## Starter Prompts

```text
Add the simplest implementation for this feature and update the README so the demo can move quickly.
```

```text
Generate the Kubernetes resources needed to deploy this service directly to OpenShift.
```

```text
Use the strongest available model to review this private source code and propose changes.
```

```text
Turn the review checklist that caught this issue into a reusable skill design.
Include purpose, when to use it, inputs, steps, constraints, validation
commands, and expected output. Do not implement tool-specific files yet.
```

## What To Notice And Why It Matters

The proof point is that the workflow catches a plausible failure before it becomes accepted work, then converts the lesson into reusable agent capability.

This matters in regulated enterprise settings because small shortcuts can create real governance problems: source sent to the wrong model, unsupported dependencies, deployment paths outside GitOps, or documentation that overstates implementation.

## How Red Hat And Open Source Make It Work

Red Hat OpenShift Dev Spaces makes the workspace reproducible. Red Hat OpenShift AI MaaS keeps model access visible. GitOps, validation scripts, and project rules define the acceptance path.

Open source assistants remain useful because their output is treated as a proposal. Skills make known review practice portable across agents and repositories.

## Red Hat Products Used

- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** provides the controlled workspace.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides governed model access through MaaS.
- **[Red Hat OpenShift GitOps](https://www.redhat.com/en/technologies/cloud-computing/openshift/gitops)** represents the approved delivery control.

## Open Source Projects To Know

- [Continue](https://www.continue.dev/) provides the IDE assistant used for the near-miss exercise.
- [AgentSkills.io](https://agentskills.io/) defines a portable skill packaging pattern.
- [Kustomize](https://kustomize.io/) and [Argo CD](https://argo-cd.readthedocs.io/) represent the GitOps delivery shape used by the repository.

## TODOs

- TODO: Select one near-miss scenario that is easy to demonstrate and detect.
- TODO: Add before and after example diffs.
- TODO: Add a reusable enterprise readiness rubric for Stage 130 agents.
- TODO: Add a small evaluation set with expected-good prompts, known-bad prompts, validation commands, and pass/fail notes.

## Deploy And Validate

This planned stage has no deploy or validate scripts. Static validation is documentation review only. Shared quality gates and evidence expectations live in [Developer Workflow Validation](../../docs/DEVELOPER_WORKFLOW_VALIDATION.md).

## References

- [AI collaboration model](../../docs/AI_COLLABORATION.md)
- [Vibes, specs, skills, and agents: The four pillars of AI coding](https://developers.redhat.com/articles/2026/03/30/vibes-specs-skills-agents-ai-coding)
- [Engineering an AI-ready code base: Governance lessons from the Red Hat Hybrid Cloud Console](https://developers.redhat.com/articles/2026/04/15/governance-lessons-red-hat-hybrid-cloud-console)
- [Eval-driven development: Build and evaluate AI agents](https://developers.redhat.com/articles/2026/03/23/eval-driven-development-build-evaluate-ai-agents)
- [AI-powered documentation updates: From code diff to docs PR in one comment](https://developers.redhat.com/articles/2026/04/21/ai-powered-documentation-updates-code-diff-docs-pr-one-comment)
- [A guide to AI code assistants with Red Hat OpenShift Dev Spaces](https://developers.redhat.com/articles/2026/01/28/guide-ai-code-assistants-red-hat-openshift-dev-spaces)
- [Red Hat OpenShift GitOps documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/)

## Next Stage

[Stage 130: Agents - Agentic Engineering With OpenCode](../130-agentic-engineering-with-opencode/README.md) shows agents reading specs, selecting skills, using approved tools, and producing reviewable changes.
