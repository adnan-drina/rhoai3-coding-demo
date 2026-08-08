# `mta-exception` waiver schema

**Status:** bound with findings provisional lock · ADR-47 kind (Architect CONCUR)  
**Pattern-steal:** checkable re-open triggers (Loiane / `E-20260808T060227Z`)

## Required fields

| Field | Type | Rule |
|-------|------|------|
| `kind` | string | always `mta-exception` |
| `id` | string | Stable id, e.g. `MTA-EX-001` |
| `ruleID` | string | Exact analyzer rule id |
| `finding_ref` | string | Same as ruleID or incident key |
| `referent` | object | `{ "path": "...", "sha256": "..." }` of `harvest_referent` |
| `incident_key` | object | `{ "uri", "lineNumber" }` (+ optional message hash) |
| `claim` | string | `false-positive` \| `wrong-target-scope` \| `upstream-bug` \| `version-skew` |
| `evidence` | string | Reproducible counter-example on that digest |
| `rationale` | string | Why waived |
| `re_open_trigger` | string | **Checkable** command/condition — **not** `"skipped"` |
| `authority` | string | Filer role (never worker-unilateral) |
| `concur` | string | `pending` \| Architect/Operator reference |
| `decided_by` | string | Role or identity |
| `decided_at` | string | ISO-8601 UTC |

**Effect:** excluded from G-3 open-mandatory set **only after** concur; must still
be **counted and reported** in G-3 output.

## Example

```yaml
kind: mta-exception
id: MTA-EX-001
ruleID: eap8/javax-to-jakarta
finding_ref: eap8/javax-to-jakarta
referent:
  path: /projects/.derived/legacy-at-3
  sha256: "…"
incident_key:
  uri: file:///src/main/java/Example.java
  lineNumber: 12
claim: wrong-target-scope
evidence: "destination is Quarkus Jakarta; rule targets EAP8 servlet stack"
rationale: Handled by free-primitives r00
re_open_trigger: "test -f migration/derived/legacy-at-3/pom.xml && ! grep -R --quiet 'javax\\.' migration/derived/legacy-at-3/src || echo REOPEN"
authority: Lead
concur: pending
decided_by: Lead
decided_at: 2026-08-08T00:00:00Z
```

## Fail closed

Skill `sdd-readiness` (`check-readiness.sh`) fails if any file under
`migration/waivers/` or `migration/mta-exceptions/` lacks a non-empty
`re_open_trigger` (YAML/JSON).
