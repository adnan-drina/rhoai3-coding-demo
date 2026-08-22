---
name: check-spec-readiness
description: Before kanban_create — lint SDD specs, story bodies (typed BODY_* codes), and partition coverage (HTTP 1:1, dest_file 1:N with supersede). Do not use to mint Kanban children or assemble M3 bodies (those scripts live in .hermes/_park/mint until K4).
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; reads migration/ specs and bodies
metadata:
  author: rhoai3-harness-team
  version: "1.6.0"
  hermes:
    tags:
    - sdd
    - m2
    category: sdd
    kind: guidance
---
## When to Use

- Before `kanban_create()` — **lint only**.
  Pin this skill from the card `skills=` list; there is no phase-attach
  matrix (`E-20260822T120850Z`).
- After the typed partition is written — prove coverage (HTTP 1:1, dest_file
  1:N with supersede) with `check-partition-coverage.py`.
  This skill does **not** author Path-A `partition.json` and does **not**
  stamp bodies (`stamp-body-dependencies.py` lives in `.hermes/_park/mint/`).
- When a body's `exit_criteria`, `files_in_scope`, or `operand_count` changed —
  these are the fields the gates refuse on.
- **Not** for creating `.specify/` or installing `specify-cli` —
  `init-spec-workspace`. **Not** for minting Kanban children from
  `tasks.md` PATH_TOKEN (OBJECT). Authority is the typed partition.
  Mint-oracles / assemble scripts are `.hermes/_park/mint/` until K4.


# SDD readiness (pattern-steals + §S.6)

## Procedure

```bash
bash "${HERMES_SKILL_DIR}/scripts/check-readiness.sh"
# W2 §6.1 typed body vocabulary
python3 "${HERMES_SKILL_DIR}/scripts/check-kanban-body.py" /projects/modernized
# AD-H §16.9 / AR-4.4 — surgical write sets + endpoint exits
python3 "${HERMES_SKILL_DIR}/scripts/check-surgical-scopes.py" /projects/modernized
# AR-2.3–2.7 — semantic product exits for REST/persistence stories
python3 "${HERMES_SKILL_DIR}/scripts/check-semantic-exits.py" /projects/modernized
# Architect E-104925Z / E-110403Z — measured operand_count (phase-name REJECT)
python3 "${HERMES_SKILL_DIR}/scripts/check-operand-count.py" "$ROOT"
# M2 exit — partition VALID as a whole (1:N dest_file + HTTP 1:1)
python3 "${HERMES_SKILL_DIR}/scripts/check-partition-coverage.py" "$ROOT" \
  --write-receipt evidence/receipts/partition-coverage/latest.json
# mint assemble / assert-mint-oracles: .hermes/_park/mint/ (not this skill)
```

`check-readiness.sh` already runs `check-ordering.py` (§S.6) and
`check-kanban-body.py` — run the body lint standalone only to scope it with
`--body`. Idle (pass) when no SDD / body artifacts exist yet.

## Contracts

- This skill (pattern-steals + kanban-body live here; no `governance/` folder)
- `.hermes/skills/sdd/check-spec-readiness/references/sdd-ordering.md` (AD-S §S.6)
- `.hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md` (AR-4.4; T-8 class-legal + dual-oracle)
- skill `derive-story-oracles` (exit derivation; `semantic-exits.md` retired)
- `.hermes/skills/sdd/check-spec-readiness/references/story-scope-and-exit.md` (operand_count)
- skill `scan-with-mta` (MTA exception / findings schemas live with that skill)
- `scripts/check-kanban-body.py` (W2 §6.1 typed body vocabulary)

## Available scripts

KEEP (this skill):

- `scripts/check-readiness.sh` — corpus SDD readiness + ordering + body lint
- `scripts/check-kanban-body.py` — W2 §6.1 typed body vocabulary (`--body` optional)
- `scripts/check-ordering.py` — §S.6 story/spec ordering
- `scripts/check-surgical-scopes.py` — AR-4.4 write-set + class-legal / dual-oracle
- `scripts/check-semantic-exits.py` — optional `semantic_families` family lint
- `scripts/check-operand-count.py` — measured operand_count / wall-fit
- `scripts/check-partition-coverage.py` — M2 partition VALID receipt
- `scripts/check-interface-closure.py` — interface closure Class-A gate
- `scripts/assert-dependency-closure.py` — Class-A dependency closure

Libraries: `.hermes/lib/` (`generated_sources.py`,
`inventory_io.py`, `path_maps.py`, `supersede.py`, `http_join.py`,
`specimen_agnostic.py`). Not a skill. Java type walk:
`analysis/inventory-legacy-surface/scripts/type_graph.py`.

Mint assemble/stamp/oracles: `.hermes/_park/mint/` until K4. Dest-POM honesty:
`manage-quarkus-extensions/scripts/` (`assert-dest-pom-extensions.py`, JDBC /
datasource / generator uptake).

Do **not** invoke DD4-retired R-M3.5/7 stubs (`check-persistence-bom.py`,
`check-compile-deps-preflight.py`) — they refuse; extensions are story-owned.
## Pitfalls

- Treating SDD readiness green as permission to `/speckit-implement` (AD-S
  stop: never implement via Spec Kit).
- Skipping JDBC preflight (`manage-quarkus-extensions/scripts/check-jdbc-deps-preflight.py`) before first `repository/jdbc/**` write.
- Reading retired R-M3.5/7 persistence/compile preflight stubs as live gates.
- Treating any dest `src/test` file as proof a `mvn … test` exit can fail —
  L2a: name the proving test in this `files_writable`.

## Verification

- `check-readiness.sh` ends `OK: SDD readiness passed (N artifact(s) checked)`;
  each violation prints `FAIL: <relpath>: …` first. **Silent-failure catch:**
  `readiness lint idle` (N=0) while specs/bodies exist means the artifacts are
  not under the scanned roots — unproven, not passed.
- `check-kanban-body.py` prints `OK: Kanban body §6.1 checks passed (N body(ies);
  corpus|single-body)`. Failures are typed and stable: `BODY_SCHEMA`,
  `BODY_REF_UNKNOWN`, `BODY_REF_SHA256`, `BODY_REF_DIGEST`, `BODY_REF_MISSING`,
  `BODY_INLINE`, `BODY_SCOPE`, `BODY_SCOPE_DEST`, `BODY_EXIT`, `BODY_IDENTITY`,
  `BODY_G2`, `BODY_SIZE`. `BODY_REF_DIGEST` is the drift catch — a ref file
  changed after the body was minted.
- `check-surgical-scopes.py` → `OK: AR-4.4 surgical scopes (N M3 body(ies))`; it
  refuses an empty destination write set, one path owned by two bodies without
  `sequence_after`, and exit criteria drawn only from the compile-only set.
- `check-operand-count.py` → `OK: … operand_class=… operand_count=R measured=M
  max=…`; `R` must equal the measured write set, so a scope edit that forgets
  the count is refused rather than silently resized.
- `check-partition-coverage.py --write-receipt` leaves
  `evidence/receipts/partition-coverage/latest.json`
  (`schema: rhoai3.partition-coverage/v1`) with `verdict`, `gaps[]`,
  `http_endpoint_count`, `mta_status`. Only `VALID` exits 0.
  `INCONCLUSIVE` is not a pass: no story files, **or** findings file
  missing (`mta_status=skipped_missing` / gap `mta_skipped_missing`).
  When `evidence/type-inventory.json` is present, every **non-generated,
  not-superseded** `dest_file` must be in some story write-set
  (`types_uncovered` otherwise). A dest_file MAY be declared superseded
  (partition or story `supersedes`) by a named non-empty successor set;
  the old row is covered iff every successor is owned. Incomplete
  successor sets are gaps. Missing file
  is skip, not INVALID.
  Behavioural 1:N fixtures: named-set PASS
  `fixtures/partition-supersede-named-set/` (`check-partition-coverage.py` exit 0);
  bare-string REFUSE `fixtures/partition-supersede-bare-string/` (exit != 0,
  `supersede_incomplete`).
  Findings **presence** at create is enough (`mta_status=checked`);
  `story.rules` / `mta_oos` are not a create-path join
  (Architect `E-20260817T154012Z`). Addressed findings stay M1 handoff
  and M5 WC-5 rescan.
- Mint-oracles (`assert-mint-oracles.py --body`) live under `.hermes/_park/mint/` until K4 — not an exit of this lint skill.
- Exit condition for the KEEP gate: every KEEP command above exits 0 **and** reports a
  non-zero artifact/body count. All-idle output on a populated workspace is a
  path defect to fix before dispatch.
