# Stage 080: AI-Autonomous Migration with an Agent Harness

The previous stages built the AI maturity ladder one rung at a time, and both stages end with a human driving every cycle. This stage asks the next question: what has to be true for an agent to carry a whole-application migration largely on its own?

Legacy applications are not just expensive to maintain. They are an expanding attack surface. AI-powered exploit tools lower the cost of finding and weaponizing vulnerabilities in outdated frameworks, and regulations are catching up: the EU Cyber Resilience Act makes vendors accountable for the security posture of every product they ship, including the libraries and runtimes underneath it. The migration backlog is no longer a cost problem alone; it is a compliance and security deadline that most teams cannot meet with manual effort.

This demo stage answers with two complementary paths on the same governed platform: assisted modernization through Migration Toolkit for Applications turning a legacy codebase into an inventory of concrete, prioritized migration issues, and autonomous migration where an agent harness takes a legacy service end-to-end to Quarkus with analysis-grounded planning, spec generation, self-evaluation loops, and a trusted software supply chain pipeline that enforces quality and security before anything merges.

## What You'll Do

You will **provision** a migration workspace through a golden-path template that, unlike stage 070's greenfield scaffold, takes the **Git repository of the legacy application you want to migrate** as input and delivers a Dev Spaces workspace with the MTA tools, the harness runbook, and migration standards preconfigured, **analyze** the legacy code with MTA so the findings become the migration's ground truth, **understand the harness** that will govern the agents (guides that steer, sensors that catch, humans that steer the harness itself), **let the orchestrator plan** — Hermes reads the findings and the legacy code and writes the migration spec, plan, and task list in the spec-kit layout — **watch the harness migrate** the service: Hermes dispatches OpenRewrite for the mechanical transforms and OpenCode for the judgment work, one bounded task at a time, with sensors after every task and correction packets on failure, and finally **ship through the factory**: the project's delivery pipeline with its SonarQube quality gate is the merge authority — not any agent's summary, and not a human approval step — with the full token cost of autonomy visible on the platform's usage dashboard.

---



## Step 1: Sign in to Developer Hub

1. Open the Developer Hub URL and sign in as `ai-developer` (OpenShift OIDC).

**What you should see:** the RHDH home screen with the catalog search bar.

---



## Step 2: Create your migration project from the template

Stage 070's template scaffolded a greenfield service from nothing. The migration template inverts the input: you bring an existing codebase.

1. Open **Self-service** and choose the **Application migration** template.
2. Provide the input the template asks for:
  - **Legacy repository URL**: the Git repository of the application to migrate — any HTTPS URL clonable without credentials. The demo uses the legacy Coolstore monolith, [https://github.com/rhpds/mca-coolstore.git](https://github.com/rhpds/mca-coolstore.git) — the same brownfield code MTA has been pointed at since stage 050.
  - **Project name**: becomes the per-run repository, namespace, and workspace name, exactly like stage 070.
3. Create, and watch the template run: fetch the migration scaffold → stamp the legacy URL into the workspace definition and `migration.yaml` (provenance) → publish the **destination** repository → register it in the catalog (its first push bootstraps the namespace and pipeline through the platform dispatcher). The legacy code itself is **not** copied anywhere: the workspace clones it read-only at start, side by side with the destination — `/projects/legacy` next to `/projects/modernized`.

**What you should see:** a new catalog component for the migration **destination** (the legacy app never appears in the catalog), with links to the destination repository, Dev Spaces, and SonarQube — the same self-service pattern as stage 070, now wrapped around code that already exists.

> **Why this matters:** migration is where self-service pays off most. Nobody hand-wires analysis tooling, workspaces, and pipelines for every one of hundreds of legacy services. The template makes "start migrating this repo" a ten-second operation with every tool pre-approved by the platform team.

---



## Step 3: Analyze the legacy code with MTA

Before any agent writes a line, the supported product establishes the facts.

1. Open the workspace from the component page's **Dev Spaces** link. Both projects clone automatically — `legacy/` (the application you're migrating, read-only) next to `modernized/` (your destination repository) — and the MTA extension pack installs on first start (1–2 minutes).
2. Click the **MTA icon** in the left Activity Bar (the Konveyor logo), then **Open Analysis Panel**. Give the panel a moment on first open: the Java language server initializes in the background (the workspace pre-configures Standard mode so the analysis provider registers without opening a `.java` file first).
3. Click **Start** (top right of the Analysis View). **Server Status** flips from `Stopped` to `Running` — this boots the analyzer engine inside the workspace. Leave **Agent Mode** off; the platform runs MTA analysis-only.
4. Click **Manage Profiles**. The legacy repository ships its own analysis profiles in `.konveyor/profiles/` — select `quarkus-profile` (Quarkus migration targets; the `audit-logging` profile adds custom organization rules).
5. Back in the Analysis View, click **Run Analysis**. The first run downloads rulesets and scans the whole legacy tree — several minutes for a monolith; later runs are much faster (everything caches in the workspace).
6. Review the findings: the issue tree in the MTA panel, plus inline diagnostics directly in `legacy/` source files — every finding anchored to a rule, file, and line, with mandatory issues and effort estimates. Each run is also saved as machine-readable JSON at `legacy/.vscode/mta-core/analysis_<timestamp>.json` — this file is what the agent consumes in the spec step.
7. Keep the findings open. From this point on, the analysis is the **checklist the agentic result must satisfy** — the migration is done when the findings are resolved, not when the agent says so.

> **Expected panel state:** two informational cards are normal — *"GenAI
> functionality is disabled"* and *"Hub Configuration — No features
> enabled"*. They gate the Developer Lightspeed surface (the hub's
> Solution Server for AI remediation suggestions, and centralized Profile
> Sync), which this platform intentionally leaves off: the agent harness
> in `modernized/` is this exercise's remediation engine, and analysis
> profiles are versioned in the legacy repository (`.konveyor/profiles/`)
> instead of synced from the hub. Analysis itself needs neither.

**What you should see:** the analysis panel enumerating concrete migration issues in the legacy code, and squiggles in the legacy sources where each issue lives.

> **Console alternative:** the same analysis runs server-side in the MTA
> console (application launcher → MTA — it auto-redirects through
> **platform SSO**, the same OpenShift login as Developer Hub, with your
> MTA role resolved from the platform realm). Add the legacy repository
> to the Application Inventory, run the analysis, and open the report
> under the application's Reports tab. The in-workspace path above is the
> demo default: the findings land exactly where the agent will work.

---



## Step 4: The concept — an AI Agent Harness

Stage 070 introduced two kinds of agent context: the memory bank and specs. This stage adds the third idea, from Birgitta Böckeler's [Harness Engineering for Coding Agents](https://martinfowler.com/articles/harness-engineering.html): **Agent = Model + Harness**. The model is fixed; the harness is everything the platform engineers around it, and it comes in two kinds:

- **Guides (feedforward):** steer the agent *before* it acts — standards, rules, specs, architectural constraints.
- **Sensors (feedback):** catch problems *after* it acts and feed them back so the agent can self-correct — builds, tests, linters, analyzers, review agents.

Each kind exists in two execution forms: **computational** (deterministic and fast: compilers, tests, recipes, static analysis) and **inferential** (semantic, model-driven: an agent reviewing another agent's diff). Fast, cheap sensors run early and often inside the loop; expensive ones guard the exit.

Everything this platform already operates maps onto that picture:


| Harness part                           | Kind                             | Platform asset                                                                    |
| -------------------------------------- | -------------------------------- | --------------------------------------------------------------------------------- |
| Migration standards, AGENTS.md, skills | Guide                            | Stage 070 memory-bank assets, extended with migration skills                      |
| Migration spec, plan, tasks            | Guide                            | spec-kit artifacts generated in Step 5                                            |
| MTA analysis findings                  | Sensor (computational)           | The Step 3 report, re-run to verify findings are resolved                         |
| OpenRewrite recipes                    | Guide + Sensor                   | Deterministic transforms for the mechanical share of the migration                |
| Build + tests                          | Sensor (computational)           | Maven build and the test suite, run by Hermes after every task                    |
| Self-review / evaluation pass          | Sensor (inferential)             | The orchestrator's milestone eval against the spec in Step 6                      |
| SonarQube + factory pipeline           | Sensor (computational, **exit**) | The regulated merge authority — same gate as stages 060/070                       |
| Human steering                         | Judgment                         | Improving guides and sensors when the loop exposes gaps — not per-change approval |


Two things follow. First, the loop inverts: in stage 060 *you* read the SonarQube report and prompted the fix; here the harness feeds sensor output back to the agent, which iterates until the checks pass — quality shifts from inspection to regulation. Second, humans move up a level: nothing merges on agent authority because the **factory** won't let it, so instead of reviewing every intermediate diff, you observe where the loop struggled and **improve the harness** — Böckeler calls this the steering loop, and it is the stage 070 "skills retro" practice graduated into a system.

### The migration process — five stages, two feedback loops

The harness runs a staged process (the "M-process"). Every stage has explicit input and output artifacts committed to the repository — `git log --oneline` reads as the process narrative — and a deterministic gate guards each hand-off. Modernization is incremental by design: M2 cuts the work into dependency-ordered **stories**, and M3→M5 cycle per story. No big bang.

```text
      ┌─────────────── outer loop: retro improves skills, rules, briefs ─────────────┐
      │                          ┌──── findings delta → roadmap revision ────────────┤
      ▼                          ▼                                                   │
┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐    │
│ (1)  M1   │    │ (2)  M2   │    │ (3)  M3   │    │ (4)  M4   │    │ (5)  M5   │    │
│  ANALYZE  │───▶│ SEQUENCE  │───▶│  SPECIFY  │───▶│ IMPLEMENT │───▶│ EVALUATE  │────┘
│           │    │           │    │ per story │    │ per story │    │ per story │
└───────────┘    └───────────┘    └─────┬─────┘    └─────┬─────┘    └─────┬─────┘
 [analysis         [roadmap        ▲    │ lint      ▲    │ sensors        │
  pipeline]         lint]          └────┘ red →     └────┘ red → fix      │
                                   revision loop    session (inner loop)  │
                                                                          │
              next story from the roadmap  ◀──────────────────────────────┘
```

| # | Stage | Enabling technology | Tasks it performs | Output artifacts (committed) |
|---|---|---|---|---|
| 1 | **M1 ANALYZE** | MTA/kantra (Windup rules incl. platform contract rules), OpenRewrite recipes, dependency-graph script, one Hermes analyst session | Rule-based analysis of the legacy app (migration path + jakarta + cloud-readiness + JDK targets); classify every finding against the MAPPINGS rule-joins; compute the conversion order and god nodes; pre-execute mechanical recipes (jakarta) into a staging tree; write the architecture profile — components, integration surfaces, behavioral contract sources, domain seams | `mta-findings.json`, `findings-inventory.md`, `dependency-order.md`, `recipe-log.md` + staged sources, `architecture-profile.md` |
| 2 | **M2 SEQUENCE** | Hermes planner session guided by the SEQUENCING skill; `roadmap-lint` gate | Cut the modernization into dependency-ordered stories (models before services before surfaces; domain seams for monoliths); mark deploy milestones; write one self-contained brief per story with real legacy code excerpts and the contracts that story owns | `roadmap.md`, `briefs/S*.md` |
| 3 | **M3 SPECIFY** | spec-kit workflow (Hermes session per story); story-scoped `plan-lint` gate | Turn one brief into spec / plan / tasks: behavioral contract from legacy tests, decided target shapes from MAPPINGS, rewrite-before-infer ordering, characterization tests early, recipe-executed rules excluded | `specs/S<NN>/{spec,plan,tasks}.md` |
| 4 | **M4 IMPLEMENT** | Supervisor task loop; Hermes orchestrator + OpenCode worker (packets); skills + AGENTS.md rules; task/milestone sensors (isolated Maven repo, in-loop SonarQube) | Execute the story's tasks one commit each; harvest from the recipe-staged sources; port/pin contract tests; every commit sensor-verified; red commits get autonomous fix sessions; mechanical commit closure for green-but-uncommitted work | code + tests, one `T-NNN:` commit per task, `run-log.md` rows |
| 5 | **M5 EVALUATE** | Pre-push preflight (full quality gate + boot check); Tekton factory pipeline + SonarQube gate; kantra after-analysis (script step); Hermes retro session | Gate the story locally, ship through the factory; deploy stories must serve their acceptance endpoints live; measure the findings delta (before vs destination); write retro proposals that improve skills, rules and the remaining briefs before the next story starts | pipeline + gate results, deployed increment, `findings-delta`, `retro-proposals.md` |

The two feedback loops do different jobs: the **inner loop** (sensors → fix sessions, lint → revision sessions) corrects the *work* within minutes; the **outer loop** (per-story retro → skills/rules/briefs, findings delta → roadmap) corrects the *process*, so each story starts smarter than the last. Steps 5–7 below walk the inner mechanics of one story; the platform runs this whole picture per story, in roadmap order.

### The harness implementation: Hermes Agent

Concepts need a runner. This stage uses **[Hermes Agent](https://hermes-agent.nousresearch.com/docs)** (Nous Research) as the harness implementation that owns the autonomous loop: a CLI-first agent that consumes the project's guides, runs the sensors as tools (build, tests, OpenRewrite, analysis), and iterates until the checks pass or the budget expires. The properties that matter here:

- **CLI-native, headless-capable**: `hermes chat -q "..."` runs a one-shot turn (including in non-TTY workers), and `hermes -w -z "..."` runs one in an isolated git worktree — the loop is drivable from a terminal and from automation alike.
- **Governed models, first-class**: `~/.hermes/config.yaml` points at any OpenAI-compatible endpoint — our MaaS gateway with a platform-issued key, so every loop iteration is metered like everything else on this platform.
- **Continuity with what you already built**: Hermes speaks the AGENTS.md and [agentskills.io](https://agentskills.io/home) mental model this project has used since stage 070 — the guides in this repository are its guides — and its built-in learning loop (skills created and improved from experience) is the "skills retro" practice running inside the agent itself.
- **A real task system for real migrations**: the Kanban board (`~/.hermes/kanban.db`) is a durable, multi-agent task graph — a dispatcher decomposes work into child tasks, routes them to specialist worker profiles, and each worker is a full OS process reporting back to the board. That is the ~100-task shape a whole-application migration actually has.

**Why not OpenClaw?** [OpenClaw](https://docs.openclaw.ai/) is the other agent harness you will hear named, and it is a strong product — but its center of gravity is different: a personal agent-ops **platform** built around a gateway daemon, chat channels, and session management, which *can* wrap coding CLIs (Codex, Copilot, even OpenCode via ACP) as embedded runtimes. Two mismatches for this stage:


| Need for stage 080                            | Hermes                                                                                      | OpenClaw                                                                                                                                        |
| --------------------------------------------- | ------------------------------------------------------------------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| Drive the loop from a CLI, not a UI           | First-class: `hermes chat -q` headless/one-shot                                             | Possible, but the CLI is a side door into a gateway/session model                                                                               |
| Point at governed MaaS (`/v1` + platform key) | First-class OpenAI-compatible endpoint in `config.yaml`                                     | Supported, with more allowlist/runtime/plugin ceremony                                                                                          |
| Continuity with 070 (AGENTS.md, skills)       | Native AGENTS.md + agentskills.io mental model                                              | Has skills/bootstrap, but less aligned with the `.opencode/skills` + spec-kit path                                                              |
| Self-correcting task loop (sensors → retry)   | Kanban/DAG workers and one-shot runs are the product center                                 | The agent loop exists, but product gravity is channels, gateway, sessions                                                                       |
| Fit the *teaching* word "harness"             | Matches Böckeler: everything around the model (tools, skills, memory, approvals, execution) | Uses "harness" for a *different* thing — its low-level runtime executors (`codex`, `copilot` plugins) — which collides with the stage narrative |
| Dev Spaces migration exercise                 | Heavier than OpenCode alone, but CLI-shaped                                                 | Heavier still: gateway daemon and channel/session semantics are the main design                                                                 |


**Verdict: Hermes fits stage 080's CLI-driven autonomous migration loop more natively than OpenClaw.** The demo should look like *watching the migration converge in the terminal* — Hermes' center of gravity is exactly that loop, with messaging surfaces optional; OpenClaw would have you operating a gateway platform to tell the same story. Division of labor: **Hermes is the orchestrator** — it plans (Step 5) and drives the loop (Step 6) but never edits application source — and **OpenCode is the coding worker inside the harness**, dispatched one bounded task at a time via `opencode run`. The whole contract is versioned in the repository as the **migration-harness runbook** (`.hermes/skills/migration-harness/`), which the workspace links into Hermes' skill path automatically; the interactive `/speckit.`* commands from stage 070 remain available when you want to author specs yourself.

---



## Step 5: The orchestrator plans

The MTA findings say what must change; the spec says what the migrated service must be. In this stage the **orchestrator writes the contract** — you review it, you don't author it.

1. In a workspace terminal, start the planning run:
  ```bash
   cd /projects/modernized
   hermes chat -q "Use the migration-harness skill. Execute Phase A (normalize ground truth) and Phase B (plan)."
  ```
2. Watch what the runbook makes Hermes do: normalize the newest MTA analysis into `migration/mta-findings.json` (the versioned ground-truth copy), script-extract the violation counts rather than reading the file into context, then write `specs/001-.../spec.md` (observed legacy behavior and API contract, with legacy file paths as evidence), `plan.md` (Quarkus mapping, every finding traced to a task), and `tasks.md` (ordered checklist — every task tagged `Class: rewrite` or `Class: infer`, rewrite first, each citing the finding rule ids it resolves).
3. Skim the artifacts — a **soft, non-blocking checkpoint**, not an approval gate. Mechanical findings (import rewrites, dependency swaps, namespace changes) should be tagged `rewrite` and delegated to **OpenRewrite** recipes; on this codebase a single rule (`javax-to-jakarta-import-00001`) accounts for well over half of all incidents, and every one of them is deterministic — that is inference budget the harness refuses to spend on a model. The interactive `/speckit.`* path from stage 070 remains available if you prefer to author the spec yourself.

**Under the hood — what Hermes actually does.** A `hermes chat -q` run is a
*headless one-shot session*: the prompt names the **migration-harness skill**,
Hermes loads the runbook from `.hermes/skills/migration-harness/` (versioned in
this very repository, linked into its skill path at workspace start), and from
that point the runbook is its standing operating procedure. Inside the session
Hermes works with a small set of tools — a **terminal** (every shell command
you could type), **file read/write**, and a **todo planner** it uses to break
the phase into steps you can watch scroll by. The runbook imposes *context
discipline*: the MTA findings file is hundreds of kilobytes, so Hermes never
reads it whole — it extracts violation counts and incident lists with small
`python3` scripts run in the terminal, keeping its context window for
judgment instead of raw JSON. Phase A is deliberately mechanical: find the
newest `legacy/.vscode/mta-core/analysis_*.json`, copy it to
`migration/mta-findings.json`, script-summarize it, commit. Phase B is where
the model earns its seat: it explores the legacy tree with `find`/`grep`,
reads the load-bearing sources, classifies every finding as deterministic
(`rewrite`) or judgment (`infer`), and writes the three artifacts — then ends
with **one commit**, because in this harness a commit is a claim: *this phase
completed and its outputs are traceable*.

**What you should see:** spec, plan, and tasks in the repository, written by the orchestrator, traceable line-by-line to MTA findings and observed behavior.

---



## Step 6: Watch the harness migrate

You start the run and observe; Hermes drives.

1. Start the execution run:
  ```bash
   hermes chat -q "Use the migration-harness skill. Execute Phase C for the tasks in specs/001-.../tasks.md."
  ```
2. What the runbook enforces, per task:
  - **rewrite tasks**: Hermes copies the legacy source to an ephemeral scratch directory (`/tmp/rewrite-staging` — the read-only rule on `legacy/` holds), runs the OpenRewrite recipes there, and dispatches an explicit **harvest task** to OpenCode with source and destination paths;
  - **infer tasks**: Hermes hands OpenCode one bounded task packet at a time via `opencode run` (worker model, auto-approved permissions, JSON output), then verifies the claimed changes against `git status` — never trusting the worker's summary alone;
  - **sensors after every task**: `mvn -q test` must pass; on milestones the orchestrator runs a short evaluation of the diff against the spec;
  - **failures become correction packets**: the original packet plus the exact sensor output, re-delegated once (two attempts per task); a task that exhausts its budget lands in `migration/debt.md` with the evidence, and the loop moves on.
3. Your job is observation. `migration/run-log.md` accumulates one line per task; where retries cluster is exactly where the harness — the spec, a skill, a sensor — needs improving. That observation feeds Step 8's retro.

**Under the hood — one task, end to end.** Each task runs in a *fresh*
orchestrator session (small context, no drift from earlier tasks). Hermes
reads the task's entry in `tasks.md`, inspects repository state (`git status`,
`git log`), and then writes a **task packet** for the worker — the runbook
fixes its schema: Task ID, Class, Goal, the finding rule ids it resolves,
Constraints, Inputs, Acceptance, Out-of-scope. Good packets are remarkably
concrete: exact source → destination file mappings, per-file transformation
rules ("drop `@Remote`", "replace the JNDI lookup with `@Inject
ShippingService`"), the unit tests that must ship with the code. For a
`rewrite` task Hermes never asks a model to do a compiler's job — it copies
the legacy tree to `/tmp/rewrite-staging` (the read-only rule on `legacy/`
holds), runs the OpenRewrite Maven plugin with the recipe named in the plan,
and turns the result into an explicit harvest packet. For an `infer` task it
dispatches `opencode run "<packet>" -m <worker-model> --auto --format json`
**synchronously** and waits: the worker's event stream (often hundreds of KB
of JSON) is redirected to a file, and Hermes reads only a script-generated
summary — tool-call count and final message — never the raw stream. Then
comes the part that makes this a harness rather than a hope: **independent
verification**. Hermes checks the claimed files against `git status`, runs
`mvn -q clean test` (`clean` is non-negotiable — a stale `target/` can hide
missing dependencies the factory will catch), escalates to `mvn -q clean
verify` whenever `pom.xml` or runtime config changed, and reads coverage
numbers out of the JaCoCo report rather than trusting any claim. A sensor
failure becomes a **correction packet** — the original packet plus the exact
failure output and "fix only this failure; change nothing else" — and the
task gets one more attempt. Budget exhausted means an honest entry in
`migration/debt.md` with the evidence, never a commit with red sensors. Each
completed task ends in one commit prefixed with its task id: the git history
*is* the execution trace.

**What you should see:** the loop converging task by task in the terminal — recipes for the mechanical share, bounded worker runs for the judgment share, sensors between every step — with a visible record of what the sensors caught that never reached you.

> **Honesty beat:** autonomy is token-hungry. Every iteration of the loop is metered through the developer's MaaS key; Step 8 shows the bill. That cost profile is why token limits exist and why deterministic transforms carry the mechanical share of the work.

> **Why these models:** the two harness roles have different failure
> modes, so the platform seats them separately and selected each seat in
> a full-migration A/B. The **orchestrator** (MiniMax M2, 196K context)
> is selected for what the loop demands of a supervisor: lean sessions,
> reliable long-horizon tool calling, and composure on large work
> orders. The **worker** (`qwen3-6-27b`, served on the cluster GPU
> behind the governed MaaS gateway) is the strongest evaluated coding
> seat (SWE-bench 77.2, AA Coding 53.7) — every code edit runs on the
> governed local model, metered on the developer key. The runbook also
> documents an all-local routing option (the 27B in both seats behind
> the supervisor). Selection history and serving details live in
> `docs/OPERATIONS.md`.

---



## Step 7: The factory ships it

Nothing merges on agent authority — and no human approval substitutes for the factory either.

1. The runbook's exit runs the re-analysis sensor first: kantra (the containerless Konveyor CLI, fetched on demand by `kantra-ensure`) re-analyzes the **migrated** code and writes `migration/mta-findings-after.json`. Done is defined as the Step 3 baseline resolved or explicitly waived in the spec — never "the agent says done."
2. Hermes commits and pushes. Its report ends there by contract: "pushed; the factory pipeline decides." (Pushing from the workspace requires your Git credentials — configure your GitHub token in the Dev Spaces user preferences if you haven't.)
3. Watch the project's pipeline run clone → build → SonarQube quality gate → image build/push — the same regulated exit every stage uses. **Red CI means autonomy failed the regulated exit**, not "wait for a human thumbs-up"; green CI is the platform's proof, not the agent's claim.
4. Spot-check the diff if you like — it is optional and non-blocking. If something slipped through, the response is not to blame the model but to tighten a guide or add a sensor and re-run: that is the steering loop.

**Under the hood — how "done" is proven.** The exit phase is symmetric with
the entry: the same analyzer that defined the work now judges it. Hermes runs
kantra against the **migrated** tree, saves
`migration/mta-findings-after.json`, and computes the baseline-vs-after delta
with a script — per rule, per incident — appending the table to
`migration/run-log.md`. Findings that remain must be *explainable* (an
advisory rule, a false positive with the reasoning recorded), not ignored. A
final `mvn -q clean verify` proves the tree builds the way the factory will
build it, and one `Phase D` commit seals the evidence. The push is where
authority transfers: the project pipeline runs build → tests → **SonarQube
quality gate** (new-code coverage ≥ 80%, zero new violations, ≤ 3% duplicated
new lines) → image build → deploy with a rollout gate. When the gate rejects
a push, that is the factory doing its job: the violation list becomes one
more correction packet — mechanical multi-file fixes are worker-class work —
and the corrected commit ships through the same gate. Nothing about the
agent's own confidence shortcuts this: green CI is the platform's proof, and
the deployed route is the demo's.

**What you should see:** an evidence-backed migration shipping through the factory: findings delta recorded, tests green, quality gate passed — with the pipeline, not a person, as the merge authority.

---



## Step 8: The bill and the retro

1. Open the Stage 040 MaaS usage dashboard: the token consumption of the full autonomous run — orchestrator and worker on the same developer key — next to the interactive stages' usage. Autonomy is visible on the same meter as everything else.
2. Run the harness retro: read `migration/run-log.md` and `migration/debt.md`. Every retry cluster is a candidate improvement — a sharper skill, a stricter spec template, a new sensor. Improvements land as versioned changes to the repository's guides, exactly like the stage 070 skills retro.

> **Token governance beat (MTA 8.2):** interactive sessions run on
> five-minute access tokens; automation runs on **API keys** you create in
> the MTA console (your username menu → Tokens → Create API Key) — scoped
> to your role, usable by CI jobs and automation, and
> revocable instantly from the same page. Create one, show a scripted hub
> API call with it, then revoke it: governed automation credentials with a
> visible lifecycle, the same story the platform tells for model keys.

**What you should see:** the complete, attributed cost of the autonomous run on the platform dashboard, and a written record — run log and debt — of exactly where the harness needs to get better.

---



## Wrap-up



### What you proved

- **Analysis grounds autonomy:** MTA's findings, not the agent's self-assessment, defined done.
- **The harness regulates quality:** guides steered generation, sensors caught and fed back failures, and the agent iterated to green before a human ever looked.
- **Determinism where possible, inference where needed:** OpenRewrite carried the mechanical transforms; the model spent its budget on judgment calls.
- **The factory, not a person, was the merge authority:** the agent could push, but only the pipeline and its quality gate could turn that push into a trusted artifact — and humans moved up a level, from reviewing diffs to improving the harness.
- **Governance held at full autonomy:** same identity, token limits, and telemetry as every previous stage — just more visible, because agents consume more.



## Red Hat Products Used

- **[Migration Toolkit for Applications](https://developers.redhat.com/products/mta)** provides modernization analysis, inventory, rules, and developer workflow integration.
- **[Red Hat Developer Hub](https://developers.redhat.com/rhdh)** provides the developer portal and the migration golden-path template.
- **[Red Hat OpenShift Dev Spaces](https://www.redhat.com/en/technologies/cloud-computing/openshift/dev-spaces)** hosts the migration workspace.
- **[Red Hat OpenShift AI](https://www.redhat.com/en/technologies/cloud-computing/openshift/openshift-ai)** provides the governed MaaS endpoints the analysis tooling and the agent consume.
- **[Red Hat OpenShift Pipelines](https://docs.redhat.com/en/documentation/red_hat_openshift_pipelines/)** runs the exit pipeline with the SonarQube quality gate.
- **[Red Hat build of Keycloak](https://access.redhat.com/products/red-hat-build-of-keycloak)** provides the platform identity broker (stage 050 `identity` component); MTA 8.2's built-in Hub OIDC provider federates to it, so MTA, RHDH, and the cluster share one OpenShift-backed sign-in.
- **[Red Hat OpenShift](https://www.redhat.com/en/technologies/cloud-computing/openshift)** provides runtime, identity integration, routes, storage, and operations.



## Open Source Projects To Know

- [Konveyor](https://www.konveyor.io/) is the upstream modernization community behind MTA.
- [Kantra](https://github.com/konveyor/kantra) provides CLI-based application analysis.
- [OpenRewrite](https://github.com/openrewrite/rewrite) provides deterministic, recipe-driven code transformation.
- [spec-kit](https://github.com/github/spec-kit) is the spec-driven development toolkit carried over from stage 070.
- [Hermes Agent](https://hermes-agent.nousresearch.com/docs) is the CLI-first agent harness that owns the autonomous migration loop.
- [OpenCode](https://opencode.ai/) is the coding worker inside the harness — dispatched by Hermes one bounded task at a time — and remains available interactively, carried over from stage 070.
- [Coolstore](https://github.com/konveyor-ecosystem/coolstore) is the legacy sample application used as the migration target.



## References


| Resource                                      | Link                                                                                                                                                                 |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Harness Engineering for Coding Agents         | [https://martinfowler.com/articles/harness-engineering.html](https://martinfowler.com/articles/harness-engineering.html)                                             |
| Hermes Agent documentation                    | [https://hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs)                                                                             |
| OpenClaw documentation (compared alternative) | [https://docs.openclaw.ai/](https://docs.openclaw.ai/)                                                                                                               |
| MTA 8.2 documentation                         | [https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.2/](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.2/) |
| OpenRewrite documentation                     | [https://docs.openrewrite.org/](https://docs.openrewrite.org/)                                                                                                       |
| spec-kit — spec-driven.md                     | [https://github.com/github/spec-kit/blob/main/spec-driven.md](https://github.com/github/spec-kit/blob/main/spec-driven.md)                                           |
| MaaS code assistant quickstart                | [https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)                     |


