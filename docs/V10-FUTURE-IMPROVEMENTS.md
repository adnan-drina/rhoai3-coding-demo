# V10 — future improvements bank

**Purpose:** bank harness gaps for Stage 080 after `stage-080-baseline`.
**⬜ = due before the next migration run** (blocks `v9-bank-gate.sh all`).
**📋 = later wave** (roadmap only — does not block preflight; see
`tmp/KAI-HARNESS-IMPROVEMENTS.md` §4). Mark ✅ when instruments prove the fix.

**Plan of record:** `tmp/KAI-HARNESS-IMPROVEMENTS.md`.
**Prior bank:** `tmp/docs-archive/V7-FUTURE-IMPROVEMENTS.md` (V7–V9 closed).

Default `BANK_DOC` is this file (`scripts/track-b/lib-quality-gates.sh`).

---

## KAI Wave 1 — shipped + follow-up defects

| ID | Status | Notes |
|----|--------|-------|
| K2 | ✅ | Analysis evidence in `task-packet.py` (caps + MiniMax escalation packet). |
| K1 | ✅ | Incident-file ownership lint + `Absorbs:` + package map + PLANNING.md. |
| K3 | ✅ | Non-mandatory decision table + roadmap adopt/defer (reason). |
| K1-OWN | ✅ | [HONESTY] Fixed 2026-07-30: ownership from Target/Absorbs/Owns only; OOS / “owned by T-” lines excluded; instruments. |
| K1-CONF | ✅ | Fixed with K1-OWN: OOS disclaimer no longer manufactures incident-conflict. |
| K2-RR | ✅ | Fixed 2026-07-30: round-robin one incident per matched Findings rule, then backfill to cap. |
| K2-MATCH | ✅ | Fixed 2026-07-30: exact → rule-id-shaped prefix (`-` required) → guarded substring; bare `springboot` no longer matches. |
| K2-CAP | ✅ | Fixed 2026-07-30: `MAX_EVIDENCE_CONTENT_CHARS = 6×400` combined message+code budget. |

## KAI Wave 2 — objective completion (later)

| ID | Status | Notes |
|----|--------|-------|
| K5 | 📋 | Native `findings` sensor — milestone + M5 only until kantra cost measured. |
| K6 | 📋 | Findings oracle for `already-complete.py` / `escw-eligible.py`. |
| K7 | 📋 | Mechanical failure-diff for sfix / O-SFIXSCOPE honesty. |

## KAI Wave 3 — force-multipliers (later)

| ID | Status | Notes |
|----|--------|-------|
| K8 | 📋 | `verify-dep.py` Maven Central advisory (WARN, never hard RED). |
| K9 | 📋 | `migration/discovered.md` forward-looking scope channel (not a second debt ledger). |
| K11 | 📋 | Per-rule outcome ledger in supervisor events / run report. |

## KAI Wave 4 — learning & critic (later)

| ID | Status | Notes |
|----|--------|-------|
| K10 | 📋 | Solved-example hints keyed by rule id (after K11; A/B before default-on). |
| K12 | 📋 | Adversarial refute at MiniMax escalation + pre-push ship only. |
| K4 | 📋 | Contract-as-rules expansion from `migration.yaml` (incremental). |
