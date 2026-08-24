---
name: assert-retrievable-tree
description: >
  Use before writing M4 PROVISIONAL_ACCEPT — refuse unless src/ and pom.xml
  are committed against HEAD. Do not treat an M3 story-complete commit as a
  substitute. Do not dest-push. Do not treat the tree as an M5 candidate SHA.
  Dirty .env, profile home, .hermes/home, and secrets are excluded from this
  refuse. Do not use for pinned-gate evidence (assert-pinned-gates-ran),
  domain parity (check-domain-parity), or verdict-token lint
  (check-release-readiness).
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; git
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
# Retrievable dest tree at M4

Architect `142524ZA`. M4-authored tests must not stay untracked.

## When to Use

- M4 is about to write `PROVISIONAL_ACCEPT`.
- **Not** an M5 ship SHA. **Not** a dest-push.

## Procedure

Run **before** `assert-pinned-gates-ran` when both are pinned.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/assert-retrievable-tree.py" /projects/modernized
```

Refuse when `src/` or `pom.xml` is missing, the root is not a git work
tree, or `git status --porcelain -- src pom.xml` is non-empty. On pass,
write `evidence/verdicts/assert-retrievable-tree.json` (`ship: false`).
Do not commit. Do not dest-push.

## Pitfalls

- Completing M4 with untracked `src/test` that the M4 worker just wrote.
- Treating a dirty `.env` as this refuse — that path is out of scope.
