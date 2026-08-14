# Concern → official executable technique (T-8 §1)

Specimen-agnostic. Prefer framework-exposed signals over greps.

| Concern | Executable technique | Typical `exit_criteria[].check` |
|---------|----------------------|----------------------------------|
| Build resolves | `mvn compile` / `quarkus:build` exit 0 | `build_resolves` |
| Config loads | `ConfigValidationException`; build-time mismatch fail; `@TestProfile` — see skill `configure-quarkus-profiles` | `config_profile_load` |
| Mapping valid | `database.generation=validate` / `SchemaManager.validateMappedObjects()` | (entity stories: prefer test that runs validate; avoid query oracles with no query write-set) |
| HTTP contract | `@QuarkusTest` + REST Assured status/body | `http_semantics`, `route_contract`, `endpoint_contract` |
| Security enforced | `@TestSecurity` asserting live 401/403 vs 200 | `security_authz`, `route_auth` |
| Cache effective | spy/counter on underlying work (thinner official grounding) | `cache_hit` |
| Logging emitted | `InMemoryLogHandler` (internal API caveat) | `log_output` |
| Health ready | HTTP contract on `/q/health/ready` | `health_probe` |

Closed check names: `SEMANTIC_EXIT_VOCAB` in
`../check-spec-readiness/scripts/specimen_agnostic.py`.
Class allow-lists: `OPERAND_CLASS_SEMANTIC_EXITS` in the same module.

**Pattern:** (a) boot/build and observe failure, or (b) `@QuarkusTest` against a
framework-exposed surface. Cache and log rows observe internal side effects —
flag that weakness when choosing them.
