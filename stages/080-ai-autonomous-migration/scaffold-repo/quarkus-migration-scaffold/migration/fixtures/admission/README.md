# Admission fixtures (W2 §10)

Specimen-free synthetic referent/destination pairs that prove each domain gate
can emit **ACCEPT**, **REFUSE**, and **INCONCLUSIVE** in the real runtime.

| Gate | known-good | known-bad | known-vacuous |
|------|------------|-----------|---------------|
| G-1 | unit + evidence of killed mutants | `char_surface` stub with invoking test | PIT ran, zero mutants |
| G-2 | field set conserved | one field silently dropped | zero classes in scope |
| G-3 | analyzer ran, open set empty | finding still present marked resolved | analyzer produced zero findings / no run evidence |
| G-4 | matching status+body | different status/body | both sides same 5xx |

Run:

```bash
bash scripts/run-admission-fixtures.sh
```

Regression net: re-run on every gate or toolchain change. Placement: scaffold
test target (this directory + script), not specimen data.
