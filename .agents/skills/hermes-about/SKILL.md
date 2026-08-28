---
name: hermes-about
metadata:
  author: rhoai3-coding-demo
  version: 1.1.0
  platform-family: "hermes"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Hermes Agent"
description: >
  Use when explaining Hermes Agent, choosing which Hermes mechanism fits a
  stage 080 need (skills vs memory, kanban vs delegate_task vs /goal,
  hooks vs plugins vs cron), checking platform/install support tiers, or
  verifying a claimed capability exists. Do NOT use for depth on any one
  mechanism — the matching hermes-* sibling skill owns it.
---

# Hermes Agent Overview

Use this skill for orientation: what Hermes is, what it ships, which
mechanism to reach for, and where it runs. Depth always lives in the
sibling skills.

## Source Grounding

Read `references/source-capture.md` for provenance and
`references/official-doc-extraction.md` for the full validated extraction —
the complete official feature inventory, the platform matrix, and all ten
documented mechanism-selection comparisons quoted verbatim. Official
Hermes Agent documentation (Nous Research) is the product authority.

## What Hermes is (first-party)

"The self-improving AI agent built by Nous Research. A terminal-native
autonomous coding and task agent with persistent memory, agent-created
skills, and a messaging gateway that lives on 21+ messaging platforms…
Runs on local, Docker, SSH, Daytona, Modal, or Singularity backends.
Works with Nous Portal, OpenRouter, OpenAI, Anthropic, Google, or any
OpenAI-compatible endpoint." (docs `llms.txt` — the only first-party
positioning prose; the user-stories page is curated community quotes and
must be cited as community voice, not Nous claims.)

Four front ends share one agent state: CLI, TUI (recommended interactive
surface), Desktop App, Web Dashboard — "start a session in one and resume
it in another".

## Mechanism selection — consult before designing

The extraction carries all ten documented comparisons verbatim. The
load-bearing one-liners:

| Need | Reach for | Official rule |
|---|---|---|
| Short reasoning subtask, result back into parent context | `delegate_task` | "a function call" |
| Work crossing agent boundaries, surviving restarts, human input | Kanban | "a work queue where every handoff is a row any profile (or human) can see and edit" |
| Mechanical multi-step pipeline, no judgment | `execute_code` | "Use `execute_code` when you need mechanical data processing" |
| Keep iterating on one task in THIS chat | `/goal` | "single-session… never creates a kanban card" |
| One board card that iterates until acceptance | kanban `--goal` | "borrows the engine, not the board" |
| Key facts always in context | Memory | "~1,300 tokens total", always in prompt |
| "Did we discuss X last week?" | `session_search` | "Unlimited (all sessions)… no LLM calls" |
| Long procedures loaded only when relevant | Skills | skills/memory self-improvement split |
| Identity/tone that follows you everywhere | SOUL.md | "if it belongs to a project, it belongs in `AGENTS.md`" |
| Time-triggered automation | Cron | dependency-triggered work is Kanban's job |
| Intercept/observe lifecycle events | Hooks (4 systems) | see `hermes-hooks` for selection within |
| Add tools/commands/integrations | Plugins / MCP / config-driven | "Not everything is a Python plugin" — pick the surface |

## Platform and install facts that gate deployment

- **Tier 1** (first priority, "we strive to never break"): macOS Apple
  Silicon, Windows 10/11, Linux/WSL2, Docker. **Tier 2** (best-effort,
  "releases may break them"): Termux, Nix. **Unsupported** (PRs rejected):
  AUR, Intel Mac, pypi, brew.
- Docker installs don't support `hermes update` — upgrade by new image.
- **OpenShift/Kubernetes is NOT an officially documented install surface.**
  A third-party deployment pattern (Red Hat Developers article + community
  repo: UBI9 image, KServe/vLLM InferenceService, PVC-backed
  `HERMES_HOME`, restricted-SCC securityContext) is captured in
  `references/openshift-deployment.md` — WITH a verified-conflicts table;
  read that table before reusing any of it.
- **Minimum model context: 64K tokens — smaller windows "will be rejected
  at startup"** (hard constraint on any private/MaaS model wired in).
- Versioning is a PROCEDURE, not a number: `hermes version` vs the GitHub
  releases page; installs track `origin/main`. Never hardcode a version
  string in stage 080 docs (point-in-time anchor at capture: v0.20.0,
  2026-08-03 — see `hermes-cli`).

## Governance-relevant defaults (orientation level)

Blank Slate setup mode = provider/model + File Operations + Terminal only
— the documented minimal-trust baseline. Plugins are opt-in
(`plugins.enabled`; project-local plugins additionally gated by
`HERMES_ENABLE_PROJECT_PLUGINS`). Nested delegation is opt-in
(`max_spawn_depth` default 1). Kanban is deliberately single-host. Cron
jobs can't create cron jobs, and the drift guard skips unattended runs
rather than silently inheriting a model switch. Context files, SOUL.md,
and memory writes are all injection-scanned before inclusion.

## Workflow

1. Before recommending a mechanism, check the comparison tables in the
   extraction — never reason from first principles when a documented
   "use X when" exists.
2. Before claiming platform support, check the tier table and quote the
   tier language (Tier 2 carries no stability promise).
3. When describing capabilities, cite the Features Overview inventory in
   the extraction; features without an owning `hermes-*` skill are
   flagged there — say "not yet covered by a sibling skill", don't omit.
4. Route depth questions to the owning sibling immediately.
5. Cite the official section in the PR (stage 080 official-first rule).

## Validation

Static checks (this is an orientation skill — no live seat needed):

- Every mechanism recommendation cites its comparison's official URL.
- No fixed Hermes version number asserted anywhere in stage 080 docs.
- Community-sourced positioning is attributed as community voice.

## Pitfalls

- Citing the user-stories page as Nous positioning — it's a curated
  third-party quote wall; only `llms.txt` is first-party prose.
- Quoting the "21+ platforms" count as exact — the messaging gateway's
  own table lists more rows; reconcile before citing a number.
- Assuming Tier 2 (Nix!) stability for GitOps-style deployment plans —
  the docs' own words: "Breaks often… Best of luck~!"
- Wiring a <64K-context model — rejected at startup, not degraded.
- Treating Curator as a standalone subsystem — it's the skills-lifecycle
  maintenance daemon (owned by `hermes-skills`).
- Copying the third-party OpenShift manifests verbatim — they commit
  `GATEWAY_ALLOW_ALL_USERS: "true"` (officially: never in production),
  serve a 32K-context model (below the 64K startup floor), and wire the
  model via undocumented env vars instead of the `config.yaml` `model:`
  block. See `references/openshift-deployment.md` conflicts table.

## Related Skills

`hermes-configuration`, `hermes-managed-scope`, `hermes-kanban`,
`hermes-skills`, `hermes-hooks`, `hermes-sessions`, `hermes-cli` — the
seven depth skills this overview routes into.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
- `references/openshift-deployment.md` (SUPPLEMENTARY, third-party —
  OpenShift AI + vLLM deployment pattern with verified-conflicts table)
