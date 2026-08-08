---
name: grounded-generation
description: >
  AD-H §17 grounded code generation — consult order, commit/packet citation
  lint, and cheap refuse of invent-without-locus. Use for M3 IMPLEMENT and when
  validating task completion metadata.
---

# Grounded generation (AD-H §17)

## Contracts

- `migration/contracts/grounded-generation.md`
- Consult order + citation + anti-invention (Architect; Operator ACK pending)

## Checks

```bash
# Packet citation + invent-without-locus (idle when no IMPLEMENT packets)
python3 "${HERMES_SKILL_DIR}/scripts/check-citation.py" /projects/modernized

# Lint a commit message file (task + brief + legacy locus for non-trivial)
python3 "${HERMES_SKILL_DIR}/scripts/check-citation.py" /projects/modernized \
  --commit-msg /tmp/commit-msg.txt
```

Citation lints do **not** replace domain-gate oracles (G-1…G-4).
