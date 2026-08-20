---
name: check-spec-readiness
description: Before kanban_create or M3 dispatch — lints SDD specs and story bodies, refuses with typed BODY_* codes. Run assert-mint-oracles when assembling or creating an M3 body (refs path-sha, Hermes task_id, SR-13 discriminating exit).
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; reads migration/ specs and bodies
metadata:
  author: rhoai3-harness-team
  version: "1.5.1"
  hermes:
    tags:
    - sdd
    - m2
    category: sdd
    kind: guidance
---
## When to Use

- Before `kanban_create()` and before dispatching any M3 body — **lint only**.
  The phase-attach matrix pins this skill to every phase M1–M5.
- After a `evidence/bodies/*.json` is assembled — validate that one body with
  `--body <path>` at create time, not only the whole corpus.
- After `handover-mint.py` writes the partition **receipt** — prove coverage
  (endpoint coverage, no write overlap) with `check-partition-coverage.py`.
  This skill does **not** author Path-A `partition.json`. `stamp-body-dependencies.py`
  may append inheritance-reachable dest twins onto an existing story frame
  (V34-5); it does not invent stories.
- When a body's `exit_criteria`, `files_in_scope`, or `operand_count` changed —
  these are the fields the gates refuse on.
- Before holder mint (`mint-m3-hermes.md`) or assemble — `assert-mint-oracles.py` (refs,
  Hermes `task_id`, SR-13/L2a discriminating exit: the test proving this
  card's AC lives in this write-set; test-shaped cmds name `proves` tests
  in this write-set).
- **Not** for creating `.specify/`, installing `specify-cli`, or authoring
  Path-A partitions — `init-spec-workspace` / `handover-mint.py`.


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
python3 "${HERMES_SKILL_DIR}/scripts/check-operand-count.py" /projects/modernized
# L2 / SR-13 — refs + Hermes task_id + discriminating exit
python3 "${HERMES_SKILL_DIR}/scripts/assert-mint-oracles.py" /projects/modernized \
  --body evidence/bodies/m3-s-003.json
# M2 exit — partition VALID as a whole (lint of the handover receipt)
python3 "${HERMES_SKILL_DIR}/scripts/check-partition-coverage.py" /projects/modernized \
  --write-receipt evidence/receipts/partition-coverage/latest.json
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

- `scripts/check-readiness.sh` — corpus SDD readiness + ordering + body lint
- `scripts/check-kanban-body.py` — W2 §6.1 typed body vocabulary (`--body` optional)
- `scripts/check-ordering.py` — §S.6 story/spec ordering
- `scripts/check-surgical-scopes.py` — AR-4.4 write-set + class-legal / dual-oracle
- `scripts/check-semantic-exits.py` — optional `semantic_families` family lint
- `scripts/check-operand-count.py` — measured operand_count / wall-fit
- `scripts/check-partition-coverage.py` — M2 partition VALID receipt
- `scripts/check-interface-closure.py` — interface closure Class-A gate
- `scripts/check-jdbc-deps-preflight.py` — R-M3.11 JDBC deps preflight
- `scripts/assert-dependency-closure.py` — Class-A dependency closure
- `scripts/assert-mint-constraints-complete.py` — mint constraints complete
- `scripts/assert-mint-oracles.py` — L2 refs / task_id / SR-13 discriminating exit
- `scripts/assert-constraints-preserved.py` — constraints survive amend
- `scripts/assert-quarantine-tombstones.py` — quarantine tombstone presence
- `scripts/assert-dest-inventory-hardinvoke.py` — dest inventory hard-invoke
- `scripts/register-quarantine-tombstone.py` — mutate: register tombstone
- `scripts/stamp-body-dependencies.py` — mutate: `--write` dest-path deps; HTTP sources = A-8 inventory `file`s (collect-all) + Java `legacy_locus`; dest-only kinds (setup/foundational/polish) with non-Java locus and unresolved dest Java may stamp `dependencies=[]`; unowned project `extends`/import dest twins join this write-set **and** the owning story's partition frame (V34-5; walk in `type_graph.py`, including star-import packages); generated types stamp `provider: generated` (not assigned, not pre-exists); `DEPENDENCY_HOLE` lists dest domain-leaf/repo holes that remain unowned (`intra_package_maps` when stamped)
- `scripts/type_graph.py` — library: in-prefix Java type walk without a `--body` (M1 `inventory-type-graph.py` reuses it)
- `scripts/generated_sources.py` — library: classify generator output (path / `@Generated` / plugin); no name patterns
- `scripts/stamp-destination-inventory.py` — mutate: `--write` dest inventory
- `scripts/specimen_agnostic.py` — library helper (not an agent entry point)
- `scripts/assert-partition-topological-order.py` — mint-time ancestor/descendant import order (coverage is not topology)
- `scripts/relocate-descendant-import-writesets.py` — move dest types that import descendant-owned types onto polish
- `scripts/assert-setup-datasource-driver.py` — dest datasource properties need a matching `quarkus-jdbc-*` on the dest pom
- `scripts/assert-dest-pom-extensions.py` — dest pom declares required-extensions `kind` (plugin vs dependency)

Do **not** invoke DD4-retired R-M3.5/7 stubs (`check-persistence-bom.py`,
`check-compile-deps-preflight.py`) — they refuse; extensions are story-owned.
## Pitfalls

- Treating SDD readiness green as permission to `/speckit-implement` (AD-S
  stop: never implement via Spec Kit).
- Skipping JDBC preflight before first `repository/jdbc/**` write.
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
  When `evidence/type-inventory.json` is present, every `dest_file` must
  be in some story write-set (`types_uncovered` otherwise). Missing file
  is skip, not INVALID.
  Findings **presence** at create is enough (`mta_status=checked`);
  `story.rules` / `mta_oos` are not a create-path join
  (Architect `E-20260817T154012Z`). Addressed findings stay M1 handoff
  and M5 WC-5 rescan.
- `assert-mint-oracles.py --body` exits 0 only when refs resolve, `task_id` is
  a Hermes card id (or `--skip-task-id` pre-create), and every test-shaped
  `cmd` names `proves` test source(s) in this `files_writable` (L2a — the
  test proving this card's AC). An
  unrelated dest `src/test` file must not pass. `--corpus DIR` exits 0 only
  when **every** body fails at least one oracle.
- Exit condition for the gate: every command above exits 0 **and** reports a
  non-zero artifact/body count. All-idle output on a populated workspace is a
  path defect to fix before dispatch.
