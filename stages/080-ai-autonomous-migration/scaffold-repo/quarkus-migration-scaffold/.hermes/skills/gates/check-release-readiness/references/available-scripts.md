# Available scripts

KEEP (this skill — M4/M5 product):

- `scripts/check-verdict-routing.py` — ship/routing legality on verdicts
- `scripts/check-semantics-manifest.py` — B8 check-semantics adequacy / over-promise lints
- `scripts/check-factory-m5.py` — factory must not contradict M5 full ACCEPT
- `scripts/check-candidate-promote.py` — candidate_sha → promote gate
- `scripts/check-accept-scope.py` — SCOPED_ACCEPT when descopes stand
- `scripts/check-m4-floor-receipts.py` — M4 floor receipt trio complete
- `scripts/write-receipt.py` — **writer** for M4-floor / gate receipts
- `scripts/run-m4-pre-verdict.sh` — snapshot surefire, parse results, refuse a pre-specified M4 token, then `assert-retrievable-tree` / `assert-pinned-gates-ran` / `assert-g4-claim-consistency` / `assert-no-fence-evasion` (Architect `151334ZA` (a); Operator `074910ZO` / `115007ZO` / `164058ZO`; fail closed; not a card pin)
- `scripts/snapshot-m4-test-reports.py` — copy surefire/failsafe XML to `evidence/m4-pre-rebuild/` before any rebuild; first XML snapshot wins
- `scripts/assert-surefire-results.py` — parse snapshot/live surefire XML; Failures>0 or missing XML is REFUSE
- `scripts/assert-m4-card-body.py` — refuse `Token:` / `ship:` on the M4 body (dest-4 named none)
- `scripts/assert-g4-claim-consistency.py` — refuse G-4 `N/A` vs verdict `INCONCLUSIVE` / M5-requires-G-4 (Operator `114101ZO`)
- `scripts/assert-m4-complete-around-red.py` — refuse `PROVISIONAL_ACCEPT` (or idle-in-reason) when a bound floor `--floor-rc` is 1 (Architect `130758ZA`; dest-8 AR-2.8)
- `scripts/run-m4-floor.sh` — run the M4 floor suite (calls `run-m4-pre-verdict.sh` first)
- `scripts/check-empty-security.py` — empty security config refuse
- `scripts/check-runnable-db-config.py` — runnable DB config gate
- `scripts/check-test-toolchain.py` — test toolchain presence
- `scripts/compute-substrate-reopen.py` — substrate reopen set

PARK retired (Operator GO `155455Z`): `.hermes/_park/` is gone. Wall/crash
requeue, chaos, workspace-clean, and evaluate-exit-criteria rebuild later
only on dest GO. Do not dump those files into kernel.

Admission G-1..G-4 fixtures: `../check-domain-parity/fixtures/admission/` only.
