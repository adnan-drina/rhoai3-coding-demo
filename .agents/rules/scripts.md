---
name: scripts
applies-to:
  - scripts/**
  - stages/*/*.sh
  - stages/*/*/*.sh
  - stages/**/*.py
---

# Operator scripts

Applies to the scripts an operator runs from a checkout (`scripts/`, `stages/` including task subfolders). Not to the Stage 120/130 golden
scaffolds (`scaffold-repo/`), image build contexts, or scripts embedded in GitOps components (they run in the
cluster or in a workspace).

## Stage scripts

- Every stage has exactly one `stages/NNN-name/deploy.sh` (GitOps stages only) and one
  `stages/NNN-name/validate.sh`. They are complete: `deploy.sh` alone deploys the whole stage and `validate.sh` alone
  validates it, in one run each, with no other script needed. Nothing else is a script at a stage's top level;
  `scripts/validate-stage-flow.sh` refuses any other `*.sh` or `*.py` there.
- Options of the two cover variants of deploying or validating the stage: a script-deployed component is
  `deploy.sh --component NAME` (the value of its Application's `demo.rhoai.io/deploy-script` annotation), capacity is
  `deploy.sh --gpus N`, a one-run check is `validate.sh --run`.
- A stage action that is neither deploying nor validating the stage (a demo step such as generating load or a showback
  dashboard, resetting the demo, rotating a credential, building an image, a release qualification) is a task-focused
  script in a named subfolder of the stage, for example `stages/040-.../showback/generate-load.sh` or
  `stages/070-.../demo-reset/reset-coolstore.sh`. Name the folder after the task; give it a short `README.md` that says
  when to run each script, and link it from the stage README. Existing examples: `050 qualification/` (the KFP
  pipeline), `050 edd/`, `050 evaluation/` and `130 qualification/`.
- `scripts/` holds only what every stage needs: `lib.sh` (environment, the cluster guard, logging, the validation
  check functions, and the shared read-only prerequisites `check_operator_policy`, `require_node_sizing`,
  `check_serving_prerequisites`), `stage-apps.sh` (the Argo CD component engine) and `validate-stage-flow.sh` (the
  offline repository gate). Do not add other files.
- Every script needs a reason to exist: it deploys or validates a stage, or performs a named stage action. A retired
  script is removed; its last version stays in git history.

## Shell only

- Write **bash** with `oc`, `jq`, `curl`, `git` and `ruby` (all documented prerequisites). Read cluster state with
  `oc ... -o json | jq` or `-o jsonpath`; build JSON with `jq -n`.
- Turn YAML into JSON with `ruby -ryaml -rjson -e 'puts JSON.generate(YAML.load_stream(STDIN.read).compact)'`
  (`yaml_json` in `lib.sh`). A YAML parse tree (duplicate keys) is the one short inline Ruby program.
- **Python only where nothing else can do it**: the Stage 050 Kubeflow pipeline (`qualification/pipeline.py`,
  `compile.py`), checks that exercise Python content (a scaffold's own self-tests and modules, or a program that runs
  inside a migration workspace against its installed harness), and compiling that Python. Never Python for JSON,
  YAML, HTTP or text checks.
- Long `jq` programs are fine when they are the clearest expression; name reusable ones as `def`s in a variable.

## Shape

```bash
#!/usr/bin/env bash
# <What the script does, in a few sentences. What it changes, or "read-only".>
# Usage: stages/NNN-name/<deploy|validate>.sh [--flag VALUE]   (task script: stages/NNN-name/TASK/NAME.sh)
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"   # one more ../ in a task subfolder
source "$REPO_ROOT/scripts/lib.sh"
# parse arguments; print the Usage line on a wrong one
load_env
check_oc_logged_in
```

- Group a long script into commented sections and functions; one statement per line; lines under ~140
  characters; descriptive names.
- `deploy.sh`: read-only preflight first (`stage-apps.sh select`, `preflight`, the stage's own prerequisites), then
  the first write, then waits and the stage's runtime setup. Never print what it applies.
- A task script states in its header what it changes and whether it is safe to rerun; it uses the same guard and
  `lib.sh` functions, and never duplicates a step `deploy.sh` already performs (call `deploy.sh` or reuse its result).
- `validate.sh`: read-only; report through `check LABEL COMMAND EXPECTED`, `record LABEL RESULT` and
  `validation_summary`. Exit codes: `0` pass, `1` fail, `2` ready but pending (a documented acceptance step not yet
  run).

## Secrets

- Never print a Secret value or pass it as a command argument (visible in `ps`). Pipe Secret JSON from `oc` straight
  into `jq` (`printf '%s' "$x" | jq`, `--slurpfile x <(printf '%s' "$y")`), give values to `jq` through its
  environment (`$ENV.NAME`), and give tokens to `curl` through `--config -` or `--config <(printf ...)`.
- No `--arg`/`--argjson` and no here-strings (`<<<`, a temp file in bash 3.2) with Secret values.
- Form bodies with credentials use `jq -j` (no trailing newline) piped to `curl --data-binary @-`.

## Proof

- A changed check is proven against the live cluster: the same PASS/FAIL as before, and a negative probe (an `oc`
  wrapper that mutates one JSON read) that makes exactly the intended check fail.
- A changed deploy step is proven read-only first (a wrapper that refuses `oc` writes), then idempotently at the
  deployed revision.
