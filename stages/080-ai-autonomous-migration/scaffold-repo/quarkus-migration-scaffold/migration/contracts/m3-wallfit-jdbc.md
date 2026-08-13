# M3 wall-fit + JDBC harness (R-M3.9–13)

**Status:** binding proving-min
**Basis:** `20260810-m3-s003-harness-review.md`

## Bindings

| ID | Rule |
|----|------|
| **R-M3.9** | At create (`--wall-fit`): refuse if `operand_count × 90s > runtime_budget` **or** dual-stack JPA+JDBC trees with measured ≥ 20. Prefer **JPA-repos vs JDBC-repos** split. **Reject** blind wall raise alone. |
| **R-M3.10** | JDBC cards: write-first / anti-essay — cite `references/persistence.md`; forbid multi-kB Spring-replacement redesign in Reasoning. |
| **R-M3.11** | Before first `repository/jdbc/**` write: `check-jdbc-deps-preflight.py` (`spring-jdbc` + `spring-data-jdbc-core`). Fail → typed `dependency_wait` (no OOS pom). |
| **R-M3.12** | Hard `skill_view` → `spring-to-quarkus-patterns` persistence (+ jdbc notes) before first JDBC edit. |
| **R-M3.13** | FIS≥20 reclaim: checkpoint-only context — do **not** re-bulk-read all legacy JDBC on soft reclaim. |

## Commands

```bash
python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-operand-count.py . BODY.json --wall-fit
python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-jdbc-deps-preflight.py .
```
