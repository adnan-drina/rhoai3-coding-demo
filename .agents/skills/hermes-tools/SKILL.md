---
name: hermes-tools
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "hermes"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Hermes Agent"
description: >
  Use when configuring or reviewing Hermes tools and toolsets for stage
  080: the toolset model (bundles, composites, platform presets, dynamic
  MCP/plugin toolsets), per-profile/per-session tool restriction, terminal
  backends, background process management, and sudo. Do NOT use for
  command approval/security posture (use hermes-managed-scope), the
  hermes tools CLI surface (use hermes-cli), or kanban tool semantics
  (use hermes-kanban).
---

# Hermes Tools & Toolsets

Use this skill when deciding what a Hermes agent or worker profile is
allowed to DO — the capability-restriction layer stage 080 leans on for
orchestrator and worker profiles.

## Source Grounding

Read `references/source-capture.md` for provenance and
`references/official-doc-extraction.md` for the validated extraction.
Official Hermes Agent documentation (Nous Research) is the product
authority: the Tools & Toolsets feature page plus the Toolsets Reference
and Tools Reference pages (~83 built-in tools, ~35 named toolsets).

## Key Concepts

### The toolset model

"Tools are functions that extend the agent's capabilities. They're
organized into logical toolsets that can be enabled or disabled per
platform." Toolsets are "the primary mechanism for configuring tool
availability per platform, per session, or per task." Select per session
with `hermes chat --toolsets "web,terminal"`, per platform with the
`hermes tools` interactive config.

### Four kinds of toolsets

1. **Atomic** — `file`, `terminal`, `web`, `search`, `memory`, `skills`,
   `vision`, `todo`, `session_search`, `clarify`, `delegation`,
   `code_execution`, `cronjob`, `browser`, `tts`, `image_gen`, … (~35
   named; full inventory in the extraction).
2. **Composites** — `coding` (file + terminal + search + web + skills +
   browser + todo + memory + session_search + clarify + code_execution +
   delegation + vision), `debugging` (file + terminal + web), `safe`
   (read-only research: image_gen, vision, web extract/search).
3. **Platform presets** — `hermes-cli` (the default for interactive
   sessions), `hermes-acp`/`hermes-api-server` (drop interactive-only
   tools), `hermes-webhook` (restricted to web_search/web_extract/
   vision_analyze/clarify), `hermes-gateway` (union), platform-specific
   additions (discord, feishu, yuanbao).
4. **Dynamic** — `mcp-<server>` generated at runtime per MCP server;
   plugin-registered toolsets; user-defined custom toolsets.

### Opt-in exceptions that matter for stage 080

- **`kanban` is opt-in and NOT enabled by `all`/`*`** — consistent with
  the kanban capture's "zero schema footprint on normal sessions".
  Workers get `kanban_*` tools by being dispatcher-spawned; orchestrators
  by explicitly enabling the toolset.
- `x_search` (needs xAI credentials) and `video` are opt-in too.
- Restriction is the official orchestrator pattern: a profile with
  `toolsets: [kanban, gateway, memory]` "literally cannot execute
  implementation tasks even if it tries".

### Terminal backends

`terminal.backend` selects one of seven: `local` (default), `docker`,
`ssh`, `singularity`, `modal`, `daytona`, `vercel_sandbox`. Container
backends are the documented production recommendation (dangerous-command
checks are skipped there because "the container itself is the security
boundary" — posture details in `hermes-managed-scope`).

### Background processes and sudo

`terminal` with `background=true` returns a `session_id` and `pid`;
manage via the `process` tool (`list`, `poll`, `wait`, `log`, `kill`,
`write`); `pty=true` for interactive CLIs. Sudo prompts and caches per
session, or reads `SUDO_PASSWORD` from `~/.hermes/.env` — a secret, so
seat-`.env`-at-0600 rules apply.

## Workflow

1. Design profiles by subtraction: start from a preset or composite, then
   restrict — a worker that shouldn't browse gets no `browser`; an
   orchestrator gets board-only toolsets.
2. Check the Toolsets Reference inventory before naming a toolset in
   config — names are exact, and composites differ from their parts.
3. Remember the opt-ins: `kanban` must be explicitly enabled for
   orchestrator profiles (never arrives via `all`).
4. For sandboxed workers pick the backend deliberately
   (`terminal.backend`); Docker is the only backend wired to the egress
   proxy today (see `hermes-managed-scope`).
5. Long-running commands: `background=true` + `process` polling, not
   blocking foreground calls.
6. Cite the official section in the PR (stage 080 official-first rule).

## Validation

```shell
hermes tools --summary            # per-platform tool configuration
hermes chat --toolsets "safe" -q "list your tools"   # restriction smoke-test
hermes prompt-size --json         # tool-schema share of the system prompt
/context all                      # per-toolset token costs in-session
```

## Pitfalls

- Assuming `all`/`*` enables everything — `kanban` (and other opt-ins)
  are excluded by design.
- Confusing the `coding` composite with `code_execution` (a single
  Python-scripting toolset) — very different capability grants.
- Tool availability is gated by platform AND credentials AND toolsets —
  a tool missing from `skills_list`-style enumeration may just be
  credential-gated (e.g. `x_search`, `homeassistant`).
- `hermes-webhook` sessions are heavily restricted by preset — don't
  expect terminal access there.
- The exact config.yaml key shape for per-platform toolset lists is not
  shown on the feature page — configure via `hermes tools` and verify
  with `--summary` rather than hand-writing YAML from memory.
- `SUDO_PASSWORD` in the seat `.env` is a real credential — never in
  Git, never in the world-readable managed `.env`.

## Related Skills

- `hermes-managed-scope` — approval modes, container security, egress.
- `hermes-kanban` — the kanban toolset's semantics and worker gating.
- `hermes-cli` — `hermes tools`, `--toolsets`, `prompt-size` surfaces.
- `hermes-configuration` — `terminal.*` key wiring.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
