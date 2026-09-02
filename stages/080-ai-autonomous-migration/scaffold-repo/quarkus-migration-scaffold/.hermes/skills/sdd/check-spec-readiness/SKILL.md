---
name: check-spec-readiness
description: Before kanban_create — lint SDD specs, story bodies (typed BODY_* codes), and partition coverage (HTTP 1:1 via story.endpoints as METHOD /path, dest_file 1:N with supersede; refuse invented HTTP paths vs inventory; K4 dest_file round-trip REFUSE dest-9 Application.java/GreetingResource.java; refuse AC HTTP tokens that diverge from endpoints; refuse mvn test whose pom parent has no test-toolchain claim). Do not use to mint Kanban children or assemble M3 bodies (K4 converter is .hermes/kernel/k4_convert.py).
license: Apache-2.0
compatibility: Linux seat; Python 3.11+; reads migration/ specs and bodies
metadata:
  author: rhoai3-harness-team
    version: "1.7.8"
  hermes:
    tags:
    - sdd
    - m2
    category: sdd
    kind: guidance
---
## When to Use

- Before `kanban_create()` — **lint only**.
  Do not pin this leaf on the card. Pin `--skill paved-road-m2`; this
  checker loads via `skill_view` from `steps.json`. There is no
  phase-attach matrix (`E-20260822T120850Z`).
- After the typed partition is written — prove coverage (HTTP 1:1, dest_file
  1:N with supersede) with `check-partition-coverage.py`.
  This skill does **not** author Path-A `partition.json` and does **not**
  stamp bodies. Typed M3 bodies come from `.hermes/kernel/k4_convert.py`.
  Skill **`plan-migration-partition`** is the producer that writes
  `evidence/partition.json`; coverage also accepts
  `evidence/briefs/partition.json`. A missing file names every path looked at.
- **M2 PLAN is the named consumer of M1 attachments:** before partition,
  `hermes kanban show` the parent M1 id, read `kanban_attachments` (paths under
  `$HERMES_HOME/kanban/attachments/<m1-id>/`) **and**
  `evidence/findings-handoff.json`. M1 metadata path lists are not the
  findings. Do not plan from metadata alone.
- **A-8 `story.endpoints` (read this before planning):** each HTTP story
  declares `endpoints: ["GET /api/foo", ...]` (METHOD + path, or path-only).
  Coverage is `story.endpoints` ∩ inventory `http_method`+`http_path`/`symbol`,
  1:1. Do not join inventory `file` to dest write-set. Missing field is
  `endpoints_uncovered`, not a secret schema.
- When a body's `exit_criteria`, `files_in_scope`, or `operand_count` changed —
  these are the fields the gates refuse on.
- **Not** for creating `.specify/` or installing `specify-cli` —
  `init-spec-workspace`. **Not** for minting Kanban children from
  `tasks.md` PATH_TOKEN (OBJECT). Authority is the typed partition.
  Assemble/stamp/oracles under `.hermes/_park/` are retired (K4 + Operator
  GO `155455Z`).


# SDD readiness (pattern-steals + §S.6)

## Procedure

M2 PLAN starts by reading the parent M1 card's attachments by id (native
`kanban_attachments` / `$HERMES_HOME/kanban/attachments/<m1-id>/`) together
with `evidence/findings-handoff.json`. Do not plan from M1 metadata path
lists. Then lint:

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
# M2 complete — speckit actually ran (Operator 123401ZO §4; dest-8 missing tasks.md REFUSE)
python3 "${HERMES_SKILL_DIR}/scripts/assert-m2-speckit-conformance.py" "$ROOT"
# mint assemble / assert-mint-oracles: deleted with _park/mint (K4 converter)
```

`check-readiness.sh` already runs `check-ordering.py` (§S.6) and
`check-kanban-body.py` — run the body lint standalone only to scope it with
`--body`. Idle (pass) when no SDD / body artifacts exist yet.

## Contracts

- This skill (pattern-steals + kanban-body live here; no `governance/` folder)
- **A-8:** partition stories that own HTTP declare `story.endpoints` as
  `METHOD /path` (or path-only) **before** planning — not only after the
  coverage refusal. See When to Use.
- Acceptance that needs a file (health → `pom.xml`; `proves` paths) must
  appear in that story's `files_writable`. Unsatisfiable acceptance is
  `kanban_block`, not complete. `mvn -q test` that does not name a file
  still needs a parent that owns `pom.xml` **and** claims
  `check-test-toolchain` (`implicit_pom_parent_vacuous` otherwise).
- AC HTTP tokens must match `story.endpoints` (`stale_ac:`). dest-6 left
  `/api/greeting` in prose after correcting the field; coverage now
  reads the text. Invented-routes shares `http_join` with coverage
  (`/api` + inventory is dest layering). dest-actual-prefix is `stale_ac`,
  not a second invented-routes join (Operator `062245ZO`).
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
- `scripts/assert-m2-speckit-conformance.py` — M2 complete: non-empty `tasks.md` **and** official-log A-gate (`assert-card-performed.py`); `k4_convert --tasks`. Workflow-run.json is **not** provenance (Architect `170112ZA` / `170540ZA`; dest-8 missing tasks.md REFUSE)
- `scripts/assert-card-performed.py` — A: official log has Hermes skill-load `┊ 📚 skill  speckit-specify` (or dest-13 `sdd/speckit-specify`); dest-9 M2 `t_af875a24` must REFUSE; `specify workflow run speckit` is not the dispatch; path mention / grep / cat of SKILL.md is not follow
- `scripts/assert-card-performed.test.py` — dest-9 fixture REFUSE; no skill follow REFUSE; synthetic workflow-run exit 0 REFUSE; skill-load PASS; path/grep/cat REFUSE
- `scripts/assert-partition-invented-routes.py` — constitution VII invented HTTP paths
- `scripts/assert-partition-invented-files.py` — dest-cite sibling (type-inventory dest_file); not the W3 close (`191845ZA`)
- `.hermes/kernel/k4_roundtrip.py` — dest_file in the typed slice vs write-set dest Java; dest-9 `Application.java` / `GreetingResource.java` REFUSE (`194048ZA`)
- `scripts/partition_story_consistency.py` — stale AC vs endpoints; implicit pom parent
- `scripts/check-interface-closure.py` — interface closure Class-A gate
- `scripts/assert-dependency-closure.py` — Class-A dependency closure
- `scripts/check-spec-readiness-selftest.py` — batch-3 negative controls

Libraries: `.hermes/lib/` (`generated_sources.py`,
`inventory_io.py`, `path_maps.py`, `supersede.py`, `http_join.py`,
`specimen_agnostic.py`). Not a skill. Java type walk:
`analysis/inventory-legacy-surface/scripts/type_graph.py`.

Mint assemble/stamp/oracles: deleted (`.hermes/_park/mint/`). K4 converter:
`.hermes/kernel/k4_convert.py`. Dest-POM honesty:
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
  `## Non-Goals` is not required on every `.md`. An **empty** Non-Goals heading
  is FAIL (state a non-goal or omit the heading).
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
  `supersede_incomplete`);
  health-unsatisfiable REFUSE `fixtures/partition-health-unsatisfiable/`
  (`acceptance_unsatisfiable:polish:pom.xml`).
  Invented-routes REFUSE `fixtures/partition-invented-health/`
  (`invented_route:T020_POLISH:/q/health`); dest-6 stale-AC REFUSE
  `fixtures/partition-dest6-grounded/` (invented-routes PASS via `http_join`;
  coverage `stale_ac:us1_greeting:/api/greeting`,
  `implicit_pom_parent_vacuous:us1_greeting:setup`); PASS
  `fixtures/partition-dest6-aligned/` (AC matches `GET /greeting`,
  setup claims `check-test-toolchain`).
  dest-8 M2 bypass REFUSE `fixtures/m2-speckit-bypass-dest8/`
  (`assert-m2-speckit-conformance.py` exit 1, `M2_SPECKIT_BYPASS`, no `tasks.md`).
  dest-9 dest_file invented REFUSE `.hermes/kernel/fixtures/k4-dest9-invented-files.json`
  (`k4_roundtrip.py` exit 1, `Application.java` and `GreetingResource.java`;
  `Greeting.java` dest twin does not REFUSE). dest-9 live partition (dest_file
  absent, invented dest Java in `files_writable`) REFUSE convert `K4_DEST_FILE`
  via `.hermes/kernel/fixtures/k4-dest9-live-partition.json` (`k4_roundtrip.py`
  exit 1 at convert; `dest_file_invented` skip STANDS). Sibling
  `assert-partition-invented-files.py` stays dest-cite, not this close.
  `/q/health` is not a grounding exception. Empty `endpoints` is legal
  scaffolding iff the story names no HTTP path.
  Default partition path is `evidence/partition.json` then
  `evidence/briefs/partition.json`; missing names every path looked at.
  Findings **presence** at create is enough (`mta_status=checked`);
  `story.rules` / `mta_oos` are not a create-path join
  (Architect `E-20260817T154012Z`). Addressed findings stay M1 handoff
  and M5 WC-5 rescan.
- Mint-oracles (`assert-mint-oracles.py`) were `_park/mint/` residue and are deleted. Not an exit of this lint skill.
- Exit condition for the KEEP gate: every KEEP command above exits 0 **and** reports a
  non-zero artifact/body count. All-idle output on a populated workspace is a
  path defect to fix before dispatch.
