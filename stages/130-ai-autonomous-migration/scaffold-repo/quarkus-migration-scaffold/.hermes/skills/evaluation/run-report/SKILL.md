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
  did the run go". The headline is the end-to-end state (M-6) from the
  completion map (M-1); task activity follows. Reads only what is recorded;
  never starts, mints, edits or re-measures anything. Not a gate and not an
  M4 floor.
license: Apache-2.0
compatibility: Python 3.9+ stdlib; git (optional); no Hermes calls
metadata:
  author: rhoai3-harness-team
  version: "1.2.0"
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
  [--plan plan.r<N>.json]           # repeatable; default the frozen evidence/planning/plan-semantics.json
  [--out <file>]                    # default evidence/reports/run-report.json
```

Markdown goes to stdout; the JSON (`rhoai3.run-report/v1`) to `--out`.

## Behaviour coverage by scenario kind (R-1, M-3)

`scripts/rehearsal-coverage.py --root /projects/modernized [--json]` lists every (security mode, scenario kind,
resource) cell of the run's OWN corpus with the verdict a comparison of the current candidate gave it: PASS, FAIL,
INCONCLUSIVE or not compared. A cell nobody compared is listed, never assumed covered. Use it on a lab candidate before
a run (the rehearsal) and on a run's candidate to see which kinds of behaviour remain unproven.

The model usage block (requests, tokens per profile) needs `--state-db <copy of a profile state.db>` (repeatable); the
"why runs stopped" line needs `--kanban-db`.

## Headline: end-to-end state

`## End-to-end state` comes first; everything after it is supporting task
activity. It is `lib/completion_map.py` (JSON: `completion_map`,
`end_to_end`), a derived view that grants, admits and accepts nothing:

- **state**: e.g. `runtime behavior unresolved; measurement invalid`, or
  `deployed at <url>; not released (M5 INCONCLUSIVE, ship=false)`.
- **last demonstrated milestone** of source understood → target structurally
  viable → persistence and one HTTP path → application behavior preserved →
  delivered and usable, each `demonstrated` / `not-demonstrated` / `unknown`
  from checks and measurements, never from card completion; plus functional,
  delivery, full release and repeatability.
- **current candidate**, **next missing prerequisite**, **oldest unresolved
  cause**, **release verdict** (M5 through `lib/m5_delivery.py` records:
  candidate → PipelineRun → image digest → deployment → live → verdict).
- **release blockers**: one row per unresolved entry point of the admitted
  plan (and per source qualification FAIL) with owner, prerequisites and
  exit. Only the M4-bound parity evidence closes one; an empty work list, a
  zero measure or a finished card never does; no plan read is `unknown`.
- **measurement**: invalid under a stale or blocked admission seal,
  comparator-refused verdicts, or INCONCLUSIVE over a recorded FAIL.
- **causal groups** only where records prove a shared producer (same
  exception, recursion in the recorded frames, one plan family and recipe);
  every affected check is kept.
- cost: model requests/tokens stay unknown unless a ledger reports them.
  Completed-card percentages are not migration percentages.

Standalone (read-only): `python3 .hermes/lib/completion_map.py --root . [--plan plan.r1.json] [--json]`.

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
| `budget` | a factory declaration (`run-budget.json` schema v2) composed with the golden `run-defaults.json#/budget` it binds and timed by the initial commit that introduced it (`planner/run_declaration.py`; a rewritten or foreign one reports its refusal, never a budget); else `--budget`, `run-budget.*`, `evidence/run/budget.*`, `decisions.yaml#budget` as recorded (v10/v11); otherwise `"undeclared"`; the loop's own stopping rule (ADR-002 threshold) |
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
- Tests: `python3 scripts/run-report.test.py`; `python3 .hermes/lib/completion_map.test.py`.
