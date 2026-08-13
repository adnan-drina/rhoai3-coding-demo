# Partition-coverage gate (M2a exit)

**Status:** binding ·
**Lint:** `.hermes/skills/sdd/check-spec-readiness/scripts/check-partition-coverage.py`

## Why

Story counts vary across runs. Without a whole-partition check, “which count is
correct” is unanswerable. This gate makes partitions **provably VALID**; count
variance becomes measured data.

## When

| Phase | Rule |
|-------|------|
| **M2a exit** | Fail-closed before M2a `kanban_complete` / before M2b dispatch |
| **Create-path** | Tip-sync + R0 needle; run before next M2a |
| **Live mid-campaign** | `--retro` evidence only — no re-plan of an armed M3 wave |

## Checks

1. **Endpoint coverage** — inventory HTTP entry_points (denominator = **runtime inventory count**, never a specimen constant )
 each map to **exactly one** story (via story `files` / body `files_in_scope`
 owning the controller file, or explicit `endpoints` lists). Package remaps
 come from `migration.yaml` `path_rewrites` / discovery — not hardcoded roots.
 Specimen fixtures only with `--allow-specimen-fixture`.
2. **No file overlaps** — non-`pom.xml` paths claimed by two stories → INVALID.
3. **MTA** — when `evidence/mta-findings.json` present, each rule id is in some
 story `rules` or partition `mta_oos` / `findings_oos`; missing findings file →
 not INVALID (checked as skipped).
4. **Compose** — per-story wall-fit / operand-class / dep-order remain create-time
 gates; this gate is the whole-partition verdict.

Body match is **exact** `identity.story_id` only .
Path-substring binding (e.g. partition `S-002` → `m3-s-002a.json`) is forbidden —
split stories must appear as their own partition rows (`S-002a` / `S-002b`).

Related create-time stamps (same bind): `stamp-body-dependencies.py`
(`dependencies:` block) and `stamp-destination-inventory.py` (`destination_inventory`
ref).

## Verdict

`VALID` | `INVALID` (gaps listed) | `INCONCLUSIVE` (missing inputs / no files).

Receipt schema: `rhoai3.partition-coverage/v1` via `--write-receipt`.

```bash
python3 .hermes/skills/sdd/check-spec-readiness/scripts/check-partition-coverage.py /projects/modernized \
 --write-receipt evidence/receipts/partition-coverage/latest.json
```
