# M3 implementer standing procedure (F6)

**Status:** binding proving-min
**Authority:** Lead F6 E-20260814T115900Z (card ≤1,500 chars; procedure lives here)
**Consumed by:** M3 Kanban card body (pointer only) from the holder mint Procedure (`mint-m3-hermes.md`)

The Kanban card carries identity + typed-body path + digest. **This file** carries
standing procedure that used to be pasted into every card (~9.5KB × N).

## Wrong-card gate (always first — one tool, then stop)

This standing file is for a **minted story child** whose card prints a typed
body path `evidence/bodies/m3-<story_id>.json`.

If that file is missing, or the title is a phase stub (`M3 IMPLEMENT:
bounded transform`, `M3 WAVE HOLDER`), or the title does not start with
`M3 IMPLEMENT: <story_id>` (story_id from the typed-body filename; the
retired `{story_id}:` title prefix is not identity — `111244Z`):

1. You are **not** the implementer. Do not inventory legacy. Do not write
   `src/` or `pom.xml`. Do not replan the whole migration.
2. Holder titles: path-invoke `.hermes/skills/harness/dispatch-phase/references/mint-m3-hermes.md`. Any other miss: `kanban
   block --kind needs_input` this card. Stop.
3. Do not invent `files_in_scope` from `tasks.md`.

## Turn law

Reasoning is at most **eight lines** and must end in **one** next action
(read the typed body, or one dest write from `files_writable`, or a typed
block). Forbidden cadence: "that's a lot, let me batch" → "more efficient"
→ "find exact paths" → `search_files` loops. One story, write-set only.

## Before first destination edit

1. Read the typed body JSON path on the card (`exit_criteria`,
   `files_writable` / `files_in_scope`, `dependencies`, `refs`).
2. Verify body sha256 matches the card digest:
   `python3 .hermes/skills/harness/record-run-evidence/scripts/check-body-digest-match.py . --body <body> --expect <digest>`
   — mismatch ⇒ REFUSE (`.hermes/skills/sdd/check-spec-readiness/references/body-integrity.md`).
3. **Do not rewrite the typed body** after dispatch (Architect E-111424Z).
4. Init/load `evidence/runs/<task_id>/checkpoint.json` via
   `init-implementer-checkpoint.py` / `check-implementer-checkpoint.py`.
5. Hard-invoke `spring-to-quarkus-patterns` (`skill_view`) before first dest
   edit; open needed `references/*`. Progressive disclosure — no bulk-paste.
   REST tests: RestAssured `given()` from the golden controller fixture.
   Do **not** use `java.net.http.HttpClient` or `URI.resolve`.

### Dest-inventory hard-invoke (BANK-DEST-INV-HARDINVOKE-1)

Any conclusion that a dependency/path is missing/absent/DEST_MISS/`empty
destination` is **INVALID** unless Reasoning cites `refs.destination_inventory`
(path+sha256) or the stamped receipt under
`evidence/receipts/destination-inventory/`. Typed `dependency_wait` **REQUIRES**
that citation first. Do **not** invent OOS owners or OOS-create "missing" deps.

### Dependencies / interface-closure

Treat `dependencies[]` as authority for import provenance. Coverage-gap on
orphan model/interface ⇒ typed BLOCK. Create path refuses `*Impl` without its
interface in scope/deps/dest (`check-interface-closure.py`). Mid-run OOS-create
of a missing interface = ABORT — typed `needs_input` only.

**No legal move:** if `exit_criteria` cannot pass because `dependencies[]`
name providers that are **descendants or siblings** of this card (this slice
runs before those types exist), do **not** restated the same decision, stub
types, or wait. `kanban_block --kind needs_input` with that reason, then
stop. A cyclic partition is a mint defect, not an implementer puzzle.

## Maven longer than 60s

Hermes terminal default is 60s. Cold `mvn` routinely exceeds that. Do **not**
invent a config key. If dest `hermes config` names an official terminal
command timeout, use it. Otherwise run Maven **detached** in-workspace and
poll with later calls each under 60s:

```bash
mkdir -p evidence/runs/${HERMES_KANBAN_TASK}
nohup mvn -q dependency:resolve > evidence/runs/${HERMES_KANBAN_TASK}/mvn.log 2>&1 & echo $! > evidence/runs/${HERMES_KANBAN_TASK}/mvn.pid
# later: kill -0 "$(cat evidence/runs/${HERMES_KANBAN_TASK}/mvn.pid)" ; tail log ; wait for exit
```

Do not wrap Maven in a custom timeout binary. Do not split one resolve into
fake 60s chunks.

### Pre-v12 R5 hard-invoke traps

When story touches REST/DTO/MapStruct — `skill_view` `references/di-config.md`.
Do **not** mandate MapStruct `componentModel = "cdi"` (B-3; doctrine pending
R-SKILL-F). When story touches
`@IfBuildProfile` / profile-gated beans — forbid that API; use `%profile`
config. When story touches QuarkusTest / continuous testing props —
`skill_view` `references/testing.md` continuous-testing enum. Cite the ref path
in Reasoning before first related dest write.

## During the story

- Write only `files_writable` / destination write-set (AR-4.4). The
  `write-set-hook.py` pre_tool_call fence allow-lists that set from
  spawn env `HERMES_KANBAN_FILES_WRITABLE` when published, else the card
  `files_writable` / `## Files Writable` list (CARD env or `kanban.db`
  body via `HERMES_KANBAN_TASK`), else phase yaml, else
  deny-all (BIND `25a7c1e9`). Dest
  `evidence/runtime/write-sets/*.json` is cache, not policy. Native id is
  `HERMES_KANBAN_TASK` — complete-path scripts default `--task-id` from
  that env. Do not scan the typed body for the card id and do not mint a
  `{TASK_ID}` placeholder.
  An out-of-set `pom.xml` is refused. Worktree `HERMES_WRITE_SAFE_ROOT`
  keeps dest-relative paths dest-relative.
- After each successful dest write: `stamp-implementer-checkpoint.py --completed <path>`.
- Do NOT bulk-read all files_in_scope in one turn — migrate file-by-file.
- Record pre/post write-set digests under `evidence/runs/` (`rhoai3.run-journal/v1`).
- **DD3 declare/apply/own:** every story stamps `identity.extensions_declared`
  (Quarkus extension artifactIds; empty = none). The sole `pom.xml` writer
  also declares M1 `evidence/required-extensions.json` (T-3 native rewrite)
  and applies `identity.extensions_apply` (sorted unique union of all
  stories, including that set). Later stories do not write `pom.xml`. Do
  not pre-provision a fixed hibernate/validator/flyway/jdbc menu on
  foundation — the required set is M1 emission, not a canned list.
  R-M3.5/7 persistence BOM handoff is **retired**.
- On typed `dependency_wait`: stamp/hold via `apply-dependency-wait-hold.py`;
  escalate `Needs: Lead:fix-upstream-pom`. Do not soft-promote or OOS-edit pom.
- Security stories: hard `skill_view` `security-config.md` +
  `security-anti-essay.md`; write-first; empty javadoc shells FAIL
  (`check-empty-security.py`).
- JDBC stories: `check-jdbc-deps-preflight.py` before first
  `repository/jdbc/**` edit; write-first mechanical transforms.
- AD-002E/F/G: each preloaded skill → `skill_view` **or** typed
  `skills_unused:<skill>:<reason>` before complete.
- Pre-flight ceiling: refuse emit when
  `prompt_tokens + max_tokens > max-model-len` via `check-preflight-ceiling.py`.

## Wall / crash / reclaim

- On `timed_out`: `apply-wall-requeue-policy.py` (soft K=1 then hard-block).
- On `crashed`: `apply-crash-requeue-policy.py` (K_crash=1).
- Soft reclaim (FIS≥20): resume from checkpoint `next` only.
- After `src/test/**` writes and on every wall:
  `sync-checkpoint-from-test-writes.py`.
- In-loop testCompile: `stamp-implementer-checkpoint.py --completed src/test/**`
  REFUSEs unless scoped `run-scoped-compile-gate.py --goal test-compile` is green
  for own `files_writable`.

## Before `kanban_complete`

1. Satisfy every `exit_criteria` item (endpoint/semantic exits required — AR-4.4).
2. Run:
   `python3 .hermes/skills/gates/check-release-readiness/scripts/assert-complete-exit-criteria.py . --body <body>`
   — card id from `HERMES_KANBAN_TASK` (native spawn). Do not pass a guessed
   story slug and do not mint `{TASK_ID}` / `{id}` placeholders.
   rc≠0 ⇒ REFUSE complete. Do not invent N/A.
3. That script also harness-invokes body-digest + ground-in-harvest citation +
   provenance — do not rely on skill_view alone.

## Constraints (always)

- workspace: `dir:/projects/modernized`
- Do not re-plan scope. Typed BLOCK if inputs wrong.
- No MiniMax (AD-008). AD-009 max-runtime from phase-dispatch / body budget.
- Skills preload ≠ consultation (AD-002D/E).
