# Official Doc Extraction — hermes-tools

Reviewer-direct capture, 2026-08-12 (single-domain gap-fill; no separate
research dossier). All quotes fetched live from the three official pages;
cross-checked against the hermes-kanban capture's toolset facts.

## Feature page (`/docs/user-guide/features/tools`) — outline

Tools & Toolsets → Available Tools → Using Toolsets → Terminal Backends
(Configuration; Shell startup files and non-interactive commands; Docker;
SSH; Singularity/Apptainer; Modal; Vercel Sandbox; Container Resources;
Container Security) → Background Process Management → Sudo Support.

## Verbatim quotes

- Definition: "Tools are functions that extend the agent's capabilities.
  They're organized into logical toolsets that can be enabled or disabled
  per platform."
- Toolsets Reference intro: "Toolsets are named bundles of tools that
  control what the agent can do. They're the primary mechanism for
  configuring tool availability per platform, per session, or per task."
- Tools Reference intro: "This page documents Hermes' built-in tools,
  grouped by toolset. Availability varies by platform, credentials, and
  enabled toolsets."
- Session-scoped selection: `hermes chat --toolsets "web,terminal"`;
  per-platform interactive config: `hermes tools`.
- X Search: "off by default, opt in via `hermes tools` → 🐦 X (Twitter)
  Search."
- Kanban toolset: "opt-in, not enabled by `all`/`*`" (Toolsets
  Reference) — consistent with the kanban capture's "zero schema
  footprint on normal sessions" and its gating quote ("Registered when
  the agent is either (a) spawned by the kanban dispatcher or (b) running
  in a profile that explicitly enables the `kanban` toolset").
- Sudo: "If a command needs sudo, you'll be prompted for your password
  (cached for the session). Or set `SUDO_PASSWORD` in `~/.hermes/.env`."
- Background processes: pass `background=true` to the terminal tool →
  returns `session_id` and `pid`; manage via the `process` tool with
  actions `list`, `poll`, `wait`, `log`, `kill`, `write`; `pty=true`
  enables interactive CLI tools.

## Toolset inventory (Toolsets Reference, condensed)

~35 named toolsets. Atomic: browser (CDP endpoint required), clarify,
code_execution, cronjob, delegation, discord, discord_admin, feishu_doc,
feishu_drive, file, homeassistant (HASS_TOKEN), computer_use,
context_engine, image_gen, video_gen, kanban (OPT-IN), memory,
desktop_ui (desktop only), project (GUI/desktop only), search,
session_search, skills, spotify, terminal, todo, tts, vision, video
(OPT-IN), web, x_search (OPT-IN, xAI credentials), yuanbao.

Composites: coding = file + terminal + search + web + skills + browser +
todo + memory + session_search + clarify + code_execution + delegation +
vision; debugging = file + terminal + web; safe = read-only research
(image_gen, vision, web extract/search).

Platform presets: hermes-cli (default for interactive CLI sessions; full
set), hermes-cron (same as cli), hermes-acp (drops clarify, cronjob,
image_gen, tts, computer_use, homeassistant, kanban), hermes-api-server
(drops clarify, tts, computer_use, kanban), hermes-webhook (web_search,
web_extract, vision_analyze, clarify only), hermes-discord (adds
discord + discord_admin), hermes-gateway (union of platform toolsets),
hermes-feishu / hermes-yuanbao (platform-specific additions).

Dynamic: `mcp-<server>` generated at runtime per MCP server; plugin
toolsets registered at plugin init; custom toolsets user-defined in
config.yaml.

## Terminal backends (`terminal.backend`)

local ("Run on your machine (default)"), docker ("Isolated containers"),
ssh ("Remote server"), singularity ("HPC containers"), modal ("Cloud
execution"), daytona ("Persistent remote dev environments"),
vercel_sandbox ("Cloud execution with snapshot-backed filesystem
persistence"). Security comparison and container hardening: see
hermes-managed-scope's extraction (Security page).

## Tools Reference structure (~83 tools, 30+ sections)

Per-toolset grouping; sampled entry format — e.g. `read_file`: "Read a
text file with line numbers and pagination. Use this instead of
cat/head/tail in terminal. Output format: 'LINE_NUM|CONTENT'." Counts:
browser 10 (+2 CDP-gated), file 4, kanban 12, spotify 7, desktop_ui 7,
homeassistant 4, video 3, terminal 2, web 2, discord 2, plus 20+ smaller
sections. Use the live page as the per-tool lookup; not reproduced here.

## Open items

See source-capture.md (config.yaml key shape for per-platform toolset
lists not displayed; no comprehensive default-enabled list; per-tool
schemas sampled only).
