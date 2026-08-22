# Available scripts

KEEP (this skill — M4/M5 product):

- `scripts/check-verdict-routing.py` — ship/routing legality on verdicts
- `scripts/check-semantics-manifest.py` — B8 check-semantics adequacy / over-promise lints
- `scripts/check-factory-m5.py` — factory must not contradict M5 full ACCEPT
- `scripts/check-candidate-promote.py` — candidate_sha → promote gate
- `scripts/check-accept-scope.py` — SCOPED_ACCEPT when descopes stand
- `scripts/check-m4-floor-receipts.py` — M4 floor receipt trio complete
- `scripts/write-receipt.py` — **writer** for M4-floor / gate receipts
- `scripts/run-m4-floor.sh` — run the M4 floor suite
- `scripts/check-empty-security.py` — empty security config refuse
- `scripts/check-runnable-db-config.py` — runnable DB config gate
- `scripts/check-test-toolchain.py` — test toolchain presence
- `scripts/compute-substrate-reopen.py` — substrate reopen set

PARK (`.hermes/_park/requeue/` until K3): wall/crash requeue, chaos,
workspace-clean, side-effect recovery, evaluate-exit-criteria.

Admission G-1..G-4 fixtures: `../check-domain-parity/fixtures/admission/` only.
