# Constraints preservation on amend (Class A)

**Status:** binding (in-tree).

## Problem

Amending an M3 typed body to fix one hole (e.g. ApplicationService interface-closure)
can silently drop the entire `constraints[]` block — including
`@IfBuildProfile` forbid, di-config required path, and sequence notes.
Proven twice: `t_29ccead3` forbid-drop class; S-002a prefer-fresh
`t_0cc3dc17` digest `cb2b8bb0…` (ACK VOIDED).

## Rule

1. Before any body amend, snapshot constraints:
 ```bash
 python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-constraints-preserved.py \
 . --body evidence/bodies/m3-s-NNN.json --snapshot-before
 ```
2. After amend (and after dependency/inventory stamps that rewrite the JSON),
 run `--check` — **FAIL-CLOSED** if any prior constraint text is missing.
3. Do **not** mint `ack-request` / accept brief-identity ack on a body that
 fails preservation.
4. Restoring constraints is additive-OK; silent loss is refuse.
5. Tip FREEZE otherwise — this is a Class A emergency exception.

## Scripts

| Script | Role |
|--------|------|
| `assert-constraints-preserved.py` | Snapshot + fail-closed diff |

## Related

- `interface-closure.md` — scope amend must not trade away constraints
- `body-immutability.md` — post-dispatch rewrite still forbidden; this gate
 covers **pre-dispatch** amend / stamp rewrites
