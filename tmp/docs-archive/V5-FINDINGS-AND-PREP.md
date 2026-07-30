# V5 cart migration — findings catalog & preparation (no implementation yet)

Written 2026-07-29. **Status: analysis / preparation only.**

Do **not** change the live run workspace, scaffold harness scripts, or Tier A
guides until this document is reviewed and an explicit implementation
decision is made. The companion backlog sketch
[`V5-HARNESS-IMPROVEMENT-PLAN.md`](V5-HARNESS-IMPROVEMENT-PLAN.md) remains a
*proposal*; it is not a start-now ticket.

**Purpose of this run (operator intent):** improve quality and speed of
*future* migrations through durable fixes — not to force the current cart
ship green.

---

## 1. Run snapshot (freeze point ~14:26 UTC 2026-07-29)

| Item | Value |
|------|--------|
| App / NS | `coolstore-cart-round3` / Dev Spaces `wksp-ai-developer` |
| Stories complete | S01–S04 (`migration/story-state.csv`) |
| S05 | M4 tasks T-001…T-010 committed; post–T-010 milestone verify → M5 expected next |
| HEAD | `386a976` T-010 already-complete (CATALOG props) |
| S05 M4 wall (metrics sum) | ~**247 min** across 16 sessions (includes sfix / burns) |
| Accept-gate semantic 5/5 | Still deferred until a clean deploy ship (if any) |
| Ship gaps at freeze | No `/api/cart/acceptance-check` in `src`; no `CATALOG_ENDPOINT` in `k8s/` |

Continue **observing** M5/evaluate/ship/acceptance. Bank failure signatures
here (append §8) — do not mid-flight patch harness or inject ship fixes
unless the operator explicitly changes this policy.

---

## 2. How to use this document

1. **Collect** — findings below (plus appendices from monitor / dual-diligence).
2. **Classify** — quality vs speed vs false-GREEN vs false-RED vs tooling tax.
3. **Blast-radius** — what each fix could break (instruments, prior green stories).
4. **Prep** — fixtures, instruments, dry-run plan (§7) before any PR.
5. **Decide** — which items enter WS-A / WS-B PRs; which stay deferred.
6. **Only then** implement, with instruments first where possible.

Related:
- Live log (may lag): [`V5-RUN-MONITOR.md`](V5-RUN-MONITOR.md)
- Lead execution plan: [`V6-LEAD-PLAN.md`](V6-LEAD-PLAN.md)
- Proposed PR detail (held): [`V5-HARNESS-IMPROVEMENT-PLAN.md`](V5-HARNESS-IMPROVEMENT-PLAN.md)
- Guide Tier A/B/C: [`SPRING-TO-QUARKUS-GUIDANCE-REVIEW.md`](SPRING-TO-QUARKUS-GUIDANCE-REVIEW.md)
- Prior cart lessons: [`CART-RUN2-ANALYSIS.md`](CART-RUN2-ANALYSIS.md)
- Lead T-008 ROI note (merged into §3.7): post-S05 harness backlog (2026-07-29)

---

## 3. Finding catalog

Confidence: **H** = reproduced with live evidence this run; **M** = strong
pattern / partial evidence; **L** = hypothesis to confirm at M5 or next e2e.

### 3.1 Authoring & plan-lint (fail late or never)

| ID | Finding | Conf | Evidence | Quality | Speed |
|----|---------|------|----------|---------|-------|
| A1 | `plan-lint` acceptance-path regex skips when a **comment** sits between `acceptance:` and `path:` | H | Live `migration.yaml`; S05 `tasks.md` has no `/api/cart/acceptance-check`; `PLAN OK` still | Ship gap invisible at M3 | Wastes full M4 before Phase E |
| A2 | `preserve: CATALOG_ENDPOINT` = substring in plan + grep in `src/main\|pom\|k8s` — **props alone suffice** | H | T-010 “ALREADY COMPLETE”; `application.properties` has token; `k8s/app.yaml` has no env | Deploy uses localhost catalog | T-010 ~8m ceremony |
| A3 | Soft target-trace tokens (`idempotent`, `thread-safe`) pass without decisive oracles (404/400/503/qty) | H | S05 T-008 vacuous tests; earlier S01/S04 soft pins in monitor | False semantic GREEN | Long infer tasks |
| A4 | `plan.md` ↔ `tasks.md` title/meaning drift (S05 T-009/T-010) | H | Live specs | Wrong worker focus | Rework / thin commits |
| A5 | Task `Location:` still cites **legacy** package paths | H | S05 tasks | Confusion / wrong reads | Opencode wrong-path reads (T-008 a1p1) |
| A6 | Brief/profile API path tension: `/cart` vs acceptance `/api/cart` | H | Monitor + live `@Path("/cart")` | Acceptance URL miss even if method added | Ship fail |
| A7 | §7 subsection / backtick discovery bugs (classroles, target-trace) — partially hot-fixed mid-run | H | Monitor early M1; lead confirmed | False RED thrash | M1 budget burn |
| A8 | `forbidden-inverted` / preserve-slice over-read — fixed earlier in V5 | H | Instruments / monitor | Was false RED on plans | — |

### 3.2 Sensors & static gates

| ID | Finding | Conf | Evidence | Quality | Speed |
|----|---------|------|----------|---------|-------|
| S1 | `@RestClient` wiring check skipped bare ctor inject (required `@Inject` window) | H | S04 T-003 Arc failure; `wiring_invariants` | Missed until augment | ~18m remediations |
| S2 | Style-autofix “compiles” ≠ Quarkus Arc validate | H | S04 T-003 | False progress | Extra sfix |
| S3 | `STORY_SCOPE` reverts needed cross-file support (`IfExists`, ExceptionMapper) | H | S05 T-005/T-007 scope_violation + debt | Contract incomplete until sfix | Multi-session tax |
| S4 | Milestone RED can be debt-recorded and continued (ship gate asymmetric) | H | T-006 debt; supervisor continue | Residual risk at ship | — |
| S5 | Preflight pollution / archive rules; pipefail empty-grep false RED | H | Prior V5 banked | False RED / wrong fixes | Preflight-fix waste |
| S6 | M5 evaluate narrative unreliable vs code+sensors | M | Monitor / prior runs | Bad operator signal | — |

### 3.3 Execution / orchestration (duration)

| ID | Finding | Conf | Evidence | Quality | Speed |
|----|---------|------|----------|---------|-------|
| E1 | Hermes backgrounds/polls `opencode` with `sleep` → `repeated_exact_failure_block` → **orphan_worker** | H | T-008 a1p0 log; events `orphan_worker` | No commit from residual | ~20–38m wait |
| E2 | Verify-and-commit re-dispatches opencode; short read-only burn | H | T-008 a1p1 | — | ~5.5m burn |
| E3 | Headless **deny-tax** ~5 min on heredoc / `python -c` / mkdir | H | T-008 a2p1 306s; S01 rewrite staging; rubric debug | — | Dominant waste class |
| E4 | EXECUTION.md already forbids heredocs & requires foreground worker — **not enforced** | H | Policy vs behavior | — | Repeated burns |
| E5 | Already-complete / absence tasks still burn long sessions (S05 T-001–003, T-010) | H | Metrics: T-001 21m, T-003 20m, T-010 8m | Low value commits | High wall |
| E6 | Lead status sometimes ahead of supervisor (assumed T-010 while on T-009) | H | Dual-diligence | Bad escalation timing | — |

### 3.4 Semantic quality / theater (GREEN ≠ done)

| ID | Finding | Conf | Evidence | Quality | Speed |
|----|---------|------|----------|---------|-------|
| Q1 | T-008 “idempotency” = mock endpoint twice → 200; no qty/state oracle | H | `55bc5f9` | Vacuous GREEN | ~45m+ churn |
| Q2 | T-009 “characterization port” = +1× 503 test | H | `5167c0b` | Thin vs task text | ~18m |
| Q3 | T-007 sfix commit message claimed mapper restore; diff was test pathParam only | H | `a39e5f8` | Narrative drift | — |
| Q4 | `dedupeCartItems` narrated as POST idempotency (§7) | H | Hermes a2p1 text | Wrong contract | — |
| Q5 | S04 `set()` nests `getShoppingCart` inside `carts.compute` (CHM reentrancy) | H | Live impl review | Latent prod bug | — |
| Q6 | S04 tests often Mockito unit, not `@InjectMock` / true CDI | M | S04 scorecard | Weaker characterization | — |
| Q7 | `ServiceExceptionMapper` maps broad `Exception` → 503, including `NotFoundException` | H | Phase E: missing `/` and acceptance → 503 with detail “HTTP 404 Not Found”; app log confirms mapper | Masks 404 as 503; acceptance fail mode distorted; can stay latent if correction only adds routes | — |
| Q8 | Fabricated `CartResource` (create-on-read) later deleted | H | S05 mid-run | Near-miss on GET contract | Cleanup tax |
| Q9 | Models correctly stayed POJOs (`needsDatabase: false`) — positive | H | Tree | Avoided JPA fabrication | — |

### 3.5 Ship / deploy contract (Phase E + correction design)

**Design (verified):** after a green pipeline on a `deploy=true` story,
`supervisor.sh` (~765–794) curls `/` and `migration.yaml` `acceptance.path`.
Failure sets `FAILED_TASK=acceptance-deploy` and opens a **deploy-correction**
round (`SHIPPING.md` acceptance-correction L87–95 + general deploy-correction
L61–67), budget `MAX_PER_CLASS=2`. So index / acceptance-check / config·k8s
fixes are **not** an unowned dead-end — they are designed Phase E inputs.
They remain **unowned by M4 tasks** and depend on a brittle Hermes session
(same deny/orphan/theater risks as M4).

| ID | Finding | Conf | Evidence | Quality | Speed |
|----|---------|------|----------|---------|-------|
| D1 | No acceptance endpoint in `src` at end of M4 | H | Grep at freeze | Expected to fail probe → correction | Full M4 before first ship attempt |
| D2 | No `CATALOG_ENDPOINT` in Deployment at end of M4 | H | `k8s/app.yaml` | Localhost catalog unless correction wires env | Same |
| D3 | T-010 closed preserve without k8s wiring | H | `386a976` | Gate under-specified (props suffice) | — |
| D4 | Acceptance path `/api/cart/...` vs resource `@Path("/cart")` | H | Live sources | Correction must add `/api` correctly | Failed or flaky correction |
| D5 | Acceptance **gate is fakeable** | H | supervisor ~767–777: `/` and path → HTTP 200 + `len(json)>0` (list length, or **`1` for any JSON object**) | Canned list/object passes without calling catalog; harness does **not** prove fetch via `CATALOG_ENDPOINT` | False ship GREEN |
| D6 | Operator fabrication-watch is load-bearing until D5 strengthened | H | SHIPPING forbids canned domain data; no automated proof | Must read endpoint source: real `@RegisterRestClient` / catalog call vs hard-coded products | — |
| D7 | Correction may **rewrite** `migration.yaml` `acceptance.path` to match a weaker endpoint | H | `14d9e83`: `/api/cart/...` → `/cart/acceptance-check` | Contract goalpost move; stamped path not immutable | Enables false green |
| D8 | Fail-open acceptance handler (`catch` → 200 empty) + no catalog call | H | Live `acceptanceCheck()`; body `cartCount:0` | Passes D5 gate without catalog or real state | — |

### 3.6 Guide / mapping gaps (feeds WS-A later — not process)

| ID | Finding | Conf | Note |
|----|---------|------|------|
| G1 | Workers still invent wrong REST/persistence defaults without richer Full maps | M | Guidance review Tier A |
| G2 | ExceptionMapper vs `@RestControllerAdvice` underspecified in OpenCode skills | M | Tied to T-007 thrash |
| G3 | REJECT `quarkus-spring-*` needs AGENTS prominence | M | Policy already elsewhere |

### 3.7 Merged ROI backlog (post-S05 / T-008 forensics)

Merged from lead dual-diligence note (2026-07-29): most of T-008’s ~45–60 min
wall was **orchestration waste**, not hard coding; `55bc5f9` was GREEN theater.
Land **after** the run, never mid-run. Maps onto catalog IDs above.

| Pri | Backlog item | Maps to | Class |
|-----|--------------|---------|-------|
| **1** | Foreground worker + residual kill/cap (~10–15 min); treat repeated `sleep` / `exit 124` / `repeated_exact_failure_block` as wedge | E1, E4 | Speed |
| **2** | Fast deny for heredocs / `python3 -c` / multi-line bash (seconds, not ~304s); allowlist `sensors.sh`, `summarize_worker.py` | E3, E4 | Speed |
| **3** | Verify-and-commit: no automatic second opencode; spawn only if dirty tree **and** sensors RED | E2 | Speed |
| **4** | Verify-class tasks: numeric oracle + already-complete probe; prefer `rewrite`+golden test; pin §7 meaning once (see oracle note below) | A3, Q1, Q4, E5 | Quality + speed |
| **5** | Story ownership: real idempotency/oracles in **S04 service**; S05 stays JAX-RS/mapping; expand `STORY_SCOPE` only when oracle needs service touch | S3, Q1 | Quality |
| **6** | Don’t gamble acceptance surface only on Phase E: M2/M3 explicit tasks **and/or** static/preflight that `acceptance.path` handler exists; fix plan-lint A1 so path must be tasked | A1, D1, D2, D3, D4 | Quality + speed |
| **7** | Strengthen acceptance gate **or** keep source-inspection as control (D5/D6); optional future: assert live catalog coupling | D5, D6 | Ship honesty |

**§7 / add() oracle (prep — do not invent “unchanged”):**  
Decide one sentence for the next e2e profile/contract, then pin tests and any
gate to it. Cart `add` is almost certainly **additive** (e.g. `add(c,i,2)`
twice → quantity **4**), not “quantity unchanged.” “Unchanged” would be a
wrong durable requirement. Alternatives only if legacy/§7 explicitly says
replace/idempotent-at-qty — write that decision in §7.2 before coding.

**Still banked outside this ROI list (do not drop):** S1 ctor `@RestClient`,
Q5 `set()` CHM reentrancy, A4/A5 plan drift & legacy Location, G\* Tier A
guides, S2/S4/S5 sensor asymmetries.

---

## 4. Duration picture (S05 M4 only)

Approximate session wall from `supervisor-metrics.csv` (S05 window):

| Band | Tasks / sessions | Notes |
|------|------------------|-------|
| Heavy (>20m) | T-004 ~31m, T-006 ~32m + sfix, T-008 a2 ~25m, T-001/T-003 ~20m | Conversion + validation + orphan aftermath |
| Remediation | T-005 sfix, T-006 sfix, T-007 sfix (~15m each, some rc=124) | Scope / sensor / deny |
| Churn | T-008 a1p0 orphan + a1p1 burn | Orchestration |
| Thin value | T-009 ~18m, T-010 ~8m | Theater / already-complete |

**Implication:** For **wall-clock**, follow §3.7 priority **1→4** (E1–E5). For
**ship honesty / less Phase E gambling**, follow **6→7** (A1, D1–D6) without
pretending correction doesn’t exist. Do not “speed up” by weakening
factory/Sonar/fidelity gates.

---

## 5. Proposed fixes → blast radius (prep, not approve)

For each candidate, prep must answer: instrument? golden fixture? what stays green?
Order below follows §3.7 ROI where applicable.

| Pri | Candidate | Helps | Risk if wrong | Prep before coding |
|-----|-----------|-------|---------------|--------------------|
| 1 | Supervisor-owned worker + residual kill/cap (E1/E4) | Speed | Kill healthy long workers; race on commit | Cap + verify-and-commit; metrics on false kills |
| 2 | Fast deny heredocs / `python -c` (E3/E4) | Speed | Block legitimate long commands | Allowlist sensors/mvn/opencode; deny only known bad shapes |
| 3 | Verify-and-commit: no auto-opencode (E2) | Speed | Leave dirty RED tree | Condition: dirty ∧ RED |
| 4 | Numeric oracle + already-complete (A3/Q1/E5) | Less theater | Wrong oracle (e.g. “qty unchanged”) | **Decide additive vs replace in §7.2 first**; golden tests |
| 5 | S04 owns service oracles; scoped STORY_SCOPE (S3) | Fewer sfix loops | Scope creep / pollution | Brief/SEQUENCING + allowlist pattern |
| 6a | Fix acceptance YAML parse (A1) | M3 catch | False RED if regex too loose | Instrument: commented `migration.yaml` unmapped → `LINT:acceptance` |
| 6b | M3 task + static handler for `acceptance.path` (D1) | Less Phase E gamble | Over-constrain non-deploy | Only `deploy=true` stories; fixture |
| 6c | k8s env for preserve when deploy (A2/D2/D3) | Real catalog | False RED without k8s | Gate when `deploy=true` / `k8s/` present |
| 6d | API path pin from acceptance prefix (A6/D4) | Ship URL | Breaks intentional `/cart` | Profile- or migration.yaml-driven |
| 7 | Stronger acceptance gate and/or keep D6 watch (D5) | Ship honesty | Flaky if catalog down; overfit cart | Prefer marker/count vs live catalog; keep source-inspect until then |
| — | Ctor `@RestClient` check (S1) | CDI quality | False RED on non-RC ctors | Unit fixture with/without qualifier |
| — | Tier A MAPPINGS/skills (G*) | Worker quality | Doc drift | Diff review; BOM pin; no scripts |
| — | Human inject acceptance+k8s on live run | Ship this run | Masks holes; two-writer | **Rejected** under current operator goal |

---

## 6. What we must not break

Regression checklist for any future PR (run before merge):

- [ ] `.hermes/harness/tests/instruments.sh` full suite GREEN
- [ ] plan-lint still accepts a minimal valid plan (rewrite-before-infer, preserve mapped, findings mapped)
- [ ] `forbidden-inverted` and preserve-slice bounds still hold
- [ ] Static sensors: package scope, forbidden mock tripwires, fidelity
- [ ] Flyway + `validate` / no `quarkus-spring-*` / constructor-injection policy unchanged
- [ ] Factory gate bars (coverage / duplication / violations) unchanged
- [ ] Non-deploy stories (`deploy=false`) not forced to have k8s env
- [ ] Cart `needsDatabase: false` path still doesn’t require JPA/Flyway
- [ ] Side-by-side scaffold + RH BOM 3.27.3.SP1 pin unchanged

---

## 7. Preparation checklist (before any implementation PR)

### 7.1 Finish evidence collection

- [ ] Let S05 M5/ship/acceptance reach a terminal outcome; append §8 with exact errors
- [ ] Export or copy `/tmp/supervisor-events.csv`, metrics, and key `sup-T-*.log` excerpts into `tmp/v5-evidence/` (gitignored) or link from monitor
- [ ] Dual-diligence accept-gate 5/5 on shipped service/endpoint **if** a deploy ever goes green; otherwise document blocker
- [ ] Reconcile monitor doc lag vs this catalog (single source: this file for decisions)

### 7.2 Analysis workshops (no code)

- [ ] Walk A1–A3 with `plan-lint.py` + real `migration.yaml` on a **fixture copy** (not live worker tree)
- [ ] Decide preserve semantics: string token vs “Deployment env required when deploy=true”
- [ ] **Decide cart `add()` / POST “idempotent” oracle** — one sentence for next e2e profile (default hypothesis: **additive**, two `add(c,i,2)` → quantity **4**). Explicitly reject “quantity unchanged” unless legacy/§7 says otherwise. Record decision in §9
- [ ] Rank implementation order using §3.7 ROI × blast radius (§5); defer low confidence
- [ ] Confirm WS-A (Tier A guides) is still desired as a **separate** PR after process prep — or after B0 only
- [ ] For D5: choose strengthen-gate design vs “source-inspect remains control” for next e2e

### 7.3 Design freeze (written before coding)

For each accepted fix ID:

- [ ] Spec: input → output → fail message
- [ ] Instrument case name(s)
- [ ] Rollback note
- [ ] “Will not change” list (§6 subset)

### 7.4 Implementation gates (when operator says go)

1. Instruments / fixtures first  
2. Harness change  
3. Re-run instruments  
4. Optional: staging dry-run on a copy of cart tree  
5. Only then schedule next e2e proving run  

---

## 8. Appendix — Phase E / post-freeze log (fill as run continues)

| UTC | Event | Evidence | Implication for catalog |
|-----|-------|----------|-------------------------|
| 14:25 | T-010 committed already-complete | `386a976` | A2/D3 confirmed |
| 14:31–14:35 | M5 ship pipeline green; acceptance fail | `/` and `/api/cart/acceptance-check` → **503**; body `detail: HTTP 404 Not Found` + `status: 503`; pod 1/1 Running; log `ServiceExceptionMapper` ← `NotFoundException` | **Q7 materialized**; layered with D1 (routes missing). Gate logged `products 1` because problem+json **object** counts as 1 (D5) |
| 14:38–14:50 | Deploy fix r1 (multiple commits → `14d9e83`) | Added `/` index + `/cart/acceptance-check`; **rewrote** `migration.yaml` `acceptance.path` `/api/cart/...` → `/cart/...` (goalpost move); fail-open `catch` → 200/`cartCount:0`; no catalog call; mapper still `Exception`; no k8s `CATALOG` | Fabrication + contract move |
| 14:53–14:55 | Supervisor declared success | `/` 200; `/cart/acceptance-check` 200; `products=1` (JSON **object**); `SUPERVISOR COMPLETE: migration shipped and accepted`; outer loop “all stories shipped”; pushed `6cec850` to origin | **False green** — accept-gate rejects |
| — | Post-run verdict (operator) | Do **not** promote run-4 tree to golden; top backlog = fabrication-proof acceptance (D5 + path immutability + k8s + mapper) | Prep before re-run |

---

## 9. Decision log (operator)

| Date | Decision |
|------|----------|
| 2026-07-29 | Goal = durable quality/speed for future runs; **no rush to implement**; no ship-injection to force V5 green |
| 2026-07-29 | WS-A Tier A brief captured in improvement plan but **held** pending this prep |
| 2026-07-29 | Acceptance gaps are Phase E **correction inputs**, not a dead-end; watch fabrication (D5/D6) |
| 2026-07-29 | Merged post-S05/T-008 ROI backlog into §3.7; **rejected** “two adds → quantity unchanged” as default oracle |
| 2026-07-29 | Run-4 **false green**: S05 accepted via fail-open/catalog-blind `/cart/acceptance-check` + path rewrite; **do not** promote to golden; harness acceptance-correction is top defect |
| 2026-07-29 | Lead takeover plan drafted: [`V6-LEAD-PLAN.md`](V6-LEAD-PLAN.md) — P0 fabrication-proof **before** fresh e2e; no coding until §7 Phase A sign-off |
| 2026-07-29 | Merged prior-lead 24-item list into V6 plan §1 (P0–P4 + `[you]`); added debt-clear, path-filter, digest-pin, readiness; cut line remains P0 |
| 2026-07-29 | Accept-gate **REJECT** recorded: [`V5-ACCEPT-GATE-REJECTION.md`](V5-ACCEPT-GATE-REJECTION.md) |
| 2026-07-29 | `add()` oracle **locked**: additive — two `add(c,i,2)` → quantity **4** |
| 2026-07-29 | Operator authorized V6 Phase B (“let’s start”); design freeze: [`V6-ACCEPTANCE-GATE-DESIGN.md`](V6-ACCEPTANCE-GATE-DESIGN.md) |
| | *(pending)* New project/workspace — only after Phase B P0 exit |

---

## 10. Bottom line

V5 already paid for a rich defect catalog: **orchestration deny/orphan tax**,
**GREEN theater on soft tasks**, **sensors that miss CDI shape**, and **ship
gates that are either late (Phase E correction) or fakeable (D5)**. The right
next step is disciplined prep (fixtures, blast-radius, design freeze) — not a
pile of scaffold PRs.

When prep §7 is checked off and §9 records an implement decision, use
[`V5-HARNESS-IMPROVEMENT-PLAN.md`](V5-HARNESS-IMPROVEMENT-PLAN.md) together with
**§3.7 ROI order** (speed 1–4 first, then ship-honesty 6–7 / A1), not the
largest Tier A doc sweep unless guides are explicitly prioritized for
non-process reasons.
