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
| `event_id` | yes | Immutable id (`evt_…`); auto-stamped by helper |
| `monitor_event_id(s)` | no | Cite Monitor `migration/monitor-events.jsonl` ids; unmatched ⇒ INCONCLUSIVE |
| `reconstructed` | forbidden | Must not be true — reconstructed A/B ⇒ INCONCLUSIVE |

## Append helper

```bash
bash .hermes/home/scripts/log-intervention.sh A findings_handoff_land "emit+check wired into mta-analyze"
bash .hermes/home/scripts/log-intervention.sh B copy_payload "thin M2" '{"phase":"M2","task_id":"t_xxx","monitor_event_ids":["mon_…"]}'
```

## Audit

```bash
# Board-side reviewer tool. Not shipped in this scaffold (hermeticity:
# a deployed seat has no link to the authoring repo). Set the path explicitly:
python3 "${HARNESS_BOARD_TOOLS:?set to the board .wake/tools dir}/audit-interventions.py" /projects/modernized
```

Log **as interventions happen**, classified A/B at the moment — do not reconstruct
after the fact for campaign measurement (AD-010 finding 7 /
`E-20260809T113120Z`).
