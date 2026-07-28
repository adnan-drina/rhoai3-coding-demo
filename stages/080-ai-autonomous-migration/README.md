# Stage 080: AI-Autonomous Migration with an Agent Harness

The previous stages built the AI maturity ladder one rung at a time, and both stages end with a human driving every cycle. This stage asks the next question: what has to be true for an agent to carry a whole-application migration largely on its own?

Legacy applications are not just expensive to maintain. They are an expanding attack surface. AI-powered exploit tools lower the cost of finding and weaponizing vulnerabilities in outdated frameworks, and regulations are catching up: the EU Cyber Resilience Act makes vendors accountable for the security posture of every product they ship, including the libraries and runtimes underneath it. The migration backlog is no longer a cost problem alone; it is a compliance and security deadline that most teams cannot meet with manual effort.

This demo stage answers with two complementary paths on the same governed platform: assisted modernization through Migration Toolkit for Applications turning a legacy codebase into an inventory of concrete, prioritized migration issues, and autonomous migration where an agent harness takes a legacy service end-to-end to Quarkus with analysis-grounded planning, spec generation, self-evaluation loops, and a trusted software supply chain pipeline that enforces quality and security before anything merges.

Application domain experts remain essential. Agents handle the volume (hundreds of files, thousands of import rewrites, test scaffolding), but domain experts define what correct migration means: which business behaviors must be preserved, which integration contracts matter, where the analysis findings are real issues versus acceptable deviations. The harness encodes their judgment as guides and sensors; they improve those assets after each run rather than reviewing every line the agent writes.

## What You'll Do

You will **provision** a migration workspace through a golden-path template that, unlike stage 070's greenfield scaffold, takes the **Git repository of the legacy application you want to migrate** as input and delivers a Dev Spaces workspace with the MTA tools, the harness runbook, and migration standards preconfigured, **analyze** the legacy code with MTA so the findings become the migration's ground truth, **understand the harness** that will govern the agents (guides that steer, sensors that catch, humans that improve the harness itself), **let the orchestrator plan** by reading the findings and the legacy code and writing the migration spec, plan, and task list in the spec-kit layout, **watch the harness migrate** the service as it dispatches OpenRewrite for the mechanical transforms and OpenCode for the judgment work, one bounded task at a time, with sensors after every task and correction packets on failure, and finally **ship through the factory**: the project's delivery pipeline with its SonarQube quality gate is the merge authority, with the full token cost of autonomy visible on the platform's usage dashboard.

---

## Step 1: Sign in to Developer Hub

1. Open the Developer Hub URL and sign in as `ai-developer` (OpenShift OIDC).

**What you should see:** the RHDH home screen with the catalog search bar.

---

## Step 2: Create your migration project from the template

Stage 070's template scaffolded a greenfield service from nothing. The migration template inverts the input: you bring an existing codebase.

1. Open **Self-service** and choose the **Application migration** template.
2. Provide the input the template asks for:
  - **Legacy repository URL**: HTTPS Git URL clonable without credentials. The demo default is the Coolstore **cart** service ([coolstore-cart-legacy](https://github.com/adnan-drina/coolstore-cart-legacy.git)) — small enough for a workshop run. The monolith round used [mca-coolstore](https://github.com/rhpds/mca-coolstore.git).
  - **Project name**: becomes the per-run repository, namespace, and workspace name, exactly like stage 070.
  - **Acceptance endpoint**, **Preserve tokens**, and **Forbidden patterns**: stamped into `migration.yaml` so sensors know what “shipped” and “must not fabricate” mean for *this* legacy app (cart defaults are pre-filled; change them when you bring your own repo).
  - **Needs database**: leave off for cart (stateless); enable when the legacy app persists to PostgreSQL.
3. Create, and watch the template run: fetch the migration scaffold → stamp provenance and acceptance/preserve/forbidden into `migration.yaml` → publish the **destination** repository → register it in the catalog (its first push bootstraps the namespace and pipeline through the platform dispatcher). The legacy code itself is **not** copied anywhere: the workspace clones it read-only at start, side by side with the destination, `/projects/legacy` next to `/projects/modernized`.

**What you should see:** a new catalog component for the migration **destination** (the legacy app never appears in the catalog), with links to the destination repository, Dev Spaces, and SonarQube, the same self-service pattern as stage 070, now wrapped around code that already exists.

> **Why this matters:** migration is where self-service pays off most. Nobody hand-wires analysis tooling, workspaces, and pipelines for every one of hundreds of legacy services. The template makes "start migrating this repo" a ten-second operation with every tool pre-approved by the platform team.

---

## Step 3: Analyze the legacy code with MTA

Before any agent writes a line, the supported product establishes the facts.

1. Open the workspace from the component page's **Dev Spaces** link. Both projects clone automatically: `legacy/` (the application you're migrating, read-only) next to `modernized/` (your destination repository). The MTA extension pack installs on first start (1–2 minutes).
2. Click the **MTA icon** in the left Activity Bar (the Konveyor logo), then **Open Analysis Panel**. Give the panel a moment on first open: the Java language server initializes in the background (the workspace pre-configures Standard mode so the analysis provider registers without opening a `.java` file first).
3. Click **Start** (top right of the Analysis View). **Server Status** flips from `Stopped` to `Running`, which boots the analyzer engine inside the workspace. Leave **Agent Mode** off; the platform runs MTA analysis-only.
4. Click **Manage Profiles**. The legacy repository ships its own analysis profiles in `.konveyor/profiles/`; select `quarkus-profile` (Quarkus migration targets; the `audit-logging` profile adds custom organization rules).
5. Back in the Analysis View, click **Run Analysis**. The first run downloads rulesets and scans the whole legacy tree (several minutes for a monolith; later runs are much faster as everything caches in the workspace).
6. Review the findings: the issue tree in the MTA panel, plus inline diagnostics directly in `legacy/` source files. Every finding is anchored to a rule, file, and line, with mandatory issues and effort estimates. Each run is also saved as machine-readable JSON at `legacy/.vscode/mta-core/analysis_<timestamp>.json`, which is what the agent consumes in the spec step.
7. Keep the findings open. From this point on, the analysis is the **checklist the agentic result must satisfy**: the migration is done when the findings are resolved, not when the agent says so.

> **Expected panel state:** two informational cards are normal: *"GenAI
> functionality is disabled"* and *"Hub Configuration: No features
> enabled"*. They gate the Developer Lightspeed surface (the hub's
> Solution Server for AI remediation suggestions, and centralized Profile
> Sync), which this platform intentionally leaves off: the agent harness
> in `modernized/` is this exercise's remediation engine, and analysis
> profiles are versioned in the legacy repository (`.konveyor/profiles/`)
> instead of synced from the hub. Analysis itself needs neither.

**What you should see:** the analysis panel enumerating concrete migration issues in the legacy code, and squiggles in the legacy sources where each issue lives.

> **Console alternative:** the same analysis runs server-side in the MTA
> console (application launcher → MTA, which auto-redirects through
> **platform SSO**, the same OpenShift login as Developer Hub, with your
> MTA role resolved from the platform realm). Add the legacy repository
> to the Application Inventory, run the analysis, and open the report
> under the application's Reports tab. The in-workspace path above is the
> demo default: the findings land exactly where the agent will work.

---

## Step 4: The concept, an AI Agent Harness

Stage 070 introduced two kinds of agent context: the memory bank and specs. This stage adds the third idea, from Birgitta Böckeler's [Harness Engineering for Coding Agents](https://martinfowler.com/articles/harness-engineering.html): **Agent = Model + Harness**. The model is fixed; the harness is everything the platform engineers around it, and it comes in two kinds:

- **Guides (feedforward):** steer the agent *before* it acts: standards, rules, specs, architectural constraints.
- **Sensors (feedback):** catch problems *after* it acts and feed them back so the agent can self-correct: builds, tests, linters, analyzers, review agents.

Each kind exists in two execution forms: **computational** (deterministic and fast: compilers, tests, recipes, static analysis) and **inferential** (semantic, model-driven: an agent reviewing another agent's diff). Fast, cheap sensors run early and often inside the loop; expensive ones guard the exit.

Böckeler's follow-up, [Maintainability sensors for coding agents](https://martinfowler.com/articles/sensors-for-coding-agents.html), confirms a practice this harness already leans on: a red sensor should carry **self-correction guidance**, not only the raw failure. Our factory-parity sensors (`sensors.sh`) print a short `FIX:` block with the evidence — what to change, what not to waive, and which runbook section applies — so the correction session spends tokens on the root cause instead of re-deriving the policy.

Everything this platform already operates maps onto that picture:

| Harness part                           | Kind                             | Platform asset                                                                    |
| -------------------------------------- | -------------------------------- | --------------------------------------------------------------------------------- |
| Migration standards, AGENTS.md, skills | Guide                            | Stage 070 memory-bank assets, extended with migration skills                      |
| Migration spec, plan, tasks            | Guide                            | spec-kit artifacts generated in Step 5                                            |
| MTA analysis findings                  | Sensor (computational)           | The Step 3 report, re-run to verify findings are resolved                         |
| OpenRewrite recipes                    | Guide + Sensor                   | Deterministic transforms for the mechanical share of the migration                |
| Build + tests                          | Sensor (computational)           | Maven build and the test suite, run by Hermes after every task                    |
| Self-review / evaluation pass          | Sensor (inferential)             | The orchestrator's milestone eval against the spec in Step 6                      |
| SonarQube + factory pipeline           | Sensor (computational, **exit**) | The regulated merge authority, same gate as stages 060/070                        |
| Human steering                         | Judgment                         | Improving guides and sensors when the loop exposes gaps, not per-change approval  |

Two things follow. First, the loop inverts: in stage 060 *you* read the SonarQube report and prompted the fix; here the harness feeds sensor output back to the agent, which iterates until the checks pass. Quality shifts from inspection to regulation. Second, humans move up a level: nothing merges on agent authority because the **factory** won't let it, so instead of reviewing every intermediate diff, you observe where the loop struggled and **improve the harness**. Böckeler calls this the steering loop, and it is the stage 070 "skills retro" practice graduated into a system.

### The migration process: five stages, two feedback loops

The harness runs a staged process (the "M-process"). Every stage has explicit input and output artifacts committed to the repository (`git log --oneline` reads as the process narrative) and a deterministic gate guards each hand-off. Modernization is incremental by design: M2 cuts the work into dependency-ordered **stories**, and M3→M5 cycle per story. No big bang.

```text
      ┌──── outer loop (automated): Retro → remaining briefs only ──────────────┐
      │                    steering (human): skills / sensors / runbook ────────┤
      ▼                                                                         │
┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐
│ (1)  M1   │    │ (2)  M2   │    │ (3)  M3   │    │ (4)  M4   │    │ (5)  M5   │
│  ANALYZE  │───▶│ SEQUENCE  │───▶│  SPECIFY  │───▶│ IMPLEMENT │───▶│ EVALUATE  │──┘
│           │    │           │    │ per story │    │ per story │    │ per story │
└───────────┘    └───────────┘    └─────┬─────┘    └─────┬─────┘    └─────┬─────┘
 [analysis         [roadmap        ▲    │ lint      ▲    │ sensors        │
  pipeline]         lint]          └────┘ red →     └────┘ red → fix      │
                                   revision loop    session (inner loop)  │
                                                                          │
              next story from the roadmap  ◀──────────────────────────────┘
              (failed story stops the run; resume via story-state.csv)
```

| # | Stage | Enabling technology | Tasks it performs | Output artifacts (committed) |
|---|---|---|---|---|
| 1 | **M1 ANALYZE** | MTA/kantra (Windup rules incl. platform contract rules), OpenRewrite recipes, dependency-graph script, one Hermes analyst session | Rule-based analysis of the legacy app (migration path + jakarta + cloud-readiness + JDK targets); classify every finding against the MAPPINGS rule-joins; compute the conversion order and god nodes; pre-execute mechanical recipes (jakarta) into a staging tree; write the architecture profile: components, integration surfaces, behavioral contract sources, domain seams | `mta-findings.json`, `findings-inventory.md`, `dependency-order.md`, `recipe-log.md` + staged sources, `architecture-profile.md` |
| 2 | **M2 SEQUENCE** | Hermes planner session guided by the SEQUENCING skill; `roadmap-lint` gate | Cut the modernization into dependency-ordered stories (models before services before surfaces; domain seams for monoliths); mark deploy milestones; write one self-contained brief per story with real legacy code excerpts and the contracts that story owns | `roadmap.md`, `briefs/S*.md` |
| 3 | **M3 SPECIFY** | spec-kit workflow (Hermes session per story); story-scoped `plan-lint` gate | Turn one brief into spec / plan / tasks: behavioral contract from legacy tests, decided target shapes from MAPPINGS, rewrite-before-infer ordering, characterization tests early, recipe-executed rules excluded | `specs/S<NN>/{spec,plan,tasks}.md` |
| 4 | **M4 IMPLEMENT** | Supervisor task loop; Hermes orchestrator + OpenCode worker (packets); skills + AGENTS.md rules; task/milestone sensors (isolated Maven repo, in-loop SonarQube) | Execute the story's tasks one commit each; harvest from the recipe-staged sources; port/pin contract tests; every commit sensor-verified; red commits get autonomous fix sessions; mechanical commit closure for green-but-uncommitted work | code + tests, one `T-NNN:` commit per task, `run-log.md` rows |
| 5 | **M5 EVALUATE** | Pre-push preflight (full quality gate + boot check); Tekton factory pipeline + SonarQube gate; kantra after-analysis (script step); Hermes retro session | Gate the story locally, ship through the factory; deploy stories must serve their acceptance endpoints live; measure the findings delta (before vs destination); write retro proposals | pipeline + gate results, deployed increment, `findings-delta`, `retro-proposals.md` |

The **inner loop** (sensors → fix sessions, lint → revision) corrects the *work* within minutes. The **outer loop** (automated) applies Retro's brief updates to **remaining** stories so the next brief starts smarter — it does not rewrite the roadmap mid-run, and a failed story stops the run (resume from `migration/story-state.csv`). The **steering loop** (human) takes Retro's skill/sensor/runbook proposals into a follow-up PR; the agent never auto-edits `.hermes/skills/**`.

Two equal demo tracks share the same M-process and gates:

| Track | Who drives | How you start |
|---|---|---|
| **A — Interactive / story walkthrough** | You run Hermes sessions stage by stage (or one story at a time via `supervisor.sh`) | Steps 5–7 below |
| **B — Autonomous outer loop** | `outer-loop.sh` owns M1→M2 and every story's M3→M5 | `nohup .hermes/harness/outer-loop.sh > /tmp/outer-loop-nohup.log 2>&1 &` then `tail -f /tmp/outer-loop.log` |

### The harness implementation: Hermes Agent

Concepts need a runner. This stage uses **[Hermes Agent](https://hermes-agent.nousresearch.com/docs)** (Nous Research) as the harness implementation that owns the autonomous loop: a CLI-first agent that consumes the project's guides, runs the sensors as tools (build, tests, OpenRewrite, analysis), and iterates until the checks pass or the budget expires. The properties that matter here:

- **CLI-native, headless-capable**: `hermes chat -q "..."` runs a one-shot turn (including in non-TTY workers), and `hermes -w -z "..."` runs one in an isolated git worktree. The loop is drivable from a terminal and from automation alike.
- **Governed models, first-class**: `~/.hermes/config.yaml` points at any OpenAI-compatible endpoint, our MaaS gateway with a platform-issued key, so every loop iteration is metered like everything else on this platform.
- **Continuity with what you already built**: Hermes speaks the AGENTS.md and [agentskills.io](https://agentskills.io/home) mental model this project has used since stage 070. The guides in this repository are its guides, and its built-in learning loop (skills created and improved from experience) is the "skills retro" practice running inside the agent itself.
- **A real task system for real migrations**: the Kanban board (`~/.hermes/kanban.db`) is a durable, multi-agent task graph. A dispatcher decomposes work into child tasks, routes them to specialist worker profiles, and each worker is a full OS process reporting back to the board. That is the ~100-task shape a whole-application migration actually has.

> **Why Hermes over other agent frameworks?** The choice comes down to
> fit: Hermes is CLI-native and headless-first (`hermes chat -q`), speaks
> the AGENTS.md + agentskills.io conventions this project already uses,
> points at any OpenAI-compatible endpoint (our MaaS gateway), and its
> Kanban task graph matches the ~100-task shape of a real migration.
> Alternatives like [OpenClaw](https://docs.openclaw.ai/) are strong
> products but center on gateway/session management rather than the
> terminal-driven autonomous loop this stage teaches.

Division of labor: **Hermes is the orchestrator** (it plans and drives the loop but never edits application source) and **OpenCode is the coding worker inside the harness**, dispatched one bounded task at a time via `opencode run`. The whole contract is versioned in the repository as the **migration-harness runbook** (`.hermes/skills/migration-harness/`), which the workspace links into Hermes' skill path automatically; the interactive `/speckit.*` commands from stage 070 remain available when you want to author specs yourself.

---

## Step 5: Plan the migration (Track A interactive, or start Track B)

The MTA findings say what must change; the spec says what the migrated service must be. In this stage the **orchestrator writes the contract**. You review it; you don't have to author it.

### Track B — autonomous (preferred for the full M-process)

One command owns M1→M2 and every story's M3→M5, including brief refresh after each successful story:

```bash
cd /projects/modernized
nohup .hermes/harness/outer-loop.sh > /tmp/outer-loop-nohup.log 2>&1 &
tail -f /tmp/outer-loop.log
```

If a story fails, the loop stops before dependents. Fix or waive, then relaunch — `migration/story-state.csv` skips stories already marked `complete`.

### Track A — interactive walkthrough

1. In a workspace terminal, start planning (whole-app path skips M2; story mode uses briefs from an earlier M2):
  ```bash
   cd /projects/modernized
   hermes chat -q "Use the migration-harness skill. Execute M1 (normalize ground truth) and M3 (plan)."
  ```
   Or drive ground truth with the script the outer loop uses: `.hermes/harness/analyze.sh`, then a Hermes session for M3 only.
2. Watch what the runbook makes Hermes do: normalize analysis into `migration/mta-findings.json`, script-extract violation counts rather than reading the file into context, then write `specs/.../spec.md`, `plan.md`, and `tasks.md` (every task tagged `Class: rewrite` or `Class: infer`, rewrite first, each citing finding rule ids).
3. Skim the artifacts — a soft, non-blocking checkpoint. Mechanical findings should be tagged `rewrite` and delegated to **OpenRewrite**; the interactive `/speckit.*` path from stage 070 remains available if you prefer to author the spec yourself.

A `hermes chat -q` run is a headless one-shot session. The prompt names the **migration-harness skill**, and Hermes loads the runbook from `.hermes/skills/migration-harness/`. Each M-stage ends with one commit: in this harness a commit is a claim that the stage completed and its outputs are traceable.

**What you should see:** spec, plan, and tasks in the repository, written by the orchestrator, traceable line-by-line to MTA findings and observed behavior (Track A), or the same artifacts appearing story-by-story under Track B's log.

---

## Step 6: Watch the harness migrate

### Track B

If you started `outer-loop.sh` in Step 5, keep watching `/tmp/outer-loop.log` and `/tmp/supervisor.log`. Per story the outer loop runs M3 (plan-lint gated), then `supervisor.sh` for M4/M5.

### Track A

You start the run and observe; Hermes (or the supervisor) drives.

1. Start execution for the tasks you planned:
  ```bash
   hermes chat -q "Use the migration-harness skill. Execute M4 for the tasks in specs/<story>/tasks.md."
  ```
   Or the supervised path (same engine Track B uses per story):
  ```bash
   nohup .hermes/harness/supervisor.sh > /tmp/supervisor-nohup.log 2>&1 &
   tail -f /tmp/supervisor.log
  ```
2. What the runbook enforces, per task:
  - **rewrite tasks**: Hermes copies the legacy source to `/tmp/rewrite-staging`, runs OpenRewrite there, and dispatches a **harvest task** to OpenCode;
  - **infer tasks**: Hermes hands OpenCode one bounded task packet via `opencode run`, then verifies claimed changes against `git status`;
  - **sensors after every task**: the supervisor runs factory-parity checks (`sensors.sh`); a red result includes evidence plus a `FIX:` guidance block and becomes a correction packet (two attempts); exhausted budget lands in `migration/debt.md`.
3. Your job is observation. `migration/run-log.md` accumulates one line per task; where retries cluster is where the harness needs improving (Step 8 steering).

Each task runs in a fresh orchestrator session. Hermes writes a **task packet** with a fixed schema, verifies independently, and ends each completed task in one commit prefixed with its task id: the git history *is* the execution trace.

**What you should see:** the loop converging task by task: recipes for the mechanical share, bounded worker runs for the judgment share, sensors between every step.

> **Honesty beat:** autonomy is token-hungry. Every iteration of the loop is metered through the developer's MaaS key; Step 8 shows the bill. That cost profile is why token limits exist and why deterministic transforms carry the mechanical share of the work.

> **Why these models:** the two harness roles have different failure
> modes, so the platform seats them separately and selected each seat in
> a full-migration A/B. The **orchestrator** (MiniMax M2, 196K context)
> is selected for what the loop demands of a supervisor: lean sessions,
> reliable long-horizon tool calling, and composure on large work
> orders. The **worker** (`qwen3-6-27b`, served on the cluster GPU
> behind the governed MaaS gateway) is the strongest evaluated coding
> seat (SWE-bench 77.2, AA Coding 53.7). Every code edit runs on the
> governed local model, metered on the developer key. The runbook also
> documents an all-local routing option (the 27B in both seats behind
> the supervisor). Selection history and serving details live in
> `docs/OPERATIONS.md`.

---

## Step 7: The factory ships it

Nothing merges on agent authority, and no human approval substitutes for the factory either.

1. M5 re-analyzes the **migrated** code (`migration/mta-findings-after.json`). Done is the Step 3 baseline resolved or explicitly waived, never "the agent says done."
2. The supervisor pushes. Its report ends there by contract: "pushed; the factory pipeline decides." (Pushing from the workspace requires your Git credentials.)
3. Watch the project's pipeline: clone → build → SonarQube quality gate → image. **Red CI means autonomy failed the regulated exit**; green CI is the platform's proof.
4. Spot-check the diff if you like — optional. If something slipped through, tighten a guide or sensor and re-run: that is the **steering** loop (human), not an auto-edit of skills mid-run.

Under Track B, deploy stories must also hit the acceptance path from `migration.yaml` live before the story is marked complete; then Retro may refresh remaining briefs before the next story.

**What you should see:** an evidence-backed migration shipping through the factory: findings delta recorded, tests green, quality gate passed, with the pipeline, not a person, as the merge authority.

---

## Step 8: The bill and the retro

1. Open the Stage 040 MaaS usage dashboard: the token consumption of the full autonomous run (orchestrator and worker on the same developer key) next to the interactive stages' usage. Autonomy is visible on the same meter as everything else.
2. Read `migration/retro-proposals.md`: **Brief updates** may already have been applied by the outer loop to remaining stories; **Skill / harness proposals** are for you — land them as versioned changes to the repository's guides, exactly like the stage 070 skills retro. Also skim `migration/run-log.md` and `migration/debt.md` for retry clusters.

> **Token governance beat (MTA 8.2):** interactive sessions run on
> five-minute access tokens; automation runs on **API keys** you create in
> the MTA console (your username menu → Tokens → Create API Key), scoped
> to your role, usable by CI jobs and automation, and
> revocable instantly from the same page. Create one, show a scripted hub
> API call with it, then revoke it: governed automation credentials with a
> visible lifecycle, the same story the platform tells for model keys.

**What you should see:** the complete, attributed cost of the autonomous run on the platform dashboard, and a written record of where the harness needs to get better.

---

## Wrap-up

### What you proved

- **Analysis grounds autonomy:** MTA's findings, not the agent's self-assessment, defined done.
- **The harness regulates quality:** guides steered generation, sensors caught and fed back failures, and the agent iterated to green before a human ever looked.
- **Determinism where possible, inference where needed:** OpenRewrite carried the mechanical transforms; the model spent its budget on judgment calls.
- **The factory, not a person, was the merge authority:** the agent could push, but only the pipeline and its quality gate could turn that push into a trusted artifact. Humans moved up a level, from reviewing diffs to improving the harness.
- **Governance held at full autonomy:** same identity, token limits, and telemetry as every previous stage, just more visible, because agents consume more.

## Red Hat Products Used

- **[Migration Toolkit for Applications](https://developers.redhat.com/products/mta)** turns legacy code into a concrete, prioritized inventory of what must change. The agent cannot define "done" on its own; MTA's findings are the ground truth.
- **[Red Hat Developer Hub](https://developers.redhat.com/rhdh)** makes "start migrating this repo" a ten-second self-service operation. No tickets, no hand-wiring of tooling per application.
- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** gives each migration a preconfigured workspace with analysis tools, agent runtime, and governed model access ready from first start.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** governs every model request through MaaS: identity, API keys, rate limits, token budgets, and usage telemetry, so autonomous workloads stay within organizational boundaries.
- **[Red Hat OpenShift Pipelines](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/)** is the merge authority. No agent, and no human, bypasses the quality gate. Green CI is the platform's proof, not anyone's claim.
- **[Red Hat build of Keycloak](https://access.redhat.com/products/red-hat-build-of-keycloak)** provides single sign-on across MTA, Developer Hub, and the cluster, so every action is attributed to a real identity.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** is the foundation: runtime, identity, networking, storage, and GitOps-managed state that makes the whole platform reproducible.

## Open Source Projects To Know

- [Konveyor](https://www.konveyor.io/) is the upstream modernization community behind MTA.
- [Kantra](https://github.com/konveyor/kantra) provides CLI-based application analysis.
- [OpenRewrite](https://github.com/openrewrite/rewrite) provides deterministic, recipe-driven code transformation.
- [spec-kit](https://github.com/github/spec-kit) is the spec-driven development toolkit carried over from stage 070.
- [Hermes Agent](https://hermes-agent.nousresearch.com/docs) is the CLI-first agent harness that owns the autonomous migration loop.
- [OpenCode](https://opencode.ai/) is the coding worker inside the harness, dispatched by Hermes one bounded task at a time, and remains available interactively, carried over from stage 070.
- [Coolstore cart (legacy demo input)](https://github.com/adnan-drina/coolstore-cart-legacy) is the default Spring Boot migration target; the [Coolstore monolith](https://github.com/rhpds/mca-coolstore) remains available for longer runs.

## References

| Resource                                      | Link                                                                                                                                                                 |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Harness Engineering for Coding Agents         | [https://martinfowler.com/articles/harness-engineering.html](https://martinfowler.com/articles/harness-engineering.html)                                             |
| Maintainability sensors for coding agents     | [https://martinfowler.com/articles/sensors-for-coding-agents.html](https://martinfowler.com/articles/sensors-for-coding-agents.html)                                 |
| Hermes Agent documentation                    | [https://hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs)                                                                             |
| OpenClaw documentation (compared alternative) | [https://docs.openclaw.ai/](https://docs.openclaw.ai/)                                                                                                               |
| MTA 8.2 documentation                         | [https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.2/](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.2/) |
| OpenRewrite documentation                     | [https://docs.openrewrite.org/](https://docs.openrewrite.org/)                                                                                                       |
| spec-kit: spec-driven.md                      | [https://github.com/github/spec-kit/blob/main/spec-driven.md](https://github.com/github/spec-kit/blob/main/spec-driven.md)                                           |
| MaaS code assistant quickstart                | [https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)                     |


