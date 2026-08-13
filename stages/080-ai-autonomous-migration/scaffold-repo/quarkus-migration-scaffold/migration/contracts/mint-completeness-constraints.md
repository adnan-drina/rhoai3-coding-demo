# Mint-completeness: standard constraints on create/re-mint (Class A)

**Status:** binding (in-tree).

## Problem

`constraints-preservation` correctly preserves whatever was already on the body.
Pre-standard mints had **no** `constraints` key — so remint preserved emptiness.
ACK checks then failed: load-bearing card prose without sidecar
constraints (Enforcement-Parity class).

## Rule

1. Fresh create / re-mint **must** carry a non-empty `constraints[]` for the
 story class, **or** be explicitly tagged `constraint_free`
 `identity.constraint_free=true`.
2. Standard applicable set (minimum):
 - FORBIDDEN `@IfBuildProfile` + required `%profile` path
 - WRITE-SET (AR-4.4)
 - COVERAGE-GAP → typed `needs_input` (never OOS-invent)
 - RESIDUE (src_code) / BUILD_CONFIG scope note (build_config)
 - Profile-locality stories (e.g. S-009): explicit `%mysql`/`%postgresql` path
3. `create-m3-implementer.sh` runs
 `assert-mint-constraints-complete.py --inject` before body digest stamp, then
 `--check` (no inject) refuse path is available for audits.
4. Distinct from `constraints-preservation-on-amend.md` (preserve ≠ invent).

## Scripts

| Script | Role |
|--------|------|
| `assert-mint-constraints-complete.py` | Check / inject standard set |

## Related

- `constraints-preservation-on-amend.md`
- `interface-closure.md`
