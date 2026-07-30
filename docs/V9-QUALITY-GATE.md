# V9 quality-advance gate

Living log for Stage 080 Track B run **V9**. See
`.agents/rules/stage-080-track-b.md` and
`.agents/skills/stage-080-quality-advance/SKILL.md`.

Cadence: **detailed** analysis after each T-NNN (and sensor-fix / partial
autofix / escalation) — immediately, without waiting to be asked; driver
O-DRV3 nags via `tmp/V9-TASK-ANALYSIS-PENDING.md`. Comprehensive after each
M; full gate before story ship / next story.

Verdicts: `ADVANCE` | `HOLD` | `ABORT`.

---

## 2026-07-30 — V9 start

- **Verdict:** ADVANCE (start only)
- **HEAD:** polished harness on pristine baseline
- **Next action:** Drive M1→… with per-task / per-M gates

---

## 2026-07-30 — S01 M4 task log (light)

| Task | Path | Note |
|------|------|------|
| T-001 | Qwen | BOM — OK |
| T-002 | **escalation** | worker rc=0, no commit (already satisfied) → MiniMax; attempt 1 burned then commit |
| T-003 | Qwen | Maven plugins — OK |
| T-004 | Qwen | native profile — OK |
| T-005 | **escalation** | same already-satisfied pattern → MiniMax |
| T-006 | Qwen | metrics — OK |
| T-007 | **escalation** + 15m quota | worker rc=0 no commit → MiniMax hit rate limit → later “Already satisfied” |
| T-008 | **escalation** | already-satisfied → MiniMax |
| T-009 | Qwen | **BAD:** created ceremonial `AcceptanceEndpoint` `Map.of("status","ok")` + test; also `application.properties` |
| T-010 | started then **HOLD** | plan required another status placeholder — stopped |

### Escalation root cause (not previously captured in depth)

OpenCode/Qwen often **verifies POM already meets the task** (earlier T-001
brought Quarkus plugins/deps), exits **rc=0**, leaves a **clean tree**, and
**does not create** a `T-NNN:` commit. Supervisor then escalates to MiniMax,
which only writes “Already satisfied” — burning rate-limited quota (T-007 =
900s backoff). `already-complete.py` does not cover POM satisfaction (only
preserve/absent-remove).

**Banked/fixed:** **O-ESCW** — clean tree + task GREEN after worker →
allow-empty “Already satisfied” commit, no MiniMax.

---

## 2026-07-30 — S01 HOLD (comprehensive mid-M4)

- **Verdict:** HOLD
- **HEAD:** `a5eae8f` (after strip + plan repair); tree = `application.properties` only under src
- **What was wrong:**
  1. Escalations not root-caused until asked (process gap → skill cadence update).
  2. T-009/T-010 scheduled ceremonial acceptance on S01 (`pom.xml` roadmap scope).
  3. T-009 shipped status-map acceptance (G-OK class); milestone did not catch it (G-AC3).
  4. Original T-012 **design** pulled `CartEndpoint` / `ShoppingCartServiceImpl` into S01.
- **Remediation done:**
  - Removed AcceptanceEndpoint (+ test); pushed.
  - Plan: drop T-010; T-009 properties-only + waivers; T-011/T-012 POM-only; plan-lint OK with S01 findings-scope.
  - Harness: O-ESCW, S-AC1, G-AC3; quality skill now **per-task + per-M**.
- **Banked:** O-ESCW ✅, S-AC1 ✅, G-AC3 ✅
- **Next action:** Resume S01 M4 for T-011/T-012 only (`RESUME_STORY=S01`,
  `RESUME_RUN_BASE=3729183`); then M5 + full S01 story gate before S02.

---

## 2026-07-30 — S01 ship → S02 M4 (catch-up)

- **S01:** factory pipeline succeeded; ledger `S01,complete`; `specs/S02-domain-models` created at M3.
- **S02 M4 (in flight):** T-001–T-004 models harvested (`Product`, `Promotion`, `ShoppingCartItem`, `ShoppingCart` under `com.demo.model`). **T-005** ShoppingCart harvest post-commit: Sonar RED → style-autofix partial → MiniMax **sensor-fix** running. **T-006** characterization tests still queued (good — S-CHAR).
- **Watch:** T-011 earlier swept `.hermes/` into a task commit (O-T6b gap on escalation path) — banked **O-T6c**.
- **Driver:** interval **120s**; ticks must produce a short user-visible chat update.
- **Process miss (corrected):** T-005 RED→partial was only surface-noted until the human asked for depth — violates quality-advance intent. **O-DRV3** + skill v1.2 bake mandatory detailed post-task analysis into the driver.

---

## 2026-07-30 — S02 T-005 detailed (Sonar RED → style-autofix partial)

- **Verdict:** ADVANCE (harness continues; sfix in flight) — process was late
- **HEAD:** `e2763e5` T-005 sensor fix: partial deterministic style-autofix
- **What shipped (substance):**
  - `2fe1731` — honest harvest: `src/main/java/com/demo/model/ShoppingCart.java` only (worker/OpenCode).
  - `e2763e5` — OpenRewrite diamond fix on demo `ShoppingCart` (`S2293` ×2 cleared).
- **Sensor trail:**
  1. Milestone RED: 3 new — `S2293`×2 on `ShoppingCart`, `S1186`×1 on **`ShoppingCartItem.java:14`** (T-004 file; cross-task new-code bleed).
  2. style-autofix: recipes OK; diamond fixed; `S1186` remains → partial commit → MiniMax sfix.
- **Anomalies / harness smells:**
  1. **O-STY:** autofix also rewrote `migration/staging/.../ShoppingCart.java`, `PromoService.java`, `ShoppingCartServiceImpl.java`; log said “1 files changed” (`src/` only) but supervisor `git add -A` swept staging into the T-005 sensor-fix commit. Staging is fidelity baseline — must not be mutated by cleanup.
  2. **S1186 sticky:** Item ctor already has `// Default constructor for deserialization` (legacy empty); gate still lists `java:S1186` — sfix may thrash if comment is already “enough” visually but analyzer disagrees (or stale list). Product/Promotion empty ctors not in current violation list (baseline/new-code window).
- **Weak / dishonest:** none on harvest itself; partial message is honest. Process was dishonest by deferring this write-up.
- **Banked:** **O-STY** ⬜ (autofix+`git add -A` staging sweep); **O-T6c** ⬜ (escalation `.hermes/` sweep); **O-DRV3** ✅ (driver pending + CRITICAL).
- **Next action:** Let MiniMax sfix finish; re-check `S1186` with cheap `sensors.sh sonar`; do not clear milestone on hope. T-006 characterization still required (S-CHAR). Implement O-STY before next full wipe/restart.

---

## 2026-07-30 — S02 T-005 sfix follow-up (`b431cf8`)

- **Verdict:** ADVANCE (closed)
- **HEAD:** `b431cf8` T-005 sensor fix: fix empty constructor Sonar violation (java:S1186)
- **Substance:** MiniMax added explanatory comment on `ShoppingCartItem()`; supervisor later logged `sensor-fix committed and milestone GREEN` at 08:30:55.
- **Next action:** Was T-006 — see HOLD below.

---

## 2026-07-30 — S02 T-006 / T-007 HOLD (O-DRV3 caught; false greens)

- **Verdict:** **HOLD** (harness stopped; `V8_AUTO_RESTART=0`)
- **HEAD:** `7cc849d` (after T-007 empty already-complete)
- **Process:** Driver O-DRV3 correctly set `tmp/V9-TASK-ANALYSIS-PENDING.md` for `cbe0fb9`+`7cc849d`. Detailed analysis run immediately (not deferred to human ask).

### T-006 `cbe0fb9` — false green

- **Message:** `Add domain model characterization tests (mechanical verify-and-commit; O-T6)`
- **Substance:** **No `src/test` files at all.** Diff is only `// Default constructor for deserialization` comments on Product/Promotion/ShoppingCart (leftover from sfix / S1186 hygiene).
- **Root cause:** O-T6 fires on dirty tree + task sensor GREEN; task sensor is green with zero tests. Mechan commit steals the T-006 title for unrelated main-source edits.
- **Banked:** **O-T6d** ⬜

### T-007 `7cc849d` — false green

- **Message:** `ALREADY COMPLETE — CATALOG_ENDPOINT already present (V6 P2.4)` (allow-empty)
- **Task goal:** Package rename verification (`com.redhat.coolstore` count → 0)
- **Root cause:** `already-complete.py` preserve fast-path: `CATALOG_ENDPOINT` is in `migration.yaml` preserve list and also appears in the T-007 body window via story waiver text → skip worker with empty commit. Confirmed: `python3 already-complete.py … T-007` → `present:CATALOG_ENDPOINT` rc=0.
- **Banked:** **O-AC2** ⬜

### Next action

1. ~~Implement O-T6d + O-AC2 + O-STY (+ O-T6c)~~ **done** (instruments green for O-AC2/O-T6d).
2. **ABORT/reset S02** (or full V10 wipe): T-006/T-007 false greens are not recoverable by resume-forward — prefer clean re-run after polish sync (AGENTS mandate: multiple partial runs > one broken completion).
3. Sync polished harness → golden scaffold → workspace; clear HOLD only when restart is ready.

---

## 2026-07-30 — Mandate + polish implemented (pre-rerun)

- **Verdict:** HOLD remains until clean re-run
- **AGENTS.md:** non-negotiable mandate baked (no compromises; fix+re-run; bank+implement; never ask)
- **Harness:** O-STY, O-T6c, O-T6d, O-AC2 ✅
- **Next action:** commit/push demo + bootstrap scaffold; wipe or reset cart S02+ and restart Track B with open bank empty
