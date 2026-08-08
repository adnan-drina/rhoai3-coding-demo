---
name: mta-analysis
description: >
  Run MTA/kantra analysis for M1 ANALYZE (and M5 findings refresh) against the
  frozen legacy@3.x harvest_referent. Use when starting M1, regenerating
  findings, or before a findings-delta comparison. Never invent --source filters.
---

# MTA analysis (legacy@3.x)

## When to use

- M1 ANALYZE needs a fresh analyzer run on the **legacy@3.x** tree
- M5 (or any findings-delta step) needs findings regenerated against the same
  referent the harvest compared to

Do **not** load this skill for unrelated coding tasks — progressive disclosure
keeps it off the token budget until M1/M5.

## What you are analyzing

Input is `harvest_referent` from `migration/derived/legacy-at-3.json`
(**legacy@3.x**), never the read-only 2.x mount alone. Comparing findings or
harvest fidelity to 2.x while the contract is Boot-3 is wrong.

Prerequisites: derivation manifest present (load `derive-legacy-boot3` if
missing), then the deterministic gate:

```bash
bash .hermes/skills/derive-legacy-boot3/scripts/check-manifest.sh
# or, with that skill loaded: bash "${HERMES_SKILL_DIR}/scripts/check-manifest.sh"
```

## Procedure

Run the bundled mechanism (self-contained: reads env + files; no CLI args):

```bash
bash "${HERMES_SKILL_DIR}/scripts/mta-analyze-legacy.sh"
```

Requires `JVM_MAX_MEM` and Java 21 on `PATH` (`JAVA_HOME_21` preferred).
Optional overrides: `MTA_OUT_DIR`, `MTA_JSON_OUT`.

If `mta-cli`/`kantra` are missing, the script runs `kantra-ensure` (lazy PVC
install under `/projects/.tools/kantra`). Findings are normalized
(`normalize-findings.py`) to `rhoai3.mta-findings/v1-provisional`
(`codeSnip` required) and schema-checked (`validate-findings-schema.py`) —
see `migration/schemas/mta-findings.md`.

The script expands `migration.yaml` `analysis.targets` into repeated
`--target` flags, writes JSON findings, and overwrites the output dir.

## Why these flags (do not "simplify" them away)

### Never pass `--source`

Passing `--source` or `--target` restricts the engine to rules that carry a
matching label. Rules **without** those labels are excluded.

- Documented in **MTA 7.1** Rules Development Guide (verbatim caveat).
- **Silent in MTA 8.1/8.2** Rule metadata docs — the sentence was dropped.
- Confirmed on an **MTA 8.2 run** (Track B, 2026-07-27): `--source` excluded
  source-labelless rules (including custom contract rules) and narrowed the set.

**AD-003 amendment A:** the harness invocation is `--target` only, from
`migration.yaml` `analysis.targets`. Do not re-add `--source` because the CLI
help lists it or because a profile once showed a source technology name.

### Targets come from `migration.yaml`

Do not invent target labels at the prompt. The analysis contract lives in
`migration.yaml` `analysis.targets`. Editing the invocation without updating
that file creates two homes for one fact.

### Java 21 and `JVM_MAX_MEM`

Kantra analyzer bundles declare `osgi.ee=JavaSE-21`; under Java 17 the provider
can hang without a clear error. `JVM_MAX_MEM` unset presents the same way.
Both are required environment facts, not optional tuning.

## Pitfalls

- Do not analyze `/projects/legacy` when the manifest says a derived
  `harvest_referent` — you will mix Boot-2 API surface into Boot-3 findings.
- Do not pass `--source` "to be more precise."
- Do not relocate this reasoning into `AGENTS.md` — conventions stay
  always-on; this procedure loads only when M1/M5 needs it.
