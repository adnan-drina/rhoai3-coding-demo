---
name: validate-contracts
description: Run the whole specimen-free harness lint suite before committing skills, contracts, fixtures
license: Apache-2.0
compatibility: Linux seat; Python 3.11+ and bash; runs specimen-free
metadata:
  author: rhoai3-harness-team
  version: "1.4.0"
  hermes:
    tags:
    - harness
    - orchestration
    category: harness
    kind: enforcement
---
## When to Use

- Before committing any change under `.hermes/skills/**`,
  `governance/contracts/**`, or `governance/fixtures/**` — this is the single
  run that exercises the whole harness at once.
- After adding, renaming, or re-categorizing a skill: the R-SK conformance
  lint (frontmatter, `category` = parent directory, required headings in
  order, ≤200 lines, description ≤60 chars, attach/invoke admission) and the
  R-SK.5 specimen-literal ban run only from here.
- On a fresh or relocated seat before the first phase dispatch — it proves
  skill discovery, bundle resolution, and ack/fence wiring **without a
  provisioned specimen**.
- When a gate refuses a card and you cannot tell whether the gate or the card
  is wrong: this replays each gate against known-good *and* known-bad
  fixtures, so a broken gate shows up as a `FAIL:` on the negative control.
- Not an acceptance signal for migrated code. Real G-1…G-4 oracles need a
  provisioned specimen — use `check-domain-parity` / `check-release-readiness`.

# Harness validate

## Procedure

Takes no arguments; resolves the scaffold root from its own location and
accumulates a return code rather than aborting at the first failure.

```bash
bash "${HERMES_SKILL_DIR}/scripts/validate.sh"
```

Or, with skills on `external_dirs`, load this skill and run the script above.

Each `== … ==` banner is one section. In order, it asserts:

1. No `.hermes.md` / `HERMES.md` anywhere in the tree (either name shadows
   `AGENTS.md` in Hermes first-match-wins context load).
2. SDD readiness and `§S.6` ordering — including the negative control that an
   IMPLEMENT task with `replan: true` is refused.
3. Domain-gate admission; G-1 PIT `mutations.xml` parse plus the missing-file
   refusal; AR-3.6 probe-vs-acceptance operand separation.
4. MTA findings schema against the known-good fixture; entry-point inventory
   smoke over a synthetic HTTP + non-HTTP source.
5. Role authority — ack presence per phase, cross-role write refusal,
   self-ACK and impersonating-comment refusals, F2 write-fence lock + seat
   probe + out-of-scope/deny-path refusal.
6. Grounded generation — invent-without-locus and commit-message refusals,
   plus the good-packet pass.
7. Validation/release gates — verdict routing (`INCONCLUSIVE` must not ship,
   `PROVISIONAL_ACCEPT` must not ship, unpinned kill-ratio, substrate reopen
   sets), factory↔M5 coupling, candidate→promote, SCOPED_ACCEPT.
8. Workspace recovery (F4): a dirty tree refuses requeue; `--action restore`
   yields a clean tree.
9. `external_dirs` relocation, kanban-body refs (including non-hex `sha256`
   prose), story sizing `operand_count` + wall-fit, wall-as-terminal
   exit-eval.
10. Checkpoint lag, the `src/test` test-compile stamp gate and its
    fixture-only skip, body-digest immutability, and AD-H §19 provenance.
11. R-M3.6 `dependency_wait` hold stamp (R-M3.5/7 persistence BOM retired DD4).
12. CS-7 bundle exists-assert and CS-9 skill conformance (see below), AD-011
    overlay presence, R-M3.9 wall-fit refusal at 42 operands @3600s,
    A-4/A-5/A-8 handover-mint from tasks.md.

Two sub-lints are also runnable standalone:

```bash
python3 "${HERMES_SKILL_DIR}/scripts/check-skill-conformance.py" --all \
  --root /projects/modernized/.hermes/skills
python3 "${HERMES_SKILL_DIR}/scripts/check-bundle-manifest.py" \
  --root /projects/modernized/.hermes/skills \
  --bundles /projects/modernized/.hermes/home/skill-bundles
bash "${HERMES_SKILL_DIR}/scripts/check-no-hermes-context-override.sh"
```

`check-skill-conformance.py` also accepts explicit skill directories, and
`--flat-ok` / `--skip-r-sk9` / `--skip-specimen` to narrow the run. Specimen
literals may be exempted only via
`references/r-sk5-specimen-keep.txt` (`relpath` or `relpath:lineno`, ledger
EID in a trailing comment).

## Pitfalls

- Judging success by the last `OK:` line — check `$?` and grep for `FAIL:`.
- Running only guidance categories and skipping `.hermes/skills/harness/`
  (EX-3: that is where dispatch/validate/fence packs live).
- Expecting this suite to admit a specimen migration (use domain gates).
- Gitignoring `migration/` to hide a resurrected directory — SR-8a. Fix the
  writer (`MTA_OUT_DIR` defaults to `evidence/mta/`). Unattributed paths fail.

## Verification

- Final stdout line is `OK: validate-contracts passed` and exit code is 0.
- **Silent-failure catch:** sections do not abort — a mid-run failure only
  surfaces as `validate-contracts FAILED` on stderr plus exit 1. Never judge by
  the last `OK:` line alone; check `$?`, and grep the run for `FAIL:`.
- Negative controls must be present, not just absent failures. A healthy run
  prints lines such as `OK: M2 refuses without m1-findings ack`,
  `OK: 5.1 gate-record issued when findings-handoff rc=0`,
  `OK: invent-without-locus refused`, and
  `OK: body digest mismatch refused`. If a negative control is missing from
  the output, that gate silently stopped refusing.
- CS-9 prints `CHECKED=<n> VIOLATIONS=0` with `<n>` equal to the number of
  `SKILL.md` files under the skills root; any violation is printed as
  `SKILL:RULE:detail`.
- CS-7 prints `BUNDLES=<n> VIOLATIONS=0` — every skill named in
  `.hermes/home/skill-bundles/*.yaml` resolves to a real `SKILL.md`.
