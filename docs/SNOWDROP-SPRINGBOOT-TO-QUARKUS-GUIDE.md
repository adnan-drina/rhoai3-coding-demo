# Snowdrop Spring Boot → Quarkus guide — harness notes

Written 2026-07-29. Lightweight notes only — not an adoption plan. Umbrella:
[SPRING-TO-QUARKUS-GUIDANCE-REVIEW.md](SPRING-TO-QUARKUS-GUIDANCE-REVIEW.md).

**Source (cloned for review):**
[snowdrop/springboot-to-quarkus-migration-guide](https://github.com/snowdrop/springboot-to-quarkus-migration-guide)
(local copy: `tmp/springboot-to-quarkus-migration-guide/`).

One-pass review of Snowdrop's rule templates. Captured borrows only —
no further upstream tracking.

## What to borrow

### 1. Rule-card schema → enrich MAPPINGS / brief cards

Snowdrop rules use a clear card shape:

- Goal
- Parameters
- Effort
- Order
- Konveyor / upstream reference
- Instructions table
- BEFORE / AFTER examples

**Best borrow:** use that shape when enriching MAPPINGS rows and BRIEF
"Decided target shapes" so agents get executable steps, not only
annotation pairs.

### 2. M1 preflights we do not have yet

| Preflight | Snowdrop rule | Suggested use |
|---|---|---|
| Multi-module Maven (`<modules>`) | `rule-multi-maven-modules` | Warn/fail or force story split in M1 — tool path is unsupported for multi-module |
| License vs Apache-2 compatibility | `rule-compatibility-oss-license` | Optional note in architecture profile or `debt.md` |

Workspace already supplies JDK/Maven, so their presence rules add little.

## Related

| Document | Relation |
|---|---|
| [OPENREWRITE-SPRINGBOOT-TO-QUARKUS.md](OPENREWRITE-SPRINGBOOT-TO-QUARKUS.md) | Executable OpenRewrite adopt/adapt/reject |
| Stage 080 `MAPPINGS.md` | Live agent catalog to enrich with rule cards |
| Upstream guide | https://github.com/snowdrop/springboot-to-quarkus-migration-guide |
