---
name: hermes-cli
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "hermes"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Hermes Agent"
description: >
  Use when invoking or scripting the Hermes CLI in stage 080: the complete
  hermes subcommand tree, global flags, headless/CI usage (-z, chat -q,
  --json, exit codes), the slash-command registry across CLI/TUI/messaging
  surfaces, and shell completion. Do NOT use for the subsystem semantics
  behind a command family — those belong to the matching hermes-* skill
  (configuration, managed-scope, kanban, skills, hooks, sessions).
---

# Hermes CLI

Use this skill when writing or reviewing anything that invokes `hermes` —
stage 080 dispatch scripts, validation commands, CI wrappers, or docs that
cite command syntax.

## Source Grounding

Read `references/source-capture.md` for provenance and
`references/official-doc-extraction.md` for the full validated extraction:
the complete ~60-family command tree, global flags, the per-surface
slash-command table, and CLI-relevant environment variables. Official
Hermes Agent documentation (Nous Research) is the product authority.
Product version at capture: v0.20.0 "The Herald Release" (tag v2026.8.3),
obtained via the docs-linked GitHub releases page — no doc page carries a
version marker, so recapture by date, not version string.

## Key Concepts

### Two registries

`hermes <command>` (the CLI tree) and `/command` (slash commands inside a
session) are distinct surfaces; both slash surfaces (interactive CLI and
messaging gateway) are "driven by a central `COMMAND_REGISTRY`". Slash
prefix matching resolves `/h` → `/help`; ambiguous prefixes resolve to
"the first match in registry order", and full names/aliases always beat
prefixes. Plugins can register additional slash commands at runtime — the
documented registry is the built-in set, not a ceiling.

### The reference page is canonical but incomplete — supplement map

Verified gaps in `/docs/reference/cli-commands` (cite the supplement, not
memory):

| Missing from the reference | Where it IS documented |
|---|---|
| `hermes photon setup` / `photon telemetry on\|off` (whole family) | messaging/photon guide (prose only) |
| `--accept-hooks` global flag | hooks feature page + env-vars reference |
| `hermes update --branch/--force/--force-venv` | getting-started/updating |
| `hermes approvals suggest --apply/--json` flags | security page |
| Fuller `hermes kanban` verb set and `hermes hooks test` flags | the kanban/hooks feature pages' own CLI blocks |

### Scripting primitives (stage 080's slice)

- `hermes -z "<prompt>"` — "single prompt in, final response text out,
  nothing else on stdout or stderr"; use `hermes chat -q` instead when the
  transcript must include tool output.
- `--usage-file <path>` writes a machine-readable spend report "even when
  the run fails" — the right hook for per-task cost accounting.
- Exit codes are documented ONLY for `hermes send` (0/1/2) and
  `hermes update` (0/1/2) — no other subcommand has an official exit-code
  contract to branch on.
- `hermes gateway run --external-supervisor` exits with **status 75** on a
  requested restart — a supervisor unit MUST relaunch on that nonzero
  exit.
- `--ignore-user-config` falls back to built-in defaults but "credentials
  in `.env` are still loaded"; `--safe-mode` disables ALL customizations
  (implies both ignore flags).

### Headless checklist

Any non-interactive invocation must decide explicitly: hooks consent
(`--accept-hooks` / `HERMES_ACCEPT_HOOKS=1` / `hooks_auto_accept: true` —
otherwise configured shell hooks silently never register), and approval
posture (`approvals.mode: off` is equivalent to `--yolo`; the hardline
blocklist "trips before the approval layer even sees the command, and
there's no override flag" — no fully-unattended run bypasses it).

### Precedence rules

Explicit flag > env var > config default (`--tui`/`--cli` vs `HERMES_TUI`
vs `display.interface`). `-p/--profile` is per-invocation and overrides
the sticky `hermes profile use` default. Kanban board resolution:
`--board` > `HERMES_KANBAN_BOARD` > `~/.hermes/kanban/current` >
`default`.

### Surface availability quirks

Some slash commands are CLI-only (`/handoff`, `/clear`, `/cron`,
`/tools`), some messaging-only (`/approve`, `/deny`, `/sethome`,
`/platform`, `/commands`), and Slack blocks native slash commands inside
threads — use the `!` prefix there (`!stop`, `!new`, `!status`). The `!`
shell mode is interactive-CLI-only. `hermes kanban` is "the human /
scripting surface" — dispatcher-spawned workers drive the board through
`kanban_*` tools, never by shelling to the CLI.

## Workflow

1. Look the command up in the extraction's command tree before scripting
   it — never infer flags from an analogous command — and check the
   supplement map for families the reference page under-documents.
2. Pick the right one-shot primitive (`-z` vs `chat -q`); add
   `--usage-file` when spend must be accounted.
3. For headless runs, set hooks-consent and approval posture explicitly;
   prefer `--ignore-user-config`/`--safe-mode` for reproducible
   diagnostics.
4. Pass `-p <profile>` and `--board <slug>` explicitly in automation —
   never rely on sticky defaults or env inheritance in CI.
5. Prefer `hermes config get/set/unset` over hand-editing config files in
   scripts (auto-routes secrets vs settings).
6. Don't branch on exit codes except for `send`/`update`/gateway-75; treat
   everything else as undocumented.
7. Cite the official section in the PR (stage 080 official-first rule).

## Validation

```shell
hermes --version                       # CLI present + version string
hermes doctor --fix                    # first-line diagnostic
hermes config check                    # stale config after an update
hermes update --check                  # non-mutating update probe (CI-safe)
hermes -z "ping" --usage-file /tmp/u.json && jq . /tmp/u.json
hermes completion bash|zsh|fish        # completion install for dev containers
```

## Pitfalls

- Trusting the CLI reference page as exhaustive — see the supplement map;
  `hermes photon` doesn't appear there at all.
- Branching on undocumented exit codes (only `send`, `update`, and the
  gateway's 75-restart contract are official).
- Forgetting the hooks-consent escape hatch in CI — configured hooks
  silently no-op.
- Treating `approvals.mode: off` and `--yolo` as different risk tiers —
  they are documented as equivalent.
- Assuming `--ignore-user-config` isolates credentials — `.env` still
  loads.
- Wiring a remote TUI via `HERMES_TUI_GATEWAY_URL` — explicitly
  unsupported ("will 404").
- Sending native slash commands into Slack threads — blocked by Slack;
  use `!` prefix.
- `hermes login` is removed — use `hermes auth`/`hermes model`/
  `hermes setup`.
- WSL: use `hermes gateway run` (in tmux), not `gateway start` — systemd
  under WSL is unreliable per the docs.

## Related Skills

- `hermes-configuration` — config/auth/model/fallback/portal semantics.
- `hermes-managed-scope` — secrets and egress (iron-proxy) semantics.
- `hermes-kanban`, `hermes-skills`, `hermes-hooks`, `hermes-sessions` —
  semantics behind those command families.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
