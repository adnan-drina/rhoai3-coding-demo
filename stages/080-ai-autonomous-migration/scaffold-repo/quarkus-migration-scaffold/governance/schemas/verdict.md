# Verdict artifact schema (AD-H §18 / §18.0)

**Status:** binding · lints in `check-release-readiness`  
**Home:** `evidence/verdicts/*.json` (also preflight when it carries a verdict)

## Fields

| Field | Rule |
|-------|------|
| `phase` | `M3`…`M5` / `factory` |
| `verdict` | `PROVISIONAL_ACCEPT` \| `ACCEPT` \| `REFUSE` \| `INCONCLUSIVE` — M4 uses **`PROVISIONAL_ACCEPT`** (literal); M5 full ship uses **`ACCEPT`** only. Bare `ACCEPT`+`accept_kind=provisional` is **refused**. |
| `accept_kind` | Optional mirror only (`provisional` / `full`) — **must not** be the sole signal |
| `implicated_substrate` | On shared-substrate G-4 fail: list of path/FQN |
| `reopen_story_ids` | Derived = §11.3 closure ∩ substrate for non-full-ACCEPT stories; required when substrate shared |
| `g1_kill_ratio` | Interim: `pending_threshold` only. `PASS` forbidden until threshold pinned |
| `g1_kill_ratio_waiver` | Typed Operator waiver for M5 `ACCEPT` while ratio is `pending_threshold` |
| `ship` | Never for `PROVISIONAL_ACCEPT` or `INCONCLUSIVE`. M5 `ACCEPT` only |
| `routing` / `failure_class` | §18.3; composition reopen → `reopen_story` or `blocked` |
| `g4_mode` | **Required on G-4 gate outputs** — `SAMPLE` until equivalence bar (AD-H §G.4 / ER#2 F8). Do not omit; do not claim equivalence oracle on SAMPLE. |

Closure map home: `evidence/slices/closure-map.json` (operand for §18.0 ¶4).

## Examples

```json
{"phase":"M4","verdict":"PROVISIONAL_ACCEPT","g1_kill_ratio":"pending_threshold","ship":false}
```

```json
{"phase":"M5","verdict":"ACCEPT","g1_kill_ratio":"pending_threshold","g1_kill_ratio_waiver":true,"ship":true}
```

```json
{
  "phase":"M5",
  "verdict":"REFUSE",
  "gate":"g4_runtime_parity",
  "story_id":"S-1",
  "prior_verdict":"PROVISIONAL_ACCEPT",
  "implicated_substrate":["com.example.shared.Entity"],
  "reopen_story_ids":["S-1","S-2"],
  "routing":"reopen_story"
}
```
