---
name: scripts
applies-to:
  - scripts/**
  - stages/**/*.sh
  - stages/**/*.py
---

# Operator scripts

Applies to scripts an operator runs from a checkout (`scripts/`, `stages/`). Not to the Stage 130 golden
scaffold or to scripts embedded in GitOps components (they run in the cluster).

## Self-contained, shell first

- Every script stands alone: read it top to bottom, run it, change it without touching other scripts.
- Only two things are shared, because they are safety logic that must not exist as drifting copies:
  `scripts/shared/lib.sh` (`load_env`, `check_oc_logged_in`, logging; mandatory guard per `AGENTS.md`) and
  `scripts/shared/stage_apps.py` (the Argo CD deploy engine). `validate-lib.sh` (the `check` line format for shell
  validators) is a thin companion of `lib.sh`. Do not add other shared helpers.
- Write scripts in **bash** with `oc`, `jq` and `curl` (all documented prerequisites). Read cluster state with
  `oc ... -o json | jq` or `-o jsonpath`; build JSON with `jq -n`.
- Turn YAML into JSON for `jq` with `oc kustomize DIR | oc create --dry-run=client -o json -f -` or
  `ruby -ryaml -rjson` (both prerequisites); no YAML library is needed in shell.
- Use **Python only when shell genuinely cannot do it**: cryptography, multi-step HTTP flows with sessions,
  KFP/SDK use, or logic that would need more than a screen of `jq`. Then write a standalone `.py` file next to the
  caller, not a heredoc.
- **No heredoc programs.** A heredoc may hold data (a manifest, a JSON payload); code longer than ~10 lines goes
  in its own file.

## Shape

Start from this skeleton and keep it:

```bash
#!/usr/bin/env bash
# <What the script does, in one or two sentences. What it changes, or "read-only".>
# Usage: <path> [--flag VALUE]
set -euo pipefail
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/shared/lib.sh"
load_env
check_oc_logged_in
```

- One statement per line; lines under ~120 characters; descriptive variable names.
- Validators source `scripts/shared/validate-lib.sh` and report through `check` / `validation_summary`.
- Exit codes: `0` pass, `1` fail, `2` ready but pending (a documented acceptance step not yet run).
- Never print Secret values; read them into variables or pipe them straight to the consumer.

## Placement and names

- `stages/NNN-name/`: `deploy.sh`, `validate.sh`, and any `deploy-<component>.sh` an Application's
  `demo.rhoai.io/deploy-script` names. Other entry points go in `tools/`, offline tests in `tests/`.
- `scripts/platform/`: tools that span stages. `scripts/demo/`: developer-workflow helpers for stages 110-130.
- Verbs: `deploy-` (applies GitOps), `setup-` (one-time runtime data or credentials), `validate-` (read-only
  checks), `qualify-` (functional tests that exercise the platform), `build-` (images, artifacts).
- Tests: `tests/test_<name>.sh` or `.py`; `validate-stage-flow.sh` runs them.
