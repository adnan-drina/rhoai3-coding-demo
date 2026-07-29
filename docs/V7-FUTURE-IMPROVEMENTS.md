# V7 — future improvements (non-blocking bank)

**Purpose:** capture **less-critical** defects and UX gaps observed during
`coolstore-cart-service-v7` (and carry-forwards from V6) so we harden the
harness methodically **without** aborting a healthy run for polish.

**Policy unchanged:** P0/correctness that would ship a broken service →
**abort, fix, rerun**. Everything below is **bank → implement between runs**
(or after V7 ship) unless it escalates.

**Related:** [`V6-RUN-FINDINGS.md`](V6-RUN-FINDINGS.md) (V6 abort P0s — mostly
landed), [`V6-OUTER-LOOP-LOGGING-NOTES.md`](V6-OUTER-LOOP-LOGGING-NOTES.md),
[`V6-LEAD-PLAN.md`](V6-LEAD-PLAN.md).

---

## Logging / demo UX

| ID | Observation | Suggested improvement |
|----|-------------|------------------------|
| L-T1 | ✅ Task codes+titles mirrored to `outer-loop.log` (landed mid-V7; active from S02 supervisor) | Done — verify on S02+ |
| L-A1 | ✅ TASK lines state actor (`Actor: … Qwen …` / MiniMax escalation) — landed with V7 WORKER_FIRST | Done — verify on S02+ |
| L-R1 | MiniMax **429 / token-limit waits** invisible in outer-loop narrative | Parse Hermes session log or rate-limit stderr; one line: `… waiting on MiniMax rate limit (Ns)` |
| L-H1 | Heartbeat subshell appears in `ps` as a second `outer-loop.sh` (PPID=parent) | Rename heartbeat process (`bash -c '…'`) or exclude from single-instance guard; avoid false “another outer-loop” refusals |
| L-N1 | `/tmp/outer-loop-nohup.log` stays empty; README still mentions both | Document single sink (`outer-loop.log`) or tee nohup |
| L-P1 | PLAIN ascii mode (`OUTER_LOOP_PLAIN=1`) for terminals that mangle `▶✓` | Optional; low priority |
| L-D1 | Richer END deliverables (file lists, finding counts) still thin on some phases | Enumerate key paths on M1/M2 END as in logging notes §3 |

---

## Orchestration / efficiency (not false-green)

| ID | Observation | Suggested improvement |
|----|-------------|------------------------|
| O-T6 | V7 S01 **T-006** (full package rename) burned attempt 1 without commit while `com.demo.*` tree already existed untracked; Continu(e) slow | Prefer harvest-script rewrite tasks + already-complete when target tree matches; or auto verify-and-commit when dirty tree + task sensor GREEN |
| O-AC | Hermes sessions still write prose `ALREADY COMPLETE` commits (T-004) **outside** the strict probe — dual paths | Route “already satisfied” only through `already-complete.py`; session should not invent skip commits |
| O-B1 | ✅ Rewrite+infer coding → OpenCode/Qwen first (`WORKER_FIRST`); MiniMax escalation only — landed mid-V7 | Done — verify S02+; optional next: script-only harvest without any LLM |
| O-CTX | Large context re-sends amplify MiniMax rate limits / wall time | Tighter session packets; avoid full-file re-reads in orch prompts |
| O-DRV | Local Cursor driver/monitor loops die if shell session ends | Document restart; or systemd/launchd — ops only |

---

## Story design / plan quality

| ID | Observation | Suggested improvement |
|----|-------------|------------------------|
| S-LC | S01 launched with `later-classes=13` and **later-story** types (`CartEndpoint`, full service/impl set) already under `src/` mid-S01 | Prefer staging-only until owning story; strengthen scope_enforce messaging in outer-loop when reverts fire |
| S-RN | Broad “rename entire package tree” as one S01 rewrite overlaps harvest-from-staging (mechanical, should be scripted) | M3/SEQUENCING: package rename = harvest script tasks per path, not one mega-infer/rewrite |
| S-FND | Empty `- findings:` still a footgun (V6 M2 bounce); logging improved, preflight could be stricter | Roadmap preflight: “findings list empty” before full lint |
| S-SOFT | Soft “prepare for…” / verification-only rewrite tasks still appear | Prefer concrete file diffs or fold into real POM tasks (V6 note) |

---

## Sensors / gates (hardening, not V7 abort)

| ID | Observation | Suggested improvement |
|----|-------------|------------------------|
| G-FID | Fidelity GREEN while large later-story surface already present — fidelity doesn’t mean “scope clean” | Optional scope-drift summary line on milestone GREEN |
| G-AC2 | Ceremonial acceptance static reject landed; ship-time products[] still the real bar | Keep; add instrument for happy-path products[] handler shape if missing |
| G-OK | V7 `AcceptanceEndpoint` returns plain `"OK"` (TEXT) — **static sensor does not catch it** (only status-Map markers). S04 deploy ship **does** fail it (`acceptance-products` → 0). Gap: non-deploy stories can story-gate-pass with `"OK"`. | Static reject: acceptance handler whose return type/body is String/`"OK"` / no catalog fetch when path matches `acceptance.path` |
| G-FAKE | Ship gate only requires `products.length > 0`, not live catalog provenance | Stronger check (marker from real CATALOG_ENDPOINT / non-canned) if correction invents a hardcoded array |
| G-PKG | Wrong-prefix `com.demo.coolstore` reject landed | Watch V7 for any other partial-rename patterns (e.g. `com.demo.redhat`) |

---

## Process / repo hygiene

| ID | Observation | Suggested improvement |
|----|-------------|------------------------|
| P-GIT | Harness fixes were golden-synced from **dirty working tree** before commit — fine for sole owner; easy to forget | Habit: commit scaffold → then `bootstrap-scaffold-repos.sh` |
| P-LOG | `docs/V5-RUN-POLL.log` and similar poll artifacts left untracked | Keep out of git; add to `.gitignore` if they recur under `docs/` |
| P-MON | Autonomous monitor must not substitute for mid-run **quality** abort judgment | Keep dual diligence: progress + artifact package/acceptance checks |

---

## How to use this file

1. After each V7 story ship (or abort), append rows with evidence (timestamp, log snippet, commit).
2. Before the next partial rerun, promote any row that became ship-blocking into P0 work.
3. Do **not** weaken sensors to clear these — fix feedforward or probes.

**V7 live notes:**
- ~20:24 UTC: S01 T-006 Continu(e) after attempt-1 no-commit.
- ~20:38 UTC: T-006 **attempts exhausted** (checkpoint `ac756e7`); T-007 committed then **milestone RED** → sensor-fix (test compile: `ShoppingCart.getShoppingCartId()` missing). `AcceptanceEndpoint` returns plain `"OK"` (not products[] / not status-map) — extend ceremonial reject beyond status-Map markers. `debt.md` empty while supervisor logged T-006 exhausted; `run-log.md` marks T-006 COMPLETE — **ledger honesty** gap (O-AC / debt sync).
