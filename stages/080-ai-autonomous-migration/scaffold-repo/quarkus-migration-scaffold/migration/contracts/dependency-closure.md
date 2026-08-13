# Dependency / pre-exists / import-closure (Class A)

**Status:** binding (in-tree).

## Problem

`check-partition-coverage.py` proves HTTP endpoint coverage + no file overlaps.
It does **not** verify `dependencies[]` truth. S-003 declared DTO/mapper/
`UserService` as `pre-exists` while DEST_MISS; worker correctly typed-BLOCK'd.
Interface-closure covers `implements` only — import/type-ref ownership is the
sibling gap.

## Rule

1. At create-m3 (fail-closed): `assert-dependency-closure.py --body <body>`
 - Every `dependencies[]` entry with `provider=pre-exists` must exist on the
 destination filesystem.
2. Optional `--imports`: existing `files_writable` `.java` files must not import
 specimen domain types that are DEST_MISS and lack an owner in writable/scope/deps.
3. Distinct from `interface-closure.md` (implements) and
 `partition-coverage.md` (endpoints/overlaps).

## Scripts

| Script | Role |
|--------|------|
| `assert-dependency-closure.py` | Pre-exists truth (+ optional import scan) |

## Related

Bank id: `BANK-DEP-CLOSURE-1`


- `interface-closure.md`
- `partition-coverage.md`
- S-003 typed BLOCK measurement `t_61dee4d8` (ADHERE_PASS notes)
