# Autostart (M1) — create then check then dispatch

Architect BIND `E-20260820T075106Z`, AMEND `E-20260820T140201Z`. Proposal
`harness-refactoring/monitoring/v35/AUTOSTART-PROPOSAL.md` §6 (human
brief-identity wait) is **STALE**. Wave proceeds on M1 `gate:` records.
Do not restore a human ack via autostart.

## Sequence (postStart)

1. Existing init + `stamp-harness-rev.py`
2. `assert-autostart-gates.py harness-rev` — dest `.hermes/HARNESS_REV` must
   equal golden `main` (`git ls-remote`). Stale existing stamp **refuses**.
3. `dispatch-phase.sh M1` with `DISPATCH_MAX=0` (create + park M2/M3 holder).
   Seat pin probe is `hermes --version` (binary-local). `hermes version` is
   argparse noise on this seat and must not be treated as the version string.
4. `assert-autostart-gates.py holder` — one card titled `M3 WAVE HOLDER…`
   and `skills=[]`
5. If both gates green: `hermes kanban dispatch --max 1`
6. Else: write `.hermes/AUTOSTART-STATUS` (`state: REFUSED`) and leave
   parked. Do **not** fail the DevWorkspace.

`t0` is `.hermes/AUTOSTART-T0` (UTC) written when dispatch is invoked.

## Off switch

Template parameter `autoStartMigration` (default **on**). Sets dest env
`AUTO_START_MIGRATION`. `0`/`false`/`off` writes `state: SKIPPED`.

## OBJECT

- `kanban daemon --force`
- dest-enable `dispatch-phase` as a skill pin
- inventing a reaper or Hermes timeout key
- landing this onto a live v36 dest
- persist-postStart secret dump
