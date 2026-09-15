# rgctl execution-model experiment — 2026-09-15

An isolated trial of graph-informed work decomposition, sequencing and repair scope
for the Spring Boot -> Quarkus migration of `spring-petclinic-rest`, run against the
same frozen source and the same accepted decisions (ADR-001..016) as the official v9
destination.

**Answer to the decisive question:** a working, behaviourally verified migration was
produced with zero human interventions during this execution — using the accumulated
decisions and the v9 evidence — and with substantially less orchestration work. The
relationship graph is not what produced it. See `RECOMMENDATION.md`, which also carries
the architect's rulings on this experiment.

## Result in one table

| | official v9 | this run |
|---|---|---|
| clean `mvn package`, tests executed | reached (package gate accepted at `6a4ba85`) | yes |
| packaged artifact boots against PostgreSQL 16 | reached (boot gate accepted at `be484e84`) | yes, 1.2 s |
| compile diagnostics driven to zero | yes, 233 -> 0 | yes, 233 -> 0 |
| parity scenarios PASS / FAIL / INCONCLUSIVE | 0 / 2 / 16 | **17 / 1 / 0** |
| entry points PASS / FAIL / INCONCLUSIVE (of 34) | 0 / 2 / 32 | **20 / 1 / 13** |
| ADR-015 product tests | none exist | 17 generated, **16 pass** |
| security enabled mode | 403 on everything | 401 anonymous, 200 admin |
| human interventions | 3 Operator steps + 3 architect rulings | **zero during this execution**, using accumulated decisions and v9 evidence |
| execution effort | 21 cards over two days | 13 commits in 56 minutes |

Build and startup are **not** where the two runs differ — v9 reached both. The
difference is behavioural coverage and execution effort. Elapsed figures describe
effort, not speed: this execution consumed decisions and evidence the earlier run had
to produce. No causal speedup is claimed. See `COMPARISON.md`.

## The migrated application

Lives outside every repository checkout, in its own git repository:

```
/Users/adrina/Sandbox/rgctl-experiment/app
HEAD b34e3eaf66bab3ed6fa3e155842e8992ba1bba4c
base e1e11e4  (bootstrap of the frozen source, before any repair)
```

## Documents

| file | what it is |
|---|---|
| `RECOMMENDATION.md` | adopt / retain / reject, and what is still open |
| `WORK-UNITS.md` | the executable work-unit manifest, its evidence and its sequence |
| `COMPARISON.md` | this run against the official v9 evidence, with the caveats |
| `FINDINGS.md` | what rgctl contributed, nine places it was wrong or empty, what actually found each defect, and the withdrawn B-1 claim |
| `POLICY.md` | the policy, its measured baseline, the mutation test, and three ways `check` passes silently |
| `INTERVENTIONS.md` | every ADR-shaped decision I made myself, scope changes, retries, interruptions |
| `REPRODUCE.md` | exact commands, configuration and the two non-obvious overrides the test run needs |
| `TIMELINE.md` | every milestone with a `date -u` timestamp |

## Evidence

| path | |
|---|---|
| `evidence/this-run/parity-receipt.json` | the 34-entry-point receipt this run produced |
| `evidence/this-run/parity-run.json` | the per-scenario run record |
| `evidence/this-run/generated-tests-manifest.json`, `generated-tests.log` | ADR-015 tests and their execution |
| `evidence/this-run/javac-baseline.log` | the uncapped 233-diagnostic baseline |
| `evidence/this-run/rgctl-migration-plan-source.json` | rgctl's own proposed migration order |
| `evidence/this-run/rgctl-kantra-findings.json` | the one-rule fixture catalog the release binary evaluated |
| `evidence/official-v9/` | v9's parity receipt, M4 verdict, loop steps and freeze receipt, copied read-only from the pod |
| `policy/baseline.json` | the domain-crossing and centrality baseline, measured before any threshold |

## Isolation

The official v9 workspace was read only: files were copied out with `oc exec ... tar`
and nothing was written, no producer was run there, no process was started. The main
repository's working tree was not touched. No cluster resource was created — the
database ran locally under podman. No golden repository was published. Credentials
were passed by environment variable and appear in no artifact here.
