# Wave 4 → v4 change manifest (R3 / SC-1) — wave-3 paused / resume pending

**Purpose:** every readiness / architecture / review recommendation for the
petclinic-rest-v4 wave is either **UNDER-TEST** (landed and judged this run)
or **NOT-UNDER-TEST** (explicitly deferred with reason + parking target).
Silence is forbidden (SC-1).

**Companion artifacts:**
- Predictions (frozen): `docs/M3-ALL-PREDICTIONS-FROZEN.md`
- Polish bank: `docs/V10-FUTURE-IMPROVEMENTS.md` (`⬜` = open; `📋` = later wave)
- LRR: `scripts/track-b/restart-readiness.sh` (asserts this file is committed)

**Baseline commit for banked harness durableize:** `5fcab70` + O-M2429CAP + O-M2COMPOSEBOOK/O-LOGLINTRES (wave-3 resume)  
**Prior wave-1 freeze baseline:** `d623641` / LRR harden `36ea5c9` (superseded — wave died at M2)  
**Workspace under test:** `petclinic-rest-v4`  
**Re-frozen:** 2026-08-03T11:28:30Z (TIDY-3 / W4-142) after M2 SEQUENCE lint×2 FAIL  
**Wave-2 end:** 2026-08-03T12:35:34Z — clean SIGTERM after operator decision W4-146a (3 then 2)  
**Wave-3 pause:** 2026-08-03T14:11:15Z — SIGTERM at O-M2-429 **2/3** (operator proceed); resume-after `tmp/V10-WAVE3-RESUME-AFTER.txt`

### Wave-2 outcome (must attribute — platform, not plan-quality)

Wave-2 on `petclinic-rest-v4` **ended on MaaS quota exhaustion after 3
rate-limited M2 seats (71s / 838s / 30s)**; M2 attempt budget never spent;
roadmap-lint residual reduced **15 → 5** by `m2-compose` fill with **no
completing LLM seat**. Outer stopped via SIGTERM (O-TMPARCHIVE
`20260803T123534Z-bcc4b1d`); host evidence
`tmp/m2-wave2-quota-evidence-20260803T123437Z/` (roadmap + 6 briefs + seat
logs). A fourth seat had started post-backoff and was terminated with the
loop — not a lint failure.

This is a **platform outcome**, not a plan-quality outcome. Wave-1's
`M2 SEQUENCE failed its lint twice` and wave-2's quota stop must not be
conflated in later baselines.

| Gate | Live result on wave-2 |
|---|---|
| **O-M2-429** | ✅ proven 3×; attempt budget untouched after ~53m wall |
| **O-M2COMPOSE** | ✅ lint residual 15 → 12 → 5 with zero completing model seats |
| **O-MONSTART** | ✅ dual-monitor auto-started and stayed up |
| **O-M2RETRYINLINE**, **O-M2CORPUS** | landed; not exercised (no retry reached the prompt; no second corpus case) |
| **O-M2429CAP** | ✅ landed at wave-2 boundary (cap was the missing piece that livelocked) |
| M3-ALL, PAUSE-3, O-TASKMUTATE | **not reached** — unchanged from wave-1 |

### Wave-1 → wave-2 delta (historical)

Wave-1 on `petclinic-rest-v4` stopped at **M2 SEQUENCE failed its lint twice**
(app HEAD `10790d6`; M2 never committed). Harness gains that flew on wave-2:

| Gate | Commit / evidence |
|---|---|
| **O-M2COMPOSE** | `m2-compose.py` skeleton + wire (`5fcab70`) |
| **O-M2-429** / **O-ORCH429BACKOFF** | 429 not-spent + backoff (`5fcab70`) |
| **O-M2RETRYINLINE** | bounded lint inlined into M2 retry prompt (`5fcab70`) |
| **O-M2CORPUS** | known-RED fixture `tests/fixtures/m2-corpus/v4-m2-lintx2-10790d6/` (`5fcab70`) |
| **O-MONSTART** | preflight `--start` wires dual-monitor; LRR SC-3 (`5fcab70`) |

Prediction honesty: row 1 (time-to-first-plan-defect) **MET on substance** via
wave-1 M2-gate stop; rows 2+ **not reached** on wave-1 or wave-2 — see frozen
prediction table.

Operator veto surface: the **NOT-UNDER-TEST** list only. Approving GO means
accepting those deferrals for this wave.

---

## UNDER-TEST

These are in the flying harness and will be judged on the **wave-3 resume**
v4 run (L3 live) against the re-frozen prediction table and honesty gates.

| ID / theme | What is under test | Evidence / gate |
|---|---|---|
| R1 supply chain | Semantic hermes parity + golden three-way (O-HERMESPREFLIGHT, O-HERMESPARITYSEM, O-GOLDENFRESH) | LRR + preflight; wake#12 tar-sync GREEN |
| R2 LRR | `restart-readiness.sh` GO/NO-GO before start | this protocol |
| R3 this manifest | Committed UNDER/NOT-UNDER lists (wave-3 pause re-freeze) | LRR asserts file |
| R5 seat economics | O-SEATBUDGET + O-STORYKIND + O-SPECREIMPL | roadmap/plan lint + freeze |
| **M2 path (new)** | O-M2COMPOSE + **O-M2COMPOSEBOOK** + O-M2-429 + O-M2429CAP + O-ORCH429BACKOFF + O-M2RETRYINLINE + O-M2CORPUS + O-MONSTART | instruments 515/515; offline probe residual **8→0**; L3 on resume |
| M3-ALL path | Whole-set plan before any M4; operator gate; predictions_fp bind | `m3-all-lint.sh`, outer two-pass, `M3_ALL=1`, `M3_ALL_OPERATOR_AUTO` unset |
| **O-M3ALLSHA** (W4R7 mid-run) | `freeze-predictions` / operator-gate must not call bare `shasum` (absent on UBI) — portable `sha256sum`/`shasum`/python | `m3-all-lint.sh` `_m3all_sha256_*`; live fail `/tmp/m3-all-predictions.txt` |
| Port / Oracle honesty | O-PORTREIMPL, O-PORTDERIVE, O-ORACLEDERIVE, O-INFERABSENT, O-M3PRESERVEDAO, O-OWNSTAGE, O-SPRINGRESIDUE, O-SDJPA-SKIP | plan-lint + corpus |
| Plan / exec / m2 corpus (seeded) | O-PLANCORPUS + O-EXECCORPUS + O-M2CORPUS (v4 lint×2 known-RED) | corpus gates + preflight |
| Watchability P1 | O-LOGSTORY, O-LOGBRIEF, O-LOGEPILOG, O-EVIDLIVE, **O-LOGLINTRES** | instruments + live window (residual on compose/gate) |
| Guard inventory seed | O-GUARDMANIFEST seed (`guard-manifest.sh --check`) | instrument guardmanifest-ok |
| Defaults honesty | O-DEFAULTAUDIT, O-DEFAULTRG | `defaults-inventory.sh --check` |
| Prediction thresholds | Re-frozen table (row-1 latency; Port/Oracle; seats; ship) — wave-1 rows 2+ explicitly not-reached | `docs/M3-ALL-PREDICTIONS-FROZEN.md` |

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
| **Specimen wipe / outer start** | Wave-1 RED tree + `outer-loop-done` still on pod until operator GO + wipe recipe | Operator GO → wipe → preflight `--start` |

---

## Operator GO meaning

1. LRR prints `LRR_VERDICT=GO` with this manifest committed (wave-2 freeze).
2. Opus/Claude has reviewed NOT-UNDER-TEST (or operator accepts without further review).
3. Operator triggers wave start on `petclinic-rest-v4` with `M3_ALL=1` and
   `M3_ALL_OPERATOR_AUTO` unset (after wipe of failed-wave markers/tree as needed).
4. Mid-wave discoveries bank to the boundary (amend-rules excepted); change
   budget otherwise zero until the next restart.
