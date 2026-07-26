#!/usr/bin/env bash
# ---------------------------------------------------------------------------
# Stage 080 harness SUPERVISOR — drives the full autonomous migration:
#   Phase A (ground truth) -> Phase B (plan) -> Phase C (task loop)
#   -> Phase D (final sensors) -> Phase E (ship through the factory gate)
#
# The supervisor owns LOOP CONTROL and FAILURE CLASSIFICATION; the
# orchestrator model owns judgment inside each session. Session outcomes
# are classified so platform faults (quota, stream stalls, context
# overflows) are retried WITHOUT burning the task's attempt budget, while
# genuine no-progress sessions consume attempts and fall through to the
# debt policy.
#
# Run inside the migration workspace:
#   nohup .hermes/harness/supervisor.sh > /tmp/supervisor-nohup.log 2>&1 &
# Progress:  tail -f /tmp/supervisor.log
# ---------------------------------------------------------------------------
set -u
export PATH=$HOME/.opencode/bin:$HOME/.local/bin:$PATH
cd /projects/modernized

ORCH_PROVIDER="${ORCH_PROVIDER:-custom:maas-m2}"
ORCH_MODEL="${ORCH_MODEL:-minimax-m2}"
WORKER_MODEL="${WORKER_MODEL:-qwen27b/qwen3-6-27b}"
SESSION_TIMEOUT="${SESSION_TIMEOUT:-2700}"
MAX_ATTEMPTS=2            # judgment attempts per stage (platform faults excluded)
MAX_PLATFORM_RETRIES=4    # consecutive platform-fault retries per stage
MAX_GATE_ROUNDS=4         # factory correction rounds in Phase E (gate + deploy classes share the budget)

RUN_BASE=$(git rev-parse HEAD)   # commits after this belong to THIS run
LOG=/tmp/supervisor.log
EVENTS=/tmp/supervisor-events.csv
METRICS=/tmp/supervisor-metrics.csv
[ -f "$EVENTS" ]  || echo "epoch,stage,attempt,class,action" > "$EVENTS"
[ -f "$METRICS" ] || echo "session,start,end,seconds,rc" > "$METRICS"

log()   { echo "[$(date -u +%F' '%T)] $*" >> "$LOG"; }
event() { echo "$(date -u +%s),$1,$2,$3,$4" >> "$EVENTS"; }

OPERATOR_NOTES='Operator context for this run:
- The destination /projects/modernized is a Quarkus scaffold. A task is complete when its FINDINGS are resolved IN THE DESTINATION. If a finding is inherently resolved by the scaffold already, verify that with concrete evidence and record it as resolved-by-scaffold in the run-log row - do not invent work.
- Rewrite tasks: run the recipes on /tmp/rewrite-staging (recreate per the skill if missing), then harvest outcomes via OpenCode tasks with explicit source and destination paths.
- Quality-gate bars are part of every acceptance: unit tests ship WITH harvested code (>= 80% new-code line coverage), zero new violations (S1186 comments go INSIDE empty method bodies), no copied duplication (consolidate, or use records for DTOs), constructor injection over field injection (S6813).
- Sensors per the skill: mvn -q clean test after every sub-fix; escalate to mvn -q clean verify when pom.xml or runtime config changed.
- Scripting: terminal python3 heredocs ONLY, never execute_code. Worker event streams: redirect to a file, read only a scripted summary.
- Worker: opencode run -m WORKER_MODEL_PLACEHOLDER --auto --format json per the skill. Dispatch SYNCHRONOUSLY and wait for exit - never background a worker, never end your turn while one runs. A worker run with no file changes is a FAILED attempt - re-dispatch once with a sharper packet.
- Packet size rule: one concern and at most ~10 files or violation sites per worker packet. Split larger work into sequential packets - large single packets stall the worker.
- Budget: 2 worker attempts per sub-fix; exhausted -> record in migration/debt.md with evidence and continue.
- Append-only run-log rows. DO NOT PUSH anywhere - the supervisor ships.'
OPERATOR_NOTES="${OPERATOR_NOTES//WORKER_MODEL_PLACEHOLDER/$WORKER_MODEL}"

committed() { git log --oneline "${RUN_BASE}..HEAD" | grep -q " $1:"; }

# NOTE: match the worker by exact process name (-x). Command-line matching
# false-positives on hermes sessions whose operator notes quote the
# `opencode run` invocation.
wait_for_worker() {
  local waited=0
  while pgrep -x opencode >/dev/null 2>&1; do
    [ $waited -eq 0 ] && log "worker process still running — waiting for it before next session"
    sleep 60; waited=$((waited+60))
    [ $waited -ge 3600 ] && { log "worker still running after 60m — proceeding anyway"; break; }
  done
}

classify() { # $1=rc $2=session-log -> failure class on stdout
  local rc="$1" f="$2"
  if grep -qE "429|Too Many Requests" "$f" 2>/dev/null; then echo quota; return; fi
  if grep -qE "maximum context length|VLLMValidationError" "$f" 2>/dev/null; then echo ctx_overflow; return; fi
  if grep -qE "unresponsive|stale attempts|ReadTimeout|stream drop|Connection to provider failed" "$f" 2>/dev/null; then echo stream_stall; return; fi
  [ "$rc" = "124" ] && { echo timeout; return; }
  if pgrep -x opencode >/dev/null 2>&1; then
    echo orphan_worker; return
  fi
  echo no_commit
}

orch() { # $1=tag $2=prompt ; logs to /tmp/sup-<tag>.log ; returns rc
  local tag="$1" prompt="$2" t0 t1 rc
  wait_for_worker
  t0=$(date +%s)
  timeout "$SESSION_TIMEOUT" hermes chat --provider "$ORCH_PROVIDER" --model "$ORCH_MODEL" -q "$prompt" \
    > "/tmp/sup-${tag}.log" 2>&1
  rc=$?
  t1=$(date +%s)
  echo "${tag},${t0},${t1},$((t1-t0)),rc=${rc}" >> "$METRICS"
  return $rc
}

# run_stage <commit-prefix> <tag> <prompt> <retry-prompt> -> 0 committed / 1 exhausted
run_stage() {
  local prefix="$1" tag="$2" prompt="$3" rprompt="$4"
  local attempt=1 pf=0
  while [ $attempt -le $MAX_ATTEMPTS ]; do
    committed "$prefix" && return 0
    local p="$prompt"; [ $attempt -gt 1 ] && p="$rprompt"
    orch "${tag}-a${attempt}p${pf}" "$p"; local rc=$?
    if committed "$prefix"; then event "$tag" "$attempt" success commit; log "$tag: committed $(git log --oneline -1)"; return 0; fi
    local cls; cls=$(classify "$rc" "/tmp/sup-${tag}-a${attempt}p${pf}.log")
    event "$tag" "$attempt" "$cls" retrying
    case "$cls" in
      quota)
        log "$tag: quota throttle — backing off 15m (attempt NOT burned)"
        sleep 900; pf=$((pf+1));;
      stream_stall|ctx_overflow)
        log "$tag: $cls — platform fault, retrying in 2m (attempt NOT burned)"
        sleep 120; pf=$((pf+1));;
      orphan_worker)
        log "$tag: session abandoned a running worker — waiting for worker, then verify-and-commit session"
        wait_for_worker
        prompt="$rprompt"; rprompt="$rprompt"; pf=$((pf+1));;
      timeout)
        log "$tag: session hit the ${SESSION_TIMEOUT}s cap — attempt $attempt burned, partial work stays for the next attempt"
        attempt=$((attempt+1));;
      no_commit)
        log "$tag: session ended without commit — attempt $attempt burned"
        attempt=$((attempt+1));;
    esac
    if [ $pf -ge $MAX_PLATFORM_RETRIES ]; then
      log "$tag: $MAX_PLATFORM_RETRIES consecutive platform faults — burning an attempt to avoid an infinite loop"
      pf=0; attempt=$((attempt+1))
    fi
  done
  log "$tag: attempts exhausted — checkpointing partial work per debt policy"
  git add -A && git commit -m "${prefix}: partial work checkpoint (supervisor: attempts exhausted)" >/dev/null 2>&1 || true
  return 1
}

# ---------------------------------------------------------------- Phase A/B
if committed "Phase A" || [ -f migration/mta-findings.json ]; then
  log "Phase A: already present"
else
  run_stage "Phase A" "phaseA" \
"Use the migration-harness skill. Execute Phase A ONLY: normalize ground truth into migration/mta-findings.json (prefer the legacy IDE analysis under /projects/legacy/.vscode/mta-core/). Print a violation summary with a terminal python3 heredoc (never read the file whole).
${OPERATOR_NOTES}
Finish with ONE commit whose message STARTS with 'Phase A:'. Stop after Phase A." \
"Use the migration-harness skill. Execute Phase A ONLY per the skill; a previous attempt did not commit. Verify migration/mta-findings.json exists and is valid konveyor JSON, then commit with message starting 'Phase A:'. ${OPERATOR_NOTES}" \
    || { log "FATAL: Phase A failed"; echo phaseA-failed > /tmp/supervisor-done; exit 1; }
fi

if committed "Phase B" && ls specs/*/tasks.md >/dev/null 2>&1; then
  log "Phase B: already present"
else
  run_stage "Phase B" "phaseB" \
"Use the migration-harness skill. Phase A is committed. Execute Phase B ONLY: read the legacy code under /projects/legacy and the findings (scripted extraction only), then write specs/001-coolstore-migration/spec.md, plan.md and tasks.md per the skill. Every mandatory finding maps to at least one task; rewrite tasks before infer tasks; every task heading uses the form '### T-NNN: title' with zero-padded numeric ids (T-001, T-002, ...). The spec MUST cover the legacy application's user-facing surface (web UI / index page) — either map it to a migration task or explicitly waive it with a reason.
${OPERATOR_NOTES}
Finish with ONE commit whose message STARTS with 'Phase B:'. Stop after Phase B." \
"Use the migration-harness skill. Execute Phase B ONLY; a previous attempt did not commit. If specs/001-coolstore-migration/{spec,plan,tasks}.md exist and are complete, commit them with message starting 'Phase B:'; otherwise finish writing them first. ${OPERATOR_NOTES}" \
    || { log "FATAL: Phase B failed"; echo phaseB-failed > /tmp/supervisor-done; exit 1; }
fi

# ---------------------------------------------------------------- Phase C
TASKS_FILE=$(ls specs/*/tasks.md 2>/dev/null | head -1)
TASK_IDS=$(grep -E '^### ' "$TASKS_FILE" | sed -E 's/^### (T[-A-Za-z0-9]*[0-9]+):.*/\1/' | grep -E '^T')
[ -n "$TASK_IDS" ] || { log "FATAL: no task ids parsed from $TASKS_FILE"; echo no-tasks > /tmp/supervisor-done; exit 1; }
log "task list: $(echo $TASK_IDS | tr '\n' ' ')"

for T in $TASK_IDS; do
  committed "$T" && { log "$T: already committed"; continue; }
  run_stage "$T" "$T" \
"Use the migration-harness skill. Execute Phase C for task ${T} from ${TASKS_FILE} ONLY.
${OPERATOR_NOTES}
Finish with ONE commit whose message STARTS with '${T}:'. Stop after ${T}." \
"Use the migration-harness skill. Execute Phase C for task ${T} from ${TASKS_FILE} ONLY. A previous attempt may have left partial uncommitted work or a finished worker run - inspect git status first, verify or finish the work, run the sensors, and commit ONE commit whose message STARTS with '${T}:'.
${OPERATOR_NOTES}" \
    || log "$T: exhausted — recorded, moving on"
done

# ---------------------------------------------------------------- Phase D
if ! committed "Phase D"; then
  run_stage "Phase D" "phaseD" \
"Use the migration-harness skill. All tasks are executed (see migration/run-log.md and migration/debt.md). Execute Phase D:
1. kantra-ensure, then /tmp/kantra/kantra analyze -i /projects/modernized -o /tmp/kantra-after --target quarkus --json-output --overwrite (tolerate exit 1 per the skill), copy /tmp/kantra-after/output.json to migration/mta-findings-after.json.
2. Compute the findings delta (baseline vs after) with a terminal python3 heredoc; append a delta summary to migration/run-log.md. Remaining findings must be individually explained (advisory / false positive with reasoning).
3. mvn -q clean verify must pass.
4. ONE commit whose message starts 'Phase D:'. DO NOT PUSH.
${OPERATOR_NOTES}" \
"Use the migration-harness skill. Execute Phase D per the skill; a previous attempt did not commit. Verify migration/mta-findings-after.json and the delta section exist, mvn -q clean verify passes, then commit with message starting 'Phase D:'. ${OPERATOR_NOTES}" \
    || log "Phase D: exhausted — shipping without final re-analysis commit"
fi

# ---------------------------------------------------------------- Phase E
NS=$(grep -rhoE '^\s*namespace:\s*\S+' k8s/*.y*ml 2>/dev/null | head -1 | awk '{print $2}')
[ -n "$NS" ] || NS="$(basename $(git remote get-url origin) .git)-dev"
SONAR_URL="${SONAR_URL:-http://sonarqube.sonarqube.svc:9000}"
SONAR_KEY="$(basename $(git remote get-url origin) .git)"

# Workspace oc is not logged in by default — authenticate with the pod's
# service account (harness-pipeline-observer RBAC grants the reads).
SA=/var/run/secrets/kubernetes.io/serviceaccount
OC() { oc --server=https://kubernetes.default.svc --token="$(cat $SA/token)" --certificate-authority=$SA/ca.crt "$@"; }

newest_pipelinerun() { OC get pipelinerun -n "$NS" --sort-by=.metadata.creationTimestamp -o jsonpath='{.items[-1:].metadata.name}' 2>/dev/null; }
pipeline_status()   { OC get pipelinerun "$1" -n "$NS" -o jsonpath='{.status.conditions[0].status} {.status.conditions[0].reason}' 2>/dev/null; }

wait_pipeline() { # $1=previous newest run; waits for a NEW run to reach a terminal state; echoes "name status"
  local prev="$1" name="" i
  for i in $(seq 1 20); do name=$(newest_pipelinerun); [ -n "$name" ] && [ "$name" != "$prev" ] && break; sleep 15; done
  [ -n "$name" ] && [ "$name" != "$prev" ] || { echo "none no-trigger"; return; }
  for i in $(seq 1 120); do
    local st; st=$(pipeline_status "$name")
    case "$st" in
      True*)  echo "$name succeeded"; return;;
      False*) echo "$name failed"; return;;
    esac
    sleep 30
  done
  echo "$name timeout"
}

gate_violations() { # writes /tmp/gate-violations.txt; echoes count
  python3 - "$SONAR_URL" "$SONAR_KEY" <<'PYEOF'
import json, sys, urllib.request, collections
base, key = sys.argv[1], sys.argv[2]
def get(path):
    with urllib.request.urlopen(base + path, timeout=30) as r: return json.load(r)
try:
    issues = get(f"/api/issues/search?componentKeys={key}&resolved=false&inNewCodePeriod=true&ps=200")
except Exception as e:
    print(0); raise SystemExit
by = collections.defaultdict(list)
for i in issues.get("issues", []):
    by[i["rule"]].append(f"{i['component'].split(':')[-1]}:{i.get('line','?')}")
with open("/tmp/gate-violations.txt", "w") as f:
    for r in sorted(by):
        f.write(f"{r} ({len(by[r])}): " + ", ".join(by[r]) + "\n")
try:
    dup = get(f"/api/measures/component_tree?component={key}&metricKeys=new_duplicated_lines&qualifiers=FIL&ps=50")
    with open("/tmp/gate-violations.txt", "a") as f:
        for c in dup.get("components", []):
            m = {x["metric"]: (x.get("period") or {}).get("value") or x.get("value") for x in c.get("measures", [])}
            dl = float(m.get("new_duplicated_lines") or 0)
            if dl > 0: f.write(f"DUPLICATION {c['path']}: {int(dl)} duplicated new lines\n")
except Exception: pass
print(issues.get("total", 0))
PYEOF
}

log "Phase E: shipping (namespace=$NS, sonar key=$SONAR_KEY)"
ROUND=1
while [ $ROUND -le $((MAX_GATE_ROUNDS+1)) ]; do
  PREV=$(newest_pipelinerun)
  git push origin main >> "$LOG" 2>&1 || { log "FATAL: git push failed"; echo push-failed > /tmp/supervisor-done; exit 1; }
  log "Phase E: pushed $(git rev-parse --short HEAD), waiting for pipeline"
  RESULT=$(wait_pipeline "$PREV"); PR_NAME=${RESULT% *}; PR_ST=${RESULT#* }
  event "phaseE" "$ROUND" "pipeline_$PR_ST" "$PR_NAME"
  log "Phase E: pipeline $PR_NAME -> $PR_ST"
  if [ "$PR_ST" = "succeeded" ]; then
    ROUTE=$(OC get route -n "$NS" -o jsonpath='{.items[0].spec.host}' 2>/dev/null)
    CODE=$(curl -sk -o /dev/null -w "%{http_code}" "https://${ROUTE}/" 2>/dev/null || echo 000)
    log "Phase E: route https://${ROUTE}/ -> HTTP ${CODE}"
    event "phaseE" "$ROUND" "route_${CODE}" done
    echo "success route=${ROUTE} http=${CODE}" > /tmp/supervisor-done
    log "SUPERVISOR COMPLETE: migration shipped"
    exit 0
  fi
  [ $ROUND -gt $MAX_GATE_ROUNDS ] && break
  # Classify WHICH pipeline stage failed — quality gate and deploy need
  # different correction packets (run #2 lesson: sonar-green pushes can
  # still crash-loop at the rollout gate).
  FAILED_TASK=$(OC get taskrun -n "$NS" -l tekton.dev/pipelineRun="$PR_NAME" \
    -o jsonpath='{range .items[?(@.status.conditions[0].status=="False")]}{.metadata.name}{"\n"}{end}' 2>/dev/null | head -1)
  log "Phase E: failed pipeline task: ${FAILED_TASK:-unknown}"
  if [[ "$FAILED_TASK" == *deploy* ]]; then
    APP=$(OC get pods -n "$NS" -o jsonpath='{range .items[*]}{.metadata.name} {.status.phase} {.status.containerStatuses[0].state.waiting.reason}{"\n"}{end}' 2>/dev/null \
      | grep -E "CrashLoopBackOff|Error" | head -1 | awk '{print $1}')
    {
      echo "Deploy-stage failure for pipeline $PR_NAME."
      echo "Failed task: $FAILED_TASK"
      echo "Crash-looping pod: ${APP:-none found}"
      echo "--- last 60 log lines of the failing pod ---"
      [ -n "$APP" ] && OC logs -n "$NS" "$APP" --tail=60 2>/dev/null
    } > /tmp/deploy-failure.txt
    run_stage "Deploy fix" "deployfix-r${ROUND}" \
"Use the migration-harness skill. Execute Phase E deploy-correction round ${ROUND}: the factory build and quality gate PASSED but the DEPLOY stage failed — the migrated service does not start in its runtime. The failure evidence (failed task, crash-looping pod, its last 60 log lines) is in /tmp/deploy-failure.txt — read it with your file tools and diagnose the root cause (typical classes: schema validation vs Flyway DDL drift, missing config/env, missing runtime dependency).
Fix the ROOT CAUSE in the repository (source, Flyway migrations under src/main/resources/db/migration/, application.properties, or k8s/ manifests). Never weaken validation to make the error disappear.
After the fix: mvn -q clean verify must pass.
Finish with ONE commit whose message STARTS with 'Deploy fix:'. DO NOT PUSH - the supervisor ships.
${OPERATOR_NOTES}" \
"Use the migration-harness skill. Continue Phase E deploy-correction round ${ROUND}; a previous attempt may have left uncommitted work - inspect git status and /tmp/deploy-failure.txt, finish the root-cause fix, run mvn -q clean verify, and commit ONE commit starting 'Deploy fix:'. DO NOT PUSH.
${OPERATOR_NOTES}" \
      || { log "Phase E: deploy-fix round $ROUND exhausted"; break; }
  else
    N=$(gate_violations)
    log "Phase E: gate round $ROUND — $N new violations exported to /tmp/gate-violations.txt"
    run_stage "Gate fix" "gatefix-r${ROUND}" \
"Use the migration-harness skill. Execute Phase E gate-correction round ${ROUND}: the factory SonarQube quality gate REJECTED the push. The complete violation list (rule (count): file:line, plus DUPLICATION lines) is in /tmp/gate-violations.txt — read it with your file tools.
Dispatch the fixes to the worker in SMALL packets per the packet size rule: group by rule, at most ~10 sites per packet, one concern per packet, sequentially. Duplication lines mean consolidation (records / static factories), not suppression.
Business logic must be unchanged — never invert boolean conditions when converting to isEmpty(). Fixes must not INTRODUCE new sites of the same rules (e.g. new exception classes bringing undeclarable throws clauses).
After all packets: mvn -q clean verify must pass and JaCoCo coverage stays >= 80%.
Finish with ONE commit whose message STARTS with 'Gate fix:'. DO NOT PUSH - the supervisor ships.
${OPERATOR_NOTES}" \
"Use the migration-harness skill. Continue Phase E gate-correction round ${ROUND}; a previous attempt may have left uncommitted fixes - inspect git status, finish the remaining violations from /tmp/gate-violations.txt, run mvn -q clean verify, and commit ONE commit starting 'Gate fix:'. DO NOT PUSH.
${OPERATOR_NOTES}" \
      || { log "Phase E: gate-fix round $ROUND exhausted"; break; }
  fi
  ROUND=$((ROUND+1))
done
echo "gate-failed after $((ROUND-1)) rounds" > /tmp/supervisor-done
log "SUPERVISOR COMPLETE: factory gate not passed — see /tmp/gate-violations.txt and migration/debt.md"
exit 1
