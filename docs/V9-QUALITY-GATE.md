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

## 2026-07-30 — Mandate + polish implemented; S02 resumed

- **Verdict:** ADVANCE (resume after polish — not nursing false greens)
- **AGENTS.md:** non-negotiable mandate baked (no compromises; fix+re-run; bank+implement; never ask)
- **Harness:** O-STY, O-T6c, O-T6d, O-AC2 ✅ (instruments 112/112)
- **Reset:** force `main` to `b431cf8` (drop false T-006/T-007); harness sync `92e30a2`; `RESUME_STORY=S02` `RESUME_RUN_BASE=6857561`
- **Live:** T-001–T-005 skipped (honest); **T-006 characterization** re-running via OpenCode (O-T6d will refuse main-only mechan); T-007 will not false-skip on waiver CATALOG (O-AC2)
- **Next action:** O-DRV3 detailed gates on T-006/T-007; HOLD again on any false green

---

## 2026-07-30 — Process miss: silent ticks (~08:50–09:02 UTC)

- **Verdict:** HOLD process (harness frozen before S03)
- **What went wrong:** Agent did not post 120s chat pulses; driver status froze at `08:49:46` while S02 M4/M5 completed unobserved in chat.
- **Banked:** **O-DRV4** ⬜ — driver CRITICAL if local status file mtime/tick age > 2.5× interval (stale wake = agent not responding); agent must treat overdue tick as P0 chat pulse.
- **Action taken:** Froze outer/supervisor/hermes before S03; driver restarted with `V8_AUTO_RESTART=0` pending S02 story gate write-up.

---

## 2026-07-30 — S02 T-006 / T-007 detailed + story gate

- **HEAD:** `5912fd7` S02 story complete: roadmap ledger; factory pipeline succeeded earlier (`coolstore-cart-service-v7-push-mdgjv`)
- **T-006 `e5fd7e1`:** ADVANCE — real `DomainModelTest.java` (+376 lines), OpenCode/Qwen; constructors/getters/toString/serialization/cart ops with real asserts; **no** G-PLACE. O-T6d did its job (worker wrote tests, not mechan main-only).
- **T-007 `0779ae9`:** ADVANCE — O-ESCW allow-empty (not O-AC2 CATALOG false-skip). Substance: `com.redhat.coolstore` under `src/main` count **0** — package-rename verification already true; empty commit honest.
- **S02 story:** sensors/preflight/pipeline green reported; characterization present (S-CHAR).
- **Verdict:** ADVANCE S02 substance — but **do not start S03** until O-DRV4 noted and chat-pulse discipline restored; then resume with `RESUME_STORY=S03` (no sticky RUN_BASE).
- **Banked:** O-DRV4 ⬜

---

## 2026-07-30 — S03 M3 specify (comprehensive)

- **HEAD:** `f1ce6e4` `S03 spec: service layer plan (plan-lint green)`
- **How we got here:** Outer started M3 after S02; operator freeze SIGKILL’d hermes (`hermes_rc=137`) twice → false “failed plan lint twice”. Left **uncommitted** lint-RED draft (`rewrite` after `infer`; `springboot-metrics-to-quarkus-0200` unmapped).
- **AI action quality (MiniMax draft):** Wrong task classing for post-conversion tests/verify (must be `infer` after first redesign infer). Metrics finding omitted despite roadmap scope. Draft otherwise had correct service harvest targets (CDI, ConcurrentHashMap, REST client, waivers).
- **Repair (agent):** Rewrote `tasks.md` — rewrite block T-001..T-003 (package, metrics closeout vs existing `quarkus-smallrye-metrics`, catalog URL), infer T-004..T-009 (Promo/Shipping/Catalog/ShoppingCartServiceImpl + characterization + package verify). `plan-lint` **EXIT 0** (9 tasks). Committed `S03 spec:`.
- **Banked:** **S-INFTEST** ⬜ (teach REDESIGN post-infer tests = Class infer); **O-M3KILL** ⬜ (rc=137 must not burn M3 attempts).
- **Verdict:** ADVANCE — resume S03 execute (M3 already present + lint green; no sticky `RUN_BASE`).
- **Next:** M4 T-001… with O-DRV3 detailed gates; HOLD on ceremonial/empty/false greens.



---

## 2026-07-30 — S03 T-001 detailed

- **HEAD:** `66324ed` T-001: Service package structure verification - directory already exists
- **Diff:** allow-empty / no tracked files (empty `src/main/java/com/demo/service/` not in git)
- **AI code quality:** N/A substance — directory exists on disk; no `.gitkeep`/`package-info.java`
- **AI action quality:** OpenCode rc=0, no commit → MiniMax escalation wrote allow-empty. **O-ESCW should have** fired (acceptance met). Likely blocked by dirty `.hermes/PLANNING.md` (S-INFTEST sync) and/or empty-dir not counting as satisfied path for mechan.
- **Verdict:** ADVANCE (structure present) — process waste noted
- **Banked:** **O-PKGDIR** ⬜; reinforce O-ESCW when acceptance is mkdir-only



---

## 2026-07-30 — S03 T-002 / T-003 detailed

- **T-002 `1e55e0a`:** ADVANCE — substance already true from S01 (`quarkus-smallrye-metrics` in pom; no Actuator). Diff is `migration/run-log.md` only. **AI action:** worker rc=0 → MiniMax escalation again (same O-ESCW/O-ESCW2 waste as T-001). Finding closeout honest.
- **T-003 `d4893fa`:** ADVANCE — `already-complete.py` fast path (CATALOG_ENDPOINT subject matches task — O-AC2 correct this time). Property present in `application.properties`. No MiniMax burn.
- **Verdict:** ADVANCE rewrite batch; infer T-004+ is the real S03 substance.



---

## 2026-07-30 — S03 T-004 detailed

- **HEAD:** `9cb3a73` T-004 PromoService via OpenCode/Qwen (no MiniMax)
- **Diff:** +68 lines `src/main/java/com/demo/service/PromoService.java` only
- **AI code quality:** ADVANCE — `@ApplicationScoped`, `ConcurrentHashMap.newKeySet()` for promotions, seed `329299`/0.25 preserved, applyCartItemPromotions/applyShippingPromotions logic matches staging; package `com.demo.service`; dropped Spring `@Component`/Serializable (appropriate CDI redesign). No G-PLACE.
- **AI action quality:** Worker-first infer path worked; auto-commit; task sensor GREEN.
- **Verdict:** ADVANCE



---

## 2026-07-30 — S03 T-005 detailed

- **HEAD:** `34782c6` ShippingService via OpenCode/Qwen
- **AI code quality:** ADVANCE — `@ApplicationScoped`; shipping tiers $2.99/$4.99/$6.99/$8.99/$10.99 preserved vs legacy; package `com.demo.service`.
- **AI action quality:** Clean worker-first path.
- **Verdict:** ADVANCE



---

## 2026-07-30 — S03 T-005 sensor fix (S1066)

- **HEAD:** `a978f29` T-005 sensor fix: collapse nested if in PromoService.applyShippingPromotions
- **Cause:** post-T-005 milestone sonar RED `java:S1066` on T-004 PromoService (nested if) — style-autofix 0 files; MiniMax sfix ~5m for one-line merge.
- **AI code quality:** ADVANCE — trivial collapse; behavior preserved.
- **AI action quality:** Correct path (sfix after autofix miss). Waste: MiniMax for S1066 that should be deterministic.
- **Banked:** **O-S1066** ⬜ — add OpenRewrite/recipe or tiny deterministic fixer for collapsible if (S1066) to style-autofix.
- **Verdict:** ADVANCE — continue T-006



---

## 2026-07-30 — HOLD S03 T-006 false already-complete (O-AC3)

- **Defect:** `79383e8` T-006 ALREADY COMPLETE — CATALOG_ENDPOINT already present — but **`CatalogService.java` absent**. O-AC2 subject-check still matched preserve token in Goal/Target of a class-conversion task.
- **AI action quality:** FAIL — false green skip; T-007 had started against missing dependency.
- **Action:** Freeze harness; implement **O-AC3** (missing Target `.java` blocks preserve skip); instruments; reset to `a978f29` (drop false T-006); resume S03 from T-006.
- **Verdict:** HOLD → polish → re-run T-006 honestly



---

## 2026-07-30 — S03 T-006 detailed (post O-AC3)

- **HEAD:** `2e920aa` CatalogService via OpenCode/Qwen (honest re-run after HOLD)
- **Diff:** +18 lines interface — `@RegisterRestClient(configKey = "catalog-service")`, `@GET @Path("/api/products")`, `List<Product> products()`
- **AI code quality:** ADVANCE — matches task target; package `com.demo.service`
- **AI action quality:** O-AC3 prevented false CATALOG_ENDPOINT skip; worker-first path
- **Verdict:** ADVANCE — T-007 next



---

## 2026-07-30 — S03 T-007 detailed

- **HEAD:** `cde82fd` ShoppingCartService + Impl + CatalogUnavailableException(+Mapper)
- **AI code quality:** ADVANCE — `@ApplicationScoped`, `@Inject` ctor with `@RestClient CatalogService`, `ConcurrentHashMap` carts/productMap, `compute` for getShoppingCart, cache TTL 300s + `shouldRefreshCache` (no clear-on-miss in getProduct), 503 mapper via `@Provider` ExceptionMapper. Business pricing/promo/shipping/dedupe preserved. Note: `refreshProductCache` clears then reloads (full refresh) — acceptable vs clear-on-miss.
- **AI action quality:** Worker wrote files rc=0 without commit → MiniMax escalation closed commit (waste). Prefer O-T6 mechan when dirty tree + GREEN — investigate why O-T6b skipped (maybe .hermes dirt from O-AC3 sync?).
- **Verdict:** ADVANCE — characterization T-008 next



---

## 2026-07-30 — S03 T-008 detailed

- **HEAD:** `c15f95d` — PromoServiceTest (+136), ShippingServiceTest (+103), ShoppingCartServiceTest (+290); pom test deps
- **AI code quality:** ADVANCE — real asserts (329299/25%, shipping tiers, cart ops); no G-PLACE
- **AI action quality:** Worker-first OpenCode; O-T6d correct
- **Verdict:** ADVANCE



---

## 2026-07-30 — Mandate: temporary manual → durable → re-run

- **Rule update:** AGENTS.md Track B mandate, `stage-080-track-b.md`,
  `stage-080-quality-advance` — hand edits OK only as probes; must durableize
  in harness/skills and re-run for proof.
- **Open from T-008 probe:** O-SFIXLOOP, O-SONARFIX (and remaining S5778 on
  PromoServiceTest) — not closed until durableize + re-run.



---

## 2026-07-30 — Mandate: MiniMax-over-Qwen escalation loop

- **Rule update:** AGENTS.md Track B + driver goal #11; `stage-080-track-b`;
  `stage-080-quality-advance` Escalation gate; `tmp/v8-driver-loop.sh` O-DRV3
  checklist embeds capture → Qwen-log RCA → durableize → retest.
- **Bar:** MiniMax GREEN after takeover is not closed until durable fix +
  retest proves Qwen can finish that failure class without MiniMax.



---

## 2026-07-30 — Mandate: migration-general durable fixes

- **Rule update:** AGENTS.md Track B (generalizable harness) + driver goal
  #12; `stage-080-track-b`; `stage-080-quality-advance` bank/fix bar.
- **Bar:** Coolstore cart is the specimen. Durable harness/skill/sensor
  fixes must apply to any Spring Boot → Quarkus migration on this method
  (parameterized by migration.yaml / briefs / findings). Specimen-specific
  literals belong in stories or named fixtures — not harness core.

