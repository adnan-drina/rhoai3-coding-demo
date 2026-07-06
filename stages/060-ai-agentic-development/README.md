# Stage 060: Agentic Development

**Theme:** From one-shot prompts to skill-guided agents
**Concept:** Enterprise development guidelines become reusable skills that AI agents follow — and improve — inside governed workspaces.

> **Status:** Workflow stage under construction. The demo design is approved
> (see [docs/PLAN-developer-arc-restructure.md](../../docs/PLAN-developer-arc-restructure.md));
> the skills and AGENT.md live in the
> [coolstore-inventory-service](https://github.com/adnan-drina/coolstore-inventory-service)
> workspace repository and are being authored now. This stage consumes the
> Stage 050 Dev Spaces workspaces and the Stage 040 MaaS endpoints; it deploys
> no additional platform resources.

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

## Deploy And Validate

This is a workflow stage: no `deploy.sh`. Validate the workspace assets with
the Stage 050 validation plus the demo script in this README once the
workspace repository skills land.

## Next Stage

[Stage 070: Autonomous Application Migration](../070-ai-autonomous-migration/README.md)
scales from skill-guided single tasks to a multi-agent migration workflow.
