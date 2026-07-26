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
MAX_FACTORY_ROUNDS=4      # Phase E correction rounds (build/gate/deploy classes share the budget)

RUN_BASE="${RUN_BASE:-$(git rev-parse HEAD)}"   # commits after this belong to THIS run (env-overridable for resume)
SUPERVISOR_VERSION=$(md5sum "$0" 2>/dev/null | cut -c1-8)
LOG=/tmp/supervisor.log
EVENTS=/tmp/supervisor-events.csv
METRICS=/tmp/supervisor-metrics.csv
[ -f "$EVENTS" ]  || echo "epoch,stage,attempt,class,action" > "$EVENTS"
[ -f "$METRICS" ] || echo "session,start,end,seconds,rc" > "$METRICS"

log()   { echo "[$(date -u +%F' '%T)] $*" >> "$LOG"; }

log "supervisor start: version=${SUPERVISOR_VERSION} run_base=${RUN_BASE} orch=${ORCH_PROVIDER}/${ORCH_MODEL} worker=${WORKER_MODEL}"
# C1: per-run isolated Maven repo — factory-parity resolution for every sensor
.hermes/harness/sensors.sh seed >> "$LOG" 2>&1 || log "WARN: isolated repo seed failed — sensors fall back to red-on-use"
event() { echo "$(date -u +%s),$1,$2,$3,$4" >> "$EVENTS"; }

# Process contract only — ALL judgment guidance (packet rules, sensors,
# gate bars, dispatch discipline) lives in the migration-harness skill
# and AGENTS.md. The supervisor injects nothing but run configuration
# and the commit/ship contract.
RUN_CONTRACT="Run contract: the worker model for this run is WORKER_MODEL_PLACEHOLDER. DO NOT PUSH anywhere - the supervisor ships. Finish with ONE commit using the exact message prefix stated below."
RUN_CONTRACT="${RUN_CONTRACT//WORKER_MODEL_PLACEHOLDER/$WORKER_MODEL}"

committed() { git log --oneline "${RUN_BASE}..HEAD" | grep -q " $1:"; }

# NOTE: match the worker by exact process name (-x). Command-line matching
# false-positives on hermes sessions whose loaded skill text quotes the
# `opencode run` invocation.
wait_for_worker() {
  local waited=0
  while pgrep -x opencode >/dev/null 2>&1; do
    [ $waited -eq 0 ] && log "worker process still running — waiting for it before next session"
    sleep 60; waited=$((waited+60))
    if [ $waited -ge 3600 ]; then
      # A worker this old has outlived its dispatching session — it is a
      # zombie. Never run a new session alongside it (two-writer risk):
      # kill it and let the next session verify whatever it left behind.
      log "worker still running after 60m — killing zombie worker before proceeding"
      pkill -9 -x opencode; sleep 2
      break
    fi
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
  [ $((t1-t0)) -gt 1800 ] && { event "$tag" 0 slow_session "$((t1-t0))s"; log "$tag: SLOW session ($((t1-t0))s) — wedge candidate"; }
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
    if committed "$prefix"; then
      event "$tag" "$attempt" success commit; log "$tag: committed $(git log --oneline -1)"
      # Escalation KPI: the orchestrator marks direct implementations with
      # an ESCALATED run-log row — count them for the retro.
      if tail -5 migration/run-log.md 2>/dev/null | grep -q "ESCALATED"; then
        event "$tag" "$attempt" escalated kpi; log "$tag: ESCALATED — orchestrator implemented directly (packet-quality KPI)"
      fi
      # The stage is sealed — any worker still running is a zombie whose
      # output can no longer land. Kill it now instead of waiting 60m.
      if pgrep -x opencode >/dev/null 2>&1; then
        log "$tag: killing residual worker (stage already committed)"
        pkill -9 -x opencode
      fi
      return 0
    fi
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
        prompt="$rprompt"; pf=$((pf+1));;
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

write_run_report() { # $1 = outcome line
  {
    echo "# Autonomous run report"
    echo ""
    echo "- Outcome: $1"
    echo "- Supervisor version: ${SUPERVISOR_VERSION}; run base: ${RUN_BASE}"
    echo "- Orchestrator: ${ORCH_PROVIDER}/${ORCH_MODEL}; worker: ${WORKER_MODEL}"
    echo ""
    echo "## Sessions"
    echo ""
    echo "| session | seconds | rc |"
    echo "|---|---|---|"
    awk -F, 'NR>1 {printf "| %s | %s | %s |\n", $1, $4, $5}' "$METRICS"
    echo ""
    echo "## Classified events"
    echo ""
    echo '```'
    awk -F, 'NR>1 {print $4}' "$EVENTS" | sort | uniq -c | sort -rn
    echo '```'
  } > migration/run-report.md
  git add migration/run-report.md && git commit -q -m "Run report: $1" 2>/dev/null || true
}

# ---------------------------------------------------------------- Phase A/B
if committed "Phase A" || [ -f migration/mta-findings.json ]; then
  log "Phase A: already present"
else
  run_stage "Phase A" "phaseA" \
"Use the migration-harness skill and read PLANNING.md in its directory. Execute Phase A ONLY: normalize ground truth into migration/mta-findings.json (prefer the legacy IDE analysis under /projects/legacy/.vscode/mta-core/). Print a violation summary with a terminal python3 heredoc (never read the file whole).
${RUN_CONTRACT}
Finish with ONE commit whose message STARTS with 'Phase A:'. Stop after Phase A." \
"Use the migration-harness skill and read PLANNING.md in its directory. Execute Phase A ONLY per the skill; a previous attempt did not commit. Verify migration/mta-findings.json exists and is valid konveyor JSON, then commit with message starting 'Phase A:'. ${RUN_CONTRACT}" \
    || { log "FATAL: Phase A failed"; echo phaseA-failed > /tmp/supervisor-done; exit 1; }
fi

if committed "Phase B" && ls specs/*/tasks.md >/dev/null 2>&1; then
  log "Phase B: already present"
else
  run_stage "Phase B" "phaseB" \
"Use the migration-harness skill and read PLANNING.md in its directory. Phase A is committed. Execute Phase B ONLY: read the legacy code under /projects/legacy and the findings (scripted extraction only), then write specs/001-coolstore-migration/spec.md, plan.md and tasks.md per the skill. Every mandatory finding maps to at least one task; rewrite tasks before infer tasks; every task heading uses the form '### T-NNN: title' with zero-padded numeric ids (T-001, T-002, ...). The spec MUST cover the legacy application's user-facing surface (web UI / index page) — either map it to a migration task or explicitly waive it with a reason.
${RUN_CONTRACT}
Finish with ONE commit whose message STARTS with 'Phase B:'. Stop after Phase B." \
"Use the migration-harness skill and read PLANNING.md in its directory. Execute Phase B ONLY; a previous attempt did not commit. If specs/001-coolstore-migration/{spec,plan,tasks}.md exist and are complete, commit them with message starting 'Phase B:'; otherwise finish writing them first. ${RUN_CONTRACT}" \
    || { log "FATAL: Phase B failed"; echo phaseB-failed > /tmp/supervisor-done; exit 1; }
fi

# ------------------------------------------------------------- Plan lint
# Deterministic B2 gate: a defective plan is bounced ONCE for revision
# with the specific lint findings before Phase C spends hours on it.
TASKS_FILE=$(ls specs/*/tasks.md 2>/dev/null | head -1)
LINT_OUT=$(python3 .hermes/harness/plan-lint.py "$TASKS_FILE" migration/mta-findings.json 2>&1)
if [ $? -ne 0 ] && ! committed "Phase B revision"; then
  log "plan lint: revision required"; echo "$LINT_OUT" | head -20 >> "$LOG"
  printf '%s\n' "$LINT_OUT" > /tmp/plan-lint.txt
  run_stage "Phase B revision" "phaseB-lint" \
"Use the migration-harness skill and read PLANNING.md and MAPPINGS.md in its directory. The plan lint REJECTED specs/*/tasks.md — the findings are in /tmp/plan-lint.txt (read it with your file tools). Revise the plan to fix every lint finding: infer tasks must carry the decided target design (file mappings, signatures, annotations — cite MAPPINGS.md shapes). Do not renumber or remove completed work.
${RUN_CONTRACT}
Commit prefix: 'Phase B revision:'." \
"Use the migration-harness skill and read PLANNING.md in its directory. Finish revising the plan per /tmp/plan-lint.txt and commit with prefix 'Phase B revision:'.
${RUN_CONTRACT}" \
    || log "plan lint: revision round exhausted — proceeding with the plan as-is (recorded)"
  LINT2=$(python3 .hermes/harness/plan-lint.py "$TASKS_FILE" migration/mta-findings.json 2>&1) \
    && log "plan lint: PASS after revision" || log "plan lint: still failing after revision — proceeding, findings logged"
fi

# ---------------------------------------------------------------- Phase C
TASKS_FILE=$(ls specs/*/tasks.md 2>/dev/null | head -1)
# Accept 3-6 hash heading levels and any T-style id — models format
# tasks.md differently no matter what the prompt mandates (run #3 lesson).
TASK_IDS=$(grep -E '^#{3,6} +T[-A-Za-z0-9]*[0-9]+:' "$TASKS_FILE" | sed -E 's/^#+ +(T[-A-Za-z0-9]*[0-9]+):.*/\1/')
[ -n "$TASK_IDS" ] || { log "FATAL: no task ids parsed from $TASKS_FILE"; echo no-tasks > /tmp/supervisor-done; exit 1; }
log "task list: $(echo $TASK_IDS | tr '\n' ' ')"

for T in $TASK_IDS; do
  committed "$T" && { log "$T: already committed"; continue; }
  run_stage "$T" "$T" \
"Use the migration-harness skill and read EXECUTION.md in its directory. Execute Phase C for task ${T} from ${TASKS_FILE} ONLY.
${RUN_CONTRACT}
Finish with ONE commit whose message STARTS with '${T}:'. Stop after ${T}." \
"Use the migration-harness skill and read EXECUTION.md in its directory. Execute Phase C for task ${T} from ${TASKS_FILE} ONLY. A previous attempt may have left partial uncommitted work or a finished worker run - inspect git status first, verify or finish the work, run the sensors, and commit ONE commit whose message STARTS with '${T}:'.
${RUN_CONTRACT}" \
    || log "$T: exhausted — recorded, moving on"
done

# ---------------------------------------------------------------- Phase D
if ! committed "Phase D"; then
  run_stage "Phase D" "phaseD" \
"Use the migration-harness skill and read SHIPPING.md in its directory. All tasks are executed (see migration/run-log.md and migration/debt.md). Execute Phase D per SHIPPING.md: re-analysis sensor, findings delta appended to the run-log with remaining findings individually explained, and mvn -q clean verify green.
${RUN_CONTRACT}
Commit prefix: 'Phase D:'. DO NOT PUSH." \
"Use the migration-harness skill and read SHIPPING.md in its directory. Execute Phase D per the skill; a previous attempt did not commit. Verify migration/mta-findings-after.json and the delta section exist, mvn -q clean verify passes, then commit with message starting 'Phase D:'. ${RUN_CONTRACT}" \
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
  if [ -z "$name" ] || [ "$name" = "$prev" ]; then
    # No new run (e.g. resume after a failure with nothing new pushed):
    # judge the newest existing run instead of erroring out.
    name="$prev"
    [ -n "$name" ] || { echo "none no-trigger"; return; }
  fi
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
BUILD_R=0; GATE_R=0; DEPLOY_R=0
MAX_PER_CLASS=2
while :; do
  PREV=$(newest_pipelinerun)
  git push origin main >> "$LOG" 2>&1 || { log "FATAL: git push failed"; write_run_report "push-failed"; echo push-failed > /tmp/supervisor-done; exit 1; }
  log "Phase E: pushed $(git rev-parse --short HEAD), waiting for pipeline"
  RESULT=$(wait_pipeline "$PREV"); PR_NAME=${RESULT% *}; PR_ST=${RESULT#* }
  event "phaseE" 0 "pipeline_$PR_ST" "$PR_NAME"
  log "Phase E: pipeline $PR_NAME -> $PR_ST"
  if [ "$PR_ST" = "succeeded" ]; then
    # E2: success = demo acceptance, not HTTP liveness — index page serves
    # AND the products API returns a non-empty catalog.
    ROUTE=$(OC get route -n "$NS" -o jsonpath='{.items[0].spec.host}' 2>/dev/null)
    sleep 10
    CODE=$(curl -sk -o /dev/null -w "%{http_code}" "https://${ROUTE}/" 2>/dev/null || echo 000)
    PRODUCTS=$(curl -sk "https://${ROUTE}/api/products" 2>/dev/null | python3 -c "import json,sys; print(len(json.load(sys.stdin)))" 2>/dev/null || echo 0)
    log "Phase E: route / -> ${CODE}; /api/products -> ${PRODUCTS} products"
    if [ "$CODE" = "200" ] && [ "${PRODUCTS:-0}" -gt 0 ]; then
      event "phaseE" 0 "acceptance_pass" "route=${CODE},products=${PRODUCTS}"
      write_run_report "success: shipped, route 200, ${PRODUCTS} products"
      git push origin main >> "$LOG" 2>&1 || true
      echo "success route=${ROUTE} http=${CODE} products=${PRODUCTS}" > /tmp/supervisor-done
      log "SUPERVISOR COMPLETE: migration shipped and accepted"
      exit 0
    fi
    log "Phase E: pipeline green but ACCEPTANCE failed (/ ${CODE}, products ${PRODUCTS}) — deploy-correction round"
    {
      echo "Acceptance failure: pipeline green but the demo acceptance is unmet."
      echo "Route / returned HTTP ${CODE} (need 200 — the storefront index page must exist)."
      echo "/api/products returned ${PRODUCTS} products (need > 0 — the legacy catalog must be served)."
      echo "If the plan waived the UI surface, the waive is OVERRIDDEN by the demo acceptance: add a minimal index page over /api/products."
    } > /tmp/deploy-failure.txt
    FAILED_TASK="acceptance-deploy"
  else
    FAILED_TASK=$(OC get taskrun -n "$NS" -l tekton.dev/pipelineRun="$PR_NAME"       -o jsonpath='{range .items[?(@.status.conditions[0].status=="False")]}{.metadata.name}{"\n"}{end}' 2>/dev/null | head -1)
    log "Phase E: failed pipeline task: ${FAILED_TASK:-unknown}"
  fi
  if [[ "$FAILED_TASK" == *maven-build* || "$FAILED_TASK" == *build-and-push* ]]; then
    CLASS=build; BUILD_R=$((BUILD_R+1)); ROUND=$BUILD_R
    [ $BUILD_R -gt $MAX_PER_CLASS ] && { log "Phase E: build round budget exhausted"; break; }
    {
      echo "Build-stage failure for pipeline $PR_NAME (task: $FAILED_TASK)."
      echo "--- maven/build errors ---"
      OC logs -n "$NS" -l tekton.dev/taskRun="$FAILED_TASK" --tail=80 2>/dev/null | grep -iE "ERROR|BUILD|Caused|Could not" | head -30
    } > /tmp/build-failure.txt
    run_stage "Build fix r${ROUND}" "buildfix-r${ROUND}" \
"Use the migration-harness skill and read SHIPPING.md in its directory. Execute the Phase E BUILD-correction procedure for round ${ROUND}: the failure evidence is in /tmp/build-failure.txt - read it with your file tools and follow SHIPPING.md for this correction class. Finish with .hermes/harness/sensors.sh preflight GREEN before committing.
${RUN_CONTRACT}
Commit prefix: 'Build fix r${ROUND}:'." \
"Use the migration-harness skill and read SHIPPING.md in its directory. Continue Phase E build-correction round ${ROUND}; inspect git status and /tmp/build-failure.txt, finish the root-cause fix, run .hermes/harness/sensors.sh preflight, and commit ONE commit starting 'Build fix r${ROUND}:'. DO NOT PUSH.
${RUN_CONTRACT}" \
      || { log "Phase E: build-fix round $ROUND exhausted"; break; }
  elif [[ "$FAILED_TASK" == *deploy* ]]; then
    CLASS=deploy; DEPLOY_R=$((DEPLOY_R+1)); ROUND=$DEPLOY_R
    [ $DEPLOY_R -gt $MAX_PER_CLASS ] && { log "Phase E: deploy round budget exhausted"; break; }
    if [ "$FAILED_TASK" != "acceptance-deploy" ]; then
      APP=$(OC get pods -n "$NS" -o jsonpath='{range .items[*]}{.metadata.name} {.status.phase} {.status.containerStatuses[0].state.waiting.reason}{"\n"}{end}' 2>/dev/null \
        | grep -E "CrashLoopBackOff|Error" | head -1 | awk '{print $1}')
      {
        echo "Deploy-stage failure for pipeline $PR_NAME."
        echo "Failed task: $FAILED_TASK"
        echo "Crash-looping pod: ${APP:-none found}"
        echo "--- last 60 log lines of the failing pod ---"
        [ -n "$APP" ] && OC logs -n "$NS" "$APP" --tail=60 2>/dev/null
      } > /tmp/deploy-failure.txt
    fi
    run_stage "Deploy fix r${ROUND}" "deployfix-r${ROUND}" \
"Use the migration-harness skill and read SHIPPING.md in its directory. Execute the Phase E DEPLOY-correction procedure for round ${ROUND}: the failure evidence is in /tmp/deploy-failure.txt - read it with your file tools and follow SHIPPING.md for this correction class. Finish with .hermes/harness/sensors.sh preflight GREEN before committing.
${RUN_CONTRACT}
Commit prefix: 'Deploy fix r${ROUND}:'." \
"Use the migration-harness skill and read SHIPPING.md in its directory. Continue Phase E deploy-correction round ${ROUND}; inspect git status and /tmp/deploy-failure.txt, finish the root-cause fix, run .hermes/harness/sensors.sh preflight, and commit ONE commit starting 'Deploy fix r${ROUND}:'. DO NOT PUSH.
${RUN_CONTRACT}" \
      || { log "Phase E: deploy-fix round $ROUND exhausted"; break; }
  else
    CLASS=gate; GATE_R=$((GATE_R+1)); ROUND=$GATE_R
    [ $GATE_R -gt $MAX_PER_CLASS ] && { log "Phase E: gate round budget exhausted"; break; }
    N=$(gate_violations)
    log "Phase E: gate round $ROUND — $N new violations exported to /tmp/gate-violations.txt"
    run_stage "Gate fix r${ROUND}" "gatefix-r${ROUND}" \
"Use the migration-harness skill and read SHIPPING.md in its directory. Execute the Phase E GATE-correction procedure for round ${ROUND}: the failure evidence is in /tmp/gate-violations.txt - read it with your file tools and follow SHIPPING.md for this correction class. Finish with .hermes/harness/sensors.sh milestone GREEN before committing (it runs the factory's own sonar gate locally - iterate until it passes).
${RUN_CONTRACT}
Commit prefix: 'Gate fix r${ROUND}:'." \
"Use the migration-harness skill and read SHIPPING.md in its directory. Continue Phase E gate-correction round ${ROUND}; inspect git status, finish the remaining violations from /tmp/gate-violations.txt, run .hermes/harness/sensors.sh milestone until GREEN, and commit ONE commit starting 'Gate fix r${ROUND}:'. DO NOT PUSH.
${RUN_CONTRACT}" \
      || { log "Phase E: gate-fix round $ROUND exhausted"; break; }
  fi
done
write_run_report "factory not passed (build=${BUILD_R} gate=${GATE_R} deploy=${DEPLOY_R} rounds)"
git push origin main >> "$LOG" 2>&1 || true
echo "factory-failed build=${BUILD_R} gate=${GATE_R} deploy=${DEPLOY_R}" > /tmp/supervisor-done
log "SUPERVISOR COMPLETE: factory not passed — evidence preserved for the retro"
exit 1
