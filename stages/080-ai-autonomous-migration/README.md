# Stage 080: AI-Autonomous Migration with an Agent Harness

The previous stages built the AI maturity ladder one rung at a time, and both stages end with a human driving every cycle. This stage asks the next question: what has to be true for an agent to carry a whole-application migration largely on its own?

Legacy applications are not just expensive to maintain. They are an expanding attack surface. AI-powered exploit tools lower the cost of finding and weaponizing vulnerabilities in outdated frameworks, and regulations are catching up: the EU Cyber Resilience Act makes vendors accountable for the security posture of every product they ship, including the libraries and runtimes underneath it. The migration backlog is no longer a cost problem alone; it is a compliance and security deadline that most teams cannot meet with manual effort.

This demo stage answers with two complementary paths on the same governed platform: assisted modernization through Migration Toolkit for Applications turning a legacy codebase into an inventory of concrete, prioritized migration issues, and autonomous migration where an agent harness takes a legacy service end-to-end to Quarkus with analysis-grounded planning, spec generation, self-evaluation loops, and a trusted software supply chain pipeline that enforces quality and security before anything merges.

Application domain experts remain essential. Agents handle the volume (hundreds of files, thousands of import rewrites, test scaffolding), but domain experts define what correct migration means: which business behaviors must be preserved, which integration contracts matter, where the analysis findings are real issues versus acceptable deviations. The harness encodes their judgment as guides and sensors; they improve those assets after each run rather than reviewing every line the agent writes.

## What You'll Do

**Demo spine (Acts A–E):** provision a governed migration workspace → establish MTA ground truth → plan with Spec Kit (never `/speckit.implement`) → **watch Hermes Kanban before dispatch** → audit with `list` / `show` / `runs` + verdict JSON. That is what you observe in the room.

The longer M-process / harness-concept material is an **architecture appendix** — useful for teaching, not the live walkthrough. Full M5 factory ship is **not** claimed DEMONSTRATED for the Owner/Pet slice yet.

---

## Step 1: Sign in to Developer Hub

1. Open the Developer Hub URL and sign in as `ai-developer` (OpenShift OIDC).

**What you should see:** the RHDH home screen with the catalog search bar.

---

## Step 2: Create your migration project from the template

Stage 070's template scaffolded a greenfield service from nothing. The migration template inverts the input: you bring an existing codebase.

1. Open **Self-service** and choose the **Application migration** template.
2. Provide the input the template asks for:
  - **Project name**: becomes the per-run destination repository, namespace, and workspace name (e.g. `coolstore-cart-v6`, `petclinic-rest-v2`).
  - **Legacy repository URL**: HTTPS Git URL clonable without credentials. Two demo inputs are maintained: the Coolstore **cart** service ([coolstore-cart-legacy](https://github.com/adnan-drina/coolstore-cart-legacy.git)) — small and stateless, good for a short workshop run — and the **Spring PetClinic REST** service ([spring-petclinic-rest-legacy](https://github.com/adnan-drina/spring-petclinic-rest-legacy), pinned at v2.6.2), the validated showcase: a database-backed REST API with OpenAPI-generated DTOs, three alternative persistence layers, and profile-driven configuration — the shapes a real migration has to decide about. The monolith round used [mca-coolstore](https://github.com/rhpds/mca-coolstore.git).
  - **Needs database**: leave off for cart (stateless); enable for PetClinic and any legacy app that persists to a database.
3. Create, and watch the template run: fetch the migration scaffold → publish the **destination** repository → register it in the catalog (its first push bootstraps the namespace and pipeline through the platform dispatcher). The legacy code itself is **not** copied anywhere: the workspace clones it read-only at start, side by side with the destination, `/projects/legacy` next to `/projects/modernized`. The migration contract in `migration.yaml` — packages, dest↔legacy leaf maps (`intra_package_maps`), acceptance path/shape, preserve/forbidden, `targetContract` — is **stamped by the app-migration template skeleton** from the legacy URL for the two demo freeze-forks (`coolstore-cart-legacy`, `spring-petclinic-rest-legacy`). The golden scaffold stays specimen-free; unknown legacy URLs get `contract.status: undecided` rather than cart defaults. The dependency deriver applies `path_rewrites` and `intra_package_maps`, so a plan may emit a dest leaf that differs from legacy without breaking gate 3. Review the stamped contract after create; override a decided flag only when you intend to.

**What you should see:** a new catalog component for the migration **destination** (the legacy app never appears in the catalog), with links to the destination repository, Dev Spaces, and SonarQube, the same self-service pattern as stage 070, now wrapped around code that already exists.

> **Why this matters:** migration is where self-service pays off most. Nobody hand-wires analysis tooling, workspaces, and pipelines for every one of hundreds of legacy services. The template makes "start migrating this repo" a ten-second operation with every tool pre-approved by the platform team.

---

## Step 3: Analyze the legacy code with MTA

Before any agent writes a line, the supported product establishes the facts.

1. Open the workspace from the component page's **Dev Spaces** link. Both projects clone automatically: `legacy/` (the application you're migrating, read-only) next to `modernized/` (your destination repository). The MTA extension pack installs on first start (1–2 minutes).
2. Click the **MTA icon** in the left Activity Bar (the Konveyor logo), then **Open Analysis Panel**. Give the panel a moment on first open: the Java language server initializes in the background (the workspace pre-configures Standard mode so the analysis provider registers without opening a `.java` file first).
3. Click **Start** (top right of the Analysis View). **Server Status** flips from `Stopped` to `Running`, which boots the analyzer engine inside the workspace. Leave **Agent Mode** off; the platform runs MTA analysis-only.
4. Click **Manage Profiles**. The legacy repository ships its own analysis profiles in `.konveyor/profiles/`; select `quarkus-profile` (Quarkus migration targets).
5. Back in the Analysis View, click **Run Analysis**. The first run downloads rulesets and scans the whole legacy tree (several minutes for a monolith; later runs are much faster as everything caches in the workspace).
6. Review the findings: the issue tree in the MTA panel, plus inline diagnostics directly in `legacy/` source files. Every finding is anchored to a rule, file, and line, with mandatory issues and effort estimates. Each run is also saved as machine-readable JSON at `legacy/.vscode/mta-core/analysis_<timestamp>.json` (the IDE path; the harness uses `migration/mta-findings.json` instead).
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

> **Harness analysis path:** M1 uses the `mta-analysis` skill / `mta-cli`
> (kantra) and writes `migration/mta-findings.json` (plus session artifacts
> under `migration/`). The IDE panel above is for *human* exploration; the
> harness reads `migration/mta-findings.json` as ground truth. Both paths
> use the same rulesets and targets from `migration.yaml`.

---

## Demo walkthrough (Acts A–E)

**Authority:** Research journey `source-analysis/demo-ux/20260808-e2e-demo-user-journey.md`;
Architect demo-surface decide; Deputy docs-only Stage-1 exception
`E-20260808T153444Z`. **Specimen for the prove path:** PetClinic Owner/Pet
(`petclinic-rest-v7-refac`) — pick one and stick to it.

| Act | Job | What you look at |
|-----|-----|------------------|
| **A** Arrive | Self-service workspace | RHDH → Dev Spaces; `/projects/legacy` (RO) beside `/projects/modernized` |
| **B** Ground truth | MTA checklist | Prefer `migration/mta-findings.json` (harness authority); IDE panel optional *human* exploration |
| **C** Plan without implementing | Spec Kit → Kanban | `/speckit.specify` → plan → tasks → `kanban_create` — **never** `/speckit.implement` |
| **D** Watch the migration | Hermes Kanban | Pane A: `hermes kanban watch` **before** dispatch · Pane B: `dispatch` |
| **E** Audit close | Snapshots + verdicts | `list` / `show` / `runs <task_id>` + `migration/verdicts/*.json` — not more watching |

**Forbidden:** `outer-loop.sh`, `supervisor.sh`, `tail -f outer-loop.log`, starting
`watch` only after the run, inventing a sixth log surface.

### Act C — Plan (brief → Spec Kit → Kanban)

```bash
cd /projects/modernized
hermes chat -q "Read migration/briefs/<brief>.md. Run /speckit.specify then /speckit.plan then /speckit.tasks. Stop. Never /speckit.implement. Create Kanban cards from tasks.md with workspace dir:/projects/modernized."
```

**What you should see:** `specs/.../{spec,plan,tasks}.md` and ready/todo cards on
`hermes kanban list`.

### Act D — Watch (Track B replacement)

**Critical ordering** (Architect binding — empty watch after the run is not a defect):

```bash
cd /projects/modernized
export HERMES_HOME=/projects/modernized/.hermes/home
# terminal A — start BEFORE any dispatch
hermes kanban watch --interval 1
# or: bash .hermes/home/scripts/kanban-track.sh watch
# terminal B — seed M1 (derive + MTA + inventory) as a Hermes Kanban task, then tick
bash .hermes/skills/phase-dispatch/scripts/dispatch-phase.sh M1
# later phases: dispatch-phase.sh M2 --parent <m1_task_id>
# (dispatch-phase already runs one hermes kanban dispatch tick)
# single-pane alternative: bash .hermes/home/scripts/kanban-track.sh follow
#   (starts daemon --force + watch; still create/dispatch cards separately)
```

Do **not** start M1 with a detached `mta-analyze-legacy.sh` — Hermes must own
M1–M5 orchestration (role, skills, `max_runtime_seconds`, recovery).

**Dashboard is not part of Acts A–E.** Operator-only Hermes dashboard (optional)
lives in `harness-refactoring/docs/DEMO-SURFACE-RUNBOOK.md` — **not** the demo
spine. Do not use Che Ports / Simple Browser for it.

Drill-down:

```bash
hermes kanban show <task_id>
hermes kanban runs <task_id>   # task_id required
hermes kanban log <task_id>
# or: bash .hermes/home/scripts/kanban-track.sh {show|runs|log|tail} <task_id>
```

**Honest exit of this act:** M4 **`PROVISIONAL_ACCEPT`** for Owner/Pet
(`ship=false`, kill-ratio `pending_threshold`) — not “migration finished and shipped.”

### Act E — Audit close

```bash
hermes kanban list
hermes kanban runs <task_id>
# open migration/verdicts/… — ship=false honesty
```

Optional: Stage 040 MaaS usage dashboard for the **metering** beat — not the
progress UI. Skip or label as future: factory push / Sonar green / M5 `ACCEPT`
unless observed in *this* environment.

| Surface | Maturity (live `petclinic-rest-v7-refac`, 2026-08-08) |
|---|---|
| `hermes kanban list` / `show` / `runs` / `log` | **DEMONSTRATED** |
| `hermes kanban watch` / `dispatch` | **DEMONSTRATED** (Owner/Pet) |
| `hermes dashboard` loopback `:9119` | **DEFINED** (operator appendix / runbook only; postStart best-effort) — **not** demo surface; not required for DEFINED→DEMONSTRATED |
| Owner/Pet → M4 `PROVISIONAL_ACCEPT` | **DEMONSTRATED** |
| Owner/Pet → M5 full `ACCEPT` / factory | **Not** DEMONSTRATED |

Evidence: `harness-refactoring/measurements/hermes-native-tracking/VERIFY.md`;
runbook: `harness-refactoring/docs/DEMO-SURFACE-RUNBOOK.md`.

---

## Appendix A: Harness concept and M-process (not the live demo spine)

> **Maturity label:** architecture / teaching material. The live demo follows
> **Acts A–E** above. Do not read this appendix as “what you will watch in this room.”

### The concept, an AI Agent Harness

Stage 070 introduced two kinds of agent context: the memory bank and specs. This stage adds the third idea, from Birgitta Böckeler's [Harness Engineering for Coding Agents](https://martinfowler.com/articles/harness-engineering.html): **Agent = Model + Harness**. The model is fixed; the harness is everything the platform engineers around it, and it comes in two kinds:

- **Guides (feedforward):** steer the agent *before* it acts: standards, rules, specs, architectural constraints.
- **Sensors (feedback):** catch problems *after* it acts and feed them back so the agent can self-correct: builds, tests, linters, analyzers, review agents.

Each kind exists in two execution forms: **computational** (deterministic and fast: compilers, tests, recipes, static analysis) and **inferential** (semantic, model-driven: an agent reviewing another agent's diff). Fast, cheap sensors run early and often inside the loop; expensive ones guard the exit.

Red Hat AI describes this as the **Agent-as-a-Workload** pattern: the agentic loop runs inside a governed workspace (our Dev Spaces pod), reaches models only through the MaaS gateway (identity, quotas, telemetry), and calls tools through governed endpoints. The workspace isolation, the MaaS gateway, and the pipeline quality gate form three layers of enforcement that the model cannot influence, even if its behavior is manipulated. This is the same defense-in-depth architecture described in [Architect an open blueprint for cloud-native AI agents](https://developers.redhat.com/articles/2026/07/20/architect-open-blueprint-cloud-native-ai-agents), applied here to a migration workload.

Böckeler's follow-up, [Maintainability sensors for coding agents](https://martinfowler.com/articles/sensors-for-coding-agents.html), confirms a practice this harness already leans on: a red sensor should carry **self-correction guidance**, not only the raw failure. Domain gates and validation skills print actionable refuse reasons (what failed, what evidence is missing) so the next Kanban attempt spends tokens on the root cause instead of re-deriving policy.

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

### The migration process: five stages, two feedback loops (appendix)

The harness runs a staged process (the "M-process"). **Maturity:** conceptual /
roadmap — Owner/Pet prove path stops at M4 `PROVISIONAL_ACCEPT`; full M5 factory
ship is not the demo spine. Every stage has explicit input and output artifacts
committed to the repository (`git log --oneline` reads as the process narrative)
and a deterministic gate guards each hand-off. Modernization is incremental by
design: M2 cuts the work into dependency-ordered **stories**, and M3→M5 cycle
per story. No big bang.

> **R-HX.2 (2026-08-11):** live phase glossary is **only**
> `scaffold …/.hermes/phase-dispatch.yaml` —
> **M1 ANALYZE → M2 PLAN → M3 IMPLEMENT → M4 VERIFY → M5 CLOSE**.
> Older SEQUENCE / SPECIFY / EVALUATE labels below are retired.

```text
      ┌──── outer loop: Retro → remaining stories ──────────────────────────────┐
      │                    steering (human): skills / sensors / runbook ────────┤
      ▼                                                                         │
┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐    ┌───────────┐
│ (1)  M1   │    │ (2)  M2   │    │ (3)  M3   │    │ (4)  M4   │    │ (5)  M5   │
│  ANALYZE  │───▶│   PLAN    │───▶│ IMPLEMENT │───▶│  VERIFY   │───▶│   CLOSE   │──┘
│           │    │           │    │ per story │    │ provisional│   │  ACCEPT   │
└───────────┘    └───────────┘    └─────┬─────┘    └─────┬─────┘    └─────┬─────┘
 [MTA/kantra +     [partition +     ▲    │ Kanban     ▲    │ gates         │
  inventory]        Spec Kit +       │    │ implementer│    │ (PROVISIONAL  │
                    typed bodies]    └───┘ soft-K     └───┘ ACCEPT)        │
                                                                          │
              next story / unblock  ◀─────────────────────────────────────┘
              (failed card → blocked; resume via phase-dispatch)
```

| # | Stage | Enabling technology | Tasks it performs | Output artifacts |
|---|---|---|---|---|
| 1 | **M1 ANALYZE** | Hermes Kanban + `mta-analysis` / `inventory-entry-points` / `derive-legacy-boot3` | Derive findings-handoff + inventory; Operator ACK | `migration/findings-handoff.json`, inventory, ACK |
| 2 | **M2 PLAN** | Hermes planner + Spec Kit (`speckit-specify` → `plan` → `tasks`); mint is the M3 wave-holder card | Read inventory before specify; enumerate every `http_path`; Resource tasks emit `@Path("...")`; M2 does not mint Kanban children | Spec Kit specs + `tasks.md` |
| 3 | **M3 IMPLEMENT** | Wave-holder session (`mint-m3-hermes.md`) then per-story implementers + `spring-to-quarkus-patterns` | Holder lints + mints parked story children (ack_gate parent); each story writes only `files_writable`; standing pointer on the card | Modernized sources under `files_writable` |
| 4 | **M4 VERIFY** | Domain / validation-release gates | Waits on story children (not the mint holder); `PROVISIONAL_ACCEPT` evidence package | Gate receipts |
| 5 | **M5 CLOSE** | Factory / full ACCEPT path | Story close when platform gates green | Pipeline + ACCEPT |

The **inner loop** (gates → fix → re-dispatch) corrects the *work* within a
card's retries. **Kanban parents/deps** sequence stories; a failed card blocks
dependents until unblocked or superseded. The **steering loop** (human) lands
skill/sensor/runbook improvements as versioned PRs — agents do not silently
rewrite `.hermes/skills/**` mid-run.

### Staying true to the source: the grounding chain

Gates answer *"is this output correct?"*. A long autonomous run needs a second, different question at every hand-off: **is what this stage produced actually derived from what the previous stage gave it?** That is what the grounding chain checks, and the run log opens with the question rather than a list of check names:

```text
GROUND  G1–G9 — grounding checks
         Each step sits at one pipeline handoff and answers: is what this
         stage produced actually derived from what the previous stage gave it?
         M1: G1/G2 · M2: G3/G6/G7/G8 · M3: G4 (inline) · M3 authoring: G5/G9
```

Each check then prints its verdict, its question in plain English, and the evidence behind the verdict — so the log is readable without knowing the codebase:

```text
GROUND  G1 — PASS
         Q: Does the architecture profile only claim things that exist in the legacy source?
         0 claimtruth findings — every §7 cited token resolves in the cited legacy file (rubric GREEN)
```

| Check | Hand-off | What it defends against |
|---|---|---|
| G1 | M1 | The profile claiming a class, method or annotation that does not exist in the legacy source |
| G2 | M1 | Vocabulary from a previous demo application leaking into this specimen's profile |
| G3 · G6 | M2 | Brief quotes drifting from the legacy files; brief claims about real symbols that are not true |
| G7 | M2 | A brief that contradicts itself — preserving X while forbidding X's only enabler |
| G8 | M2 | Briefs still quoting a profile section that M1 has since corrected |
| G4 | M3 | The planner inventing derived facts instead of using the ones inlined in its packet |
| G5 · G9 | M3 authoring | Task tokens that resolve nowhere; acceptance that can be satisfied without doing what the goal requires |

Together with Hermes Kanban typed bodies (`migration/bodies/m3-s-*.json`) and Spec Kit artifacts, this gives the migration several independent reasons to stay factual rather than one:

- **Claims are checked against the source.** G1 resolves every cited token in the file it was cited from; G2 keeps the vocabulary native to this specimen.
- **Derived facts are derived, not recalled.** Story identity, scope, and acceptance ride typed body fields and phase-dispatch; the coding seat is refused if it tries to invent them.
- **Evidence is anchored.** Code quotes carry `path:line` cites that the harness resolves; a cite that will not resolve is dropped from the packet rather than passed through for the agent to reconstruct.
- **The agent is given the facts instead of sent to find them.** Prefer inlined packet facts over open-ended legacy tree walks.
- **The whole derivation is reproducible.** Re-running M1 inventory/handoff and M2 Spec Kit → typed bodies regenerates harness-owned fields; invented fields would drift.

**The chain reports its own gaps.** `G5` and `G9` currently print `NOT-LANDED` with the reason (`Goal↔Acceptance coherence not enforced at authoring yet`), and the log states plainly that `GREEN is not full grounding`. That is deliberate: a check that quietly passes when it has not really run is worse than no check, and the honest verdict is what tells the steering loop where to invest next.

### The harness implementation: Hermes Agent (appendix)

Concepts need a runner. This stage uses **[Hermes Agent](https://hermes-agent.nousresearch.com/docs)** (Nous Research): a CLI-first agent that consumes the project's guides (AGENTS.md, skills, SOUL), runs sensors as tools, and drives work through **Kanban tasks** with native recovery (`max_runtime_seconds`) rather than a repo-owned supervisor.

- **CLI-native, headless-capable**: `hermes chat -q "..."`; Kanban via `dispatch`.
- **Governed models:** Managed Scope (`$HERMES_MANAGED_DIR/config.yaml`) pins
  platform `qwen3-6-27b` / MaaS — not a PVC checklist overlay.
- **Continuity with stage 070**: Spec Kit in-workspace (AD-S); stop before
  `/speckit.implement`.
- **Kanban is the engine**: see **Acts C–E** above for the human walkthrough.

> **Why Hermes?** CLI-native and headless-first, speaks AGENTS.md +
> agentskills.io, points at our MaaS gateway, durable Kanban board.

---

## Step 7: The factory ships it (future / not demo spine)

> **Maturity:** **Not DEMONSTRATED** for the Owner/Pet slice in the live prove
> path. Label clearly if shown; do not imply the room will see this today.

Nothing merges on agent authority, and no human approval substitutes for the factory either.

1. After M5 (full `ACCEPT` path — **after** kill-ratio pin; a waiver cannot
   author ACCEPT),
   re-analyze migrated code; done is the Step 3 baseline resolved or the
   gate REFUSE with a remediation card.
2. Push from the workspace (Git credentials required). The report ends:
   "pushed; the factory pipeline decides."
3. Watch the project's pipeline: clone → build → SonarQube quality gate → image.
   **Red CI means autonomy failed the regulated exit**; green CI is the proof.
4. Spot-check optional. Gaps → improve guides/sensors (steering), not mid-run
   skill rewrites.

**What you should see:** findings delta recorded, tests green, quality gate
passed — pipeline as merge authority. Do not claim this exit until a slice has
actually shipped.

---

## Step 8: The bill and the retro (optional beat)

1. Open the Stage 040 MaaS usage dashboard: token consumption for Hermes
   sessions / Kanban workers on the developer key, next to earlier stages.
2. After a real slice: skim Kanban run history (`hermes kanban runs`), any
   `migration/retro-proposals.md` / debt notes, and tighten guides/skills as
   versioned repo changes (stage 070 skills-retro practice).

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
- **Determinism where possible, inference where needed:** mechanical transforms ride skills and typed bodies; judgement-heavy work stays on Spec Kit + implementer cards under Hermes Kanban.
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
- [spec-kit](https://github.com/github/spec-kit) is the spec-driven development toolkit. Stage 080 provisions it **in the migration workspace only** (AD-S) via Hermes skill `specify-workspace-init` (`specify init --integration hermes`), installs the Non-Goals override, and stops at `/speckit.tasks` → Hermes `kanban_create()` — never `/speckit.implement`. Scaffold taxonomy: `.hermes/LAYOUT.md`.
- [Hermes Agent](https://hermes-agent.nousresearch.com/docs) is the CLI-first agent harness that owns the autonomous migration loop.
- [OpenCode](https://opencode.ai/) is the coding worker inside the harness, dispatched by Hermes one bounded task at a time, and remains available interactively, carried over from stage 070.
- [Coolstore cart (legacy demo input)](https://github.com/adnan-drina/coolstore-cart-legacy) is the small, stateless Spring Boot migration target — the first specimen the harness shipped; [Spring PetClinic REST (legacy demo input)](https://github.com/adnan-drina/spring-petclinic-rest-legacy) is the database-backed validated showcase, pinned at v2.6.2 so every run migrates the same code; the [Coolstore monolith](https://github.com/rhpds/mca-coolstore) remains available for longer runs.

## References

| Resource                                      | Link                                                                                                                                                                 |
| --------------------------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| Harness Engineering for Coding Agents         | [https://martinfowler.com/articles/harness-engineering.html](https://martinfowler.com/articles/harness-engineering.html)                                             |
| Maintainability sensors for coding agents     | [https://martinfowler.com/articles/sensors-for-coding-agents.html](https://martinfowler.com/articles/sensors-for-coding-agents.html)                                 |
| Open blueprint for cloud-native AI agents     | [https://developers.redhat.com/articles/2026/07/20/architect-open-blueprint-cloud-native-ai-agents](https://developers.redhat.com/articles/2026/07/20/architect-open-blueprint-cloud-native-ai-agents) |
| Hermes Agent documentation                    | [https://hermes-agent.nousresearch.com/docs](https://hermes-agent.nousresearch.com/docs)                                                                             |
| OpenClaw documentation (compared alternative) | [https://docs.openclaw.ai/](https://docs.openclaw.ai/)                                                                                                               |
| MTA 8.2 documentation                         | [https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.2/](https://docs.redhat.com/en/documentation/migration_toolkit_for_applications/8.2/) |
| OpenRewrite documentation                     | [https://docs.openrewrite.org/](https://docs.openrewrite.org/)                                                                                                       |
| spec-kit: spec-driven.md                      | [https://github.com/github/spec-kit/blob/main/spec-driven.md](https://github.com/github/spec-kit/blob/main/spec-driven.md)                                           |
| MaaS code assistant quickstart                | [https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant](https://docs.redhat.com/en/learn/ai-quickstarts/rh-maas-code-assistant)                     |


