# M3 seat corpus (O-M3SEATCORPUS)

L2 real-artifact coverage for **seat behaviour** guards
(`O-M3ALLSTALL`, `O-M3TOOLHIST`, future `O-M3EVENTSTALL`).

Plan-corpus / m2-corpus cover plan and roadmap text. This tree covers
OpenCode/Hermes session JSONL that the stall and tool-histogram logic
actually parse.

## Cases

| id | source | expect | pins |
|----|--------|--------|------|
| `s01-w1-zerowrite-185509` | live `m3-S01-w1` @18:55–18:57Z (post-GO) | `writes=0`, `read≥5` | O-M3TOOLHIST / O-M3ALLSTALL |

Consumed by instruments: `m3seatcorpus-zerowrite-ok`.
