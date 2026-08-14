# Constraints preservation on amend (Class A)

**Status:** binding (in-tree).
**F9 (E-20260814T120500Z):** create path wires `--snapshot-before` after mint
inject so the gate is no longer callerless.

## Problem

Amending an M3 typed body to fix one hole (e.g. ApplicationService interface-closure)
can silently drop the entire `constraints[]` block — including forbid / profile /
write-set imperatives (F7). Proven twice: `t_29ccead3` forbid-drop class; S-002a
prefer-fresh `t_0cc3dc17`.

## Rule

1. Create path snapshots after mint inject (automatic).
2. Before any **manual** body amend, re-snapshot if needed:
 ```bash
 python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-constraints-preserved.py \
 . --body evidence/bodies/m3-s-NNN.json --snapshot-before
 ```
3. After amend (and after dependency/inventory stamps that rewrite the JSON),
 run `--check` — **FAIL-CLOSED** if any prior constraint text is missing.
4. Do **not** mint `ack-request` / accept brief-identity ack on a body that
 fails preservation.
5. Restoring constraints is additive-OK; silent loss is refuse.
6. Tip FREEZE otherwise — this is a Class A emergency exception.

## Scripts

| Script | Role |
|--------|------|
| `assert-constraints-preserved.py` | Snapshot + fail-closed diff (create-m3 wires snapshot) |

## Related

- `interface-closure.md` — scope amend must not trade away constraints
- `body-immutability.md` — post-dispatch rewrite still forbidden; this gate
 covers **pre-dispatch** amend / stamp rewrites
- `injection-receipts.md` — F2 provenance for injected constraint text
