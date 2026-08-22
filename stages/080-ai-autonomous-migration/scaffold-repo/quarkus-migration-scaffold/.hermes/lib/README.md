# `.hermes/lib/` — shared Python, not a skill

No `SKILL.md`. Discovery does not list this directory.

| Module | Concern |
|--------|---------|
| `inventory_io.py` | load JSON / migration.yaml, resolve inventory path |
| `path_maps.py` | `path_rewrites`, `intra_package_maps`, dest-as-written |
| `supersede.py` | 1:N dest_file successor sets |
| `http_join.py` | HTTP denominator + story.endpoints ∩ inventory rows |
| `specimen_agnostic.py` | remainder (oracles / operand / refs) + re-exports |
| `type_graph.py` | in-prefix Java type walk |
| `generated_sources.py` | generator classification at **read** (stamp is a hint) |
| `assert_web_dist_pin.py` | dashboard bundle stamp vs `pins.json` (refuse stale UI) |

Do not add `.hermes/home/scripts/` or repo-root `scripts/` for new procedures.
`.hermes/kernel/` is first K land after Gate P-kernel — not this directory.
