---
name: native-kanban-alignment
skill-group: Demo Environment
applies-to:
  - stages/080-ai-autonomous-migration/scaffold-repo/**
---

# Native review, attachments, and K4 translation — do not retire G1–G4

Operator `112748ZO` measured 32 custom M4 scripts and zero uses of
native `request-review` / `attach` / owned payload→card translation.
Native-first is a default with a **stated exception**. G1–G4 domain
parity (Maven, PIT, HTTP) has no general-tool substitute. Do not delete
those gates on a line count.

Official: `.agents/skills/hermes-kanban/` — `review` is a first-class
state; `kanban_request_review` is a worker terminator; `block` is
escalation not review; attachments 25 MB/file; `kanban swarm` is
parallel workers + verifier + synthesizer.

## Non-negotiable

1. **Keep G1–G4.** Domain receipts (`write-receipt.py`,
   `check-verdict-routing.py`, O1–O3 HTTP) stay. Native `review` does
   **not** replace runtime oracles.
2. **Board lifecycle:** after **honest** M3/M4 work, prefer
   `kanban_request_review` so Review dest-cites from `review`. Do not
   `kanban_complete` dest-4 `t_9acd47cb` on PASS JSON minted during the
   verdict card (`112249ZA` item 7; Review `112352ZR`).
3. **Attachments:** M1/M2 KEEP evidence listed in run metadata MUST also
   `kanban attach` (≤25 MB). PVC paths stay (dual-write). Not dest-4
   mid-run. A dest wipe must not be the only copy of harvest.
4. **K4:** derivation stays in `k4_convert.py`. Graph create is
   **named, tested mint-writer** (`.hermes/kernel/k4_mint.py` → CLI
   `hermes kanban create`). Native-first is
   **not** LLM-first (Operator `113305ZO`): `decompose` **can** express
   serial `parents` (retract “cannot do serial”) and still must **not**
   mint dest cards (`temperature=0.3`, skills are not an input). OBJECT
   `kanban swarm` for serial T0.
5. **Fact vs judgement (Operator `113305ZO`):** mechanical facts
   (exec bits, digests, schema, coverage counts) stay **code**. Genuine
   judgement may move to a skill+LLM **only** if a deterministic check
   validates the output. Do not convert the ≥12 pure-logic M4 gates
   this sitting; dest-5 first.
6. Do **not** retire gates on the audit alone. dest-4 M4 `t_9acd47cb`
   is **done** via worker `kanban_complete` (contaminated; do not
   reopen). Land review/attach/mint-writer on golden / dest-5.
7. **G-4 tokens must agree.** Refusal `N/A` and verdict
   `g4_hook=INCONCLUSIVE` cannot both stand (Operator `114101ZO`).
   SAMPLE-floor `INCONCLUSIVE` is honest (`check-release-readiness`).
   `N/A` is OBJECT for a live `GET /greeting` — G-4 applies; compare
   referent vs dest or leave INCONCLUSIVE. M5 reads the refusal file.
   Gate K M4-O1/O2/O3 are dest HTTP oracles (`090119Z`); they are not
   G-4. Implementing `quarkus-smallrye-health` on the verdict card
   taints O1. CLOSE still waits dest-5.
