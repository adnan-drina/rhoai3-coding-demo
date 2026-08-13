# D1 pre-exists EXISTENCE (W4)

Remint / create must **refuse** when `dependencies[].provider=pre-exists` and the
destination path is missing (`test -f` / `Path.is_file()`).

```bash
mkdir -p /tmp/d1-empty-dest
python3 .hermes/skills/sdd/check-spec-readiness/scripts/assert-dependency-closure.py /tmp/d1-empty-dest \
  --body governance/fixtures/d1-pre-exists/body-false-pre-exists.json
# expect: FAIL DEPENDENCY_CLOSURE + pre-exists DEST_MISS (rc=1)
```

Cite: Architect E-20260811T203657Z · plan W4 D1 / E-163136Z.
