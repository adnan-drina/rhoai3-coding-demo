# `.hermes/lib/` — shared Python, not a skill

No `SKILL.md`. Discovery does not list this directory.

| Module | Concern |
|--------|---------|
| `paved_road.py` | M1/M2 paved-road audit + coverage CLI (`python3 .hermes/lib/paved_road.py coverage`). Generated `audit.json` from `steps.json`. |
| `inventory_io.py` | load JSON / migration.yaml, resolve inventory path |
| `path_maps.py` | `path_rewrites`, `intra_package_maps`, dest-as-written |
| `supersede.py` | 1:N dest_file successor sets |
| `http_join.py` | HTTP denominator + story.endpoints ∩ inventory rows |
| `specimen_agnostic.py` | remainder (oracles / operand / refs) + re-exports |
| `generated_sources.py` | generator classification at **read** (stamp is a hint) |
| `human_home.py` | OS-account home (`pwd`/`getent`), not `Path.home()` / `$HOME` |

Importable modules only — no `__main__` CLIs — except `paved_road.py`, which
is the coverage/audit/generate/sync CLI for the paved-road index. Dashboard
pin is overlay bake `HERMES_WEB_DIST`; dest `.hermes/checks/` is retired.
Java type walk lives in `inventory-legacy-surface/scripts/type_graph.py`
(relocate, not delete).

Discovery identity is the zero-byte marker `.hermes/lib/.hermes-lib`,
not a member module name. Scripts that need this path on `sys.path`
test `(lib / ".hermes-lib").is_file()` and refuse with
`FAIL: .hermes/lib marker missing`. Do not re-anchor on
`specimen_agnostic.py` or any other module that later thinning may
relocate.

Do not add `.hermes/home/scripts/` or repo-root `scripts/` for new procedures.
`.hermes/kernel/pre_tool_call.sh` is the K2 REHOST (not this directory; not claimed control). K1, K3, and K4 live in `.hermes/kernel/` (`k1_*.py`, `k3_*.py`, `k4_*.py`). Do not add the converter here.
