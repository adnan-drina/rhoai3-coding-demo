---
name: scan-with-mta
description: Runs the pinned MTA CLI 8.2 against the frozen original legacy source (freeze-migration-input analysis copy) with the custom canary ruleset, records a full-provenance producer receipt, and emits normalized findings plus the bounded handoff. Use at M1 ANALYZE, for the destination rescan that closes obligations (M3/M4), or when findings are missing, stale by digest, or failing schema validation. A kantra fallback is recorded as provisional and non-admissible.
license: Apache-2.0
compatibility: Linux seat; MTA CLI 8.2 (kantra provisional); Java 21; network for rule bundles
metadata:
  author: rhoai3-harness-team
  version: "2.0.0"
  hermes:
    tags:
    - analysis
    - m1
    category: analysis
    kind: guidance
    paths:
      reads: ["/projects/modernized/.derived/frozen-input", "/opt/mta-cli", "/projects/.tools/kantra", "/home/user/.local/bin"]
      writes: ["/projects/modernized/evidence/mta", "/projects/modernized/evidence/mta-findings.json", "/projects/modernized/evidence/findings-handoff.json", "/projects/modernized/evidence/required-extensions.json", "/projects/modernized/evidence/producers", "/projects/modernized/verification/mta-rescan", "/projects/.tools/mta-run"]
---
# MTA analysis (frozen original source)

## When to Use

- M1 ANALYZE, fourth step of `paved-road-m1`, after `inventory-legacy-surface`,
  before `assemble-evidence-bundle`.
- Destination rescan after every loop step (`mta-rescan-destination.sh`,
  run by `fix-until-green/scripts/run-verify.sh`; its incidents are the
  work list's `incident` items) and the M4 `mta_rescan` assertion.
- `evidence/findings-handoff.json` missing or its `evidence.sha256` no
  longer matches `evidence/mta-findings.json`; findings failing
  `validate-findings-schema.py`.

Preconditions the one script dies without: `evidence/producers/freeze.json`
with an `analysis_copy` (byte-identical, verified by
`assert-frozen-input-intact.py` **before** analysis), `migration.yaml`
with non-empty `analysis.targets`, Java 21, `JVM_MAX_MEM`, and
`evidence/entry-point-inventory.json` (`inventory-legacy-surface`).

Not this skill: structural inventory, build evidence, or the planner.
Do **not** pin this leaf on the card; it loads via `skill_view` from
`paved-road-m1` `steps.json`.

## What you are analyzing

The **frozen original source**: the freeze receipt's `analysis_copy`
(`/projects/modernized/.derived/frozen-input`), never `/projects/legacy`
directly (read-only; JDT/m2e needs to write `.project`) and never a
derived Boot 3 tree. `derive-legacy-boot3` is an execution-side
transformation and is not an M1 input (SAD §5.1).

## Procedure

```bash
bash "${HERMES_SKILL_DIR}/scripts/mta-analyze-legacy.sh" --root /projects/modernized
```

`--root` is required for isolated rehearsal (`rehearse-legacy.sh --root /tmp/rehearsal`). Without it the script walks up from its own path and can write findings into the dest clone that ships the skill.

In order (each step dies non-zero on failure):

1. **Resolve the CLI as a capability probe.** Product order: the pinned
   MTA CLI 8.2 (`MTA_CLI_HOME`, default `/opt/mta-cli`), then kantra
   (`/projects/.tools/kantra`, PATH, `kantra-ensure`). After each
   candidate, `~/.local/bin/kantra-assert-exec` runs on the realpath
   install prefix; present-but-unusable falls through. The checker
   requires ELF analysis binaries and jdtls shebang launchers; it skips
   shebang files under `rulesets/` (product test fixtures, not helpers).
   No version or provider-RPC handshake.
2. `assert-frozen-input-intact.py` — the analysis copy still matches the
   frozen manifest.
3. `analyze --input <copy> --output … --target … --rules
   .hermes/planning/mta-rules --json-output … --overwrite`, cwd
   `/projects/.tools/mta-run`. **Never `--source`** (see below). The
   custom ruleset carries `rhoai3-canary-00001` labelled for every
   `migration.yaml` target.
4. `normalize-findings.py` → `rhoai3.mta-findings/v1-provisional` with
   `execution_evidence.input_digest = frozen:<source sha256>`, rules
   coverage sidecar, static report pointer. `assert-mta-rescan.py
   --snapshot-m1`, `validate-findings-schema.py`.
5. `emit-mta-receipt.py` → `evidence/producers/mta.json`: exact binary
   (path, realpath, sha256, size), install-prefix provider/analyzer
   artifacts with digests, product pin, argv and mode, targets, bundled
   and custom ruleset digests, input digest, exit status, output digest,
   canary result, and `admissible` — true only when `.hermes/pins.json`
   `mta_cli.artifact_sha256` equals the executed binary. **Unpinned or
   kantra = provisional, non-admissible** (admission BLOCK `MTA_PROVENANCE`).
6. `assert-mta-canary.py` names a missing canary at M1 time
   (`CANARY_MISSING` blocks admission regardless).
7. `emit-findings-handoff.py` (refuses unless `assert-frozen-root-pair.py`
   passes), `check-findings-handoff.py`, `emit-required-extensions.py`
   (legacy pom from the analysis copy).

## Why these flags (do not "simplify" them away)

### Never pass `--source`

Passing `--source` or `--target` restricts the engine to rules that carry
a matching label. Rules **without** those labels are excluded
(documented in MTA 7.1 rules development; silent in 8.1/8.2 docs;
confirmed on an MTA 8.2 run 2026-07-27). The custom canary carries a
`konveyor.io/target=<t>` label for every configured target; adding a
target to `migration.yaml` requires adding the label to
`.hermes/planning/mta-rules/rhoai3-canary.yaml`, or the canary stops
firing and admission is INCONCLUSIVE. `emit-mta-receipt.py` refuses an
argv containing `--source`.

### Targets and rules come from `migration.yaml`

`analysis.targets`, `analysis.custom_rules`, `analysis.canary_rule_id`.
One home per fact.

### Java 21 and `JVM_MAX_MEM`

Analyzer bundles declare `osgi.ee=JavaSE-21`; under Java 17 the provider
can hang without a clear error. `JVM_MAX_MEM` unset presents the same way.

## Destination rescan (M3/M4)

```bash
bash "${HERMES_SKILL_DIR}/scripts/mta-rescan-destination.sh" /projects/modernized
```

Writes `verification/mta-rescan/findings.json` (append-only execution
evidence). `assert-obligations-closed.py` and `assert-mta-rescan.py`
consume it; the sealed planning artifacts are never touched (the work list is rebuilt from the rescan by `build-worklist` / `advance.py`).

## Pitfalls

- Analyzing `/projects/legacy` or a derived tree: the receipt's input
  digest would not be the frozen source digest and admission fails.
- Passing `--source` "to be more precise".
- Running analyze with cwd inside `/projects/modernized` (Equinox dirs
  land in cwd; the script forces `MTA_RUN_CWD`).
- Treating a kantra run as MTA 8.2: it is recorded, provisional, and
  blocks admission until the pinned artifact runs.

## Verification

- Last stderr line is `OK: findings → … receipt → … handoff → …` and the
  script exits 0; stdout is one JSON object.
- `evidence/producers/mta.json` passes the producer-receipt schema and
  says `admissible: true` only for the pinned artifact.
- `evidence/mta-findings.json`: `execution_evidence.analyzer_ran: true`,
  `rule_set` = `migration.yaml` targets, `input_digest` =
  `frozen:<source sha256>`; `assert-mta-canary.py` exits 0.
- `evidence/findings-handoff.json` passes `check-findings-handoff.py`;
  `evidence/required-extensions.json` is present with a non-empty
  `legacy_pom`.
- `scripts/scan-with-mta.test.py` proves the receipt provenance rules
  (pinned → admissible; kantra → provisional; `--source` refused) and the
  canary check on fixtures.

## Scripts

- `scripts/mta-analyze-legacy.sh` — the one M1 entry point (also the `ensure_cli` library)
- `scripts/assert-frozen-input-intact.py` — analysis copy == frozen manifest
- `scripts/normalize-findings.py`, `scripts/validate-findings-schema.py` — envelope
- `scripts/emit-mta-receipt.py` — full-provenance producer receipt
- `scripts/assert-mta-canary.py` — canary fired
- `scripts/assert-mta-rescan.py` — WC-5 rescan proof (M1 snapshot / M4)
- `scripts/emit-findings-handoff.py`, `scripts/check-findings-handoff.py` — M1→M2 handoff
- `scripts/emit-required-extensions.py` — T-3 extension set from findings + legacy pom
- `scripts/mta-rescan-destination.sh` — destination rescan for obligation closure
- `scripts/assert-ensure-cli-path.sh` — capability-probe selftest
- `scripts/emit-required-extensions.test.py`, `scripts/scan-with-mta.test.py` — selftests
