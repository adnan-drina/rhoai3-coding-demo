---
name: ground-in-harvest
description: Refuses IMPLEMENT packets and commits that write code without a brief id and a legacy locus. Use when a packet claims done or lists writes, when linting commit messages, or when generated code must be traced back to the legacy source it came from.
license: Apache-2.0
compatibility: Linux seat; Python 3.11+
metadata:
  author: rhoai3-harness-team
  version: "1.2.0"
  hermes:
    tags:
    - harness
    - orchestration
    category: harness
    kind: enforcement
---
## When to Use

- Before dispatching an M3 / implementer packet: it must name a task id, a
  brief or story id, and a `legacy_locus` (`path:lines`, or a
  `staging/` · `harvest/` · `legacy-at-3` path) — otherwise the transform is
  invention, not migration.
- Before committing destination code: lint the commit message file so the
  subject carries task id + brief/story id + legacy locus.
- Whenever a packet claims `status: done` or declares `writes[]` /
  `files_touched[]` with no locus — that is the invent-without-locus shape
  and must REFUSE.
- On a `kind: redesign` packet with neither `targetContract` nor `ac_ids`
  and no locus.
- This lints *citation*, not *behaviour*. Whether the ported code is correct
  is `check-domain-parity` (G-1…G-4); whether the run is replayable is
  `record-run-evidence`.

# Grounded generation (AD-H §17)

## Contracts

- This skill is the grounded-generation contract (AD-H §17). There is no `governance/` folder.

## Procedure

1. **Lint the packet corpus.** Scans `evidence/tasks/*.json` and
   `evidence/kanban/*.json`, selecting objects whose `phase` is `M3`/`IMPLEMENT`,
   whose `role` is implementer/worker, or whose `kind` is
   implement/harvest/redesign. Exits 0 as idle when none are present.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/check-citation.py" /projects/modernized
```

2. **Lint the commit message before committing.** Reads the file and applies
   the same three assertions.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/check-citation.py" /projects/modernized \
  --commit-msg /tmp/commit-msg.txt
```

3. **Exempt only genuinely trivial work.** Set `trivial: true` (or
   `formatting_only`) on the packet, or pass `--trivial` with `--commit-msg`.
   The task id stays mandatory; brief and locus are waived. Do not use this
   to smuggle a real transform past the gate.

4. On exit 1, fix the packet or the message — do **not** invent a plausible
   locus. If the legacy referent genuinely cannot be resolved, raise a typed
   `needs_input` BLOCK.

Citation lints do **not** replace domain-gate oracles (G-1…G-4).

## Pitfalls

- Inventing symbols, paths, or capabilities not present in harvest/findings.
- Softening a citation miss into prose instead of typed stop.
- Editing the write-fence or harvest locus to clear a refusal (DD5).

## Verification

- `check-citation.py <root>` prints
  `OK: ground-in-harvest citation passed (N IMPLEMENT packet(s))` — assert
  **N ≥ 1**.
- **Silent-failure catch:** `OK: no IMPLEMENT packets / commit-msg — citation
  lint idle` is exit 0 while proving nothing. An idle line during M3 means
  the packets are not where the lint looks (`evidence/tasks/`,
  `evidence/kanban/`), not that they are grounded.
- Commit-message run prints `OK: commit message citation passed`; a missing
  task id, brief/story id, or locus prints `FAIL: commit message missing …`
  and exits 1.
- Negative control before trusting a pass: a packet carrying `writes[]` with
  no `legacy_locus` must exit 1 with
  `invent-without-locus refused (AD-H §17)`.
- A `legacy_locus` that is neither a `path:lines` form nor a
  staging/harvest reference is rejected by value, not merely by presence.
