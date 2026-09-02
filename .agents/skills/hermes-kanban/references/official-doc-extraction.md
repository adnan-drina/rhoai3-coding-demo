# Official Doc Extraction — hermes-kanban

Validated research dossier (capture date 2026-08-12) plus a reviewer
addendum extracting the v1 design spec PDF the research run could not
fetch. Reviewer validation: the state enum, failure_limit default, stale
timeout + heartbeat rule, scheduled_at semantics, silent-assignee-failure
quote, and HERMES_KANBAN_* precedence were re-verified verbatim against
live pages on 2026-08-12. Original dossier:
`source-analysis/hermes/hermes-kanban-capture-B.md`; spec copy:
`source-analysis/hermes/hermes-kanban-v1-spec.pdf`.

---

# hermes-kanban — Source Capture (Run B)

## Executive summary (5 lines)

1. **Captured**: the full Kanban reference page and the Kanban tutorial page (both read in full, ~1,460 combined lines), plus targeted extraction of kanban-specific material from CLI Commands, Slash Commands, Environment Variables, Delegation, Profiles, Cron, Gateway Internals, and Architecture — task lifecycle, dispatcher/worker mechanics, tool surface, CLI/slash surface, config keys, and event vocabulary are all documented in detail on the primary page.
2. **Confidence**: High for task states, dispatcher behavior, worker protocol, circuit breaker/retry/stale-reclaim mechanics, and the CLI/tool/event surfaces — all directly quoted from the primary doc. Medium for headless/cron interplay (thin, incidental documentation) and for whether some named constants (`BLOCK_RECURRENCE_LIMIT`, `_PROTOCOL_VIOLATION_FAILURE_LIMIT`) are actually exposed as `config.yaml` keys.
3. **Biggest gap**: `docs/hermes-kanban-v1-spec.pdf` is cited repeatedly by the primary doc page as *the* authoritative design spec (architecture, concurrency-correctness proof, comparative analysis, all 8+ collaboration patterns) but is a binary PDF in the repository that could not be fetched with the allowed read-only web tools — every fact attributed to it here is explicitly flagged as unavailable, not inferred.
4. **Placeholder contradiction check**: none found — the placeholder's pinned URL (`.../docs/user-guide/features/kanban`) is correct, live, and is in fact the single richest source page for this skill's entire scope.
5. **Suggested next skill to research**: `hermes-hooks` (the kanban page's "Lifecycle plugin hooks" section and the Gateway Internals hook-event table both assume a general hooks model this skill deliberately did not chase) or `hermes-sessions` (kanban's `task_runs`/`task_events` durability model parallels but is distinct from session persistence, and the boundary is worth confirming from that skill's side).

---

## 1. Capture header

| Field | Value |
|---|---|
| Product | Hermes Agent (Nous Research) |
| Version marker | **No version marker on any page read.** No "Docs version," build number, or "as of vX.Y" string appears on the Kanban, Kanban tutorial, CLI Commands, Slash Commands, Environment Variables, Delegation, Profiles, Cron, Gateway Internals, or Architecture pages. |
| Capture date | 2026-08-12 |
| Capturing run | B |

### Full page inventory (from `/docs/llms.txt`, the curated site index)

The index groups pages under headings; below is every page judged plausibly relevant to the TOPIC (kanban board, task lifecycle, dispatcher/worker, routing, headless/cron dispatch, kanban CLI/slash surface), marked **READ** (fetched and used) or **DEPRIORITIZED** (identified, not fetched, with reason).

| Page | URL | Status | Reason |
|---|---|---|---|
| Kanban Multi-Agent | `/docs/user-guide/features/kanban` | **READ (full, primary)** | Core reference page for the entire topic; already the placeholder's pin. |
| Kanban Tutorial | `/docs/user-guide/features/kanban-tutorial` | **READ (full)** | Narrative walkthrough of all 4 canonical stories (solo dev, fleet farming, retry pipeline, circuit breaker) with CLI/worker-tool-call transcripts; the primary page explicitly says "This page is the reference; the tutorial is the narrative." |
| CLI Commands | `/docs/reference/cli-commands` | **READ (targeted: `## hermes kanban` section + `hermes project bind-board`)** | Authoritative CLI reference; kanban section is a shorter paraphrase of the primary page's own CLI block, but confirms flag names and adds the `hermes project bind-board` cross-link. |
| Slash Commands | `/docs/reference/slash-commands` | **READ (targeted: `/kanban` rows, both CLI and messaging surfaces)** | Confirms `/kanban` argument-surface identity claim and cross-surface command-availability table. |
| Environment Variables | `/docs/reference/environment-variables` | **READ (targeted: `HERMES_KANBAN_*` rows)** | Only source for `HERMES_KANBAN_HOME`, `_BOARD`, `_DB`, `_WORKSPACES_ROOT`, `_DISPATCH_IN_GATEWAY`, `_TASK` semantics and precedence. |
| Delegation | `/docs/user-guide/features/delegation` | **READ (targeted: kanban-comparison line)** | Confirms the per-task model override is kanban-exclusive vs. `delegate_task`'s single global model pin — otherwise this page's core is `delegate_task`, out of TOPIC scope. |
| Profiles | `/docs/user-guide/profiles` | **READ (full)** | Documents `--description` at `hermes profile create` / `hermes profile describe` as the input to kanban's decomposer routing; explicitly says "see the Kanban guide for the full routing model," confirming Profiles is upstream of, not a duplicate of, kanban routing docs. |
| Cron Jobs | `/docs/user-guide/features/cron` | **READ (targeted grep, one hit)** | Only overlap found: Kanban workers share the "runtimes that can't receive detached results fall back to synchronous execution" behavior with `hermes -z` and `hermes cron run`. No kanban-task-creation-from-cron or chronos-provider integration is documented. |
| Gateway Internals | `/docs/developer-guide/architecture` companion — `/docs/developer-guide/gateway-internals` | **READ (full)** | No kanban-specific section; read to confirm the dispatcher-in-gateway claim's architectural context (background maintenance loop, hook events) and to positively establish the absence of a distinct kanban subsystem write-up here (see Gaps). |
| Architecture | `/docs/developer-guide/architecture` | **READ (full)** | Top-level subsystem map; Kanban is not listed as a "Major Subsystem" (only Agent Loop, Prompt System, Provider Resolution, Tool System, Session Persistence, Messaging Gateway, Plugin System, Cron, ACP, Trajectories) — confirms Kanban's design write-up lives entirely in the feature docs, not the developer/architecture docs. |
| Persistent Goals | `/docs/user-guide/features/goals` | DEPRIORITIZED | Kanban's `--goal` / `goal_mode` cards explicitly say they "share the engine with the `/goal` slash command, not the state" — the primary kanban page's own "Goal-mode cards" section already gives the load-bearing facts (judge model, turn budget, block-on-budget-exhaustion). Fetching the standalone Goals page would only add non-kanban `/goal` chat-session mechanics, out of TOPIC. |
| Hooks | `/docs/user-guide/features/hooks` | DEPRIORITIZED (boundary) | Owned by sibling skill `hermes-hooks`. Kanban-specific hook *events* (`kanban_task_claimed/completed/blocked`) are already fully quoted from the primary kanban page; the general hooks plugin contract is out of scope here. |
| Skills System | `/docs/user-guide/features/skills` | DEPRIORITIZED (boundary) | Owned by sibling skill `hermes-skills`. Kanban's `--skill` / `skills=[...]` task-pinning mechanic is fully captured from the primary page; the skill-authoring/install system itself is out of scope. |
| Sessions | `/docs/user-guide/sessions` | DEPRIORITIZED (boundary) | Owned by sibling skill `hermes-sessions`. Not fetched — no kanban-specific claim required it. |
| Configuration / Configuring Models | `/docs/user-guide/configuration`, `/docs/user-guide/configuring-models` | DEPRIORITIZED (boundary) | Owned by sibling skill `hermes-configuration` for config-key *wiring*. Kanban-specific config-key *behavior* is captured directly from the primary kanban page's own config tables, which is the in-scope half per the assignment. |
| Profile Commands | `/docs/reference/profile-commands` | DEPRIORITIZED | Not fetched; the Profiles page's own prose already supplied the one kanban-relevant fact (`--description` for routing). Risk: a `hermes profile describe --auto` flag detail could live here undiscovered — flagged as a minor gap below. |
| Delegation Patterns (guide) | `/docs/guides/delegation-patterns` | DEPRIORITIZED | Guide-level article; the primary kanban page already contains its own authoritative `delegate_task` vs. Kanban comparison table, which is the normative source. A guide article restating the same comparison would not add new normative facts. |
| Git Worktrees | `/docs/user-guide/git-worktrees` | DEPRIORITIZED | Kanban's `worktree:` workspace kind is fully specified on the primary page (path convention, `--branch`, preserved-on-completion). The general git-worktree feature page would add non-kanban detail out of TOPIC. |
| MCP Config Reference | `/docs/reference/mcp-config-reference` | DEPRIORITIZED | No kanban relevance identified in `llms.txt` description or in-page cross-references. |
| `docs/hermes-kanban-v1-spec.pdf` (repository, not docs site) | referenced by path only, no working hyperlink recovered | **UNREACHABLE — see Gaps** | Cited by name at least 6 times on the primary Kanban page as the source of the architecture rationale, concurrency-correctness proof, comparative analysis (vs. Cline Kanban / Paperclip / NanoClaw / Google Gemini Enterprise), and "eight canonical collaboration patterns" (a ninth, P9 Triage specifier, appears in-page). It is a binary PDF; the allowed `WebFetch` tool explicitly does not support binary/PDF content, and it is not a docs-site page reachable by domain-restricted search. Not fetched. Nothing from it appears in this dossier. |

### Dead links or redirects

None encountered among the 10 URLs actually fetched — every `WebFetch` call returned 200 content. The only unreachable resource is the repository PDF above (not a docs-site URL, and outside allowed-tool capability, not a dead link in the HTTP sense).

---

## 2. Recommended source pins

For `references/source-capture.md`, in order of authority for this skill's scope:

1. **`https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban`** — keep as primary pin (already pinned correctly). This single page is normative for: core concepts, task states, dispatcher behavior, worker protocol, tool surface, CLI reference, config keys, event reference, collaboration patterns, and the `/kanban` slash command.
2. **`https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban-tutorial`** — **recommend adding**. The current pin (kanban-only) misses this page entirely. It is the only source for the four worked stories with concrete state transitions in sequence (`created → claimed → spawn_failed → claimed → spawn_failed → claimed → gave_up`, etc.) and for confirming the reference/tutorial split is deliberate ("This page is the reference; the tutorial is the narrative" / "start there — this assumes you know what a task, run, assignee, and dispatcher are").
3. **`https://hermes-agent.nousresearch.com/docs/reference/environment-variables`** (kanban rows only) — recommend adding as a secondary citation source for `HERMES_KANBAN_*` semantics, since these are dispatcher/worker runtime behavior (in-scope) even though the page as a whole belongs more to `hermes-cli`/reference territory.
4. **`https://hermes-agent.nousresearch.com/docs/reference/cli-commands`** (`## hermes kanban` section only) and **`https://hermes-agent.nousresearch.com/docs/reference/slash-commands`** (`/kanban` rows only) — optional, lower priority: they corroborate but do not add facts beyond the primary page's own "CLI command reference" and "`/kanban` slash command" sections. Cite only if the reviewer wants an independent corroborating source for the CLI/slash surface.
5. **`https://hermes-agent.nousresearch.com/docs/user-guide/profiles`** — optional, for the routing-input fact (`--description` on `hermes profile create`/`describe`) if the skill discusses how the decomposer picks an assignee.

No pins proved irrelevant — the placeholder had only one pin and it was correct; the gap was incompleteness (missing the tutorial), not error.

---

## 3. Page maps

### 3.1 `/docs/user-guide/features/kanban` (primary)

Heading outline, in document order, one line per section:

- **(intro, no heading)** — durable SQLite task board shared across profiles; per-task row model; "two front doors" framing.
- **Two surfaces: the model talks through tools, you talk through the CLI** — `kanban_*` toolset vs. `hermes kanban …`/`/kanban …`/dashboard; both route through `kanban_db`.
- **Kanban vs. delegate_task** — comparison table (shape, parent-blocking, identity, resumability, human-in-loop, agents-per-task, audit trail, coordination) + one-sentence distinction + "when to use each."
- **Core concepts** — Board, Task (states enum), Link, Comment, Workspace (`scratch`/`dir:`/`worktree`), Dispatcher (tick interval, reclaim/promote/claim/spawn, `failure_limit`), Tenant.
- **Boards (multi-project)** — per-board isolation list; CLI board-management commands; board resolution order; slug validation rules.
  - Managing boards from the CLI
  - Managing boards from the dashboard
- **File attachments** — upload/storage/what-the-worker-sees/download-remove; 25 MB cap; `HERMES_KANBAN_ATTACHMENTS_ROOT`.
- **Quick start** — 5-command bootstrap sequence; "first thing that worker's model does is call `kanban_show()`."
  - Gateway-embedded dispatcher (default) — `config.yaml` snippet; `HERMES_KANBAN_DISPATCH_IN_GATEWAY`; `daemon` deprecation + `--force` escape hatch and its unsupported dual-dispatcher warning.
  - Idempotent create (for automation / webhooks) — `--idempotency-key`.
  - Bulk CLI verbs — multi-id lifecycle verbs; "Where an unblocked task lands" callout (unblock routing rules + `BLOCK_RECURRENCE_LIMIT` loop-breaker).
- **How workers interact with the board** — full `kanban_*` tool table (purpose, required params); typical single-worker turn; orchestrator fan-out turn.
  - Why tools instead of shelling to `hermes kanban` — 3 reasons (backend portability, shell-quoting fragility, structured errors); "zero schema footprint" claim.
  - Recommended handoff evidence — suggested `metadata` JSON shape; "four questions" framing; secrets warning.
  - The worker lifecycle — 4-step numbered protocol; heartbeat-interval guidance and stale-reclaim consequence; `protocol_violation` definition; agent-side nudge + `HERMES_KANBAN_STOP_NUDGE`; dispatcher-side bounded retry (`_PROTOCOL_VIOLATION_FAILURE_LIMIT`).
  - Pinning extra skills to a specific task — `kanban_create(skills=[...])`, CLI `--skill`, dashboard field; "no runtime install" caveat.
  - Per-task model override — `--model`/`--provider` at create or via `set-model`; dashboard dropdown parity.
  - Cost strategy: frontier orchestrator, inexpensive workers — per-profile `config.yaml` model split rationale.
  - Lifecycle plugin hooks — `kanban_task_claimed/completed/blocked`; process-split note (claimed fires in dispatcher, completed/blocked fire in worker); Python hook example.
  - Goal-mode cards (`--goal`) — goal loop mechanics, judge, turn budget, block-on-exhaustion; "Goal-mode cards borrow the `/goal` engine — they don't connect to it" callout.
  - How the orchestrator behaves — anti-temptation framing, Step-0 profile-discovery requirement, canonical two-researcher→writer example, "decide before you fan out" design-ownership rule, hotspot/collision framing pointer.
- **Dashboard (GUI)** — bundled plugin framing; open command.
  - What the plugin gives you — six-column board, triage auto-decompose default, card fields, per-profile lanes, live updates, drag-drop, create-task dialog, multi-select bulk actions, side drawer contents (incl. Decompose/Specify LLM actions).
  - Auto vs Manual orchestration — Auto/Manual pill; decomposer mechanics; config-key table (`auto_decompose`, `auto_decompose_per_tick`, `orchestrator_profile`, `default_assignee`, `auto_subscribe_on_create`); auxiliary-LLM-slot table (`kanban_decomposer`, `profile_describer`); profile-description input note; "NEVER lands a child task with `assignee=None`" rule.
  - Architecture — ASCII diagram, GUI-is-thin claim.
  - REST surface — full endpoint table.
  - Dashboard config — `dashboard.kanban.*` YAML keys.
  - Security model — unauthenticated-by-design plugin routes; WebSocket token requirement; `--host 0.0.0.0` warning.
  - Live updates — `task_events` append-only + WebSocket tail mechanics.
  - Extending it — plugin-contract pointer.
  - Scope boundary — "GUI is deliberately thin... Auto-assignment, budgets, governance gates, and org-chart views remain user-space" out-of-scope list.
- **CLI command reference** — full command block (every verb + flags in one fenced block); `--max-retries` semantics paragraph.
  - Concurrency, scheduling, and child promotion config — 4-row config table (`max_in_progress`, `max_in_progress_per_profile`, `auto_promote_children`, `default_workdir`) + YAML example.
  - Scheduled task starts (`scheduled_at`) — dispatcher skip-until-timestamp behavior + example.
  - Respawn guard — 3 named guard reasons (`blocker_auth`, `recent_success`, `active_pr`) and their rationale.
  - Drag-to-delete and bulk delete (dashboard) — trash drop zone + bulk REST delete.
  - Worker visibility endpoints — 4-row read-only/run-control endpoint table.
  - Kanban Swarm topology helper — `hermes kanban swarm` one-shot graph creation; atomicity guarantee.
- **`/kanban` slash command** — cross-surface identity claim (`hermes_cli.kanban.run_slash()`); example block; `shlex.split` quoting note.
  - Mid-run usage: `/kanban` bypasses the running-agent guard — 3 concrete human-in-the-loop examples.
  - Auto-subscribe on `/kanban create` (gateway only) — terminal-event auto-subscribe + example transcript; `--json` opt-out.
  - Output truncation in messaging — ~3800-char cap + footer text.
  - Autocomplete — Tab-cycled subcommand list vs. full verb list discrepancy noted in-page.
- **Collaboration patterns** — 9-row pattern table (P1–P9, including P9 Triage specifier which is not in the earlier "eight patterns" framing).
- **Handing context to follow-up cards (the parent link)** — parent-link-is-context-channel framing; immediate-`ready`-on-done-parent rule; `build_worker_context` "Parent task results" section format + example; "completed cards are immutable history" rule; worked bash example.
  - Reconciling colliding worker branches — reconciliation-card pattern; `merge-reconciler` bundled skill pointer.
  - Collision hotspots in parallel campaigns — `hotspot:` comment-prefix convention.
- **Multi-tenant usage** — `--tenant` + `$HERMES_TENANT` + example.
- **Gateway notifications** — auto-subscribe-on-create, terminal-event set, `--result` first-line delivery; explicit subscribe/list/unsubscribe CLI.
  - Multi-profile setups: delivery is profile-owned — single-dispatcher-owner rule; per-profile notifier ownership; legacy-subscription tie-break rule.
- **Runs — one row per attempt** — `task_runs` rationale; `summary`/`metadata`/`result` field definitions; worked tool-call + CLI-equivalent examples; `runs` CLI output example; reclaimed-run rule; synthetic-run-for-never-claimed rule; live-drawer-refresh note.
  - Forward compatibility — `workflow_template_id`/`current_step_key` reserved columns.
- **Event reference** — three clustered tables (Lifecycle, Edits, Worker telemetry) with Kind/Payload/When for every event kind.
- **Out of scope** — single-host-only statement; no cross-host coordination; workaround pointer (`delegate_task`/message queue).
- **Design spec** — pointer to `docs/hermes-kanban-v1-spec.pdf` (unreachable, see Gaps).

### 3.2 `/docs/user-guide/features/kanban-tutorial`

- **Setup** — bootstrap commands; explicit statement that spawned workers never see dashboard/CLI.
- **The board at a glance** — six-column description (Triage/Todo/Ready/In progress/Blocked/Done) with per-column behavior notes.
  - Flat view — "Lanes by profile" off behavior.
- **Story 1 — Solo dev shipping a feature** — 3-task parent-chain example; dependency-promotion behavior; full worker tool-call transcript; drawer/Run-History description; terminal inspection commands + example output.
- **Story 2 — Fleet farming** — 3-profile independent-task-pile example; parallel dispatch description; per-profile lane framing.
- **Story 3 — Role pipeline with retry** — pre-created-downstream-card model vs. first-class review lifecycle; full `kanban_request_review`/`kanban_request_changes` choreography with run-outcome sequence.
- **Story 4 — Circuit breaker and crash recovery** — spawn-failure circuit-breaker example with `--max-retries 3`; `hermes kanban runs` example output; crash-detection (`kill(pid, 0)`) OOM example with two-attempt run history.
- **Structured handoff — why summary and metadata matter** — restates worker_context composition; bulk-close guard restated with rationale ("copy-pasting the same summary to three tasks is almost always wrong").
- **Follow-up on a done card — CI remediation via the parent link** — worked remediation-card example; "three things that make this work" list.
- **Inspecting a task currently running** — `active` run outcome / no `ended_at` description.
- **Next steps** — pointers back to the reference page, `--help`, `watch --kinds`, `notify-subscribe`.

### 3.3 `/docs/reference/cli-commands` (targeted section)

- `## hermes kanban` — command signature, global `--board` flag, human/scripting-vs-tool-surface framing, full action table (subset of the primary page's own CLI block — omits `promote`, `edit`, `reassign`, `diagnostics`, `heartbeat`, `runs`, `assignees`, `watch`, `stats`, `log`, `notify-*`, `daemon`, `swarm` as distinct rows though several are mentioned by name elsewhere on the same page), board-resolution-order restatement, cross-reference to slash command and design-spec PDF.
- `## hermes project` (adjacent, one row) — `bind-board` action ties a named project to a kanban board for "a deterministic worktree + branch convention."

### 3.4 `/docs/reference/slash-commands` (targeted rows)

- Interactive-CLI table row for `/kanban` (Automation section) — argument-surface identity claim, multi-board sub-verbs listed.
- Messaging-platform table row for `/kanban` — identical argument-surface claim, explicit "bypasses the running-agent guard" statement, auto-subscribe-on-create restatement.
- Notes section — cross-surface availability list confirms `/kanban` "work[s] in both the CLI and the messaging gateway."

### 3.5 `/docs/reference/environment-variables` (targeted rows)

- General-purpose variables table — 6 `HERMES_KANBAN_*` rows (`_HOME`, `_BOARD`, `_DB`, `_WORKSPACES_ROOT`, `_DISPATCH_IN_GATEWAY`) plus a separate later row for `HERMES_KANBAN_TASK` (found in a different table further down the page, described as set by the dispatcher on worker spawn).

### 3.6 `/docs/user-guide/features/delegation` (targeted line)

- One paragraph, no dedicated heading captured beyond running prose: contrasts `delegation.model`'s single global pin against Kanban's per-task model override ("the kanban board... does support a per-task model override").

### 3.7 `/docs/user-guide/profiles`

- What are profiles? / Quick start / Creating a profile (Blank / `--clone` / `--clone-all` / `--clone-from`) — the "Blank profile" subsection is the only one with kanban relevance: instructs setting `--description` at creation "If you plan to use this profile as a kanban worker (or want the kanban orchestrator to route work to it)," and cross-references "the Kanban guide for the full routing model."
- Using profiles / Profiles vs workspaces vs sandboxing / Running gateways / Configuring profiles / Updating / Managing profiles / Deleting a profile / Tab completion / How it works / Sharing profiles as distributions — general profile mechanics, no further kanban-specific content.

### 3.8 `/docs/user-guide/features/cron` (targeted grep)

- One sentence under a "Manual runs are asynchronous" subsection: Kanban workers are grouped with `hermes -z` and `hermes cron run` as runtimes that "can't receive detached results" and so "fall back to synchronous execution automatically" for tools like `delegate_task`/`cronjob(action="run")`.

### 3.9 `/docs/developer-guide/gateway-internals`

- Full page read; no section is kanban-specific. Relevant confirmable facts: "Background Maintenance" lists "Cron ticking," "Session expiry," "Memory flush," "Cache refresh" — **does not list a Kanban dispatch tick**, even though the primary kanban page states the dispatcher "Runs inside the gateway by default." This is a documentation-coverage gap, not a contradiction (see Gaps).

### 3.10 `/docs/developer-guide/architecture`

- Full page read; "Major Subsystems" enumerates Agent Loop, Prompt System, Provider Resolution, Tool System, Session Persistence, Messaging Gateway, Plugin System, Cron, ACP Integration, Trajectories. **Kanban is not listed as a subsystem** and does not appear in the "Directory Structure" tree either (no `kanban/` or `kanban_db` entry shown). Confirms Kanban's own feature page is the sole authoritative write-up; the developer/architecture docs do not independently corroborate or contradict it.

---

## 4. Normative statements

All quotes are from `/docs/user-guide/features/kanban` unless otherwise noted. Section anchors are the heading names from §3.1/§3.2.

| Exact quote | Page + section | Why it matters for stage 080 |
|---|---|---|
| "Task — a row with title, optional body, one assignee (a profile name), status (`triage \| todo \| ready \| running \| blocked \| review \| done \| archived`), optional tenant namespace, optional idempotency key (dedup for retried automation)." | Kanban / Core concepts | Defines the canonical 8-state enum stage 080 task overlays must not silently extend without noting the divergence. |
| "Link — `task_links` row recording a parent → child dependency. The dispatcher promotes `todo → ready` when all parents are `done`." | Kanban / Core concepts | The dependency-gating rule that governs all pipeline/fan-out designs. |
| "Dispatcher — a long-lived loop that, every N seconds (default 60): reclaims stale claims, reclaims crashed workers (PID gone but TTL not yet expired), promotes ready tasks, atomically claims, spawns assigned profiles." | Kanban / Core concepts | The one-sentence definition of dispatcher responsibilities; default tick interval is load-bearing for any "how fast will my task run" design question. |
| "After `kanban.failure_limit` consecutive spawn failures on the same task (default: 2) the dispatcher auto-blocks it with the last error as the reason — prevents thrashing on tasks whose profile doesn't exist, workspace can't mount, etc." | Kanban / Core concepts | Default circuit-breaker threshold; directly affects retry/stuck-task design. |
| "Files explicitly declared through `kanban_complete(artifacts=[...])` are copied into durable per-task attachment storage before cleanup... A missing declared scratch artifact keeps the task in-flight so the worker can correct the path and retry." | Kanban / Core concepts (Workspace bullet) | Defines the only officially documented persistence path for scratch-workspace deliverables, and a self-healing retry rule for a missing declared artifact. |
| "Relative paths like `dir:../tenants/foo/` are rejected at dispatch because they'd resolve against whatever CWD the dispatcher happens to be in, which is ambiguous and a confused-deputy escape vector." | Kanban / Core concepts | Security-relevant hard constraint on `dir:` workspace paths. |
| "One dispatcher sweeps all boards per tick; workers are spawned with `HERMES_KANBAN_BOARD` pinned so they can't see other boards." | Kanban / Core concepts | Single-dispatcher-process model; per-board isolation mechanism. |
| "Slugs are validated: lowercase alphanumerics + hyphens + underscores, 1-64 chars, must start with alphanumeric... Anything else (slashes, spaces, dots, `..`) is rejected at the CLI layer so path-traversal tricks can't name a board." | Kanban / Boards (multi-project) | Board-slug validation is a security control, not cosmetic. |
| "Board resolution order (highest precedence first): 1. Explicit `--board <slug>`... 2. `HERMES_KANBAN_BOARD` env var... 3. `~/.hermes/kanban/current`... 4. `default`." | Kanban / Boards (multi-project) | Canonical precedence chain for any board-targeting logic. |
| "Each upload is capped at 25 MB." | Kanban / File attachments | Hard limit for the attachment mechanism. |
| "Without a running gateway, `ready` tasks stay where they are until one comes up — `hermes kanban create` warns about this at creation time." | Kanban / Gateway-embedded dispatcher | Direct headless-operation implication: no gateway process ⇒ no dispatch, by design. |
| "Running `hermes kanban daemon` as a separate process is deprecated; use the gateway... running both a gateway-embedded dispatcher AND a standalone daemon against the same `kanban.db` causes claim races and is not supported." | Kanban / Gateway-embedded dispatcher | Hard constraint for headless/dual-dispatcher deployment topologies. |
| "`unblock` restores the safe source phase: `review` for reviewer-origin work whose parents are complete, `ready` for implementation work whose parents are complete, or `todo` while any parent remains open. A `todo` task keeps its source-phase provenance... `unblock` never routes directly to `triage`." | Kanban / Bulk CLI verbs | Precise unblock-routing rule; frequently misunderstood without this quote. |
| "after a task is blocked → unblocked → re-blocked for the same cause `BLOCK_RECURRENCE_LIMIT` times (default `2`), the unblock-loop breaker stops sending it back to `blocked`... and routes it to `triage` for a human decision. This is a deterministic DB guard, not an LLM judgment call, and a task's body text cannot opt out of it: the recurrence counter deliberately survives each unblock (it resets only on a successful `complete`)." | Kanban / Bulk CLI verbs | Loop-breaker is deterministic and cannot be bypassed by prompt/body content — important safety property for stage 080 task-body design. |
| "Dispatcher-spawned workers are still task-scoped for destructive lifecycle operations and cannot mutate unrelated tasks." | Kanban / How workers interact with the board | Confirms a tool-level authorization boundary even for orchestrator-capable tool calls. |
| "Zero schema footprint on normal sessions. A regular `hermes chat` session has zero `kanban_*` tools in its schema unless the active profile explicitly enables the `kanban` toolset for orchestrator work." | Kanban / Why tools instead of shelling to hermes kanban | Confirms opt-in-only tool exposure; relevant to profile/toolset config design (behavior, not the config schema itself). |
| "If your work may run longer than 1 hour, call `kanban_heartbeat` at least once an hour — the dispatcher reclaims tasks that have been running past `kanban.dispatch_stale_timeout_seconds` (default 4 h) with no heartbeat in the last hour... A reclaim is benign (the task goes back to `ready` for re-dispatch without a failure-counter tick) but you lose your current run's progress." | Kanban / The worker lifecycle | Defines the stale-task watchdog precisely: default 4h total AND no heartbeat in the last hour, and explicitly states it does not tick the failure counter. |
| "If the worker process exits with status 0 while the task is still `running`, the dispatcher treats that as a protocol violation and emits a `protocol_violation` event." | Kanban / The worker lifecycle | Defines the "silent success exit" failure mode precisely. |
| "This guard is active only for dispatcher-spawned workers (`HERMES_KANBAN_TASK` is set) and can be disabled with `HERMES_KANBAN_STOP_NUDGE=0`." | Kanban / The worker lifecycle | Scoping + kill-switch for the agent-side stop-nudge safety net. |
| "the dispatcher gives the violation a bounded retry (up to `_PROTOCOL_VIOLATION_FAILURE_LIMIT` consecutive violations, default 3) before auto-blocking the task instead of respawning it into the same loop. The budget counts only consecutive clean-exit protocol violations — interleaved rate-limited requeues are neutral, and any other failure kind resets the streak — and a per-task `max_retries` overrides the bound." | Kanban / The worker lifecycle | Precise retry-budget semantics for the specific "model exited without calling a board tool" failure mode, distinct from the general circuit breaker. |
| "The skill names must match skills that are actually installed on the assignee's profile (run `hermes skills list` to see what's available); there's no runtime install." | Kanban / Pinning extra skills to a specific task | Hard constraint: task-pinned skills are not auto-installed. |
| "With no override, the worker uses its profile's configured model." | Kanban / Per-task model override | Default-fallback behavior for `model_override`. |
| "Board transitions fire plugin hooks: `kanban_task_claimed`, `kanban_task_completed`, and `kanban_task_blocked`, each carrying `task_id` and `profile_name`. Hooks fire after the board DB change commits, so callbacks always see durable state. Note the process split: `kanban_task_claimed` fires in the dispatcher process, while `kanban_task_completed`/`kanban_task_blocked` fire in the worker process — register the hook in the dispatcher profile to observe every transition centrally." | Kanban / Lifecycle plugin hooks | Directly answers "which process fires which kanban hook," a common integration pitfall. Boundary note: general hook mechanics belong to `hermes-hooks`. |
| "By default each worker gets one shot at its card — do the work, call `kanban_complete`/`kanban_block`, exit. Pass `--goal`... to instead run that worker in a goal loop... after every turn an auxiliary judge checks the worker's output against the card's title + body (treated as the acceptance criteria), and if the work isn't done — and the turn budget remains — the worker keeps going... until the judge agrees, the worker terminates the task itself, or the budget runs out (which blocks the card for human review rather than exiting silently)." | Kanban / Goal-mode cards | Precisely defines goal-mode's judge loop and its terminal conditions (3 distinct ways it ends). |
| "`--goal` runs the continuation loop inside that one card's worker session. It shares the engine with the `/goal` slash command, not the state: setting a `/goal` in a chat session never creates, claims, or moves a kanban card, and a goal-mode card's loop is invisible to any chat session's `/goal status`." | Kanban / Goal-mode cards | Explicit non-interaction boundary between two features that sound related. |
| "A well-behaved orchestrator does not do the work itself... the dispatcher silently fails on unknown assignee names, so the orchestrator must ground every card in profiles that actually exist on your machine." | Kanban / How the orchestrator behaves | Critical failure mode: unknown assignee = silent dispatcher failure, not an error surfaced to the orchestrator. |
| "Workers cannot see sibling cards, so every child card body must carry every decision it depends on." | Kanban / How the orchestrator behaves | Hard design constraint for fan-out task-body authoring. |
| "The decomposer NEVER lands a child task with `assignee=None`: when the LLM picks an unknown profile, the child gets routed to `kanban.default_assignee` (or the active default profile if that's unset)." | Kanban / Auto vs Manual orchestration | Guarantees every auto-decomposed child always has an assignee. |
| "`kanban.orchestrator_profile` does not load that profile's prompt, skills, or custom logic into the decomposition call. It controls who owns the root/orchestration task after fan-out." | Kanban / Auto vs Manual orchestration | Precisely scopes what this frequently-misread config key does and does NOT do. |
| "The dashboard's HTTP auth middleware explicitly skips /api/plugins/— plugin routes are unauthenticated by design because the dashboard binds to localhost by default... If you run `hermes dashboard --host 0.0.0.0`, every plugin route — kanban included — becomes reachable from the network. Don't do that on a shared host." | Kanban / Security model | Security-critical statement for any deployment/stage-080 exposure decision. |
| "`--max-retries` is a per-task circuit-breaker override for the dispatcher. `--max-retries 1` blocks the task on the first non-successful attempt, while `--max-retries 3` allows two retries and blocks on the third failure. Omit it to use `kanban.failure_limit` from `config.yaml`, then the built-in default." | Kanban / CLI command reference | Precise per-task override chain (task flag → config key → built-in default). |
| "The dispatcher refuses to re-spawn a ready task when it hit a quota/auth/429 error on the previous run (`blocker_auth`), or completed a run successfully within the guard window (`recent_success`), or a recent task comment links to a GitHub PR (`active_pr`)." | Kanban / Respawn guard | Three named, distinct anti-thrash conditions, each independently important for debugging "why didn't my task re-run." |
| "A task is a logical unit of work; a run is one attempt to execute it... A task that's been attempted three times has three `task_runs` rows." | Kanban / Runs | Core task-vs-run data-model distinction. |
| "Downstream children read the most recent completed run's summary + metadata for each parent. Retrying workers read the prior attempts on their own task (outcome, summary, error) so they don't repeat a path that already failed." | Kanban / Runs | Defines exactly what context propagates where. |
| "Bulk close caveat. `hermes kanban complete a b c --summary X` is refused — structured handoff is per-run, so copy-pasting the same summary to N tasks is almost always wrong." | Kanban / Runs | Hard CLI-level restriction, not merely a style recommendation. |
| "Reclaimed runs from status changes. If you drag a running task off `running`... or archive a task that was still running, the in-flight run closes with `outcome='reclaimed'` rather than being orphaned. The `task_runs` row is always in a terminal state when `tasks.current_run_id` is `NULL`, and vice versa — that invariant holds across CLI, dashboard, dispatcher, and notifier." | Kanban / Runs | States a cross-surface data invariant explicitly. |
| "Synthetic runs for never-claimed completions... the kernel inserts a zero-duration run row (`started_at == ended_at`) carrying the summary / metadata / reason so attempt history stays complete." | Kanban / Runs | Explains an edge case (human completes a task a worker never claimed) that would otherwise look like a data gap. |
| "Two nullable columns on `tasks` are reserved for v2 workflow routing: `workflow_template_id`... and `current_step_key`... The v1 kernel ignores them for routing but lets clients write them." | Kanban / Runs (Forward compatibility) | Confirms these two CLI filter fields (`--workflow-template-id`, `--current-step-key` seen in CLI reference) are currently inert for routing — important so stage 080 doesn't assume they gate anything today. |
| "`dependency_wait` — Worker blocked with `kind=dependency` — the task is only waiting on another task, so it routes to `todo`(parent-gated, auto-promoted) instead of `blocked`. No human needed." | Kanban / Event reference | Clarifies that a `kind=dependency` block is not a "stuck" state requiring a human. |
| "`stale`... Dispatcher SIGTERM'd the host-local worker (if any), reset the task to `ready` for re-dispatch. Does NOT tick the failure counter (stale is dispatcher-side absence detection, not a worker fault)." | Kanban / Event reference | Explicit statement that stale-reclaim is fault-neutral for circuit-breaker accounting — directly relevant to "stuck/failed/retry handling" scope item. |
| "`reconciled`... Orphaned-card reconciliation: the card was `running` with broken claim bookkeeping... and no live worker, so none of the TTL/crash/stale paths could ever recover it. The dispatcher requeued it to `ready`... Gated by `kanban.reconcile_orphans` in config.yaml (default `true`)." | Kanban / Event reference | Documents a fourth, distinct recovery path beyond TTL-expiry/crash-detection/stale-timeout. |
| "`gave_up`... Circuit breaker fired after N consecutive non-successful attempts. Task auto-blocks with the last error. The effective limit resolves as task `max_retries`, then dispatcher `failure_limit`/`kanban.failure_limit`, then the built-in default." | Kanban / Event reference | The authoritative 3-level resolution order for the circuit-breaker threshold. |
| "Kanban is deliberately single-host. `~/.hermes/kanban.db` is a local SQLite file and the dispatcher spawns workers on the same machine... If you need multi-host, run an independent board per host and use `delegate_task`/ a message queue to bridge them." | Kanban / Out of scope | Explicit architectural limit — important for any stage 080 multi-host ambition. |
| "Runtimes that can't receive detached results (one-shot `hermes -z`, `hermes cron run` from the CLI, cron child sessions, Kanban workers) fall back to synchronous execution automatically." | Cron / Manual runs are asynchronous | The only documented cron↔kanban interaction: shared synchronous-fallback behavior for detached-result-incapable runtimes. |
| "If you plan to use this profile as a kanban worker (or want the kanban orchestrator to route work to it), pass `--description "<text>"` at create time so the orchestrator knows what it's good at." | Profiles / Creating a profile → Blank profile | Names the exact upstream input (`--description`) consumed by the decomposer's routing decision documented on the kanban page. |

---

## 5. Reference tables

### 5.1 Task states / lifecycle

| State | Documented meaning | Entry conditions (documented) | Exit / notes |
|---|---|---|---|
| `triage` | "the parking column for rough ideas" | Explicit `--triage` at create; `block_loop_detected` re-routes here after `BLOCK_RECURRENCE_LIMIT` same-cause re-blocks; dashboard "Creating from the Triage column automatically parks the new task in triage" | Auto-decompose (default) fans it into children + keeps parent alive until graph completes, then promotes parent back to `ready`; or `hermes kanban specify`/`decompose` (manual) |
| `todo` | "created but waiting on dependencies, or not yet assigned" (tutorial); holds tasks whose parents aren't all `done` | `kanban_create` with open parents; `unblock` when a parent remains open; `dependency_wait` block routes here | Promoted to `ready` by `recompute_ready` when the last parent hits `done` (`promoted` event) |
| `ready` | "assigned and waiting for the dispatcher to claim" | Task created with all parents `done` (immediate); `promoted` from `todo`; `unblock` of reviewer/implementer-origin work whose parents are complete | Dispatcher atomically `claim`s → `running`; dispatcher skips if `scheduled_at` is future; respawn-guard reasons can also keep it here without spawning |
| `running` | "a worker is actively running the task" | Dispatcher claim + spawn (`claimed`, `spawned` events) | `kanban_complete` → `done`; `kanban_block`/`kanban_request_review` transitions away; crash/TTL/stale/reconcile paths return it to `ready` |
| `blocked` | "a worker asked for human input, or the circuit breaker tripped" | `kanban_block` (non-dependency kinds); `gave_up` circuit-breaker trip; `_PROTOCOL_VIOLATION_FAILURE_LIMIT` exhaustion | `unblock` → source phase (`review`/`ready`/`todo`); repeated same-cause re-block → `triage` via `block_loop_detected` |
| `review` | Card is under review (first-class review lifecycle) | `kanban_request_review` | `kanban_complete` (approve) → `done`; `kanban_request_changes` → back to original implementer (ready/todo) without block-loop accounting; `reopen-review` also sends back for changes |
| `done` | Completed | `kanban_complete` (worker or human/CLI) | Terminal for that task (row); new work continues via child cards on the parent link, not by reopening |
| `archived` | "Hidden from the default board" | `hermes kanban archive`; dashboard archive/drag-to-trash | `gc` removes scratch workspaces for archived tasks |
| *(possible additional state)* `scheduled` | CLI-commands reference literally says `hermes kanban schedule` will "Park time-delay/follow-up work in `scheduled`" | Unclear — see Gaps §9 | Unclear — see Gaps §9 |

Run-level outcomes (distinct from task states, one row per `task_runs` attempt): `completed`, `blocked`, `review_requested`, `changes_requested`, `crashed`, `timed_out`, `spawn_failed`, `reclaimed`, `gave_up`, `active` (in-flight, no `ended_at`).

### 5.2 Config keys (all documented as living under `kanban:` in `~/.hermes/config.yaml` unless noted)

| Key | Default | Description | Source |
|---|---|---|---|
| `dispatch_in_gateway` | `true` | Dispatcher runs inside the gateway process | Kanban / Gateway-embedded dispatcher |
| `dispatch_interval_seconds` | `60` | Dispatcher tick interval | Kanban / Gateway-embedded dispatcher |
| `review_dispatch` | `true` | Spawn the assigned profile with the bundled `sdlc-review` skill for review-column dispatch; set `false` for human-only review boards | Kanban / Gateway-embedded dispatcher |
| `failure_limit` | `2` | Consecutive spawn-failure threshold before auto-block (`gave_up`) | Kanban / Core concepts; corroborated in Event reference (`gave_up`) |
| `dispatch_stale_timeout_seconds` | `4h` (4 hours) | Max running time with no heartbeat in the last hour before stale-reclaim | Kanban / The worker lifecycle; Event reference (`stale`) |
| `auto_decompose` | `true` | Dispatcher auto-runs the decomposer on triage tasks every tick | Kanban / Auto vs Manual orchestration (config table) |
| `auto_decompose_per_tick` | `3` | Cap on decompositions per dispatcher tick; excess defers to next tick | Kanban / Auto vs Manual orchestration (config table) |
| `orchestrator_profile` | `""` (empty → active default profile) | Profile assigned to the root/orchestration task after decomposition | Kanban / Auto vs Manual orchestration (config table) |
| `default_assignee` | `""` (empty → active default) | Where a child task lands when the LLM picks an unknown profile | Kanban / Auto vs Manual orchestration (config table) |
| `auto_subscribe_on_create` | `true` | Auto-subscribe originating session to a newly `kanban_create`d task's completion/block events | Kanban / Auto vs Manual orchestration (config table) |
| `max_in_progress` | unset (unlimited) | Caps simultaneously running tasks board-wide; invalid/<1 values log a warning and behave as unlimited | Kanban / Concurrency, scheduling, and child promotion config |
| `max_in_progress_per_profile` | unset (unlimited) | Per-assignee-profile concurrency cap; applies alongside `max_in_progress` (both must allow a spawn) | Kanban / Concurrency, scheduling, and child promotion config |
| `auto_promote_children` | `true` | Auto-promote no-blocker decomposed children to `ready`; `false` requires manual promotion | Kanban / Concurrency, scheduling, and child promotion config |
| `default_workdir` | unset | Board-level default working directory for new tasks when neither `--workspace` nor the task overrides it | Kanban / Concurrency, scheduling, and child promotion config |
| `reconcile_orphans` | `true` | Gates the orphaned-`running`-card reconciliation path | Kanban / Event reference (`reconciled`) |
| `auxiliary.kanban_decomposer` | (model path, no stated default model) | Model used to produce the triage→children task graph | Kanban / Auto vs Manual orchestration (aux table) |
| `auxiliary.profile_describer` | (model path, no stated default model) | Model used by `hermes profile describe --auto` | Kanban / Auto vs Manual orchestration (aux table) |
| `auxiliary.triage_specifier` | (model path, no stated default model) | Model used by `hermes kanban specify` | Kanban / CLI command reference (`specify` row) |
| `dashboard.kanban.default_tenant` | undocumented (no value shown; "optional... falls back to the shown default" but no default literal given) | Preselects the dashboard tenant filter | Kanban / Dashboard config |
| `dashboard.kanban.lane_by_profile` | `true` (shown in example, described as "default for the 'lanes by profile' toggle") | Default for lanes-by-profile toggle | Kanban / Dashboard config |
| `dashboard.kanban.include_archived_by_default` | `false` (shown in example) | Whether archived tasks show by default | Kanban / Dashboard config |
| `dashboard.kanban.render_markdown` | `true` (shown in example) | Markdown vs. plain `<pre>` rendering | Kanban / Dashboard config |
| `dashboard.plugins.kanban.enabled` | implicit `true` (disable by setting `false`) | Disable the kanban dashboard plugin without removing it | Kanban / Extending it |
| `BLOCK_RECURRENCE_LIMIT` | `2` | Same-cause re-block count before loop-breaker routes to `triage`; page says "raise `BLOCK_RECURRENCE_LIMIT` if the loop is expected" | Kanban / Bulk CLI verbs. **Undocumented**: whether this is a `config.yaml`-settable key (with what dotted name) or a code-level constant only — not stated on any page read. |
| `_PROTOCOL_VIOLATION_FAILURE_LIMIT` | `3` | Consecutive clean-exit protocol-violation budget before auto-block | Kanban / The worker lifecycle. **Undocumented**: same ambiguity as above — the leading underscore and code-style name suggest this may not be an exposed config key at all. |

### 5.3 Commands (`hermes kanban <verb>`, from the primary page's CLI command reference block, cross-checked against `/docs/reference/cli-commands`)

| Command | Purpose | Notable flags |
|---|---|---|
| `init` | Create `kanban.db` + print daemon hint; idempotent | — |
| `create "<title>"` | Create a task | `--body`, `--assignee`, `--parent <id>` (repeatable), `--tenant`, `--workspace scratch\|worktree\|worktree:<path>\|dir:<path>`, `--branch`, `--priority N`, `--triage`, `--idempotency-key KEY`, `--max-runtime`, `--max-retries N`, `--goal`, `--goal-max-turns N` (default 20), `--skill` (repeatable), `--json` |
| `list` / `ls` | List tasks | `--mine`, `--assignee P`, `--status S`, `--tenant T`, `--archived`, `--workflow-template-id <id>`, `--current-step-key <key>`, `--sort`, `--json` |
| `show <id>` | Show a task with comments/events | `--json` |
| `assign <id> <profile>` | Assign/reassign (`none` to unassign) | refused while running |
| `reassign <id>... <profile>` | Bulk reassign | — |
| `edit <id>` | Edit title/body/priority in place | `--title`, `--body`, `--priority N` |
| `promote <id>...` | Move todo/blocked tasks to ready (recovery) | — |
| `schedule <id> --at <ISO8601>` | Set/clear scheduled start | — |
| `diagnostics` (alias `diag`) | Board health snapshot | `--json` |
| `link <parent_id> <child_id>` | Add dependency; cycle-detected | — |
| `unlink <parent_id> <child_id>` | Remove dependency | — |
| `claim <id>` | Atomically claim a ready task; prints resolved workspace path | `--ttl SECONDS` |
| `comment <id> "<text>"` | Append a comment | `--author NAME` |
| `complete <id>...` | Mark done (bulk-capable, but see bulk-close caveat) | `--result`, `--summary`, `--metadata` |
| `block <id> "<reason>"` | Mark blocked; also appends reason as comment | `--ids <id>...` |
| `request-review <id>` | Move to `review`, not a block | `--summary`, `--metadata`, `--reviewer` |
| `request-changes <id> "<changes>"` | Reviewer verdict: close review run, route to original implementer | — |
| `reopen-review <id>...` | `review` → ready/todo | `--reason` |
| `unblock <id>...` | Restore to source phase | — |
| `archive <id>...` | Hide from default list | — |
| `tail <id>` | Follow a single task's event stream | — |
| `watch` | Stream all board events live | `--assignee P`, `--tenant T`, `--kinds`, `--interval SECS` |
| `heartbeat <id>` | Worker liveness signal | `--note` |
| `runs <id>` | Attempt history | `--json` |
| `assignees` | Profiles on disk + per-assignee task counts | `--json` |
| `dispatch` | One-shot dispatcher pass | `--dry-run`, `--max N`, `--failure-limit N`, `--json` |
| `daemon` (DEPRECATED) | Standalone dispatcher; use `hermes gateway start` instead | `--force`, `--failure-limit N`, `--pidfile PATH`, `-v` |
| `stats` | Per-status + per-assignee counts | `--json` |
| `log <id>` | Worker log from `~/.hermes/kanban/logs/` | `--tail BYTES` |
| `notify-subscribe <id>` | Gateway bridge hook (used by `/kanban` in the gateway) | `--platform`, `--chat-id`, `--thread-id`, `--user-id` |
| `notify-list [<id>]` | List subscriptions | `--json` |
| `notify-unsubscribe <id>` | Remove subscription | `--platform`, `--chat-id`, `--thread-id` |
| `context <id>` | Print full worker-visible context | — |
| `specify [<id>\|--all]` | Flesh out a triage idea into a spec, promote to `todo` | `--tenant`, `--author`, `--json` |
| `gc` | Remove scratch workspaces + old events/logs | `--event-retention-days N`, `--log-retention-days N` (defaults `undocumented`) |
| `boards list` / `ls` | List all boards with task counts | `--json`, `--all` |
| `boards create <slug>` | Create a new board | `--name`, `--description`, `--icon`, `--color`, `--switch` |
| `boards switch <slug>` / `boards use` | Persist active board | — |
| `boards show` / `boards current` | Print active board's name/DB path/counts | — |
| `boards rename <slug> "<name>"` | Change display name (slug immutable) | — |
| `boards rm <slug>` | Archive (default) or hard-delete | `--delete` (refused for `default`) |
| `swarm "<goal>"` | Create a durable Kanban Swarm v1 graph (root + N workers + verifier + synthesizer) in one atomic commit | `--workers`, `--verifier`, `--synthesizer` |

Global flag on every action: `--board <slug>`.

### 5.4 Flags (selected, with documented type/default/description — beyond the command table above)

| Flag | Command(s) | Type | Default | Description |
|---|---|---|---|---|
| `--max-retries N` | `create`, effectively also read at dispatch | int | unset → falls back to `kanban.failure_limit` → built-in default | "`--max-retries 1` blocks the task on the first non-successful attempt, while `--max-retries 3` allows two retries and blocks on the third failure." Also overrides the protocol-violation retry budget. |
| `--goal-max-turns N` | `create --goal` | int | `20` | Turn budget for goal-mode judge loop |
| `--idempotency-key KEY` | `create` | string | none | "Any subsequent call with the same key returns the existing task id instead of duplicating." |
| `--workspace` | `create` | enum-like string: `scratch\|worktree\|worktree:<path>\|dir:<path>` | `scratch` | Selects workspace kind |
| `--priority N` | `create`, `edit` | int | undocumented (no default literal shown) | Task priority; surfaced as a "priority badge" in dashboard |
| `--ttl SECONDS` | `claim` | int (seconds) | undocumented | Claim TTL |
| `--tail BYTES` | `log` | int | undocumented | Worker log tail size |
| `--event-retention-days N` / `--log-retention-days N` | `gc` | int | `undocumented` | GC retention windows |

### 5.5 `HERMES_KANBAN_*` environment variables

| Variable | Description | Source |
|---|---|---|
| `HERMES_KANBAN_HOME` | "Override the shared Hermes root that anchors the kanban board (db + workspaces + worker logs). Falls back to `get_default_hermes_root()`(the parent of any active profile). Useful for tests and unusual deployments" | Environment Variables reference |
| `HERMES_KANBAN_BOARD` | "Pin the active kanban board for this process. Takes precedence over `~/.hermes/kanban/current`; the dispatcher injects this into worker subprocess env so workers physically cannot see tasks on other boards. Defaults to `default`. Slug validation: lowercase alphanumerics + hyphens + underscores, 1-64 chars" | Environment Variables reference (also stated on Kanban page) |
| `HERMES_KANBAN_DB` | "Pin the kanban database file path directly (highest precedence; beats `HERMES_KANBAN_BOARD` and `HERMES_KANBAN_HOME`). The dispatcher injects this into worker subprocess env so profile workers converge on the dispatcher's board" | Environment Variables reference |
| `HERMES_KANBAN_WORKSPACES_ROOT` | "Pin the kanban workspaces root directly (highest precedence for workspaces; beats `HERMES_KANBAN_HOME`). The dispatcher injects this into worker subprocess env" | Environment Variables reference |
| `HERMES_KANBAN_DISPATCH_IN_GATEWAY` | "Runtime override for `kanban.dispatch_in_gateway`. Set to `0`, `false`, `no`, or `off` to keep the gateway from starting the embedded Kanban dispatcher; any other non-empty value enables it. Useful when a separate dispatcher process owns the board." | Environment Variables reference |
| `HERMES_KANBAN_TASK` | "Set by the kanban dispatcher when spawning a worker (task UUID). Workers and the spawned `hermes-tools` MCP subprocess inherit it so kanban tools gate correctly. Don't set manually." | Environment Variables reference |
| `HERMES_KANBAN_ATTACHMENTS_ROOT` | Pins a custom attachment storage location | Kanban / File attachments (not independently found on the Environment Variables page — possible coverage gap on that reference page) |
| `HERMES_KANBAN_STOP_NUDGE` | Set to disable (`=0`) the agent-side stop-nudge guard | Kanban / The worker lifecycle (not independently found on the Environment Variables page — possible coverage gap on that reference page) |
| `HERMES_TENANT` | Exposed to workers for memory-key namespacing in multi-tenant usage | Kanban / Multi-tenant usage |

### 5.6 `kanban_*` agent tool surface

| Tool | Purpose | Required params | Availability |
|---|---|---|---|
| `kanban_show` | Read current task (title, body, prior attempts, parent handoffs, comments, `worker_context`); defaults to env's task id | — | All spawned workers |
| `kanban_list` | List task summaries, filterable by `assignee`/`status`/`tenant`/archived/limit | — | Orchestrators |
| `kanban_complete` | Finish with `summary`+`metadata` | at least one of `summary`/`result` | All workers |
| `kanban_request_review` | Start same-card review | `summary` | All workers |
| `kanban_request_changes` | Reviewer verdict from active review run | `reason` | Reviewer workers |
| `kanban_block` | Stop work, route by `kind` (`dependency`/`needs_input`/`capability`/`transient`) | `reason` | All workers |
| `kanban_heartbeat` | Liveness signal, pure side-effect | — | All workers |
| `kanban_comment` | Append durable note | `task_id`, `body` | All workers |
| `kanban_attach` | Attach file inline (base64), 25 MB cap | file bytes + name | All workers |
| `kanban_attach_url` | Attach file by URL | `url` | All workers |
| `kanban_attachments` | List a task's attachments | — | All workers |
| `kanban_create` | Fan out into child tasks | `title`, `assignee` | Orchestrators |
| `kanban_link` | Add parent→child edge after the fact | `parent_id`, `child_id` | Orchestrators |
| `kanban_unblock` | Restore a blocked task to source phase | `task_id` | Orchestrators |

Note: the CLI Commands reference page states a slightly narrower baseline list (`kanban_show, kanban_complete, kanban_request_review, kanban_request_changes, kanban_block, kanban_create, kanban_link, kanban_comment, kanban_heartbeat` for all workers, "orchestrator profiles also get `kanban_list` and `kanban_unblock`"), which both narrows tool-availability slightly differently from the primary page's own table (which lists all 13 tools together and marks only 5 of them "(Orchestrators)" in prose: `kanban_list`, `kanban_create`, `kanban_link`, `kanban_unblock`, and `kanban_comment` on foreign tasks). This is a minor cross-page inconsistency — see Gaps §9.

### 5.7 Event reference (`task_events` kinds)

**Lifecycle cluster:**

| Kind | Payload | When |
|---|---|---|
| `created` | `{assignee, status, parents, tenant}` | Task inserted; `run_id` NULL |
| `promoted` | — | `todo → ready`, all parents `done`; `run_id` NULL |
| `claimed` | `{lock, expires, run_id}` | Dispatcher atomically claimed a ready task |
| `completed` | `{result_len, summary?}` | Worker/human completion; `summary` first-line, 400-char cap; synthesizes a zero-duration run if never-claimed |
| `blocked` | `{reason, kind, recurrences}` | Flip to blocked; `kind` ∈ `needs_input`/`capability`/`transient`/`null`; synthesizes zero-duration run if never-claimed |
| `dependency_wait` | `{reason, kind}` | `kind=dependency` block → routes to `todo`, no human needed |
| `block_loop_detected` | `{reason, kind, recurrences, limit}` | Same-reason re-block `BLOCK_RECURRENCE_LIMIT` (default 2) times → routes to `triage` |
| `unblocked` | — | `blocked → ready` or `todo`; resets `consecutive_failures`, preserves `block_recurrences`; `run_id` NULL |
| `archived` | — | Hidden from board; carries reclaimed run's `run_id` if it was running |

**Edits cluster:**

| Kind | Payload | When |
|---|---|---|
| `assigned` | `{assignee}` | Assignee changed (incl. unassignment) |
| `edited` | `{fields}` | Title/body updated |
| `reprioritized` | `{priority}` | Priority changed |
| `status` | `{status}` | Dashboard drag-drop direct status write |

**Worker telemetry cluster:**

| Kind | Payload | When |
|---|---|---|
| `spawned` | `{pid}` | Worker process started |
| `heartbeat` | `{note?}` | `kanban_heartbeat` called |
| `reclaimed` | `{stale_lock}` | Claim TTL expired without completion |
| `crashed` | `{pid, claimer}` | Worker PID gone, TTL not yet expired |
| `timed_out` | `{pid, elapsed_seconds, limit_seconds, sigkill}` | `max_runtime_seconds` exceeded; SIGTERM then SIGKILL after 5s grace |
| `stale` | `{elapsed_seconds, last_heartbeat_at, heartbeat_age_seconds, timeout_seconds, pid, terminated}` | Ran past `dispatch_stale_timeout_seconds` (default 4h) with no heartbeat in last hour; does NOT tick failure counter |
| `reconciled` | `{reason, claim_lock, claim_expires, worker_pid}` | Orphaned claim bookkeeping with no live worker; gated by `kanban.reconcile_orphans` (default `true`) |
| `respawn_guarded` | `{reason}` | Reasons: `blocker_auth`, `recent_success`, `active_pr`; stays `ready` |
| `spawn_failed` | `{error, failures}` | One spawn attempt failed; counter increments, returns to `ready` |
| `protocol_violation` | `{pid, claimer, exit_code, protocol_violation}` | Clean exit while still `running`; bounded retry up to `_PROTOCOL_VIOLATION_FAILURE_LIMIT` (default 3) |
| `gave_up` | `{failures, effective_limit, limit_source, error}` | Circuit breaker fired; resolution order: task `max_retries` → dispatcher `failure_limit`/`kanban.failure_limit` → built-in default |

### 5.8 REST surface (dashboard plugin, mounted under `/api/plugins/kanban/`)

| Method | Path | Purpose |
|---|---|---|
| GET | `/board?tenant=&include_archived=…` | Full board grouped by status column + filter dropdowns |
| GET | `/tasks/:id` | Task + comments + events + links |
| POST | `/tasks` | Create |
| PATCH | `/tasks/:id` | Update status/assignee/priority/title/body/result |
| POST | `/tasks/bulk` | Bulk patch by `ids` |
| POST | `/tasks/:id/comments` | Append comment |
| POST | `/tasks/:id/specify` | Run triage specifier |
| POST | `/tasks/:id/decompose` | Run decomposer |
| GET | `/profiles` | List profiles + descriptions |
| PATCH | `/profiles/:name` | Set/clear description |
| POST | `/profiles/:name/describe-auto` | Auto-generate description |
| GET | `/orchestration` | Read orchestration settings + resolved effective values |
| PUT | `/orchestration` | Update orchestration keys |
| POST | `/links` | Add dependency |
| DELETE | `/links?parent_id=…&child_id=…` | Remove dependency |
| POST | `/dispatch?max=…&dry_run=…` | Nudge dispatcher |
| GET | `/config` | Read `dashboard.kanban` preferences |
| WS | `/events?since=<event_id>` | Live `task_events` stream |
| GET | `/workers/active` | Currently spawned workers (PID, profile, task id, started-at, last heartbeat) |
| GET | `/runs/{id}` | Single-run detail |
| POST | `/runs/{run_id}/terminate` | Terminate a reclaimable run |
| GET | `/inspect` | Combined dispatcher snapshot (backlog, in-progress vs. max, recent events) |
| DELETE | `/tasks` (body `{"ids": [...]}`) | Bulk delete |

---

## 6. Official examples (verbatim)

**Quick start** (Kanban / Quick start):

```bash
# 1. Create the board (you)
hermes kanban init
# 2. Start the gateway (hosts the embedded dispatcher)
hermes gateway start
# 3. Create a task (you — or an orchestrator agent via kanban_create)
hermes kanban create "research AI funding landscape" --assignee researcher
# 4. Watch activity live (you)
hermes kanban watch
# 5. See the board (you)
hermes kanban list
hermes kanban stats
```

**Gateway-embedded dispatcher config** (Kanban / Gateway-embedded dispatcher):

```yaml
# config.yaml
kanban:
  dispatch_in_gateway: true        # default
  dispatch_interval_seconds: 60    # default
  review_dispatch: true            # default: spawn the assigned profile with
                                    # the bundled sdlc-review skill. Set false
                                    # for human-only review boards.
```

**Idempotent create** (Kanban / Idempotent create):

```bash
# First call creates the task. Any subsequent call with the same key
# returns the existing task id instead of duplicating.
hermes kanban create "nightly ops review" \
    --assignee ops \
    --idempotency-key "nightly-ops-$(date -u +%Y-%m-%d)" \
    --json
```

**Bulk CLI verbs** (Kanban / Bulk CLI verbs):

```bash
hermes kanban complete t_abc t_def t_hij --result "batch wrap"
hermes kanban archive  t_abc t_def t_hij
hermes kanban unblock  t_abc t_def
hermes kanban block    t_abc "need input" --ids t_def t_hij
```

**Typical worker turn** (Kanban / How workers interact with the board):

```text
# Model's tool calls, in order:
kanban_show()                                     # no args — uses HERMES_KANBAN_TASK
# (model reads the returned worker_context, does the work via terminal/file tools)
kanban_heartbeat(note="halfway through — 4 of 8 files transformed")
# (more work)
kanban_complete(
    summary="migrated limiter.py to token-bucket; added 14 tests, all pass",
    metadata={"changed_files": ["limiter.py", "tests/test_limiter.py"], "tests_run": 14},
)
```

**Orchestrator fan-out** (Kanban / How workers interact with the board):

```text
kanban_show()
kanban_create(
    title="research ICP funding 2024-2026",
    assignee="researcher-a",
    body="focus on seed + series A, North America, AI-adjacent",
)
# → returns {"task_id": "t_r1", ...}
kanban_create(title="research ICP funding — EU angle", assignee="researcher-b", body="…")
# → returns {"task_id": "t_r2", ...}
kanban_create(
    title="synthesize findings into launch brief",
    assignee="writer",
    parents=["t_r1", "t_r2"],                     # promotes to ready when both complete
    body="one-pager, 300 words, neutral tone",
)
kanban_complete(summary="decomposed into 2 research tasks + 1 writer; linked dependencies")
```

**Recommended handoff `metadata` shape** (Kanban / Recommended handoff evidence):

```json
{
  "changed_files": ["path/to/file.py"],
  "verification": ["pytest tests/hermes_cli/test_kanban_db.py -q"],
  "dependencies": ["parent task id or external issue, if any"],
  "blocked_reason": null,
  "retry_notes": "what failed before, if this was a retry",
  "residual_risk": ["what was not tested or still needs human review"]
}
```

**Skill pinning** (Kanban / Pinning extra skills to a specific task):

```text
kanban_create(
    title="translate README to Japanese",
    assignee="linguist",
    skills=["translation"],
)
```

```bash
hermes kanban create "translate README to Japanese" \
    --assignee linguist \
    --skill translation
```

**Per-task model override** (Kanban / Per-task model override):

```bash
# At creation
hermes kanban create "hard refactor" --assignee coder \
    --model claude-opus-4.6 --provider anthropic
# Or later — takes effect on the next dispatch
hermes kanban set-model t_abcd claude-opus-4.6 --provider anthropic
hermes kanban set-model t_abcd none    # clear the override
```

**Cost-split per-profile config** (Kanban / Cost strategy):

```yaml
# ~/.hermes/config.yaml (orchestrator / dispatcher profile)
model:
  default: "your-frontier-model"

# ~/.hermes/profiles/coder/config.yaml (worker profile)
model:
  default: "your-inexpensive-model"
```

**Lifecycle plugin hook** (Kanban / Lifecycle plugin hooks):

```python
def register(ctx):
    def on_blocked(task_id=None, profile_name=None, **kw):
        ctx.dispatch_tool("terminal", {"command": f"notify-send 'kanban blocked: {task_id}'"})
    ctx.register_hook("kanban_task_blocked", on_blocked)
```

**Goal-mode card creation** (Kanban / Goal-mode cards):

```bash
hermes kanban create "Translate the docs site to French" \
    --body "Acceptance: every page translated, no English left, links intact." \
    --assignee linguist \
    --goal \
    --goal-max-turns 15      # optional; default 20
```

**Canonical orchestrator turn** (Kanban / How the orchestrator behaves):

```text
# Goal from user: "draft a launch post on the ICP funding landscape"
kanban_create(title="research ICP funding, NA angle",  assignee="researcher-a", body="…")  # → t_r1
kanban_create(title="research ICP funding, EU angle",  assignee="researcher-b", body="…")  # → t_r2
kanban_create(
    title="synthesize ICP funding research into launch post draft",
    assignee="writer",
    parents=["t_r1", "t_r2"],        # promoted to 'ready' when both researchers complete
    body="one-pager, neutral tone, cite sources inline",
)                                     # → t_w1
kanban_link(parent_id="t_r1", child_id="t_followup")
kanban_complete(
    summary="decomposed into 2 parallel research tasks → 1 synthesis task; writer starts when both researchers finish",
)
```

**Board management** (Kanban / Managing boards from the CLI):

```bash
hermes kanban boards list
hermes kanban boards create atm10-server \
    --name "ATM10 Server" \
    --description "Minecraft modded server ops" \
    --icon 🎮 \
    --switch
hermes kanban --board atm10-server list
hermes kanban --board atm10-server create "Restart ATM server" --assignee ops
hermes kanban boards switch atm10-server
hermes kanban boards show
hermes kanban boards rename atm10-server "ATM10 (Prod)"
hermes kanban boards rm atm10-server
hermes kanban boards rm atm10-server --delete
```

**Scheduled task start** (Kanban / Scheduled task starts):

```bash
hermes kanban create "nightly backup audit" \
  --assignee ops --scheduled-at "2026-06-01T03:00:00Z"
```

**Kanban Swarm** (Kanban / Kanban Swarm topology helper):

```bash
hermes kanban swarm "Design a multi-region failover plan" \
  --workers researcher,architect,sre \
  --verifier reviewer --synthesizer writer
```

**`/kanban` slash command** (Kanban / `/kanban` slash command):

```text
/kanban list
/kanban show t_abcd
/kanban create "write launch post" --assignee writer --parent t_research
/kanban comment t_abcd "looks good, ship it"
/kanban unblock t_abcd
/kanban dispatch --max 3
/kanban specify t_abcd                  # flesh out a triage one-liner into a real spec
/kanban specify --all --tenant engineering  # sweep every triage task in one tenant
```

**Auto-subscribe transcript** (Kanban / Auto-subscribe on `/kanban create`):

```text
you> /kanban create "transcribe today's podcast" --assignee transcriber
bot> Created t_9fc1a3  (ready, assignee=transcriber)
     (subscribed — you'll be notified when t_9fc1a3 completes or blocks)
… ~8 minutes later …
bot> ✓ t_9fc1a3 completed by transcriber
     transcribed 42 minutes, saved to podcast/2026-05-04.md
```

**Follow-up card on a done parent** (Kanban / Handing context to follow-up cards):

```bash
# Implementation card t_impl is done. CI fails two hours later.
hermes kanban create "Fix CI failure from t_impl: test_retry flakes on 3.11" \
    --assignee coder \
    --parent t_impl \
    --body "$(cat <<'EOF'
CI run #4812 failed after t_impl merged.
Log excerpt: FAILED tests/test_retry.py::test_backoff_jitter - TimeoutError
Acceptance: tests/test_retry.py green on 3.11 and 3.12 in CI.
Use a fresh worktree/branch; do not force-push the original branch.
EOF
)"
```

**Hotspot comment convention** (Kanban / Collision hotspots in parallel campaigns):

```text
hotspot: hermes_cli/kanban_db.py — third conflicting edit to the dispatch loop this wave
```

**Multi-tenant task** (Kanban / Multi-tenant usage):

```bash
hermes kanban create "monthly report" \
    --assignee researcher \
    --tenant business-a \
    --workspace dir:~/tenants/business-a/data/
```

**Notify subscription management** (Kanban / Gateway notifications):

```bash
hermes kanban notify-subscribe t_abcd \
    --platform telegram --chat-id 12345678 --thread-id 7
hermes kanban notify-list
hermes kanban notify-unsubscribe t_abcd \
    --platform telegram --chat-id 12345678 --thread-id 7
```

**Full CLI surface listing** (Kanban / CLI command reference — verbatim fenced block, reformatted from a rendering-collapsed single line back to one command per line for readability; content is unmodified):

```text
hermes kanban init
hermes kanban create "<title>" [--body ...] [--assignee <profile>]
                                [--parent <id>]... [--tenant <name>]
                                [--workspace scratch|worktree|worktree:<path>|dir:<path>]
                                [--branch <name>]
                                [--priority N] [--triage] [--idempotency-key KEY]
                                [--max-runtime 30m|2h|1d|<seconds>]
                                [--max-retries N]
                                [--goal] [--goal-max-turns N]
                                [--skill <name>]...
                                [--json]
hermes kanban list [--mine] [--assignee P] [--status S] [--tenant T] [--archived]
        [--workflow-template-id <id>] [--current-step-key <key>]
        [--sort created|created-desc|priority|priority-desc|status|assignee|title|updated]
        [--json]
hermes kanban show <id> [--json]
hermes kanban assign <id> <profile>                    # or 'none' to unassign
hermes kanban reassign <id>... <profile>               # bulk re-assign tasks to a profile
hermes kanban edit <id> [--title ...] [--body ...]     # edit task title / body / priority in place
        [--priority N]
hermes kanban promote <id>...                          # move todo/blocked tasks to ready (recovery)
hermes kanban schedule <id> --at <ISO8601>             # set/clear a task's scheduled_at start time
hermes kanban diagnostics [--json]                     # board health snapshot (alias: diag)
hermes kanban link <parent_id> <child_id>
hermes kanban unlink <parent_id> <child_id>
hermes kanban claim <id> [--ttl SECONDS]
hermes kanban comment <id> "<text>" [--author NAME]
# Bulk verbs — accept multiple ids:
hermes kanban complete <id>... [--result "..."]
hermes kanban block <id> "<reason>" [--ids <id>...]
hermes kanban unblock <id>...
hermes kanban archive <id>...
hermes kanban request-review <id> [--summary "..."] [--metadata JSON] [--reviewer PROFILE]
hermes kanban request-changes <id> "<required changes>"               # active reviewer -> implementer
hermes kanban reopen-review  <id>... [--reason "..."]                 # changes requested: 'review' -> ready/todo
hermes kanban tail <id>                                # follow a single task's event stream
hermes kanban watch [--assignee P] [--tenant T]        # live stream ALL events to the terminal
        [--kinds completed,blocked,…] [--interval SECS]
hermes kanban heartbeat <id> [--note "..."]            # worker liveness signal for long ops
hermes kanban runs <id> [--json]                       # attempt history (one row per run)
hermes kanban assignees [--json]                       # profiles on disk + per-assignee task counts
hermes kanban dispatch [--dry-run] [--max N]           # one-shot pass
        [--failure-limit N] [--json]
hermes kanban daemon --force                           # DEPRECATED — standalone dispatcher (use `hermes gateway start` instead)
        [--failure-limit N] [--pidfile PATH] [-v]
hermes kanban stats [--json]                           # per-status + per-assignee counts
hermes kanban log <id> [--tail BYTES]                  # worker log from ~/.hermes/kanban/logs/
hermes kanban notify-subscribe <id>                    # gateway bridge hook (used by /kanban in the gateway)
        --platform <name> --chat-id <id> [--thread-id <id>] [--user-id <id>]
hermes kanban notify-list [<id>] [--json]
hermes kanban notify-unsubscribe <id>
        --platform <name> --chat-id <id> [--thread-id <id>]
hermes kanban context <id>                             # what a worker sees
hermes kanban specify [<id> | --all] [--tenant T]      # flesh out a triage-column idea
        [--author NAME] [--json]                       #   into a full spec and promote to todo
hermes kanban gc [--event-retention-days N]            # workspaces + old events + old logs
        [--log-retention-days N]
```

**Story 1 worker transcript** (Kanban tutorial / Story 1):

```python
# worker tool calls — NOT commands you run
kanban_show()
# → returns title, body, worker_context, parents, prior attempts, comments
# (worker reads worker_context, uses terminal/file tools to design the schema,
#  write migrations, run its own checks, commit — the real work happens here)
kanban_heartbeat(note="schema drafted, writing migrations now")
kanban_complete(
    summary="users(id, email, pw_hash), sessions(id, user_id, jti, expires_at); "
            "refresh tokens stored as sessions with type='refresh'",
    metadata={
        "changed_files": ["migrations/001_users.sql", "migrations/002_sessions.sql"],
        "decisions": ["bcrypt for hashing", "JWT for session tokens",
                      "7-day refresh, 15-min access"],
    },
)
```

**Story 3 full review choreography** (Kanban tutorial / Story 3):

```python
# --- Engineer: first implementation attempt ---
kanban_show()
# (write code, run tests, prepare the candidate)
kanban_request_review(
    summary="implemented reset flow; candidate is ready for review",
    metadata={"changed_files": ["auth/reset.py"], "tests_run": 8},
    reviewer="reviewer",
)
# → the same card enters review; the implementation run closes as
#   outcome='review_requested'
# --- Reviewer: request concrete changes ---
kanban_show()
# (inspect the handoff and candidate)
kanban_request_changes(
    reason="Add password-strength validation and make reset tokens single-use.")
# → the review run closes as outcome='changes_requested'; the card returns
#   to backend-dev in ready/todo without touching block-loop accounting
# --- Engineer: second implementation attempt ---
kanban_show()  # prior review evidence is in worker_context
# (apply feedback and re-run tests)
kanban_request_review(
    summary="added zxcvbn validation and single-use reset tokens",
    metadata={
        "changed_files": [
            "auth/reset.py",
            "auth/tests/test_reset.py",
            "migrations/003_single_use_reset_tokens.sql",
        ],
        "tests_run": 11,
        "review_iteration": 2,
    },
    reviewer="reviewer",
)
# --- Reviewer: approve ---
kanban_complete(summary="review passed; acceptance criteria verified")
# → done
```

**Story 4 circuit-breaker example** (Kanban tutorial / Story 4):

```bash
hermes kanban create "Deploy to staging (missing creds)" \
    --assignee deploy-bot --tenant ops \
    --max-retries 3
```

```bash
hermes kanban runs t_ef5d
#  #   OUTCOME        PROFILE        ELAPSED  STARTED
#  1   spawn_failed   deploy-bot          0s  2026-04-27 19:34
#        ! AWS_ACCESS_KEY_ID not set in deploy-bot env
#  2   spawn_failed   deploy-bot          0s  2026-04-27 19:34
#        ! AWS_ACCESS_KEY_ID not set in deploy-bot env
#  3   gave_up        deploy-bot          0s  2026-04-27 19:34
#        ! AWS_ACCESS_KEY_ID not set in deploy-bot env
```

**Story 1 terminal inspection** (Kanban tutorial / Story 1):

```bash
hermes kanban show $SCHEMA
hermes kanban runs $SCHEMA
# #  OUTCOME       PROFILE       ELAPSED  STARTED
# 1  completed     backend-dev        0s  2026-04-27 19:34
#     → users(id, email, pw_hash), sessions(id, user_id, jti, expires_at); refresh tokens ...
```

---

## 7. Recommendations found (docs' own "recommendation" / "best practice" language)

- "For engineering and review tasks, **prefer this optional metadata shape**: [`changed_files`, `verification`, `dependencies`, `blocked_reason`, `retry_notes`, `residual_risk`]. These keys are a convention, not a schema requirement." — Kanban / Recommended handoff evidence.
- "Keep secrets, raw logs, tokens, OAuth material, and unrelated transcripts out of `metadata`. Store pointers and summaries instead." — Kanban / Recommended handoff evidence.
- "If your work may run longer than 1 hour, call `kanban_heartbeat` at least once an hour" — Kanban / The worker lifecycle.
- "Run your orchestrator/dispatcher profile on a frontier model and point worker profiles at inexpensive models." — Kanban / Cost strategy.
- "For the occasional quality-sensitive card, pin just that task back to a stronger model with the per-task model override... no profile edits needed." — Kanban / Cost strategy.
- "Use it [`--goal`] for open-ended, multi-step, or 'keep going until X is true' cards. Skip it for cheap one-shot work — the per-turn judge overhead isn't worth it... The judge is only as good as your goal text, so write the body as explicit acceptance criteria." — Kanban / Goal-mode cards.
- "Decide before you fan out. Design decisions belong to the orchestrator, not to the workers... the orchestrator decides it once and stamps the decision into both card bodies." — Kanban / How the orchestrator behaves.
- "For best results, pair it [the orchestrator] with a profile whose toolsets are restricted to board operations (`kanban`, `gateway`, `memory`) so the orchestrator literally cannot execute implementation tasks even if it tries." — Kanban / How the orchestrator behaves.
- "Don't let either worker self-adjudicate — the colliding agent lacks its peer's context and reliably overwrites the other side or abandons its own. Instead, create a reconciliation card assigned to a third, neutral profile with both conflicted cards linked as parents." — Kanban / Reconciling colliding worker branches.
- "A worker that notices its diff keeps colliding with siblings in one file... should not silently pile on. Instead it leaves a comment on its own card with a recognizable prefix... Orchestrators (or humans reviewing the board) who see two or more `hotspot:` comments naming the same path should create a dedicated refactor/decomposition card for that file before queuing more work that touches it — splitting the magnet file is cheaper than reconciling every future collision it would cause." — Kanban / Collision hotspots in parallel campaigns.
- "This is why the pattern for follow-up work on a finished card is a new child card, not reopening the done card." — Kanban / Handing context to follow-up cards.
- "Prefer a fresh worktree/branch for the remediation card. Checking out the original branch gives the worker repo state but none of the rationale." — Kanban tutorial / Follow-up on a done card.
- "`kanban_block` is reserved for a real external escalation (missing access, a product decision, unavailable infrastructure), not normal review feedback." — Kanban tutorial / Story 3.
- "Don't run `hermes dashboard --host 0.0.0.0`... on a shared host." (paraphrase-adjacent to a direct warning; direct quote already given in §4) — Kanban / Security model.
- "If you run workers on a remote backend (Docker, Modal), mount the board's `attachments/` directory into the sandbox so the absolute paths in the worker context are reachable." — Kanban / File attachments (Remote terminal backends callout).
- "To keep an unblocked task in the work pool, resolve why it keeps re-blocking (unfinished parent, missing input, unmet capability) before unblocking, or raise `BLOCK_RECURRENCE_LIMIT` if the loop is expected." — Kanban / Bulk CLI verbs.

---

## 8. Boundary notes (content belonging to sibling `hermes-*` skills)

- General event-hook mechanics (hook discovery paths, `HOOK.yaml` manifest format, the full Gateway Hook Events table) → `hermes-hooks`. In scope here only: the three kanban-specific hook names and their firing-process split.
- Skill installation/authoring/registry mechanics (`/skills`, Skills Hub, `hermes skills list`) → `hermes-skills`. In scope here only: the `--skill`/`skills=[...]` task-pinning mechanic and its "no runtime install" constraint.
- Session persistence, `/sessions`, `/resume`, checkpoint/rollback mechanics → `hermes-sessions`. Not touched by this capture; `task_runs`/`task_events` are a separate durability model from chat sessions, not documented as sharing storage.
- `config.yaml` key *schema*, provider/model block wiring, `auxiliary.*` provider/model resolution mechanics in general → `hermes-configuration`. In scope here only: what the dispatcher *does* with kanban-specific keys (behavior), per the assignment's explicit carve-out.
- Admin-tier config/secret pins, managed-scope precedence → `hermes-managed-scope`. Not touched; no kanban-specific managed-scope interaction was found in any page read.
- The full `hermes` CLI command surface (all non-kanban subcommands) and the full slash-command registry → `hermes-cli`. This capture only pulled the `hermes kanban`/`/kanban` rows from those reference pages.
- `delegate_task` mechanics themselves (RPC shape, `delegation.model` global pin, subagent lifecycle) → out of this skill's scope; only the explicit Kanban-vs-`delegate_task` comparison table (which lives on the primary kanban page itself) was captured.
- `/goal` slash command and Persistent Goals mechanics for ordinary chat sessions → out of this skill's scope; only the kanban-specific `--goal` card behavior (which explicitly shares-but-doesn't-connect-to that engine) was captured.
- General dashboard plugin architecture ("Extending the Dashboard," Plugin SDK, shell/page-scoped slots) → likely a dashboard/plugin-system skill if one exists; not chased here beyond the kanban plugin's own REST/security/config specifics.
- Git worktree feature mechanics in general → not this skill's scope beyond the `worktree:` workspace-kind behavior already captured.

---

## 9. Gaps & open questions

- **`docs/hermes-kanban-v1-spec.pdf` is unreachable** with the allowed tool set (binary PDF; `WebFetch` explicitly refuses binary content; not a docs-site page reachable by domain-restricted search). This file is cited by the primary doc page as the source of: the full architecture write-up, the concurrency-correctness proof, the comparative analysis against Cline Kanban / Paperclip / NanoClaw / Google Gemini Enterprise, and "the eight canonical collaboration patterns" in full worked-example form (the docs page itself only gives a compact 9-row pattern table, P1–P9, as a summary). **None of that content is in this dossier.**
- **Is `scheduled` an actual distinct task status, or is the CLI-reference wording loose?** The primary Kanban page's canonical state enum (Core concepts) is `triage | todo | ready | running | blocked | review | done | archived` — eight values, no `scheduled`. But the CLI Commands reference page's action table describes `hermes kanban schedule` as parking "time-delay/follow-up work in `scheduled`," and the primary page's own "Scheduled task starts (`scheduled_at`)" section instead describes `scheduled_at` as a *column* the dispatcher checks on an otherwise-`ready` task ("The dispatcher skips ready tasks whose `scheduled_at` is in the future"), never naming a `scheduled` status value. **Neither page resolves this directly** — it is left as an unquoted discrepancy for the reviewer, not resolved by inference here.
- **Are `BLOCK_RECURRENCE_LIMIT` and `_PROTOCOL_VIOLATION_FAILURE_LIMIT` configurable via `config.yaml`, and if so under what dotted key names?** Both are referred to only by their apparent internal constant names on the primary page (one with a leading underscore, suggesting private/internal). The page says "raise `BLOCK_RECURRENCE_LIMIT` if the loop is expected" without stating how to raise it (env var? config key? code change?). **Undocumented** on every page read.
- **Minor cross-page tool-availability inconsistency**: the primary Kanban page's own prose ("How workers interact with the board") marks only `kanban_list`, `kanban_create`, `kanban_link`, `kanban_unblock`, and `kanban_comment`-on-foreign-tasks as "(Orchestrators)" within one unified 13-tool table available to all dispatcher-spawned workers; the separate CLI Commands reference page instead states plain workers get a 9-tool baseline (omitting `kanban_list`, `kanban_unblock`, `kanban_attach`, `kanban_attach_url`, `kanban_attachments`) and "orchestrator profiles also get `kanban_list` and `kanban_unblock`" as if only those two are orchestrator-exclusive. The two pages do not fully agree on exactly which tools are baseline-vs-orchestrator-gated. Not resolved here.
- **No default literal is given for `dashboard.kanban.default_tenant`, `--priority`, `--ttl`, `--tail`, or the two `gc` retention-day flags.** Marked `undocumented` in the reference tables above rather than guessed.
- **No documented interaction between Cron and Kanban beyond the shared synchronous-fallback behavior.** The assignment's "headless/cron dispatch contexts" scope item is answered mostly by the *gateway-embedded dispatcher* material (headless = no running gateway ⇒ no dispatch; the deprecated standalone `daemon --force` escape hatch for "headless host policy forbids long-lived services"), not by any cron-specific kanban integration — no page documents cron jobs creating, querying, or completing kanban tasks, and no page documents the `chronos` cron provider having any kanban awareness.
- **Gateway Internals' "Background Maintenance" list does not mention a kanban dispatch tick** even though the primary Kanban page states the dispatcher runs inside the gateway process by default. This is most likely a documentation-completeness gap on the Gateway Internals page rather than a functional discrepancy (the Kanban page's claim is stated far more explicitly and repeatedly), but it was not independently corroborated from the gateway-internals side.
- **No standalone "Kanban Config Reference" or "Kanban CLI Reference" page exists** as a separate URL — everything is embedded in the one long feature page plus the tutorial. This is worth knowing for future runs: `llms.txt`'s Automation section lists only "Kanban Multi-Agent" and "Kanban Tutorial," no third kanban-only reference page.
- **`hermes profile describe --auto` / `--text` flag details** were only found in prose on the Profiles page (not the dedicated `/docs/reference/profile-commands` page, which was deprioritized and not fetched) — a full flag-by-flag reference for `hermes profile describe` was not captured and may exist there.
- **No documented maximum for `--max-runtime`**, nor a stated default when the flag is omitted entirely (the `timed_out` event implies a `max_runtime_seconds` value always exists at dispatch time, but no default literal is given on any page read).

---

## 10. Suggested SKILL.md inputs (for the reviewer — not an edit)

**Key concepts** (each citing the table row / quote it derives from):

- Define the 8 canonical task states and the dependency-promotion rule as the skill's core mental model — derives from §4 row 1–2 ("Task — a row with... status (`triage|todo|ready|running|blocked|review|done|archived`)"; "Link... dispatcher promotes `todo → ready` when all parents are `done`") and §5.1.
- Teach the task-vs-run distinction explicitly before discussing retries/stuck-task handling — derives from §4 ("A task is a logical unit of work; a run is one attempt to execute it...") and §5.1's run-outcome list.
- Teach the three-tier retry/circuit-breaker resolution order (task `max_retries` → `kanban.failure_limit` → built-in default) as a single mental model spanning both the general spawn-failure circuit breaker and the protocol-violation-specific budget — derives from §4 (`gave_up` row) and §5.2 (`failure_limit`, `_PROTOCOL_VIOLATION_FAILURE_LIMIT` rows).
- Teach the stale-vs-crashed-vs-reconciled distinction as three separate, fault-attribution-aware recovery paths (stale = no failure-counter tick; crashed = PID-gone detection; reconciled = broken-claim-bookkeeping orphan recovery) — derives from §5.7 event table (`stale`, `crashed`, `reconciled` rows).
- Teach "workers cannot see sibling cards; the orchestrator must stamp shared decisions into every child body" as a hard design rule for any stage-080 fan-out task design — derives from §4 ("Workers cannot see sibling cards, so every child card body must carry every decision it depends on.").
- Teach the parent-link-as-context-channel model (not just a scheduling gate) as the primary mechanism for cross-task handoff — derives from §4 (`build_worker_context` "Parent task results" quote) and §6 (worked follow-up-card example).
- Teach headless dispatch explicitly: no running gateway ⇒ `ready` tasks simply wait; the standalone `daemon --force` path is a deprecated one-release-cycle escape hatch, never run alongside the gateway dispatcher — derives from §4 ("Without a running gateway, `ready` tasks stay where they are..."; "running both... is not supported").

**Workflow steps** (each citing its source):

1. Read the official Kanban page and Kanban tutorial before designing any dispatcher/worker-facing behavior — derives from the recommended pins in §2.
2. Model task bodies and completion metadata against the documented convention (`changed_files`, `verification`, `dependencies`, `blocked_reason`, `retry_notes`, `residual_risk`) rather than inventing a new shape — derives from §6 (Recommended handoff evidence JSON) and §7 (first bullet).
3. When designing stuck/retry handling, cite the specific event kind (`stale`, `crashed`, `gave_up`, `respawn_guarded`, `protocol_violation`, `reconciled`) rather than a generic "task failed" concept — derives from §5.7.
4. When designing routing/assignment, require every profile a kanban orchestrator might route to have a `--description` set, and treat unknown-assignee names as a silent-failure risk to be defended against explicitly — derives from §4 ("the dispatcher silently fails on unknown assignee names") and §3.7 (Profiles page).
5. Prefer Kanban-native dispatch over external process management (already the placeholder's stated validation rule) — reinforced by §4's headless-dispatch and daemon-deprecation quotes, which give the concrete "why."

**Validation commands** (each citing its source):

- `hermes kanban diagnostics --json` — board health snapshot; derives from §5.3 (`diagnostics` row).
- `hermes kanban runs <id> --json` — attempt-history inspection for verifying retry/circuit-breaker behavior in a design review; derives from §5.3 (`runs` row) and §6 (Story 4 example output).
- `hermes kanban dispatch --dry-run --json` — one-shot dispatcher pass without side effects, useful for validating a board's ready-queue state without waiting for the next tick; derives from §5.3 (`dispatch` row).
- `hermes kanban context <id>` — print exactly what a worker would see, for validating that a task body/parent-handoff design actually surfaces the intended information; derives from §5.3 (`context` row).
- `hermes kanban tail <id>` / `hermes kanban watch --kinds gave_up,timed_out,stale` — live event-stream validation of lifecycle/telemetry behavior during a design review or incident; derives from §5.3 (`tail`, `watch` rows) and §5.7.

---

*End of Run B capture.*

---

## Reviewer addendum (2026-08-12): the v1 design spec, recovered and read

The dossier's biggest flagged gap — `docs/hermes-kanban-v1-spec.pdf` —
was resolved by the reviewer: the PDF lives in the product repository, not
the docs site
(https://raw.githubusercontent.com/NousResearch/hermes-agent/main/docs/hermes-kanban-v1-spec.pdf,
213 KB, 32 pages, read in full). Header: "Hermes Kanban — Multi-Agent
Profile Collaboration for Hermes Agent", Hermes & Teknium, Nous Research,
April 25, 2026, "Design Spec, Revision 01", "Status: DESIGN ONLY."

**Standing rule: cite the live feature docs for behavior; cite the spec
only for design rationale.** The shipped product has evolved past the
spec on at least these points:

| Dimension | v1 spec (design) | Live docs (product) |
|---|---|---|
| Task states | 6: `todo/ready/running/blocked/done/archived` | 8: adds `triage`, `review` |
| Agent surface | "Recommend CLI + skill", no toolset ("zero schema bloat") | 13-tool `kanban_*` toolset, opt-in per profile |
| Patterns | 8 (P1–P8) | 9 (adds P9 Triage specifier) |
| Boards | single board | multi-board with slug validation |
| Runs | not modeled (events only) | first-class `task_runs`, one row per attempt |
| Review | not modeled | first-class `review` state + request-review/changes choreography |

### Spec facts worth keeping (design rationale)

- **Three-plane architecture**: control plane (user via CLI/gateway),
  state plane (SQLite `kanban.db` in WAL mode + "deliberately dumb"
  dispatcher), execution plane (pool of independent profile processes).
  "All coordination flows through the board; there is no direct
  inter-process communication between profiles."
- **The critical invariant**: "Every coordinating worker is an
  operating-system process under the user's control... When a worker
  exits — whether cleanly, by crash, or by SIGKILL during a host reboot —
  its claim lock expires and the next dispatcher tick reclaims the task.
  There is no lifecycle we do not own." (Lesson from NanoClaw's broken
  in-process SDK swarms.)
- **Concurrency correctness**: atomic claim is a compare-and-swap UPDATE
  inside BEGIN IMMEDIATE — `WHERE id = ? AND status = 'ready' AND
  claim_lock IS NULL`; "at most one claimer can win any given task.
  Losers simply observe zero affected rows and move on." Original claim
  TTL: `claim_expires = now + 900` (15 min); live docs supersede with the
  richer TTL/heartbeat/stale model.
- **Status ownership** (spec table): creator owns `todo`, dispatcher owns
  `ready→running`, workers own `running→done|blocked`, humans/peers own
  `blocked→ready`, user owns `archived`. "Only one role may transition
  each status; this separation eliminates write contention."
- **Kanban vs. delegate_task, the single test**: "Does this handoff need
  to outlive a single API loop and be visible to others? If yes, board.
  If no, delegate." delegate_task is a synchronous fork-and-join call;
  kanban is "a durable work queue where every handoff is a row any
  profile (or human) can read and edit." They coexist — a kanban worker
  may call delegate_task internally.
- **Assignment semantics — deliberately NOT supported in v1**: two
  assignees per task ("causes claim races; muddies accountability"),
  round-robin pools, auto-assignment/open queues, broadcast ("if N copies
  are desired, create N tasks"). Worker's complete context = title, body,
  comments chronologically, parent completion results, profile
  skills/memory: "If it is not visible on `hermes kanban show <id>`, the
  worker cannot see it either."
- **Orchestrator profile design**: disabled execution toolsets
  (`toolsets: [kanban, gateway, memory]`, no terminal/file/web/browser/
  code) so it "literally cannot do implementation work"; prescriptive
  skill ("You are a dispatcher, not a worker"); standard roster
  convention. "The dispatcher does not know or care that a profile is
  called 'orchestrator.' The board has no role field."
- **Scope boundaries (kernel stays small)**: smart routing → a `router`
  profile; org charts → naming conventions; budgets → a spawn-wrapping
  plugin; dashboards → a plugin; approval gates → existing approval
  infrastructure; governance control plane → "user-space profiles and
  plugins where they cannot take down the coordination fabric."
- **Risks the spec pre-registered** (all now visible as shipped
  mechanisms in the live docs): SQLite contention → WAL + BEGIN
  IMMEDIATE; stale workspaces → `gc`; profile misconfiguration at spawn →
  verify on assign; cron drift on sleep/wake → mini-dispatch on every CLI
  invocation; runaway automation chains → approval-gated `ready`
  transition.

### Discrepancy resolutions (reviewer verdicts)

1. **`scheduled` status**: NOT a status. Live enum is 8 values; the
   primary page confirms the dispatcher "skips ready tasks whose
   `scheduled_at` is in the future and picks them up on the first tick
   after that timestamp" — verified 2026-08-12, tasks remain `ready`. The
   CLI reference's "park ... in `scheduled`" is loose wording. (The spec's
   6-state model confirms `scheduled` was never a designed state either.)
2. **Tool gating (primary page vs CLI reference)**: unresolved in docs.
   The primary feature page's 13-tool table with "(Orchestrators)"
   markings is the richer, more recently maintained authority; the CLI
   reference's 9-tool baseline phrasing should not be cited alone. Left
   open in `source-capture.md`.

---

## Addendum 2 (reviewer, 2026-08-12): full-page coverage audit, tutorial fold-in, worker lanes

### Coverage audit

Complete heading outline of the live feature page (52 headings) diffed
against the dossier's page map: identical — no new sections since
capture. The kanban-tutorial page was already read in full by the
original run (§3.2; its story transcripts are in §6). SKILL.md upgraded
to v1.1.0 as a systematically thorough distillation covering every
feature-page section plus tutorial-grounded review choreography.

### Verbatim additions (sections previously captured in outline only)

Collaboration patterns P1–P9 (full table): P1 Fan-out (N siblings, same
role); P2 Pipeline (scout → editor → writer); P3 Voting/quorum (N
siblings + 1 aggregator); P4 Long-running journal (same profile + shared
dir + cron); P5 Human-in-the-loop (block → comment → unblock); P6
@mention (inline routing from prose); P7 Thread-scoped workspace
(`/kanban here`); P8 Fleet farming (one profile, N subjects); P9 Triage
specifier (idea → `triage` → `specify` → `todo`).

File attachments: 25 MB/file; storage
`~/.hermes/kanban/attachments/<task_id>/`; workers receive absolute paths
in context; Docker/Modal backends must mount the attachments directory.

Gateway notifications: `/kanban create` auto-subscribes the creating chat
to terminal events (`completed`, `blocked`, `gave_up`, `crashed`,
`timed_out`); completed also delivers the result's first line;
multi-profile delivery is profile-owned with "atomic per-event claiming
in the database prevents duplicate delivery".

### NEW PAGE captured: Kanban worker lanes
(`/docs/user-guide/features/kanban-worker-lanes` — absent from the
original capture's inventory and from `/docs/llms.txt`; discovered via
maintainer pointer 2026-08-12)

- QUOTE: "A worker lane is a class of process that the kanban dispatcher
  can route tasks to. Each lane has an identity (the assignee string), a
  spawn mechanism, and a contract for what it must do with the task once
  spawned."
- Spawn env (default Hermes-profile lane): HERMES_KANBAN_TASK, _DB,
  _BOARD, _WORKSPACES_ROOT, _WORKSPACE, _RUN_ID, _CLAIM_LOCK,
  HERMES_PROFILE, HERMES_TENANT. (Three of these — _WORKSPACE, _RUN_ID,
  _CLAIM_LOCK — were not in the env-vars reference capture.)
- Unresolvable assignees stay `ready` with a `skipped_nonspawnable` event
  (a 23rd event kind, beyond the feature page's 22-kind reference).
- Lifecycle terminators: exactly one of kanban_complete /
  kanban_request_review / kanban_block; clean exit without one is the
  protocol_violation path.
- `DEFAULT_CLAIM_TTL_SECONDS` = 15 min (corroborates the v1 spec's
  `claim_expires = now + 900`); `kanban.stranded_threshold_seconds`
  (~30 min) feeds `hermes kanban diagnostics` stranded-task detection.
- Lane-author constraints: no secrets/tokens/raw PII in summary/metadata
  (audit-durable); same-card review and pre-created downstream review are
  mutually exclusive; orchestrator profiles must exclude
  terminal/file/code/web; "external CLI lane integration is not yet a
  paved path".
