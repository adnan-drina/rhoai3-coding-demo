# M2 corpus (O-M2CORPUS)

Standing archived-roadmap re-lint with **live M2 roadmap-lint argv parity**.

## Why this exists

A golden wipe / pod reset destroys uncommitted RED `roadmap.md` + briefs
that exercised new gates (O-SEATBUDGET / O-STORYKIND / O-PORTDERIVE /
coverage / fabrication). Without a committed corpus, those failure classes
cannot regress-test `roadmap-lint.py` or `m2-compose.py` changes.

Symmetric with `plan-corpus/` (O-PLANCORPUS) for M3 plans.

## Live argv set (mandatory)

Outer-loop M2 gate:

```text
roadmap-lint.py migration/roadmap.md migration/findings-inventory.md \
  /projects/legacy migration/architecture-profile.md
```

## Cases

| id | source | expect | signals |
|----|--------|--------|---------|
| `v4-m2-lintx2-10790d6` | v4 M2 lint×2 FAIL @ `10790d6` / `20260803T110142Z` | RED | coverage, O-SEATBUDGET, O-STORYKIND, O-PORTDERIVE, fabrication, briefs, stories(S-FND) |

Each case carries `SOURCE.txt`, `EXPECTED_LINT.txt` (live snapshot), M1
inputs (`findings-inventory.md`, `architecture-profile.md`), briefs, and a
minimal `legacy/` tree for fabrication cross-checks.

## Run

```bash
bash .hermes/harness/m2-corpus-lint.sh
bash .hermes/harness/m2-corpus-lint.sh --case v4-m2-lintx2-10790d6
```

Host preflight: `bash scripts/track-b/v10-m2-corpus-gate.sh`.
