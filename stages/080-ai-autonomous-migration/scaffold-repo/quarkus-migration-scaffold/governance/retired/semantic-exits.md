# Semantic product exits (AR-2.3–2.7)

**Status:** retired (GR3 / T-8 Z2 land)
**Superseded by:** skill `derive-story-oracles` + contract `surgical-scopes.md`
  (class-legal exits + dual-oracle refuse in `check-surgical-scopes.py`).
**Basis:** was in-tree AR-2.3–2.7 family table; derivation replaces enumeration.
**History:** GR3 removed specimen literals; T-8 skill retires the contract.

Bodies that touch REST/persistence CRUD **MUST** name falsifiable exits — not
compile-only. Stamp families via `identity.semantic_families` (list).

| Family | AR | Required `exit_criteria[].check` (any of) | Intent |
|--------|-----|-------------------------------------------|--------|
| `create_fk` | 2.3 | `create_fk` | Editable-field POST 201; reject client IDs; nest FK parents; 404 absent parents |
| `route_contract` | 2.4 | `route_contract` \| `endpoint_contract` | Routes match authoritative contract; no literal `*` wildcard abuse |
| `hql_entity_path` | 2.5 | `hql_entity_path` \| `delete_cascade_it` | Entity-path HQL; one-tx deletes without stale-state |
| `http_semantics` | 2.6 | `http_semantics` \| `exception_mapping` | 400/404/409/500 mapping; no leak of exception class/SQL |
| `tx_rmw` | 2.7 | `tx_rmw` \| `concurrency` | Single service tx RMW; stale update rejected/reconciled |

Non-REST families (`build_resolves`, `config_profile_load`, `test_suite_runs`,
`log_output`, `cache_hit`, `health_probe`) and operand-class preferred exits
are defined only in `specimen_agnostic.py` — do not re-list specimen paths here.

When `identity.semantic_families` is absent but write-set paths match
`*RestController*` / `*Repository*`, checker requires at least **two** distinct
families from the AR table (proving-min default for REST stories).

Foundation / build stories (`operand_class` build_config / pom / config) must
use resolution oracles (`build_resolves`, …) — not `quarkus_compile` / compile
(DD6).

```bash
python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-semantic-exits.py .
```
