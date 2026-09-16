---
name: run-report
description: >
  Use after a run (or during one, read-only) to write
  evidence/reports/run-report.json: what the destination's own record says
  about the run - pinned inputs and environment, a timeline whose clock
  starts before bootstrap, loop work, decided bootstrap repairs, live
  interventions, cost, final state, the comparable contract and the
  classification. Use when comparing runs (a repeatability run against an
  earlier run or an isolated experiment), even if the user only asks "how
  did the run go". Reads only what is recorded; never starts, mints, edits
  or re-measures anything. Not a gate and not an M4 floor.
license: Apache-2.0
compatibility: Python 3.9+ stdlib; git (optional); no Hermes calls
metadata:
  author: rhoai3-harness-team
  version: "1.1.0"
  hermes:
    tags:
    - evaluation
    - report
    category: evaluation
    kind: guidance
    paths:
      reads: ["/projects/modernized/verification", "/projects/modernized/evidence", "/projects/modernized/decisions.yaml", "/projects/modernized/.hermes/pins.json"]
      writes: ["/projects/modernized/evidence/reports/run-report.json"]
---
# Run report

One read-only script. Every value in the report is `{"value", "source"}`;
an unknown value is `null` with a `reason`. A milestone the records show was
never reached is `"unreached"` - a claim, made only when those records are
present. Nothing is guessed.

```bash
python3 "${HERMES_SKILL_DIR}/scripts/run-report.py" --root /projects/modernized \
  [--kanban-json board.json]        # output of: hermes kanban list --json
  [--kanban-logs <dir>]             # per-card worker logs (<task>.log)
  [--hermes-config <copy>]          # the live config (Managed Scope keeps it outside the tree); repeatable
  [--budget <file>]                 # budget + stopping conditions declared before launch
  [--git-log <file>]                # git log --format='%H %ct %s', for a replica without history
  [--compare LABEL=<run-report.json>]   # repeatable
  [--out <file>]                    # default evidence/reports/run-report.json
```

Markdown goes to stdout; the JSON (`rhoai3.run-report/v1`) to `--out`.

## What it reads

| Section | Records |
|---|---|
| `pinned_inputs` | `evidence/producers/freeze.json`, `evidence/frozen/source-manifest.json`, the bundle's `source.digest`; admission seals (bundle, `decisions.yaml`, pins) against the files; `decisions.yaml` `loop.*` and accepted ADRs; `evidence/harness/install-manifest-*.json` (both formats) matched to `harness: install golden …` commits |
| `pinned_environment` | `.hermes/pins.json`; the live config (`--hermes-config`, or `.hermes/home/config.yaml` and profiles when the tree has them) - model/provider, inference and concurrency keys only, secret-named keys never read; the config template, labelled as such; board model overrides; build toolchain, package argv, `.mvn/maven.config`; `decisions.datasource` and its asset digests, the bootstrap baseline, parity reset commands; corpus and capture receipts per mode; comparator script digests and producer names |
| `timeline` | clock start = the earliest of the destination's first commit and the M1 dispatch (bootstrap and dispatch inside it); baseline, first accepted step, first `[0,0,0]`, first package pass, first boot pass (step `runtime`, commit times from git); first full parity composition and first **passing** parity per mode; every M4 verdict (close rows, the verdict file, board M4 cards) and the first **passing** one; offsets since start and since baseline |
| `bootstrap_repairs` | decided transformations applied at bootstrap (ADR-019): `evidence/producers/decided-repairs.json` rows (`applied` / `already-applied` count as applied, `refused` does not) with files and symbols from the rows and the receipt inventory, its binding in `bootstrap.json#decided_repairs`, the `decisions.yaml#decided_repairs` decision; zero only when nothing was decided and nothing bound, otherwise "no bootstrap receipt"; the bootstrap receipt's mechanical changes counted by op, apart |
| `loop_work` | `verification/loop/steps.json` (accepted, attempt rows, closed-without-verdict, close rows, pending, attempts), `deferred.json`, `issued.json`, K4 mint receipts, amendments and revisions, `evidence/planning/batch-scope/**` (v4 unit sizes), kinds per card from K1 bodies |
| `interventions` | operator steps (ADR, author, reviewer, whether each ADR is accepted), rewinds, dispositions, M4 resumes (listed, not counted), worker vs operator repaired files |
| `harness_changes` | installs before the clock start (prior preparation), after it, other `harness:` commits - never counted as interventions |
| `cost` | verification count and time from the verify records, warmup, `run.json` cache fields; wall time, card run/queue time, time outside card runs, tool time from the logs; provider time only if recorded (it is not today) |
| `final_state` | loop state, admission, package/boot receipts; parity per security mode with the entry-point denominator (receipt) and the scenario denominators (run record, scenario records); M4 verdict; release blockers; generated-test execution from the latest TEST-*.xml; coverage account |
| `contract` | entry points (bundle) and scenarios (corpus) with content digests - the input of `--compare` |
| `budget` | `--budget`, `run-budget.*`, `evidence/run/budget.*`, `decisions.yaml#budget`; otherwise `"undeclared"`; the loop's own stopping rule (ADR-002 threshold) |
| `board` | card counts, statuses, run/queue durations per phase, cards the record has no row for; log token counts (blocked, protocol_violation, REFUSE, non-zero exits) - "not provided" without the inputs |
| `comparison` | with `--compare`: the common unchanged entry points and scenarios, changed and extra ones per run, parity counts on the common entry points, headline metrics side by side |

## Classification

| Class | When |
|---|---|
| `autonomous` | no operator step, rewind or disposition, and the bootstrap receipt records no decided repair |
| `autonomous_execution_with_predecided_repairs` | no live intervention, and the bootstrap applied decided repairs |
| `assisted-by-decision` | every operator step applies an accepted ADR and names a reviewer; no rewind, no disposition |
| `assisted` | anything else; the reasons are listed |

`prior_assistance` sits beside the class: the number of decided bootstrap
repairs, or `null` with "no bootstrap receipt" - never a zero that was not
read. Harness installs never change the class.

## Rules

- Read-only: it runs `git log` (or reads `--git-log`) and nothing else; it
  refuses a git history that belongs to an enclosing repository.
- Specimen-agnostic: no application name, package or path is in the script;
  `run-report.test.py` builds two specimens and compares their shapes.
- Tests: `python3 scripts/run-report.test.py`.
