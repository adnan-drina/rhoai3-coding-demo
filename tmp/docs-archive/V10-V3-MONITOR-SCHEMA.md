# V10 V3 monitor schema (O-MONSCHEMA)

Use this schema in **every** Hermes/Qwen activity + ~10m general note written to
`tmp/V10-V3-MONITOR.md` **only** (do **not** mirror into `tmp/KAI-WAVE4-REVIEW.md`
— Opus fingerprints MONITOR.md under Standing Rule #2). Goal: assess AI agent
**correctness and efficiency** without re-parsing `/tmp` by hand.

## Required per active seat (cheapest high-value subset)

| Field | Source | Example |
|-------|--------|---------|
| `tools: read/write/edit/glob/bash` | `/tmp/oc-T-*.json` via `v10-monitor-seat-enrich.py` | `read=12 write=0 edit=0 glob=1 bash=15` |
| `time_to_first_write` (s + % budget) | same | `none yet / 1800s` or `45s (3% of budget) via write` |
| `sensor_delta before→after` | failure-sig + supervisor GREEN/RED | `22→2` or `?—GREEN` |

## Also log when known

- `budget_used: elapsed/cap`
- `rc` / `signal` / `killer` (separate)
- `guard_refusals[]` (O-SFIXLOOP REFUSED, O-T6d, …)
- `last_utterance` (one line)
- `discarded` + whether sensor had improved (O-SFIXKEEP)
- `escalation_cause` + converted vs burned
- Hermes: seat wall-clock, `hermes_rc`, tool/msg counts if session log present

## Helper (host or after `oc cp` / `oc exec cat`)

```bash
# Pull latest oc json for task T-003 then enrich:
oc exec -n wksp-ai-developer "$POD" -- cat /tmp/oc-T-003.json > /tmp/oc-T-003.json
python3 scripts/track-b/v10-monitor-seat-enrich.py \
  --json /tmp/oc-T-003.json \
  --err /tmp/oc-T-003.err \
  --failure-sig /tmp/failure-sig-before-T-003.txt \
  --budget-s 1800 --task T-003 --role qwen
```

Dual bash loop (`tmp/v10-v3-dual-monitor-loop.sh`) calls this automatically each
activity/general tick when oc artifacts exist.

## Activity note template

```markdown
### Activity — Qwen — <ts> — <event>
**Actor path:** …
**tools:** read=N write=N edit=N glob=N bash=N
**time_to_first_write:** … / budget=…
**sensor_delta:** …
**rc/signal/killer:** …
**efficiency:** <one derived line>
**Bank?** …
— Qwen-monitor
```
