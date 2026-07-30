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
| Bank ⬜ | `v9-bank-gate.sh honesty\|all` | implement ⬜→✅; preflight refuses start |
| Coolstore hardcode | `v9-coolstore-lint.sh` | remove specimen hardcoding from harness |
| O-FALSECOMPLETE | `v9-story-complete-lint.sh` | re-earn via ship-only path below |
| Outer start | `v9-preflight-outer-start.sh` | bank + coolstore + story-complete lint + no blocking pendings |
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
