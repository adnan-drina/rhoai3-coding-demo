---
name: scaffold-invariants
description: >
  Deterministic scaffold lints that protect Hermes load order and taxonomy
  homes. Use after scaffold edits or in harness-validate.
---

# Scaffold invariants

## No Hermes context override (AD-001 / AD-002)

`.hermes.md` / `HERMES.md` must not exist — they shadow `AGENTS.md`.

```bash
bash "${HERMES_SKILL_DIR}/scripts/check-no-hermes-context-override.sh"
```
