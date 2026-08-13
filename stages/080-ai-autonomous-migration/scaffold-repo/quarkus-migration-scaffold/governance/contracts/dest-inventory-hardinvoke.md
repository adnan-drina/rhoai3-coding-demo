# Destination-inventory hard-invoke (BANK-DEST-INV-HARDINVOKE-1)

**Status:** binding (in-tree).

## Problem

Workers can conclude "destination empty / dependency absent" without reading the
stamped `refs.destination_inventory` receipt. Run#68 claimed no Java under
`src/` while 36 files existed — FLAG-1 recurring search-scope class.

## Rule

1. Create-m3 stamps a card obligation: any missing/absent/DEST_MISS/`empty
 destination` conclusion is **INVALID** unless Reasoning cites
 `refs.destination_inventory` (path+sha256) or
 `evidence/receipts/destination-inventory/<story>.json`.
2. Typed `dependency_wait` **requires** that citation first.
3. R0 lint: `assert-dest-inventory-hardinvoke.py` refuses tip drift that drops
 the `BANK-DEST-INV-HARDINVOKE-1` stamp from `create-m3-implementer.sh`.

## Scripts

| Script | Role |
|--------|------|
| `stamp-destination-inventory.py` | Build receipt + body ref (pre-create) |
| `assert-dest-inventory-hardinvoke.py` | R0: obligation stamp present on create path |

## Related

- `dependency-closure.md` (pre-exists truth)
- `partition-coverage.md`
