# Product acceptance tests (AD-H §G.1 / AR-2.8)

**Status:** binding proving-min
**Basis:** in-tree harness obligations (sibling contracts + skills).

## Bar

G-1 / M3 acceptance MUST measure **migrated product behavior**, not harness
probes. Required families (one or more product `*Test.java` / `*IT.java` each):

| Family | Intent | Typical evidence |
|--------|--------|------------------|
| **boot** | package/start smoke | `@QuarkusTest` + `GET /q/health` → 200 |
| **security** | authz migrated | anonymous **401**, allowed role success |
| **crud** | REST product paths | `/api/...` GET/PUT (or POST/DELETE) statuses |
| **db** | intended schema/data | Flyway seed row visible via API or query |

`com.demo.harness.*` is **tooling smoke only** (`G1_OPERAND=tooling_smoke`).
It never satisfies AR-2.8.

Optional markers in test sources: `AR28:boot`, `AR28:security`, `AR28:crud`,
`AR28:db`.

## Checker

```bash
python3 .hermes/skills/gates/check-domain-parity/scripts/check-product-tests.py .
# Also refuse probe-only (AR-3.6):
python3 .hermes/skills/gates/check-domain-parity/scripts/check-g1-acceptance-operand.py .
```

Fixtures: `governance/fixtures/product-tests/ar28-*`.

## Honesty

Checker proves **family presence** in the dest test tree. Live green
(`mvn -Dtest=…IT test`) is a separate prove step before claiming M3 phase
PASS / `ad010_demo=true`.
