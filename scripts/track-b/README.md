# Track B quality gates (script-enforced)

These scripts replace memory-only mandates for Stage 080 Track B.
Driver: `v8-driver-loop.sh` (wrapper: `tmp/v8-driver-loop.sh`).

Shared helpers: `lib-quality-gates.sh` (`qg_ws_pod`, `qg_story_complete_ok`,
`qg_remote_pgrep_busy`, gate validators, bank scanners).

| Gate | Script | Clears with |
|------|--------|-------------|
| O-DRV3 task analysis | driver → `V9-TASK-ANALYSIS-PENDING` | `v9-capture-diff.sh` + gate entry + `v9-clear-task-analysis.sh` |
| O-DRV5 milestone | driver → `V9-M-ANALYSIS-PENDING` | gate + `**Verdict:**` + `v9-clear-m-analysis.sh` |
| O-DRV4 chat pulse | driver every tick | post in chat then `tmp/v9-chat-pulse.sh` → `v9-chat-pulse.sh` |
| O-DRV6 debt HOLD | driver + ledger | fix debt; harness freezes via **O-DEBTFRZ** |
| O-DRV7 escalation | `V9-ESCALATION-PENDING` | `v9-clear-escalation.sh` (Qwen RCA + bank + retest) |
| O-HAND hand fix | `v9-handfix-detect.sh` | `v9-clear-handfix.sh` |
| O-ADV story ADVANCE | `v9-advance-gate.sh` | `check` / `clear` after gate ADVANCE |
| Bank ⬜ | `v9-bank-gate.sh honesty\|all` (`BANK_DOC`=`docs/V10-FUTURE-IMPROVEMENTS.md`) | implement ⬜→✅; 📋 = later wave (ignored); preflight refuses start |
| Coolstore hardcode | `v9-coolstore-lint.sh` | remove specimen hardcoding from harness |
| O-FALSECOMPLETE | `v9-story-complete-lint.sh` | re-earn via ship-only path below |
| Outer start | `v9-preflight-outer-start.sh` | bank + coolstore + plan-corpus/defaults (`v10-plan-corpus-gate.sh`) + exec-corpus (`v10-exec-corpus-gate.sh`) + story-complete lint + **O-HERMESPREFLIGHT** (`v10-hermes-parity.sh`) + **O-GOLDENFRESH** (`v10-golden-fresh.sh`) + no blocking pendings |
| Plan corpus | `v10-plan-corpus-gate.sh` | O-PLANCORPUS live-flag re-lint + O-DEFAULTAUDIT seed check |
| Exec corpus | `v10-exec-corpus-gate.sh` | O-EXECCORPUS archived sfix/escalation honesty replay |
| Hermes parity | `v10-hermes-parity.sh` | O-HERMESPREFLIGHT fail-closed golden↔pod `.hermes` digest; `--compare` for instruments; **O-HERMESPARITYSEM** shared semantic exclusions via `qg_hermes_list_semantic_files` |
| Golden fresh | `v10-golden-fresh.sh` | O-GOLDENFRESH publish-fp + three-way repo/published/pod; `--stamp` / `--check-local` for instruments; same semantic digest as parity |
| Restart readiness (R2) | `restart-readiness.sh` | LRR GO/NO-GO: SC-0..SC-3 checkable facts (predictions committed, **R3** `docs/V10-CHANGE-MANIFEST.md` UNDER/NOT-UNDER committed with R4/R6/R8 lines, clean `.hermes`, parity+golden, `M3_ALL=1`, `M3_ALL_OPERATOR_AUTO` off, corpus gates). Does **not** start outer |
| Driver uptime | `v9-ensure-driver.sh` + launchd plist example | external watchdog |

## O-FALSECOMPLETE — honest ship re-earn

| Script | Role |
|--------|------|
| `v9-ship-only.sh` | Host: start `SHIP_ONLY=1` supervisor in pod (no commits) |
| `v9-ship-only-waiter.sh` | Pod: wait for **completion markers** (`outer-complete` / `S0N,complete`), then ship-only |
| `v9-record-ship-only.sh` | App repo: write harness-shaped `S0N story complete: success…` (**no push** by default) |
| `v9-story-complete-lint.sh` | Reject parenthetical / agent-authored story-complete subjects |

Waiter must **not** treat “outer process absent” as done (crash ≠ complete).

Bare `echo SHA > tmp/V9-TASK-ANALYSIS.sha` **does not clear** — sha files need
`# validated:` from the clear scripts.

Honesty-blocking bank rows: open `⬜` with `[HONESTY]` in Notes, or open
`O-DRV*` / `O-ESCAL*` / `O-DEBT*` / `O-GATE*` / `O-HAND*` / `O-ADV*` ids.

Fixture tests: `bash scripts/track-b/tests/gate-instruments.sh`
(O-HANDNOISE / O-ADVTASK / O-DRV3EV / O-FALSECOMPLETE).
