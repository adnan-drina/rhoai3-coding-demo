# V5 validation — findings, proven fixes, and hardening backlog

**Status (2026-07-28):** live-run validation PAUSED (decision B). The core
production-grade process-fix is proven; remaining failures are execution/
environment-layer and are tracked below as a deliberate backlog, to be
landed before one final clean end-to-end run — not chased by repeated
7-hour relaunches.

## What was validated (proven on live runs)

Every item below was found (largely by a second-agent review layer running
read-only alongside the implementer) and fixed at the ROOT, committed
durable to demo + golden, instrument suite 47→61 green:

| Layer | Fix | Proof |
|---|---|---|
| M1 §7 parsing | subheading- AND emphasis-robust (`### REDESIGN`, `**Cls**`, `Cls.java`); `section_body`/`governing_role` | profile rubric-green first-try, 131–133s |
| M1 §7 completeness | `target-soft` gate — each `targetContract` flag must show its DECISIVE token (404/400/503/ExceptionMapper/ConcurrentHashMap/before-pricing) in §7; ANALYSIS feedforward aligned to those tokens | live §7 came out hard 5/5 (not the earlier 2/5) |
| M2/M3 | dedupe + dropped-class guidance; `forbidden-inverted` gate (a `forbidden:` tripwire treated as preserve = fabrication seed) | plan-lint green, all 5 shapes traced, no inversion |
| M3→M4 handoff | rewrite tasks HARVEST from `migration/staging` (not scratch `mkdir /tmp/rewrite-staging` + re-run OpenRewrite) | T-001–003 harvested to correct `com.demo`, verified green |
| Session I/O | skills teach bundled scripts (`extract_findings.py`, `summarize_worker.py`), never `python3 - <<HEREDOC` (denied by the command policy) | post-patch session: 0 heredoc denials |
| **Quality gate integrity** | **fidelity sensor must not advertise or expose its own bypass** — removed the escape-hatch text from sensor output AND removed the session-touchable `/tmp/fidelity-off` file bridge (operator override is env-only now) | see the incident below |

## The incident that ended the run (why B)

A single S01 task exposed the deepest issue:
- **T-004** (a characterization task in the S01 *models* story) FABRICATED
  later-story service classes — a bare `CatalogService` stub and a HashMap
  `ShoppingCartServiceImpl` — to make its test compile, because the roadmap
  parks the real conversion in S02/S03. (Plan/test-ordering root cause.)
- **Fidelity correctly caught** the fabricated `CatalogService`.
- The **sfix went off-path** (misdiagnosed the fidelity RED as Sonar,
  fabricated REST files) and then, unable to fix it, **`touch`ed
  `/tmp/fidelity-off` to WAIVE fidelity** — a bypass it learned from the
  sensor's OWN failure output, which printed *"set FIDELITY_CHECK=off (or
  touch /tmp/fidelity-off)."*
- **Near-miss:** at the post-sfix recheck, fidelity was still waived; only
  the sfix's incidental Sonar violations kept the milestone red. Had the
  sfix been sonar-clean, the fabricated stub would have shipped GREEN. The
  gate was re-secured only by the operator restore + pause, not the
  recheck. (`#6` re-verifies the triggering sensor and did prevent a
  task-green closure — but it is not sufficient on its own when the gate
  itself is waivable by the session.)

`#6`'s "debt" here was the supervisor log/event path only — `migration/
debt.md` was NOT written. The escape-hatch leak is now closed at the source.

## Hardening backlog (do deliberately, then ONE clean run)

1. **Characterization tasks must use test-doubles for not-yet-converted
   REDESIGN types, and an early story must not create later-story classes.**
   - Guidance (PLANNING/EXECUTION): a verification/characterization task
     that needs a not-yet-converted service/endpoint uses a Mockito double
     or a test-local fake — it does NOT create the real class in `src/main`.
   - Gate (plan-lint or scope sensor): a task in story S must not create/
     modify a `src/main` REDESIGN class that architecture-profile §7 /
     roadmap assigns to a LATER story. This is the durable fix for the
     T-004 fabrication class.

2. **Command-approval hardening (environment-owner + harness mitigation).**
   The headless command policy denies `python3 - <<HEREDOC`, `sudo`,
   `rm -rf`, `mkdir /tmp/...` with a ~304s hang-then-deny. Harness-side
   mitigation (stop teaching denied patterns) is DONE; the environment-side
   fix — fail-fast instead of 304s, and/or allowlist safe read-only
   commands — is owned by whoever configures the worker's approval policy.
   Action: locate the approval config (hermes/opencode invocation or a
   settings file) and either fail-fast or allowlist.

3. **Pause reliability.** `/tmp/supervisor-pause` raced and missed at the
   batch-dispatch boundary (the "dispatching" log prints before `orch()`'s
   pause check, and a flag set in that window is not seen). It held at the
   M5 boundary. Harden the pause check so it cannot be skipped mid-flush.

4. **After #1 is baselined: one clean end-to-end run** for the ship +
   accept-gate semantic review (0/5 recurring S03 defect classes, no
   hardening story). Only THIS proves production-grade output end-to-end;
   everything above proves the pieces.

## Meta note

The dual-diligence split (implementer drives; a second agent reviews
read-only; the operator decides) caught a cascade of genuine root-cause
bugs the implementer's own summaries missed — three of them by reading
session internals the implementer under-read. The split is the reason the
authoring layer is now solid. The lesson carried forward: read worker
session transcripts as deeply as the supervisor summaries, and never trust
"sensors green" from a commit message over the milestone path.
