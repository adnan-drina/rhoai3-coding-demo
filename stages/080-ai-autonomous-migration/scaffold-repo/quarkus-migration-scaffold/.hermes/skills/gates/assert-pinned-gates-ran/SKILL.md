---
name: assert-pinned-gates-ran
description: >
  Use before writing M4 PROVISIONAL_ACCEPT — refuse unless every gate skill
  pinned on the M4 card has a verdict under evidence/verdicts/ naming it, or
  an explicit evidence/verdicts/refusals/<gate>.json with ran false and a
  reason. Silence fails. specimen-n/a: no DB is a refusal reason, not a skip.
  Do not require G-1 kill-ratio, Owner/Pet, or a runnable DB as proof a gate
  ran. Do not idle-exit-0 on missing artifacts. Do not use for domain
  measurement (check-domain-parity) or verdict-token lint
  (check-release-readiness).
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; git not required
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - gates
    - m4
    category: gates
    kind: guidance
---
# Pinned gates must have run (or refused)

Architect `142524ZA`. Run **before** writing `PROVISIONAL_ACCEPT`.

## When to Use

- M4 is about to write `evidence/verdicts/` with `PROVISIONAL_ACCEPT`.
- A gate is on the M4 card `skills` list (`check-spec-readiness`,
  `check-domain-parity`, `check-release-readiness`, this skill,
  `assert-retrievable-tree`).
- **Not** to invent Owner/Pet, kill-ratio, or DB floors. **Not** idle-pass
  when artifacts are missing.

## Procedure

Pass the M4 card's skills list. Missing list is fail-closed.

```bash
python3 "${HERMES_SKILL_DIR}/../assert-retrievable-tree/scripts/assert-retrievable-tree.py" \
  /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/assert-pinned-gates-ran.py" /projects/modernized \
  --skills "${M4_CARD_SKILLS:?missing M4 card skills}"
```

`--skills-file` or `--card-json` (object with `skills`) are equivalents.
Env `M4_CARD_SKILLS` is the same comma list.

For each pinned gate leaf: require either a JSON under `evidence/verdicts/`
(not `refusals/`) that names it (`gate` / `skill` / `name` / filename stem),
**or** `evidence/verdicts/refusals/<gate>.json` with `"ran": false` and a
non-empty `reason`. Example reason: `specimen-n/a: no DB`.

This script does not write `PROVISIONAL_ACCEPT`. On pass, if this leaf is
pinned, it writes `evidence/verdicts/assert-pinned-gates-ran.json` so its
own pin is evidenced.

## Pitfalls

- Reading a missing `evidence/verdicts/` tree as skip.
- Treating `specimen-n/a: no DB` as a skip instead of a refusal file.
- Running this before `assert-retrievable-tree` when that leaf is also pinned.
