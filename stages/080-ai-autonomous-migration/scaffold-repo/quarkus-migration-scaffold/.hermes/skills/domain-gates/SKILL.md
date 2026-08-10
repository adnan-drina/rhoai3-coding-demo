---
name: domain-gates
description: >
  Migration fidelity domain gates G-1..G-4 (characterization, harvest-fidelity,
  findings-delta, runtime-parity) and W2 §10 admission fixtures. Use when
  admitting a gate, regressing gate/toolchain changes, or before ADVANCE.
---

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

Specimen-free pairs under `migration/fixtures/admission/gN-<name>/`.

**Honesty bound:** green fixtures prove **parser + fixture shape**, not
toolchain-faithful admission. Live sensors (PIT dry-run on a specimen, running
apps for G-4) are a separate prove step — see
`migration/fixtures/admission/README.md`. Do not treat 12/12 as admission.

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

**AR-3.6:** default PIT targets are **product** packages. `com.demo.harness.*`
is tooling smoke only (`G1_OPERAND=tooling_smoke`). Probe-only trees **REFUSE**
as acceptance (`check-g1-acceptance-operand.py`).

**AR-2.8:** acceptance also requires product-test **families** boot + security +
crud + db (`check-product-tests.py`; contract `migration/contracts/product-tests.md`).

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
  migration/fixtures/pit-dry-run/mutations.xml
```

## G-1 kill-ratio pin (plan #8) — live PIT only

Dry-run volume is **not** a kill-ratio pin. After live
`mutationCoverage` on slice classes, pin from measured evidence (no folklore %):

```bash
python3 "${HERMES_SKILL_DIR}/scripts/pin-kill-ratio-from-pit.py" \
  target/pit-reports/mutations.xml \
  -o migration/contracts/g1-kill-ratio-pin.json \
  --coverage-min 0.41 --kill-attempted-min 0.60 --kill-generated-min 0.38 \
  --rationale "Architect stringency <entry>: declared margins, not measured-at-equality"
```

Dual-denominator (AD-H §18.0¶5): coverage floor `attempted/generated` **and**
kill strength `killed/attempted`; sole attempted PASS predicate forbidden.
`source` must be `declared_engineering_target`. Typed Operator/deputy waiver
(sole alternate M5 path): `migration/schemas/g1-kill-ratio-waiver.md`.
Pinning ≠ M5 `ACCEPT` (#1e).

## Home rule

Do **not** add gate logic under top-level `scripts/` or invent parallel names
(`g1_mutation`, `obligation`, …). Vocabulary names above are binding.
