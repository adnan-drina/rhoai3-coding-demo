# Official Doc Extraction — hermes-about

Validated research dossier (capture date 2026-08-12). Reviewer validation:
the llms.txt positioning paragraph, the three platform-tier definition
sentences, the Docker no-in-place-update note, and the Goals-vs-Kanban
quotes were re-verified verbatim against live sources on 2026-08-12; the
feature inventory was cross-mapped against the seven implemented sibling
skills. Original dossier:
`source-analysis/hermes/hermes-about-capture.md`.

---

# hermes-about — Documentation Research Dossier

## Executive summary (read this first)

- **Captured:** Product positioning (llms.txt tagline, user-stories taxonomy), the getting-started shape (install → provider → first chat → verify sessions → key features → next layer), the four-surface interface model (CLI / TUI / Desktop App / Web Dashboard), the three-tier platform-support matrix, the full official feature inventory (~45 named features across Core/Automation/Media & Web/Integrations/Customization), and **ten** exact "use X when / use Y when" mechanism-selection comparisons pulled verbatim from seven different pages.
- **Confidence:** High for feature inventory, platform matrix, and install/getting-started shape (all read from primary pages, several fetched twice via independent tool paths). Medium for "who it's for" positioning, since the only page that speaks to audience/use-cases (`/docs/user-stories`) is Nous-curated but the individual quotes on it originate from third-party social posts — I've flagged every such quote as community-voice-on-an-official-page, not a Nous positioning claim.
- **Biggest gap:** There is no single page that states Hermes's positioning/tagline as prose on a "concepts" or "about" page — the closest things are the `llms.txt` one-paragraph description (official, machine-readable index, high confidence) and a curated community quote ("Hermes is the general agent, not a coding/research/automation agent") that is explicitly third-party. There is also no discrete "product version" — Hermes ships as a rolling `main`-branch checkout with git-tag releases (e.g. `v2026.5.16` used only as a rollback example), so "current version" is operationally defined as `hermes version` compared against the GitHub releases page, not a fixed number this dossier can pin.
- **Contradicts current placeholder:** Nothing contradicts `hermes-about`'s current `SKILL.md`/`source-capture.md`, but the current pins are incomplete — they cover 3 of the roughly 15+ pages this topic actually needs (see Recommended source pins below).
- **Suggested next skill to research:** `hermes-skills` and `hermes-hooks` already have captures per `AGENTS.md`; of the remaining orientation-adjacent gaps, `hermes-configuration`/`hermes-managed-scope` already have captures too. The clearest next gap this run surfaced is a dedicated capture for **Sessions** (`/docs/user-guide/sessions`) and **MCP** (`/docs/user-guide/features/mcp`) — both are referenced constantly by other features (kanban, delegation, memory, plugins) but I only skimmed them for this orientation pass and they deserve their own depth pass if no sibling skill already owns them.

---

## 1. Capture header

- **Product:** Hermes Agent (Nous Research)
- **Product version:** No version marker on any page read. The docs describe version-checking as a *procedure*, not a fixed number: `hermes version` / `hermes --version`, compared against "the latest release at the GitHub releases page" (source: `/docs/getting-started/updating`, section "Checking your current version"). `hermes update` tracks `origin/main` by default; rollback examples reference a tag format like `v2026.5.16` but this is illustrative, not a claim about the current release.
- **Capture date:** 2026-08-12
- **Capture method:** Live fetches against `https://hermes-agent.nousresearch.com` (WebFetch tool) plus domain-restricted web search (WebSearch tool) used only to locate page URLs not linked from `llms.txt`, per the assignment's practical notes. No repository source was read (not needed — no gap required it).

### Page inventory (from `/docs/llms.txt`, the curated site index)

**Read in full or substantially (primary evidence for this dossier):**

| Page | URL | Why read |
|---|---|---|
| Hermes Agent (llms.txt root description) | `/docs/llms.txt` | Official one-paragraph positioning + full nav index |
| User Stories & Use Cases | `/docs/user-stories` | "who it's for" / use-case breadth |
| Quickstart | `/docs/getting-started/quickstart` | getting-started shape, provider table |
| Installation | `/docs/getting-started/installation` | install-surface detail, prerequisites |
| Platform Support | `/docs/getting-started/platform-support` | Tier 1/Tier 2/Unsupported matrix (the "Platform Support" lead) |
| Learning Path | `/docs/getting-started/learning-path` | orientation-by-experience-level and by-use-case routing |
| Updating & Uninstalling | `/docs/getting-started/updating` | versioning/release mechanics |
| Nix & NixOS Setup | `/docs/getting-started/nix-setup` | Nix install surface, Tier 2 |
| Android / Termux | `/docs/getting-started/termux` | Termux install surface, Tier 2 |
| Features Overview | `/docs/user-guide/features/overview` | canonical feature inventory (5 categories) |
| Skills System | `/docs/user-guide/features/skills` | skill mechanism, "when bundles beat individual skills" |
| Persistent Memory | `/docs/user-guide/features/memory` | memory mechanism, session_search vs memory table |
| Subagent Delegation | `/docs/user-guide/features/delegation` | delegate_task vs execute_code table |
| Kanban (Multi-Agent Board) | `/docs/user-guide/features/kanban` | Kanban vs delegate_task table |
| Persistent Goals | `/docs/user-guide/features/goals` | Goals vs Kanban table |
| Event Hooks | `/docs/user-guide/features/hooks` | four-hook-system comparison table |
| Scheduled Tasks (Cron) | `/docs/user-guide/features/cron` | automation mechanism, model-resolution order |
| Plugins | `/docs/user-guide/features/plugins` | plugin mechanism, "pluggable interfaces — where to go for each" table |
| Personality & SOUL.md | `/docs/user-guide/features/personality` | SOUL.md vs AGENTS.md, SOUL.md vs /personality tables |
| Context Files | `/docs/user-guide/features/context-files` | AGENTS.md/CLAUDE.md/.cursorrules priority chain |
| Curator | `/docs/user-guide/features/curator` | skill-lifecycle maintenance mechanism |
| MCP (Model Context Protocol) | `/docs/user-guide/features/mcp` | skimmed — positioning paragraph + catalog mechanics |
| CLI Interface | `/docs/user-guide/cli` | skimmed — CLI surface description |
| TUI | `/docs/user-guide/tui` | modern terminal UI surface, relation to classic CLI |
| Desktop App | `/docs/user-guide/desktop` | skimmed — the "which interface is which" four-surface breakdown |
| Docker Backend | `/docs/user-guide/docker` | fetched, used lightly (terminal-backend detail, not core to orientation) |

**Located via search, read via snippet/synthesis only (flagged where used):**

| Page | URL | Note |
|---|---|---|
| Windows (Native) Guide | `/docs/user-guide/windows-native` | native-vs-WSL2 feature-parity table, read via search snippet |
| Messaging Gateway | `/docs/user-guide/messaging/` | platform-support table, read via search snippet (not a full fetch — flagged in Reference Tables) |
| Integrations Overview | `/docs/integrations/` | one-paragraph category summaries, read via search snippet |
| AI Providers | `/docs/integrations/providers` | provider list, read via search snippet |
| Fallback Providers | `/docs/user-guide/features/fallback-providers` | provider list, read via search snippet |
| Provider Routing | `/docs/user-guide/features/provider-routing` | one-paragraph description, read via search snippet |
| Web Dashboard | `/docs/user-guide/features/web-dashboard` | one-paragraph description, read via search snippet |

**Deprioritized (in scope per llms.txt, out of scope for THIS skill's breadth-not-depth mandate — owned by sibling skills or clearly a depth topic):**

| Page | Reason deprioritized |
|---|---|
| Configuration, Configuring Models, Profiles | Owned by `hermes-configuration` per AGENTS.md skill map |
| Sessions | Owned by depth topic (`hermes-sessions` capture already exists per repo state — see Suggested next skill) |
| Security | Owned by `hermes-managed-scope` (admin pins/secrets/security posture — explicit boundary in this skill's own `SKILL.md`) |
| Checkpoints & Rollback | Feature-specific depth, one-line mention in Features Overview suffices for orientation |
| Git Worktrees | Feature-specific depth, tangential to "about" |
| Voice Mode, Wake Word, Browser, Vision, Image Generation, Text-to-Speech | Media & Web features — one-line descriptions already captured from Features Overview; deep dives are sibling-skill territory if any exists |
| All 15 messaging-platform-specific pages (Telegram, Discord, Slack, WhatsApp, Signal, Email, SMS, Matrix, Mattermost, Home Assistant, Webhooks, etc.) | One gateway concept, many nearly-identical setup pages; captured only the overview table |
| Batch Processing, Credential Pools, Honcho Memory, Memory Providers | One-line descriptions captured from Features Overview; each is a deep integration topic |
| ACP, API Server | One-line descriptions captured from Features Overview and llms.txt; not expanded |
| All Guides & Tutorials pages (Tips, Local LLMs on Mac, Daily Briefing Bot, Team Telegram Assistant, Python Library, Use MCP, Use Voice Mode, Use SOUL.md, Build a Plugin, Automate with Cron, Work with Skills, Delegation Patterns, GitHub PR Review Agent) | Tutorials/how-tos, not conceptual inventory — the "By Use Case" table in Learning Path already indexes these |
| All Developer Guide pages (Contributing, Architecture, Agent Loop, Prompt Assembly, Context Compression, Gateway Internals, Session Storage, Provider Runtime, Adding Tools, Adding Providers, Adding Platform Adapters, Creating Skills, Extending the CLI) | Internals/contributor depth, explicitly out of scope for a user-facing orientation skill |
| All Reference pages (CLI Commands, Slash Commands, Profile Commands, Environment Variables, Tools Reference, Toolsets Reference, MCP Config Reference, Model Catalog, Skills Catalogs, FAQ) | Exhaustive reference tables — belongs to `hermes-cli` (which already has a capture) or a future `hermes-tools`/`hermes-mcp` skill, not to orientation |

**Dead links / redirects:** None encountered. `https://hermes-agent.nousresearch.com/docs/integrations/index` (a guessed URL) 404'd; the correct URL is `/docs/integrations/` (no `index` segment) — recorded as a practical note for future runs.

---

## 2. Recommended source pins

The current `references/source-capture.md` pins only 3 URLs (`user-stories`, `quickstart`, `features/overview`). Given this skill's actual scope (product positioning + full mechanism-selection map + install surfaces + versioning), I recommend expanding the pin list to:

**Positioning / getting started:**
- `https://hermes-agent.nousresearch.com/docs/llms.txt` (canonical feature/page index — cite for the one-paragraph tagline)
- `https://hermes-agent.nousresearch.com/docs/user-stories`
- `https://hermes-agent.nousresearch.com/docs/getting-started/quickstart`
- `https://hermes-agent.nousresearch.com/docs/getting-started/learning-path`
- `https://hermes-agent.nousresearch.com/docs/getting-started/updating` (versioning procedure)

**Install surfaces / platform support:**
- `https://hermes-agent.nousresearch.com/docs/getting-started/installation`
- `https://hermes-agent.nousresearch.com/docs/getting-started/platform-support`
- `https://hermes-agent.nousresearch.com/docs/getting-started/nix-setup`
- `https://hermes-agent.nousresearch.com/docs/getting-started/termux`
- `https://hermes-agent.nousresearch.com/docs/user-guide/desktop` (the four-surface "which interface is which" statement)
- `https://hermes-agent.nousresearch.com/docs/user-guide/tui`
- `https://hermes-agent.nousresearch.com/docs/user-guide/cli`

**Feature inventory / mechanism selection (the core of this skill):**
- `https://hermes-agent.nousresearch.com/docs/user-guide/features/overview` (already pinned — keep)
- `https://hermes-agent.nousresearch.com/docs/user-guide/features/skills`
- `https://hermes-agent.nousresearch.com/docs/user-guide/features/memory`
- `https://hermes-agent.nousresearch.com/docs/user-guide/features/delegation`
- `https://hermes-agent.nousresearch.com/docs/user-guide/features/kanban`
- `https://hermes-agent.nousresearch.com/docs/user-guide/features/goals`
- `https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks`
- `https://hermes-agent.nousresearch.com/docs/user-guide/features/cron`
- `https://hermes-agent.nousresearch.com/docs/user-guide/features/plugins`
- `https://hermes-agent.nousresearch.com/docs/user-guide/features/personality`
- `https://hermes-agent.nousresearch.com/docs/user-guide/features/context-files`

**Flag:** none of the current 3 pins "proved irrelevant" — all three remain load-bearing. They are just insufficient alone for the mechanism-selection and platform-support duties this skill's own description commits to ("choosing which Hermes mechanism fits a stage 080 harness need").

---

## 3. Page maps (heading outlines for the highest-value pages)

**`/docs/llms.txt`** — flat one-paragraph description, then `## Getting Started`, `## Using Hermes`, `## Core Features`, `## Automation`, `## Media & Web`, `## Messaging Platforms`, `## Integrations`, `## Guides & Tutorials`, `## Developer Guide`, `## Reference`. Each line is `[Page Title](url): one-line description` — this structure alone is a ready-made "capability inventory" source.

**`/docs/getting-started/quickstart`** — Prefer to watch? → Who this is for → The fastest path (table) → 1. Install → 2. Choose a Provider (setup modes: Quick/Full/Blank Slate; provider table; "How settings are stored") → 3. Run Your First Chat → 4. Verify Sessions Work → 5. Try Key Features (terminal, slash commands, multi-line input, interrupt) → 6. Add the Next Layer (bot/shared assistant, automation, sandboxed terminal, voice, skills, MCP, ACP) → Common Failure Modes → Recovery Toolkit → Quick Reference → Next Steps.

**`/docs/getting-started/platform-support`** — Tier 1 (table) → Tier 2 (table) → Unsupported (list).

**`/docs/user-guide/features/overview`** — Core (6 items) → Automation (5 items) → Media & Web (6 items) → Integrations (9 items) → Customization (3 items). Every bullet is `**Name**— one-line description.`

**`/docs/user-guide/features/memory`** — How It Works → How Memory Appears in the System Prompt → Memory Tool Actions → Two Targets Explained → What to Save vs Skip → Capacity Management → Duplicate Prevention → Security Scanning → Session Search (with `### session_search vs memory` comparison table) → Learning Journey → Configuration → write_approval → background review notifications → running review on cheaper model → skill write_approval → External Memory Providers.

**`/docs/user-guide/features/kanban`** — intro → "Two surfaces" → **`## Kanban vs. delegate_task`** (the comparison table) → Core concepts → Boards → File attachments → Quick start → How workers interact → Collaboration patterns (8 named patterns, P1–P9) → Handing context to follow-up cards → Multi-tenant usage → Gateway notifications → Runs → Event reference → Out of scope → Design spec.

**`/docs/user-guide/features/delegation`** — Single Task → Parallel Batch → How Subagent Context Works → Practical Examples → Batch Mode Details → Model Override (cost strategy) → Inherited Tool Access → Max Iterations → Child Timeout → Stall Detection → Monitoring (`/agents`) → Steering → Live Transcripts → Depth Limit and Nested Orchestration → Lifetime and Durability → Key Properties → **`## Delegation vs execute_code`** (comparison table) → Configuration.

**`/docs/user-guide/features/goals`** — intro → When to use it → **`## Goals vs Kanban: which one do I want?`** (comparison table) → Quick start → Commands → Completion contracts → /subgoal → Quality gates → Parking on a background process → Behavior details → Configuration → Example walkthrough → When the judge gets it wrong → Attribution (explicit credit to Codex CLI's `/goal`, adapted independently).

**`/docs/user-guide/features/hooks`** — intro with **four-hook-system table** → Gateway Event Hooks (creating a hook, HOOK.yaml, handler.py, available events, wildcard matching, examples, BOOT.md tutorial) → (truncated in this read; page continues to Plugin hooks, Shell hooks, Outbound webhooks per the intro table and per the Plugins page's cross-reference).

**`/docs/user-guide/features/plugins`** — Quick overview → Minimal working example → What plugins can do (table) → Plugin discovery (table + sub-categories table) → Plugins are opt-in (allow-list mechanics, what bypasses it, migration) → Available hooks (24-hook catalog reference) → Plugin types (4 kinds) → **`## Pluggable interfaces — where to go for each`** (the master "want to add X → use Y" table) → NixOS declarative plugins → Managing plugins → Injecting Messages.

**`/docs/user-guide/features/personality`** — How SOUL.md works now → Why this design → Where to edit it → What should go in SOUL.md → Good SOUL.md content → What Hermes injects into the prompt → Security scanning → **`## SOUL.md vs AGENTS.md`** → **`## SOUL.md vs /personality`** → Built-in personalities (14-row table) → Switching personalities → Custom personalities in config → Resetting to default → Recommended workflow → How personality interacts with the full prompt (8-layer prompt stack) → Related docs → CLI appearance vs conversational personality.

**`/docs/user-guide/desktop`** — intro with **`Which interface is which?`** callout (Desktop / CLI+TUI / Web Dashboard) → Install → What's in the app (Chat, status bar, etc.) → CLI reference: `hermes desktop` → How it works → Connecting to a remote backend.

---

## 4. Reference tables

### (a) Complete official feature inventory

Source for one-line descriptions unless noted otherwise: `/docs/user-guide/features/overview` ("Features Overview"). Owning sibling skill per the AGENTS.md skill-group map and this skill's own boundary notes; "—" means no sibling `hermes-*` skill currently claims it (a taxonomy gap, flagged again in §9).

| Feature | Official one-line description (QUOTE) | Doc URL | Owning sibling |
|---|---|---|---|
| Tools & Toolsets | "Tools are functions that extend the agent's capabilities. They're organized into logical toolsets that can be enabled or disabled per platform, covering web search, terminal execution, file editing, memory, delegation, and more." | `/docs/user-guide/features/tools` | — (no `hermes-tools` skill yet) |
| Skills System | "On-demand knowledge documents the agent can load when needed. Skills follow a progressive disclosure pattern to minimize token usage and are compatible with the agentskills.io open standard." | `/docs/user-guide/features/skills` | `hermes-skills` |
| Persistent Memory | "Bounded, curated memory that persists across sessions. Hermes remembers your preferences, projects, environment, and things it has learned via `MEMORY.md` and `USER.md`." | `/docs/user-guide/features/memory` | — |
| Context Files | "Hermes automatically discovers and loads project context files (`.hermes.md`, `AGENTS.md`, `CLAUDE.md`, `SOUL.md`, `.cursorrules`) that shape how it behaves in your project." | `/docs/user-guide/features/context-files` | — |
| Context References | "Type `@` followed by a reference to inject files, folders, git diffs, and URLs directly into your messages." | `/docs/user-guide/features/context-references` | — |
| Checkpoints | "Hermes automatically snapshots your working directory before making file changes, giving you a safety net to roll back with `/rollback` if something goes wrong." | `/docs/user-guide/checkpoints-and-rollback` | — |
| Scheduled Tasks (Cron) | "Schedule tasks to run automatically with natural language or cron expressions. Jobs can attach skills, deliver results to any platform, and support pause/resume/edit operations." | `/docs/user-guide/features/cron` | — |
| Subagent Delegation | "The `delegate_task` tool spawns child agent instances with isolated context, restricted toolsets, and their own terminal sessions. Run 3 concurrent subagents by default (configurable) for parallel workstreams." | `/docs/user-guide/features/delegation` | — |
| Code Execution | "The `execute_code` tool lets the agent write Python scripts that call Hermes tools programmatically, collapsing multi-step workflows into a single LLM turn via sandboxed RPC execution." | `/docs/user-guide/features/code-execution` | — |
| Event Hooks | "Run custom code at key lifecycle points. Gateway hooks handle logging, alerts, and webhooks; plugin hooks handle tool interception, metrics, and guardrails." | `/docs/user-guide/features/hooks` | `hermes-hooks` |
| Batch Processing | "Run the Hermes agent across hundreds or thousands of prompts in parallel, generating structured ShareGPT-format trajectory data for training data generation or evaluation." | `/docs/user-guide/features/batch-processing` | — |
| Voice Mode | "Full voice interaction across CLI and messaging platforms. Talk to the agent using your microphone, hear spoken replies, and have live voice conversations in Discord voice channels." | `/docs/user-guide/features/voice-mode` | — |
| Wake Word | (feature list entry; "Hands-free 'Hey Hermes' trigger for the CLI, TUI, and desktop app.") | `/docs/user-guide/features/voice-mode` (same page grouping) | — |
| Browser Automation | "Full browser automation with multiple backends: Browserbase cloud, Browser Use cloud, local Chrome/Brave/Chromium/Edge via CDP, or local Chromium." | `/docs/user-guide/features/browser` | — |
| Vision & Image Paste | "Multimodal vision support. Paste images from your clipboard into the CLI and ask the agent to analyze, describe, or work with them using any vision-capable model." | `/docs/user-guide/features/vision` | — |
| Image Generation | "Generate images from text prompts using FAL.ai. Eleven models supported..." | `/docs/user-guide/features/image-generation` | — |
| Voice & TTS | "Text-to-speech output and voice message transcription across all messaging platforms, with ten native provider options..." | `/docs/user-guide/features/tts` | — |
| MCP Integration | "Connect to any MCP server via stdio or HTTP transport. Access external tools from GitHub, databases, file systems, and internal APIs without writing native Hermes tools. Includes per-server tool filtering and sampling support." | `/docs/user-guide/features/mcp` | — |
| Provider Routing | "Fine-grained control over which AI providers handle your requests. Optimize for cost, speed, or quality with sorting, whitelists, blacklists, and priority ordering." | `/docs/user-guide/features/provider-routing` | — |
| Fallback Providers | "Automatic failover to backup LLM providers when your primary model encounters errors, including independent fallback for auxiliary tasks like vision and compression." | `/docs/user-guide/features/fallback-providers` | — |
| Credential Pools | "Distribute API calls across multiple keys for the same provider. Automatic rotation on rate limits or failures." | `/docs/user-guide/features/credential-pools` | — |
| Prompt caching | "Built-in cross-session 1-hour prefix cache for Claude on native Anthropic, OpenRouter, and Nous Portal. Always-on; no configuration required." | (feature list entry, no dedicated URL given) | — |
| Memory Providers | "Plug in external memory backends (Honcho, OpenViking, Mem0, Hindsight, Holographic, RetainDB, ByteRover, Supermemory) for cross-session user modeling and personalization beyond the built-in memory system." | `/docs/user-guide/features/memory-providers` | — |
| API Server | "Expose Hermes as an OpenAI-compatible HTTP endpoint. Connect any frontend that speaks the OpenAI format — Open WebUI, LobeChat, LibreChat, and more." | `/docs/user-guide/features/api-server` | — |
| IDE Integration (ACP) | "Use Hermes inside ACP-compatible editors such as VS Code, Zed, and JetBrains. Chat, tool activity, file diffs, and terminal commands render inside your editor." | `/docs/user-guide/features/acp` | — |
| Personality & SOUL.md | "Fully customizable agent personality. `SOUL.md` is the primary identity file — the first thing in the system prompt — and you can swap in built-in or custom `/personality` presets per session." | `/docs/user-guide/features/personality` | — |
| Skins & Themes | "Customize the CLI's visual presentation: banner colors, spinner faces and verbs, response-box labels, branding text, and the tool activity prefix." | (feature list entry) | — |
| Plugins | "Add custom tools, hooks, and integrations without modifying core code. Three plugin types: general plugins (tools/hooks), memory providers (cross-session knowledge), and context engines (alternative context management). Managed via the unified `hermes plugins` interactive UI." | `/docs/user-guide/features/plugins` | — |
| Persistent Goals (`/goal`) | "Set a standing goal and let Hermes keep working across turns until it's done. Our take on the Ralph loop." (source: `/docs/llms.txt`) | `/docs/user-guide/features/goals` | — |
| Kanban Multi-Agent | "Durable SQLite-backed task board for coordinating multiple Hermes profiles." (source: `/docs/llms.txt`) | `/docs/user-guide/features/kanban` | `hermes-kanban` (capture exists per repo) |
| Curator | "Background maintenance for agent-created skills — usage tracking, staleness, archival, and LLM-driven review." (source: `/docs/llms.txt`) | `/docs/user-guide/features/curator` | `hermes-skills` (boundary: curator manages skill lifecycle) |
| Built-in Plugins | "Plugins shipped with Hermes Agent that run automatically via lifecycle hooks — disk-cleanup and friends." (source: `/docs/llms.txt`) | `/docs/user-guide/features/built-in-plugins` | — |
| Sessions | (feature list entry) "Session persistence, resume, search, management, and per-platform session tracking." (source: `/docs/llms.txt`) | `/docs/user-guide/sessions` | `hermes-sessions` (capture exists per repo) |
| Honcho Memory | "AI-native persistent memory via Honcho — dialectic reasoning, multi-agent user modeling, and deep personalization." (source: `/docs/llms.txt`) | `/docs/user-guide/features/honcho` | — |

*(The remaining Features-Overview bullets — Skins & Themes, Prompt caching — have no dedicated page and are recorded verbatim above; a small number of llms.txt-only entries such as Git Worktrees, Security, Batch Processing details, Delegation Patterns guide, etc. are omitted here as clearly owned by the deprioritized list in §1.)*

### (b) Platform / install-surface support matrix

Source: `/docs/getting-started/platform-support` ("Platform Support") unless noted.

**Tier 1 — "We strive to never break installations and updates for these. Issues & regressions in Tier 1 are our first priority and take precedence over other platforms."**

| OS / Architecture | Installation methods | Notes (QUOTE) |
|---|---|---|
| macOS (Apple Silicon) | Hermes Desktop, install.sh | — |
| Windows 10/11 (x86_64, aarch64) | Hermes Desktop, install.ps1 | "A few features are not available." |
| Linux / WSL2 (x86_64, aarch64) | install.sh | "We test on the latest Ubuntu and WSL2. If your distro has glibc, systemd, and follows the Filesystem Hierarchy Standard, it's likely to work pretty well." |
| Docker Container (x86_64, aarch64) | `docker pull` | "Docker installs do not support `hermes update`. Updating is done by running a new image." |

**Tier 2 — "These platforms are maintained in-tree only as a best effort. Releases may break them, and we can't promise we'll fix them promptly when they break."**

| OS / Architecture | Installation methods | Notes (QUOTE) |
|---|---|---|
| Android (Termux) (aarch64) | install.sh | "A few features are not available." |
| Nix (macOS, Linux, NixOS) | install.sh | "Breaks often due to node.js packaging woes. Best of luck~! <3" |

**Unsupported — "PRs to fix them will not be accepted, and any code that keeps compatibility with them may be removed at any point."**
- installs via the AUR
- macOS on x86 (Intel) processors
- installs via pypi (e.g. `uv tool install hermes-agent`, `pip install hermes-agent`)
- installs via brew (`brew install hermes-agent`)

**Install surfaces (four front ends, one agent) — QUOTE, source `/docs/user-guide/desktop`:**

> "Hermes has several front ends that all talk to the same agent: Desktop App (this page) — a native application with a purpose-built UI for chat, configuration, and management. CLI (`hermes`) and TUI (`hermes --tui`) — terminal interfaces. Web Dashboard (`hermes dashboard`) — a browser admin panel; its optional Chat tab embeds the TUI through a pseudo-terminal. Pick whichever fits the moment. They share state, so you can start a session in one and resume it in another."

- Desktop app runs on macOS, Windows, and Linux (QUOTE: "It runs on macOS, Windows, and Linux." — `/docs/user-guide/desktop`) and is installed via the Hermes Desktop installer or `hermes desktop` once the CLI exists.
- TUI: "The TUI is the modern front-end for Hermes — a terminal UI backed by the same Python runtime as the Classic CLI... It's the recommended way to run Hermes interactively." (`/docs/user-guide/tui`). Requires Node.js ≥ 20 and a TTY.
- Classic CLI: "Hermes Agent's CLI is a full terminal user interface (TUI) — not a web UI." (`/docs/user-guide/cli`) — remains the shipped default (`display.interface: cli`).
- Windows native vs WSL2 (QUOTE table, source `/docs/user-guide/windows-native`, read via search snippet): native Windows supports CLI, TUI, messaging gateway, cron scheduler, browser tool, MCP servers, local LLM backends, and the web dashboard; only the dashboard's embedded `/chat` terminal pane is WSL2-only ("✗ (needs POSIX PTY)").
- Nix: three levels — `nix run`/`nix profile install` (any Nix user, pre-built binary), NixOS module native (declarative, hardened systemd service), NixOS module container (adds self-modification via a persistent Ubuntu container) — table quoted in full in §6.
- Termux: "Tier 2 platform... maintained on a best-effort basis only." Tested bundle = CLI + cron + PTY/background terminal + Telegram gateway (manual/best-effort) + MCP + Honcho memory + ACP. Not yet supported on Android: `.[all]` extra, voice extra (`ctranslate2` has no Android wheels), automatic browser/Playwright bootstrap, Docker-based terminal isolation.

### (c) Mechanism-selection table — every documented "use X when / use Y when" comparison found

1. **`session_search` vs `memory`** (source: `/docs/user-guide/features/memory`, section "session_search vs memory")

| Feature | Persistent Memory | Session Search |
|---|---|---|
| Capacity | ~1,300 tokens total | Unlimited (all sessions) |
| Speed | Instant (in system prompt) | ~20ms FTS5 query, ~1ms scroll |
| Cost | Token cost in every prompt | Free — no LLM calls |
| Use case | Key facts always available | Finding specific past conversations |
| Management | Manually curated by agent | Automatic — all sessions stored |

> QUOTE: "Memory is for critical facts that should always be in context. Session search is for 'did we discuss X last week?' queries where the agent needs to recall specifics from past conversations."

2. **Kanban vs `delegate_task`** (source: `/docs/user-guide/features/kanban`, section "Kanban vs. delegate_task")

| | `delegate_task` | Kanban |
|---|---|---|
| Shape | RPC call (fork → join) | Durable message queue + state machine |
| Parent | Blocks until child returns | Fire-and-forget after `create` |
| Child identity | Anonymous subagent | Named profile with persistent memory |
| Resumability | None — failed = failed | Block → unblock → re-run; crash → reclaim |
| Human in the loop | Not supported | Comment / unblock at any point |
| Agents per task | One call = one subagent | N agents over task's life (retry, review, follow-up) |
| Audit trail | Lost on context compression | Durable rows in SQLite forever |
| Coordination | Hierarchical (caller → callee) | Peer — any profile reads/writes any task |

> QUOTE: "One-sentence distinction: `delegate_task` is a function call; Kanban is a work queue where every handoff is a row any profile (or human) can see and edit. Use `delegate_task` when the parent agent needs a short reasoning answer before continuing, no humans involved, result goes back into the parent's context. Use Kanban when work crosses agent boundaries, needs to survive restarts, might need human input, might be picked up by a different role, or needs to be discoverable after the fact. They coexist: a kanban worker may call `delegate_task` internally during its run."

3. **`delegate_task` vs `execute_code`** (source: `/docs/user-guide/features/delegation`, section "Delegation vs execute_code")

| Factor | delegate_task | execute_code |
|---|---|---|
| Reasoning | Full LLM reasoning loop | Just Python code execution |
| Context | Fresh isolated conversation | No conversation, just script |
| Tool access | All non-blocked tools with reasoning | 7 tools via RPC, no reasoning |
| Parallelism | 3 concurrent subagents by default (configurable) | Single script |
| Best for | Complex tasks needing judgment | Mechanical multi-step pipelines |
| Token cost | Higher (full LLM loop) | Lower (only stdout returned) |
| User interaction | None (subagents can't clarify) | None |

> QUOTE: "Rule of thumb: Use `delegate_task` when the subtask requires reasoning, judgment, or multi-step problem solving. Use `execute_code` when you need mechanical data processing or scripted workflows."

4. **`/goal` vs Kanban** (source: `/docs/user-guide/features/goals`, section "Goals vs Kanban: which one do I want?")

| You want | Reach for |
|---|---|
| Keep iterating on one task in this chat until it's done | `/goal <objective>` |
| Many independent tasks, with dependencies, handoffs, or multiple profiles | Kanban — `hermes kanban create …` |
| One card on the board that should keep iterating until its acceptance criteria are met | A kanban card with `--goal` |

> QUOTE: "`/goal` is single-session. The loop feeds continuation prompts back into this conversation until the judge says done. Setting a goal never creates a kanban card, never assigns work to another profile, and never fans out. There is no handoff to the board, implicit or otherwise. Kanban is a board of many tasks. Each card is dispatched to its own worker process with its own session... The overlap is deliberate, and small. A kanban card created with `--goal` runs the same Ralph-style continuation engine as `/goal` — but inside that one card's worker session. It borrows the engine, not the board."

5. **Four hook systems** (source: `/docs/user-guide/features/hooks`, opening table)

| System | Registered via | Runs in | Use case |
|---|---|---|---|
| Gateway hooks | `HOOK.yaml` + `handler.py` in `~/.hermes/hooks/` | Gateway only | "Logging, alerts, webhooks" |
| Plugin hooks | `ctx.register_hook()` in a plugin | CLI + Gateway | "Tool interception, metrics, guardrails" |
| Shell hooks | `hooks:` block in `~/.hermes/config.yaml` pointing at shell scripts | CLI + Gateway | "Drop-in scripts for blocking, auto-formatting, context injection" |
| Outbound webhooks | `hooks.outbound:` list in `~/.hermes/config.yaml` | CLI + Gateway | "Push signed lifecycle events to external HTTP endpoints — CI, dashboards, other agents" |

> QUOTE: "Hook callback errors are isolated and logged rather than crashing the agent. Hooks are not all passive: directive/control hooks can change flow, transforms can replace content, and a shell `pre_tool_call` hook can block or fail closed."

6. **SOUL.md vs AGENTS.md** (source: `/docs/user-guide/features/personality`, section "SOUL.md vs AGENTS.md")

> QUOTE: "SOUL.md — Use for: identity, tone, style, communication defaults, personality-level behavior. AGENTS.md — Use for: project architecture, coding conventions, tool preferences, repo-specific workflows, commands, ports, paths, deployment notes. A useful rule: if it should follow you everywhere, it belongs in `SOUL.md`; if it belongs to a project, it belongs in `AGENTS.md`."

7. **SOUL.md vs `/personality`** (source: same page, section "SOUL.md vs /personality")

> QUOTE: "`SOUL.md` is your durable default personality. `/personality` is a session-level overlay that changes or supplements the current system prompt. So: `SOUL.md` = baseline voice; `/personality` = temporary mode switch." Example given: "keep a pragmatic default SOUL, then use `/personality teacher` for a tutoring conversation."

8. **Skill bundles vs installing each skill manually** (source: `/docs/user-guide/features/skills`, section "When bundles beat installing each skill manually")

> QUOTE: "Use a bundle when: You always pair the same skills for a recurring task (`/backend-dev`, `/release-prep`, `/incident-response`). You want a one-character-shorter mental model than typing several `/skill` invocations in a row. You want to ship a team-wide 'task profile' by checking the bundle YAML into a shared dotfiles repo and symlinking it into `~/.hermes/skill-bundles/`."

9. **NixOS deployment mode: Native vs Container** (source: `/docs/getting-started/nix-setup`, section "Choosing a Deployment Mode")

| | Native (default) | Container |
|---|---|---|
| How it runs | Hardened systemd service on the host | Persistent Ubuntu container with `/nix/store` bind-mounted |
| Security | `NoNewPrivileges`, `ProtectSystem=strict`, `PrivateTmp` | Container isolation, runs as unprivileged user inside |
| Agent can self-install packages | No — only tools on the Nix-provided PATH | Yes — `apt`, `pip`, `npm` installs persist across restarts |
| When to choose | "Standard deployments, maximum security, reproducibility" | "Agent needs runtime package installation, mutable environment, experimental tools" |

10. **Where to build an extension — "Pluggable interfaces" master table** (source: `/docs/user-guide/features/plugins`, section "Pluggable interfaces — where to go for each"; abridged to the mechanism-selection rows most relevant to orientation)

| Want to add… | How |
|---|---|
| A tool the LLM can call | Python plugin — `ctx.register_tool()` |
| A lifecycle hook | Python plugin — `ctx.register_hook()` |
| A slash command | Python plugin — `ctx.register_command()` |
| A TTS/STT backend | "Config-driven (recommended)... OR Python backend plugin... for Python-SDK / streaming engines that need more than a shell template." |
| External tools via MCP | "Config-driven — declare `mcp_servers.<name>` with `command:`/`url:` in `config.yaml`. Hermes auto-discovers the server's tools and registers them alongside built-ins." |
| Gateway event hooks | "Drop `HOOK.yaml` + `handler.py` into `~/.hermes/hooks/<name>/`" |

> QUOTE (framing line): "Not everything is a Python plugin. Some extension surfaces intentionally use config-driven shell commands (TTS, STT, shell hooks) so any CLI you already have becomes a plugin without writing Python. Others are external servers (MCP) the agent connects to and auto-registers tools from... Pick the right surface for the integration style that fits your use case."

**Additional "use X, not Y" guidance found (not full comparison tables, but explicit steering statements):**

- Custom tools: QUOTE (source: `/docs/user-guide/features/plugins`, opening line, corroborated verbatim on `/docs/getting-started/learning-path`): "If you want to create a custom tool for yourself, your team, or one project, this is usually the right path [plugins]. The developer guide's Adding Tools page is for built-in Hermes core tools that live in `tools/` and `toolsets.py`."
- Curator pruning vs consolidation: QUOTE (source: `/docs/user-guide/features/curator`): "By default the curator only prunes — the deterministic inactivity pass marks skills stale and archives long-unused ones. The opinionated LLM consolidation pass (umbrella-building, merging overlapping skills) is off by default because it costs aux-model tokens on every run and makes broad structural changes to your library."
- Skills vs memory (self-improvement loop split): QUOTE (source: `/docs/user-guide/features/skills`, section "Agent-Managed Skills"): "Skills and memory work together in the self-improvement loop: memory stores small durable facts that should always be in context, while skills store longer procedures that should load only when relevant."

---

## 5. Normative statements

| Exact quote | Page + section | Why it matters for stage 080 |
|---|---|---|
| "We strive to never break installations and updates for these. Issues & regressions in Tier 1 are our first priority and take precedence over other platforms." | Platform Support / Tier 1 | Sets reliability expectations before pinning a stage 080 harness to a platform. |
| "Nix is no longer an explicitly supported install path (best-effort only)." | Installation / Prerequisites, and Platform Support / Tier 2 | Any stage 080 GitOps/Nix-flavored deployment plan for Hermes must not assume Tier-1 stability. |
| "Docker installs do not support `hermes update`. Updating is done by running a new image." | Platform Support / Tier 1 table | Directly affects how a containerized stage 080 harness would perform upgrades — image rebuild, not in-place update. |
| "Minimum context: 64K tokens... Models with smaller windows cannot maintain enough working memory for multi-step tool-calling workflows and will be rejected at startup." | Quickstart / Choose a Provider | Hard constraint on which private/self-hosted models stage 080 can wire into Hermes as the main or delegation model. |
| "Blank Slate — everything starts off except the bare minimum needed to run an agent: provider & model, the File Operations toolset, and the Terminal toolset. No web, browser, code execution, vision, memory, delegation, cron, skills, plugins, or MCP servers..." | Quickstart / Choose a Provider, "Setup modes" | Names the exact minimal-trust baseline a governed/sandboxed stage 080 profile could start from. |
| "General plugins and user-installed backends are disabled by default... nothing with hooks or tools loads until you add the plugin's name to `plugins.enabled`... This stops third-party code from running without your explicit consent." | Plugins / "Plugins are opt-in" | Security-relevant default for any stage 080 policy on installing third-party Hermes plugins. |
| "Project-local plugins under `./.hermes/plugins/` are disabled by default. Enable them only for trusted repositories by setting `HERMES_ENABLE_PROJECT_PLUGINS=true`." | Plugins / Minimal working example | Directly relevant if stage 080 repos ship their own `.hermes/plugins/`. |
| "Nested delegation is opt-in — only `role=\"orchestrator\"` children can delegate further, and only when `max_spawn_depth` is raised from its default of 1 (flat)." | Delegation / Key Properties | Bounds runaway multi-agent fan-out — relevant to any stage 080 cost/safety guardrail design. |
| "Kanban is deliberately single-host. `~/.hermes/kanban.db` is a local SQLite file and the dispatcher spawns workers on the same machine... If you need multi-host, run an independent board per host and use `delegate_task` / a message queue to bridge them." | Kanban / Out of scope | Scoping constraint if stage 080 imagines a distributed multi-agent board across cluster nodes. |
| "Cron-run sessions cannot recursively create more cron jobs. Hermes disables cron management tools inside cron executions to prevent runaway scheduling loops." | Cron / intro | Safety guardrail worth mirroring in any custom stage 080 automation loop design. |
| "The model/provider drift guard is enabled by default... it skips the run, makes no inference call, and alerts you to pin the provider/model explicitly... This prevents an unattended job from silently inheriting a switch to a paid provider/model." | Cron / "Letting unpinned jobs track global defaults" | Cost-control default relevant to unattended stage 080 harness jobs against MaaS-billed models. |
| "SOUL.md is scanned like other context-bearing files for prompt injection patterns before inclusion." / "All context files are scanned for potential prompt injection before being included." | Personality / Security scanning; Context Files / Security | Baseline prompt-injection defense already built into context loading — relevant when comparing to this repo's own AGENTS.md/skills trust model. |
| "Memory entries are scanned for injection and exfiltration patterns before being accepted... Content matching threat patterns... or containing invisible Unicode characters is blocked." | Memory / Security Scanning | Same defense-in-depth pattern applied to agent-writable memory. |
| "By default the agent saves memory freely — including from the background self-improvement review that runs after a turn. If you'd rather approve saves first, set `memory.write_approval: true`." | Memory / Controlling memory writes | Human-in-the-loop control point relevant to any stage 080 governance requirement over autonomous learning. |
| "One agent per Hermes home... Memory is scoped per profile by design — give a second agent its own profile, and if they need shared memory, use an external memory provider instead." | Memory / How It Works | Multi-agent isolation rule directly relevant to designing a stage 080 multi-profile harness. |

---

## 6. Official examples (verbatim blocks)

**Blank Slate provider setup modes** (source: Quickstart / Choose a Provider):
> "Quick Setup (Nous Portal) — free OAuth login, no API keys; sets up a model plus the Tool Gateway tools. The recommended fast path. Full Setup — walk through every provider, tool, and option yourself (bring your own keys). Blank Slate — everything starts off except the bare minimum needed to run an agent: provider & model, the File Operations toolset, and the Terminal toolset."

**Minimal plugin** (source: Plugins / Minimal working example) — registers a `hello_world` tool and a `post_tool_call` hook:
```python
"""Minimal Hermes plugin — registers a tool and a hook."""
import json

def register(ctx):
    schema = {
        "name": "hello_world",
        "description": "Returns a friendly greeting for the given name.",
        "parameters": {
            "type": "object",
            "properties": {"name": {"type": "string", "description": "Name to greet"}},
            "required": ["name"],
        },
    }
    def handle_hello(params, **kwargs):
        del kwargs
        name = params.get("name", "World")
        return json.dumps({"success": True, "greeting": f"Hello, {name}!"})
    ctx.register_tool(name="hello_world", toolset="hello_world", schema=schema, handler=handle_hello)

    def on_tool_call(tool_name, params, result):
        print(f"[hello-world] tool called: {tool_name}")
    ctx.register_hook("post_tool_call", on_tool_call)
```

**Minimal gateway hook** (source: Hooks / Creating a Hook):
```yaml
# HOOK.yaml
name: my-hook
description: Log all agent activity to a file
events:
  - agent:start
  - agent:end
  - agent:step
```
```python
# handler.py
async def handle(event_type: str, context: dict):
    """Called for each subscribed event. Must be named 'handle'."""
    ...
```

**Delegation call shape** (source: Delegation / Single Task):
```python
delegate_task(
    goal="Debug why tests fail",
    context="Error: assertion in test_foo.py line 42")
```

**Kanban orchestrator fan-out** (source: Kanban / How workers interact with the board):
```text
kanban_create(title="research ICP funding 2024-2026", assignee="researcher-a", body="…")
kanban_create(title="research ICP funding — EU angle", assignee="researcher-b", body="…")
kanban_create(title="synthesize findings into launch brief", assignee="writer",
              parents=["t_r1", "t_r2"], body="one-pager, 300 words, neutral tone")
kanban_complete(summary="decomposed into 2 research tasks + 1 writer; linked dependencies")
```

**`/goal` completion contract inline syntax** (source: Goals / Two ways to set a contract):
```text
/goal Migrate auth to JWT
verify: pytest tests/auth passes
constraints: keep the /login response shape unchanged
boundaries: only touch services/auth and its tests
stop when: a DB schema migration is required
```

---

## 7. Recommendations found (docs-stated best practices)

- "Rule of thumb: if Hermes cannot complete a normal chat, do not add more features yet. Get one clean conversation working first, then layer on gateway, cron, skills, voice, or routing." (Quickstart / The fastest path)
- "For most first-time users: choose a provider, accept the defaults unless you know why you're changing them." (Quickstart / Choose a Provider)
- "`hermes setup --portal` is the lowest-friction option for unattended runs since OAuth refresh is automatic." (Cron / intro)
- "Decomposing a problem into well-specified subtasks takes frontier-level judgment; executing a subtask that already comes with a clear goal, full context, and an output contract usually doesn't... Pinning `delegation.model` to an inexpensive model while your main session stays on a frontier model keeps the planning quality where it matters and cuts spend where the volume is." (Delegation / Cost strategy — mirrored near-verbatim in Kanban / Cost strategy for the orchestrator/worker split)
- "The `patch` action is preferred for updates [to skills] — it's more token-efficient than `edit` because only the changed text appears in the tool call." (Skills / Agent-Managed Skills)
- "Best practice: When memory is above 80% capacity (visible in the system prompt header), consolidate entries before adding new ones." (Memory / Capacity Management)
- "Decide before you fan out. Design decisions belong to the orchestrator, not to the workers... the orchestrator decides it once and stamps the decision into both card bodies." (Kanban / How the orchestrator behaves)
- "Don't let either worker self-adjudicate — the colliding agent lacks its peer's context and reliably overwrites the other side or abandons its own. Instead, create a reconciliation card assigned to a third, neutral profile..." (Kanban / Reconciling colliding worker branches)
- "A strong default setup is: 1. Keep a thoughtful global `SOUL.md`... 2. Put project instructions in `AGENTS.md`... 3. Use `/personality` only when you want a temporary mode shift." (Personality / Recommended workflow)
- "Skip it [`--goal` on a kanban card] for cheap one-shot work — the per-turn judge overhead isn't worth it, and the dispatcher's existing retry/circuit-breaker already handles transient worker failures." (Kanban / Goal-mode cards)
- Community-voice recommendation curated on the official user-stories page (third-party, not a Nous claim): "Start with one small workflow. Make it boringly reliable. Then add the next piece. Don't turn the default profile into a giant backpack full of every skill, every tool, every instruction." (u/itsdodobitch, curated on `/docs/user-stories`)

---

## 8. Boundary notes (depth deferred to sibling skills)

- Configuration keys, `config.yaml` schema, model/provider wiring, `context_length`/`max_tokens`, auxiliary-model routing → **`hermes-configuration`**.
- Admin-tier pins under `/etc/hermes`, secret/vault handling, fleet security posture → **`hermes-managed-scope`**.
- Full Kanban board mechanics (dispatcher internals, board CRUD, collaboration-pattern depth) → **`hermes-kanban`** (this dossier captured only the orientation-level comparison table and one-line description).
- Full Skills-system authoring mechanics (SKILL.md format depth, hub sources, trust levels, taps) → **`hermes-skills`** (this dossier captured only the orientation-level "when to use a skill" framing and the bundle-vs-individual-skills comparison).
- Full Hooks depth (all four systems' complete mechanics, the 24-event plugin-hook catalog, firing order) → **`hermes-hooks`** (this dossier captured only the top-level four-system comparison table).
- Sessions lifecycle (resume/handoff/search, retention, checkpoints/rollback, provenance) → **`hermes-sessions`**.
- Command surface (full CLI/slash-command reference) → **`hermes-cli`**.
- MCP configuration depth (filtering semantics, utility-tool policy, per-server config keys) → no current sibling skill claims this; flagged as a taxonomy gap in §9.
- Delegation depth (subagent internals beyond the orientation-level comparison table already captured here) → no current sibling `hermes-delegation` skill; the AGENTS.md skill list has no dedicated delegation skill, so depth currently has no owner (flagged in §9).

---

## 9. Gaps & open questions

- **No fixed "product version."** Hermes has no discrete version number this skill can pin as "the current release" — it is a rolling `main`-branch install (`hermes update` tracks `origin/main`), version is checked operationally via `hermes version` / `hermes --version` compared to the GitHub releases page, and git tags (example format `vYYYY.M.D`, e.g. `v2026.5.16`) exist only as rollback targets. A `hermes-about` skill (or `AGENTS.md`'s platform-baseline field) should describe this as a *procedure*, not record a static version string, or it will silently go stale.
- **Taxonomy gaps** — official feature-inventory rows with no owning `hermes-*` sibling skill (per the current skill-group list in `AGENTS.md`): Tools & Toolsets, Persistent Memory, MCP, Delegation, Persistent Goals (`/goal`), Plugins, Context Files, Personality/SOUL.md, Provider Routing/Fallback/Credential Pools, API Server, ACP, Voice/Vision/Browser/Image-gen/TTS, Batch Processing, Memory Providers (Honcho et al.), Curator (partially covered if `hermes-skills` claims it). This matches the note already in this skill's assignment ("mcp, memory, plugins, cron, delegation so far" as known gaps) but the list is larger than that after this pass — cron also has no dedicated sibling skill despite being a first-class automation primitive with its own page.
- **No canonical "positioning" prose page.** The only place Nous states what Hermes *is* in marketing language is the `llms.txt` one-paragraph description and the docs homepage tagline; there is no `/docs/about` or `/docs/concepts` chapter. The richest "who it's for" evidence (`/docs/user-stories`) is a curated third-party quote wall, not first-party prose — any skill content built from it must keep the QUOTE/PARAPHRASE distinction intentionally visible (e.g., "community members report using Hermes for X" rather than "Hermes is positioned for X").
- **Messaging-platform count is imprecise across sources.** `llms.txt` states "21+ messaging platforms — 19 native to the gateway plus IRC and Microsoft Teams via plugins"; the Messaging Gateway page's own platform-support table (read via a search-engine snippet, not a full fetch in this run) lists at least 28 named platform rows including channels like BlueBubbles, Photon (iMessage), Feishu/Lark, WeCom, Weixin, Yuanbao, SimpleX, Buzz, ntfy, and Raft that don't obviously map onto "19 native + 2 plugin." A future capture should do a full fetch of `/docs/user-guide/messaging/` and reconcile the exact count rather than quoting the llms.txt figure as authoritative by default.
- **MCP page was only lightly read** (first ~80 lines of a 725-line fetch) — this dossier captured MCP's one-line positioning and catalog/install mechanics but not its full configuration-reference depth (filtering semantics, sampling support details) referenced in Features Overview ("Includes per-server tool filtering and sampling support"). Flag for whichever skill ends up owning MCP depth.
- **Curator vs Skills ownership is genuinely ambiguous.** The Curator page's own framing ("It exists so that skills created via the self-improvement loop don't pile up forever") makes it read as a skills-adjacent maintenance daemon, but it's listed as its own page under "Core Features" in llms.txt, not nested under Skills System. This dossier provisionally assigned it to `hermes-skills` in §4a; the reviewer should confirm that's the intended ownership or treat Curator as its own gap.
- **No explicit statement of Hermes's target audience/persona** beyond the community-curated stories page and one third-party quote ("Hermes is the general agent, not a coding/research/automation agent — one tool running every category of work a builder does," @sudoingX, curated on `/docs/user-stories`). If the reviewer wants a first-party positioning statement, none exists in the docs as read; only the `llms.txt` description is unambiguously first-party.

---

## 10. Suggested SKILL.md inputs (for the reviewer — not an edit)

**Key concepts to state (each cites its backing evidence above):**
- Hermes Agent is "the self-improving AI agent built by Nous Research... terminal-native autonomous coding and task agent with persistent memory, agent-created skills, and a messaging gateway" — cite §1 llms.txt QUOTE.
- Four interchangeable front ends sharing one agent state (CLI, TUI, Desktop App, Web Dashboard) — cite §4b QUOTE from `/docs/user-guide/desktop`.
- Three-tier platform support (Tier 1: macOS Apple Silicon/Windows/Linux-WSL2/Docker; Tier 2: Termux/Nix; Unsupported: AUR/Intel-Mac/pypi/brew) — cite §4b table.
- Getting-started shape is Install → Choose a Provider → First Chat → Verify Sessions → Try Key Features → Add the Next Layer — cite §3 page map of Quickstart.
- Versioning is procedural (`hermes version` vs GitHub releases), not a fixed number — cite §1 and §9 gap note.
- The mechanism-selection decision surface (this skill's stated core job) has (at least) ten documented comparisons — cite §4c in full; this should likely become the skill's centerpiece table.

**Workflow steps to propose:**
1. Before recommending a Hermes mechanism for a stage 080 need, check §4c's comparison table first (delegate_task vs kanban vs goal vs cron vs hooks vs plugins) rather than reasoning from first principles — cite the "one-sentence distinction" and "rule of thumb" QUOTEs in §4c items 2–3.
2. Before claiming platform support for a deployment target, check §4b's tier table — cite the exact Tier 1/2/Unsupported QUOTEs so the skill doesn't imply Nix or Termux carry Tier-1 guarantees.
3. When describing "what Hermes can do," cite the Features Overview five-category structure (§4a) rather than an ad hoc list, and flag taxonomy-gap features (§9) as "documented but not yet covered by a dedicated sibling skill" rather than silently omitting them.

**Validation commands to propose (static, doc-citation checks — no live cluster involved):**
- Grep the skill body for every mechanism name in §4c's ten tables (`delegate_task`, kanban, `/goal`, hooks, SOUL.md, skill bundles, plugins) and confirm each cites a `hermes-agent.nousresearch.com` URL, per this skill's own `SKILL.md` validation line ("The change or review cites the official doc section it relied on").
- Confirm the skill does not assert a fixed Hermes version number anywhere (per §9's versioning gap).

---

## Reviewer addendum (2026-08-12) — family closure notes

### Ownership decisions

- Curator → `hermes-skills` CONFIRMED (that skill's capture covers curator
  jurisdiction, pinning, archival, and rollback in full).
- The dossier's version framing ("procedural, not a fixed number")
  reconciles with the hermes-cli capture's point-in-time anchor (v0.20.0,
  tag v2026.8.3, 2026-08-03, via the docs-linked releases page): record
  the PROCEDURE in prose, keep the anchor only as capture metadata.

### Cross-map result (feature inventory vs implemented skills)

All rows the dossier assigned to siblings check out against the
implemented captures (skills, hooks, kanban, sessions, cli,
configuration, managed-scope). The consolidated unowned-feature list is
recorded in this skill's source-capture.md as the definitive taxonomy-gap
register for the family — superseding the partial lists in earlier
captures' open items.

### Community-voice discipline

The user-stories page is a curated third-party quote wall. The SKILL.md
carries this as a pitfall; any stage 080 material quoting it must
attribute to the community author, not to Nous Research.
