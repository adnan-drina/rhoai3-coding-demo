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

Pin **`pitest-maven` 1.25.5**; use **`-Dpit.dryRun=true`** (not `+dryRun`
feature). Referent needs **≥1 compilable test**; refuse zero-test skip and
`-DskipTests`. **No static-metric floor.**

```bash
# Live count (writes evidence JSON optional)
bash "${HERMES_SKILL_DIR}/scripts/count-pit-dry-run.sh" /path/to/module \
  migration/evidence/pit-dry-run.json

# Parse an existing mutations.xml (fail closed if missing/empty)
python3 "${HERMES_SKILL_DIR}/scripts/parse-pit-mutations.py" \
  migration/fixtures/pit-dry-run/mutations.xml
```

## Home rule

Do **not** add gate logic under top-level `scripts/` or invent parallel names
(`g1_mutation`, `obligation`, …). Vocabulary names above are binding.
