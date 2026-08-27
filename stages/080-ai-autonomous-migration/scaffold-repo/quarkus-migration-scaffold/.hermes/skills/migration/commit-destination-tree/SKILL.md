---
name: commit-destination-tree
description: >
  Use after the last M3 product write and before M4 — commit dest pom.xml,
  src/, and README from this card's files_writable with a one-shot git -c
  identity so assert-retrievable-tree can PASS. Do not git config. Do not
  dest-push. Do not Signed-off-by. Do not commit evidence/, .hermes/,
  .specify/, target/, or .env. Do not use on M4 VERDICT (the judge must not
  edit the defendant). Do not dest-commit dest-7's blocked tree.
license: Apache-2.0
compatibility: Linux seat; git
metadata:
  author: rhoai3-harness-team
  version: "1.0.0"
  hermes:
    tags:
    - migration
    - m3
    category: migration
    kind: guidance
---
# Stamp the dest product tree (M3 harvest)

Architect `101242ZA`. M4 must not commit. Each M3 story must not commit.
This card is the named harvest between last M3 and M4.

## Paths

- **Mutate (dest tree):** `pom.xml`, `src/`, `README.md` listed on this
  card's `files_writable`.
- **Invoke, do not mutate:** `git` with one-shot `-c user.name` /
  `-c user.email`. Do not `git config`. Do not dest-push.
- **OBJECT:** `evidence/`, `.hermes/`, `.specify/`, `target/`, `.env`.
  Derived output stays inside the dest tree grant. Do not widen
  `K2_ALLOW_ROOT`.

## When to Use

- This card is `M3 STAMP_DESTINATION_TREE`.
- **Not** M4. **Not** dest-push. **Not** dest-7 (that block is evidence).

## Procedure

Write-set is this card's `files_writable` only (union of M3 product paths).

```bash
python3 "${HERMES_SKILL_DIR}/scripts/commit-destination-tree.py" \
  /projects/modernized \
  --files pom.xml src/main/java/... README.md
python3 .hermes/skills/gates/assert-retrievable-tree/scripts/assert-retrievable-tree.py \
  --check-only /projects/modernized
```

`--check-only` must PASS before `kanban_complete`. If it fails,
`kanban_block`. Do not `git add -A`. Do not `git config`. Identity is
`git -c user.name='Hermes Kanban' -c user.email='kanban@hermes.local'`.

## Pitfalls

- Restoring the commit to M4 (dest-5).
- Clearing dest-7's M4 block to make the tree look green.
- Writing `evidence/verdicts/` on this card — that is M4's leaf, not the stamp.
