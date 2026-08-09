# Interventions ledger

**Path (binding):** `migration/interventions.jsonl` under the modernized project root
(`/projects/modernized/migration/interventions.jsonl` in Dev Spaces).

**Not** `.derived/cleanroom-e2e/interventions.jsonl` — that path was a clean-room
audit gap (Lead mis-cite, 2026-08-09).

## Row shape

One JSON object per line:

| Field | Required | Meaning |
|-------|----------|---------|
| `ts` | yes | UTC ISO-8601 |
| `class` | yes | `A` = harness fix (survives next specimen) · `B` = run nourishment (specimen-local) |
| `type` | yes | Short snake token |
| `detail` | yes | Human-readable what/why |
| extra | no | Optional keys (`phase`, `task_id`, `supersedes`, …) |

## Append helper

```bash
bash .hermes/home/scripts/log-intervention.sh A findings_handoff_land "emit+check wired into mta-analyze"
bash .hermes/home/scripts/log-intervention.sh B copy_payload '{"phase":"M2","task_id":"t_xxx"}'
```

Log **as interventions happen**, classified A/B at the moment — do not reconstruct
after the fact for campaign measurement.
