# Card ↔ sidecar digest cross-assert

**Authority:** Operator `E-20260812T061639Z`; Architect `E-20260812T061718Z`.

## Law

Before emitting or accepting an unsigned `migration/acks/ack-request-<story>.yaml`
for a card, the create/regen path **MUST** assert:

`card Body digest (AR-4.3)` == `sha256(live typed body sidecar)`.

Mismatch ⇒ **REFUSE** (do not emit ack-request; do not sign).

## Why

Ack-regen previously asserted file↔ack consistency but never card↔sidecar.
Fresh cards minted before a body restamp kept dead digests in the card markdown
while ack-requests cited live sidecars — Dispatch would digest-refuse on first
worker check (C5 FAIL / SIGN WITHHELD 2026-08-12).

## Tooling

```bash
python3 .hermes/skills/harness/auditability-repeatability/scripts/assert-card-body-digest-match.py \
  . --task-id <task_id> --body migration/bodies/m3-s-NNN.json
```

Wired into `create-m3-implementer.sh` after ack-request emit (fail-closed).
