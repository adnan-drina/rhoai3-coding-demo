# V6 run findings — improvements (not a green bill of health)

**Run:** `coolstore-cart-service-v6` · cluster `cluster-kjbwr` · started ~2026-07-29 16:20 UTC  
**Status:** **ABORTED mid-S03** (~19:30 UTC) — do not resume this tree.  
**Policy:** fix harness + golden sync + new RHDH Application migration (partial
runs that harden the process beat one completed broken service).

**Harness fixes landed after abort (instruments 94/94):**
- P2.4 strict `already-complete.py` (no Convert/Port verb false greens)
- package + plan-lint reject `com.demo.coolstore` when `targetPackage=com.demo`
- ceremonial status-map acceptance static reject
- outer-loop demo logging (Actor / START-END / heartbeats)

Related: [`V6-OUTER-LOOP-LOGGING-NOTES.md`](V6-OUTER-LOOP-LOGGING-NOTES.md)
(demo log UX).

---

## P0 / high — correctness

### 1. Wrong target package: `com.demo.coolstore` vs `com.demo`

`migration.yaml` says `targetPackage: com.demo`, and models/interfaces live
under `com.demo.*`. Pricing services were written as:

- `com.demo.coolstore.service.PromoService`
- `com.demo.coolstore.service.ShippingService`
- `com.demo.coolstore.service.ShoppingCartServiceImpl`

while `ShoppingCartService` / `CatalogService` remain `com.demo.service`.

S03 OpenCode packet explicitly instructed
`com.redhat.coolstore → com.demo.coolstore` — **feedforward bug** (brief/spec
and/or worker packet), not just a typo in one file.

**Improve:** plan-lint / scope sensor must reject any `src/main` type whose
package is not under `targetPackage`; harvest script + SEQUENCING/BRIEF must
never invent `targetPackage + ".coolstore"`. M3 must cite `migration.yaml`
`targetPackage` literally in every file mapping.

### 2. Ceremonial acceptance endpoint

`AcceptanceEndpoint` serves `/api/cart/acceptance-check` but returns a status
map (`service_interfaces_ready` / story id), **not** a real catalog
`products[]` / live fetch. V6 P0 was built to stop this at deploy ship.

**Improve:** keep non-deploy stories from claiming “acceptance done”; S04
deploy gate + `acceptance-products.py` must remain hard. Consider plan-lint
rejecting acceptance tasks that specify TEXT_PLAIN / status-map shapes when
`acceptance.path` is the cart check.

### 3. P2.4 “ALREADY COMPLETE” false greens

Multiple tasks skipped with messages like:

- `CATALOG_ENDPOINT already present`
- `Convert already absent` / `Port already absent`

including S01 T-016/T-018 and S03 T-001–T-003 — while the real CDI conversion
work was incomplete or misplaced under the wrong package.

**Improve:** already-complete probes must match **task acceptance** (class
exists in **correct** package with expected annotations/state), not a loose
string/path heuristic. Log the probe evidence in supervisor.log.

---

## P1 — process / model routing honesty

### 4. Rewrite path never uses Qwen (by design today)

Mechanical rewrite batches are Hermes/MiniMax “apply directly”; OpenCode/Qwen
only for infer. Demo narrative (“Qwen is the coder”) overstates GPU involvement
on foundation stories.

**Improve:** outer-loop/supervisor **Actor:** lines (see logging notes);
optionally document rewrite-on-orchestrator in Stage 080 README so demos don’t
imply Qwen did POM/harvest work.

### 5. MiniMax rate limits dominate wall time

M2 a1 alone: long session + many **429 token-limit** waits (~400k/min portal
cap). Large context re-sends amplify cost.

**Improve:** surface 429 waits in outer-loop log; consider tighter session
context / fewer full-file re-reads; longer-term route orch through governed
gateway when RHOAI streaming allows.

### 6. Outer-loop log inadequate for demos

Bare `session … rc=0` then lint RED; no phase descriptions; no model actor;
kantra spam; no heartbeats. Captured in detail in
`V6-OUTER-LOOP-LOGGING-NOTES.md` (L0–L7 + Actor requirement).

---

## P2 — planning / lint / roadmap

### 7. M2 empty `findings:` eats next fields

Empty `- findings:` made lint report `depends:` / `S01` as rule ids; required
bounce. Preflight should say “S02 findings list empty.”

### 8. Soft “prepare for…” rewrite tasks

S01 T-013–T-015 style tasks are thin; one caused micrometer vs smallrye-metrics
conflict (fixed in sensor-fix). Prefer concrete file diffs or fold into real
POM tasks.

### 9. Roadmap dual-ownership / recipe-owned rules

M2 a1 failed exclusive ownership + recipe-executed `javax-to-jakarta` on a
story. Feedforward in SEQUENCING.md already says this; lint messages should
stay humanized in the outer-loop frame.

### 10. S02 `findings=none` at supervisor launch

Outer-loop logged S02 with `findings=none` after a2 — verify parse-roadmap /
empty-findings convention doesn’t drop real ownership for later plan-lint
scopes.

---

## What went well (keep)

- M1 profile first-try rubric-green; harvest fidelity green on models.
- M2 recovered on a2; story loop S01→S02 completed with pipeline green
  (non-deploy).
- Sensor-fix recovered micrometer/smallrye conflict.
- First real OpenCode→Qwen dispatch observed on S03 T-004 (infer).
- V6 P0 acceptance gate not yet the merge authority for S01/S02 (correct —
  deploy=false); must prove itself on S04.

---

## Suggested follow-up work (post-run or mid-run if S03 fails)

| ID | Action |
|----|--------|
| F1 | Fix package to `com.demo.service` (or fail S03 hard) before S04 |
| F2 | Harden already-complete probes + package==targetPackage sensor |
| F3 | Implement outer-loop logging notes (Actor + START/END deliverables) |
| F4 | Plan-lint: forbid wrong target package prefix in tasks/spec paths |
| F5 | README honesty: rewrite=orchestrator, infer=Qwen worker |
| F6 | Capture this file’s open items into BACKLOG when run finishes |

---

## Evidence pointers (workspace)

- `/tmp/outer-loop.log`, `/tmp/supervisor.log`
- `migration/story-state.csv`, `migration/architecture-profile.md`, briefs
- Tree: `src/main/java/com/demo/coolstore/service/*` vs `com/demo/service/*`
- OpenCode packet on S03 T-004 (live) named `com.demo.coolstore`
