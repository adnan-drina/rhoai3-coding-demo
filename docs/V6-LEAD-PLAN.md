# V6 lead plan — harness fixes, then fresh e2e migration

Written 2026-07-29 (updated with consolidated outstanding list merge).  
**Lead:** Cursor agent (takeover). Prior driver list merged below.

**Authority (read in this order before changing anything):**

1. [`V5-FINDINGS-AND-PREP.md`](V5-FINDINGS-AND-PREP.md) — findings catalog, D5–D8 false green, ROI §3.7, must-not-break §6  
2. [`V5-HARNESS-IMPROVEMENT-PLAN.md`](V5-HARNESS-IMPROVEMENT-PLAN.md) — WS-A/WS-B detail  
3. [`SPRING-TO-QUARKUS-GUIDANCE-REVIEW.md`](SPRING-TO-QUARKUS-GUIDANCE-REVIEW.md) — Tier A guides (optional)  
4. This file — **execution sequence + merged backlog**

**Non-goals:** promote run-4/V5 tree to golden; patch that tree to force green;
OpenRewrite/Spring-compat; weaken factory/Sonar/fidelity gates; start P0 code
before Phase A sign-off + design freeze.

---

## 0. Posture

| Item | Decision |
|------|----------|
| Run-4 / V5 ship | **REJECT** — fabricated acceptance; do not golden |
| Contaminated remote | `coolstore-cart-round3` `main` — not a golden source; V6 = new/wiped app |
| Cut line | **P0 must land before any re-run, golden sync, or further stories** |
| Lead role | Phase A docs → design freeze → instruments→code P0 → P2 speed → V6 e2e |
| Operator `[you]` | Explicit V6 project name / RHDH create if scaffolder UI needed; otherwise lead executes |

---

## 1. Merged outstanding backlog (canonical)

Tags: `[harness-code]` · `[process/doc]` · `[app]` · `[you]`  
**V6 phase** maps to this plan’s execution phases.  
**ID** cross-links findings where useful.

### P0 — Blocks any honest re-run (fabrication-proofing)

Agree with prior lead: **honest cut line is here.**

| # | Item | Tag | V6 | Findings |
|---|------|-----|----|----------|
| P0.1 | Acceptance must prove **real catalog fetch** (products array / live marker — not any 200+JSON) | harness-code | B R2/R4 | D5, D8 |
| P0.2 | Forbid fail-open on acceptance path (`catch` → `Response.ok` 200) | harness-code | B R3 | D8 |
| P0.3 | Forbid correction editing `migration.yaml` `acceptance.path` | harness-code | B R1 | D7 |
| P0.4 | Strengthen gate beyond `200 + len(json)>0` (object→1 is invalid) | harness-code | B R4 | D5 |
| P0.5 | Acceptance-correction **requires** k8s `CATALOG_ENDPOINT` + mapper narrowing (not optional) | harness-code | B R5/R6 | D2, D3, Q7 |

### P1 — Correctness (run-4 bugs → enforce on next run)

| # | Item | Tag | V6 | Notes |
|---|------|-----|----|-------|
| P1.1 | Narrow `ServiceExceptionMapper` (not `ExceptionMapper<Exception>`) | harness-code (+ app on V6) | B R6 + E bar | Don’t “fix” run-4 for golden; gate/SHIPPING force it on V6 |
| P1.2 | Wire `CATALOG_ENDPOINT` in `k8s/` Deployment env | harness-code (+ app on V6) | B R5 | Same — enforce, don’t baseline run-4 |
| P1.3 | Decide `add()` semantics; numeric-oracle T-008 (not vacuous 200×2) | process/doc | A2 + D Q2 | **Decision: additive → qty 4** (confirm in §7) |
| P1.4 | Constructor `@RestClient` wiring check | harness-code | D Q1 | Findings S1 |

### P2 — Orchestration efficiency (T-008 forensics)

| # | Item | Tag | V6 | Findings |
|---|------|-----|----|----------|
| P2.1 | Foreground worker + residual kill/cap (~10–15 min) | harness-code | C S1 | E1, E4 |
| P2.2 | Fast-deny heredocs / `python3 -c` / multi-line bash (seconds) | harness-code and/or `[you]` platform | C S2 | E3 — prefer harness; platform deny is bonus |
| P2.3 | Verify-and-commit without automatic second opencode | harness-code | C S3 | E2 |
| P2.4 | Already-complete fast path (probe → skip opencode) | harness-code | C S4 | E5 |
| P2.5 | **Don’t clear debt on green ship that still has unresolved RED** | harness-code | C S5 | S4 — **added from prior lead list** |

### P3 — Story-design / process

| # | Item | Tag | V6 | Notes |
|---|------|-----|----|-------|
| P3.1 | Verify-class tasks: numeric oracle in profile; prefer rewrite+golden | process/doc | D Q2/Q3 | ROI #4 |
| P3.2 | Own idempotency in S04 service; S05 JAX-RS; careful STORY_SCOPE | process/doc | D Q2 | S3 thrash |
| P3.3 | M2/M3 emit acceptance surface tasks **or** static handler-before-deploy | harness-code + process | B R7 | A1, D1 |
| P3.4 | 2nd-pipeline path-filter (docs-only pushes shouldn’t full build/deploy) | harness-code | F (post-V6 or parallel if cheap) | **Added — not P0** |

### P4 — Pipeline / deploy robustness

| # | Item | Tag | V6 | Notes |
|---|------|-----|----|-------|
| P4.1 | Digest-pin Deployment image (not `:latest` + force-restart) | harness-code | F | **Added** — reduces stale-pod race |
| P4.2 | Real readiness wait before acceptance probe (replace `sleep 10`) | harness-code | B adjacent / F | **Added** — pair with P0 gate if small; else F |

### Evaluation / operator deliverables

| # | Item | Tag | V6 |
|---|------|-----|----|
| E.1 | Formal run-4 accept-gate **REJECTION** + evidence trail | process/doc | A1 |
| E.2 | Confirm run-4 tree excluded from golden | process/doc | A / §0 |
| E.3 | Golden force-sync of **harness scaffold** (not run-4 app) via `bootstrap-scaffold-repos.sh` | harness-code | Lead executes after merge — **never** sync fabricated cart HEAD |
| E.4 | Environment-level fail-fast deny | harness-code | `maas-api-key-provisioning.yaml` → `approvals.timeout=5` + `approvals.deny` |

### Optional (not in prior lead’s 24 — keep deferred)

| # | Item | Tag | V6 |
|---|------|-----|----|
| O.1 | Tier A MAPPINGS / OpenCode / AGENTS enrichment | process/doc | D PR-A1 or V6.1 |
| O.2 | `set()` CHM reentrancy (Q5) | app/process | Accept-gate watch on V6; fix in-run if seen |

**Count:** prior lead 24 + O.* deferred. Cut line unchanged: **P0 (P0.1–P0.5) before re-run.**

---

## 2. Analysis vs prior lead list

| Prior lead claim | Dual-diligence |
|------------------|----------------|
| P0 is the cut line | **Agree** |
| Start drafting P0 patch now | **Hold** until Phase A sign-off + design freeze (instruments first) |
| P1 mapper/k8s as app fix on run-4 | **Disagree on venue** — don’t polish run-4 for golden; encode as harness **requirements** for V6 |
| P2.2 platform vs harness deny | Prefer **harness** fast-fail; `[you]` platform is additive |
| P2.5 debt clear on green ship | **Agree — was under-weighted; now C S5** |
| P3.4 path-filter, P4 digest/readiness | **Agree useful; not P0** — Phase F unless readiness pairs cheaply with P0a |
| Golden force-sync | **Agree `[you]`** — never baseline fabricated ship; reconcile golden with pre-run-4 harness fixes only |

---

## 3. Phase A — Close the books on V5 (docs only)

**Done when:** formal reject recorded; oracle locked; implement signed in findings §9.

| Step | Action | Output |
|------|--------|--------|
| A1 | Formal accept-gate rejection (E.1) | `docs/V5-ACCEPT-GATE-REJECTION.md` |
| A2 | Lock `add()` oracle (P1.3) | §7 below / findings §9: **additive → qty 4** |
| A3 | Sign implement | Findings §9: authorize Phase B |
| A4 | Snapshot evidence | `tmp/v5-evidence/` if still on pod |
| A5 | Golden posture (E.2, E.3) | Operator: no sync from run-4; decide golden SHA separately |

Do **not** start scaffold coding until A3.

---

## 4. Phase B — P0 fabrication-proof (must ship before V6)

### 4.1 Design freeze (before code)

Write `docs/V6-ACCEPTANCE-GATE-DESIGN.md`:

| Rule | Requirement | Backlog |
|------|-------------|---------|
| R1 | Correction must not modify `acceptance.path` | P0.3 |
| R2 | Body proves live catalog (products array / marker) | P0.1 |
| R3 | No fail-open `catch` → 200 on acceptance handler | P0.2 |
| R4 | Gate: 200 + **array** (or `.products[]`) length > 0 — never object→1 | P0.4 |
| R5 | `deploy=true`: `CATALOG_ENDPOINT` in `k8s/` env before success | P0.5 / P1.2 |
| R6 | Mapper must not be `ExceptionMapper<Exception>`; no NotFound→503 | P0.5 / P1.1 |
| R7 | plan-lint A1 + acceptance tasked / handler exists before deploy | P3.3 |

Optional with P0a if small: replace acceptance `sleep 10` with rollout/readiness wait (**P4.2**).

### 4.2 Implement (instruments → code → instruments)

| PR | Contents | Backlog |
|----|----------|---------|
| **PR-B0** | plan-lint acceptance YAML comment-tolerant parse + instrument | A1 / R7 |
| **PR-P0a** | Supervisor gate R2/R4 (+ optional readiness wait P4.2) | P0.1, P0.4 |
| **PR-P0b** | Sensors R1/R3/R5; SHIPPING R5/R6 mandatory correction checklist | P0.2, P0.3, P0.5 |
| **PR-P0c** | M3 substance / static handler-before-deploy | P3.3 / R7 |

**Exit:** `instruments.sh` GREEN; design doc checked off.

---

## 5. Phase C — Orchestration / debt (P2)

| PR | Contents | Backlog |
|----|----------|---------|
| **PR-S1** | Foreground worker + residual kill/cap | P2.1 |
| **PR-S2** | Fast-deny heredocs / `python3 -c` | P2.2 |
| **PR-S3** | Verify-and-commit: no auto second opencode | P2.3 |
| **PR-S4** | Already-complete fast path | P2.4 |
| **PR-S5** | Do not `clear_debt` on ship if unresolved milestone/debt REDs remain | P2.5 |

Minimum before V6 launch: **S1 + S2**; S3–S5 strongly preferred.

---

## 6. Phase D — Authoring quality (P1.3/P1.4, P3.1–P3.2)

| PR | Contents | Backlog |
|----|----------|---------|
| **PR-Q1** | Ctor `@RestClient` wiring check | P1.4 |
| **PR-Q2** | BRIEF/SEQUENCING: S04 additive oracle; S05 JAX-RS; STORY_SCOPE allowlist | P1.3, P3.1, P3.2 |
| **PR-Q3** | Decisive target-trace tokens (cart §7) | P3.1 |
| **PR-A1** | Optional Tier A guides | O.1 |

---

## 7. Phase E — V6 fresh e2e (lead-driven)

### Preconditions

- [ ] Phase A complete  
- [ ] Phase B P0 merged + synced into run tree  
- [ ] Phase C S1–S2 minimum  
- [ ] `load_env` + `check_oc_logged_in`; `RHOAI_EXPECTED_API_SERVER`  
- [ ] New/wiped app — **not** run-4 HEAD  
- [ ] In-cluster catalog URL known  
- [ ] Instruments GREEN  
- [ ] Golden decision (E.3) settled by `[you]`  

### Diligence bar

| Gate | Pass |
|------|------|
| M1–M3 | Acceptance.path tasked; A1 lint holds |
| §7 | 404 / 400 / narrow mapper / CHMap / add→**qty 4** |
| Ship | Catalog-backed acceptance; k8s env; R1–R6; no fabrication |
| Debt | Unresolved RED must not be wiped by “green ship” |

Run log: `docs/V6-RUN-LOG.md` from launch.

---

## 8. Phase F — Post-V6 / parallel if capacity

| Item | Backlog |
|------|---------|
| Pipeline path-filter for docs-only pushes | P3.4 |
| Digest-pin Deployment image | P4.1 |
| Readiness wait if not landed in P0a | P4.2 |
| Platform fail-fast deny | E.4 `[you]` |
| Tier A guides if deferred | O.1 |

---

## 9. Decision checklist (operator sign-off)

- [x] Reject V5/run-4 ship; exclude from golden (E.1, E.2) — [`V5-ACCEPT-GATE-REJECTION.md`](V5-ACCEPT-GATE-REJECTION.md)  
- [x] `add()` oracle = **additive → quantity 4** (P1.3)  
- [x] Authorize Phase B P0 before any re-run — operator “let’s start” 2026-07-29  
- [x] Authorize Phase C S1–S2 before/with V6 — implemented in scaffold  
- [x] Golden sync: harness scaffold only via bootstrap — **never** run-4 app HEAD (E.3)  
- [ ] V6 = new/wiped app — create after golden push (name: `coolstore-cart-v6` unless overridden)  
- [x] Tier A / P3.4 / P4.1: included in this harness pass  
- [x] Platform deny-in-seconds (E.4) — Dev Spaces Hermes config rewrite |

---

## 10. Progress (2026-07-29)

| Deliverable | Status |
|-------------|--------|
| A1 rejection doc | ✅ [`V5-ACCEPT-GATE-REJECTION.md`](V5-ACCEPT-GATE-REJECTION.md) |
| A2 add() oracle = qty 4 | ✅ locked |
| B design freeze | ✅ [`V6-ACCEPTANCE-GATE-DESIGN.md`](V6-ACCEPTANCE-GATE-DESIGN.md) |
| PR-B0 plan-lint R7 | ✅ + instruments |
| PR-P0a gate R2/R4 + readiness wait + R1 stamp | ✅ `supervisor.sh` + `acceptance-products.py` |
| PR-P0b sensors R3/R5/R6 + SHIPPING checklist | ✅ |
| PR-P0c handler-before-deploy + acceptance substance | ✅ `acceptance_path_handler` + plan-lint ceremonial reject |
| PR-S1 worker wait cap 900s | ✅ `WORKER_WAIT_CAP` |
| PR-S2 denied-shapes + EXECUTION/SKILL + Hermes `approvals` rewrite | ✅ E.4 in `maas-api-key-provisioning.yaml` |
| PR-S3 verify-and-commit on orphan (no auto second opencode) | ✅ |
| PR-S4 already-complete fast path | ✅ `try_already_complete` |
| PR-S5 do not clear debt with unresolved `##` | ✅ |
| PR-Q1 ctor `@RestClient` wiring | ✅ |
| PR-Q2 BRIEF/SEQUENCING oracles + STORY_SCOPE | ✅ (Tier A session) |
| PR-Q3 decisive add()→qty 4 in profile-rubric / plan-lint TARGET | ✅ |
| PR-A1 Tier A MAPPINGS/OpenCode/AGENTS | ✅ |
| P3.4 path-filter (docs-only skip) | ✅ CEL on scaffolded + inventory push triggers |
| P4.1 digest/revision pin deploy | ✅ pipeline IMAGE=`:$(revision)`; no force-restart |
| Instruments | ✅ **89/89** passed |
| **New project / workspace** | Next: RHDH **Application migration** template → `coolstore-cart-v6` (legacy = coolstore-cart-legacy). Do not reuse run-4. |

---

## 11. When to create a new project and workspace

Harness + platform deny + scaffold golden sync are lead-executed. Create V6 via
RHDH self-service (or equivalent scaffolder API) as **`coolstore-cart-v6`**
from `coolstore-cart-legacy` — never from contaminated `coolstore-cart-round3`.
