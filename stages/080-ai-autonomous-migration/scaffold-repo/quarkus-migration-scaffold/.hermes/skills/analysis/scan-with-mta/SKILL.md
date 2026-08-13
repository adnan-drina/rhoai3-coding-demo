---
name: scan-with-mta
description: Runs kantra against the legacy@3.x referent and emits normalized findings plus the bounded M2 handoff. Use at M1 ANALYZE, at M5 for the findings delta, or when findings-handoff.json is missing, stale by digest, or failing schema validation.
license: Apache-2.0
compatibility: Linux seat; kantra CLI and Java 21; network for rule bundles
metadata:
  author: rhoai3-harness-team
  version: "1.2.0"
  hermes:
    tags:
    - analysis
    - m1
    category: analysis
    kind: guidance
---
# MTA analysis (legacy@3.x)

## When to Use

- M1 ANALYZE needs a fresh analyzer run on the **legacy@3.x** tree
- M5 (or any findings-delta step, G-3) needs findings regenerated against the
  same referent the harvest compared to
- M2 is blocked because `evidence/findings-handoff.json` is missing or its
  `evidence.sha256` no longer matches `evidence/mta-findings.json`
- `evidence/mta-findings.json` exists but fails
  `validate-findings-schema.py` (wrong schema, missing `codeSnip`/`category`)

Preconditions — all four, or the script dies before analyzing:
`evidence/derived/legacy-at-3.json` (skill `derive-legacy-boot3`),
`migration.yaml` with non-empty `analysis.targets`, Java 21 on `PATH`,
`JVM_MAX_MEM` set. `evidence/entry-point-inventory.json` must also exist
before the handoff step (AR-4.1) — skill `inventory-entry-points`.

Not this skill: entry-point enumeration (`inventory-entry-points`), harvest
derivation (`derive-legacy-boot3`), gate scoring (`check-domain-parity`).

**Orchestration:** start M1 via skill `dispatch-phase`
(`dispatch-phase.sh M1`) so Kanban owns the task, role, budget, and recovery.
Do **not** invoke this script from a Lead/operator detached shell as the
migration control plane — that yields `tasks=0` and cannot stamp
`orchestration=hermes_native`.

Do **not** load this skill for unrelated coding tasks — progressive disclosure
keeps it off the token budget until M1/M5.

## What you are analyzing

Input is `harvest_referent` from `evidence/derived/legacy-at-3.json`
(**legacy@3.x**), never the read-only 2.x mount alone. Comparing findings or
harvest fidelity to 2.x while the contract is Boot-3 is wrong.

Prerequisites: derivation manifest present (load `derive-legacy-boot3` if
missing), then the deterministic gate:

```bash
bash .hermes/skills/migration/derive-legacy-boot3/scripts/check-manifest.sh
# or, with that skill loaded: bash "${HERMES_SKILL_DIR}/scripts/check-manifest.sh"
```

## Procedure

One entry point — self-contained, reads env + files, takes no CLI args:

```bash
bash "${HERMES_SKILL_DIR}/scripts/mta-analyze-legacy.sh"
```

What it does, in order (each step dies non-zero on failure):

1. Resolve the CLI: `/projects/.tools/kantra/kantra`, else `kantra`/`mta-cli`
   on `PATH`, else run `~/.local/bin/kantra-ensure` (lazy ~690MB PVC install)
   and re-resolve. Keeps `mta-cli` as a symlink alias to `kantra`.
2. Assert `evidence/derived/legacy-at-3.json` + `migration.yaml`, export
   `JAVA_HOME_21`, assert `JVM_MAX_MEM`.
3. Read `harvest_referent` from the manifest; write-probe it and, if frozen,
   clone to `/projects/.derived/legacy-at-3-mta-input` (JDT/m2e needs to write
   `.project`). Expand `analysis.targets` into repeated `--target` flags.
4. `cd "${MTA_RUN_CWD}"` (default `/projects/.tools/mta-run`) and run
   `analyze --input … --output "${MTA_OUT_DIR}" --target … --json-output
   "${MTA_JSON_OUT}" --overwrite`. Non-zero tool exit is soft if
   `<out-dir>/output.json` exists (it is copied to the JSON out).
5. `normalize-findings.py <json> <cli> <targets-csv> legacy-at-3:<sha256>` →
   envelope `rhoai3.mta-findings/v1-provisional` with `execution_evidence`
   and `codeSnip` preserved; then `validate-findings-schema.py <json>`.
   See `governance/schemas/mta-findings.md`.
6. `emit-findings-handoff.py <root> <findings> <handoff>` → the M1→M2 seam
   `evidence/findings-handoff.json` (`rhoai3.findings-handoff/v1`: rule IDs,
   category, bounded `description`, `disposition`, loci, digests — **no**
   `codeSnip`), then `check-findings-handoff.py <root>` as the gate.
   See `governance/schemas/findings-handoff.md`.

Defaults: `MTA_OUT_DIR=migration/mta-analyze-out`,
`MTA_JSON_OUT=evidence/mta-findings.json`, both under the project root.

AD-H §16.7 / AR-4.1–4.2: inventory digest **required** before emit; each rule
carries bounded `description` + `disposition`; optional
`story-endpoint-partition.json` conservation gate.

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
- Do not run `mta-cli analyze` with cwd inside `/projects/modernized` —
  analyzer-lsp uses `-configuration ./` and drops Equinox dirs in cwd
  (script forces `MTA_RUN_CWD`, default `/projects/.tools/mta-run`).
- Frozen `legacy-at-3` is not a valid analyze input for JDT/m2e (needs a
  writable `.project`). The script clones to `legacy-at-3-mta-input` when
  the harvest referent is not writable.
- Do not relocate this reasoning into `AGENTS.md` — conventions stay
  always-on; this procedure loads only when M1/M5 needs it.


## Verification

- Last stderr line is
  `OK: findings → … handoff → … report → …` and the script exits 0.
  Stdout is one JSON object
  `{script,ok,findings,handoff,report_dir,analyze_input}` (UPLIFT-2).
- `evidence/mta-findings.json`: `schema: rhoai3.mta-findings/v1-provisional`,
  `execution_evidence.analyzer_ran: true`, `execution_evidence.rule_set`
  matching `migration.yaml` `analysis.targets`, `execution_evidence.input_digest`
  = `legacy-at-3:<manifest sha256>`. Re-run `validate-findings-schema.py` for
  the assertion: every incident carries `uri`, `lineNumber`, `message`,
  `codeSnip`; every violation carries `category`.
- `evidence/mta-analyze-out/output.json` exists (raw analyzer report kept
  beside the normalized envelope).
- `evidence/findings-handoff.json` passes
  `python3 "${HERMES_SKILL_DIR}/scripts/check-findings-handoff.py" .` — exit 0.
  It re-hashes both `mta-findings.json` and `entry-point-inventory.json` and
  fails on digest drift, size > 65536 B, handoff/evidence ratio ≥ 0.25, any
  `codeSnip`/`raw` key, a `rule_id` absent from the evidence store, a missing
  `description`, a `disposition` outside
  {`apply`,`false_positive`,`needs_review`,`opaque_exception`}, or an
  `opaque:` description not dispositioned as opaque/needs_review.
  Exit 1 = typed BLOCK (product/gate residue); exit 2 = harness path defect —
  do not paper over it.
- Silent-failure catch: `violations` = `{}` (handoff gate reports
  `handoff.rules empty`) or an empty `rule_set` means targets never expanded or
  the analyzer produced nothing — treat as INCONCLUSIVE, not "clean".
