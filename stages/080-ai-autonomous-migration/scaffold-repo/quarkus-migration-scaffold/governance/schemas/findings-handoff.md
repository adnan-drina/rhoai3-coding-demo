# Schema: `rhoai3.findings-handoff/v1`

M1→M2 **seam** artifact (Architect `E-20260809T072752Z` · AD-H §16.7 AR-4.1/4.2).

| Layer | Path | Role |
|-------|------|------|
| Evidence store | `evidence/mta-findings.json` | Full analyzer envelope (may contain `codeSnip`) |
| Inventory | `evidence/entry-point-inventory.json` | Entry-point set (digest required on handoff) |
| Seam handoff | `evidence/findings-handoff.json` | Planner input index — **no snips** |
| Partition (optional) | `migration/story-endpoint-partition.json` | Story→endpoint map; conservation gated when present |

## Shape

```json
{
  "schema": "rhoai3.findings-handoff/v1",
  "emitted_at": "RFC3339Z",
  "evidence": { "path": "evidence/mta-findings.json", "sha256": "…" },
  "inventory": {
    "path": "evidence/entry-point-inventory.json",
    "sha256": "…",
    "endpoint_count": 42
  },
  "rules": [
    {
      "rule_id": "…",
      "category": "mandatory|optional|…",
      "effort": 1,
      "incident_count": 3,
      "description": "bounded analyzer text (≤240 chars)",
      "disposition": "apply|false_positive|needs_review|opaque_exception",
      "loci": [{ "path": "…", "line": 12 }]
    }
  ],
  "totals": {
    "violations": 32,
    "by_category": { "mandatory": 10 },
    "inventory_endpoints": 42
  },
  "ack_obligation": "…"
}
```

## Invariants

- **AR-4.1:** `inventory` REQUIRED; sha256 must match file; emit refuses if inventory missing.
- **AR-4.1:** When `story-endpoint-partition.json` exists, union of story endpoints =
  inventory `entry_points` (no silent drop / no duplicates).
- **AR-4.2:** Every rule has non-empty `description` + allowed `disposition`.
  Opaque IDs (`description` starts with `opaque:`) must use `opaque_exception` or
  `needs_review` — planners must not invent semantics.
- Bytes scale with rule/locus **cardinality**, never evidence-store snip density.
- Absolute size cap: 65536 bytes (emit + gate).
- Ratio: `size(handoff) / size(evidence) < 0.25`.
- Forbidden keys anywhere: `codeSnip` / snip-like fields.

## Tools

```bash
python3 .hermes/skills/analysis/scan-with-mta/scripts/emit-findings-handoff.py /projects/modernized
python3 .hermes/skills/analysis/scan-with-mta/scripts/check-findings-handoff.py /projects/modernized
```

Emit runs after normalize in `mta-analyze-legacy.sh` **and** after inventory exists
(dispatch order: inventory → analyze/emit, or re-emit after inventory).
