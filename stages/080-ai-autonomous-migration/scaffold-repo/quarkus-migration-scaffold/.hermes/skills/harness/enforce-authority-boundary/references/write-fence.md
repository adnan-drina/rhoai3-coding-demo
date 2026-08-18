# Write fence — proving min (AD-H §16.4 / ER#2 F2)

**Status:** binding for `validation_protocol_conformant` · **not** `release_qualified`
**Basis:** AD-H §16.4

`HERMES_WRITE_SAFE_ROOT=/projects/modernized` alone is **insufficient**: ACKs,
gate verdicts, and ballot-adjacent stores live inside that tree. Proving-min
adds **operand separation** so an Implementing-task worker cannot forge those paths.

## Tier (a) — proving min (this contract)

| Mechanism | What it does |
|-----------|--------------|
| Path deny-list | `evidence/acks/**`, `evidence/verdicts/**`, `.hermes/skills/**`, `.hermes/skills/harness/**` (A-1 / DD5), `SOUL.md`, `.hermes/home/kanban.db` (lint) |
| OS fence | `apply-write-fence.sh lock` → ACK/verdict/skills/harness/SOUL not writable by the worker UID (`kanban.db` stays tool-writable; lint still denies file-tool tamper) |
| Scope refuse | `check-write-fence.py` fails dirty/out-of-scope paths **before** `kanban_complete` (`norm()` prefix-strips `./` only — never `lstrip("./")`, which defeated `.hermes/**` DENY; Z15-a) |
| Seat probe | `probe-write-fence.py` must observe `PermissionError` / refuse on deny paths |

`HERMES_WRITE_SAFE_ROOT` is also an EX-5 Managed Scope pin (layer 2). The
EX-3 write-set hook is **path-bearing** (Architect `091919Z` / v24 env+hook
deny): a dest path is checked against spawn-env
`HERMES_KANBAN_FILES_WRITABLE`. Published `[]` denies every dest-relative
write. Dest `evidence/runtime/write-sets/*.json` is a mint **cache**
(Architect 35099226) — the hook must not read it, whatever it contains.
The GitOps `pre_tool_call` matcher is invocation-only (`write` plus
`terminal` as in-workspace defence-in-depth; not a hole-1 fix; hole 2 /
`$HOME` stays open). A deny-prefix path **inside** SAFE_ROOT is rc 0 on
the native fence (HKN-12). `approvals.deny` and `terminal.backend: local`
are outer overlays, not a replacement. v24 does not claim a new trust
boundary.

## Tier (b) — release (deferred)

Authenticated human approvals bound to artifact digests in a store the worker
**cannot** write. Not claimed under `ad010_demo=false`.

## Commands

```bash
# Lock Implementing-task deny-list (default worker fence)
bash .hermes/skills/harness/enforce-authority-boundary/scripts/apply-write-fence.sh lock

# /human temporarily unlock to grant an ack, then re-lock
bash .hermes/skills/harness/enforce-authority-boundary/scripts/apply-write-fence.sh unlock
bash .hermes/skills/harness/enforce-authority-boundary/scripts/apply-write-fence.sh lock

# Seat probe (must PASS after lock)
python3 .hermes/skills/harness/enforce-authority-boundary/scripts/probe-write-fence.py .

# Pre-complete refuse (git dirty + optional body scope)
python3 .hermes/skills/harness/enforce-authority-boundary/scripts/check-write-fence.py . \
 --body evidence/bodies/S-010.json
```

Forging an ACK file must not advance a stage once this fence is locked.
