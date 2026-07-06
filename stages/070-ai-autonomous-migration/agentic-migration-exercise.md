# Stage 070 Exercise: Autonomous Spring Boot → Quarkus Migration

> **Status:** design complete, pending the OpenCode-compatibility proving run
> in Dev Spaces (see BACKLOG "Stage 070 agentic migration provenance").
> MigIQ is an experimental community project (`@sshaaf/migiq`, pinned to
> `0.2.2`), demonstrated here as a pattern for multi-agent migration under
> platform governance — it is not a supported Red Hat product.

## The Story

Stages 050 and 060 scaled AI assistance from one-shot prompts to
skill-guided tasks. This exercise scales it again: a whole-application
migration executed by cooperating agents — analysis, planning, parallel
execution, test generation, containerization, deployment — while the
platform keeps every model call identified, rate-limited, and measured, and
a human approves the result before it merges.

## Workflow

1. **Open the migration workspace** (Dev Spaces). The workspace clones the
   Spring Boot sample service (from the MigIQ examples) and carries the
   OpenCode + MaaS configuration from Stage 050.
2. **Install the pinned MigIQ skill set** into the workspace project:

   ```bash
   npx @sshaaf/migiq@0.2.2
   ```

   This lays down the `migiq` orchestrator and the `mig-*` skills
   (`graphify`, `plan`, `execute`, `test-gen`, `containerize`, `deploy`).
3. **Ground with MTA first (recommended):** run an MTA analysis of the
   sample app and keep the report open — the supported product's findings
   are the checklist the agentic result must satisfy.
4. **Run the orchestrated migration** with the agent
   (`/migiq` interactive mode for demos; approve each phase):
   - graphify: knowledge-graph analysis of entities, dependencies, clusters;
   - plan: dependency-ordered tasks (expect ~100+ subtasks);
   - execute: parallel sub-agents apply Spring→Quarkus transformations;
   - test-gen: unit tests for migrated code.
5. **Human review gate (mandatory):** review the diff against the MTA
   findings and project standards; reject or re-run phases as needed.
   Nothing merges on agent authority.
6. **Containerize and deploy** to OpenShift; verify the running service.
7. **Show the governance evidence:** the Stage 040 MaaS usage dashboard
   during the run — per-model token consumption of an autonomous multi-agent
   workload, attributable to the developer's MaaS key.

## Model Routing

| Role | Model | Why |
|------|-------|-----|
| Execution agents | `qwen3-6-35b-a3b` | strong coding model, tool calling, 32K context |
| Planning / graph context | `nemotron-3-nano-30b-a3b` | 131K context for repository-scale analysis |

Both are private models on the platform; prompts and source code never leave
the OpenShift boundary. Expect a token-heavy run — that is part of the
demo's honesty about what autonomy costs and why token limits exist.

## Open Items Before This Exercise Is Demo-Ready

- [ ] Proving run: MigIQ skills under OpenCode (project is Claude-Code-first;
      `.opencode/skills` compatibility must be verified in Dev Spaces).
- [ ] Workspace wiring: DevWorkspace entry for the Spring Boot sample with
      the pinned MigIQ install in postStart (Stage 050 pattern).
- [ ] Model behavior: confirm the qwen tool-call parser handles MigIQ's
      structured prompts; fall back to nemotron as executor if needed.
- [ ] Evidence capture: scripted before/after test + MaaS usage screenshots
      for the stage README.
