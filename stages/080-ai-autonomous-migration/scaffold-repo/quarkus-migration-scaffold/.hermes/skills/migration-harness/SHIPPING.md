# Phases D and E — final sensors and the factory gate

## Contents
- Phase D — re-analysis, delta, final verify
- Phase E — the supervised factory gate loop

## Phase D — final sensors + ship

1. Re-analysis of the MIGRATED code:

```bash
kantra-ensure
/tmp/kantra/kantra analyze -i /projects/modernized -o /tmp/kantra-after \
  --target quarkus --json-output --overwrite || true
cp /tmp/kantra-after/output.json /projects/modernized/migration/mta-findings-after.json
```

Done means the baseline findings are resolved (or waived in the spec) —
not "the agent says done."

2. `mvn -q clean verify` green.
3. Commit with a conventional message referencing the spec id. Under the
   supervisor, DO NOT push — the supervisor ships and drives Phase E.
4. Final report: tasks completed/deferred, debt entries, findings delta
   (before → after).

## Phase E — the factory gate loop (supervised)

The supervisor (`.hermes/harness/supervisor.sh`) owns shipping: it pushes,
watches the project PipelineRun (read-only RBAC is provisioned into every
project namespace), and on a SonarQube gate rejection exports the complete
new-code violation list to `/tmp/gate-violations.txt` (SonarQube allows
anonymous reads inside the cluster) and starts a **gate-correction
session** with you. In that session:

1. Read `/tmp/gate-violations.txt` with your file tools — rule, count,
   `file:line` sites, plus `DUPLICATION` lines per file.
2. Dispatch fixes to the worker in SMALL packets per the packet-size rule
   (group by rule, ≤ ~10 sites per packet, sequential). Duplication means
   consolidation — records, static factories — never suppression.
3. Semantics are inviolable: converting checks to `isEmpty()` and
   injection styles must preserve behavior exactly.
4. `mvn -q clean verify` green, JaCoCo coverage ≥ 80%, then ONE commit
   starting `Gate fix:` — the supervisor re-pushes and re-observes.

Budget: two gate rounds. A second rejection halts the run with the
violation list preserved for the retro — never bypass or water down the
gate.

