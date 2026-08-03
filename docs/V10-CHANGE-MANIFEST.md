# Wave 4 → v4 change manifest (R3 / SC-1)

**Purpose:** every readiness / architecture / review recommendation for the
petclinic-rest-v4 wave is either **UNDER-TEST** (landed and judged this run)
or **NOT-UNDER-TEST** (explicitly deferred with reason + parking target).
Silence is forbidden (SC-1).

**Companion artifacts:**
- Predictions (frozen): `docs/M3-ALL-PREDICTIONS-FROZEN.md`
- Polish bank: `docs/V10-FUTURE-IMPROVEMENTS.md` (`⬜` = open; `📋` = later wave)
- LRR: `scripts/track-b/restart-readiness.sh` (asserts this file is committed)

**Baseline commit for banked harness durableize:** `d623641`  
**LRR harden follow-up:** `36ea5c9`  
**Workspace under test:** `petclinic-rest-v4`

Operator veto surface: the **NOT-UNDER-TEST** list only. Approving GO means
accepting those deferrals for this wave.

---

## UNDER-TEST

These are in the flying harness and will be judged on the v4 wave (L3 live)
against the frozen prediction table and honesty gates.

| ID / theme | What is under test | Evidence / gate |
|---|---|---|
| R1 supply chain | Semantic hermes parity + golden three-way (O-HERMESPREFLIGHT, O-HERMESPARITYSEM, O-GOLDENFRESH) | LRR + preflight |
| R2 LRR | `restart-readiness.sh` GO/NO-GO before start | this protocol |
| R3 this manifest | Committed UNDER/NOT-UNDER lists | LRR asserts file |
| R5 seat economics | O-SEATBUDGET + O-STORYKIND + O-SPECREIMPL | roadmap/plan lint + freeze |
| M3-ALL path | Whole-set plan before any M4; operator gate; predictions_fp bind | `m3-all-lint.sh`, outer two-pass, `M3_ALL=1`, `M3_ALL_OPERATOR_AUTO` unset |
| Port / Oracle honesty | O-PORTREIMPL, O-PORTDERIVE, O-ORACLEDERIVE, O-INFERABSENT, O-M3PRESERVEDAO, O-OWNSTAGE, O-SPRINGRESIDUE, O-SDJPA-SKIP | plan-lint + corpus |
| Plan / exec corpus (seeded) | O-PLANCORPUS (11 cases) + O-EXECCORPUS (2 cases: sfixnodelta, escalation-cause) | `v10-plan-corpus-gate.sh`, `v10-exec-corpus-gate.sh` |
| Watchability P1 | O-LOGSTORY, O-LOGBRIEF, O-LOGEPILOG, O-EVIDLIVE | instruments + live window |
| Guard inventory seed | O-GUARDMANIFEST seed (`guard-manifest.sh --check`) | instrument guardmanifest-ok |
| Defaults honesty | O-DEFAULTAUDIT, O-DEFAULTRG | `defaults-inventory.sh --check` |
| Prediction thresholds | Frozen table rows (time-to-first-plan-defect ≤30m, Port/Oracle coverage, seat bounds, S03-equivalent ship) | `docs/M3-ALL-PREDICTIONS-FROZEN.md` |

Open bank `⬜` rows that are **honesty-blocking** remain gated by
`v9-bank-gate.sh honesty` / preflight and are under test if they fire mid-wave
(fail closed — bank + HOLD). Non-honesty `⬜` polish is parked below unless a
row is promoted mid-wave into UNDER-TEST via amend-rules.

---

## NOT-UNDER-TEST

Deferred for this wave. Operator may veto any line before GO.

| ID / theme | Reason | Parking target |
|---|---|---|
| **R4** exec-corpus per-sfix coverage (`O-SFIXNAMING`, `O-SFIXPATHS`, `O-SFIX-K7-vs-sonar` replay cases) | Seeded corpus is 2/N (sfixnodelta + escalation-cause). **Deferred by operator choice at GO** — v3 PVC scrapped / not used for the v4 flight path; wave runs only on `petclinic-rest-v4`. Gate GREEN on the two seeded cases remains UNDER-TEST. | Next boundary from host archives or future specimens; keep `O-SFIX-K7-vs-sonar` ⬜ |
| **R6** O-LOGPROG / O-LOGRUN | Banked `📋` follow-on; P1 log identity/brief/epilog already UNDER-TEST. Positional heartbeat + run line not required to start. | Next polish wave (`docs/V10-FUTURE-IMPROVEMENTS.md` 📋) |
| **R7** full guard-manifest build / L2–L3 completeness program | Seed + `--check` UNDER-TEST; exhaustive Guard×Mechanism×Verification build may trail. | Predicate / guard program after v4 story-1 |
| **R8** A-1 work-inventory union | Spine still findings-centric; schema/data-init/test-strategy partition not landed. Risk accepted: known v3 gap class may recur until inventory lands. | ADR-9 / post-v4 architecture land |
| **R8** A-2 missing M1 gates (classification / staging / join completeness) | Not wired as fail-closed M1 exits this wave. PAUSE-3 (M3-ALL operator gate) remains. | Next harness wave; consider PAUSE-1 markers |
| **R8** A-3 M2 computed-dependency graph check | Roadmap still uses declared depends; computed-graph lint not landed. | Next harness wave; PAUSE-2 |
| **R9** roll to dedicated v4 review file | Architect seeds at GO; WAVE4 doc remains active Implementing-note trail. Gate log opened as `docs/V10-QUALITY-GATE.md`; monitor trail as `tmp/V10-V4-MONITOR.md`. | At operator GO (Claude R9) — optional rename/seed of review file |
| **ARCH-C2** `time_to_first_write` in `.hermes/harness/` | Parser remains host-side (`v10-monitor-seat-enrich.py`); exec-corpus does not require in-harness promotion to start. | Pair with R4 corpus expansion |
| **PAUSE-1 / PAUSE-2** (ADR-11) | Only PAUSE-3 (M3-ALL OPERATOR_GATE) is fail-closed this wave. | Land markers + review-doc entries next wave |
| **O-UXLOG-*** 📋 set | UX polish; not honesty-blocking. | Later wave (📋) |
| **Non-honesty bank ⬜** (remainder of `docs/V10-FUTURE-IMPROVEMENTS.md`) | Large polish backlog; preflight `honesty` subset still blocks start. Full `v9-bank-gate.sh all` is not a GO requirement. | Implement opportunistically; promote to UNDER-TEST if a defect proves wave-blocking |

---

## Operator GO meaning

1. LRR prints `LRR_VERDICT=GO` with this manifest committed.
2. Opus/Claude has reviewed NOT-UNDER-TEST (or operator accepts without further review).
3. Operator triggers wave start on `petclinic-rest-v4` with `M3_ALL=1` and
   `M3_ALL_OPERATOR_AUTO` unset.
4. Mid-wave discoveries bank to the boundary (amend-rules excepted); change
   budget otherwise zero until the next restart.
