# Stage 120: Quality Bar Breakpoint

## Why This Matters

AI assistance can produce plausible output that looks correct before it has been tested against the project's standards. That is the key transition from vibe coding to agentic engineering: the question is not whether the assistant can help, but whether the engineering system can catch gaps before they become accepted changes.

This planned stage introduces a deliberate near miss. The point is not to make the model look bad. The point is to show that professional software still depends on tests, architecture judgment, conventions, policy, and human review.

## Story Goal

Show a useful but imperfect AI-assisted result and catch the issue through an explicit quality gate. The audience should see why free-form prompting is not enough for enterprise software and why the next stage moves into controlled OpenCode agents and skills.

## Platform Capabilities Consumed

- Stage 070 provides the controlled Dev Spaces workspace.
- Stage 110 provides the Continue prompt workflow and initial coding exercise.
- Project rules in `AGENTS.md` and `docs/AI_COLLABORATION.md` provide the human accountability and validation model.

## What This Stage Adds

This planned stage adds the quality-bar transition exercise.

- A deliberately ambiguous prompt or task.
- A plausible assistant output with a detectable defect.
- A review rubric that catches the defect.
- An AI-ready codebase governance layer using project rules, structured documentation, lint rules, and tests as machine-readable control points.
- An eval-driven development pattern for comparing agent outputs against expected-good and known-bad cases.
- A corrected path that demonstrates the expected enterprise standard.
- A narrative bridge from IDE assistance to agentic engineering.

## Developer Workflow

### Starting Point

The developer has already used Continue for a bounded coding task in Stage 110. The same repository or exercise is used again, but the prompt is intentionally broader or underspecified.

### AI-Assisted Task

Ask for a change that is tempting to accept quickly but likely to expose a quality gap. Good candidates include:

- adding a dependency without checking the approved version list;
- updating README content without verifying implementation behavior;
- generating a deployment or pipeline manifest that bypasses GitOps;
- proposing an external model path for sensitive source-code context;
- producing code that compiles but violates package, naming, or test conventions.

The exact example will be selected in the next iteration.

### Prompts Or Agent Instructions

Example near-miss prompts:

```text
Add the simplest implementation for this feature and update the README so the demo can move quickly.
```

```text
Generate the Kubernetes resources needed to deploy this service directly to OpenShift.
```

```text
Use the strongest available model to review this private source code and propose changes.
```

These prompts are intentionally unsafe or incomplete. The stage exists to show how the review process responds.

### Expected Developer Actions

- Let the assistant produce a proposed answer or diff.
- Review the output against project standards.
- Identify the specific defect or policy issue.
- Correct the task framing.
- Re-run the smallest relevant validation check.
- Document what the quality gate caught.

### Review And Quality Gates

- Dependency and version changes must match approved standards.
- Documentation must describe implemented behavior only.
- Project rules such as `AGENTS.md`, `docs/AI_COLLABORATION.md`, lint rules, and tests must be treated as input to the review, not background advice.
- Known-bad prompts and expected-good outputs should be added to the evaluation set when the exact demo task is chosen.
- OpenShift deployment changes must use the approved platform delivery path.
- Sensitive source-code context must stay on the private model path.
- The final corrected output must pass the selected static or test validation.

### Evidence To Capture

- Original ambiguous prompt.
- Defect or policy issue found.
- Review checklist item that caught it.
- Corrected prompt or agent instruction.
- Final validation evidence.

## What To Notice And Why It Matters

The important proof point is that the workflow catches a plausible failure before it becomes accepted work. That is the quality bar Karpathy's distinction points toward: vibe coding raises the floor, but professional engineering needs an explicit system for preserving standards.

This matters in regulated enterprise settings because a small AI-assisted shortcut can create a real governance problem: source sent to the wrong model, an unsupported dependency, a deployment path outside GitOps, or documentation that overstates the implementation.

## How Red Hat And Open Source Make It Work

The platform gives the developer controlled tools, but the quality gate comes from the engineering process around those tools. Red Hat OpenShift Dev Spaces makes the workspace reproducible. MaaS keeps model access visible. GitOps, validation scripts, and project rules define how output becomes acceptable.

Open source assistants remain useful in this model because their output is treated as a proposal that must pass review.

Red Hat's AI-ready codebase guidance strengthens this point: agent behavior improves when repositories expose clear rules, structured docs, lint feedback, tests, and review expectations in formats that tools can consume. Eval-driven development adds a second layer by making non-deterministic assistant behavior measurable through repeatable conversations, generated tests, known-bad cases, CI checks, cost awareness, and telemetry.

## Trust Boundaries

The most important boundary in this stage is the difference between assistant output and accepted engineering work. AI-generated code, documentation, or manifests are not trusted until they pass review and validation. External model suggestions for sensitive source-code context should be rejected unless policy explicitly permits them.

## Red Hat Products Used

- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** provides the controlled workspace where the near miss is reviewed.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides governed model access through MaaS.
- **[Red Hat OpenShift GitOps](https://www.redhat.com/en/technologies/cloud-computing/openshift/gitops)** represents the approved delivery control that generated manifests must not bypass.

## Open Source Projects To Know

- [Continue](https://www.continue.dev/) provides the IDE assistant used for the near-miss exercise.
- [Kustomize](https://kustomize.io/) and Argo CD patterns represent the GitOps delivery shape used by the repository.

## Future Implementation Notes

- Select one near-miss scenario that is easy to demonstrate and easy to detect.
- Add before and after example diffs.
- Add a review rubric that can be reused in Stage 130 as an OpenCode skill.
- Add a small evaluation set with expected-good prompts, known-bad prompts, validation commands, and pass/fail notes.
- Decide whether the failure is caught by tests, docs review, dependency review, or GitOps policy review.

## Deploy And Validate

This planned workflow stage does not yet include deploy or validate scripts. Static validation for this iteration is documentation review only.

## References

- [AI collaboration model](../../docs/AI_COLLABORATION.md)
- [Engineering an AI-ready code base: Governance lessons from the Red Hat Hybrid Cloud Console](https://developers.redhat.com/articles/2026/04/15/governance-lessons-red-hat-hybrid-cloud-console)
- [Eval-driven development: Build and evaluate AI agents](https://developers.redhat.com/articles/2026/03/23/eval-driven-development-build-evaluate-ai-agents)
- [AI-powered documentation updates: From code diff to docs PR in one comment](https://developers.redhat.com/articles/2026/04/21/ai-powered-documentation-updates-code-diff-docs-pr-one-comment)
- [A guide to AI code assistants with Red Hat OpenShift Dev Spaces](https://developers.redhat.com/articles/2026/01/28/guide-ai-code-assistants-red-hat-openshift-dev-spaces)
- [Red Hat OpenShift GitOps documentation](https://docs.redhat.com/en/documentation/red_hat_openshift_gitops/)

## Next Stage

[Stage 130: Agentic Engineering With OpenCode](../130-agentic-engineering-with-opencode/README.md) turns the quality gate into controlled agent roles, skills, permissions, and repeatable workflows.
