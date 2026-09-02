---
name: assert-retrievable-tree
description: >
  Use on the M3 stamp card (--check-only) and again before writing M4
  PROVISIONAL_ACCEPT — refuse unless src/ and pom.xml are committed against
  HEAD. An M3 story-complete is not the harvest; the stamp card is. M4 still
  refuses a dirty tree. Do not dest-push. Do not treat the tree as an M5
  candidate SHA. Dirty .env, profile home, .hermes/home, and secrets are
  excluded from this refuse. Do not use for pinned-gate evidence
  (assert-pinned-gates-ran), domain parity (check-domain-parity), or
  verdict-token lint (check-release-readiness).
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; git
metadata:
  author: rhoai3-harness-team
  version: "1.1.0"
  hermes:
    tags:
    - gates
    - m4
    category: gates
    kind: guidance
---
# Retrievable dest tree at stamp and M4

Architect `142524ZA` / AMEND `101242ZA`. M3 story-complete is not the
harvest. The stamp card is. M4 still refuses dirty `src/` / `pom.xml`.

## When to Use

- Stamp card: `--check-only` before `kanban_complete` (no verdict file).
- M4 is about to write `PROVISIONAL_ACCEPT` (writes the verdict file).
- **Not** an M5 ship SHA. **Not** a dest-push. **Not** dest-7 (blocked
  tree is evidence; do not dest-commit it by hand).

## Procedure

Stamp (no `evidence/verdicts/` write):

```bash
python3 "${HERMES_SKILL_DIR}/scripts/assert-retrievable-tree.py" \
  --check-only /projects/modernized
```

M4 (before `assert-pinned-gates-ran` when both are pinned):

```bash
python3 "${HERMES_SKILL_DIR}/scripts/assert-retrievable-tree.py" /projects/modernized
```

Refuse when `src/` or `pom.xml` is missing, the root is not a git work
tree, or `git status --porcelain -- src pom.xml` is non-empty. On M4
pass, write `evidence/verdicts/assert-retrievable-tree.json` (`ship: false`).
Do not commit. Do not dest-push.

## Pitfalls

- Completing M4 with untracked `src/test` that the M4 worker just wrote.
- Treating a dirty `.env` as this refuse — that path is out of scope.
- Treating an M3 story `kanban_complete` as the harvest.
