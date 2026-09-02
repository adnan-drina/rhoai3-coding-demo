# Source Capture

## Official Sources

| Field | Value |
|-------|-------|
| Product | Hermes Agent (Nous Research) |
| Product version | no version marker on doc pages |
| Chapter or page title | Skills System; Creating Skills; Curator; Working with Skills; Bundled/Optional Skills Catalogs; Configuration (skill-gate anchors); Slash/CLI references (skills rows); Plugins (register_skill); FAQ (skills.disabled) |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/features/skills |
| Source URL | https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/features/curator |
| Source URL | https://hermes-agent.nousresearch.com/docs/user-guide/configuration (anchors: Skill Settings; Guard on agent-created skill writes; Write approval for skill writes) |
| Source URL | https://hermes-agent.nousresearch.com/docs/guides/work-with-skills |
| Source URL | https://hermes-agent.nousresearch.com/docs/reference/skills-catalog and /docs/reference/optional-skills-catalog |
| Documentation category | Features / Developer Guide / Guides / Reference |
| Capture date | 2026-08-12 |
| Capture method | Research-agent dossier (`source-analysis/hermes/hermes-skills-capture.md`); reviewer re-verified the external_dirs writability/precedence quotes, gate-independence statement, progressive-disclosure model, sync hash rule, --force ceiling, curator defaults, agent-created test, and never-auto-deletes guarantee verbatim against live pages on 2026-08-12 |

## Captured Sections

- Skills System: progressive disclosure, SKILL.md format, platform and
  conditional activation, secure setup on load, directory structure
  (including `.hub/`, `.bundled_manifest`, `.usage.json`), external
  directories, bundles, `skill_manage` governance, Skills Hub (8 sources,
  4 trust tiers), bundled-skill sync.
- Creating Skills: skill-vs-tool decision, frontmatter superset
  (`blueprint`, `required_credential_files`, `license`, `author`),
  credential-file sandbox mounting, inline shell snippets, template-var
  substitution, placement decision tree, blueprints, publishing.
- Curator: run triggers and defaults, agent-created 3-condition test,
  pinning, adoption, archival/rollback, telemetry, protected built-ins.
- Working with Skills: plugin-provided skills (`plugin:skill`),
  per-platform management, skills-vs-memory heuristic.
- FAQ: `skills.disabled` / `skills.platform_disabled` (documented nowhere
  else).
- Coverage audit 2026-08-12 (reviewer): full heading outline of the live
  Skills System page diffed against this capture — no new sections; four
  under-captured subsections closed with verbatim quotes (skill
  output/media delivery incl. `[[as_document]]`; `/learn` knowledge-base
  skills; tap non-default `path`; direct single-skill GitHub install).
  Every heading on the page is now represented (extraction Addendum 2).

## Repository-sourced supplements (not docs — treat as provisional)

- Scanner verdict tiers (`safe`/`caution`/`dangerous` per trust level)
  from `tools/skills_guard.py`.
- Open upstream issue proposing `skills.guard_agent_created` default flip
  to `true` — documented default is still `false`; re-check on recapture.

## Source Boundaries

This skill captures the Hermes skills system: format, discovery,
governance, lifecycle, and the skills CLI/slash surface. `skills.*` key
schema wiring belongs to `hermes-configuration`; kanban task-pinning to
`hermes-kanban`; hook mechanics (incl. `on_skill_lifecycle`) to
`hermes-hooks`; full CLI encyclopedia to `hermes-cli`. This repository's
own `.agents/skills/` taxonomy is a separate, non-Hermes concept
(`maintain-rules-and-skills`).

## Known Open Items

- `external_dirs`↔`external_dirs` same-name collision precedence is
  undocumented (only local-vs-external is stated).
- Defaults for `curator.backup.enabled`, `skills.template_vars`, and
  `skills.inline_shell_timeout` are inferable from prose only, never
  stated in a canonical defaults block.
- Security-scanner findings taxonomy is not enumerated on the docs site.
- Catalog counts in `/docs/llms.txt` are stale relative to live tables —
  cite the live table if a count matters.
- Taxonomy gap flagged: no `hermes-*` skill owns general Cron Jobs or
  general Plugins, though both intersect the skills system.
