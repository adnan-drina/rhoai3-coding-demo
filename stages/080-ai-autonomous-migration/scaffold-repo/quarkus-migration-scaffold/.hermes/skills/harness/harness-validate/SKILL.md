---
name: harness-validate
description: Validate harness contracts and pins
version: 1.2.0
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


# Harness validate

## Procedure

From the modernized project root:

```bash
bash "${HERMES_SKILL_DIR}/scripts/validate.sh"
```

Or, with skills on `external_dirs`, load this skill and run the script above.
Does **not** require a provisioned specimen.


## Verification

- Scripts under `scripts/` exit 0 on a healthy seat.
- Conformance lint passes for this skill.
