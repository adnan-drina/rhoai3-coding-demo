# Implementer checkpoint / resume (S-010 Class A #3)

**Status:** binding proving-min
**Basis:** in-tree harness obligations (sibling contracts + skills).

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
python3 .hermes/skills/harness/record-run-evidence/scripts/init-implementer-checkpoint.py \
 evidence/bodies/m3-s-010.json --task-id t_example

# After writing a dest file (src/test/** runs mvn test-compile gate first)
python3 .hermes/skills/harness/record-run-evidence/scripts/stamp-implementer-checkpoint.py \
 evidence/runs/t_example/checkpoint.json \
 --completed src/test/java/com/demo/rest/OwnerRestControllerTests.java

# Validate shape / resume readiness
python3 .hermes/skills/harness/record-run-evidence/scripts/check-implementer-checkpoint.py \
 evidence/runs/t_example/checkpoint.json
```

`src/test/**` stamp without a green **scoped** gate → **REFUSE**
(#1b). `--skip-test-compile-gate`
requires `RHOAI3_FIXTURE_ALLOW_SKIP_TEST_COMPILE=1` (live seats FORBIDDEN).
See `compile-scope-filtered.md`.

Schema: `.hermes/skills/harness/dispatch-phase/references/implementer-checkpoint.md` (this file; no `governance/` folder).
