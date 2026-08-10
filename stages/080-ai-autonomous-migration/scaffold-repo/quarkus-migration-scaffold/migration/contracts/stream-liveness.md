# Stream liveness split (Architect E-20260810T145240Z / AD-009 §3.2a)

**Status:** binding proving-min  
**Peer:** `lost-turn-block.md`

## Rule

| Timer | Default | Meaning |
|-------|---------|---------|
| Time-to-first-chunk (TTFC) | **90s** (band 60–120s) | Zero chunks since request start → treat as lost/dead stream |
| Inter-chunk stale | **900s** | After first chunk, long thinking / compose may continue |

Raising inter-chunk to 900s alone is correct for slow compose. **Zero-chunk
must not wait 15 minutes** before kill.

## Hermes gap (typed)

Current Hermes exposes a single provider knob `stale_timeout_seconds` used for
both TTFC and inter-chunk (`Stream stale … no chunks received`). Tip keeps
`stale_timeout_seconds: 900` for inter-chunk / thinking.

Until Hermes adds a distinct TTFC knob, Lead/Monitor **MUST** apply the 90s
TTFC band operationally:

```bash
python3 .hermes/home/scripts/check-stream-liveness.py . --task-id t_xxx --ttfc-sec 90
```

Exit `2` ⇒ TTFC breach (stamp `lost_turn` / consider `environmental_provider`
primary when stream-stale / Broken pipe). Does not MiniMax.

## Forbidden

- Forever-`running` with frozen transcript and empty expected write set
- Collapsing zero-chunk waits into wall-fit / story-too-big
