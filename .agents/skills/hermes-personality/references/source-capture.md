# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Hermes Agent (Nous Research) |
| Product version | no version marker on doc pages (family anchor: v0.20.0, 2026-08-03) |
| Chapter or page title | Personality & SOUL.md (feature); Use SOUL.md with Hermes (guide) |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/features/personality |
| Source URL | https://hermes-agent.nousresearch.com/docs/guides/use-soul-with-hermes |
| Documentation category | Features (Customization) / Guides |
| Capture date | 2026-08-12 |
| Capture method | Reviewer-direct capture (maintainer-requested gap-fill): verbatim extraction from both pages; cross-checked against hermes-about (SOUL-vs-AGENTS and SOUL-vs-/personality comparisons, 8-layer prompt stack, injection scanning — all verified earlier same day) and the profiles capture ("SOUL.md does not enforce a workspace boundary") — consistent |

## Captured Content

- Identity model: SOUL.md = slot #1 of the 8-layer system prompt,
  replacing the hardcoded default; loaded from $HERMES_HOME only (never
  cwd — "personality stays predictable"); auto-created starter; never
  overwritten by updates; built-in fallback on empty/unloadable;
  "injected verbatim after security scanning and truncation".
- Three-surface split: SOUL.md (identity/tone/style, follows you
  everywhere) vs AGENTS.md (project rules) vs /personality (session
  overlay stored in display.personality; reset via none/default/neutral).
- Authoring guidance: Identity/Style/Avoid/Defaults structure; strong
  content is stable, broad, voice-shaping, non-task-specific; four
  worked personas (pragmatic engineer, research partner, teacher, tough
  reviewer).
- Custom personalities: agent.personalities map in config.yaml;
  /personality <name> activation; built-in preset list.
- Security: injection-scanned before inclusion; not an enforcement
  mechanism.

## Source Boundaries

Identity/personality mechanics live here. Context-file discovery
(AGENTS.md/.cursorrules loading, priority chain) is the unowned Context
Files topic; profile/HERMES_HOME mechanics → `hermes-configuration`;
this repository's own AGENTS.md conventions → `maintain-rules-and-skills`
(not a Hermes topic).

## Known Open Items

- The two fetches disagree on the built-in personality count ("Thirteen
  options include:" followed by 14 names, vs the about capture's page map
  noting a "14-row table") — cosmetic; recount on recapture before citing
  a number.
- SOUL.md truncation threshold ("security scanning and truncation") is
  not quantified on either page.
