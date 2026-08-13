# Create-path interface-closure (Class A)

**Status:** binding (in-tree).

## Problem

An M3 body can place `FooImpl.java` in `files_writable` while omitting the
interface `Foo.java` from scope, dest, and `dependencies[]`. The impl cannot
compile without the interface. Workers are cornered into typed `needs_input`
BLOCK vs OOS-create invent (proven: S-002a reclaim `t_f3e44947`
`ApplicationService` after quoting coverage-gap BLOCK law).

## Rule

Before `create-m3` / dispatch:

1. For every in-scope / writable Java type that implements an interface
 (heuristic: `*Impl.java` → sibling `*.java`; plus parse `implements`
 from legacy/dest sources when available):
2. That interface path MUST be:
 - in `files_in_scope` / `files_writable`, **or**
 - already present on destination, **or**
 - declared in `dependencies[]` with a provider / `pre-exists`
3. Fail-closed create if any hole remains — do **not** dispatch a body that
 corners the worker into block-vs-OOS-create.
4. Mid-run OOS-create of a missing interface is **ABORT** (no legalize).
 Prefer-fresh only after this gate tip-lands and the body includes the
 interface (or declared dep).

## Scripts

| Script | Role |
|--------|------|
| `check-interface-closure.py` | Fail-closed create-path gate |
| Wired into `create-m3-implementer.sh` | Pre-create |

## Related

Bank id: `BANK-CREATE-PATH-IFACE-1`


- `partition-coverage.md` — whole-partition VALID
- `compile-scope-filtered.md` — in-scope compile errors FAIL (raises corner pressure)
- Bank: board monitoring record `v12-m3-s002a-t_f3e44947-create-path-iface-closure` (authoring repo; not present in a deployed seat)
