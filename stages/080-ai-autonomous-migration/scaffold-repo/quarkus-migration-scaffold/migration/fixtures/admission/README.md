# Admission fixtures (W2 §10)

Specimen-free synthetic pairs that prove each **domain gate** can emit
**ACCEPT**, **REFUSE**, and **INCONCLUSIVE**.

| Gate | Directory | known-bad proves |
|------|-----------|------------------|
| G-1 characterization | `g1-characterization/` | char_surface stub |
| G-2 harvest-fidelity | `g2-harvest-fidelity/` | silently dropped field |
| G-3 findings-delta | `g3-findings-delta/` | finding marked resolved while present |
| G-4 runtime-parity | `g4-runtime-parity/` | status/body mismatch; identical 5xx = vacuous |

```bash
bash .hermes/skills/domain-gates/scripts/run-admission.sh
# or: bash "${HERMES_SKILL_DIR}/scripts/run-admission.sh"  # skill domain-gates loaded
```

Home: skill `domain-gates` (AD-H §7). See `.hermes/LAYOUT.md`.
