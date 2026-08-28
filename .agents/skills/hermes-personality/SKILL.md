---
name: hermes-personality
metadata:
  author: rhoai3-coding-demo
  version: 1.0.0
  platform-family: "hermes"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Hermes Agent"
description: >
  Use when authoring or reviewing SOUL.md identity files for Hermes seats
  in stage 080, choosing between SOUL.md, AGENTS.md, and /personality
  overlays, or wiring custom personalities. Do NOT use for project
  context files and AGENTS.md discovery mechanics (unowned Context Files
  topic), profile mechanics (hermes-configuration), or this repo's own
  AGENTS.md conventions (maintain-rules-and-skills).
---

# Hermes Personality & SOUL.md

Use this skill when touching agent identity. Stage 080 authors four
SOUL.md files: dest-user `.hermes/SOUL.md` (base `HERMES_HOME`) and
`.hermes/config/profiles/{orchestrator,implementer,reviewer}.SOUL.md`
(placed into each profile home). Official: one SOUL.md per profile.
Content rules come from these official pages.

## Source Grounding

Official pages (captured 2026-08-12, see `references/source-capture.md`):
the Personality & SOUL.md feature page and the "Use SOUL.md with Hermes"
guide.

## Key Concepts

### What SOUL.md is

"The primary identity for your Hermes instance" — it "occupies slot #1 in
the system prompt, replacing the hardcoded default identity", loaded from
`$HERMES_HOME/SOUL.md` (per profile), NEVER from the working directory —
"personality stays predictable" across projects by design. Auto-created
as a starter on first run; user files never overwritten by updates;
empty/unloadable files fall back to a built-in identity. Content is
"injected verbatim after security scanning and truncation" — SOUL.md is
prompt-injection-scanned like every context-bearing file, and it "does
not enforce a workspace boundary" (identity, not access control).

### The three-surface split (the rule that prevents misplacement)

- **SOUL.md** — identity, tone, style, communication defaults: "if it
  should follow you everywhere, it belongs in SOUL.md".
- **AGENTS.md** — "project architecture, coding conventions, tool
  preferences, repo-specific workflows, commands, ports, paths": "if it
  belongs to a project, it belongs in AGENTS.md". (Stage 080 enforces
  this split: the scaffold's AGENTS.md is the sole standing-convention
  surface; SOUL.md carries identity only.)
- **`/personality`** — "a session-level overlay… temporary mode switch";
  stored as a name in `display.personality`, never modifying SOUL.md.
  Built-ins include technical, teacher, concise, and novelty presets;
  custom ones live under `agent.personalities` in config.yaml; reset
  with `/personality none|default|neutral`.

### Writing a strong SOUL.md

Suggested structure: **Identity** (who), **Style** (how it sounds),
**Avoid** (what not to do), **Defaults** (behavior under ambiguity).
Effective content is "stable across contexts", "broad enough to apply in
many conversations", "specific enough to materially shape the voice",
and "focused on communication and identity, not task-specific
instructions". The guide's four worked personas (pragmatic engineer,
research partner, teacher, tough reviewer) are the reference shapes —
the tough-reviewer persona ("point out weak assumptions directly…
prioritize correctness over harmony") maps well onto stage 080 reviewer
profiles.

### Prompt stack position

SOUL.md is layer 1 of 8: SOUL → tool-aware guidance → memory/user
context → skills guidance → context files (AGENTS.md, .cursorrules) →
timestamp → platform formatting → optional overlays (`/personality`).
Overlays come LAST — a session overlay supplements, and can contradict,
the base voice; keep them temporary.

## Workflow

1. One SOUL.md per profile (`$HERMES_HOME/SOUL.md`) — worker roles in
   stage 080 get identity there, never in task bodies or AGENTS.md.
2. Apply the three-surface split before writing a line: identity →
   SOUL.md; project rules → AGENTS.md; temporary mode → `/personality`.
3. Structure as Identity/Style/Avoid/Defaults; keep it voice-only — no
   meta-instructions, no paths, no tool commands.
4. Never rely on SOUL.md for enforcement — it guides the model; managed
   scope, toolsets, and filesystem permissions enforce.
5. Cite the official section in the PR (stage 080 official-first rule).

## Validation

```shell
cat "$HERMES_HOME/SOUL.md"              # the seat's actual identity
hermes config get display.personality   # active overlay, if any
/personality                            # in-session: list/show overlays
/status                                 # confirms profile + session identity
```

## Pitfalls

- Project instructions in SOUL.md ("use pytest, not unittest" belongs in
  AGENTS.md) — the most common misplacement, called out by both pages.
- Expecting a repo-local SOUL.md to load — Hermes reads only
  `$HERMES_HOME/SOUL.md`, by design.
- Treating SOUL.md as a guardrail — it "does not enforce a workspace
  boundary"; it also can't smuggle meta-instructions past the injection
  scanner.
- Editing SOUL.md for a temporary shift — that's `/personality`'s job;
  the overlay resets cleanly, the file edit doesn't.
- Forgetting the scaffold rule: `workshop-extensions/` overlays never
  touch SOUL (stage 080 convention on top of the official model).
- Sharing one SOUL.md across dest worker profiles — official load is
  `$HERMES_HOME/SOUL.md` for that profile; dest-init must place a
  distinct file after `profile create --no-alias`, not `--clone`.
- An empty SOUL.md doesn't mean "no identity" — the built-in fallback
  takes over silently.

## Related Skills

- `hermes-configuration` — profiles, `HERMES_HOME`, `display.*` and
  `agent.personalities` wiring.
- `hermes-skills` — skills-vs-SOUL content boundaries (procedures vs
  identity).
- `hermes-about` — the SOUL.md vs AGENTS.md comparison in the
  mechanism-selection map.

## References

- `references/source-capture.md`
