# Available scripts


- `scripts/check-phase-matrix.py` — AD-H §18 required_checks present in dispatch
- `scripts/check-verdict-routing.py` — ship/routing legality on verdicts
- `scripts/check-semantics-manifest.py` — B8 check-semantics adequacy / over-promise lints (`governance/contracts/check-semantics-manifest.md`)
- `scripts/check-factory-m5.py` — factory must not contradict M5 full ACCEPT
- `scripts/check-candidate-promote.py` — candidate_sha → promote gate
- `scripts/check-accept-scope.py` — SCOPED_ACCEPT when descopes stand
- `scripts/check-m4-floor-receipts.py` — M4 floor receipt trio complete
- `scripts/write-receipt.py` — **writer** for M4-floor / gate receipts
- `scripts/run-m4-floor.sh` — run the M4 floor suite
- `scripts/check-wall-exit-eval.py` — wall exit-eval present
- `scripts/apply-wall-requeue-policy.py` — mutate: wall requeue / hard ceiling
- `scripts/apply-crash-requeue-policy.py` — mutate: crash requeue
- `scripts/apply-dependency-wait-hold.py` — mutate: dependency_wait hold stamp
- `scripts/restore-or-refuse-requeue.py` — F4 restore-or-refuse after crash
- `scripts/check-workspace-clean.py` — workspace clean probe
- `scripts/check-side-effect-recovery.py` — side-effect recovery idle/live
- `scripts/check-empty-security.py` — empty security config refuse
- `scripts/check-runnable-db-config.py` — runnable DB config gate
- `scripts/check-test-toolchain.py` — test toolchain presence
- `scripts/assert-complete-exit-criteria.py` — complete exit-criteria assert
- `scripts/evaluate-exit-criteria.py` — evaluate exit-criteria cmds
- `scripts/compute-substrate-reopen.py` — substrate reopen set
- `scripts/run-chaos-matrix.py` — chaos matrix runner
