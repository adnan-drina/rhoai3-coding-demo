# Schema: `rhoai3.findings-handoff/v1`

M1→M2 **seam** artifact (Architect `E-20260809T072752Z`).

| Layer | Path | Role |
|-------|------|------|
| Evidence store | `migration/mta-findings.json` | Full analyzer envelope (may contain `codeSnip`) |
| Seam handoff | `migration/findings-handoff.json` | Planner input index — **no snips** |

## Shape

```json
{
  "schema": "rhoai3.findings-handoff/v1",
  "emitted_at": "RFC3339Z",
  "evidence": { "path": "migration/mta-findings.json", "sha256": "…" },
  "inventory": { "path": "migration/entry-point-inventory.json", "sha256": "…" },
  "rules": [
    {
      "rule_id": "…",
      "category": "mandatory|optional|…",
      "effort": 1,
      "incident_count": 3,
      "loci": [{ "path": "…", "line": 12 }]
    }
  ],
  "totals": { "violations": 32, "by_category": { "mandatory": 10 } },
  "ack_obligation": "…"
}
```

## Invariants

- Bytes scale with rule/locus **cardinality**, never evidence-store snip density.
- Absolute size cap: 65536 bytes (emit + gate).
- Ratio: `size(handoff) / size(evidence) < 0.25`.
- Forbidden keys anywhere in the document: `codeSnip` / snip-like fields.

## Tools

```bash
python3 .hermes/skills/mta-analysis/scripts/emit-findings-handoff.py /projects/modernized
python3 .hermes/skills/mta-analysis/scripts/check-findings-handoff.py /projects/modernized
```

Emit runs after normalize in `mta-analyze-legacy.sh`. Gate is required before M2 PLAN at original scope.
