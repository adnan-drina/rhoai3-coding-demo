# `mta-exception` waiver schema (stub)

**Status:** schema lock in progress — bind at mta-cli / findings cut  
**Pattern-steal:** Loiane ADR/waiver re-open triggers (`E-20260808T060227Z`)

## Required fields

| Field | Type | Rule |
|-------|------|------|
| `id` | string | Stable id, e.g. `MTA-EX-001` |
| `finding_ref` | string | MTA/kantra rule id or finding key |
| `rationale` | string | Why waived for this specimen/run |
| `re_open_trigger` | string | **Checkable** command or condition that forces re-open — **not** `"skipped"` |
| `decided_by` | string | Role or identity |
| `decided_at` | string | ISO-8601 UTC |

## Example

```yaml
id: MTA-EX-001
finding_ref: eap8/javax-to-jakarta
rationale: Handled by free-primitives r00; destination is Quarkus Jakarta.
re_open_trigger: "test -f migration/derived/legacy-at-3/pom.xml && ! grep -R --quiet 'javax\\.' migration/derived/legacy-at-3/src || echo REOPEN"
decided_by: Lead
decided_at: 2026-08-08T00:00:00Z
```

## Fail closed

`scripts/check-sdd-readiness.sh` fails if any file under
`migration/waivers/` or `migration/mta-exceptions/` lacks a non-empty
`re_open_trigger` (YAML/JSON).
