---
name: grounded-generation
description: Ground generation in harvest and findings
version: 1.1.0
author: rhoai3-harness-team
license: Apache-2.0
platforms: [linux]
metadata:
  hermes:
    tags:
    - harness
    - orchestration
    category: harness
---
## When to Use

Use this skill when its name matches the active phase or gate.


# Grounded generation (AD-H §17)

## Contracts

- `migration/contracts/grounded-generation.md`
- Consult order + citation + anti-invention (Architect; Operator ACK pending)

## Procedure

Run the checks below.

## Checks

```bash
# Packet citation + invent-without-locus (idle when no IMPLEMENT packets)
python3 "${HERMES_SKILL_DIR}/scripts/check-citation.py" /projects/modernized

# Lint a commit message file (task + brief + legacy locus for non-trivial)
python3 "${HERMES_SKILL_DIR}/scripts/check-citation.py" /projects/modernized \
  --commit-msg /tmp/commit-msg.txt
```

Citation lints do **not** replace domain-gate oracles (G-1…G-4).


## Verification

- Scripts under `scripts/` exit 0 on a healthy seat.
- Conformance lint passes for this skill.
