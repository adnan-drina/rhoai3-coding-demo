# V6 notes — outer-loop logging & gate UX

**Source:** live `coolstore-cart-service-v6` run (2026-07-29), watching
`/tmp/outer-loop.log` as a demo user / observer.  
**Scope:** enhance `.hermes/harness/outer-loop.sh` (and light touch on
`analyze.sh` / session wrappers) so progress is **descriptive and
demo-safe**. Logic fixes that make gates clearer are included where they
are inseparable from good logging.  
**Status:** implemented in scaffold `outer-loop.sh` (2026-07-29 V6 abort
pass) — START/END markers, Actor labels, sparse heartbeats, analyze side-log,
session≠gate wording. **Task progress** (T-001 + title) mirrored from
`supervisor.sh` into `/tmp/outer-loop.log` (2026-07-29 follow-up). Remaining
polish (PLAIN ascii mode, richer deliverable enumeration, actual MiniMax vs
Qwen actor on each TASK line) can land on the next pass if demos need it.

### Task progress (required)

Demo users watching `tail -f /tmp/outer-loop.log` must see **which tasks**
are in flight, not only story-level M4/M5. Every task line includes:

- **code** — `T-001`, `T-002`, …
- **description** — the heading title from `tasks.md` (what the task entails)
- **class** — `rewrite` / `infer` when known
- **lifecycle** — `▶ TASK` start, `✓ TASK` end, `· TASK` skip/already-complete,
  `▶ TASKS` for rewrite batches (list each id + title in the detail)

Supervisor remains the source of truth for execution; it **mirrors** these
lines into `OUTER_LOG` (`/tmp/outer-loop.log`) so one `tail -f` covers the
demo narrative.

---

## 1. What’s wrong today (observed)

Demo users are told to `tail -f /tmp/outer-loop.log`. That file currently
behaves like an engineer debug stream, not a process narrative.

### 1.1 Opaque session lines

```text
[2026-07-29 16:44:38] session m2-sequence-a1: 1051s rc=0
LINT:stories: S02: findings field contains non-rule-id token 'depends:' ...
[2026-07-29 16:44:39] M2: roadmap lint red — bouncing once with the findings
```

Problems:

| Symptom | Why it confuses |
|--------|------------------|
| `rc=0` then immediate lint failure | Session exit ≠ gate success. Looks like a contradiction. |
| Raw `LINT:` lines with no frame | No “what failed / what happens next / attempt N of 2”. |
| “bouncing once with the findings” | Doesn’t say *which* findings, where they live, or that a2 is starting. |
| 17+ minutes of silence during M2 | No heartbeat while Hermes runs — looks hung. |
| No pointer to `/tmp/outer-m2-sequence-a1.log` | Full orchestrator transcript is invisible from the main log. |
| `analyze.sh` / kantra ANSI spam | M1 floods the same file; narrative lines are hard to find. |
| No model / token / wait context | V6 lost ~5+ min to MiniMax 429s; outer-loop never mentioned it. |
| Success lines omit commit SHA | Can’t correlate log ↔ `git log` without extra commands. |

### 1.2 Logic gaps that worsen the UX

- **Empty `- findings:`** on a story makes the roadmap lint parser eat the
  next fields (`depends:`, `S01`) and emit cryptic “non-rule-id token”
  errors. A preflight “roadmap shape” check would fail with a clear
  message (“S02 findings list is empty”) before the bounce prompt.
- Gate helpers (`roadmap_green`, rubric, plan-lint) append tool stdout
  straight into `$LOG` with no wrapper; success and failure look the same
  shape.
- `mchat` only logs duration + `rc`; it never logs “started”, model,
  attempt, or “still running”.
- Dual sinks (`outer-loop.log` vs `outer-loop-nohup.log`) — README points
  at one; `nohup` redirect of the script’s own stdout/stderr is mostly
  empty because almost everything goes through `log()`.

---

## 2. Design goals (demo user)

1. **Codes + plain language** — never log bare `M1` / `M2` / `M3` alone.
   Always pair the stage code with a short human title, e.g.
   `M2 SEQUENCE — cut the migration into dependency-ordered stories`.
   A demo user following the log should understand *what* is happening
   behind the scenes without memorizing the M-process glossary.
2. **Start and end every phase** — each phase emits a clear START and a
   clear END. The END line names **concrete deliverables** produced
   (or why none were accepted), not just `rc=0`.
3. **Milestone narrative, not chatty debug** — prefer a few high-signal
   lines the presenter can read aloud. Do **not** dump tool traces,
   full lint files, model prompts, or per-token noise into the main log.
   Detail belongs in side files; the main log only *points* to them.
4. **Name the model doing the work** — every START (and sparse heartbeat)
   that involves an LLM must say **which seat / which model** is active,
   in demo language. Codes alone (`maas-m2`) are not enough; prefer
   `orchestrator MiniMax M2` / `worker Qwen3.6 27B`. If the supervisor
   *advertises* a worker but Hermes escalates and edits without OpenCode,
   the log must say so (configured worker vs actually executing model) —
   V6 S01 rewrite batches ran entirely on MiniMax while Qwen stayed idle.
5. **Session ≠ gate** — always state both when an authoring session runs.
6. **Sparse heartbeats** — during long Hermes waits, one line per ~60s
   (`still working on <model>…`) is enough so the run doesn’t look hung;
   not a progress bar of internal tool calls.
7. **Actionable red** — bounce/fail: what failed, top findings (≤5),
   attempt N/2, path to full lint — then continue or stop.
8. **Optional depth** — token/latency totals as one line after a session
   (or `OUTER_LOOP_VERBOSE=1`), never on every heartbeat. **Which model**
   is not optional; counts are.

**Anti-goals for tone:** no play-by-play of every file write, no
repeating the full Hermes prompt, no kantra rule-by-rule spam, no
stack traces unless the outer loop itself crashes.

---

## 3. Proposed log format

### 3.1 Phase dictionary (code + description)

Use these titles consistently in START/END lines (tweak wording freely;
keep the code stable for grepping):

| Code | Description (log title) | What “done” names on END |
|------|-------------------------|---------------------------|
| **M1 ANALYZE** | Establish migration ground truth (MTA + recipes) | e.g. `24 findings, 47 incidents; recipe javax-to-jakarta staged; commit d003f54` |
| **M1 PROFILE** | Write the architecture profile (class roles & target contract) | e.g. `architecture-profile.md rubric-green; commit a2398ae` |
| **M2 SEQUENCE** | Cut the migration into dependency-ordered stories | e.g. `roadmap.md + 4 briefs (S01…S04); lint-green; commit …` — and list each brief: `S01-BOM-and-domain-models.md generated` |
| **M3 SPECIFY** | Plan one story (spec / plan / tasks) | e.g. `specs/S01-…/{spec,plan,tasks}.md plan-lint-green; commit …` |
| **M4/M5 EXECUTE** | Implement and ship one story (supervisor) | e.g. `S01 complete — supervisor success; factory …` / or fail reason |
| **BRIEF REFRESH** | Apply retro brief updates to remaining stories | e.g. `updated S03, S04 briefs` or `nothing to apply` |

Story lines always include **id + slug**, not bare `S01`:

```text
S01-BOM-and-domain-models (story 1/4)
```

### 3.2 Helpers

```bash
# Conceptual API — names illustrative
phase_start "M2" "SEQUENCE" "Cut the migration into dependency-ordered stories" "attempt 1/2"
phase_heartbeat "M2"           # sparse; every ~60s only
phase_session_end "M2" duration_s=1051 hermes_rc=0
phase_deliverables …           # END: concrete artifacts
phase_gate "M2" "roadmap-lint" RED|GREEN
fail_run_rich …
```

### 3.3 Example — happy path (main log only)

Sparse enough to read live; dense enough to teach the process:

```text
[ts] ▶ START  Outer loop — autonomous migration
[ts]          Models: orchestrator MiniMax M2 · coding worker Qwen3.6 27B (via OpenCode)
[ts]          Progress log: /tmp/outer-loop.log · resume state: migration/story-state.csv

[ts] ▶ START  M1 ANALYZE — establish migration ground truth (MTA + recipes)
[ts]          Actor: harness scripts (no LLM)
[ts] ✓ END    M1 ANALYZE — ground truth ready (24 findings, 47 incidents;
[ts]          jakarta recipe staged → migration/staging/; commit d003f54)

[ts] ▶ START  M1 PROFILE — architecture profile (class roles & target contract) [attempt 1/2]
[ts]          Actor: orchestrator MiniMax M2 (Hermes)
[ts] …        M1 PROFILE still working on MiniMax M2 (120s) — details /tmp/outer-m1-profile-a1.log
[ts] ✓ END    M1 PROFILE — architecture-profile.md rubric-green; commit a2398ae

[ts] ▶ START  M2 SEQUENCE — cut migration into dependency-ordered stories [attempt 1/2]
[ts]          Actor: orchestrator MiniMax M2 (Hermes)
[ts] …        M2 SEQUENCE still working on MiniMax M2 (300s) — details /tmp/outer-m2-sequence-a1.log
[ts] ✓ END    M2 SEQUENCE — roadmap + stories lint-green; commit b1c2d3e
[ts]          • S01-BOM-and-domain-models brief generated
[ts]          • S02-Service-interfaces-and-external-integration brief generated
[ts]          • S03-Core-pricing-services brief generated
[ts]          • S04-JAX-RS-endpoint-modernization brief generated (deploy story)

[ts] ▶ START  Story loop — 4 stories (S01 → S04)

[ts] ▶ START  M3 SPECIFY — plan story S01-BOM-and-domain-models (1/4) [attempt 1/2]
[ts]          Actor: orchestrator MiniMax M2 (Hermes)
[ts] ✓ END    M3 SPECIFY — S01 spec/plan/tasks written; plan-lint-green; commit …

[ts] ▶ START  M4/M5 EXECUTE — implement & ship S01-BOM-and-domain-models (1/4)
[ts]          Models: orchestrator MiniMax M2 · worker Qwen3.6 27B (OpenCode)
[ts]          Supervisor log: /tmp/supervisor.log
[ts] …        M4 batch T-001–T-003 — actor: MiniMax M2 (Hermes rewrite; Qwen not invoked)
[ts] …        M4 batch T-016 — actor: worker Qwen3.6 27B (OpenCode)
[ts] ✓ END    M4/M5 EXECUTE — S01 story complete (supervisor success)

[ts] …        (S02–S04 likewise)

[ts] ✓ END    Outer loop — all stories shipped; HEAD <sha>
```

**Rule:** `Actor:` is required whenever work is in flight. Log the
**actually executing** model when it differs from the configured worker
(escalation / rewrite-in-Hermes). Configured seats are stated at
outer-loop START and again at M4/M5 START.

### 3.4 Example — bounce (still sparse)

```text
[ts] ▶ START  M2 SEQUENCE — cut migration into dependency-ordered stories [attempt 1/2]
[ts]          Actor: orchestrator MiniMax M2 (Hermes)
[ts] …        M2 SEQUENCE still working on MiniMax M2 (600s) — details /tmp/outer-m2-sequence-a1.log
[ts] ·        M2 SEQUENCE session finished (1051s, hermes_rc=0) — checking roadmap gate…
[ts] ✗ GATE   M2 SEQUENCE — roadmap-lint RED [attempt 1/2]
[ts]          • S02: findings list empty (parser misread depends:/S01 as rule ids)
[ts]          • S03: must not own recipe-executed javax-to-jakarta-import-00001
[ts]          Full findings: /tmp/roadmap-lint.txt
[ts] ↻ RETRY  M2 SEQUENCE — bouncing once; starting attempt 2/2
```

Note: session finished and gate RED are **two lines** — never collapse them
into one ambiguous `rc=0` success.

(ASCII markers `▶ … ✓ ✗ ↻ ·` are fine; keep `OUTER_LOOP_PLAIN=1` →
`[START]` / `[OK]` / `[FAIL]` / `[RETRY]` / `[…]`.)

### 3.5 What to log at each boundary (required, still lean)

| Event | START says | END says (deliverables) |
|------|------------|-------------------------|
| Outer-loop | **both model seats** (orch + worker), where to `tail`, resume file | all stories shipped / FATAL + HEAD |
| M1 ANALYZE | “establish ground truth” + `Actor: harness scripts (no LLM)` | finding counts, recipe summary, commit |
| M1 PROFILE | title + attempt + **Actor: orchestrator MiniMax M2** | profile path, rubric-green/red, commit |
| M2 SEQUENCE | title + attempt + **Actor: orchestrator …** | each `S0k-<slug> brief generated` (or lint RED) |
| Story loop | `N` stories and order | — (ends with outer complete) |
| Per story header | `S0k-<slug> (k/N)`, deploy yes/no | — |
| M3 SPECIFY | title + attempt + **Actor: orchestrator …** | `specs/…` written + plan-lint + commit |
| M4/M5 | title + **configured orch + worker** + supervisor log path; per batch: **actual actor** | story complete / failed + outcome |
| Brief refresh | title + **Actor: orchestrator …** | which briefs changed, or skipped |

Supervisor should mirror the same “Actor:” lines into `/tmp/supervisor.log`
(and ideally one-line echoes into outer-loop when a batch starts) so the
demo user’s single `tail -f` stays truthful about Qwen vs MiniMax.

**Keep off the main log:** kantra rule ticks, OpenRewrite plugin chatter,
full lint JSON, Hermes tool-call traces, API keys, raw prompts. One
pointer line to the side file is enough.

### 3.6 Heartbeats during `mchat` (sparse)

Today `mchat` blocks with zero outer-loop lines. Add a watcher:

- While `timeout … hermes chat` runs, every **~60s** one line only:
  `… M2 SEQUENCE still working on MiniMax M2 (300s) — details /tmp/outer-….log`.
- Heartbeat must include the **active model name**; do **not** echo tool
  names, diffs, or token deltas on each tick. Optional totals belong in
  the single post-session line (§5), not the heartbeat.

### 3.7 Gate reporting

Replace bare lint append with framed GREEN/RED (see §3.4 bounce example):
top ≤5 humanized findings, path to full file, attempt N/2. Never treat
`hermes_rc=0` as phase success.

### 3.8 Separate noisy tool output

- `analyze.sh` / kantra → `/tmp/analyze.log`; main log gets counts only.
- Hermes transcript → `/tmp/outer-<tag>.log`; main log only points to it.
- Supervisor detail → `/tmp/supervisor.log`; main log START/END + outcome.

---

## 4. Logic enhancements tied to clearer logging

These are small gate/preflight improvements; each should emit a clear
log line when it fires.

1. **Roadmap structural preflight** (before/after M2 session):
   - Every story has non-empty `findings:` **or** explicit `findings: none`
     / `findings: -` convention documented in SEQUENCING.md.
   - Reject empty `findings:` that cause the parser to ingest `depends:`.
   - Reject recipe-executed rule ownership with message naming
     `migration/recipe-log.md`.
2. **Post-session commit check**: if gate is green but no
   `M2 sequence:` (or expected prefix) commit exists, log
   `mechanical commit` vs `session already committed <sha>` explicitly
   (today’s quiet `git commit -q` hides that).
3. **Attempt labels in tags** already exist (`m2-sequence-a1`); surface
   them in user-facing lines (“attempt 1 of 2”).
4. **On bounce, snapshot dirty tree** (optional):
   `git status --short migration/` into the log so demos see what a1
   left behind before a2 edits.
5. **Resume banner**: if `story-state.csv` has completes, log
   `resuming — S01 complete, next S02` at story-loop start.

---

## 5. Model identity + time-loss (demo honesty beat)

**Identity (required):** see design goal §2.4 and the `Actor:` lines in
§3.3. Demo users must always know whether MiniMax (orchestrator),
Qwen3.6 (worker), or a non-LLM harness script is performing the current
step.

**Cost / waits (optional one-liner after a session):**

```text
[ts] LLM MiniMax M2 (orchestrator): calls≈38 in≈2.1M_tok_sum max_in≈56k
     latency_sum≈20m 429_waits≈5m — detail ~/.hermes/logs/agent.log
[ts] LLM Qwen3.6 27B (worker): idle this phase (no OpenCode dispatch)
```

During M1–M3, saying the worker is idle is correct and reassuring (GPU
cold ≠ broken). During M4, if rewrite batches complete with **zero**
OpenCode/Qwen activity (V6 S01 observation), log that explicitly —
otherwise presenters assume the private model did the coding.

Implementation sketch: outer-loop knows orch provider/model from env;
supervisor already prints `worker=qwen27b/qwen3-6-27b` at start — promote
that to human labels and, when dispatching, log actual path
(`OpenCode→Qwen` vs `Hermes rewrite/escalation→MiniMax`). Best-effort
parse of `~/.hermes/logs/agent.log` for post-session totals; never fail
the run if parsing fails; never print API keys.

---

## 6. Suggested implementation slices

| Slice | Change | Demo value |
|------|--------|------------|
| **L0** | Phase dictionary: `M2 SEQUENCE — <description>`; START/END helpers; session≠gate | Readable process narrative |
| **L0b** | `Actor:` / model seat on every LLM phase + M4 batch (actual vs configured) | Demo user knows who is working |
| **L1** | END deliverables (`S01-… brief generated`, commit SHA) | User sees what was produced |
| **L2** | Sparse 60s heartbeat includes model name + transcript path | Not hung, not noisy |
| **L3** | Framed gate summaries (≤5 findings) + attempt N/2 | Bounce is teachable |
| **L4** | analyze/kantra → side log + counts summary | Clean M1 narrative |
| **L5** | Roadmap empty-`findings` preflight | Fewer cryptic lint tokens |
| **L6** | One-line LLM timing after sessions (verbose-friendly) | Honest cost / wait story |
| **L7** | Story `S0k-slug (k/N)` + supervisor log pointer | Multi-story runs stay followable |

Instruments: add a small harness test that sources the log helpers and
asserts a fake bounce produces `attempt`, `gate`, and findings path
substrings (no live Hermes).

---

## 7. README / demo-script alignment

When L0–L2 land, update Stage 080 README Step 5/6 “what you should see”
with **example log excerpts** (green path + one bounce path), so
presenters know the bounce line is expected pedagogy, not a crash.

Also document the side logs:

| File | Contents |
|------|----------|
| `/tmp/outer-loop.log` | Process narrative (tail this) |
| `/tmp/outer-<tag>.log` | Single Hermes session transcript |
| `/tmp/roadmap-lint.txt` / `/tmp/plan-lint.txt` | Last gate findings |
| `/tmp/analyze.log` | (proposed) kantra/OpenRewrite detail |
| `/tmp/supervisor.log` | Per-story M4/M5 |

---

## 8. Non-goals

- Do not stream full model tokens into `outer-loop.log`.
- Do not make outer-loop depend on cluster `oc` / vLLM metrics (observer
  monitors can keep doing that).
- Do not auto-kill sessions on 429; only **surface** waits.
- Do not change gate severity in the name of prettier logs — fix
  messages and preflights, keep two-attempt bounce semantics.

---

## 9. V6 evidence to keep in mind while implementing

- M1 profile: ~298s, first-try green — short success path must still
  print commit SHA + rubric OK.
- M2 a1: **1051s**, `hermes_rc=0`, gate RED, bounce — the exact
  failure mode these notes target.
- Time loss on a1 was largely orchestrator **429 token limits** + large
  context re-sends, invisible in outer-loop — motivates §5.
- Qwen3.6 worker idle through M2 **and** through S01 rewrite M4 batches
  (MiniMax/Hermes did the work; OpenCode never dispatched) — outer-loop
  must not imply the local GPU is coding when it isn’t; log actual actor.
