# Stage 060: Agentic Development

**Theme:** From one-shot prompts to skill-guided agents
**Concept:** Enterprise development guidelines become reusable skills that AI agents follow — and improve — inside governed workspaces.

> **Status:** deployable. This stage provisions the `agentic-coolstore`
> DevWorkspace: coolstore-inventory-service checked out on the
> `demo/agentic-skills` branch (AGENTS.md + `.opencode/skills` Quarkus
> standards, authored and pushed), with agent-scale resources for OpenCode
> multi-step runs. It consumes the Stage 050 Dev Spaces platform and the
> Stage 040 MaaS keys. Flip the workspace checkout to `main` once the skills
> branch merges.

## Why This Matters

Stage 050 ends with an honest observation: one-shot prompting produces
plausible code that ignores project standards, misses multi-file consistency,
and forgets hidden requirements. Enterprises do not fix that by writing
longer prompts — they fix it by teaching the agent how the team builds
software.

This stage shows that path: OpenCode running in the same governed workspace,
now with `AGENT.md` (project identity, build and test commands) and a set of
reusable skills that encode how this team builds Quarkus applications —
REST resource conventions, Panache entity patterns, test standards, and
OpenAPI documentation rules. The same task that produced a mediocre one-shot
result in Stage 050 is repeated here with the agent following the skills.

The bigger message for platform teams: internal development guidelines stop
being wiki pages that nobody reads and become living, versioned assets that
agents apply on every change — and that humans improve through review
feedback.

## What This Stage Adds

- OpenCode as the terminal coding agent in the Stage 050 workspaces,
  authenticated to MaaS-published models (no personal provider keys).
- `AGENT.md` in the coolstore-inventory-service repository: project map,
  build/test commands, and pointers to the skills.
- Reusable Quarkus skills (workspace repository): REST endpoint conventions,
  Panache entity patterns, project test standards, API documentation rules.
- A comparison exercise: the Stage 050 one-shot task re-run under skills.
- A skill-improvement exercise: review feedback turned into a skill update.

## Demo Script

### Part 1 — The same task, with the team's standards loaded

**Know.** Stage 050 ended with plausible-but-unreviewable code. Enterprises
fix that by encoding standards where agents can execute them: AGENT.md and
reusable skills in the repository, versioned and reviewed like code.

**Show.**
- Open the `agentic-coolstore` workspace (Dev Spaces). Show the repository's
  `AGENTS.md` and `.opencode/skills/` — four skills that encode how this
  team builds Quarkus services (REST conventions, domain model, test
  standards, docs consistency).
- In the terminal, start OpenCode and give it the same class of task the
  one-shot attempt fumbled in Stage 050 (for example: "add a reservation
  endpoint for inventory items").
- Narrate what is different: the agent consults the skills, follows the
  `/api/` path conventions, writes behavior-named tests with RestAssured,
  and updates the README API table in the same change — because the
  definition of done lives in the skill, not in the prompt.
- **What they should notice:** nobody wrote a long prompt. The standards
  did the steering, and they are a pull request away from improving.

### Part 2 — Fail forward: the gate fails, the agent fixes it under rules

**Know.** The most convincing demo beat is a failure handled well (adapted
from the platform showroom's pipeline-fails moment). Quality gates exist
precisely so AI-generated code cannot skip review discipline.

**Show.**
- Introduce a deliberate smell into the change (a `System.out.println` and
  an empty catch block) or use a prepared branch, and run `./mvnw test` /
  the project's quality checks so a gate fails visibly.
- Hand the failure back to OpenCode. The `project-test-standards` skill
  forbids weakening assertions, and the REST skill mandates proper error
  contracts — so the agent fixes the code, not the test.
- Close the loop: "Review feedback that recurs becomes a skill update —
  the guideline is now enforced on every future run. That is what it means
  for internal standards to be living assets."

## Deploy And Validate

```bash
./stages/060-ai-agentic-development/deploy.sh
./stages/060-ai-agentic-development/validate.sh
```

Manifests: [`gitops/stages/060-ai-agentic-development/base/`](../../gitops/stages/060-ai-agentic-development/base/)

## Next Stage

[Stage 070: Autonomous Application Migration](../070-ai-autonomous-migration/README.md)
scales from skill-guided single tasks to a multi-agent migration workflow.
