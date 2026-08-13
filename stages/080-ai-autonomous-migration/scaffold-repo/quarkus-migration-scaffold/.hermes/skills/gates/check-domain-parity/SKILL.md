---
name: check-domain-parity
description: Measures the destination against the referent and emits G-1..G-4 ACCEPT/REFUSE/INCONCLUSIVE verdicts. Use at M4 for volume and substance, at M5 for findings delta and runtime parity, or when pinning a kill ratio or re-proving an edited evaluator.
license: Apache-2.0
compatibility: Linux seat; Maven and Java 21 for PIT and product tests
metadata:
  author: rhoai3-harness-team
  version: "1.2.0"
  hermes:
    tags:
    - gates
    - m4
    - m5
    category: gates
    kind: guidance
---
## When to Use

- **M4 needs fidelity evidence** — the destination tree must show G-1 mutation
  volume/substance (plus G-2 field conservation when the packet claims HARVEST)
  before an M4 verdict can cite anything measured.
- **M5 needs closure evidence** — after MTA re-scan and live acceptance: G-3
  (no finding present-but-asserted-resolved) and G-4 (referent vs destination
  status + body on the same scenario).
- **Pinning or re-pinning the G-1 kill ratio** from a live `mutationCoverage`
  report, or re-proving an edited evaluator against the admission fixtures.
- **Not this skill** when the question is whether a verdict token, phase
  `required_checks`, requeue, or ship claim is *legal* — that is
  `check-release-readiness`. This skill measures code against the referent and
  emits a gate verdict; it never decides what may advance, ship, or requeue.

# Domain gates (ours — AD-H)

Hermes owns orchestration. **We** own these deterministic fidelity checks
(AD-H §7). They are executables, not LLM judgement.

| ID | Vocabulary name | Failure mode (known-bad) |
|----|-----------------|--------------------------|
| G-1 | `characterization` | char_surface stub / hollow coverage |
| G-2 | `harvest-fidelity` | silently dropped obligation (field) |
| G-3 | `findings-delta` | finding present but asserted resolved |
| G-4 | `runtime-parity` | different status/body; identical 5xx = vacuous |

**G-4 mode (ER#2 F8 / AD-H §G.4):** gate outputs stamp `g4_mode: SAMPLE`.
This is **not** a behavioral-equivalence oracle. Full `ACCEPT` /
`release_qualified` needs referent-derived partitions, per-normalizer
permitted equivalence, and zero unverified entry points.

## Admission fixtures (W2 §10)

Specimen-free pairs under `governance/fixtures/admission/gN-<name>/`.

**Honesty bound:** green fixtures prove **parser + fixture shape**, not
toolchain-faithful admission. Live sensors (PIT dry-run on a specimen, running
apps for G-4) are a separate prove step — see
`governance/fixtures/admission/README.md`. Do not treat 12/12 as admission.

```bash
bash "${HERMES_SKILL_DIR}/scripts/run-admission.sh"
```

Expect ACCEPT / REFUSE / INCONCLUSIVE for each gate.

## Run a single gate evaluator

```bash
python3 "${HERMES_SKILL_DIR}/scripts/g1-characterization.py" /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/g2-harvest-fidelity.py" /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/g3-findings-delta.py" /projects/modernized
python3 "${HERMES_SKILL_DIR}/scripts/g4-runtime-parity.py" /projects/modernized
```

## G-1 volume floor — PIT dry-run (Research R1 / Architect ACCEPT)

Pin **`pitest-maven` 1.25.5** + **`pitest-junit5-plugin` ≥1.2.3** (declared
on the scaffold `pom.xml` pitest plugin); use **`-Dpit.dryRun=true`** (not
`+dryRun` feature). Referent needs **≥1 compilable test**; refuse zero-test
skip and `-DskipTests`. **No static-metric floor.**

**AR-3.6:** default PIT targets are **product** packages. Tooling-smoke probe
sources live under `examples/g1-volume-probe/` (relocated out of template `src/`;
`com.demo.harness.*` when copied for smoke). `G1_OPERAND=tooling_smoke` only.
Probe-only trees **REFUSE**
as acceptance (`check-g1-acceptance-operand.py`).

**AR-2.8:** acceptance also requires product-test **families** boot + security +
crud + db (`check-product-tests.py`; contract `governance/contracts/product-tests.md`).

```bash
# Acceptance operand preflight (probe refuse)
python3 "${HERMES_SKILL_DIR}/scripts/check-g1-acceptance-operand.py" /projects/modernized

# Product-test families (boot/CRUD/security/DB)
python3 "${HERMES_SKILL_DIR}/scripts/check-product-tests.py" /projects/modernized

# Live count (product default — writes evidence JSON optional)
bash "${HERMES_SKILL_DIR}/scripts/count-pit-dry-run.sh" /path/to/module \
  migration/evidence/pit-dry-run.json

# Tooling smoke only (NOT acceptance)
G1_OPERAND=tooling_smoke bash "${HERMES_SKILL_DIR}/scripts/count-pit-dry-run.sh" .

# Parse an existing mutations.xml (fail closed if missing/empty)
python3 "${HERMES_SKILL_DIR}/scripts/parse-pit-mutations.py" \
  governance/fixtures/pit-dry-run/mutations.xml
```

## G-1 kill-ratio pin (plan #8) — live PIT only

Dry-run volume is **not** a kill-ratio pin. After live
`mutationCoverage` on slice classes, pin from measured evidence (no folklore %):

```bash
python3 "${HERMES_SKILL_DIR}/scripts/pin-kill-ratio-from-pit.py" \
  target/pit-reports/mutations.xml \
  -o governance/contracts/g1-kill-ratio-pin.json \
  --coverage-min 0.41 --kill-attempted-min 0.60 --kill-generated-min 0.38 \
  --source declared_engineering_target \
  --rationale "Architect stringency <entry>: declared margins, not measured-at-equality"
```

Dual-denominator (AD-H §18.0¶5): coverage floor `attempted/generated` **and**
kill strength `killed/attempted`; sole attempted PASS predicate forbidden.
`--source` is required — `declared_engineering_target` (bars from outside this
subject's score) or `ratchet_from_measured` (margins recorded under this tree's
measured score). Typed Operator/deputy waiver
(sole alternate M5 path): `governance/schemas/g1-kill-ratio-waiver.md`.
Pinning ≠ M5 `ACCEPT` (#1e).

## Home rule

Do **not** add gate logic under top-level `scripts/` or invent parallel names
(`g1_mutation`, `obligation`, …). Vocabulary names above are binding.


## Procedure

Operand first, then live evidence, then pin. Scripts are under
`${HERMES_SKILL_DIR}/scripts/`; `<root>` is the product tree (e.g.
`/projects/modernized`).

1. **Qualify the operand** — `check-g1-acceptance-operand.py <root>`. Exit 1
   when `src/test/java` holds no `*Test.java`/`*IT.java` outside
   `com.demo.harness.*`. `G1_OPERAND=tooling_smoke` permits harness-only, and
   that result is never acceptance evidence.
2. **Qualify the test families** — `check-product-tests.py <root>`. Exit 1
   unless boot, security, crud and db are each matched by a non-harness test
   (regex heuristics; explicit `AR28:<family>` markers accepted).
3. **Measure G-1 volume live** — `count-pit-dry-run.sh <module> [evidence.json]`
   re-runs steps 1–2 itself, then `mvn test-compile … pitest mutationCoverage
   -Dpit.dryRun=true`, refuses a missing JUnit-5 plugin or a zero-test skip, and
   parses `target/pit-reports/mutations.xml` via `parse-pit-mutations.py`
   (zero mutants ⇒ exit 1).
4. **Exercise the evaluators** — `g1-characterization.py`,
   `g2-harvest-fidelity.py`, `g3-findings-delta.py`, `g4-runtime-parity.py`,
   each taking `<root>`; `run-admission.sh <root>` runs all four. Each walks the
   named fixture dirs under `<root>/governance/fixtures/admission/<gate>/`,
   compares the computed verdict to the fixture's expected verdict, and writes
   `…/admission/out/<gate>/<fixture>.json`. Disagreement ⇒ exit 1.
5. **Pin the kill ratio** (after live `mutationCoverage`, never after a dry run)
   — `pin-kill-ratio-from-pit.py <mutations.xml> -o <pin.json> --coverage-min
   --kill-attempted-min [--kill-generated-min] --source --rationale`.
6. **Persisted data** — when `migration/persisted-data/claim.json` sets
   `pre_existing_db`, `check-persisted-data-contract.py <root>` requires passing
   `schema_compat` **and** `quarkus_db_copy_read_all` records; otherwise idle.

## Verification

- `run-admission.sh` exits 0 and prints `OK: admission fixtures — G-1..G-4 emit
  ACCEPT/REFUSE/INCONCLUSIVE as specified`. A disagreeing evaluator prints
  `FAIL <gate>/<fixture>: got X, want Y` on **stderr** (UPLIFT-2; JSON
  `{gate,fixture,got,want,ok}` per fixture on stdout) and the run exits 1.
- One verdict JSON exists per fixture under
  `evidence/fixtures/admission/out/<gate>/<fixture>.json`, and every G-4 file
  carries `"g4_mode": "SAMPLE"` — `g4-runtime-parity.py` re-reads its own write
  and fails if the stamp is absent (ER#2 F8).
- **Silent-failure assertion:** a green admission run is *not* admission — it
  proves parser + fixture shape only. A G-1 claim is live only when
  `mutations.xml` exists with `mutations_total > 0`; a G-4 claim is live only
  when a product `parity.json` had `execution_evidence.scenarios_ran` true and
  at least one scenario that was not an identical ≥500 pair. ACCEPT without
  those inputs is vacuous and must be read as INCONCLUSIVE.
- Kill-ratio pin file has `status: PINNED`, `threshold.source` of
  `ratchet_from_measured` or `declared_engineering_target`, and floors that do
  not equal the measured ratios (the script refuses circular pins) — and all
  mutants `NOT_STARTED` is refused outright. Pinning is not M5 `ACCEPT`.
- Conformance lint passes for this skill.
