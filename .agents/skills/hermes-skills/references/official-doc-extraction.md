# Official Doc Extraction — hermes-skills

Validated research dossier (capture date 2026-08-12). Reviewer validation:
the external_dirs writability and precedence quotes, the
write_approval/guard_agent_created independence statement, the
progressive-disclosure model, the bundled-sync hash rule, the --force
ceiling, the curator defaults block, the agent-created 3-condition test,
and the never-auto-deletes guarantee were all re-verified verbatim against
live pages on 2026-08-12. Original dossier:
`source-analysis/hermes/hermes-skills-capture.md`.

---

# hermes-skills — Research Dossier

## Executive Summary

1. **Captured:** The full Skills System feature (progressive disclosure, SKILL.md format incl. all optional frontmatter fields, directory structure, external dirs, bundles, skill_manage governance incl. both independent gates, the Skills Hub with 8 sources/trust levels, bundled-skill sync/opt-out, and the Curator background-maintenance lifecycle), plus the skills CLI/slash surface and both catalogs.
2. **Confidence:** High. Every normative claim below is a verbatim quote from a live, successfully fetched official page; no page in the core topic area was unreachable.
3. **Biggest gap:** No worked end-to-end example of the security-scanner *findings taxonomy* on the docs site itself (only category names); the GitHub source fills this partially but is repository-not-docs. Also unresolved: exact precedence when a skill name collides across `external_dirs` entries themselves (only local-vs-external precedence is documented).
4. **Contradicts current placeholder?** Partially. The placeholder's pinned URL (`.../docs/user-guide/features/skills`) is correct and remains the best single source, but the placeholder's scope description ("SKILL.md format, skill directory structure, discovery paths (external_dirs), bundles, and skill governance") undersells how much normative material exists — it should also anchor on `/docs/developer-guide/creating-skills` (the authoring-guidelines counterpart) and reference the two catalog pages and the Curator page, none of which are currently pinned anywhere in this skill.
5. **Suggested next skill to research:** `hermes-cli` (to formally own the full `hermes skills` / `hermes bundles` / `hermes curator` subcommand reference tables started here) or `hermes-configuration` (to formally own `skills.write_approval`, `skills.guard_agent_created`, `skills.config`, `skills.disabled`/`platform_disabled` key wiring, which this dossier only records the *behavior* of).

---

## 1. Capture Header

| Field | Value |
|---|---|
| Product | Hermes Agent (Nous Research) |
| Version marker | No version marker on any page read. `hermes dump` example output on the CLI Commands page shows a sample `version: 0.8.0 (2026.4.8)` but this is illustrative example output, not a stated "docs current as of" version. |
| Capture date | 2026-08-12 |

### Page inventory

**Read (primary/full fetch or targeted grep of full fetch):**

| Page | URL | Why read |
|---|---|---|
| Skills System | `/docs/user-guide/features/skills` | Primary pinned page — the full feature reference |
| Creating Skills | `/docs/developer-guide/creating-skills` | Authoring-guidelines counterpart; has fields absent from Skills System (e.g. `blueprint`, `required_credential_files`, inline shell snippets, `${HERMES_SKILL_DIR}` substitution) |
| Curator | `/docs/user-guide/features/curator` | Governance/lifecycle for agent-created skills — explicitly in TOPIC ("guarding agent-created skills") |
| Working with Skills (guide) | `/docs/guides/work-with-skills` | User-facing day-to-day workflow; confirms/cross-checks Skills System claims, adds "Plugin-Provided Skills" and "Skills vs Memory" |
| Bundled Skills Catalog | `/docs/reference/skills-catalog` | Reference table required by deliverable §5 |
| Optional Skills Catalog | `/docs/reference/optional-skills-catalog` | Reference table required by deliverable §5 |
| Security | `/docs/user-guide/security` (grepped, not fully read) | Env-var/credential-file passthrough mechanics tied to skill frontmatter; "Skills Guard" mention |
| Slash Commands reference | `/docs/reference/slash-commands` (grepped) | Full skills-related slash surface (`/skills`, `/bundles`, `/curator`, `/learn`, `/reload-skills`, `/journey`, `/commands`) across CLI/TUI/messaging |
| CLI Commands reference | `/docs/reference/cli-commands` (grepped) | `hermes skills`, `hermes bundles`, `hermes curator` subcommand tables; `hermes prompt-size`; migration commands that touch skills |
| Configuration | `/docs/user-guide/configuration` (grepped) | "Skill Settings", "Guard on agent-created skill writes", "Write approval for skill writes" sections — the canonical location of these two independent gates' full text |
| Plugins | `/docs/user-guide/features/plugins` (grepped) | `ctx.register_skill()` — a *fourth* skill-discovery path (plugin-bundled, `plugin:skill` namespace) not mentioned on the Skills System page itself |
| FAQ & Troubleshooting | `/docs/reference/faq` (grepped) | `skills.disabled` / `skills.platform_disabled` config keys (Telegram 100-command-limit scenario) — not documented anywhere else found |
| `/docs/llms.txt` | site index | Territory-mapping — full page inventory used to decide what to read vs. deprioritize |

**Deprioritized (in-inventory, not read), with reason:**

| Page | Reason deprioritized |
|---|---|
| Getting Started: Installation, Quickstart, Updating, Termux, Nix Setup | General setup; the one skill-relevant fact (`--no-skills` install/profile flags) is already stated verbatim on the Skills System page itself |
| CLI (user-guide/cli), TUI | General interface docs; skill-specific slash/CLI surface fully covered via the two reference pages instead |
| Sessions, Profiles, Git Worktrees, Docker Backend, Checkpoints & Rollback | Adjacent but not skill-format/discovery; profile-level skill isolation (`.bundled_manifest` per profile, `hermes -p <name> skills reset`) already stated on Skills System/Curator pages |
| Features Overview | Superseded by `/docs/llms.txt` as a navigation index |
| Tools (features/tools) | "Skill vs. Tool" decision already fully answered on Creating Skills page |
| Memory, Memory Providers | Sibling concept; comparison table already captured via Work with Skills "Skills vs Memory"; deep Memory internals out of scope |
| Context Files, Context References, Personality & SOUL.md, Built-in Plugins | Distinct features, out of TOPIC |
| Cron Jobs, Delegation, Kanban Multi-Agent, Kanban Tutorial, Persistent Goals, Code Execution, Batch Processing | Automation features; cron `--skill` attachment and kanban skill-pinning are explicitly named as sibling-skill boundaries in the assignment |
| Hooks | Owned by `hermes-hooks` |
| Voice Mode, Browser, Vision, Image Generation, Text-to-Speech, all Messaging Platforms pages | Media/channel features, out of TOPIC |
| Integrations Overview, Providers, MCP, ACP, API Server, Honcho, Provider Routing, Fallback Providers, Credential Pools | Out of TOPIC, except that skill conditional-activation fields (`requires_toolsets`, etc.) can reference MCP-provided toolsets — noted inline where relevant, not deep-dived |
| Guides: Tips, Local LLMs on Mac, Daily Briefing Bot, Team Telegram Assistant, Python Library, Use MCP with Hermes, Use Voice Mode, Use SOUL.md, Build a Hermes Plugin, Automate with Cron, Delegation Patterns, GitHub PR Review Agent | Tutorials; "Build a Hermes Plugin → Bundle skills" cross-checked instead via the Plugins feature page directly |
| Developer Guide: Contributing, Architecture, Agent Loop, Prompt Assembly, Context Compression & Caching, Gateway Internals, Session Storage, Provider Runtime, Adding Tools, Adding Providers, Adding Platform Adapters, Extending the CLI | Internals, out of TOPIC |
| Reference: Profile Commands, Environment Variables, Tools Reference, Toolsets Reference, MCP Config Reference, Model Catalog | Not skill-specific enough to warrant full read; the skill-declared-env-var behavior is fully covered via Creating Skills + Security instead |

**Dead links / redirects:** None encountered — every fetched URL returned content on the first request.

---

## 2. Recommended Source Pins

The current `references/source-capture.md` pins exactly one URL. Recommend expanding to:

| Priority | URL | Role |
|---|---|---|
| 1 (primary, keep) | `https://hermes-agent.nousresearch.com/docs/user-guide/features/skills` | Feature reference: progressive disclosure, SKILL.md format, directory structure, external dirs, bundles, skill_manage + both governance gates, Skills Hub, bundled-skill sync |
| 2 (add) | `https://hermes-agent.nousresearch.com/docs/developer-guide/creating-skills` | Authoring guidelines: Skill-vs-Tool decision, additional frontmatter fields (`blueprint`, `required_credential_files`, `license`, `author`), inline shell snippets, `${HERMES_SKILL_DIR}`/`${HERMES_SESSION_ID}` substitution, "where should the skill live" (bundled vs. optional-skills vs. hub) |
| 3 (add) | `https://hermes-agent.nousresearch.com/docs/user-guide/features/curator` | Full governance/lifecycle for agent-created skills: pinning, adoption, archival, rollback, `prune_builtins` |
| 4 (add) | `https://hermes-agent.nousresearch.com/docs/user-guide/configuration` (anchors: "Skill Settings", "Guard on agent-created skill writes", "Write approval for skill writes") | Canonical text for the two independent write-gates and `skills.config` storage — cite the anchor, not just the page, since it is a very long page (1888 lines) |
| 5 (add, optional) | `https://hermes-agent.nousresearch.com/docs/guides/work-with-skills` | Day-to-day workflow guide; adds Plugin-Provided Skills and Per-Platform Skill Management, which the feature page doesn't cover |
| 6 (add, optional) | `https://hermes-agent.nousresearch.com/docs/reference/skills-catalog` and `.../optional-skills-catalog` | For any content that needs to cite "which skills ship by default" |

Nothing in the current single pin proved irrelevant — it was simply too narrow for the topic's actual breadth.

---

## 3. Page Maps

### Skills System (`/docs/user-guide/features/skills`)

1. Intro — on-demand knowledge docs, progressive disclosure, agentskills.io compatibility, `~/.hermes/skills/` as source of truth
2. Starting with a blank slate — `--no-skills`, `hermes skills opt-out/opt-in`, `.no-bundled-skills` marker
3. Using Skills — slash-command auto-exposure, stacking up to 5 skills, `hermes chat --toolsets skills -q`
4. Learning a skill from sources (`/learn`) — knowledge-base skills, `${HERMES_SKILL_DIR}` scripts, dashboard "Learn a skill" panel
5. Progressive Disclosure — the 3-level `skills_list`/`skill_view`/`skill_view(path)` model
6. SKILL.md Format — full frontmatter example
7. Platform-Specific Skills — `platforms:` field
8. Skill output and media delivery — bare path auto-detection, `[[audio_as_voice]]`, `[[as_document]]`
9. Conditional Activation (Fallback Skills) — `fallback_for_toolsets`/`_tools`, `requires_toolsets`/`_tools`
10. Secure Setup on Load — `required_environment_variables`
11. Skill Config Settings — `metadata.hermes.config`
12. Skill Directory Structure — full tree incl. `.hub/`, `.bundled_manifest`
13. External Skill Directories — `skills.external_dirs`, precedence, write behavior
14. Skill Bundles — YAML schema, `hermes bundles` CLI, precedence over same-name skills
15. Agent-Managed Skills (`skill_manage` tool) — actions table, when the agent creates skills
16. Gating agent skill writes (`skills.write_approval`) — full approve/deny workflow
17. Skills Hub — `hermes skills` command reference, 8 sources, trust levels, update lifecycle, publishing a tap
18. Bundled skill updates (`hermes skills reset`) — sync/hash/reset mechanics, per-profile manifests

### Creating Skills (`/docs/developer-guide/creating-skills`)

1. Should it be a Skill or a Tool? — decision criteria + examples both ways
2. Skill Directory Structure — repo-side (`skills/`, `optional-skills/`)
3. SKILL.md Format — superset frontmatter (adds `license`, `author`, `blueprint`, `related_skills`)
4. Platform-Specific Skills (duplicate of Skills System, same content)
5. Conditional Skill Activation (duplicate content, phrased as a table)
6. Environment Variable Requirements — field-by-field spec
7. Secure Setup on Load — sandbox passthrough details, legacy `prerequisites.env_vars` alias
8. Config Settings (config.yaml) — field-by-field spec, storage path, discovery via `hermes config migrate`
9. Credential File Requirements (OAuth tokens, etc.) — `required_credential_files`, Docker/Modal mounting behavior
10. Skill Guidelines — no external deps, progressive disclosure ordering, helper scripts, `[[as_document]]`, `${HERMES_SKILL_DIR}`/`${HERMES_SESSION_ID}` substitution, inline shell snippets (`skills.inline_shell`)
11. Test It
12. Where Should the Skill Live? — bundled vs. optional-skills vs. Hub decision tree
13. Blueprints: skills that are also automations — `metadata.hermes.blueprint`, `/suggestions`
14. Suggested Cron Jobs — 4 suggestion sources
15. Publishing Skills — `hermes skills publish`, tap
16. Security Scanning — trust levels (repeats Skills System content, slightly reworded)

### Curator (`/docs/user-guide/features/curator`)

1. Intro — purpose, `prune_builtins`, never-auto-deletes guarantee, tracks GitHub issue #7816
2. How it runs — inactivity-triggered (not cron daemon), `interval_hours`/`min_idle_hours`, first-run deferral, `--dry-run`, two phases (deterministic prune vs. opt-in LLM consolidation)
3. Configuration — full `curator:` YAML block with defaults
4. Running the review on a cheaper aux model — `auxiliary.curator` slot, `hermes model` picker, legacy `curator.auxiliary.*` deprecation
5. CLI — full `hermes curator <subcommand>` table
6. Backups and rollback — automatic tar.gz snapshot before every real pass, `hermes curator rollback`, `curator.backup.keep`
7. What "agent-created" means — 3-condition test, `.usage.json` markers, `mark_agent_created()` call path
8. Adopting unmanaged skills — `hermes curator adopt`, pre-dates-marker vs. foreground-created reasons
9. Pinning a skill — `hermes curator pin/unpin`, interaction with `skill_manage(delete)`, cron-job skill references get equivalent protection, protected built-ins (e.g. `plan`) hardcoded as never-archivable
10. Usage telemetry — `.usage.json` schema, counter semantics
11. Per-run reports — `~/.hermes/logs/curator/<timestamp>/{run.json,REPORT.md}`
12. Restoring an archived skill — `hermes curator restore`, refusal condition
13. Disabling per environment — `curator.enabled: false`, `hermes curator pause/resume`

### Working with Skills guide (`/docs/guides/work-with-skills`)

1. Finding Skills — `/skills`, `hermes skills list`, `/skills search`
2. Using a Skill — slash-command invocation, natural-language trigger via `skill_view`
3. Installing from the Hub — `hermes skills install official/...`, effect steps, `/reset` or `--now` for current-session activation
4. Plugin-Provided Skills — `plugin:skill` namespace, not in `skills_list`, opt-in load
5. Configuring Skill Settings — `hermes skills config <skill>`, `hermes config get skills.config --json`
6. Creating Your Own Skill — 4-step walkthrough
7. Per-Platform Skill Management — `hermes skills` interactive TUI for per-platform enable/disable
8. Skills vs Memory — comparison table
9. Tips — keep skills focused, let the agent create skills, use categories, update stale skills

### Bundled Skills Catalog (`/docs/reference/skills-catalog`)

Flat category → table structure (14 categories, ~70 skills enumerated on the fetched page — page states "~90 skills bundled with Hermes" per the index description). Each row: skill name, one-line description, path. Notes the catalog is regenerated by `website/scripts/generate-skill-docs.py` and that sync respects local deletions/edits.

### Optional Skills Catalog (`/docs/reference/optional-skills-catalog`)

Same table structure, 21 categories, ~140 rows read (page states "~60 additional installable skills" in the index description — the actual table content is larger than that summary line, treat the summary figure as approximate/stale relative to the live table). Ends with a "Contributing Optional Skills" 4-step section for PR submission.

---

## 4. Normative Statements

| Exact quote | Page + section | Why it matters for stage 080 |
|---|---|---|
| "All skills live in `~/.hermes/skills/` — the primary directory and source of truth." | Skills System, intro | Establishes the one write-authoritative location Hermes worker seats read from |
| "The agent can modify or delete any skill." | Skills System, intro | Any skill placed in the primary dir — including project-authored ones — is mutable by the agent unless pinned |
| "All three paths write a `.no-bundled-skills` marker into the profile directory. While the marker is present, the installer, `hermes update`, and any skill sync all skip bundled-skill seeding for that profile." | Skills System, "Starting with a blank slate" | If stage 080 wants a clean, non-bundled skill set per worker profile, this is the exact mechanism |
| "Every leading `/skill` token (up to 5) is loaded, and the rest becomes your instruction" | Skills System, "Using Skills" | Hard cap of 5 stacked skills per slash invocation |
| "There is no model-tool footprint: `/learn` builds a standards-guided prompt and hands it to the agent as a normal turn. The agent saves the result with the `skill_manage` tool, so the write-approval gate applies if you have it on." | Skills System, "Learning a skill from sources" | `/learn`-authored skills are subject to the same `skills.write_approval` gate as any other agent write |
| "Level 0: skills_list() → [{name, description, category}, ...] (~3k tokens) / Level 1: skill_view(name) → Full content + metadata (varies) / Level 2: skill_view(name, path) → Specific reference file (varies)" | Skills System, "Progressive Disclosure" | The exact 3-level cost model; ~3k tokens is the fixed floor for having any skills installed at all |
| "When set, the skill is automatically hidden from the system prompt, `skills_list()`, and slash commands on incompatible platforms. If omitted, the skill loads on all platforms." | Skills System, "Platform-Specific Skills" | `platforms:` filtering behavior and its scope (3 surfaces) |
| "`fallback_for_toolsets` \| Skill is hidden when the listed toolsets are available. Shown when they're missing." / "`requires_toolsets` \| Skill is hidden when the listed toolsets are unavailable. Shown when they're present." | Skills System, "Conditional Activation" | Exact (inverse) semantics of the two condition families — easy to get backwards |
| "Hermes never exposes the raw secret value to the model." | Creating Skills, "Secure Setup on Load" | Security guarantee for `required_environment_variables` |
| "declared env vars are automatically passed through to `execute_code` and `terminal` sandboxes — the skill's scripts can use `$TENOR_API_KEY` directly" | Skills System, "Secure Setup on Load" | Automatic sandbox passthrough is tied to *declaring* the var in frontmatter, not to manual config |
| "Use `required_environment_variables` for API keys, tokens, and other secrets... Use `config` for paths, preferences, and non-sensitive settings" | Creating Skills, "When to use which" | The exact secret-vs-non-secret storage split (`.env` vs `config.yaml`) |
| "`path` (required) — file path relative to `~/.hermes/`" | Creating Skills, "Credential File Requirements" | `required_credential_files` paths are relative to HERMES_HOME, not the skill directory |
| "Missing files trigger `setup_needed`. Existing files are automatically: Mounted into Docker containers as read-only bind mounts / Synced into Modal sandboxes (at creation + before each command, so mid-session OAuth works)" | Creating Skills, "Credential File Requirements" | Concrete sandbox-mounting behavior per backend |
| "`~/.hermes/skills/ / /SKILL.md` (required)... `.hub/` (Skills Hub state)... `.bundled_manifest` (Tracks seeded bundled skills)" | Skills System, "Skill Directory Structure" | Canonical on-disk layout, including the two hidden state files |
| "Third-party URL and GitHub installs include `SKILL.md` plus the exact local files it references under `references/`, `templates/`, `scripts/`, and `examples/`. Unreferenced repository files are not copied." | Skills System, "Skill Directory Structure" | Installs are *reference-scoped*, not full-repo copies — important for what stage 080 can assume ships with an installed skill |
| "Add `external_dirs` under the `skills` section in `~/.hermes/config.yaml`... Paths support `~` expansion and `${VAR}` environment variable substitution." | Skills System, "External Skill Directories" | Exact config key/path and substitution support |
| "If an external skill directory is writable by the Hermes process, agent-managed skill updates can change files in that directory. Use filesystem permissions or a separate profile/toolset setup if shared external skills must stay read-only." | Skills System, "External Skill Directories → How it works" | External dirs are **not** a write-protection boundary by default — critical for any shared/team skill directory design (e.g. this repo's own `.agents/skills/` if ever wired as an `external_dirs` entry) |
| "If the same skill name exists in both the local dir and an external dir, the local version wins." | Skills System, "External Skill Directories → How it works" | Precedence rule |
| "Non-existent paths are silently skipped: If a configured directory doesn't exist, Hermes ignores it without errors." | Skills System, "External Skill Directories → How it works" | No error path to detect a mistyped `external_dirs` entry from the CLI alone |
| "Bundles take precedence over individual skills when slugs collide." | Skills System, "Skill Bundles → Behavior" | Explicit precedence — opposite direction from the local-vs-external rule above |
| "Missing skills are skipped, not fatal." | Skills System, "Skill Bundles → Behavior" | Bundle robustness guarantee |
| "Bundles do not invalidate the prompt cache. They generate a fresh user message at invocation time... no system prompt mutation." | Skills System, "Skill Bundles → Behavior" | Cache-cost implication for repeated bundle use |
| "By default the agent writes skills freely — including from the background self-improvement review that runs after a turn." | Skills System, "Gating agent skill writes" | Default is unrestricted; `skills.write_approval` is opt-in |
| "When `write_approval: true`, every `skill_manage` write (create / edit / patch / delete / write_file / remove_file) is staged instead of committed — a SKILL.md is too large to review inline, so staging applies regardless of whether the write came from a foreground turn or the background review." | Skills System, "Gating agent skill writes" | Staging applies uniformly to foreground and background writes |
| "The separate `skills.guard_agent_created` setting is a content scanner (dangerous-pattern heuristics), not an approval gate — the two are independent." | Skills System, "Gating agent skill writes" | Explicit statement that the two governance mechanisms (write_approval vs. guard_agent_created) are orthogonal |
| "skills: guard_agent_created: true # default: false" ... "The scanner is off by default — real agent workflows that legitimately touch `~/.ssh/` or mention `$OPENAI_API_KEY` were tripping the heuristic too often." | Configuration, "Guard on agent-created skill writes" | Exact default (`false`) and the documented reason it defaults off |
| "skills: write_approval: false # false = write freely (default) \| true = stage every write for review" | Configuration, "Write approval for skill writes" | Exact default and key |
| "Official optional skills (`official/...`) are treated as built-in trust and do not show the third-party warning panel." | Skills System, "Security scanning and --force" | Official optional skills bypass the third-party warning even though install is explicit |
| "`--force` can override policy blocks for caution/warn-style findings." / "`--force` does not override a `dangerous` scan verdict." | Skills System, "Security scanning and --force" | Exact override ceiling |
| "builtin — Ships with Hermes — Always trusted" / "official — optional-skills/ in the repo — Built-in trust, no third-party warning" / "trusted — Trusted registries/repos such as openai/skills, anthropics/skills, huggingface/skills, NVIDIA/skills — More permissive policy" / "community — Everything else — Non-dangerous findings can be overridden with --force; dangerous verdicts stay blocked" | Skills System, "Trust levels" | The 4-tier trust model, verbatim |
| "GitHub rate limits: Skills hub operations use the GitHub API, which has a rate limit of 60 requests/hour for unauthenticated users... set GITHUB_TOKEN in your .env file to increase the limit to 5,000 requests/hour." | Skills System, "Update lifecycle" | Operational gotcha for any automated/CI use of `hermes skills` against GitHub-backed sources |
| "Each skill directory must contain a SKILL.md with standard SKILL.md frontmatter (name, description, plus optional metadata.hermes.tags, version, author, platforms, metadata.hermes.config)." / "Skills whose directory name starts with `.` or `_` are ignored." | Skills System, "Publishing a custom skill tap → Repo layout → Rules" | Exact tap-repo authoring rules |
| "New taps are assigned `community` trust by default... If your org or a widely-trusted source should get higher trust, add its repo to `TRUSTED_REPOS` in `tools/skills_hub.py` (requires a Hermes core PR)." | Skills System, "Trust levels for taps" | Raising trust for an org's own tap is not user-configurable — it requires a core code change |
| "On each sync, Hermes recomputes the hash of your local copy and compares it to the origin hash: Unchanged → safe to pull upstream... Changed → treated as user-modified and skipped forever" | Skills System, "Bundled skill updates" | Exact drift-detection mechanism for `hermes update` |
| "Each profile has its own `.bundled_manifest` under its own `HERMES_HOME`, so `hermes -p coder skills reset <skill>` only affects that profile." | Skills System, "Bundled skill updates → Profiles" | Per-profile isolation of bundled-skill state — relevant if stage 080 uses Hermes profiles per worker seat |
| "Make it a Skill when: The capability can be expressed as instructions + shell commands + existing tools... Make it a Tool when: It requires end-to-end integration with API keys, auth flows, or multi-component configuration" | Creating Skills, "Should it be a Skill or a Tool?" | The documented decision boundary, with worked examples both directions |
| "Disable substitution globally with `skills.template_vars: false` in `config.yaml`." | Creating Skills, "Referencing bundled scripts from SKILL.md" | `${HERMES_SKILL_DIR}` / `${HERMES_SESSION_ID}` substitution has a global kill-switch |
| "This is off by default — any snippet in a SKILL.md runs on the host without approval, so only enable it for skill sources you trust" | Creating Skills, "Inline shell snippets (opt-in)" | `skills.inline_shell` executes unapproved host commands when on — a meaningful security posture note for any shared/tap-sourced skill |
| "Snippets run with the skill directory as their working directory, and output is capped at 4000 characters." | Creating Skills, "Inline shell snippets" | Exact execution context and output cap |
| "If your skill is official and useful but not universally needed... put it in `optional-skills/`... If your skill is specialized, community-contributed, or niche, it's better suited for a Skills Hub" | Creating Skills, "Where Should the Skill Live?" | 3-tier placement decision: bundled / optional-skills / Hub |
| "Installing a blueprint... Hermes registers it as a suggested cron job rather than scheduling it. Scheduling is opt-in — installing never silently creates a recurring job." | Creating Skills, "Blueprints" | Installing a blueprint skill never auto-schedules — explicit accept step required |
| "The blueprint layer adds no new object type, store, or transport — the blueprint is a skill, the schedule is a cron job, and sharing is the existing publish/tap/index path." | Creating Skills, "Blueprints" | Architectural claim: blueprints are not a separate subsystem |
| "By default (`prune_builtins: true`) the curator can archive unused bundled built-in skills... after `archive_after_days` of non-use, alongside the agent-created skills it primarily manages. Hub-installed skills are always off-limits." | Curator, intro | Default curator scope includes bundled skills, always excludes hub-installed |
| "The curator also never auto-deletes — the worst outcome is archival into `~/.hermes/skills/.archive/`, which is recoverable." | Curator, intro | Hard safety ceiling on curator actions |
| "On a brand-new install... the curator does not run immediately... defers the first real pass by one full `interval_hours`." | Curator, "How it runs → First-run behavior" | New-install grace period before any curator mutation is possible |
| "Skills unused for `stale_after_days` (30) become `stale`; skills unused for `archive_after_days` (90) are moved to `~/.hermes/skills/.archive/`." | Curator, "How it runs" | Exact default thresholds |
| "Never-used skills (`use_count == 0`) get a grace floor: they are not archived until they are at least `stale_after_days` old." | Curator, "How it runs" | Zero-use skills are not immediately archivable |
| "Pinned skills and skills referenced by any cron job (including paused/disabled jobs) are skipped entirely" | Curator, "How it runs" | Cron-referenced skills get pin-equivalent protection automatically, without an explicit pin |
| "curator: enabled: true / interval_hours: 168 / min_idle_hours: 2 / stale_after_days: 30 / archive_after_days: 90 / consolidate: false / prune_builtins: true" | Curator, "Configuration" | Full default config block, verbatim |
| "A skill qualifies when ALL of the following are true: 1. Its name is not in `.bundled_manifest`. 2. Its name is not in `.hub/lock.json`. 3. Its `.usage.json` entry has `\"created_by\": \"agent\"` or `\"agent_created\": true`." | Curator, "What 'agent-created' means" | Exact 3-condition eligibility test for curator jurisdiction |
| "Skills the foreground agent creates via `skill_manage(action=\"create\")` during a conversation are not marked as agent-created — they are considered user-directed and the curator intentionally leaves them alone." | Curator, "What 'agent-created' means" | Foreground-created skills are permanently outside curator jurisdiction unless explicitly adopted |
| "`created_by` is a policy flag, not a provenance claim... it is consumed as \"may autonomous curation touch this?\" — not \"who wrote this file\"." | Curator, "Adopting unmanaged skills" | Important semantic clarification to avoid misreading the field |
| "Only agent-created skills can be pinned — `hermes curator pin` refuses on bundled and hub-installed skills" | Curator, "Pinning a skill" | Pin is scoped; cannot be used on bundled/hub skills |
| "A small set of protected built-ins is hardcoded as never-archivable and never-consolidatable, regardless of `curator.prune_builtins`, pin state, or LLM judgment... for example, `plan` powers the `/plan` slash-command flow" | Curator, "Pinning a skill" | Certain load-bearing built-ins are protected unconditionally, independent of all curator settings |
| "Before every real curator pass, Hermes takes a tar.gz snapshot of `~/.hermes/skills/`" | Curator, "Backups and rollback" | Automatic pre-mutation snapshot, unconditional on real (non-dry-run) passes |
| "Bundled and hub-installed skills are explicitly excluded from telemetry writes." | Curator, "Usage telemetry" | `.usage.json` only tracks agent-created (and adopted) skills |
| "Plugin skills are not listed in the system prompt and don't appear in `skills_list`. They're opt-in — load them explicitly when you know a plugin provides one." | Work with Skills, "Plugin-Provided Skills" | Plugin-bundled skills are invisible to normal discovery — a 4th discovery path distinct from bundled/user/external |
| "Installed skills take effect in new sessions. If you want it available in the current session, use `/reset` to start fresh, or add `--now` to invalidate the prompt cache immediately (costs more tokens on the next turn)." | Work with Skills, "Installing from the Hub" | New installs are not live in the current session by default |
| "Rule of thumb: If you'd put it in a reference document, it's a skill. If you'd put it on a sticky note, it's memory." | Work with Skills, "Skills vs Memory" | The documented heuristic for the skills/memory boundary |
| "Bundle skills — `ctx.register_skill(name, path)` — namespaced as `plugin:skill`, loaded via `skill_view(\"plugin:skill\")`" | Plugins, capability table | Confirms the plugin-skill API and namespace format from the source-code side of the docs |
| "skills: disabled: [] # globally disabled skills / platform_disabled: telegram: [skill-a, skill-b] # disabled only on telegram" | FAQ, "Managing skills on Telegram (slash command limit)" | `skills.disabled` / `skills.platform_disabled` config keys — not documented on the Skills System page itself; only surfaced here and via the `hermes skills` per-platform TUI mention in Work with Skills |
| "Skills with very long descriptions are truncated to 40 characters in the Telegram menu to stay within payload size limits." | FAQ, same section | Concrete Telegram-specific truncation limit |

---

## 5. Reference Tables

### 5a. SKILL.md frontmatter fields (superset of Skills System + Creating Skills)

| Field | Location | Type | Default | Description |
|---|---|---|---|---|
| `name` | top-level | string | required | Skill identifier / slash-command slug |
| `description` | top-level | string | required | Shown in skill search results / `skills_list()` |
| `version` | top-level | string | undocumented (example shows `1.0.0`) | Skill version |
| `author` | top-level | string | undocumented | Creating Skills example only |
| `license` | top-level | string | undocumented | Creating Skills example only (e.g. `MIT`) |
| `platforms` | top-level | list, one of `macos`/`linux`/`windows` | omitted = all platforms | Restricts skill visibility (system prompt, `skills_list()`, slash commands) to listed OS(es) |
| `metadata.hermes.tags` | nested | list of strings | undocumented | Categorization/search keywords |
| `metadata.hermes.category` | nested | string | undocumented | Category directory grouping |
| `metadata.hermes.related_skills` | nested | list of strings | undocumented | Creating Skills example only |
| `metadata.hermes.requires_toolsets` | nested | list of strings | undocumented (absent = always shown) | Hide skill when ANY listed toolset is unavailable |
| `metadata.hermes.requires_tools` | nested | list of strings | undocumented | Hide skill when ANY listed tool is unavailable |
| `metadata.hermes.fallback_for_toolsets` | nested | list of strings | undocumented | Hide skill when ANY listed toolset IS available |
| `metadata.hermes.fallback_for_tools` | nested | list of strings | undocumented | Hide skill when ANY listed tool IS available |
| `metadata.hermes.config` | nested | list of objects (`key`, `description`, `default`, `prompt`) | undocumented | Declares non-secret settings stored under `skills.config.*` |
| `metadata.hermes.blueprint` | nested | object (`schedule`, `deliver`, `prompt`, `no_agent`) | `deliver` default `origin`; others undocumented | Presence of `blueprint:` block marks the skill a runnable automation |
| `required_environment_variables` | top-level | list of objects (`name` required; `prompt`, `help`, `required_for` optional) | n/a | Declares secrets prompted for on load, auto-passed to sandboxes |
| `prerequisites.env_vars` | top-level (legacy) | — | — | "Legacy `prerequisites.env_vars` remains supported as a backward-compatible alias" (for `required_environment_variables`) |
| `required_credential_files` | top-level | list of objects (`path` required, relative to `~/.hermes/`; `description` optional) | n/a | Declares OAuth/credential files to mount read-only into sandboxes |

### 5b. Skill directory structure (user-facing, `~/.hermes/skills/`)

| Path | Purpose |
|---|---|
| `<category>/<skill-name>/SKILL.md` | Required — main instructions |
| `<category>/<skill-name>/references/` | Additional docs, loaded on demand via `skill_view(name, path)` |
| `<category>/<skill-name>/templates/` | Output-format templates |
| `<category>/<skill-name>/scripts/` | Helper scripts callable from the skill |
| `<category>/<skill-name>/examples/` | Referenced example outputs |
| `<category>/<skill-name>/assets/` | Supplementary files |
| `.hub/lock.json` | Hub-install provenance: source URL, content hash, scanner version, findings, timestamp, fresh-or-cached status |
| `.hub/quarantine/` | Quarantined bundle scan staging |
| `.hub/audit.log` | Hub audit trail |
| `.hub/taps.json` | Configured custom GitHub tap sources (path per tap) |
| `.bundled_manifest` | Maps bundled skill name → origin content hash at last sync |
| `.usage.json` | Curator telemetry sidecar (per-skill use/view/patch counts, state, pinned flag) |
| `.archive/` | Curator-archived skills (recoverable) |
| `.curator_backups/<timestamp>/skills.tar.gz` | Pre-run curator snapshots |

### 5c. Repo-side skill directory structure (for contributing bundled/optional skills)

| Path | Purpose |
|---|---|
| `skills/<category>/<skill-name>/SKILL.md` | Bundled skills shipped with every install |
| `optional-skills/<category>/<skill-name>/SKILL.md` | Official but not-active-by-default skills, installed via `hermes skills install official/<category>/<skill>` |
| `website/scripts/generate-skill-docs.py` | Regenerates the two catalog pages from repo content |

### 5d. Config keys (behavior documented here; schema/placement wiring belongs to `hermes-configuration`)

| Key | Default | Behavior |
|---|---|---|
| `skills.external_dirs` | undocumented default (implicitly empty list) | Additional directories scanned alongside `~/.hermes/skills/`; supports `~` and `${VAR}` expansion |
| `skills.write_approval` | `false` | Stages every `skill_manage` write (create/edit/patch/delete/write_file/remove_file) for approval via `/skills pending|diff|approve|reject|approval` |
| `skills.guard_agent_created` | `false` | Enables a dangerous-keyword content scanner on agent `skill_manage` writes; independent of `write_approval` |
| `skills.config.<key>` | n/a | Namespace for skill-declared non-secret settings |
| `skills.disabled` | `[]` | Globally disabled skill names |
| `skills.platform_disabled.<platform>` | undocumented default (implicitly empty per platform) | Per-platform disabled skill names, e.g. `telegram: [skill-a, skill-b]` |
| `skills.template_vars` | undocumented default (implicitly `true`) | Global kill-switch for `${HERMES_SKILL_DIR}`/`${HERMES_SESSION_ID}` substitution |
| `skills.inline_shell` | `false` (documented as "off by default") | Enables `!\`cmd\`` inline shell snippet execution inside SKILL.md bodies |
| `skills.inline_shell_timeout` | `10` (seconds, per example) | Per-snippet timeout when `inline_shell` is on |
| `curator.enabled` | `true` | Master on/off for the curator |
| `curator.interval_hours` | `168` (7 days) | Minimum time between curator runs |
| `curator.min_idle_hours` | `2` | Minimum agent idle time before a run triggers |
| `curator.stale_after_days` | `30` | Inactivity threshold for `active → stale` |
| `curator.archive_after_days` | `90` | Inactivity threshold for `stale → archived` |
| `curator.consolidate` | `false` | Enables the opt-in LLM umbrella-building/consolidation pass |
| `curator.prune_builtins` | `true` | Whether bundled built-in skills are eligible for archival (hub skills always exempt regardless) |
| `curator.backup.enabled` | undocumented default (examples imply `true`) | Gates automatic + manual snapshotting together |
| `curator.backup.keep` | `5` | Snapshot retention count |
| `auxiliary.curator.{provider,model,timeout,extra_body,base_url,api_key}` | `provider: auto` implied default | Routes the curator's LLM review pass; `auto` = use main chat model |
| `curator.auxiliary.{provider,model}` (legacy) | — | Deprecated alias for `auxiliary.curator`; still works, logs a deprecation line |

### 5e. `skill_manage` tool actions

| Action | Use for | Key params |
|---|---|---|
| `create` | New skill from scratch | `name`, `content` (full SKILL.md), optional `category` |
| `patch` | Targeted fixes (preferred — more token-efficient) | `name`, `old_string`, `new_string` |
| `edit` | Major structural rewrites | `name`, `content` (full SKILL.md replacement) |
| `delete` | Remove a skill entirely | `name` |
| `write_file` | Add/update supporting files | `name`, `file_path`, `file_content` |
| `remove_file` | Remove a supporting file | `name`, `file_path` |

### 5f. Skills Hub sources and trust levels

| Source id | Example identifier | Trust level | Notes |
|---|---|---|---|
| `official` | `official/security/1password` | `official` (built-in trust) | Maintained in-repo under `optional-skills/`; no third-party warning |
| `skills-sh` | `skills-sh/vercel-labs/agent-skills/vercel-react-best-practices` | `community` (unless repo matches `TRUSTED_REPOS`) | Vercel's public directory; alias-slug resolution |
| `well-known` | `well-known:https://mintlify.com/docs/.well-known/skills/mintlify` | `community` | `/.well-known/skills/index.json` convention, not a centralized hub |
| `url` (github/direct URL install) | `https://sharethis.chat/SKILL.md` | `community` (always) | Name resolution order: frontmatter `name:` → parent dir slug (must match `^[a-z][a-z0-9_-]*$`) → interactive prompt → `--name` flag |
| `github` | `openai/skills/k8s` | `trusted` if in `TRUSTED_REPOS` (`openai/skills`, `anthropics/skills`, `huggingface/skills`, `NVIDIA/skills`), else `community` | Also supports custom taps via `hermes skills tap add` |
| `clawhub` | community marketplace | `community` | Third-party |
| `lobehub` | LobeHub catalog conversion | `community` | Converts agent entries into installable skills |
| `browse-sh` | `browse-sh/airbnb.com/search-listings-ddgioa` | `community` (explicitly labeled) | 200+ site-specific browser-automation skills |

### 5g. `hermes skills` CLI subcommands

| Subcommand | Purpose |
|---|---|
| `browse [--source official]` | Paginated browser for skill registries |
| `search <query> [--source ...]` | Search skill registries |
| `install <id> [--force] [--name] [--category]` | Install a skill |
| `inspect <id>` | Preview a skill (incl. upstream metadata) without installing |
| `list [--source hub]` | List installed skills |
| `check` | Check installed hub skills for upstream updates |
| `update [<skill>]` | Reinstall hub skills with upstream changes |
| `audit` | Re-scan all hub skills for security |
| `uninstall <skill>` | Remove a hub-installed skill |
| `reset <skill> [--restore] [--yes]` | Un-stick a bundled skill flagged `user_modified`; `--restore` also replaces content |
| `opt-out [--remove]` | Stop bundled-skill seeding; `--remove` also deletes unmodified bundled skills |
| `opt-in [--sync]` | Undo opt-out |
| `publish <path> --to github --repo owner/repo` | Publish a skill |
| `snapshot export/import <file>` | Export/import skill configuration |
| `tap add/remove/list <repo>` | Manage custom GitHub skill sources |
| `config <skill>` / bare `hermes skills` | Interactive per-platform enable/disable TUI |

### 5h. `hermes bundles` and `hermes curator` CLI subcommands

| Command family | Subcommand | Purpose |
|---|---|---|
| `hermes bundles` | `list` | List installed bundles (default) |
| | `show <name>` | Show one bundle's detail |
| | `create <name> [--skill ...] [-d desc] [--force]` | Create/overwrite a bundle |
| | `delete <name>` | Remove a bundle |
| | `reload` | Re-scan `~/.hermes/skill-bundles/` |
| `hermes curator` | `status` | Show stats, pinned list, LRU top 5 |
| | `run [--consolidate] [--background] [--dry-run]` | Trigger a run |
| | `backup [--reason]` / `rollback [--list] [--id] [-y]` | Manual snapshot / restore |
| | `pause` / `resume` | Toggle runs |
| | `pin <skill>` / `unpin <skill>` | Protect a skill from auto-transition and `skill_manage delete` |
| | `adopt <skill>... [--all-unmanaged] [--dry-run] [--yes]` | Bring unmanaged skills under curator jurisdiction |
| | `list-unmanaged` | Itemize skills with no provenance marker |
| | `restore <skill>` | Un-archive a skill |
| | `list-archived` | List archived skills |
| | `archive <skill>` | Manually archive one skill |
| | `prune [--days N]` | Bulk-archive idle agent-created skills |

### 5i. Skill-related slash commands (surfaces: CLI-only / both CLI+messaging, per the reference page's own annotations)

| Slash command | Surfaces | Purpose |
|---|---|---|
| `/<skill-name> [args]` | Both | Load any installed skill on-demand |
| `/skills [browse\|search\|inspect\|install\|check\|update\|reset\|list\|config\|pending\|diff\|approve\|reject\|approval]` | Search/browse/install: CLI-only. Write-approval review subcommands: both, only shown when the gate is on or writes are staged | Full skills-hub + write-approval-review surface |
| `/bundles` | Both | List configured skill bundles |
| `/learn <source/description>` | Both (CLI, gateway, TUI, dashboard) | Distill a skill from described sources |
| `/curator [status\|run\|pin\|archive]` | Both | Background skill maintenance controls |
| `/reload-skills` (alias `/reload_skills`) | Both | Re-scan `~/.hermes/skills/` for new/removed skills |
| `/journey [list\|delete\|edit]` (aliases `/learning`, `/memory-graph`) | CLI/TUI/desktop app only, not messaging | Timeline of learned skills + memories |
| `/commands [page]` | Messaging-only | Browse all commands and skills, paginated |
| `/context all` | Both | Adds per-skill and per-toolset token-cost listings |

---

## 6. Official Examples (verbatim)

### SKILL.md format (Skills System page)

```markdown
---
name: my-skill
description: Brief description of what this skill does
version: 1.0.0
platforms: [macos, linux]     # Optional — restrict to specific OS platforms
metadata:
  hermes:
    tags: [python, automation]
    category: devops
    fallback_for_toolsets: [web]    # Optional — conditional activation (see below)
    requires_toolsets: [terminal]   # Optional — conditional activation (see below)
    config:                          # Optional — config.yaml settings
      - key: my.setting
        description: "What this controls"
        default: "value"
        prompt: "Prompt for setup"
---
# Skill Title
## When to Use
Trigger conditions for this skill.
## Procedure
1. Step one
2. Step two
## Pitfalls
- Known failure modes and fixes
## Verification
How to confirm it worked.
```

### SKILL.md format (Creating Skills page — superset)

```markdown
---
name: my-skill
description: Brief description (shown in skill search results)
version: 1.0.0
author: Your Name
license: MIT
platforms: [macos, linux]          # Optional — restrict to specific OS platforms
                                    #   Valid: macos, linux, windows
                                    #   Omit to load on all platforms (default)
metadata:
  hermes:
    tags: [Category, Subcategory, Keywords]
    related_skills: [other-skill-name]
    requires_toolsets: [web]            # Optional — only show when these toolsets are active
    requires_tools: [web_search]        # Optional — only show when these tools are available
    fallback_for_toolsets: [browser]    # Optional — hide when these toolsets are active
    fallback_for_tools: [browser_navigate]  # Optional — hide when these tools exist
    config:                              # Optional — config.yaml settings the skill needs
      - key: my.setting
        description: "What this setting controls"
        default: "sensible-default"
        prompt: "Display prompt for setup"
    blueprint:                              # Optional — marks this skill a runnable automation
      schedule: "0 9 * * *"              #   cron expr / "every 2h" / ISO timestamp
      deliver: origin                    #   optional (default origin)
      prompt: "Task instruction for each run"  # optional
      no_agent: false                    # optional
required_environment_variables:          # Optional — env vars the skill needs
  - name: MY_API_KEY
    prompt: "Enter your API key"
    help: "Get one at https://example.com"
    required_for: "API access"
---
# Skill Title
Brief intro.
## When to Use
Trigger conditions — when should the agent load this skill?
## Quick Reference
Table of common commands or API calls.
## Procedure
Step-by-step instructions the agent follows.
## Pitfalls
Known failure modes and how to handle them.
## Verification
How the agent confirms it worked.
```

### External Skill Directories config (Skills System page)

```yaml
skills:
  external_dirs:
    - ~/.agents/skills
    - /home/shared/team-skills
    - ${SKILLS_REPO}/skills
```

### Skill Bundle YAML schema (Skills System page)

```yaml
name: backend-dev
description: Backend feature work — review, test, PR workflow.
skills:
  - github-code-review
  - test-driven-development
  - github-pr-workflow
instruction: |
  Always start by writing failing tests, then implement.
  Open the PR through the standard workflow with co-author tags.
```

### Minimal tap example (Skills System page)

Repo `my-org/hermes-skills`:

```text
my-org/hermes-skills
└── skills/
    └── deploy-runbook/
        └── SKILL.md
```

`skills/deploy-runbook/SKILL.md`:

```markdown
---
name: deploy-runbook
description: Our deployment runbook — services, rollback, Slack channels
version: 1.0.0
author: My Org Platform Team
metadata:
  hermes:
    tags: [deployment, runbook, internal]
---
# Deploy Runbook
Step 1: ...
```

### Curator default config block (Curator page)

```yaml
curator:
  enabled: true
  interval_hours: 168          # 7 days
  min_idle_hours: 2
  stale_after_days: 30
  archive_after_days: 90
  consolidate: false           # LLM umbrella-building pass — opt-in (prune-only by default)
  prune_builtins: true         # archive unused bundled built-in skills too (hub skills always exempt)
```

### Curator usage telemetry entry (Curator page)

```json
{
  "my-skill": {
    "use_count": 12,
    "view_count": 34,
    "last_used_at": "2026-04-24T18:12:03Z",
    "last_viewed_at": "2026-04-23T09:44:17Z",
    "patch_count": 3,
    "last_patched_at": "2026-04-20T22:01:55Z",
    "created_at": "2026-03-01T14:20:00Z",
    "state": "active",
    "pinned": false,
    "archived_at": null
  }
}
```

### Write-approval gate config (Configuration page)

```yaml
skills:
  guard_agent_created: true   # default: false
```

```yaml
skills:
  write_approval: false   # false = write freely (default) | true = stage every write for review
```

### Per-platform disable config (FAQ page)

```yaml
skills:
  disabled: []                    # globally disabled skills
  platform_disabled:
    telegram: [skill-a, skill-b]  # disabled only on telegram
```

### Skill config settings (Creating Skills page)

```yaml
metadata:
  hermes:
    config:
      - key: myplugin.path
        description: Path to the plugin data directory
        default: "~/myplugin-data"
        prompt: Plugin data directory path
      - key: myplugin.domain
        description: Domain the plugin operates on
        default: ""
        prompt: Plugin domain (e.g., AI/ML research)
```

Resulting storage:

```yaml
skills:
  config:
    myplugin:
      path: ~/my-data
```

---

## 7. Recommendations Found (docs-phrased best practices, quoted)

- "Keep skills focused. A skill that tries to cover 'all of DevOps' will be too long and too vague. A skill that covers 'deploy a Python app to Fly.io' is specific enough to be genuinely useful." — Work with Skills, Tips
- "Let the agent create skills... Say yes — these agent-authored skills capture the exact workflow including pitfalls that were discovered along the way." — Work with Skills, Tips
- "Use categories. Organize skills into subdirectories... This keeps the list manageable and helps the agent find relevant skills faster." — Work with Skills, Tips
- "Update skills when they go stale... Skills that aren't maintained become liabilities." — Work with Skills, Tips
- "Prefer stdlib Python, curl, and existing Hermes tools (`web_extract`, `terminal`, `read_file`). If a dependency is needed, document installation steps in the skill." — Creating Skills, "No External Dependencies"
- "Put the most common workflow first. Edge cases and advanced usage go at the bottom. This keeps token usage low for common tasks." — Creating Skills, "Progressive Disclosure"
- "For XML/JSON parsing or complex logic, include helper scripts in `scripts/` — don't expect the LLM to write parsers inline every time." — Creating Skills, "Include Helper Scripts"
- "The `patch` action is preferred for updates — it's more token-efficient than `edit` because only the changed text appears in the tool call." — Skills System, "Actions" tip callout
- "If you want a stronger guarantee than 'no deletion'... edit `~/.hermes/skills/<name>/SKILL.md` directly with your editor. The pin guards tool-driven deletion, not your own filesystem access." — Curator, "Pinning a skill"
- "For combinations you use repeatedly, prefer a skill bundle — same effect under one short command." — Skills System, "Stacking multiple skills in one command"

---

## 8. Boundary Notes (content belonging to a sibling skill)

- `skills.*` config key schema/placement wiring in `config.yaml` (as opposed to the *behavior* documented here) → `hermes-configuration`.
- Pinning skills to kanban tasks, and kanban's own `--skill` attachment surface (`hermes kanban create ... --skill`) → `hermes-kanban`.
- Admin-tier pins/secrets for skill-related settings under `/etc/hermes` (managed scope) → `hermes-managed-scope`.
- Event hooks in general (`on_skill_lifecycle` plugin hook point, `HOOK.yaml`/`handler.py` mechanism) → `hermes-hooks`. Note: the Plugins page lists `on_skill_lifecycle` as an Observer-category hook point but this dossier did not investigate its payload/semantics — flag to `hermes-hooks`.
- Sessions/checkpoints in general, and `/journey` as a session-timeline UI (this dossier only recorded that `/journey` also surfaces skills) → `hermes-sessions`.
- Full CLI reference beyond the skill-specific subcommand tables captured here (e.g. `hermes prompt-size`, `hermes dump`, `hermes migrate`/`hermes claude-migrate` full behavior) → `hermes-cli`.
- Cron `--skill`/`--add-skill`/`--remove-skill` attachment mechanics beyond "cron-referenced skills get curator pin-equivalent protection" (already captured as a normative statement above) → no `hermes-*` skill in the current taxonomy appears to own general Cron Jobs; flagged in Gaps below, not chased further per the "ignore overlaps" instruction.
- General Plugin system mechanics (`ctx.register_skill`, plugin manifest, `plugins/` discovery) beyond the specific `plugin:skill` namespace fact captured here → no `hermes-*` skill in the current taxonomy appears to own general Plugins either; same as above, flagged in Gaps.
- This repository's own `.agents/skills/` taxonomy is explicitly out of scope entirely (confirmed no overlap risk — it is a wholly separate, non-Hermes concept; the only touchpoint would be if `.agents/skills/` were ever wired into a Hermes worker's `skills.external_dirs`, which is not currently the case per this research).

---

## 9. Gaps & Open Questions

- **No exhaustive findings taxonomy on the docs site.** The docs name scanner categories generically ("data exfiltration patterns, prompt injection attempts, destructive commands, shell injection" — Creating Skills, "Security Scanning") but do not enumerate the actual heuristic patterns or severity levels. `source: repository, not docs` — `tools/skills_guard.py` (linked indirectly via web search, not from a docs-site page) shows an `INSTALL_POLICY` dict with a 3-tier verdict system (`safe`/`caution`/`dangerous`) per trust level, e.g. `"agent-created": ("allow", "allow", "ask")`. This is repository-sourced, not docs-sourced, and should be treated as supplementary only.
- **`skills.guard_agent_created` default may be about to change.** `source: repository, not docs` — a GitHub issue (`NousResearch/hermes-agent#16461`, "feat(security): Default skills.guard_agent_created to true") proposes flipping the default from `false` to `true`. As of this capture the *documented* default is still `false` (Configuration page, quoted above) — flag this as a currently-open proposal, not a shipped behavior change, and re-check on any future re-capture.
- **Bundled-skill count is stated inconsistently across pages.** `/docs/llms.txt` describes the Bundled Skills Catalog as "Table of all ~90 skills bundled with Hermes" and the Optional Skills Catalog as "Table of ~60 additional installable skills," but the live catalog tables as fetched contain roughly 70 and 140+ rows respectively. Treat the llms.txt summary counts as approximate/potentially stale relative to the live tables; cite the live table, not the summary line, if an exact count is ever needed.
- **`external_dirs`-to-`external_dirs` collision precedence is undocumented.** The docs state local-vs-external precedence ("local version wins") but not what happens if the *same* skill name exists in two different `external_dirs` entries simultaneously.
- **No documented default for `curator.backup.enabled`.** The docs only show it inside an explicit-`true` example block ("Set `curator.backup.enabled: false` to disable automatic snapshotting") — the implicit shipped default is inferable as `true` but never stated as a bare fact the way `curator.enabled: true` is in the main defaults block.
- **`skills.template_vars` and `skills.inline_shell_timeout` are documented only via their disable/example snippets, not a canonical defaults block** — same category of soft gap as above (inferred `true`/`10s` from prose, not from a `DEFAULT_CONFIG`-style table).
- **Ownership gap for general Cron Jobs and general Plugins topics.** Neither appears as a dedicated `hermes-*` skill in this repository's current taxonomy (checked against the AGENTS.md skill list), even though both intersect the skills system (cron's `--skill` attachment; plugin-bundled `plugin:skill` skills). This dossier captured only the narrow skill-system-facing slice of each; a reviewer may want to flag this taxonomy gap separately from the hermes-skills skill itself.
- **FAQ page's skill-relevant entries were found by full-page grep, not systematic top-to-bottom reading** — it's possible other skill-adjacent troubleshooting entries exist in the ~770-line page that a keyword-only pass missed (e.g. entries that discuss skills without the literal substring "skill" in that exact sentence). Low confidence risk, but worth a note.

---

## 10. Suggested SKILL.md Inputs

*Input for the reviewer — not an edit to the skill itself.*

- **Key concept — dual independent governance gates.** State clearly, citing §4 rows for `skills.write_approval` (default `false`) and `skills.guard_agent_created` (default `false`): these are two separate, composable mechanisms (approval-staging vs. content-scanning), not one setting with two names. Derived from the exact quote "the two are independent" (Skills System, "Gating agent skill writes").
- **Key concept — where a new skill should live.** Reproduce the 3-tier decision (bundled repo skill / `optional-skills/` / Skills Hub) from §4's "Where Should the Skill Live?" quote, since this repo's own skill-authoring guidance (`maintain-rules-and-skills`) will need to make an analogous call for anything written for Hermes worker seats specifically (as opposed to this repo's own `.agents/skills/`).
- **Key concept — external_dirs is not a read-only boundary.** Surface the exact quote from §4 ("External dirs are not a write-protection boundary") prominently if stage 080 ever wires a shared team skill directory via `skills.external_dirs` — this is a security-relevant gotcha, not just a technical detail.
- **Workflow step — before authoring any Hermes-facing SKILL.md, consult §5a's frontmatter field table** to avoid re-deriving the field list from memory; note the field superset (Creating Skills has fields — `blueprint`, `required_credential_files`, `license`, `author` — that Skills System's own example omits).
- **Workflow step — for any skill install via `hermes skills install`/`tap add`, apply §5f's trust-level table** before assuming a `--force` override is safe (it never overrides a `dangerous` verdict, per the exact quote in §4).
- **Validation command — `hermes curator status`** to confirm curator jurisdiction/state before assuming a change to an agent-created skill will persist through the curator's pruning pass (derived from §4's "agent-created" 3-condition test and the `.usage.json` schema in §6).
- **Validation command — `hermes skills list | grep <name>`** (or `/skills search <name>`) to verify a new/updated skill is discoverable, per the "Verifying Installation" pattern in the Working with Skills guide page map (§3).
- **Cross-reference — link to Curator's pin/unpin CLI (§5h) from any guidance about hand-authored skills that must never be auto-archived**, since only agent-created skills can be pinned (§4 quote) — a hand-written skill placed under `~/.hermes/skills/` is already outside curator jurisdiction by default and needs no pin, but this distinction should be stated explicitly to avoid confusion.

---

## Reviewer addendum (2026-08-12)

### Verification outcome

All eight spot-checked load-bearing quotes verified verbatim. The two
repository-sourced items (scanner verdict tiers from `tools/skills_guard.py`;
the open issue proposing to default `skills.guard_agent_created` to `true`)
remain flagged as supplementary, per the dossier's own discipline — the
SKILL.md states the documented default (`false`) and notes the open
proposal.

### Stage 080 relevance notes

- The official `external_dirs` example itself lists `~/.agents/skills` as
  a plausible entry. If stage 080 ever wires a shared or repo-provided
  skill directory into a worker seat via `skills.external_dirs` (the
  scaffold already uses this mechanism), the "writable external dirs are
  mutable by agent-managed writes" and "nonexistent paths are silently
  skipped" facts are the two operational gotchas to design against.
- The bundled-sync hash rule ("changed → user-modified → skipped forever")
  parallels the drift-detection pattern the scaffold's own skill-authoring
  law relies on (version bump on every content change) — the official
  mechanism is content-hash-based, not version-based.

### Taxonomy gap (for the maintainer, not this skill)

General Cron Jobs and general Plugins have no owning `hermes-*` skill in
this repo's family; both intersect the skills system (cron `--skill`
attachment, `plugin:skill` namespace). Recorded in `source-capture.md`
open items.

---

## Addendum 2 (reviewer, 2026-08-12): full-page coverage audit + gap closure

A section-by-section audit of the live Skills System page (complete
heading outline fetched 2026-08-12) against this extraction confirmed NO
new sections since capture, and identified four under-captured
subsections, now closed with verbatim quotes:

### Skill output and media delivery (+ `[[as_document]]`)

- QUOTE: "When a skill response includes a bare absolute path to a media
  file — for example `/home/user/screenshots/diagram.png` — the gateway
  auto-detects it, strips it from the visible text, and delivers the file
  natively to the user's chat."
- QUOTE: "If a response contains the literal directive `[[as_document]]`,
  every media path extracted from that response is delivered as a
  document/file attachment rather than an image bubble." Rationale:
  preserves resolution ("Telegram's `sendPhoto` recompresses it to
  ~200 KB at 1280 px, destroying readability").

### `/learn` — knowledge-base skills for large sources

- QUOTE: "`/learn` is the fast way to turn something you already know —
  or a pile of reference material — into a reusable skill, without
  hand-writing the `SKILL.md`."
- QUOTE: "When the source is a book, a stack of papers, a spec, or a
  large docs folder, the agent doesn't cram it into one file or reduce it
  to a lossy summary. Instead it authors an expansive knowledge-base
  skill." — one distilled file per chapter/topic under `references/`,
  loaded on demand via `skill_view`.

### Publishing a tap — non-default paths

- QUOTE: "If your skills don't live under `skills/` (common when you're
  adding a `skills/` subtree to an existing project), edit the tap entry
  in `~/.hermes/skills/.hub/taps.json`" — e.g. `"path": "internal/skills/"`.

### Installing individual skills directly (without adding a tap)

- QUOTE: "install a single skill from any public GitHub repo without
  adding the whole repo as a tap: `hermes skills install
  owner/repo/skills/my-workflow`" — for sharing one skill "without asking
  the user to subscribe to your whole registry."

Coverage status after this addendum: every heading on the live page
(## through #####, 50 headings total) is represented in this extraction
or the original dossier's page map. SKILL.md updated to v1.1.0 with the
media-delivery, /learn, tap-path, and direct-install facts.
