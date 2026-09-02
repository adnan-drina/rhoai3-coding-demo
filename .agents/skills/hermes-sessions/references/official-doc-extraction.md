# Official Doc Extraction — hermes-sessions

Validated research dossier (capture date 2026-08-12). Reviewer validation:
the sessions.json admonition, session-ID grammar, prune defaults and
guarantees, delegate-cascade rule, and the checkpoint opt-in/shadow-store/
restore/guards quotes were all re-verified verbatim against live pages on
2026-08-12. The dossier's headline gap (worker session provenance) was
resolved by the reviewer against the shipped source — see the addendum.
Original dossier: `source-analysis/hermes/hermes-sessions-capture.md`.

---

# hermes-sessions — Documentation Capture Dossier

## Executive Summary (read first)

- **Captured:** Session lifecycle/identity (CLI + gateway), full SQLite-backed
  storage schema, resume/handoff mechanics, session search (FTS5), per-platform
  session keying, expiry/auto-prune, and the full Checkpoints & Rollback
  subsystem (shadow git store, triggers, config, safety guards). All from the
  two primary pages plus three developer-guide pages plus targeted CLI/slash
  reference grep and three boundary pages (delegation, kanban, profiles).
- **Confidence:** High for the two primary user-guide pages and the three
  developer-guide pages — full page content read. Medium for CLI-commands /
  slash-commands / delegation / kanban — read via targeted grep on saved full
  fetches (not every line of those large pages was read), so treat anything
  from them as representative, not exhaustive.
- **Biggest gap:** The current skill's stage-080-provenance assumption — that
  Hermes kanban records a `worker_session_id` in task completion metadata — is
  **not documented anywhere in official sources**. `kanban_complete`'s
  `metadata` field is free-form/model-supplied JSON with no schema requiring a
  session id; the only session-correlation primitive documented is the
  `HERMES_SESSION_ID` env var exported into tool subprocesses (not into kanban
  task rows). This is a load-bearing gap for stage 080 — see Gaps §9.
- **Contradicts current placeholder:** No contradiction found. The placeholder's
  two pinned URLs (`/docs/user-guide/sessions`,
  `/docs/user-guide/checkpoints-and-rollback`) are both correct and current.
- **Suggested next skill:** `hermes-hooks` already has a capture
  (`hermes-hooks-capture.md` exists per directory listing) — recommend
  `hermes-cli` next, since this run surfaced a large `hermes sessions`/`hermes
  checkpoints` CLI surface that a full CLI reference pass should cross-check
  against the Reference → CLI Commands page in full (this run only grepped it).

---

## 1. Capture Header

| Field | Value |
| --- | --- |
| Product | Hermes Agent (Nous Research) |
| Product version | No version marker rendered on any fetched page (Docusaurus site; no visible "vX.Y" badge in extracted text). Internal version signals found: SQLite `schema_version` = 23 (Session Storage page); Checkpoints subsystem is "v2" with a documented v1→v2 migration (Checkpoints & Rollback page). |
| Capture date | 2026-08-12 |
| Docs site | https://hermes-agent.nousresearch.com |
| Index used | https://hermes-agent.nousresearch.com/docs/llms.txt (full page inventory, 135 lines, read in full) |

### Page inventory (from `/docs/llms.txt`)

**Read in full** (primary, directly in scope):
- `/docs/user-guide/sessions` — Sessions (primary topic page)
- `/docs/user-guide/checkpoints-and-rollback` — Checkpoints & Rollback (primary topic page)
- `/docs/developer-guide/session-storage` — Session Storage (SQLite schema, internals)
- `/docs/developer-guide/architecture` — Architecture (Session Persistence subsystem, data flow)
- `/docs/developer-guide/gateway-internals` — Gateway Internals (session routing, expiry, hooks)
- `/docs/user-guide/profiles` — Profiles (session scoping per `HERMES_HOME`, clone semantics)
- `/docs/user-guide/features/memory` — Persistent Memory (session_search cross-reference, memory-flush-on-session-end)
- `/docs/user-guide/git-worktrees` — Git Worktrees (checkpoint scope vs session scope clarification)

**Read via targeted grep on full saved fetch** (large reference/feature pages; only session/checkpoint-relevant lines extracted, not full read):
- `/docs/reference/cli-commands` (1502 lines saved; grepped for session/checkpoint terms)
- `/docs/reference/slash-commands` (294 lines saved; grepped)
- `/docs/reference/environment-variables` (954 lines saved; grepped for SESSION/CHECKPOINT/HERMES_HOME/HERMES_KANBAN)
- `/docs/user-guide/features/delegation` (303 lines saved; grepped for session)
- `/docs/user-guide/features/kanban` (780 lines saved; grepped for session_id/worker_session/task_runs/task_events/metadata)

**Deprioritized** (plausibly relevant, not fetched this run — reason given):
- `/docs/user-guide/features/cron` — Sessions page confirms `cron` is a session source and Architecture page shows cron creates "a fresh AIAgent (no history)"; deprioritized because cron's session semantics (no-history, one-off) are already fully covered by the two lines captured from Architecture/Sessions and cron's own config surface belongs to `hermes-configuration`/a cron-focused skill.
- `/docs/user-guide/tui`, `/docs/user-guide/features/batch-processing`, `/docs/guides/delegation-patterns` — mentioned only tangentially (batch is a session source per the Sessions table; TUI has a `/sessions` "switch" alias already captured via slash-commands grep); full read deprioritized for time given they add no new session-identity or storage facts beyond what's already captured.
- `/docs/user-guide/cli` — likely duplicates much of `/docs/reference/cli-commands`; not fetched separately.
- Pages referenced only as internal anchors and NOT found as standalone entries in `llms.txt` — "CLI Background Sessions" (linked from `/background` in slash-commands) and "Session Heartbeats" (linked from `/heartbeat`) — could not confirm a canonical URL from the index; flagged as a gap (see §9), not guessed.

**Dead links / redirects:** None encountered. All fetched URLs resolved on first request (HTTP 200 via the WebFetch tool; DNS/HTTP reachability independently confirmed via `curl`, since the WebFetch tool stalled on the very first three call attempts of this run before working normally afterward — a tooling transient, not a docs-site issue).

---

## 2. Recommended Source Pins

The current `references/source-capture.md` pins exactly two URLs. Both are correct and should stay. Recommend expanding the pin list to:

| Priority | URL | Why pin it |
| --- | --- | --- |
| Keep (primary) | `/docs/user-guide/sessions` | Session lifecycle, identity, resume, search, per-platform keying, expiry — the skill's core topic. |
| Keep (primary) | `/docs/user-guide/checkpoints-and-rollback` | Checkpoint/rollback mechanics — the skill's other core topic. |
| **Add** | `/docs/developer-guide/session-storage` | Authoritative SQLite schema (tables, columns, migrations) — needed for any provenance/audit design that reads `state.db` directly. |
| **Add** | `/docs/developer-guide/gateway-internals` | Session key format, session expiry as background maintenance, session-lifecycle hook events (`session:start`/`session:end`/`session:reset`) — the exact boundary with `hermes-hooks`. |
| **Add (recommended, not required)** | `/docs/developer-guide/architecture` | One-paragraph "Session Persistence" subsystem summary + data-flow diagrams showing where session save happens per entry point (CLI/gateway/cron) — cheap page, high orientation value. |
| Pages that proved irrelevant to this skill specifically | none — both original pins were on-topic and necessary | — |

No pin in the current file needs to be removed.

---

## 3. Page Maps

### `/docs/user-guide/sessions` (Sessions)
1. How Sessions Work — storage location, SQLite fields tracked, session sources table (21 platform/source tags)
2. What Counts Toward Context — media handling, context growth guidance
3. CLI Session Resume — `--continue`/`-c`, `--resume`/`-r`, resume-by-name, resume-by-directory (`--in`), cwd restore behavior, session ID format
4. Cross-Platform Handoff — `/handoff`, session id preserved across platforms, per-platform thread behavior, failure modes
5. Session Naming — auto-titling, `/title`, title rules, auto-lineage on compression
6. Session Management Commands — `list`, `export` (4 formats + prompts-only + trace), `delete`, `rename`, `prune`, `archive`, `stats`, `repair-routing`
7. Session Search Tool — `session_search` tool, 3 calling shapes (discovery/scroll/browse), FTS5 syntax, optional params
8. Per-Platform Session Tracking — gateway session key table, shared vs isolated group sessions, reset policies, crash/restart continuity guarantees
9. Storage Locations — table of on-disk paths, `sessions.json` legacy-mirror clarification, legacy JSONL note
10. Session Expiry and Cleanup — auto-prune config keys/defaults, manual cleanup commands

### `/docs/user-guide/checkpoints-and-rollback` (Checkpoints & Rollback)
1. (intro) — opt-in-as-of-v2 posture, enable flags
2. What Triggers a Checkpoint — tool/command triggers, once-per-directory-per-turn cap
3. Quick Reference — in-session `/rollback` variants table, CLI `hermes checkpoints` subcommand table
4. How Checkpoints Work — shadow-store mechanics summary
5. Configuration — full `checkpoints:` YAML block with defaults, auto-prune sub-block
6. Listing Checkpoints — `/rollback` sample output
7. Inspecting the Store from the Shell — `hermes checkpoints` sample output
8. Previewing Changes with `/rollback diff`
9. Restoring with `/rollback` — 4-step restore mechanics (verify → pre-rollback snapshot → restore files → undo last turn)
10. Single-File Restore
11. Safety and Performance Guards — 8 documented guards
12. Where Checkpoints Live — directory tree, per-project hashing note, Migration from v1 sub-section
13. Best Practices

### `/docs/developer-guide/session-storage` (Session Storage)
1. (intro) — SQLite replaces per-session JSONL; source file `hermes_state.py`
2. Architecture Overview — table list (9 tables) in `state.db`
3. SQLite Schema — Sessions Table (abridged CREATE TABLE + full-column callout), Messages Table (abridged + callout), FTS5 Full-Text Search (CREATE VIRTUAL TABLE + trigger note)
4. Schema Version and Migrations — version 23 current; full 1–23 migration table; declarative-vs-version-gated distinction
5. Write Contention Handling — retry/jitter/WAL-checkpoint constants
6. Common Operations — Initialize, Create/Manage Sessions, Store Messages, Retrieve Messages, Session Titles (all as Python snippets)
7. Full-Text Search — Basic Search, FTS5 syntax table, Filtered Search, Search Results Format, sanitizer behavior
8. Session Lineage — `parent_session_id` chains, ancestor/descendant recursive SQL queries
9. Export and Cleanup — Python API snippets
10. Database Location — path resolution via `get_hermes_home()` / `HERMES_HOME`

### `/docs/developer-guide/architecture` (Architecture)
1. System Overview — ASCII diagram: entry points → AIAgent → Session Storage / Tool Backends
2. Directory Structure — full source tree incl. `hermes_state.py`, `gateway/session.py`
3. Data Flow — CLI Session / Gateway Message / Cron Job sequences (session save/load points visible)
4. Recommended Reading Order — places Session Storage as item 7, Gateway Internals as item 8
5. Major Subsystems — "Session Persistence" one-paragraph summary
6. Design Principles table — includes "Profile isolation" (own sessions per profile)
7. File Dependency Chain

### `/docs/developer-guide/gateway-internals` (Gateway Internals)
1. Key Files — `gateway/session.py` = `SessionStore`
2. Architecture Overview — ASCII diagram showing `SessionStore` below `_handle_message()`
3. Message Flow — 6-step message handling incl. session-key resolution
4. Session Key Format — `agent:main:{platform}:{chat_type}:{chat_id}`, thread-aware note, `build_session_key()` warning
5. Two-Level Message Guard — session-active guard behavior
6. Authorization — 5-step precedence
7. Slash Command Dispatch
8. Config Sources
9. Platform Adapters
10. Delivery Path — cron deliveries NOT mirrored into session history (deliberate)
11. Hooks — Gateway Hook Events table (`session:start`, `session:end`, `session:reset`, etc.)
12. Memory Provider Integration — Memory Flush Lifecycle (4 steps on session reset/resume/expiry)
13. Background Maintenance — bullet list incl. "Session expiry" and "Memory flush"
14. Process Management

### `/docs/user-guide/profiles` (Profiles) — boundary/context page
Sections read: What are profiles?, How it works (`HERMES_HOME` scoping), Clone everything (`--clone-all` explicitly **excludes** session history/`state.db`/checkpoints).

### `/docs/user-guide/features/memory` (Persistent Memory) — boundary/context page
Sections read in full; session-relevant: "Session Search" section (cross-links Sessions page's `session_search` tool) and "session_search vs memory" comparison table.

### `/docs/user-guide/git-worktrees` (Git Worktrees) — boundary/context page
Sections read in full; session-relevant: checkpoint history is scoped **per worktree path hash**, not per session — an important disambiguation from session identity.

---

## 4. Reference Tables

### 4.1 On-disk paths / layouts

| Path | What | Default? | Source |
| --- | --- | --- | --- |
| `~/.hermes/state.db` | SQLite DB — all session metadata + full message history, WAL mode | Yes (`HERMES_HOME`-relative) | Sessions §Storage Locations; Session Storage §Database Location |
| `~/.hermes/state.db-wal`, `~/.hermes/state.db-shm` | WAL / shared-memory sidecars, same directory as `state.db` | — | Session Storage §Database Location |
| `gateway_routing` (table, inside `state.db`) | Canonical gateway routing index: session keys → active session IDs (origin metadata, expiry flags) | — | Sessions §Storage Locations |
| `~/.hermes/sessions/sessions.json` | **Legacy mirror** of `gateway_routing`, gateway/messaging entries only | Written by default (`gateway.write_sessions_json: true`) | Sessions §Storage Locations |
| `~/.hermes/sessions/saved/*.json` | `/save` snapshots — "convenience exports, not the index" | — | Sessions §Storage Locations |
| `~/.hermes/sessions/*.jsonl` | Legacy pre-state.db transcripts; "no longer written or read"; safe to delete after verifying session exists in `state.db` | — | Sessions §Storage Locations |
| `~/.hermes/session-exports/` | Default output dir for `--format md`/`qmd` bulk exports (one file per session + `manifest.jsonl`) | Default | Sessions §Export Sessions §Markdown/QMD |
| `~/.hermes/checkpoints/store/` | Single shared bare git repo — shadow store for all projects' checkpoints | Yes | Checkpoints §intro, §Where Checkpoints Live |
| `~/.hermes/checkpoints/store/refs/hermes/<hash>` | Per-project branch tip (`<hash>` derived from absolute workdir path) | — | Checkpoints §Where Checkpoints Live |
| `~/.hermes/checkpoints/store/indexes/<hash>` | Per-project git index | — | Checkpoints §Where Checkpoints Live |
| `~/.hermes/checkpoints/store/projects/<hash>.json` | Per-project metadata: workdir + `created_at` + `last_touch` | — | Checkpoints §Where Checkpoints Live |
| `~/.hermes/checkpoints/.last_prune` | Auto-prune idempotency marker | — | Checkpoints §Where Checkpoints Live |
| `~/.hermes/checkpoints/legacy-<ts>/` | Archived pre-v2 per-project shadow repos (moved here on first v2 run) | — | Checkpoints §Where Checkpoints Live, §Migration from v1 |
| `~/.hermes/kanban.db` | Kanban board SQLite (separate system) | — | kanban page (boundary; via grep) |

### 4.2 Session / checkpoint config keys

| Key | Type | Default | Description | Source |
| --- | --- | --- | --- | --- |
| `sessions.auto_prune` | bool | `false` | Opt-in auto-pruning of ended sessions inactive for `retention_days` at CLI/gateway startup | Sessions §Session Expiry and Cleanup |
| `sessions.retention_days` | int (days) | `90` | Age threshold (from latest message) for auto-prune eligibility | same |
| `sessions.vacuum_after_prune` | bool | `true` (per example block) | Reclaim disk space after a pruning sweep | same |
| `sessions.min_vacuum_interval_days` | int (days) | `30` | Minimum interval between `VACUUM` operations | same |
| `sessions.min_interval_hours` | int (hours) | `24` | Minimum interval between prune sweeps; last-run timestamp tracked in `state.db` itself, shared across processes in same `HERMES_HOME` | same |
| `group_sessions_per_user` | bool | `true` | Per-user session isolation in group chats/channels | Sessions §Shared vs Isolated Group Sessions |
| `thread_sessions_per_user` | bool | `false` (implied — "default" shared) | Per-user sessions inside a shared thread/topic (overrides default shared-thread behavior) | Sessions §Per-Platform Session Tracking table |
| `session_reset.mode` | enum | `none` | Gateway auto-reset policy: `none`/`idle`/`daily`/`both` | Sessions §Session Reset Policies |
| `display.resume_display` | enum | `full` | `full` (recap panel) vs `minimal` (one-liner) on resume | Sessions §Conversation Recap on Resume |
| `gateway.write_sessions_json` | bool | `true` | Whether to write the legacy `sessions.json` mirror | Sessions §Storage Locations (`sessions.json is not the session list` admonition) |
| `checkpoints.enabled` | bool | `false` | Master switch — checkpoints are opt-in | Checkpoints §Configuration |
| `checkpoints.max_snapshots` | int | `20` | Max checkpoints per project (enforced via ref rewrite + `git gc`) | same |
| `checkpoints.max_total_size_mb` | int (MB) | `500` | Hard cap on total store size; oldest commit per project dropped round-robin when exceeded | same |
| `checkpoints.max_file_size_mb` | int (MB) | `10` | Skip any single file larger than this | same |
| `checkpoints.auto_prune` | bool | `true` | Enables the startup sweep that deletes stale project entries | same |
| `checkpoints.retention_days` | int (days) | `7` | Age threshold (via `last_touch`) for the auto-prune sweep | same |
| `checkpoints.min_interval_hours` | int (hours) | `24` | Minimum interval between auto-prune sweeps (tracked via `.last_prune` marker) | same |
| `HERMES_CHECKPOINT_TIMEOUT` (env var) | int (seconds) | `30` | Timeout for filesystem checkpoint creation | environment-variables reference (grep) |

### 4.3 Session identifiers / formats

| Item | Format / Value | Source |
| --- | --- | --- |
| CLI/TUI session ID | `YYYYMMDD_HHMMSS_<6-char hex>` e.g. `20250305_091523_a1b2c3` | Sessions §CLI Session Resume tip |
| Gateway session ID | `YYYYMMDD_HHMMSS_<8-char hex>` e.g. `20250305_091523_a1b2c3d4` | same |
| `latest` | Reserved keyword for `--resume` (resolves to most recent session); a session literally titled "latest" is still reachable by ID or `-c latest` (title match) | Sessions §Resume Specific Session (note) |
| Gateway session key | `agent:main:{platform}:{chat_type}:{chat_id}` — e.g. `agent:main:telegram:private:123456789` | Gateway Internals §Session Key Format |
| Gateway session key (per-platform table variant, Sessions page) | e.g. `agent:main:telegram:dm:<chat_id>`, `agent:main::group:<chat_id>:<user_id>`, `agent:main::group:<chat_id>:<thread_id>`, `agent:main::channel:<chat_id>:<user_id>` | Sessions §Per-Platform Session Tracking table |
| `HERMES_SESSION_ID` (env var) | Exported automatically into every tool subprocess Hermes spawns (`terminal`, `execute_code`, persistent shell, Docker/Singularity backends, **delegated subagent runs**); set by the agent to the current session ID; "You should not set this manually" | environment-variables reference (grep) — undocumented whether/how this correlates to kanban `task_runs` rows (see Gaps §9) |
| `HERMES_KANBAN_TASK` (env var) | Task **UUID** (not a session id) set by the dispatcher when spawning a kanban worker | environment-variables reference (grep) |

### 4.4 CLI commands (session/checkpoint surface — grepped, not exhaustive)

| Command | Purpose | Source |
| --- | --- | --- |
| `hermes sessions list [--source] [--limit] [--workspace]` | List recent sessions, filterable | cli-commands (grep); Sessions page |
| `hermes sessions browse` | Interactive session picker with search and resume | cli-commands (grep) |
| `hermes sessions export [--format jsonl\|md\|qmd\|html\|trace] ...` | Export sessions; many filter flags | Sessions §Export Sessions (full); cli-commands (grep) |
| `hermes sessions delete <id> [--yes]` | Delete one session | Sessions §Delete a Session |
| `hermes sessions rename <id> "<title>"` | Set/change title | Sessions §Rename a Session |
| `hermes sessions prune [filters] [--dry-run] [--yes]` | Delete ended sessions matching filters; default 90-day cutoff only when bare | Sessions §Prune Old Sessions (full) |
| `hermes sessions archive [filters]` | Soft-hide sessions (requires ≥1 filter) | Sessions §Bulk-Archive Sessions |
| `hermes sessions stats` | Session-store statistics | Sessions §Session Statistics |
| `hermes sessions optimize` | Merge FTS5 segments + VACUUM (non-destructive) | Sessions §tip admonition; cli-commands (grep) |
| `hermes sessions optimize-storage` | Migrate FTS index to compact v23 external-content layout | cli-commands (grep) |
| `hermes sessions repair-routing [--apply] [--max-gap-seconds N]` | Repair stranded gateway sessions that lost routing identity | Sessions §Repair Stranded Gateway Sessions (full) |
| `hermes checkpoints` / `status` / `list` | Show store size, project count, per-project breakdown | Checkpoints §Quick Reference, §Inspecting the Store |
| `hermes checkpoints prune [--retention-days N] [--max-size-mb N]` | Force cleanup sweep, ignores 24h idempotency marker | Checkpoints §Quick Reference |
| `hermes checkpoints clear [-f]` | Delete entire checkpoint base (irreversible, confirms) | Checkpoints §Quick Reference; cli-commands (grep) |
| `hermes checkpoints clear-legacy [-f]` | Delete only v1-migration `legacy-*` archives | Checkpoints §Quick Reference |
| `hermes backup` | Zips Hermes home; explicitly excludes `*.db-wal/-shm/-journal` sidecars and per-session checkpoint trajectory caches | cli-commands (grep, §hermes backup) |
| `hermes logs [--session <substr>] [--level] [--since] [-f]` | Filter agent/gateway logs by session ID substring | cli-commands (grep, §hermes logs) |

### 4.5 Slash commands (session/checkpoint surface — grepped)

| Command | Description | Source |
| --- | --- | --- |
| `/new [name]` (alias `/reset`) | Start a new session (fresh ID + history); optional initial title | slash-commands (grep) |
| `/clear` | Clear screen and start a new session | same |
| `/save` | Save the current conversation | same |
| `/title [name]` | Set/show session title | same |
| `/resume [name]` | Resume a previously-named session | same |
| `/sessions [all] [search]` (TUI alias `/switch`) | Browse/resume sessions; `search <term>` filters; `all` is admin-only cross-origin listing | slash-commands (grep) |
| `/handoff <platform>` | CLI-only; hands session to a messaging platform, preserves `session_id` | slash-commands (grep); Sessions §Cross-Platform Handoff (full) |
| `/rollback [N]` | List or restore filesystem checkpoints | Checkpoints §Quick Reference (full) |
| `/rollback diff <N>` | Preview diff vs checkpoint N | same |
| `/rollback <N> <file>` | Restore a single file from checkpoint N | same |
| `/diff [staged\|all\|session] [--stat] [path...]` | `session` variant = cumulative diff since earliest retained checkpoint baseline (requires checkpoints enabled) | slash-commands (grep) |
| `/snapshot [create\|restore\|prune]` (alias `/snap`) | **Config/state** snapshots — distinct system from checkpoints/rollback | slash-commands (grep) — flagged boundary, see §8 |
| `/status` | Session info incl. model/provider/profile/session ID/cwd/title/timestamps + local recap block | slash-commands (grep) |
| `/pass-session-id` (CLI flag `--pass-session-id`) | Include session ID in the agent's own system prompt | cli-commands (grep) |
| `/heartbeat every <interval>` (alias `/hb`) | Session-scoped recurring re-entry; references "Session Heartbeats" page (URL not found in `llms.txt` — gap) | slash-commands (grep) |
| `/background <prompt>` (alias `/bg`, `/btw`) | Runs in a separate background session; references "CLI Background Sessions" page (URL not found in `llms.txt` — gap) | slash-commands (grep) |
| `/branch [name]` (alias `/fork`) | Branch the current session | slash-commands (grep) |

---

## 5. Normative Statements

| Exact quote | Page + section | Why it matters for stage 080 |
| --- | --- | --- |
| "Every conversation — whether from the CLI, Telegram, Discord, Slack, WhatsApp, Signal, Matrix, Teams, or any other messaging platform — is stored as a session with full message history." | Sessions § How Sessions Work | Confirms a single, uniform session model — worker CLI invocations spawned by the kanban dispatcher (`hermes -p <profile> ...`) are ordinary CLI sessions, not a distinct kind of record. |
| "1. SQLite database (`~/.hermes/state.db`) — structured session metadata with FTS5 full-text search, plus full message history" | Sessions § How Sessions Work | Single canonical store — any provenance design should read `state.db`, not `sessions.json`. |
| "`sessions.json` is not the session list ... The gateway routing index lives in the `gateway_routing` table inside `state.db`; `~/.hermes/sessions/sessions.json` is a legacy mirror of it ... It only ever contains gateway/messaging entries" | Sessions § Storage Locations (admonition) | Direct warning against using the JSON mirror for audit/provenance — it's incomplete by design (gateway-only) and legacy. |
| "Session IDs follow the format `YYYYMMDD_HHMMSS_<hex>` — CLI/TUI sessions use a 6-char hex suffix ... gateway sessions use an 8-char suffix ... You can resume by ID (full or unique prefix) or by title" | Sessions § CLI Session Resume (tip) | Exact identifier grammar — needed if a provenance chain parses or validates session IDs. |
| "Pruning only deletes ended sessions (sessions that have been explicitly ended or auto-reset). Active sessions are never pruned." | Sessions § Prune Old Sessions (info box) | Safety guarantee relevant to any automated retention policy stage 080 might configure. |
| "Because deleting a parent session also removes its delegate/subagent sessions, this mode exports and verifies each delegate in a separate file before deleting anything." | Sessions § Export Sessions § Markdown/QMD | Confirms delegate/subagent runs are themselves full session rows with parent/child relationships — directly relevant to any worker-session provenance model. |
| "Default is off — session history is valuable for `session_search` recall, and silently deleting it could surprise users." | Sessions § Session Expiry and Cleanup | `auto_prune` defaults false; a stage-080 harness that wants automatic session cleanup must opt in explicitly. |
| "Active sessions are never auto-pruned, regardless of age. Ended sessions are aged from their latest message" | Sessions § Session Expiry and Cleanup | Precise aging semantics. |
| "Checkpoints are opt-in as of v2 — most users never use `/rollback`, and the shadow-store storage is non-trivial over time, so the default is off." | Checkpoints § intro | `checkpoints.enabled` defaults false; any stage-080 safety-net design must explicitly enable checkpoints per-profile or per-session. |
| "This safety net is powered by an internal Checkpoint Manager that keeps a single shared shadow git repository under `~/.hermes/checkpoints/store/` — your real project `.git` is never touched." | Checkpoints § intro | Checkpoints never touch the real repo — safe to enable without git-history risk. |
| "The agent creates at most one checkpoint per directory per turn, so long-running sessions don't spam snapshots." | Checkpoints § What Triggers a Checkpoint | Rate-limiting behavior relevant to sizing/cost expectations for long autonomous worker runs. |
| "When `enabled: false`, the Checkpoint Manager is a no-op and never attempts git operations. When `auto_prune: false`, the store grows until you run `hermes checkpoints prune` manually." | Checkpoints § Configuration | Two independent switches — must both be considered when designing retention. |
| "Git availability — if `git` is not found on `PATH`, checkpoints are transparently disabled." / "Repository size — directories with more than 50,000 files are skipped." | Checkpoints § Safety and Performance Guards | Hard operational limits stage 080 should account for on large migration workspaces. |
| "Restoring with /rollback: 1. Verifies ... 2. Takes a pre-rollback snapshot of the current state so you can 'undo the undo' later. 3. Restores tracked files ... 4. Undoes the last conversation turn so the agent's context matches the restored filesystem state." | Checkpoints § Restoring with /rollback | Exact restore mechanics — filesystem and conversation state are rolled back together. |
| "Current schema version: 23" | Session Storage § Schema Version and Migrations | Concrete DB version fact, useful for any tooling that reads `state.db` directly and needs a compatibility floor. |
| "Multiple hermes processes (gateway + CLI sessions + worktree agents) share one `state.db`." | Session Storage § Write Contention Handling | Directly relevant: stage 080's multi-agent/kanban model means concurrent workers all write the same DB file; the documented retry/jitter/WAL strategy is the only concurrency guarantee. |
| "Batch runner and RL trajectories are NOT stored here (separate systems)" | Session Storage § Architecture Overview | Explicit scope boundary of `state.db` — batch/trajectory data has its own storage, not sessions. |
| "Session identity (routing key, chat, origin) is written atomically when the session row is created ... If that write ever fails, the very next turn's routing refresh repairs the row automatically." / "After a restart, the gateway re-resolves each chat to the session with the most recent actual activity" | Sessions § Continuity After Crashes and Restarts | Documented self-healing behavior for gateway session continuity — relevant to any HA/reliability claims about a hosted Hermes deployment. |
| "Cron job deliveries are NOT mirrored into gateway session history — they live in their own cron session only. This is a deliberate design choice to avoid message alternation violations." | Gateway Internals § Delivery Path | Explicit boundary: cron-triggered agent runs are isolated sessions, not appended to a chat's history. |
| "Hooks are discovered from `gateway/builtin_hooks/` (an extension point — currently empty in the shipped distribution; `_register_builtin_hooks()` is a no-op stub) and `~/.hermes/hooks/` (user-installed)." | Gateway Internals § Hooks | Session-lifecycle hooks (`session:start`/`session:end`/`session:reset`) are the mechanism `hermes-hooks` should own; this skill should only reference, not restate, the hook contract. |
| "Per-profile history is excluded (session history, `state.db`, `backups/`, `state-snapshots/`, `checkpoints/`) — these belong to the source profile and can reach tens of GB." | Profiles § Clone everything (--clone-all) | Confirms sessions and checkpoints are both profile-scoped runtime state, explicitly excluded even from a "clone everything" operation — reinforces the skill's existing "keep session/log locations out of Git" guidance. |
| "`HERMES_SESSION_ID` — Exported automatically into every tool subprocess Hermes spawns (`terminal`, `execute_code`, persistent shell, Docker/Singularity backends, delegated subagent runs). Set by the agent to the current session ID ... You should not set this manually" | Environment Variables reference | The only documented mechanism correlating a running agent (including a delegated/subagent run) to its own session ID from inside tool execution — the closest official primitive to a "worker_session_id," but it is scoped to tool subprocesses, not written into any completion-metadata record automatically (see Gaps §9). |

---

## 6. Official Examples (verbatim)

**Resume by name with lineage** (Sessions § Resume by Name):
```bash
# Resume a named session
hermes -c "my project"
# If there are lineage variants (my project, my project #2, my project #3),
# this automatically resumes the most recent one
hermes -c "my project"   # → resumes "my project #3"
```

**Session config — resume display** (Sessions § Conversation Recap on Resume):
```yaml
display:
  resume_display: minimal   # default: full
```

**Session config — group isolation** (Sessions § Shared vs Isolated Group Sessions):
```yaml
group_sessions_per_user: false
```

**Auto-prune config block** (Sessions § Session Expiry and Cleanup):
```yaml
sessions:
  auto_prune: true          # opt in — default is false
  retention_days: 90        # keep ended sessions active within this window
  vacuum_after_prune: true  # reclaim disk space after a pruning sweep
  min_vacuum_interval_days: 30 # don't rewrite the DB more often than this
  min_interval_hours: 24    # don't re-run the sweep more often than this
```

**Prune sample output invocation set** (Sessions § Prune Old Sessions):
```bash
hermes sessions prune --older-than 30
hermes sessions prune --newer-than 5h
hermes sessions prune --after "2026-07-05 09:00" --before "2026-07-05 14:30"
hermes sessions prune --source cron --older-than 60
hermes sessions prune --branch feature/old-experiment
hermes sessions prune --dry-run
```

**Checkpoints enable** (Checkpoints § intro):
```bash
hermes chat --checkpoints
```
```yaml
checkpoints:
  enabled: true
```

**Checkpoints full config block** (Checkpoints § Configuration):
```yaml
checkpoints:
  enabled: false              # master switch (default: false — opt-in)
  max_snapshots: 20           # max checkpoints per project (enforced via ref rewrite + gc)
  max_total_size_mb: 500      # hard cap on total store size; oldest commits dropped
  max_file_size_mb: 10        # skip any single file larger than this
  auto_prune: true
  retention_days: 7
  min_interval_hours: 24
```

**`/rollback` sample listing** (Checkpoints § Listing Checkpoints):
```text
📸 Checkpoints for /path/to/project:
  1. 4270a8c  2026-03-16 04:36  before patch  (1 file, +1/-0)
  2. eaf4c1f  2026-03-16 04:35  before write_file
  3. b3f9d2e  2026-03-16 04:34  before terminal: sed -i s/old/new/ config.py  (1 file, +1/-1)
  /rollback <N>             restore to checkpoint N
  /rollback diff <N>        preview changes since checkpoint N
  /rollback <N> <file>      restore a single file from checkpoint N
```

**`hermes checkpoints` sample store output** (Checkpoints § Inspecting the Store from the Shell):
```text
Checkpoint base: /home/you/.hermes/checkpoints
Total size:      142.3 MB
  store/         138.1 MB
  legacy-*       4.2 MB
Projects:        12
  WORKDIR                                                       COMMITS    LAST TOUCH  STATE
  /home/you/code/hermes-agent                                        20       2h ago  live
  /home/you/code/experiments/rl-runner                                8       1d ago  live
  /home/you/code/old-prototype                                        3       9d ago  orphan
```

**Where checkpoints live — directory tree** (Checkpoints § Where Checkpoints Live):
```text
~/.hermes/checkpoints/
  ├── store/                 # single shared bare git repo
  │   ├── HEAD, objects/     # git internals (shared across projects)
  │   ├── refs/hermes/<hash> # per-project branch tip
  │   ├── indexes/<hash>     # per-project git index
  │   ├── projects/<hash>.json  # workdir + created_at + last_touch
  │   └── info/exclude
  ├── .last_prune            # auto-prune idempotency marker
  └── legacy-<ts>/           # archived pre-v2 per-project shadow repos
```

**Sessions table CREATE TABLE (abridged)** and **Schema Version table** — both reproduced verbatim in §4 above via the Session Storage page; full SQL is long, see page directly for the complete statement (this dossier's §4.2/table already captures the load-bearing columns and the version-by-version migration table).

**Session key format** (Gateway Internals § Session Key Format):
```text
agent:main:{platform}:{chat_type}:{chat_id}
```
Example: `agent:main:telegram:private:123456789`

**Gateway session key table** (Sessions § Per-Platform Session Tracking):
| Chat Type | Default Key Format |
| --- | --- |
| Telegram DM | `agent:main:telegram:dm:<chat_id>` |
| Group thread/topic | `agent:main::group:<chat_id>:<thread_id>` |

**`session_search` calling shapes** (Sessions § Session Search Tool):
```python
session_search(query="auth refactor", limit=3)
session_search(session_id="20260510_174648_805cc2", around_message_id=590803, window=10)
session_search()
```

---

## 7. Recommendations Found (verbatim, docs-phrased "best practice"/"should")

- "Use `/compress` when a session gets long, `/new` for a fresh thread, and `hermes sessions prune` only when you want to delete old ended sessions from storage. If `state.db` has simply grown large, start with the non-destructive option first: `hermes sessions optimize` merges FTS5 index segments and VACUUMs the database without touching any session data." — Sessions § What Counts Toward Context (tip)
- "Prefer summaries, file paths, focused excerpts, and tool-backed lookups over copying large artifacts into chat." — Sessions § What Counts Toward Context
- "Back up first (`cp ~/.hermes/state.db ~/.hermes/state.db.bak`)." — Sessions § Repair Stranded Gateway Sessions
- "Use `/rollback diff` before restoring — preview what will change to pick the right checkpoint." — Checkpoints § Best Practices
- "Use `/rollback` instead of `git reset` when you want to undo agent-driven changes only." — Checkpoints § Best Practices
- "Check `hermes checkpoints status` occasionally if you use checkpoints regularly — shows which projects are active and what the store costs you." — Checkpoints § Best Practices
- "Combine with Git worktrees for maximum safety — keep each Hermes session in its own worktree/branch, with checkpoints as an extra layer." — Checkpoints § Best Practices
- "Enable checkpoints only when you need them — `hermes chat --checkpoints` or per-profile `enabled: true`." — Checkpoints § Best Practices
- "The database grows slowly (typical: 10-15 MB for hundreds of sessions) ... so auto-prune ships disabled. Enable it if you're running a heavy gateway/cron workload where `state.db` is meaningfully affecting performance (observed failure mode: 384 MB state.db with ~1000 sessions slowing down FTS5 inserts and `/resume` listing)." — Sessions § Session Expiry and Cleanup (tip) — directly actionable for a stage-080 harness expected to run many worker sessions.
- "One worktree per Hermes experiment ... Name branches after the experiment ... Commit frequently ... Avoid running Hermes from the bare repo root when using worktrees" — Git Worktrees § Best Practices

---

## 8. Boundary Notes (belongs to a sibling `hermes-*` skill)

- **`hermes-configuration`** — Compression/compaction trigger config and behavior beyond the session-lineage effect (`/compress`, auto-lineage titling on split); full `config.yaml` key precedence and profile/`HERMES_HOME` mechanics (this dossier only captured the session/checkpoint-relevant slice of Profiles).
- **`hermes-kanban`** — `task_runs`/`task_events` durability model is confirmed as a **separate** system from chat sessions (own SQLite DB `~/.hermes/kanban.db`, own append-only event log). Documented worker-spawn mechanism: dispatcher sets `HERMES_KANBAN_TASK` (task UUID) in the worker's env; no session-id field is set or required by kanban's own env-var contract. `kanban_complete(summary=..., metadata={...})` metadata is free-form JSON with no documented session-id key. **This is the seam flagged in the assignment** — see Gaps §9 for the full finding.
- **`hermes-hooks`** — Gateway Hook Events table (`gateway:startup`, `session:start`, `session:end`, `session:reset`, `agent:start`, `agent:step`, `agent:end`, `command:*`) lives on the Gateway Internals page but is squarely `hermes-hooks` territory; this dossier only cites it for boundary purposes (§5).
- **`hermes-managed-scope`** — Admin pins were not encountered on any session/checkpoint page in this run; no boundary content found to report.
- **`hermes-cli`** — The full `hermes sessions` and `hermes checkpoints` CLI subcommand trees live authoritatively on `/docs/reference/cli-commands`; this dossier's §4.4 is a grep-derived subset, not the canonical CLI reference. `hermes-cli` should do its own full read of that page rather than relying on this table.
- **Not a sibling skill, but a config-naming trap worth flagging to the SKILL.md author:** `/snapshot` (alias `/snap`) creates **config/state snapshots** ("Hermes config/state") — a different, smaller feature from Checkpoints/`/rollback` (filesystem safety net). Docs text for `/snapshot` is thin (one grepped line); the skill should be careful not to conflate the two "snapshot" concepts when writing about checkpoints.
- **Delegation (`delegate_task`)** — Each subagent "gets its own terminal session (separate from the parent)" and delegate/subagent chat sessions are real rows in `state.db` (confirmed independently by the Sessions page's export-deletion cascade language: "deleting a parent session also removes its delegate/subagent sessions"). Full delegation lifecycle/steering/stall-detection semantics belong to whatever skill owns `delegate_task` (not explicitly named in this run's sibling list — flag for the maintainer to confirm ownership, likely a `hermes-delegation` skill if one exists, otherwise a gap in skill coverage).

---

## 9. Gaps & Open Questions

1. **`worker_session_id` in kanban completion metadata is not documented.** The assignment's tailoring note states stage 080 provenance "depends on" this field appearing in kanban completion metadata. Across the full Kanban page (grepped for `session_id`, `worker_session`, `task_runs`, `task_events`, `metadata`, `completion`) and the Delegation page, no official text documents kanban writing, requiring, or reserving a session-id field in `task_runs`/`task_events`/`kanban_complete` metadata. What IS documented:
   - `kanban_complete(summary=..., metadata={...}, result=...)` — `metadata` is described as "free-form JSON dict on the run"; the model chooses its own keys entirely.
   - The dispatcher spawns each worker as a fresh CLI-style process (`hermes -p <profile> ...`, confirmed indirectly by Profiles § Command aliases and Kanban's "dispatcher injects the profile-scoped `HERMES_HOME` when it spawns `hermes -p <profile>`" — captured via grep), which per the Sessions page will create/use an ordinary CLI session with its own `state.db` row and session ID.
   - `HERMES_SESSION_ID` is exported into "delegated subagent runs" per the environment-variables reference, but this is documented for `delegate_task` children, not explicitly for kanban dispatcher-spawned workers, and nothing in the docs says this value is captured into `task_runs`/`task_events`.
   - **Conclusion for the reviewer:** if stage 080 wants a `worker_session_id` in kanban completion metadata, this is either (a) an undocumented implementation detail the reviewer should verify against the actual `hermes-agent` source repository (`kanban_db` / `dispatcher` code — the docs point at `plugins/kanban/` and `kanban_db` but this run did not fetch source), or (b) something stage 080's own harness must explicitly implement (e.g., a worker-side skill/hook that calls `kanban_complete(metadata={"session_id": ...})` using its own `HERMES_SESSION_ID`). This is NOT something the current skill can state as documented product behavior.
2. **"CLI Background Sessions" and "Session Heartbeats" pages** — referenced by name from `/background` and `/heartbeat` slash-command descriptions, but no matching URL was found in `/docs/llms.txt`'s 135-line index. They may be anchors within another page (e.g., the CLI page or a Features page not fully enumerated) rather than standalone docs. Not guessed; flagged for the reviewer to locate directly (try site search or the CLI page in full).
3. **No documented interaction between `sessions.retention_days` (session auto-prune) and `checkpoints.retention_days` (checkpoint auto-prune)** — they are separate config namespaces with separate defaults (90 days vs 7 days) and no cross-reference in either page confirming/denying whether pruning a session also prunes its checkpoints, or vice versa. Worth an explicit question if stage 080 relies on both retention windows lining up.
4. **Exact source-repository path for kanban's dispatcher/session-spawn code** was cited by the docs only as `kanban_db` / `plugins/kanban/dashboard/plugin_api.py`, never as a specific worker-spawn function name; the docs did not link a specific file for "how the dispatcher constructs the `hermes -p <profile>` invocation," so Gap #1 cannot be closed by a further docs-site read — it would require reading the `NousResearch/hermes-agent` repository directly (permitted only for facts left undocumented by the docs site; the docs site itself does not link this specific file, so a repository read here would count as `source: repository, not docs` per the assignment's source hierarchy, and was out of scope for this docs-only capture run).
5. **No explicit "last-updated" or semantic version marker rendered on any of the 8 fully-read pages** — the only version signals found are the SQLite `schema_version` (23) and the checkpoints v1→v2 migration note. If the skill needs a product version string for its frontmatter, none was available from the docs site itself.

---

## 10. Suggested SKILL.md Inputs (for the reviewer — not an edit)

**Key concepts to state:**
- Sessions are uniformly stored in one SQLite database (`~/.hermes/state.db`), regardless of origin (CLI, gateway, cron, delegate/subagent, batch) — cites §5 row 1–2.
- `sessions.json` is a legacy, gateway-only mirror, not the canonical session list — cites §5 row 3 (use this to correct any assumption that `sessions.json` is inspectable for provenance).
- Session IDs have a documented, parseable grammar (`YYYYMMDD_HHMMSS_<hex>`, 6-hex for CLI/TUI vs 8-hex for gateway) — cites §4.3.
- Checkpoints are an opt-in, separate safety-net system (shadow git store, never touches the real repo) — cites §5 rows 9–10, distinct from chat sessions entirely; do not conflate checkpoint identity with session identity (a checkpoint's identity key is the workdir path hash, not a session ID — cites Git Worktrees page finding in §3).
- Delegate/subagent runs are real session rows with parent/child relationships in `state.db` — cites §5 row 6, useful for stage 080 audit trails that need to trace a worker back through a delegation chain.

**Workflow steps to propose:**
1. Before relying on session storage/checkpoint behavior, read `references/source-capture.md` and open the pinned Sessions / Checkpoints / Session Storage / Gateway Internals pages — cites §2 pin recommendations.
2. When designing a stage 080 provenance/audit trail keyed on a Hermes session id, verify the exact field name and population mechanism directly against the `hermes-agent` source (kanban dispatcher / `kanban_db`) rather than assuming a documented `worker_session_id` — cites Gap §9.1 (this is the single most important correction this dossier can hand to the reviewer, since the assignment's own framing assumed the field was documented).
3. If enabling checkpoints for autonomous/unattended workers, set `checkpoints.enabled: true` explicitly (default off) and size `max_total_size_mb`/`retention_days` for expected worker volume — cites §4.2 and §7 best-practices.
4. If configuring session cleanup for a high-volume harness, opt into `sessions.auto_prune` explicitly and expect the documented observed-failure-mode threshold (~384 MB / ~1000 sessions) as a rough sizing signal — cites §7.

**Validation commands to propose:**
- `hermes sessions list --workspace <path>` — confirm sessions are being recorded for a given stage 080 worker's workspace — cites §4.4.
- `hermes sessions stats` — confirm `state.db` size stays within expected bounds for the harness's session volume — cites §4.4, §7.
- `hermes checkpoints status` — confirm checkpoint store growth is bounded when checkpoints are enabled for workers — cites §4.4, §7.
- `hermes sessions export --format jsonl --session-id <id> --redact` — recommended pattern for extracting a worker's session as evidence in a PR/audit trail without leaking secrets — cites §4.4 Export Sessions.

---

## Reviewer addendum (2026-08-12): the worker-session provenance question, resolved

The dossier correctly found that `worker_session_id` in kanban completion
metadata is NOT documented anywhere — correcting the assignment's own
framing, which had assumed it was official behavior. The reviewer closed
the remaining question against the shipped source
(`source: repository, not docs`; main branch, 2026-08-12):

- `hermes_cli/kanban_db.py`: every `INSERT INTO task_runs` shape carries
  task_id/profile/status/claim/heartbeat/timing columns — **no session-id
  column exists on task_runs**.
- `tasks.session_id` DOES exist (TEXT, `idx_tasks_session_id`, added by a
  schema migration): it is a `create_task(...)` parameter recording the
  session a task was CREATED from, surfaced in `_task_to_dict` and
  filterable via `hermes kanban list --session <id>`. It is the
  origin/creator session, not the worker's.
- `kanban_db.py` contains `retag_kanban_worker_sessions` /
  `_retag_legacy_worker_sessions(workspaces_root)`: worker sessions are
  ordinary `state.db` sessions that kanban retags with a worker source
  label keyed on the kanban workspaces root — identifiable, but never
  written into kanban's own tables.

**Verdict:** stage 080's `worker_session_id` completion-metadata field (the
scaffold's AD-H §19 provenance rule) is a project convention implemented by
the worker writing its own session id into `kanban_complete(metadata=...)`.
The official sourcing primitive is `HERMES_SESSION_ID` (documented for tool
subprocesses and delegated runs; its presence in kanban-spawned workers
specifically is undocumented — verify on a live seat). The skill states
this distinction explicitly so no stage 080 doc ever cites the field as
official product behavior.

### Operational note

The research run's first three WebFetch attempts stalled (~11 min) before
succeeding — transient tooling, site confirmed reachable via curl
throughout; no dead links encountered afterward.
