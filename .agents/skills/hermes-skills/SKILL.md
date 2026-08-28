---
name: hermes-skills
metadata:
  author: rhoai3-coding-demo
  version: 1.1.0
  platform-family: "hermes"
  platform-baseline: "repo"
  ocp-baseline: "repo"
  skill-group: "Hermes Agent"
description: >
  Use when authoring or governing skills for Hermes worker seats in stage
  080: SKILL.md format and frontmatter, discovery paths and precedence
  (bundled, user, external_dirs, plugin), skill bundles, write gates,
  curator lifecycle, Skills Hub trust levels, and the skills CLI/slash
  surface. Do NOT use for this repo's own .agents/skills taxonomy (use
  maintain-rules-and-skills), skills.* key schema wiring (use
  hermes-configuration), or pinning skills to kanban tasks (use
  hermes-kanban).
---

# Hermes Skills System

Use this skill for any stage 080 change touching skills that Hermes worker
seats discover, load, or write.

## Source Grounding

Read `references/source-capture.md` for provenance and
`references/official-doc-extraction.md` for the full validated extraction
(frontmatter superset table, directory layouts, config-key behavior, CLI
tables, trust levels, verbatim examples). Official Hermes Agent
documentation (Nous Research) is the product authority.

## Key Concepts

### Progressive disclosure

Three levels: `skills_list()` (name/description/category, ~3k tokens — the
fixed floor for having any skills installed), `skill_view(name)` (full
content), `skill_view(name, path)` (a specific reference file). Author
accordingly: most common workflow first, depth in `references/`, helper
logic in `scripts/` — "don't expect the LLM to write parsers inline".

### SKILL.md format

Required frontmatter: `name`, `description`. The Creating Skills page's
example is the superset (adds `author`, `license`, `platforms`,
`metadata.hermes.{tags, category, related_skills, config, blueprint}`,
`required_environment_variables`, `required_credential_files`).
Conditional activation is easy to get backwards: `requires_toolsets/_tools`
hides the skill when those are UNAVAILABLE; `fallback_for_toolsets/_tools`
hides it when they ARE available. Declared env vars are auto-passed into
`execute_code`/`terminal` sandboxes and the raw secret is never exposed to
the model; credential file paths are relative to `~/.hermes/`, mounted
read-only into Docker / synced into Modal.

Output/media delivery: a bare absolute media path in a skill response is
auto-detected by the gateway, stripped from the text, and delivered
natively to chat; the literal `[[as_document]]` directive forces every
media path in that response to be delivered as a document/file attachment
instead of an image bubble (preserves resolution — e.g. Telegram's
`sendPhoto` recompresses to ~200 KB at 1280 px).

### Authoring without hand-writing: `/learn`

`/learn` distills sources into a skill without hand-writing the SKILL.md;
large sources (a book, a spec, a docs folder) become an "expansive
knowledge-base skill" — one distilled file per chapter/topic under
`references/`, loaded on demand via `skill_view`. `/learn` saves through
`skill_manage`, so the `skills.write_approval` gate applies when on.

### Discovery paths and precedence

Four paths: bundled (seeded into `~/.hermes/skills/`, the "primary
directory and source of truth"), user-authored (same directory), external
directories (`skills.external_dirs`, with `~` and `${VAR}` expansion), and
plugin-provided (`plugin:skill` namespace — invisible to `skills_list`,
opt-in load). Precedence: on a name collision, "the local version wins"
over external; bundles beat individual skills on slug collision.
Nonexistent `external_dirs` paths are **silently skipped** — a typo
produces no error. Hub/URL installs are reference-scoped: only SKILL.md
plus the files it actually references are copied.

### Governance — three independent mechanisms

1. **`skills.write_approval`** (default `false`): when on, every
   `skill_manage` write — foreground or background self-improvement review
   — is staged for `/skills pending|diff|approve|reject`.
2. **`skills.guard_agent_created`** (default `false`): a dangerous-pattern
   content scanner — "not an approval gate — the two are independent".
   (An open upstream issue proposes flipping this default to `true`;
   documented default is still `false`.)
3. **The curator**: background maintenance over agent-created skills only
   (3-condition test: not in `.bundled_manifest`, not in `.hub/lock.json`,
   `.usage.json` marks agent creation). It "never auto-deletes — the worst
   outcome is archival" (defaults: stale 30d, archive 90d, weekly run
   after 2h idle). Foreground `skill_manage(create)` skills are
   user-directed and outside its jurisdiction; hub-installed skills are
   always off-limits; `prune_builtins: true` means unused bundled skills
   CAN be archived; cron-referenced skills get pin-equivalent protection.

### Trust and updates

Hub trust tiers: `builtin` > `official` (`optional-skills/`, no
third-party warning) > `trusted` (hardcoded repos: openai, anthropics,
huggingface, NVIDIA) > `community` (everything else, including your own
taps — raising a tap's trust requires a Hermes core PR). Tap skills that
don't live under `skills/` need a `"path"` entry in
`~/.hermes/skills/.hub/taps.json`; a single skill installs from any public
GitHub repo without adding the tap
(`hermes skills install owner/repo/skills/<name>`). `--force`
overrides caution/warn findings but "does not override a `dangerous` scan
verdict". Bundled-skill sync is hash-based: a locally edited bundled skill
is "treated as user-modified and skipped forever" (un-stick with
`hermes skills reset`). Fleet note: hub operations hit the GitHub API —
set `GITHUB_TOKEN` to lift the 60/hr unauthenticated limit.

## Workflow

1. Author against the frontmatter superset table in
   `references/official-doc-extraction.md` §5a — never from memory; follow
   the documented body shape (When to Use → Procedure → Pitfalls →
   Verification).
2. Decide placement: agent seat dir vs. `skills.external_dirs` vs. a tap.
   For shared/external dirs, decide the write posture explicitly — "if an
   external skill directory is writable by the Hermes process,
   agent-managed skill updates can change files in that directory"; use
   filesystem permissions for read-only intent.
3. For fleet governance, enable `skills.write_approval` deliberately (the
   default is write-freely, including background reviews) and treat
   `guard_agent_created` as a separate decision.
4. Repeatedly co-loaded skills become a bundle (`skill-bundles/` YAML) —
   bundles don't invalidate the prompt cache.
5. Installs take effect in NEW sessions — `/reset` or `--now` for the
   current one.
6. Cite the official section in the PR (stage 080 official-first rule).

## Validation

```shell
hermes skills list                    # discoverability of the new/edited skill
hermes skills inspect <id>            # preview an install without installing
hermes skills audit                   # re-scan hub skills for security
hermes curator status                 # jurisdiction, pinned list, staleness
hermes config get skills.config --json  # skill-declared settings storage
/skills pending                       # staged writes when the gate is on
```

## Pitfalls

- `external_dirs` is not a write-protection boundary, and mistyped paths
  are silently ignored — validate wiring by listing skills, not by
  trusting config.
- `requires_*` vs `fallback_for_*` have inverse semantics — a swapped
  field silently hides the skill in exactly the wrong sessions.
- A hand-edited bundled skill is skipped by every future sync — silent
  staleness until `hermes skills reset`.
- `skills.inline_shell` (off by default) executes SKILL.md snippets on the
  host without approval — never enable it for tap/community-sourced
  skills.
- Only agent-created skills can be curator-pinned; hand-authored skills in
  the seat dir are already outside curator jurisdiction — but "the agent
  can modify or delete any skill" there unless the write gate is on.
- Blueprints never auto-schedule on install — scheduling is an explicit
  opt-in step; don't assume an installed automation is running.
- Plugin-provided skills don't appear in `skills_list` — absence from the
  list is not proof a capability is missing.
- Stacking is capped at 5 skills per slash invocation; prefer a bundle.

## Related Skills

- `maintain-rules-and-skills` — this repo's own (non-Hermes) skill
  taxonomy.
- `hermes-configuration` — schema wiring for the `skills.*` keys whose
  behavior is described here.
- `hermes-kanban` — pinning installed skills to tasks (`--skill`, no
  runtime install).
- `hermes-managed-scope` — fleet-pinning skill governance keys at the
  admin tier.

## References

- `references/source-capture.md`
- `references/official-doc-extraction.md`
