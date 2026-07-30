# V8 quality-advance gate

Living log for Stage 080 Track B. Agents must append a review before M5 ship,
story-complete, or next-story start. See `.agents/rules/stage-080-track-b.md`
and `.agents/skills/stage-080-quality-advance/SKILL.md`.

Verdicts: `ADVANCE` | `HOLD` | `ABORT`.

---

## 2026-07-30 — S02 model-harvest (pre-ship)

- **Verdict:** HOLD
- **HEAD:** `17b302c` M5 evaluate: Migration evaluation complete…
- **What shipped (substance):**
  - Four HARVEST models under `com.demo.model`: `Product`, `Promotion`,
    `ShoppingCart`, `ShoppingCartItem` (package rename from legacy).
  - S01 complete; S02 ledger not yet `complete`.
  - Plan trimmed: T-005/T-006 service/boundary tests removed (defer to service
    stories) after placeholder false-green abort.
  - Harness polish landed: O-T6b, G-PLACE, O-RESUME, PLANNING/SEQUENCING
    feedforward; golden scaffold re-pushed.
- **Weak / dishonest:**
  - Story brief is **"HARVEST with characterization"** and calls models god
    nodes that must be characterized before dependents — but **`src/test` is
    empty**. Dropping service tests was correct; dropping *all* characterization
    was not.
  - M5 evaluate commit claims "factory preflight green" while ship immediately
    hit **preflight RED**: new-code coverage **0%** on all four model classes
    (Product 22, Promotion 13, ShoppingCart 42, ShoppingCartItem 16 uncovered
    lines). Evaluate messaging overstated readiness.
  - Racing resume→M5 after abort skipped substance review (process failure;
    this gate exists to stop that).
- **Sensor/preflight:** harvest fidelity GREEN; task sensor GREEN (no tests);
  ship preflight RED on coverage (≥80% required).
- **Banked:**
  - G-PLACE ✅ (already) — placeholder tests
  - O-T6b ✅ (already) — mechan-commit `.hermes/` sweep
  - **S-CHAR** ⬜ — model-harvest stories must keep *model-level*
    characterization (or equivalent coverage) when the brief requires it;
    deferring service tests must not delete the characterization obligation
  - **L-M5e** ⬜ — M5 evaluate must not claim preflight/factory green when
    ship preflight has not passed (or must re-run the same preflight bar)
- **Next action:** Keep harness stopped. Add real model unit tests (constructors,
  accessors, cart/item math as applicable — no G-PLACE stubs) until coverage
  gate can pass; implement S-CHAR + L-M5e feedforward; re-run this gate; only
  then resume M5 ship. Do **not** start S03.

---

## 2026-07-30 — S02 model-harvest (post HOLD fixes)

- **Verdict:** ADVANCE
- **HEAD:** `929f274` T-005: Model characterization unit tests (S02 HOLD / S-CHAR)
- **What shipped (substance):**
  - Prior four models retained.
  - Real JUnit model tests: `ProductTest`, `PromotionTest`, `ShoppingCartItemTest`,
    `ShoppingCartTest` (constructors/accessors, Serializable, cart add/remove/reset,
    additive quantity 2+2→4 on item) — no G-PLACE stubs.
  - Plan T-005 documents model-level characterization; service tests still deferred.
  - Harness: S-CHAR plan-lint + L-M5e evaluate/preflight honesty.
- **Weak / dishonest:** None material for S02 ship. Coverage was the blocker; now
  preflight GREEN. Evaluate commit `17b302c` still has an overstated message in
  history — accepted as historical; L-M5e prevents repeat.
- **Sensor/preflight:** `.hermes/harness/sensors.sh preflight` → **GREEN** on
  `929f274` (2026-07-30T05:53Z).
- **Banked:** S-CHAR ✅, L-M5e ✅ (implemented this HOLD cycle).
- **Next action:** Resume M5 ship only (do not skip quality ticks). After S02
  story-complete, run this gate again before S03.

---

## 2026-07-30 — V8 stop / V9 full wipe

- **Verdict:** ABORT (run boundary)
- **HEAD at stop:** V8 had reached S03 M3 after S02 factory push; not used as durability proof
- **Why:** S02 characterization was HOLD-loop human-written; polish landed mid-run — not a clean harness e2e
- **Wipe:** `coolstore-cart-service-v7` `main`+`golden` → `8c2102c` then harness sync `9a0b183` (+ hygiene); Sonar project deleted (204); workspace `/tmp` logs cleared
- **Next action:** Fresh **V9** Track B from clean tree; quality-advance after each story
