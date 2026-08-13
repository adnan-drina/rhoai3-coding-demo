# Write fence — proving min (AD-H §16.4 / ER#2 F2)

**Status:** binding for `validation_protocol_conformant` · **not** `release_qualified`
**Basis:** AD-H §16.4

`HERMES_WRITE_SAFE_ROOT=/projects/modernized` alone is **insufficient**: ACKs,
gate verdicts, and ballot-adjacent stores live inside that tree. Proving-min
adds **operand separation** so an Implementing-task worker cannot forge those paths.

## Tier (a) — proving min (this contract)

| Mechanism | What it does |
|-----------|--------------|
| Path deny-list | `evidence/acks/**`, `evidence/verdicts/**`, `.hermes/skills/**`, `SOUL.md`, `.hermes/home/kanban.db` (lint) |
| OS fence | `apply-write-fence.sh lock` → ACK/verdict/skills/SOUL not writable by the worker UID (`kanban.db` stays tool-writable; lint still denies file-tool tamper) |
| Scope refuse | `check-write-fence.py` fails dirty/out-of-scope paths **before** `kanban_complete` |
| Seat probe | `probe-write-fence.py` must observe `PermissionError` / refuse on deny paths |

## Tier (b) — release (deferred)

Authenticated human approvals bound to artifact digests in a store the worker
**cannot** write. Not claimed under `ad010_demo=false`.

## Commands

```bash
# Lock Implementing-task deny-list (default worker fence)
bash .hermes/enforcement/enforce-authority-boundary/scripts/apply-write-fence.sh lock

# /human temporarily unlock to grant an ack, then re-lock
bash .hermes/enforcement/enforce-authority-boundary/scripts/apply-write-fence.sh unlock
bash .hermes/enforcement/enforce-authority-boundary/scripts/apply-write-fence.sh lock

# Seat probe (must PASS after lock)
python3 .hermes/enforcement/enforce-authority-boundary/scripts/probe-write-fence.py .

# Pre-complete refuse (git dirty + optional body scope)
python3 .hermes/enforcement/enforce-authority-boundary/scripts/check-write-fence.py . \
 --body evidence/bodies/S-010.json
```

Forging an ACK file must not advance a stage once this fence is locked.
