# Official Doc Extraction — hermes-cli

Validated research dossier (capture date 2026-08-12). Reviewer validation:
the -z and --usage-file quotes, the --accept-hooks ABSENCE from the Global
options table, the gateway --external-supervisor exit-75 contract, hermes
send exit codes, the shared COMMAND_REGISTRY statement, the
allow_admin_from backward-compat default, the Slack-thread ! rule, and the
prefix/alias resolution rule were all re-verified verbatim against live
pages on 2026-08-12. Cross-checked against the six sibling skills'
previously verified CLI fragments: consistent — the reference page's
kanban and hooks sections are subsets of the feature pages' fuller CLI
blocks, exactly as those captures reported from the other side. Original
dossier: `source-analysis/hermes/hermes-cli-capture.md`.

---

# hermes-cli — Documentation Capture

## Executive Summary (5 lines)

1. **Captured:** The full `hermes` subcommand tree (~60 top-level commands, all documented subcommands/flags), all global flags, the complete interactive-CLI and messaging slash-command registries with per-surface availability, CLI-relevant environment variables, and shell completion — sourced from both reference pages read cover-to-cover plus five supporting guide pages.
2. **Confidence:** High for the two canonical reference pages (read in full, no gaps found in rendering) and for env vars / slash commands. Medium for a few command families whose *only* documentation lives outside `cli-commands` (e.g. `hermes photon`, `hermes approvals suggest` flags, `hermes update --branch/--force/--force-venv`).
3. **Biggest gap:** `hermes photon` (iMessage via Photon) is a real, currently-shipping top-level command family — invoked as `hermes photon setup` / `hermes photon telemetry on|off` and referenced from the environment-variables and messaging pages — but it is **absent from the `cli-commands` top-level command table entirely**. Anyone relying only on the canonical CLI reference would not know this command exists. Same class of gap, smaller: `--accept-hooks` is a documented global CLI flag but is missing from the CLI reference's own "Global options" table (it only appears on the Event Hooks feature page).
4. **Contradicts placeholder:** Nothing in the current placeholder is factually contradicted — it only pins two URLs (`user-guide/cli`, `reference/cli-commands`) and defers all content. This capture recommends adding `reference/slash-commands`, `reference/profile-commands`, `reference/environment-variables`, and `user-guide/tui` as co-equal pins, since slash-command surface, profile CLI, and CLI-relevant env vars are core to this skill's stated scope and are each on separate pages the placeholder doesn't cite.
5. **Suggested next skill:** `hermes-hooks` or `hermes-sessions` reference verification — both have CLI surface fragments (`hermes hooks`, `hermes sessions`) whose full flag semantics are cross-referenced here but whose *behavioral* depth (consent model, hook payload shapes, session repair internals) is out of this skill's scope and should be checked against whatever those sibling skills already captured, since this run found extra CLI-relevant flag detail (`hermes hooks test --for-tool/--payload-file`) not present in the `cli-commands` page itself.

---

## 1. Capture Header

| Field | Value |
|---|---|
| Product | Hermes Agent (Nous Research) |
| Version marker on `cli-commands`/`slash-commands` pages themselves | **No version marker on page** (neither reference page shows a version banner, "last updated" date, or doc-version selector) |
| Product version (from linked GitHub Releases page — see below) | **v0.20.0 "The Herald Release"**, tag `v2026.8.3`, published 2026-08-03 |
| How version was obtained | The docs page `docs/getting-started/updating` § "Checking your current version" explicitly instructs: *"Compare against the latest release at the GitHub releases page."* — i.e. the docs site links to `https://github.com/NousResearch/hermes-agent/releases`. This satisfies the "release notes, if linked from the docs site" allowance. Treated as **PARAPHRASE of a linked official release note**, not "repository, not docs." |
| Capture date | 2026-08-12 |

### Page inventory (step 1: territory mapping)

Enumerated from `docs/llms.txt` (the curated index) plus targeted web search for pages not in that index. Per the assignment's caveat, `llms.txt` was treated only as a starting inventory.

| Page | Relevance | Disposition |
|---|---|---|
| `/docs/reference/cli-commands` | Canonical CLI command reference | **Read in full** (1502 lines, no grep shortcuts) |
| `/docs/reference/slash-commands` | Canonical slash-command reference (CLI + messaging) | **Read in full** (294 lines, no grep shortcuts) |
| `/docs/reference/profile-commands` | `hermes profile`, `hermes -p`, `hermes completion` detail (more detail than `cli-commands`' summary rows) | **Read in full** — directly in scope (command surface) |
| `/docs/reference/environment-variables` | All env vars, many CLI-relevant (flag equivalents, overrides) | **Read in full** (954 lines) — in scope per assignment ("the CLI's relationship to environment variables") |
| `/docs/user-guide/cli` | Classic CLI interface guide: keybindings, `!` shell mode, resume flow, quick commands | **Read in full** — in scope (interactive surface) |
| `/docs/user-guide/tui` | TUI interface guide: launch flags, TUI-only slash commands, TUI env vars | **Read in full** — in scope (interactive surface, explicitly named in assignment) |
| `/docs/user-guide/security` | Approval flow CLI details (`hermes approvals suggest`, approval prompt UI, YOLO mode activation paths) | **Read (targeted, full section read)** — contains command-surface facts (`hermes approvals suggest --apply/--json`) not in `cli-commands` |
| `/docs/getting-started/updating` | `hermes update`/`hermes uninstall` extra flags (`--branch`, `--force`, `--force-venv`) not in `cli-commands` | **Read in full** — command-surface supplement |
| `/docs/getting-started/quickstart` | First-run command sequence, "Quick Reference" table, Recovery Toolkit command list | **Read in full** — cross-check / official-examples source |
| `/docs/user-guide/features/hooks` | Documents `--accept-hooks` flag (missing from `cli-commands` global options) and `hermes hooks` subcommand flags (`test --for-tool/--payload-file`) | **Read (targeted)** — command-surface supplement; deep hook semantics deferred to `hermes-hooks` |
| `/docs/user-guide/messaging/` (index) | Confirms per-platform slash-command availability context, toolset table | **Read (targeted)** — cross-check only |
| `/docs/user-guide/messaging/photon` | Reveals `hermes photon setup` / `hermes photon telemetry on\|off` — a command family **absent from `cli-commands`** | **Read (targeted)** — gap discovery |
| `/docs/user-guide/messaging/whatsapp-cloud` | Confirms `hermes whatsapp-cloud` is a bare wizard invocation (no subflags documented) | **Read (targeted)** — cross-check only |
| `/docs/reference/faq` | Approval/troubleshooting cross-references | **Skimmed via search snippet only** — deprioritized: no new CLI command-surface facts beyond what security page gave |
| `/docs/reference/mcp-config-reference` | `hermes mcp` semantics | **Deprioritized** — subsystem semantics, not command surface; `hermes mcp` subcommand table already complete from `cli-commands` |
| `/docs/reference/tools-reference`, `/docs/reference/toolsets-reference` | Tool/toolset catalogs | **Deprioritized** — not CLI command surface (feeds `hermes tools`/`--toolsets` but doesn't add flags) |
| `/docs/user-guide/features/api-server` | OpenAI-compatible API server (not a CLI surface beyond `hermes serve`, already captured) | **Deprioritized** — HTTP API, not `hermes` command surface |
| `/docs/developer-guide/extending-the-cli` | Wrapper-CLI development (building on the TUI) | **Deprioritized** — developer/plugin authoring guide, not end-user command surface |
| `/docs/user-guide/features/plugins` | Confirms `ctx.register_command()` can add arbitrary `/slash` commands at runtime | **Read (targeted)** — relevant caveat: dynamic slash commands exist beyond the fixed registry; noted in gaps |
| `/docs/user-guide/sessions`, `/docs/user-guide/features/kanban`, `/docs/user-guide/features/skills`, `/docs/user-guide/features/curator`, `/docs/user-guide/configuration` | Subsystem semantics owned by sibling skills | **Deprioritized for depth** — command surface already fully captured from `cli-commands`; only consulted where a command's flags weren't in `cli-commands` (none found needing this) |
| `/docs/reference/faq` "Profiles section" (referenced by profile-commands "See also") | Possible profile FAQ detail | **Not separately fetched** — profile-commands page was already exhaustive; flagged as unread in case reviewer wants a final check |

### Dead links / redirects

None encountered. All fetched URLs returned 200 with content (some via a full-page-dump helper rather than truncated preview, noted inline). No page in the inventory above was unreachable.

---

## 2. Recommended Source Pins

The current `references/source-capture.md` pins only:
- `https://hermes-agent.nousresearch.com/docs/user-guide/cli`
- `https://hermes-agent.nousresearch.com/docs/reference/cli-commands`

**Recommended full pin set** (based on what this capture actually used):

| Priority | URL | Why |
|---|---|---|
| 1 (primary) | `https://hermes-agent.nousresearch.com/docs/reference/cli-commands` | Canonical command tree — already pinned, confirmed correct and current |
| 1 (primary) | `https://hermes-agent.nousresearch.com/docs/reference/slash-commands` | Canonical slash-command registry — **missing from current pins**; this skill's own description explicitly covers "the slash-command registry across surfaces," which lives entirely on this page |
| 2 | `https://hermes-agent.nousresearch.com/docs/reference/profile-commands` | `hermes profile`, `hermes -p`/`--profile`, `hermes completion` — fuller detail than the summary rows in `cli-commands`; **missing from current pins** |
| 2 | `https://hermes-agent.nousresearch.com/docs/reference/environment-variables` | CLI-relevant env vars (flag equivalents, overrides); the assignment explicitly asks for "the CLI's relationship to environment variables" — **missing from current pins** |
| 2 | `https://hermes-agent.nousresearch.com/docs/user-guide/cli` | Classic CLI guide — already pinned, confirmed correct |
| 2 | `https://hermes-agent.nousresearch.com/docs/user-guide/tui` | TUI guide — the assignment explicitly names "interactive CLI vs TUI vs messaging gateway" as in scope; **missing from current pins** |
| 3 (supplementary, cite only for the specific facts below) | `https://hermes-agent.nousresearch.com/docs/user-guide/security` | Source for `hermes approvals suggest` flags and the CLI approval-prompt UI, which `cli-commands` does not fully specify |
| 3 (supplementary) | `https://hermes-agent.nousresearch.com/docs/getting-started/updating` | Source for `hermes update --branch/--force/--force-venv` and `hermes uninstall` manual-uninstall steps, not in `cli-commands` |
| 3 (supplementary) | `https://hermes-agent.nousresearch.com/docs/user-guide/features/hooks` | Source for the `--accept-hooks` global flag (absent from `cli-commands`' own global-options table) and `hermes hooks test` flag detail |
| 3 (supplementary, gap pointer) | `https://hermes-agent.nousresearch.com/docs/user-guide/messaging/photon` | Only known source documenting `hermes photon setup` / `hermes photon telemetry on\|off` — a command family missing from `cli-commands` entirely |

**Pins that proved irrelevant to this skill's scope:** none of the current pins were wrong — both are correct and load correctly. The gap is incompleteness (missing the four page-2 pins above), not inaccuracy.

---

## 3. Page Maps

### `/docs/reference/cli-commands` ("CLI Commands Reference")
No version marker on page.
1. Global entrypoint — `hermes [global-options] <command> [subcommand/options]` syntax line
2. Global options — table of 12 flags (`--version`/`-V`, `--profile`/`-p`, `--resume`/`-r`, `--continue`/`-c`, `--in`, `--worktree`/`-w`, `--yolo`, `--pass-session-id`, `--ignore-user-config`, `--ignore-rules`, `--tui`, `--cli`, `--dev`)
3. Top-level commands — table of ~60 command rows, one line each
4. One `##`/`###` section per command family (`hermes chat` through `hermes update`), each with a fenced usage line, an options/subcommands table where applicable, and worked examples
5. Maintenance commands — recap table (`version`, `update`, `uninstall`)
6. See also — full TOC mirror

### `/docs/reference/slash-commands` ("Slash Commands Reference")
No version marker on page.
1. Intro — two surfaces share one `COMMAND_REGISTRY` in `hermes_cli/commands.py`
2. Permissions and admin/user split — `allow_admin_from`/`user_allowed_commands` gating model
3. Interactive CLI slash commands — subsectioned: Session, Configuration, Tools & Skills, Info, Exit, Dynamic CLI slash commands, Quick Commands, Custom model aliases, Alias Resolution
4. Messaging slash commands — one flat table (all messaging-surface commands)
5. Notes — cross-surface availability call-outs (CLI-only / messaging-only / both)
6. Confirmation prompts for destructive commands — the 3-choice modal + inline-skip syntax

### `/docs/reference/profile-commands` ("Profile Commands Reference")
No version marker on page.
1. `hermes profile` (top-level + subcommand table)
2. One `##`/`###` per subcommand (`list`, `use`, `create`, `describe`, `delete`, `show`, `alias`, `rename`, `export`, `import`)
3. Distribution commands — `install`, `update`, `info`, Private distributions, `distribution.yaml` schema, Publishing a distribution
4. `hermes -p`/`hermes --profile` — global flag detail
5. `hermes completion` — shell + what gets completed
6. See also

### `/docs/reference/environment-variables` ("Environment Variables")
No version marker on page.
Sections in order: LLM Providers; Provider Auth (OAuth); Tool APIs (+ Skill API Keys, Langfuse Observability, Nous Tool Gateway); Terminal Backend; SSH Backend; Container Resources; Persistent Shell; Egress proxy (sandbox-injected); Messaging (+ per-platform subsections, Web Dashboard & Hermes Desktop, Microsoft Graph ×2, Teams Meeting Summary Delivery, LINE, ntfy, IRC, SimpleX, Photon, Buzz, Microsoft Teams adapter, Raft, Advanced Messaging Tuning); Agent Behavior (+ `HERMES_WRITE_SAFE_ROOT` detail box); Interface; Session Settings; Context Compression (config.yaml only); Auxiliary Task Overrides; Fallback Providers (config.yaml only); Provider Routing (config.yaml only).

### `/docs/user-guide/cli` ("CLI Interface")
No version marker on page.
Running the CLI; Plugin management; Interface Layout (Status Bar, Session Resume Display); Keybindings (`!` Shell Mode); Slash Commands (pointer to reference page); Quick Commands; Preloading Skills at Launch; Skill Slash Commands; Personalities; Multi-line Input (Shift+Enter compatibility); Redirecting the Agent Mid-Turn (Busy Input Mode, Suspending to Background); Tool Progress Display (Tool Preview Length); Session Management (Resuming Sessions, Session Storage, Context Compression); Background Sessions (How It Works, Results, Use Cases); Quiet Mode.

### `/docs/user-guide/tui` ("TUI")
No version marker on page.
Launch; Why the TUI (Collapsible banner sections); Requirements (External prebuild); Keybindings; Slash commands (TUI-owned overrides table); Live session switcher; LaTeX math rendering; Light-terminal detection; Busy indicator styles; Auto-resume; Status line; Configuration; Sessions; How the TUI talks to its gateway; Reverting to the classic CLI; See also.

### `/docs/user-guide/security` (targeted read, § Dangerous Command Approval only)
Overview (8-layer model); Dangerous Command Approval → Approval Modes, YOLO Mode, Hardline Blocklist, User-Defined Deny Rules, Approval Timeout, What Triggers Approval, Approval Flow (CLI), Approval Flow (Gateway/Messaging), Permanent Allowlist, **Mining Approval History (`hermes approvals suggest`)**.

### `/docs/getting-started/updating` ("Updating & Uninstalling")
No version marker on page (but instructs comparing against GitHub Releases for version).
Updating (What happens during an update; Updating against a non-default branch `--branch`; Local changes on non-interactive updates; Preview-only `--check`; Full pre-update backup `--backup`; Windows "another hermes.exe" guard incl. `--force`/`--force-venv`; Recommended Post-Update Validation; terminal-disconnect resilience; Checking your current version; Updating from Messaging Platforms; Manual Update; Rollback instructions; Note for Nix users); Uninstalling (Manual Uninstall).

### `/docs/getting-started/quickstart` ("Quickstart")
No version marker on page.
Prefer to watch?; Who this is for; The fastest path (goal→command table); 1. Install; 2. Choose a Provider (How settings are stored); 3. Run Your First Chat; 4. Verify Sessions Work; 5. Try Key Features (terminal, slash commands, multi-line input, interrupt); 6. Add the Next Layer (gateway, tools/skills, sandboxed terminal, voice, skills, MCP, ACP); Common Failure Modes; Recovery Toolkit; Quick Reference; Next Steps.

### `/docs/user-guide/features/hooks` (targeted read via search snippet + confirmed section)
Relevant section only: "Consent model" → three escape hatches (`--accept-hooks` flag, `HERMES_ACCEPT_HOOKS=1`, `hooks_auto_accept: true`); "The hermes hooks CLI" → 4-row subcommand table with fuller flag detail than `cli-commands`.

### `/docs/user-guide/messaging/photon` (targeted read via search snippet)
Confirms `hermes photon setup` device-login flow (6 numbered steps) and passing mention of `hermes photon telemetry on|off` (paired with `PHOTON_TELEMETRY` env var). No dedicated CLI reference table on this page — command syntax is inline prose only.

---

## 4. Reference Tables

### 4.1 Global flags (from `cli-commands` § Global options, cross-checked against env-vars page)

| Flag | Alias | Env var equivalent | Description (QUOTE) |
|---|---|---|---|
| `--version` | `-V` | — | "Show version and exit." |
| `--profile <name>` | `-p <name>` | — | "Select which Hermes profile to use for this invocation. Overrides the sticky default set by `hermes profile use`." |
| `--resume <id\|title\|latest>` | `-r` | — | "Resume a previous session by ID or title. The keyword `latest` resumes the most recent session (workspace-scoped, same lookup as `-c`)." |
| `--continue [name]` | `-c [name]` | — | "Resume the most recent session, or the most recent session matching a title." |
| `--in <dir>` | — | — | "Change into `<dir>` before starting or resuming. Scopes `--resume latest`/`-c` lookups to that directory's workspace and keeps the session there (skips the recorded-cwd restore)." |
| `--worktree` | `-w` | — | "Start in an isolated git worktree for parallel-agent workflows." |
| `--yolo` | — | `HERMES_YOLO_MODE=1` | "Bypass dangerous-command approval prompts." |
| `--pass-session-id` | — | — | "Include the session ID in the agent's system prompt." |
| `--ignore-user-config` | — | `HERMES_IGNORE_USER_CONFIG` | "Ignore `~/.hermes/config.yaml` and fall back to built-in defaults. Credentials in `.env` are still loaded." |
| `--ignore-rules` | — | `HERMES_IGNORE_RULES` | "Skip auto-injection of `AGENTS.md`, `SOUL.md`, `.cursorrules`, memory, and preloaded skills." |
| `--tui` | — | `HERMES_TUI=1` | "Launch the TUI instead of the classic CLI. Equivalent to `HERMES_TUI=1`. Always wins over `display.interface`." |
| `--cli` | — | — | "Force the classic prompt_toolkit REPL. Use this to override `display.interface: tui` for a single invocation." |
| `--dev` | — | — | "With `--tui`: run the TypeScript sources directly via `tsx` instead of the prebuilt bundle (for TUI contributors)." |
| `--safe-mode` | — | `HERMES_SAFE_MODE` | GAP: documented only under `hermes chat` options in `cli-commands`, not in the top-level Global options table, though `HERMES_SAFE_MODE`'s description implies it is settable at the top level too ("Set automatically by `--safe-mode`"). Treat as chat-scoped unless the reviewer confirms otherwise. |
| `--accept-hooks` | — | `HERMES_ACCEPT_HOOKS` | **UNDOCUMENTED in `cli-commands`' Global options table.** Source: `/docs/user-guide/features/hooks` § Consent model: "1. `--accept-hooks` flag on the CLI (e.g. `hermes --accept-hooks chat`)". Env-var page confirms: "Auto-approve any unseen shell hooks declared in `config.yaml` without a TTY prompt. Equivalent to `--accept-hooks` or `hooks_auto_accept: true`." |
| `-s <skills>` | `--skills` | — | Documented under `hermes chat`/CLI guide as preload-skills flag; also usable at top level per CLI guide example `hermes -s hermes-agent-dev,github-auth`. `cli-commands` lists it only under `hermes chat`, not the top-level Global options table — PARAPHRASE/inference that it also works bare (confirmed by the literal example on `/docs/user-guide/cli`). |

### 4.2 Complete `hermes` top-level command family tree

One row per top-level command family. "Subcommands/flags" column condenses the fullest documented set found across all pages (not just `cli-commands`). `sibling` marks the owning skill for deep semantics per the assignment's split.

| Command | Purpose (QUOTE from `cli-commands` unless noted) | Key subcommands / flags | Sibling skill (semantics) |
|---|---|---|---|
| `hermes chat` | "Interactive or one-shot chat with the agent." | `-q/--query`, `-m/--model`, `-t/--toolsets`, `--provider <list…>`, `-s/--skills`, `-v/--verbose`, `-Q/--quiet`, `--image`, `--resume`/`--continue`, `--worktree`, `--checkpoints`, `--yolo`, `--pass-session-id`, `--ignore-user-config`, `--ignore-rules`, `--safe-mode`, `--source`, `--max-turns` | `hermes-configuration` (defaults resolution) |
| `hermes -z "<prompt>"` | Scripted one-shot alias of `chat --oneshot`-like mode; "single prompt in, final response text out, nothing else on stdout or stderr" | `-m/--model`, `--provider`, `--usage-file <path>` | — (this skill) |
| `hermes model` | "Interactively choose the default provider and model." | none documented beyond bare invocation; distinguished from `/model` slash command | `hermes-configuration` |
| `hermes moa` | "Configure named Mixture of Agents presets selectable from the model picker." | `list`, `configure [name]`, `delete <name>` | `hermes-configuration` |
| `hermes fallback` | "Manage fallback providers tried when the primary model errors." | `list`/`ls` (default), `add`, `remove`/`rm`, `clear` | `hermes-configuration` |
| `hermes gateway` | "Run or manage the messaging gateway service." | `run`, `start`, `stop`, `restart`, `status`, `list`, `install`, `uninstall`, `setup`, `migrate-legacy [--dry-run] [-y/--yes]`, `enroll [--token] [--connector-url] [--gateway-id] [--wake-url]`; flags `--all`, `--no-supervise`, `--external-supervisor` | — (this skill for surface; gateway internals are developer-guide territory, no sibling skill in the routing table) |
| `hermes proxy` | "Local OpenAI-compatible proxy that attaches OAuth provider credentials." | `start [--provider <nous\|xai>] [--host] [--port]`, `status`, `providers` | — |
| `hermes egress` | "Outbound credential-injection firewall for remote terminal sandboxes (iron-proxy). Disabled by default." | `install [--force]`, `setup [--tunnel-port N] [--from-bitwarden] [--no-bitwarden] [--rotate-tokens]`, `start`, `stop`, `restart`, `reload`, `status [--show-tokens]`, `disable`, `config` | — |
| `hermes lsp` | "Manage Language Server Protocol integration (semantic diagnostics for write_file/patch)." | `status`, `list [--installed-only]`, `install <server>`, `install-all`, `restart`, `which <server>` | — |
| `hermes setup` | "Interactive setup wizard for all or part of the configuration." | positional section `[model\|tts\|terminal\|gateway\|tools\|agent]`; `--quick`, `--non-interactive`, `--reset`, `--reconfigure`, `--portal` | `hermes-configuration` |
| `hermes whatsapp` | "Configure and pair the WhatsApp bridge." | bare invocation only (mode selection + QR pairing interactive) | — |
| `hermes whatsapp-cloud` | "Configure the official Meta WhatsApp Business Cloud API adapter (Business account + public webhook required)." | bare invocation only (no flags documented on either `cli-commands` or the messaging/whatsapp-cloud page) | — |
| `hermes slack` | "Slack helpers (currently: generate the app manifest with every command as a native slash)." | `manifest [--write [PATH]] [--name] [--description] [--long-description] [--long-description-file] [--slashes-only]` | — |
| `hermes auth` | "Manage credentials — add, list, remove, reset, status, logout. Handles OAuth flows for Codex/Nous/Anthropic." | `add <provider> [--api-key\|--type oauth]`, `list [provider]`, `remove <provider> <index>`, `reset <provider>`, `status <provider>`, `logout <provider>`, `spotify`; bare = interactive wizard | `hermes-configuration` (credential pools) |
| `hermes login`/`hermes logout` | **Deprecated** — "`hermes login` has been removed. Use `hermes auth` to manage OAuth credentials, `hermes model` to select a provider, or `hermes setup` for full interactive setup." | n/a | — |
| `hermes send` | "Send a one-shot message to a configured messaging platform … Useful from shell scripts, cron jobs, CI hooks, and monitoring daemons — no agent loop, no LLM." | `-t/--to <target>`, `-f/--file <path>` (`-` = stdin), `-s/--subject`, `-l/--list [platform]`, `-q/--quiet`, `--json`; positional `message`; `MEDIA:<path>` / `[[as_document]]` directives in message body | — |
| `hermes secrets` | "Manage external secret sources (currently Bitwarden Secrets Manager)…" | `bitwarden`/`bw` subcommands: `setup [--project-id] [--access-token] [--server-url]`, `status`, `token [--access-token] [--no-verify]`, `sync [--apply]`, `install [--force]`, `disable` | — |
| `hermes migrate` | "Diagnose and (optionally) rewrite `config.yaml` to replace references to retired models or deprecated settings." | `xai [--apply] [--no-backup]` | `hermes-configuration` |
| `hermes security` | On-demand OSV.dev supply-chain audit | `audit [--json] [--fail-on <low\|moderate\|high\|critical>] [--skip-venv] [--skip-plugins] [--skip-mcp]` | — |
| `hermes status` | Show agent, auth, platform status | `[--all] [--deep]` | — |
| `hermes cron` | "Inspect and tick the cron scheduler." | `list`, `create`/`add [--skill]`, `edit [--clear-skills] [--add-skill] [--remove-skill]`, `pause`, `resume`, `run`, `remove`, `status`, `tick` | — (no `hermes-cron` sibling in routing table; treat as this skill's surface, semantics undocumented depth in `docs/user-guide/features/cron`) |
| `hermes kanban` | "Multi-profile collaboration board (tasks, links, dispatcher)." | `[--board <slug>]` global flag; `init`, `boards list/create/switch/show/rename/rm`, `create`, `list/ls`, `show`, `assign`, `link`, `unlink`, `claim`, `comment`, `complete`, `block`, `request-review`, `request-changes`, `reopen-review`, `schedule`, `unblock`, `archive`, `tail`, `dispatch [--dry-run] [--max N] [--failure-limit N] [--json]`, `context`, `specify`/`specify --all`, `decompose`/`decompose --all`, `gc` | **`hermes-kanban`** |
| `hermes project` | "Manage named, multi-folder workspaces (projects)." | `create`, `list`/`ls`, `show`, `add-folder`, `remove-folder`, `rename`, `set-primary`, `use`, `archive`, `restore`, `bind-board` | — |
| `hermes webhook` | "Manage dynamic webhook subscriptions for event-driven activation." | `subscribe`/`add <name> [--prompt] [--events] [--description] [--skills] [--deliver] [--deliver-chat-id] [--secret] [--deliver-only] [--script]`, `list`/`ls`, `remove`/`rm`, `test` | — |
| `hermes hooks` | "Inspect, approve, or remove shell-script hooks declared in `config.yaml`." | `list`/`ls`; `test <matcher>` (full form per hooks page: `test [--for-tool X] [--payload-file F]`); `revoke`/`remove`/`rm <command>`; `doctor` | **`hermes-hooks`** |
| `hermes doctor` | Diagnose config and dependency issues | `[--fix]` | — |
| `hermes approvals` | "Approval-prompt tools — mine approval history into allowlist proposals." | `suggest [--apply N[,M…]] [--json]` (source: security page, not `cli-commands`, which only names the family) | — |
| `hermes dump` | Copy-pasteable setup summary for support | `[--show-keys]` | — |
| `hermes prompt-size` | "Show a byte breakdown of the system prompt + tool schemas…" | `[--platform <name>] [--json]` | — |
| `hermes debug` | Upload debug report | `share [--lines N] [--expire N] [--nous] [--local] [--no-redact]` | — |
| `hermes backup` | "Back up Hermes home directory to a zip file." | `-o/--output <path>`, `-q/--quick`, `-l/--label <text>` | — |
| `hermes checkpoints` | "Inspect / prune / clear `~/.hermes/checkpoints/`…" | `status` (default)/`list`, `prune [--retention-days N] [--max-size-mb N] [--keep-orphans]`, `clear [-f]`, `clear-legacy [-f]`; global `--limit N` | `hermes-sessions` (rollback/checkpoint subsystem is session-adjacent; not explicitly routed to a sibling in the taxonomy — flagged as boundary gap below) |
| `hermes import` | "Restore a Hermes backup from a zip file." | `<zipfile> [-f/--force]` | — |
| `hermes logs` | View/tail/filter log files | `[log_name] [-n/--lines N] [-f/--follow] [--level LEVEL] [--session ID] [--since DURATION] [--component NAME]` | — |
| `hermes config` | "Show, edit, migrate, and query configuration files." | `show`, `edit`, `get [--json]`, `set`, `unset`, `path`, `env-path`, `check`, `migrate` | **`hermes-configuration`** |
| `hermes pairing` | Approve/revoke messaging pairing codes | `list`, `approve <code>`, `revoke <user>`, `clear-pending` | — |
| `hermes skills` | "Browse, install, publish, audit, and configure skills." | `browse [--source]`, `search [--source]`, `install [--force] [--name]`, `inspect`, `list`, `check`, `update`, `audit`, `uninstall`, `reset [--restore] [--yes]`, `opt-out [--remove] [--yes]`, `opt-in [--sync]`, `publish`, `snapshot`, `tap`, `config` | **`hermes-skills`** |
| `hermes bundles` | Group skills under one `/name` command | `list` (default), `show <name>`, `create <name> [--skill (repeat)] [--description] [--instruction] [--force]`, `delete <name>`, `reload` | `hermes-skills` |
| `hermes curator` | Background skill maintenance | `status`, `run [--background] [--dry-run]`, `backup`, `rollback [--list] [--id] [-y]`, `pause`, `resume`, `pin <skill>`, `unpin <skill>`, `restore <skill>`, `archive <skill>`, `prune`, `list-archived` | `hermes-skills` |
| `hermes memory` | External memory provider setup | `setup`, `status`, `off`; provider-specific commands (e.g. `hermes honcho`) register dynamically | — (no `hermes-memory` sibling in taxonomy) |
| `hermes acp` | "Starts Hermes as an ACP (Agent Client Protocol) stdio server for editor integration." | bare invocation; related entrypoints `hermes-acp`, `python -m acp_adapter` | — |
| `hermes mcp` | Manage MCP server configs / run as MCP server | (none)/`picker`, `catalog`, `install <name>`, `serve [-v/--verbose]`, `add [--url] [--command] [--auth oauth\|header] [--args …]`, `remove`/`rm`, `list`/`ls`, `test`, `configure`/`config`, `login <name>` | — (no `hermes-mcp` sibling in taxonomy) |
| `hermes plugins` | Unified plugin management | (none) = composite UI; `install [--force]`, `update <name>`, `remove`/`rm`/`uninstall <name>`, `enable <name>`, `disable <name>`, `list`/`ls` | — |
| `hermes tools` | Per-platform tool configuration | `[--summary]` | — |
| `hermes computer-use` | cua-driver backend installer | `install [--upgrade]`, `status` | — |
| `hermes pets` | Petdex mascot gallery | `list`, `install`, `select`, `show`, `off`, `scale`, `remove`, `doctor` | — |
| `hermes sessions` | Browse/export/prune/rename/delete sessions | `list`, `browse`, `export [--session-id ID]`, `delete <id>`, `prune [many filters — see quote below]`, `archive`, `stats`, `rename <id>`, `optimize`, `optimize-storage`, `repair`, `repair-routing [--apply] [--max-gap-seconds N]`, `recover`, `retitle-skills [--apply]` | **`hermes-sessions`** |
| `hermes insights` | Token/cost/activity analytics | `[--days N] [--source platform]` | — |
| `hermes claw` | OpenClaw → Hermes migration | `migrate [--dry-run] [--preset full\|user-data] [--overwrite] [--migrate-secrets] [--no-backup] [--source] [--workspace-target] [--skill-conflict skip\|overwrite\|rename] [--yes]` | — |
| `hermes import-agent` | Import Claude Code / Codex CLI setup | `[claude-code\|codex] [--source] [--dry-run] [--overwrite] [--yes/-y]` | — |
| `hermes serve` | Headless backend server (JSON-RPC/WebSocket) | Same options as `hermes dashboard` (`--host`, `--port`, `--insecure`, `--skip-build`, `--stop`, `--status`) | — |
| `hermes dashboard` | Web dashboard | `--port` (9119), `--host` (127.0.0.1), `--no-open`, `--insecure` (deprecated/no-op), `--skip-build`, `--isolated`, `--stop`, `--status`; subcommand `register [--name] [--redirect-uri] [--portal-url]` | — |
| `hermes profile` | Multi-profile management | see § 4.3 below | — (this skill; profile *semantics* like description-based kanban routing touch `hermes-kanban`) |
| `hermes completion` | Shell completion scripts | positional `[bash\|zsh\|fish]` | — |
| `hermes version` | Show version info | none | — |
| `hermes update` | Pull latest code + reinstall deps | `--gateway` (internal), `--check`, `--no-backup`, `--backup`, `--yes`/`-y`; **also** (from `getting-started/updating`, not in `cli-commands`): `--branch <name>`, `--force` (Windows lock override), `--force-venv` | — |
| `hermes uninstall` | Remove Hermes | `[--full] [--gui] [--dry-run] [--yes]` | — |
| `hermes portal` | Nous Portal status / Tool Gateway routing | `status` (default), `open`, `tools` | `hermes-configuration` |
| `hermes photon` | **UNDOCUMENTED command family — absent from `cli-commands` entirely.** Source: `/docs/user-guide/messaging/photon` (prose only, no flags table). | `setup` (device-login wizard, 6 steps); `telemetry on\|off` (mentioned once, paired with `PHOTON_TELEMETRY` env var) | — |
| `hermes journey` (aliases `learning`, `memory-graph`) | Learning journey timeline | `[list\|delete <id>\|edit]` | — |

### 4.3 `hermes profile` subcommand detail (from `profile-commands`, fuller than `cli-commands`)

| Subcommand | Signature | Key options |
|---|---|---|
| `list` | `hermes profile list` | none; active profile marked `*` |
| `use` | `hermes profile use <name>` | none |
| `create` | `hermes profile create <name> [options]` | `--clone`, `--clone-all`, `--clone-from <name>`, `--no-alias`, `--description "<text>"`, `--no-skills` |
| `describe` | `hermes profile describe [<name>] [options]` | `--text "<text>"`, `--auto`, `--overwrite`, `--all` |
| `delete` | `hermes profile delete <name> [options]` | `--yes`/`-y` |
| `show` | `hermes profile show <name>` | none |
| `alias` | `hermes profile alias <name> [options]` | `--remove`, `--name <alias>` |
| `rename` | `hermes profile rename <old> <new>` | none |
| `export` | `hermes profile export <name> [options]` | `-o/--output <path>` |
| `import` | `hermes profile import <archive> [options]` | `--name <name>` |
| `install` (distribution) | `hermes profile install <source> [--name] [--alias] [--force] [--yes]` | git URL or local dir with `distribution.yaml` |
| `update` (distribution) | `hermes profile update <name> [--force-config] [--yes]` | preserves user data; `--force-config` resets `config.yaml` |
| `info` (distribution) | `hermes profile info <name>` | prints manifest — name/version/hermes_requires/author/env vars/source/Installed timestamp |

Global: `hermes -p <name> <command>` / `hermes --profile <name> <command>` — QUOTE: "Global flag to run any Hermes command under a specific profile without changing the sticky default."

### 4.4 Slash-command registry — per-surface availability

Legend: **CLI** = interactive classic CLI, **TUI** = modern TUI (inherits CLI set unless noted), **MSG** = messaging gateway (Telegram/Discord/Slack/WhatsApp/Signal/Email/Home Assistant/Teams/etc.), **U** = undocumented cell (not stated for that surface).

| Command | CLI | TUI | MSG | Notes / aliases |
|---|---|---|---|---|
| `/new [name]` | ✅ | ✅ | ✅ | alias `/reset`; destructive-confirm eligible |
| `/clear` | ✅ | U (CLI-only per Notes list) | ❌ | destructive-confirm eligible |
| `/history` | ✅ | U | ❌ (CLI-only per Notes) | |
| `/save` | ✅ | U | ❌ (CLI-only per Notes) | |
| `/prompt` (`/compose`) | ✅ | U | ❌ (CLI-only per Notes) | opens `$EDITOR` |
| `/retry` | ✅ | ✅ | ✅ | |
| `/undo` | ✅ | ✅ | ✅ | destructive-confirm eligible |
| `/title` | ✅ | ✅ | ✅ | |
| `/compress` | ✅ | ✅ | ✅ | |
| `/rollback` | ✅ | ✅ | ✅ | listed in "works in both" Notes line |
| `/diff` | ✅ | ✅ | ✅ | |
| `/snapshot`/`/snap` | ✅ | U | ❌ (CLI-only per Notes) | |
| `/stop` | ✅ | ✅ | ✅ | |
| `/queue`/`/q` | ✅ | ✅ | ✅ | |
| `/steer` | ✅ | ✅ | ✅ | |
| `/goal` | ✅ | ✅ (implied, no exclusion) | ✅ | |
| `/subgoal` | ✅ | ✅ | ✅ | |
| `/heartbeat`/`/hb` | ✅ | ✅ | ✅ (Slack: `/hermes heartbeat …`) | |
| `/refine` | ✅ | ✅ | ✅ (Slack: `/hermes refine …`) | |
| `/moa` | ✅ | ✅ | ✅ | |
| `/resume [name]` | ✅ | ✅ | ✅ | |
| `/sessions` | ✅ | ✅ (TUI: live switcher, alias `/switch`) | ✅ | messaging table also shows `/sessions [all] [search]` |
| `/egress [status]` | ✅ | ✅ | ✅ | "Works in CLI, TUI, Desktop chat, and messaging gateway" |
| `/redraw` | ✅ | U | ❌ (CLI-only per Notes) | |
| `/status` | ✅ | ✅ | ✅ | |
| `/context`/`/ctx` | ✅ | ✅ | ✅ | |
| `/agents`/`/tasks` | ✅ | ✅ (TUI: observability overlay) | ✅ | |
| `/background`/`/bg`/`/btw` | ✅ | ✅ | ✅ | |
| `/branch [name]`/`/fork` | ✅ | ✅ | ✅ | |
| `/journey`/`/learning`/`/memory-graph` | ✅ | ✅ (overlay) | ❌ ("Not available on messaging platforms") | also desktop app (Star Map panel) |
| `/handoff` | ✅ (explicitly "CLI only") | U | n/a (target, not source) | hands session to a messaging platform |
| `/config` | ✅ | ✅ (shared config) | U | |
| `/model` | ✅ | ✅ (modal picker) | ✅ | |
| `/codex-runtime` | ✅ | U | ✅ | |
| `/personality` | ✅ | ✅ | ✅ | |
| `/verbose` | ✅ (CLI-only by default) | U | opt-in via `display.tool_progress_command: true` | |
| `/focus` | ✅ | U | U | |
| `/fast` | ✅ | U | ✅ | listed "works in both" |
| `/reasoning` | ✅ | U | ✅ | |
| `/skin` | ✅ (CLI-only per Notes) | ✅ (live preview) | ❌ | |
| `/statusbar`/`/sb` | ✅ (CLI-only per Notes) | U | ❌ | |
| `/battery` | ✅ (CLI-only per Notes) | U | ❌ | |
| `/voice` | ✅ | ✅ | ✅ | |
| `/yolo` | ✅ | ✅ | ✅ | |
| `/approvals` | ✅ | U | U | |
| `/footer` | ✅ | U | ✅ | |
| `/busy` | ✅ ("CLI-only") | U | n/a | |
| `/indicator` | ✅ ("CLI-only") | U | n/a | |
| `/timestamps` | ✅ ("CLI-only") | U | n/a | |
| `/wake` | ✅ ("CLI-only") | U | n/a | |
| `/tools` | ✅ (CLI-only per Notes) | U | ❌ | |
| `/toolsets` | ✅ (CLI-only per Notes) | U | ❌ | |
| `/browser` | ✅ (CLI-only per Notes) | U | ❌ | |
| `/skills` | ✅ (search/browse/install: CLI-only) | U | ✅ for `pending/approve/reject/diff/approval` subcommands only, when gate is on | |
| `/memory` | ✅ | U | ✅ | "works on both surfaces" |
| `/bundles` | ✅ | U | ✅ | |
| `/learn` | ✅ | ✅ | ✅ | "Works in the CLI, the messaging gateway, the TUI, and the dashboard Skills page" |
| `/init` | ✅ | ✅ | ✅ | |
| `/cron` | ✅ (CLI-only per Notes) | U | ❌ | |
| `/suggestions`/`/suggest` | ✅ | U | ✅ | |
| `/blueprint`/`/bp` | ✅ | U | ✅ | |
| `/curator` | ✅ | U | ✅ | |
| `/kanban` | ✅ | U | ✅ (bypasses running-agent guard) | |
| `/reload-mcp` | ✅ | U | ✅ | |
| `/reload-skills` | ✅ | U | ✅ | |
| `/reload` | ✅ (CLI-only per Notes) | ✅ (TUI-owned: re-reads `.env`) | ❌ | |
| `/plugins` | ✅ (CLI-only per Notes) | U | ❌ | |
| `/pet` | ✅ (CLI-only per Notes) | U | ❌ | |
| `/hatch`/`/generate-pet` | ✅ (CLI-only per Notes) | U | ❌ | |
| `/help` | ✅ | ✅ (overlay) | ✅ | |
| `/version` | ✅ | U | U | |
| `/whoami` | ✅ | U | ✅ | |
| `/usage` | ✅ | ✅ (rich panel) | ✅ | |
| `/topup` | ✅ | U | ✅ | replaces old `/credits`/`/billing` |
| `/subscription`/`/upgrade` | ✅ ("CLI only") | U | ❌ | |
| `/insights` | ✅ | U | ✅ | |
| `/update` | ✅ | U | ✅ | |
| `/platforms`/`/gateway` | ✅ ("CLI-only summary view") | U | n/a (see `/platform` below — different, messaging-only command) | |
| `/paste` | ✅ (CLI-only per Notes) | U | ❌ | |
| `/copy [n]` | ✅ ("CLI-only") | U | ❌ | |
| `/image` | ✅ (CLI-only per Notes) | U | ❌ | |
| `/debug` | ✅ | U | ✅ | |
| `/profile` | ✅ | U | U | |
| `/quit`/`/exit` | ✅ | U | n/a | destructive with `--delete` |
| `/<skill-name>` | ✅ | ✅ | ✅ | dynamic, one per installed skill |
| `/sethome`/`/set-home` | n/a | n/a | ✅ ("messaging-only") | |
| `/topic` | n/a | n/a | ✅ (Telegram DM only, "messaging-only") | |
| `/platform <list\|pause\|resume>` | n/a | n/a | ✅ ("messaging-only") | distinct from `/platforms` above |
| `/commands [page]` | n/a | n/a | ✅ ("messaging-only") | |
| `/approve`/`/deny` | n/a | n/a | ✅ ("messaging-only") | |
| `/restart` | n/a | n/a | ✅ ("messaging-only") | |
| `/start` | n/a | n/a | ✅ | platform-protocol handshake ack, silent |
| `/details` | n/a | ✅ (TUI-owned) | n/a | `[hidden\|collapsed\|expanded\|cycle\|reset]` |
| `/mouse` | n/a | ✅ (TUI-owned) | n/a | `[on\|off\|toggle\|wheel\|buttons\|all]` |
| `/switch` | n/a | ✅ (TUI alias of `/sessions`) | n/a | |
| `/terminal-setup` | n/a | ✅ (TUI-mentioned) | n/a | installs VS Code/Cursor/Windsurf terminal keybindings |

**Quick Commands** (user-defined, config-driven, work identically on CLI and messaging): declared under `quick_commands:` in `config.yaml` with `type: exec` (shell command) or `type: alias` (points at another slash command). QUOTE: "String-only prompt shortcuts are not supported as quick commands."

**Custom model aliases**: `model_aliases:` (full form: pin model/provider/base_url) or `hermes config set model.aliases.<name> <provider>/<model>` (short form). Reachable as `/model <alias>` on both CLI and messaging.

### 4.5 CLI-relevant environment variables

Only variables that map to a CLI flag, override CLI behavior, or gate CLI/TUI surfaces (full messaging/provider-key catalog is out of scope for this skill — see `hermes-configuration`).

| Variable | Maps to / effect | Default |
|---|---|---|
| `HERMES_HOME` | Overrides `~/.hermes` config directory; scopes gateway PID file + systemd service name | `~/.hermes` |
| `HERMES_INFERENCE_MODEL` | `-m`/`--model` equivalent; "Override model name at process level (takes priority over `config.yaml` for the session)" | unset |
| `HERMES_YOLO_MODE` | `--yolo` / `/yolo` equivalent | unset (off) |
| `HERMES_ACCEPT_HOOKS` | `--accept-hooks` equivalent | unset |
| `HERMES_IGNORE_USER_CONFIG` | `--ignore-user-config` equivalent | unset |
| `HERMES_IGNORE_RULES` | `--ignore-rules` equivalent | unset |
| `HERMES_SAFE_MODE` | Set automatically by `--safe-mode`; also independently settable | unset |
| `HERMES_TUI` | `--tui` equivalent | unset (0) |
| `HERMES_TUI_DIR` | Points at a prebuilt `ui-tui/` dir (skips first-launch `npm install`) | unset |
| `HERMES_TUI_RESUME` | Auto-resume TUI session on launch (`1` = most recent, or a session ID) | unset |
| `HERMES_TUI_THEME` | Force TUI theme: `light`/`dark`/6-char hex | auto-detect |
| `HERMES_TUI_GATEWAY_URL` | Internal-only wiring for dashboard's embedded TUI child; QUOTE: "There is no general 'point any TUI at any standalone gateway port' mode." | n/a |
| `HERMES_KANBAN_BOARD` | `hermes kanban --board` equivalent; pins active board for the process | `default` |
| `HERMES_KANBAN_HOME`/`HERMES_KANBAN_DB`/`HERMES_KANBAN_WORKSPACES_ROOT` | Override kanban root/db-file/workspaces-root paths | derived from `HERMES_HOME` |
| `HERMES_KANBAN_DISPATCH_IN_GATEWAY` | Runtime override for `kanban.dispatch_in_gateway` | unset (config governs) |
| `HERMES_KANBAN_TASK` | Set by the dispatcher on spawned workers; "Don't set manually." | n/a |
| `HERMES_MODEL` | "Override model name at process level (used by cron scheduler; prefer `config.yaml` for normal use)" | unset |
| `HERMES_MAX_ITERATIONS` | Same knob as `hermes chat --max-turns` / `agent.max_turns` | 500 |
| `HERMES_QUIET` | Suppress non-essential output — CLI-relevant analog of `-Q`/`--quiet` | `false` |
| `HERMES_SESSION_ID` | Auto-exported into every tool subprocess; "You should not set this manually" | n/a |
| `AI_AGENT` / `HERMES_AGENT` | Child-process attribution markers; "Don't set manually." | n/a |
| `HERMES_WRITE_SAFE_ROOT` | Sandbox root(s) for `write_file`/`patch`, `os.pathsep`-separated | unset |
| `HERMES_DISABLE_FILE_STATE_GUARD` | Disables the "file changed since you read it" guard | unset |
| `HERMES_GIT_BASH_PATH` | Windows-only `bash.exe` override for terminal tool | auto-discovered |
| `HERMES_DISABLE_WINDOWS_UTF8` | Windows-only stdio-shim disable | unset |
| `SESSION_IDLE_MINUTES` / `SESSION_RESET_HOUR` | Session reset policy | `1440` / `4` |
| `TERMINAL_CWD` | Deprecated gateway/cron cwd override; "CLI still uses the launch directory" | unset |
| `HERMES_GATEWAY_NO_SUPERVISE` | `hermes gateway run --no-supervise` equivalent (s6 Docker image) | unset |

undocumented cell note: env-vars page states plainly "there are no environment variables for" context compression, fallback providers, and provider routing — those are `config.yaml`-only by explicit design, not an omission.

---

## 5. Normative Statements

| Exact quote | Page + section | Why it matters for stage 080 |
|---|---|---|
| "`hermes -z` is the purest one-shot entry point: single prompt in, final response text out, nothing else on stdout or stderr." | `cli-commands` § `hermes -z — scripted one-shot` | This is the correct primitive for stage 080 shell/CI wrappers that need to capture a clean agent answer without banner/tool-preview noise. |
| "Same agent, same tools, same skills — just strips every interactive / cosmetic layer. If you need tool output in the transcript too, use `hermes chat -q` instead; `-z` is explicitly for 'I only want the final answer'." | `cli-commands` § `hermes -z` | Prevents mis-selecting `-z` when a script actually needs tool-call transcripts. |
| "`hermes -z '…' --usage-file /path/report.json` writes a machine-readable usage report after the run… The report is written even when the run fails, so batch pipelines can always account for spend." | `cli-commands` § `--usage-file` | Direct fit for stage 080's per-task cost accounting in kanban/dispatcher pipelines. |
| "`--ignore-user-config` … Ignore `~/.hermes/config.yaml` and fall back to built-in defaults. Credentials in `.env` are still loaded." | `cli-commands` § Global options | Important for isolated/reproducible CI invocations — secrets still load even in isolation mode. |
| "`--safe-mode` … Troubleshooting mode: disable ALL customizations — user config, rules/memory injection, plugins, shell hooks, and MCP servers (implies `--ignore-user-config` and `--ignore-rules`). Use to isolate whether a problem comes from your setup or from Hermes itself." | `cli-commands` § `hermes chat` options | Correct diagnostic tool to recommend before assuming a Hermes bug in stage 080 scripts. |
| "`--worktree` … Start in an isolated git worktree for parallel-agent workflows." | `cli-commands` § Global options | Relevant to any stage 080 pattern that runs multiple concurrent Hermes invocations against the same repo. |
| "Board resolution order (highest precedence first): `--board <slug>` flag → `HERMES_KANBAN_BOARD` env var → `~/.hermes/kanban/current` file → `default`." | `cli-commands` § `hermes kanban` | Exact precedence order needed to correctly script multi-board kanban dispatch from stage 080 automation. |
| "This is the human / scripting surface. Agent workers spawned by the dispatcher drive the board through a dedicated `kanban_*` toolset… instead of shelling to `hermes kanban`." | `cli-commands` § `hermes kanban` | Clarifies `hermes kanban` CLI is for humans/orchestration scripts, not for worker agents themselves — avoids stage 080 scripts wrongly assuming workers shell out to the CLI. |
| "All actions are also available as a slash command in the gateway (`/kanban …`), with the same argument surface — including `boards` subcommands and the `--board` flag." | `cli-commands` § `hermes kanban` | Confirms CLI/messaging parity for kanban control — relevant when stage 080 demo drives kanban from a chat surface instead of a terminal. |
| "`--external-supervisor` is a restart-policy contract: an in-chat restart or service-restart update exits with status `75`, so the wrapper's supervisor must relaunch the gateway after that nonzero exit." | `cli-commands` § `hermes gateway` | A concrete, non-obvious exit-code contract a systemd/launchd unit file MUST honor — critical if stage 080 ever manages a Hermes gateway as a supervised service. |
| "Exit codes: `0` on success, `1` on delivery/backend failure, `2` on usage errors." | `cli-commands` § `hermes send` | One of the few CLI commands with fully documented exit codes — usable as a scripting pattern to imitate for other stage 080 wrappers. |
| "Exit codes. `0` on success, `1` on pull/install/post-install errors, `2` on unexpected working-tree changes that block `git pull`." | `cli-commands` § `hermes update` | Same — needed if stage 080 automates unattended `hermes update` runs and must branch on exit code. |
| "The update ignores `SIGHUP`, so closing your SSH session or terminal window no longer kills it mid-install." | `getting-started/updating` § If your terminal disconnects mid-update | Relevant for remote/headless stage 080 update automation — no need to wrap in `screen`/`tmux`. |
| "`hermes update` will refuse to run if it detects another `hermes.exe` process holding the venv's entry-point executable open" (Windows) … "Override with `hermes update --force`" | `getting-started/updating` § Windows: another hermes.exe is running | `--force` here is undocumented in `cli-commands`' own `hermes update` options table — a genuine cross-page gap worth carrying into the skill. |
| "A second, separate guard refuses to touch the venv while any process is running from its Python interpreter… This guard is not bypassed by `--force`… use the explicit `hermes update --force-venv`." | `getting-started/updating` § Windows: another hermes.exe is running | `--force-venv` is a second, distinct escape hatch from `--force` — conflating them would produce incorrect automation guidance. |
| "`--branch <name>`… If your local checkout is on a different branch, Hermes auto-stashes any uncommitted work, switches HEAD to the target branch, and then pulls." | `getting-started/updating` § Updating against a non-default branch | Needed if stage 080 ever pins Hermes to a release-candidate or custom branch. |
| "1. `--accept-hooks` flag on the CLI (e.g. `hermes --accept-hooks chat`) … Non-TTY runs (gateway, cron, CI) need one of these three — otherwise any newly-added hook silently stays un-registered and logs a warning." | `user-guide/features/hooks` § Consent model | Directly load-bearing for stage 080: any CI/headless Hermes invocation with shell hooks configured MUST set one of the three escape hatches or hooks silently no-op. This flag is missing from `cli-commands`' own Global options table. |
| "`command_allowlist` … These patterns are loaded at startup and silently approved in all future sessions." | `user-guide/security` § Permanent Allowlist | Security-relevant default behavior a stage 080 reviewer must understand before recommending `command_allowlist` entries. |
| "Setting `approvals.mode: off` disables all safety prompts. Use only in trusted environments (CI/CD, containers, etc.)." | `user-guide/security` § Approval Modes | Direct CI/CD guidance applicable to stage 080 automated agent runs. |
| "`off` … Disable all approval checks — equivalent to running with `--yolo`." | `user-guide/security` § Approval Modes table | Confirms `approvals.mode: off` and `--yolo` are behaviorally equivalent — important so a reviewer doesn't treat them as different risk tiers. |
| "The hardline blocklist… trips before the approval layer even sees the command, and there's no override flag." | `user-guide/security` § Hardline Blocklist | Establishes an absolute floor that `--yolo`, `approvals.mode: off`, and allowlists cannot bypass — relevant to any stage 080 claim about "fully autonomous, no prompts" runs. |
| "Nothing is ever applied automatically — the default run is read-only; only an explicit `--apply N[,M...]` writes to `config.yaml`." | `user-guide/security` § Mining Approval History | Documents `hermes approvals suggest` safety default — this whole subcommand is absent from `cli-commands`. |
| "`hermes completion <bash\|zsh\|fish>`… After installation, tab completion works for: `hermes profile <TAB>`, `hermes profile use <TAB>`, `hermes -p <TAB>`." | `profile-commands` § `hermes completion` | Confirms shell completion is profile-name-aware, not just static-subcommand-aware — relevant if stage 080 documents CLI ergonomics. |
| "`hermes_requires` supports `>=`, `<=`, `==`, `!=`, `>`, `<`, or a bare version (treated as `>=`). Install fails with a clear error if the current Hermes version doesn't satisfy the spec." | `profile-commands` § Distribution manifest | Relevant if stage 080 ships a profile distribution pinned to a Hermes version range. |
| "There is no general 'point any TUI at any standalone gateway port' mode… Setting `HERMES_TUI_GATEWAY_URL` to that port will 404." | `user-guide/tui` § How the TUI talks to its gateway | Important negative statement — prevents a stage 080 script from wrongly trying to wire a remote TUI via that env var. |
| "The classic CLI remains the shipped default… Explicit flags always win — run `hermes --cli` to drop back to the classic REPL for a single invocation, or `hermes --tui`/`HERMES_TUI=1` to force the TUI when the config default is `cli`." | `user-guide/tui` § Launch | Precedence rule (explicit flag > env var > config default) needed for correct troubleshooting guidance. |
| "Shell mode is CLI-only. Gateway platforms (Discord, Telegram, Slack) and cron runs ignore it — those users already have their own shells." | `user-guide/cli` § `!` Shell Mode | Correct scoping — `!` is not a general Hermes feature, only an interactive-CLI convenience. |
| "Commands support prefix matching: typing `/h` resolves to `/help`, `/mod` resolves to `/model`. When a prefix is ambiguous (matches multiple commands), the first match in registry order wins." | `slash-commands` § Alias Resolution | Documents non-obvious resolution order — relevant if stage 080 scripts programmatically send short slash prefixes. |
| "Slack itself blocks native slash commands inside message threads… Inside a Slack thread, use the `!` prefix instead — `!stop`, `!new`, `!status`" | `slash-commands` § Messaging slash commands | Platform-specific gotcha that would otherwise cause a stage 080 Slack integration demo to silently fail inside threads. |
| "If `allow_admin_from` is unset for a scope, that scope stays in unrestricted backward-compat mode — every allowed user can run every command." | `slash-commands` § Permissions and admin/user split | Security-relevant default a reviewer must flag before recommending any messaging-gateway command-gating configuration. |

---

## 6. Official Examples (verbatim)

**`hermes -z` scripted one-shot** (`cli-commands` § `hermes -z`):
```bash
hermes -z "What's the capital of France?"
# → Paris.
# Parent scripts can cleanly capture the response:
answer=$(hermes -z "summarize this" < /path/to/file.txt)
```

**`--usage-file`** (`cli-commands` § `--usage-file`):
```bash
hermes -z "summarize this repo" --usage-file /tmp/usage.json
jq .estimated_cost_usd /tmp/usage.json
```

**`hermes kanban` multi-board** (`cli-commands` § `hermes kanban`):
```bash
# Create a second board and put a task on it without switching away.
hermes kanban boards create atm10-server --name "ATM10 Server" --icon 🎮
hermes kanban --board atm10-server create "Restart server" --assignee ops
# Switch the active board for subsequent calls.
hermes kanban boards switch atm10-server
hermes kanban list                  # shows atm10-server tasks
# Archive a board (recoverable) or hard-delete it.
hermes kanban boards rm atm10-server
hermes kanban boards rm atm10-server --delete
```

**`hermes send`** (`cli-commands` § `hermes send`):
```bash
hermes send --to telegram "deploy finished"
echo "RAM 92%" | hermes send --to telegram:-1001234567890
hermes send --to discord:#ops --file /tmp/report.md
hermes send --to slack:#eng --subject "[CI]" --file build.log
hermes send --list                  # all platforms
hermes send --list telegram         # filter by platform
```

**`hermes profile` workflow** (`profile-commands` § `hermes -p`):
```bash
hermes -p work chat -q "Check the server status"
hermes --profile dev gateway start
hermes -p personal skills list
hermes -p work config edit
```

**`hermes completion`** (`profile-commands` § `hermes completion`):
```bash
hermes completion bash >> ~/.bashrc
hermes completion zsh >> ~/.zshrc
hermes completion fish > ~/.config/fish/completions/hermes.fish
source ~/.bashrc
```

**Resume flows** (`user-guide/cli` § Resuming Sessions):
```bash
hermes --continue                          # Resume the most recent CLI session
hermes -c                                  # Short form
hermes -c "my project"                     # Resume a named session (latest in lineage)
hermes --resume 20260225_143052_a1b2c3     # Resume a specific session by ID
hermes --resume "refactoring auth"         # Resume by title
hermes --resume latest                     # Resume the most recent session (same as -c)
hermes --resume latest --in ./my-project   # Latest session for ./my-project's workspace
hermes -r 20260225_143052_a1b2c3           # Short form
```

**Approval-history mining** (`user-guide/security` § Mining Approval History):
```bash
hermes approvals suggest            # dry run — prints a numbered proposal
hermes approvals suggest --apply 1,3  # merge picks into command_allowlist
hermes approvals suggest --json     # machine-readable output
```

**CLI approval prompt UI** (`user-guide/security` § Approval Flow (CLI)):
```text
  ⚠️  DANGEROUS COMMAND: recursive delete
      rm -rf /tmp/old-project
      [o]nce  |  [s]ession  |  [a]lways  |  [d]eny
      Choice [o/s/a/D]:
```

**Windows update lock error** (`getting-started/updating` § Windows: another hermes.exe is running):
```text
$ hermes update
✗ Another hermes.exe is running:
    PID 12345  hermes.exe
  Updating now would fail to overwrite ...\venv\Scripts\hermes.exe because
  Windows blocks REPLACE on a running executable.
  Close Hermes Desktop, exit any open `hermes` REPLs, and
  stop the gateway (`hermes gateway stop`) before retrying.
  Override with `hermes update --force` if you've already
  confirmed those processes will not write to the venv.
```

**Recovery Toolkit sequence** (`getting-started/quickstart` § Recovery Toolkit):
```text
1. hermes doctor
2. hermes model
3. hermes setup
4. hermes sessions list
5. hermes --continue
6. hermes gateway status
```

**TUI launch/env** (`user-guide/tui` § Launch):
```bash
hermes --tui --dev
export HERMES_TUI=1
hermes          # now uses the TUI
hermes chat     # same
```

---

## 7. Recommendations Found (verbatim best-practice / recommendation language)

- "Rule of thumb: if Hermes cannot complete a normal chat, do not add more features yet. Get one clean conversation working first, then layer on gateway, cron, skills, voice, or routing." — `getting-started/quickstart` § The fastest path
- "For most first-time users: choose a provider, accept the defaults unless you know why you're changing them." — `getting-started/quickstart` § 2. Choose a Provider
- "It's the recommended way to run Hermes interactively." (referring to the TUI) — `user-guide/tui` intro
- "WSL users — Use `hermes gateway run` instead of `hermes gateway start`— WSL's systemd support is unreliable. Wrap it in tmux for persistence." — `cli-commands` § `hermes gateway`
- "Use `/goal status`, `/goal pause`, `/goal resume`, `/goal clear`" pattern guidance implied by subcommand naming convention across multiple families — not a direct recommendation quote, omitted from this section as PARAPHRASE-only.
- "You no longer need to wrap `hermes update` in `screen` or `tmux` to survive a terminal drop." — `getting-started/updating` § If your terminal disconnects mid-update
- "Use `hermes config edit` to review or remove patterns from your permanent allowlist." — `user-guide/security` § Permanent Allowlist
- "Deny rules are a guardrail against an honest-but-wrong agent… They are not a sandbox against a deliberately adversarial process — for that, use an isolated backend (Docker, Modal) or an egress-restricted environment." — `user-guide/security` § User-Defined Deny Rules (Threat model box)
- "Use git tags for versioned releases — recipients who clone `HEAD` get your latest state, and you can always bump `version:` in the manifest." — `profile-commands` § Publishing a distribution
- "Moving to a new machine instead? Update backups protect an in-place update. If you're migrating your whole setup to different hardware, use `hermes backup` + `hermes import` instead." — `getting-started/updating` § Full pre-update backup callout

---

## 8. Boundary Notes

- **`hermes kanban`** — full command tree captured above; task lifecycle states, dispatcher/worker behavior, and orchestrator fan-out semantics belong to **`hermes-kanban`**.
- **`hermes hooks`** — command surface captured (`list`, `test`, `revoke`, `doctor`, plus the `--accept-hooks` global flag); event catalog, payload shapes, and the consent-model architecture belong to **`hermes-hooks`**.
- **`hermes skills`, `hermes bundles`, `hermes curator`** — command surfaces captured; progressive-disclosure design, skill authoring, staleness/archival logic, and write-approval gating semantics belong to **`hermes-skills`**.
- **`hermes sessions`, `hermes checkpoints`** — command surfaces captured; storage architecture (SQLite `state.db`, FTS5, lineage, shadow-git checkpoint store) and repair/recovery internals belong to **`hermes-sessions`**. Note: no sibling skill in the routing table is explicitly named for checkpoints — this capture assumed `hermes-sessions` as the closest owner since checkpoints/`​/rollback` are session-adjacent state; **flag for reviewer confirmation**.
- **`hermes config`, `hermes auth`, `hermes model`, `hermes setup`, `hermes portal`, `hermes migrate`, `hermes fallback`, `hermes moa`** — command surfaces captured; config precedence rules, credential-pool rotation logic, and provider-routing semantics belong to **`hermes-configuration`**.
- **`hermes profile`** — command surface captured in full (§ 4.3); profile-description-driven kanban routing touches `hermes-kanban`; no dedicated `hermes-profiles` sibling skill exists in the routing table, so this skill (`hermes-cli`) is the most complete owner of profile *command* facts, while `hermes-configuration` should own config-precedence facts about profiles (per-profile `config.yaml`/`.env` isolation).
- **`hermes mcp`, `hermes memory`, `hermes plugins`, `hermes cron`** — command surfaces fully captured here; no sibling skill for these subsystems appears in the current `hermes-*` skill-group taxonomy (only `hermes-about`, `hermes-configuration`, `hermes-managed-scope`, `hermes-skills`, `hermes-hooks`, `hermes-kanban`, `hermes-sessions`, `hermes-cli` exist). Deep semantics for these four families currently have **no owning skill** — flagged for the reviewer as a possible taxonomy gap, not something this run should fill.
- **`hermes egress`, `hermes secrets`** — command surfaces captured; credential-injection architecture (iron-proxy, Bitwarden Secrets Manager integration) has no owning `hermes-*` skill either — same taxonomy-gap flag as above.

---

## 9. Gaps & Open Questions

1. **`hermes photon` command family is entirely absent from `cli-commands`.** Only `hermes photon setup` (inline prose, 6-step flow) and a single passing mention of `hermes photon telemetry on|off` were found, both on `/docs/user-guide/messaging/photon`. No flags, no exit codes, no dedicated reference table. The reviewer should decide whether to document this from the messaging page (acceptable per assignment rules — same product, official page) or flag it upstream as a documentation gap in Hermes' own reference.
2. **`--accept-hooks` is missing from `cli-commands`' Global options table**, discoverable only via the Event Hooks feature page and the environment-variables page's description of `HERMES_ACCEPT_HOOKS`. Official docs do not explain *why* it's scoped where it is (global vs. `chat`-only) — inferred as global by the literal example `hermes --accept-hooks chat`, which places it before the subcommand.
3. **`hermes approvals` has only one documented subcommand (`suggest`)** despite the `cli-commands` top-level table describing it generically as "Approval-prompt tools." No official page documents whether other subcommands exist; treat the table as exhaustive for now but flag as unconfirmed completeness.
4. **`hermes update --force` and `--force-venv` are Windows-specific escape hatches documented only in prose** (`getting-started/updating`), not in `cli-commands`' `hermes update` options table alongside `--gateway`/`--check`/`--no-backup`/`--backup`/`--yes`. No official source states whether `--branch`, `--force`, or `--force-venv` are cross-platform-safe to combine with `--check` or `--gateway`; not tested, not documented.
5. **`hermes whatsapp-cloud` and `hermes whatsapp` (Baileys)** are both described only as bare, flagless wizard invocations across every page checked. It is not documented whether either accepts any non-interactive/scripted flags (e.g. for CI-driven pairing) — likely genuinely interactive-only, but the docs never say so explicitly (absence of a flags table is the only evidence).
6. **No official page documents exit codes for the vast majority of `hermes` subcommands.** Only `hermes send` (0/1/2) and `hermes update` (0/1/2) have documented exit-code tables. A skill or downstream automation that branches on exit codes for any other command (`hermes doctor`, `hermes checkpoints`, `hermes kanban dispatch`, etc.) has no official contract to cite.
7. **Dynamic slash commands from plugins** (`ctx.register_command()`, confirmed on `/docs/user-guide/features/plugins`) mean the slash-command registry in § 4.4 is the *built-in* set, not an absolute ceiling — a given install can have additional commands from active plugins. No official page provides a way to enumerate plugin-added commands from the CLI reference itself (would need `/help` at runtime).
8. **`hermes cron`'s `cron.provider` pluggability** (mentioned in passing in `cli-commands`: "name a custom provider under `plugins/cron/<name>/` or `$HERMES_HOME/plugins/<name>/`") is not elaborated anywhere in the reference or feature pages read for this capture — the shape of a custom cron provider plugin is undocumented in the pages this skill is scoped to.
9. **`hermes profile describe --all --auto` model configuration** references `auxiliary.profile_describer` in `config.yaml`, and several other commands reference `auxiliary.*` config keys (`auxiliary.triage_specifier`, `auxiliary.kanban_decomposer`, `auxiliary.compression`) — these are `hermes-configuration` territory and were not chased per the assignment's "don't chase overlaps" instruction, but the reviewer should confirm `hermes-configuration`'s capture actually covers all of them, since they're referenced from CLI command descriptions.
10. **No version marker appears on any of the reference/guide pages themselves** — version was obtained only by following the docs' own instruction to check GitHub Releases. If Nous Research ships a CLI change between v0.20.0 and the next release, this dossier's command tree could silently drift with no page-level signal to catch it; recommend the skill's `source-capture.md` record the capture date prominently for future diff-checking rather than relying on a page version string that doesn't exist.
11. **`profile-commands`' own "See also" list points to "FAQ — Profiles section"** which was not separately fetched in this run (deprioritized as likely-redundant); the reviewer may want a final confirmation pass on that FAQ section for any profile CLI facts not already captured in `profile-commands` itself.

---

## 10. Suggested SKILL.md Inputs

*(Input for the reviewer — not an edit. Each line cites the table row / normative statement it derives from.)*

**Key concepts to state:**
- "The CLI command surface (`hermes <command>`) and the slash-command surface (`/command` inside a session) are two distinct registries that partially overlap" — derived from § 4.4 intro quote ("Hermes has two slash-command surfaces, both driven by a central `COMMAND_REGISTRY`") and the general command-vs-slash split visible across §4.2/§4.4.
- "`hermes -z` is the correct primitive for scripted/CI one-shot calls; `hermes chat -q` is the correct primitive when tool-call transcripts must also be captured" — derived from Normative Statements rows 1–2.
- "`--accept-hooks` / `HERMES_ACCEPT_HOOKS=1` / `hooks_auto_accept: true` are the three required escape hatches for any non-interactive Hermes invocation that has shell hooks configured" — derived from Normative Statements hooks-consent row.
- "The hardline command blocklist cannot be bypassed by `--yolo`, `approvals.mode: off`, or any allowlist — there is no override flag" — derived from Normative Statements hardline-blocklist row.
- "Profile selection precedence for scripted calls is `-p`/`--profile` (per-invocation) over the sticky default set by `hermes profile use`" — derived from § 4.1 `--profile` row and § 4.3 `hermes -p` quote.
- "Kanban board selection precedence is `--board` flag → `HERMES_KANBAN_BOARD` → `~/.hermes/kanban/current` → `default`" — derived from Normative Statements kanban board-resolution row.

**Workflow steps to propose:**
1. "Before writing a stage 080 script that invokes `hermes`, check § 4.2's command table for the exact subcommand and flags — do not infer flags from analogous commands (e.g., `hermes migrate` flags do not carry over to `hermes claw migrate`, which has a different flag set)" — derived from § 4.2 rows for `hermes migrate` vs `hermes claw`.
2. "For any headless/CI Hermes invocation, explicitly decide and set the hooks-consent escape hatch (§4.1 `--accept-hooks` row) and the approval mode (§ Normative Statements `approvals.mode: off` row) rather than relying on interactive defaults" — derived from Gaps item 2 and Normative Statements hooks/approval rows.
3. "When scripting kanban dispatch across multiple boards, always pass `--board` explicitly rather than relying on the `HERMES_KANBAN_BOARD` env var or the `current` file, to avoid precedence surprises in CI" — derived from § 4.2 `hermes kanban` board-resolution normative statement.
4. "Prefer `hermes config get/set/unset` over hand-editing `config.yaml`/`.env` from scripts, since `hermes config set` auto-routes secrets vs. non-secret values to the correct file" — derived from § 4.2 `hermes config` row and the Quickstart § "How settings are stored" section.

**Validation commands to propose:**
- `hermes --version` / `hermes version` — confirm CLI is present and get the version string (Normative Statements: "Checking your current version").
- `hermes doctor [--fix]` — first-line diagnostic before assuming a Hermes bug (§ 4.2 `hermes doctor` row; Quickstart Recovery Toolkit step 1).
- `hermes config check` then `hermes config migrate` — detect and fix stale config after an update (§ 4.2 `hermes config` row; `getting-started/updating` tip).
- `hermes update --check` — non-mutating check for available updates, safe to run in CI gating scripts (Normative Statements `hermes update` exit-codes row + `--check` description in § 4.2).
- `hermes completion bash|zsh|fish` — verify shell completion install if a stage 080 dev-container ships Hermes (§ 4.3 `hermes completion` example).

---

## Reviewer addendum (2026-08-12)

### Boundary confirmations requested by the dossier

- `hermes checkpoints` ownership: CONFIRMED as `hermes-sessions` (that
  skill's implemented capture covers the checkpoint subsystem in full).
- `hermes egress` / `hermes secrets` semantics: owned by
  `hermes-managed-scope` (iron-proxy and Bitwarden are captured there) —
  the dossier's taxonomy-gap flag for these two is resolved; the remaining
  unowned families are mcp, memory, plugins, and cron, consistent with
  gaps flagged by earlier captures.

### Product version note (family-wide)

This run established the product version at capture — v0.20.0 "The Herald
Release" (tag v2026.8.3, 2026-08-03) — via the docs' own instruction to
compare against the GitHub releases page. Doc pages themselves carry no
version markers, so all `hermes-*` skill recaptures should diff by capture
DATE; the version string is a point-in-time anchor, not a page property.
