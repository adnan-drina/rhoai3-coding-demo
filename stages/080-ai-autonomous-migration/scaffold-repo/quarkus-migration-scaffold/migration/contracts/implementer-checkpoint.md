# Implementer checkpoint / resume (S-010 Class A #3)

**Status:** binding proving-min  
**Sources:** Deputy `E-20260810T104752Z` defect 3 · Lead BIND `E-20260810T104932Z` · Architect sizing BIND

## Problem

Two budget-wall `timed_out` runs re-walked context; written files persist,
reasoning does not. Cold restart dies near the same seam.

## Rule

For M3 implementer tasks (especially test-authoring):

1. **Init** a checkpoint from the typed body dest write-set at create/start
2. **Stamp** after each successful dest write (or batch): mark path completed;
   set `next`
3. **Resume** on re-dispatch / retry: read checkpoint first; continue at `next`;
   refuse body-digest mismatch

```bash
# Init from body (dest paths under modernized / files_writable)
python3 .hermes/skills/auditability-repeatability/scripts/init-implementer-checkpoint.py \
  migration/bodies/m3-s-010.json --task-id t_example

# After writing a dest file
python3 .hermes/skills/auditability-repeatability/scripts/stamp-implementer-checkpoint.py \
  migration/runs/t_example/checkpoint.json \
  --completed src/test/java/com/demo/rest/OwnerRestControllerTests.java

# Validate shape / resume readiness
python3 .hermes/skills/auditability-repeatability/scripts/check-implementer-checkpoint.py \
  migration/runs/t_example/checkpoint.json
```

Schema: `migration/schemas/implementer-checkpoint.md`.

S-010 re-dispatch remains HOLD until this land is on tip + live (with Class A
#1 toolchain and #2 sizing BIND already done).
