# Scar-archive triage (F9)

**Status:** binding record (in-tree).
**Authority:** Deputy M2 content review F9 / Lead land E-20260814T120500Z.

Incident-named gates that run (or ran) on every create/dispatch. Verdict:

| Artefact | Verdict | Why |
|----------|---------|-----|
| `check-s008-resurrection-order.py` | **KEEP** (general rule) | Parent→child→grandchild entity order — specimen-agnostic contract already; create+dispatch wired |
| `assert-quarantine-tombstones.py` | **KEEP** | General wipe-survival assert; every-chain |
| `register-quarantine-tombstone.py` | **KEEP opt-in** | Mutate helper after wipe — **no auto caller by design** (not every-chain tax) |
| `assert-constraints-preserved.py` | **WIRED** | Was callerless; create-m3 now `--snapshot-before` after mint inject |
| `check-jdbc-deps-preflight.py` | **KEEP** | General JDBC dep rule when JDBC stories write |
| `check-persistence-bom.py` | **RETIRED** (DD4) | R-M3.5 stub — story-owns-extensions |
| `check-compile-deps-preflight.py` | **RETIRED** (DD4) | R-M3.7 stub |

Do not add new incident-named permanent gates without a general rule name and
a create/dispatch caller (or an explicit opt-in mutate role).
