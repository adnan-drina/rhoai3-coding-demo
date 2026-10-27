#!/usr/bin/env bash
# Stage 130 validation: MTA 8.3 and its AI components, the migration platform the Stage 070 factory provisions, and
# the golden migration scaffold (its contracts, pins and self-tests; the scaffold's own Python tests run as the
# content they test). Read-only; models stay stopped.
# --run checks one migration run before launch (see the run section below; needs WORKSPACE, POD, GOLDEN_CHECKOUT,
# GOLDEN_SHA and PLATFORM_SHA).
# Usage: stages/130-ai-autonomous-migration/validate.sh [--run]
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "$SCRIPT_DIR/../.." && pwd)"
source "$REPO_ROOT/scripts/lib.sh"
case "${1:-}" in
  --run|"") ;;
  *) sed -n 's/^# Usage: //p' "$0" >&2; exit 1 ;;
esac
load_env
check_oc_logged_in

# ── Launch check of one migration run (--run) ────────────────────────────────────────────────────────────────────
# Read-only launch check for ANY run created by the app-migration factory after 2026-09-24 (run-budget.json schema
# v2). Does not reset data, mint cards, or install a harness. Required: WORKSPACE (the run: the full project name, never
# a suffix), POD, GOLDEN_CHECKOUT (verified published checkout), GOLDEN_SHA, PLATFORM_SHA (the merged platform
# revision); optional NS (wksp-ai-developer), CONTAINER (development-tooling), EXPECTED_MODEL. The expected model and
# wall budget are read from the golden's run-defaults.json, so a pin change is made once, in the golden.
# The checks inside the workspace import the installed harness (planner.run_identity, run_declaration,
# outcome_protocol, maas_route), so they run as one Python program in the workspace container.
run_fail() { echo "FAIL: $*" >&2; exit 1; }
# jq: the run-stop pins (v32): the selected model profile's run_input_token_budget (and, with loop escalation,
# retry_start_turns) and the golden's run-level budget.run_input_token_budget and no_accepted_checkpoint_minutes.
RUN_STOP_GAPS='def positive: type == "number" and . > 0 and . == floor;
  def run_stop_gaps($doc; $model; $defaults):
    (if ($doc | type) == "object" then ($doc.profiles // {})[$model] else null end) as $p
    | if ($p | type) != "object" then ["RUN_TOKEN_BUDGET: no model profile for \($model)"]
      else [ (if ($p.run_input_token_budget | positive) then empty
               else "RUN_TOKEN_BUDGET: the profile for \($model) pins no positive run_input_token_budget" end),
             (if ($p.loop_escalation | type) == "object" and $p.loop_escalation.enabled == true and (($p.loop_escalation.retry_start_turns | positive) | not)
               then "RUN_TOKEN_BUDGET: the profile for \($model) enables loop_escalation without a positive retry_start_turns" else empty end),
             (($defaults // {}).budget // {}) as $b | ("run_input_token_budget", "no_accepted_checkpoint_minutes")
               | select(($b[.] | positive) | not) | "RUN_STOPS: run-defaults.json budget.\(.) is not a positive integer" ] end;'
# jq: the provisioning receipt binds the golden's pinned database and provisioner images.
IMAGE_BINDINGS='def image_binding_gaps($defaults; $receipt): ($defaults.configuration.images // {}) as $i
  | [("databaseImage", "provisionerImage") as $k
     | if (($i[$k] | type) != "string") or (($i[$k] | test(".+@sha256:[0-9a-f]{64}$")) | not) then "golden lacks a pinned \($k)"
       elif $receipt[$k] != $i[$k] then "provisioning receipt differs from golden: \($k)" else empty end];'
# jq: the worker runs as the per-run ServiceAccount, bound to devworkspace-default-role by no subject.
WORKER_IDENTITY='def worker_identity_gaps($pod; $receipt; $binding; $ns; $ws): ($ws + "-worker") as $sa
  | [ (if $receipt.workerServiceAccount != $sa then "provisioning receipt does not bind the per-run worker identity" else empty end),
      (if $pod.spec.serviceAccountName != $sa then "workspace pod still uses a generated or foreign ServiceAccount" else empty end),
      (($binding.subjects // [])[] | select((.kind == "ServiceAccount" and .name == $sa and (.namespace // $ns) == $ns)
          or (.kind == "Group" and (.name | IN("system:authenticated", "system:serviceaccounts", "system:serviceaccounts:" + $ns)))
          or (.kind == "User" and .name == "system:serviceaccount:\($ns):\($sa)")) | "worker is bound to devworkspace-default-role") ] | unique;'
# jq: the worker container's kubeconfig directory is an ephemeral emptyDir; the legacy source is mounted read-only
# from a claim no container mounts writable at, above or below the same path.
POD_MOUNTS='def worker($p; $c): $p.spec.containers[] | select(.name == $c);
  def kubeconfig_mount_ok($p; $c): worker($p; $c) as $w
    | (([$w.env[]? | {key: .name, value: .value}] | from_entries).KUBECONFIG == "/home/user/.kube/config")
      and ([$w.volumeMounts[]? | select(.mountPath == "/home/user/.kube")] as $m
           | ($m | length) == 1 and ([$p.spec.volumes[]? | select(.name == $m[0].name)][0] // {} | has("emptyDir")));
  def source_mount_ok($p; $c): worker($p; $c) as $w
    | [$w.volumeMounts[]? | select(.mountPath == "/projects/legacy")] as $m
    | if ($m | length) != 1 or ($m[0].readOnly | not) then false else
        ([$p.spec.volumes[] | {key: .name, value: (.persistentVolumeClaim.claimName // null)}] | from_entries) as $claims
        | $claims[$m[0].name] as $claim | ($m[0].subPath // "" | ltrimstr("/") | rtrimstr("/")) as $src
        | if $claim == null or $src == "" or $m[0].subPathExpr != null then false else
            all($p.spec.containers[].volumeMounts[]? | select($claims[.name] == $claim and (.readOnly | not));
              (.subPath // "" | ltrimstr("/") | rtrimstr("/")) as $parent
              | (.subPathExpr == null) and $parent != "" and $src != $parent
                and (($src | startswith($parent + "/")) | not) and (($parent | startswith($src + "/")) | not)) end end;'
IN_WORKSPACE_CHECKS=$(cat <<'PY'
def require(condition, message):
    if not condition:
        raise AssertionError(message)
import hashlib, json, os, sys, subprocess
from pathlib import Path
root = Path('/projects/modernized')
# Check the CLI credential as well as the admitted pod identity. Do not print
# kubeconfig contents or token values. The replacement Config has one user.
kube = json.loads(subprocess.check_output(['oc', 'config', 'view', '-o', 'json'], text=True))
users = kube.get('users', [])
require(len(users) == 1 and users[0].get('name') == 'current-pod'
        and users[0].get('user') == {'tokenFile': '/var/run/secrets/kubernetes.io/serviceaccount/token'},
        'CLI kubeconfig retains a different credential')
require(subprocess.check_output(['oc', 'whoami'], text=True).strip() == WORKER_IDENTITY,
        'CLI credential is not the per-run worker')
sys.path.insert(0, str(root / '.hermes/lib'))
from planner import run_identity
from planner.yamlite import load_yaml
expected = json.loads(EXPECTED)
require(all(((root / k).is_file() and hashlib.sha256((root / k).read_bytes()).hexdigest() == v for k, v in expected.items())), 'installed harness differs from golden')
v = run_identity.check(root)
require(v.code == run_identity.OK, str(v))
require(not run_identity.fixture_gaps(root), 'fixture variables missing')
import socket
with socket.create_connection((v.observed['host'], v.observed['port']), timeout=5):
    pass
issued = root / 'verification/loop/issued.json'
require(not issued.exists() or not json.loads(issued.read_text()).get('task_id'), 'card already issued')
require(not (root / 'evidence/producers/bootstrap.json').exists(), 'preflight requires a fresh destination before bootstrap')
require(not (root / 'src/main/java').exists(), 'product sources present before bootstrap')
d = load_yaml(root / 'decisions.yaml')
require(d.get('loop', {}).get('unit_formation') == 'v1' and d.get('loop', {}).get('runtime_feedback') == 'v1' and d.get('loop', {}).get('plan_semantics') == 'v1', 'loop flags (unit_formation, runtime_feedback, plan_semantics v1)')
r = d['decided_repairs']
require(hashlib.sha256((root / r['manifest']).read_bytes()).hexdigest() == r['manifest_sha256'], 'repair manifest mismatch')
config = next((p for p in (Path('/etc/hermes/config.yaml'), Path('/projects/.platform/hermes/config.yaml')) if p.is_file()), None)
require(config, 'managed Hermes config missing')
c = load_yaml(config)
# The effective hook registrations (Stage 050 producer): K2 fail-closed with the
# complete terminator in its matcher and a 5 s timeout; the terminal
# post_tool_call observer the harness ships (V17-6b), never fail-closed.
hooks = c.get('hooks') or {}
k2 = [h for h in hooks.get('pre_tool_call') or [] if str(h.get('command', '')).endswith('pre_tool_call.sh')]
require(len(k2) == 1 and k2[0].get('fail_closed') is True and k2[0].get('timeout') == 5
        and 'kanban_complete' in str(k2[0].get('matcher', '')).split('|'),
        'the K2 pre_tool_call hook is not registered fail-closed with a 5 s timeout')
require((root / '.hermes/kernel/post_tool_call.py').is_file()
        and any(h.get('matcher') == 'terminal' and str(h.get('command', '')).endswith('post_tool_call.py')
                and not h.get('fail_closed') for h in hooks.get('post_tool_call') or []),
        'the terminal post_tool_call observer is not shipped or not registered')
# v32: the in-workspace stops (kernel/run_budget.py): the per-run token budget before every tool call
# (fail-open, never fail-closed) and the run-level stops on the dispatcher tick; the launch shim
# (kernel/worker_launch.py) is the dispatcher's HERMES_BIN.
if (root / '.hermes/kernel/run_budget.py').is_file():
    require(any(h.get('matcher') == '.*' and str(h.get('command', '')).endswith('run_budget.py pre-tool')
                and not h.get('fail_closed') for h in hooks.get('pre_tool_call') or []),
            'RUN_TOKEN_BUDGET: the per-run budget hook is not registered (pre_tool_call .* run_budget.py pre-tool)')
    require(any(' tick --root ' in str(h.get('command', '')) and 'run_budget.py' in str(h.get('command', ''))
                for h in hooks.get('on_kanban_dispatch_tick') or []),
            'RUN_STOPS: the run-level stops are not registered on the dispatcher tick (run_budget.py tick)')
if (root / '.hermes/kernel/worker_launch.py').is_file():
    _shim = config.parent / 'bin' / 'hermes-worker-launch'
    _envt = (config.parent / '.env').read_text() if (config.parent / '.env').is_file() else ''
    require(('HERMES_BIN=%s' % _shim) in _envt.splitlines() and _shim.is_file(),
            'RETRY_ESCALATION: the managed .env does not route worker spawns through the launch shim (HERMES_BIN)')
require(c.get('model', {}).get('default') == 'publishers/internal-models/models/' + MODEL, 'worker model mismatch')
import socket
from urllib.parse import urlsplit
require(urlsplit(os.environ.get('MAAS_API_BASE_URL', '')).hostname == MAASHOSTVAL, 'worker MaaS endpoint is not the platform gateway host')
addrs = {a[4][0] for a in socket.getaddrinfo(MAASHOSTVAL, 443, proto=socket.IPPROTO_TCP)}
require(addrs == {MAASIPVAL}, 'MaaS host resolves to %s, not the in-cluster gateway %s: the workspace is on the public ELB path' % (sorted(addrs), MAASIPVAL))
# B3 / R2: the run's ENFORCED allowance (the Hermes pacer, patch 0007, paces
# every model request of the run -- main, each retry, auxiliary, reviewer --
# to max_requests_per_window) at the largest request the SERVER admits (the
# pacer counts requests, not input tokens, so the bound is the served window,
# prompt plus output: vLLM --max-model-len) plus the declared reserve for
# every other consumer, fits the subscription's limit. The profile is the one
# PINNED for this run.
def rate_budget_gap(q, served, runs, limit):
    reserve = int(q['reserve_tokens_per_window'])
    if q.get('accounting_mode') == 'token':
        # V15-1: reserved-and-settled tokens (runtime 0010). Each request
        # reserves reservation_tokens (at least the served window) and is
        # admitted while settled + open + reservation <= the run allowance, so
        # the run can never exceed its allowance; admission sums allowances.
        allowance, reservation = int(q['token_allowance_per_window']), int(q['reservation_tokens'])
        if 'max_requests_per_window' in q:
            return 'a token-mode profile also declares a request ceiling (max_requests_per_window)'
        if reservation < served:
            return 'the profile reserves %d tokens per request and the model serves %d' % (reservation, served)
        if not 0 < reservation <= allowance:
            return 'the reservation %d does not fit the allowance %d' % (reservation, allowance)
        if not 0 < int(q['max_output_tokens']) < reservation:
            return 'the output cap %s does not fit a %d-token request' % (q['max_output_tokens'], reservation)
        total = runs * allowance + reserve
        if total > limit:
            return 'effective %d, declared %d (%d run(s) x %d token allowance + reserve %d)' % (limit, total, runs, allowance, reserve)
        return ''
    per_request = int(q['max_request_tokens'])
    if per_request < served:
        return 'the profile sizes a request at %d tokens and the model serves %d' % (per_request, served)
    if not 0 < int(q['max_output_tokens']) < per_request:
        return 'the output cap %s does not fit a %d-token request' % (q['max_output_tokens'], per_request)
    total = runs * int(q['max_requests_per_window']) * per_request + reserve
    if total > limit:
        return 'effective %d, declared %d (%d run(s) x %d requests x %d tokens + reserve %d)' % (
            limit, total, runs, int(q['max_requests_per_window']), per_request, reserve)
    return ''
prof_path = Path('/etc/rhoai3/run-control/profile.json')
if not prof_path.is_file():
    prof_path = Path('/projects/.platform/hermes/model-profile.json')
prof_doc = json.loads(prof_path.read_text())
prof = prof_doc['profiles'][prof_doc['default_model']]
q = prof['quota']
runs = 1 + QOTHERSVAL
win = '%dh' % (int(q['window_seconds']) // 3600) if int(q['window_seconds']) % 3600 == 0 else '%ds' % int(q['window_seconds'])
require(win == QWINVAL, 'the profile paces per %s and the subscription limits per %s' % (win, QWINVAL))
budget_gap = rate_budget_gap(q, WINDOW, runs, QLIMITVAL)
require(not budget_gap, 'MOD' + 'EL_RATE_BUDGET: %s, quota devspaces-coding-models/%s: %s; profile %s'
        % (prof_doc['default_model'], QWINVAL, budget_gap, prof_path))
env_text = Path('/projects/.platform/hermes/.env').read_text() if Path('/projects/.platform/hermes/.env').is_file() else ''
require(((q.get('accounting_mode') == 'token'
          and 'RHOAI3_ACCOUNTING_MODE=token' in env_text
          and 'RHOAI3_TOKEN_BUDGET=%d/%d' % (int(q.get('token_allowance_per_window') or 0), int(q['window_seconds'])) in env_text
          and 'RHOAI3_TOKEN_RESERVATION=%d' % int(q.get('reservation_tokens') or 0) in env_text
          and 'RHOAI3_REQUEST_BUDGET=' not in env_text)
         or (q.get('accounting_mode') != 'token'
             and 'RHOAI3_REQUEST_BUDGET=%d/%d' % (int(q.get('max_requests_per_window') or 0), int(q['window_seconds'])) in env_text))
        and 'RHOAI3_REQUEST_LEDGER=' in env_text,
        'the worker runtime is not configured to pace this allowance (RHOAI3_REQUEST_BUDGET/LEDGER in the managed .env)')
# B1: the workspace's own startup gate (planner.maas_route) must agree with
# the cluster truth read above: the platform values stamped into this
# workspace name that gateway and address, and TLS verifies through it.
if (root / '.hermes/lib/planner/maas_route.py').is_file():
    require(os.environ.get('RHOAI3_MAAS_HOST') == MAASHOSTVAL and os.environ.get('RHOAI3_MAAS_INTERNAL_IP') == MAASIPVAL,
            'the workspace was stamped with MaaS route %s -> %s, the cluster gateway is %s -> %s: refresh the factory routing input'
            % (os.environ.get('RHOAI3_MAAS_HOST'), os.environ.get('RHOAI3_MAAS_INTERNAL_IP'), MAASHOSTVAL, MAASIPVAL))
    sys.path.insert(0, str(root / '.hermes/lib'))
    from planner.maas_route import route_gaps
    gaps, _rec = route_gaps(dict(os.environ))
    require(not gaps, 'STARTUP_MAAS_ROUTE: %s' % (gaps[0] if gaps else ''))

def leaves(x):
    if isinstance(x, dict):
        for k, v in x.items():
            if k == 'context_length':
                yield int(v)
            elif isinstance(v, (dict, list)):
                yield from leaves(v)
    elif isinstance(x, list):
        for v in x:
            yield from leaves(v)
# the SELECTED model's limits against the selected model's served window (E-1 v31, 2026-10-01: with
# qwen3-6-27b selected, the still-configured qwen38 provider's 220000 -- below ITS 262144 window --
# was compared with qwen3-6-27b's 131072 and refused a correct config)
_m = c.get('model') or {}
_sel = ((c.get('providers') or {}).get(_m.get('provider')) or {}).get('models', {}).get(_m.get('default'))
windows = list(leaves({'model': _m, 'selected': _sel or {}}))
require(_sel is not None, 'the selected model has no provider entry')
require(windows and all((0 < v < WINDOW for v in windows)), 'context limit must be below served window')
require(c.get('terminal', {}).get('timeout', 0) >= 600, 'terminal timeout')
require(c.get('compression', {}).get('threshold', 0) >= 0.8, 'compression threshold')
# E-1 v31: the pinned profile's compression (absolute trigger, tool-result prune, protected tail) is what the worker runs
_pp = Path('/etc/rhoai3/run-control/profile.json')
if _pp.is_file():
    _pd = json.loads(_pp.read_text())
    _want = ((_pd.get('profiles') or {}).get(_pd.get('default_model')) or {}).get('compression') or {}
    for _k, _v in _want.items():
        require(c.get('compression', {}).get(_k) == _v, 'compression %s is %r, the pinned profile says %r' % (_k, c.get('compression', {}).get(_k), _v))
    # patch 0017: the selected profile's loop escalation and reasoning echo reach the worker config exactly
    _prof = ((_pd.get('profiles') or {}).get(_pd.get('default_model')) or {})
    if _prof.get('loop_escalation'):
        require((_sel or {}).get('loop_escalation') == _prof['loop_escalation'],
                'the selected model entry does not carry the pinned loop_escalation')
    if _prof.get('reasoning_echo'):
        require(_m.get('reasoning_echo') is True, 'model.reasoning_echo is not set for a profile that requires it')
source = Path('/projects/legacy')
require(bool(os.statvfs(source).f_flag & os.ST_RDONLY), 'legacy checkout is writable; require a read-only mount')
source_receipt = source / '.git/rhoai3-source.json'
require(source_receipt.is_file(), 'source clone receipt missing')
origin = json.loads(source_receipt.read_text())
require(origin.get('schema') == 'rhoai3.source-volume/v1' and origin.get('commit') == subprocess.check_output(['git', '-c', 'safe.directory=' + str(source), '-C', str(source), 'rev-parse', 'HEAD'], text=True).strip(), 'source clone receipt mismatch')
# The factory declared this run's budget in the destination's initial commit;
# the loader refuses a missing, foreign, stale or rewritten declaration, and a
# history that does not begin at the platform receipt's scaffolding commit.
from planner import run_declaration
d = run_declaration.load(root, expected_run=WORKSPACE_NAME)
require(d.code == run_declaration.OK, str(d))
require(d.budget.get('max_wall_hours') == EXPECTED_HOURS, 'declared wall budget differs from the golden defaults')
# The board protocol: the run request in its initial commit, agreed by the
# read-only run control (outcome_protocol.launch_gaps). A request the installed
# harness cannot honour, a disagreement, a missing selection or a disabled
# outcome board refuses here; the serial loop is never launched instead.
initial = subprocess.check_output(['git', '-C', str(root), 'rev-list', '--max-parents=0', 'HEAD'], text=True).split()
declared = json.loads(subprocess.check_output(['git', '-C', str(root), 'show', initial[0] + ':run-budget.json'], text=True))
try:
    from planner import outcome_protocol
    launch = getattr(outcome_protocol, 'launch_gaps', None)
except ImportError:
    launch = None
if launch is None:
    require(declared.get('board_protocol') in (None, 'serial-loop/v1'),
            'BOARD_PROTOCOL: the run requests %s and the installed harness cannot select it' % declared.get('board_protocol'))
    protocol = 'serial-loop/v1'
else:
    sel, gaps = launch(root)
    require(not gaps, 'BOARD_PROTOCOL: %s' % (outcome_protocol.describe(gaps).splitlines()[0] if gaps else ''))
    protocol = sel.protocol
    if protocol == 'outcome-board/v2':
        # native control: the producer extended the K2 matcher from the same selection and
        # registered NO reconciler (the one native dispatcher promotes dependents itself)
        hk = c.get('hooks') or {}
        m = str((hk.get('pre_tool_call') or [{}])[0].get('matcher', '')).split('|')
        require(all(t in m for t in ('kanban_block', 'kanban_request_review', 'request_review', 'kanban_comment',
                                     'kanban_attach', 'kanban_create', 'kanban_link'))
                and not any('outcome_reconcile.py' in str(h.get('command', '')) for h in hk.get('on_kanban_dispatch_tick') or []),
                'BOARD_PROTOCOL: the managed config lacks the outcome-board/v2 hooks (review/block terminators, '
                'kanban record/graph tools) or registers a reconciler')
    if protocol == 'outcome-board/v1':
        # the producer registered the outcome hooks from the same selection
        hk = c.get('hooks') or {}
        require(any('outcome_reconcile.py' in str(h.get('command', '')) for h in hk.get('on_kanban_dispatch_tick') or [])
                and all(t in str((hk.get('pre_tool_call') or [{}])[0].get('matcher', '')).split('|')
                        for t in ('kanban_block', 'kanban_request_review', 'request_review')),
                'BOARD_PROTOCOL: the managed config lacks the outcome-board hooks (reconciler tick, review/block terminators)')
print('PASS: board protocol %s (requested %s)' % (protocol, declared.get('board_protocol', 'nothing')))
print('PASS: fresh workspace, golden, ownership, credentials, decisions, model, source protection and budget')
PY
)
run_launch_check() {
  local ns=${NS:-wksp-ai-developer} container=${CONTAINER:-development-tooling} golden defaults model doc pod receipt maas_host maas_ip
  local sub limits quota_limit quota_window quota_others llmi windows expected run d
  : "${POD:?set POD}" "${GOLDEN_CHECKOUT:?set GOLDEN_CHECKOUT}" "${GOLDEN_SHA:?set the full published golden commit}"
  : "${PLATFORM_SHA:?set the merged platform commit}" "${WORKSPACE:?set the run: the full project name the factory was given}"
  golden=$GOLDEN_CHECKOUT
  [[ "$GOLDEN_SHA" =~ ^[0-9a-f]{40}$ && "$PLATFORM_SHA" =~ ^[0-9a-f]{40}$ ]] || run_fail "full golden/platform commits required"
  [[ $(git -C "$golden" rev-parse HEAD) == "$GOLDEN_SHA" ]] || run_fail "golden checkout is not the pin"
  [[ -z "$(git -C "$golden" status --porcelain)" ]] || run_fail "golden checkout is dirty"
  defaults=$(cat "$golden/run-defaults.json")
  jq -e '.schema == "rhoai3.run-defaults/v1"' <<<"$defaults" >/dev/null || run_fail "golden predates run-defaults.json; use the preflight of that run"
  # The model this run requested at creation is the one the provisioner pinned in its run control (template parameter
  # "model", 2026-10-02); the golden's run-defaults model is only the fallback for a run created before that.
  model=${EXPECTED_MODEL:-$(oc --request-timeout=30s get configmap "$WORKSPACE-run-control" -n "$ns" -o json 2>/dev/null |
    jq -r '.data["profile.json"] | fromjson | .default_model // ""' 2>/dev/null || true)}
  [[ -n "$model" ]] || model=$(jq -r '.configuration.model.id' <<<"$defaults")
  # v32: the selected profile's per-run token budget (the run's pinned run-control copy, else the platform table)
  # and the golden's run-level stops are pinned before anything starts.
  doc=$(oc --request-timeout=30s get configmap "$WORKSPACE-run-control" -n "$ns" -o json 2>/dev/null | jq -c '.data["profile.json"] | fromjson' 2>/dev/null ||
        oc --request-timeout=30s get configmap migration-model-profiles -n "$ns" -o json 2>/dev/null | jq -c '.data["model-profiles.json"] | fromjson' 2>/dev/null || echo null)
  gaps=$(jq -n -r --argjson doc "$doc" --arg m "$model" --argjson d "$defaults" "$RUN_STOP_GAPS"' run_stop_gaps($doc; $m; $d) | join("; ")')
  [[ -z "$gaps" ]] || run_fail "$gaps"
  # Validate this workspace against the released defaults and the live platform; old receipts are not promoted.
  oc --request-timeout=30s get applications.argoproj.io -n openshift-gitops -l demo.rhoai.io/stage=070 -o json | jq -e --arg rev "$PLATFORM_SHA" '
    [.items[] | select(.spec.project == "rhoai-demo")] | length > 0 and all(.[]; .status.sync.revision == $rev
      and .status.sync.status == "Synced" and .status.health.status == "Healthy")' >/dev/null || run_fail "Stage 070 is not healthy at the selected revision"
  oc --request-timeout=30s get tektonconfig config -o json | jq -e 'any(.status.conditions[]?; .type == "Ready" and .status == "True")' >/dev/null ||
    run_fail "TektonConfig is not Ready"
  # GitLab push webhooks reach the run's own project EventListener (Stage 070 creates <run>-dev per enrolled project).
  oc --request-timeout=30s get eventlistener gitlab -n "$WORKSPACE-dev" -o json | jq -e 'any(.status.conditions[]?; .type == "Ready"
    and .status == "True")' >/dev/null || run_fail "the run's webhook EventListener ($WORKSPACE-dev/gitlab) is not ready"
  pod=$(oc --request-timeout=30s get pod "$POD" -n "$ns" -o json)
  jq -n -e --argjson p "$pod" --arg c "$container" "$POD_MOUNTS"' source_mount_ok($p; $c)' >/dev/null ||
    run_fail "source mount is writable or has a writable runtime alias"
  jq -e --arg ws "$WORKSPACE" '.metadata.labels["controller.devfile.io/devworkspace_name"] == $ws' <<<"$pod" >/dev/null || run_fail "actual workspace name mismatch"
  # v32 (2026-10-02): every ws-080 container runs exactly the golden's pinned image (a factory once wrote the previous one).
  jq -n -e --argjson p "$pod" --arg want "$(jq -r '.pins.workspace_overlay.ws_080.digest' "$golden/.hermes/pins.json")" '[$p.status.containerStatuses[]?
    | (.imageID // .image // "") as $i | select(((.image // "") + (.imageID // "")) | contains("rhoai3-ws-080")) | $i]
    | length > 0 and all(.[]; endswith($want))' >/dev/null || run_fail "the workspace does not run the golden's pinned ws-080 image"
  receipt=$(oc --request-timeout=30s get configmap "migration-run-$WORKSPACE" -n "$ns" -o json | jq -c '.data')
  jq -e --arg ws "$WORKSPACE" --arg ns "$ns" '.phase == "provisioned" and .workspace == $ws and .namespace == $ns' <<<"$receipt" >/dev/null ||
    run_fail "provisioning receipt is not ready for this workspace"
  gaps=$(jq -n -r --argjson p "$pod" --argjson r "$receipt" --argjson b "$(oc --request-timeout=30s get rolebinding devworkspace-default-rolebinding -n "$ns" -o json)" \
    --arg ns "$ns" --arg ws "$WORKSPACE" "$WORKER_IDENTITY"' worker_identity_gaps($p; $r; $b; $ns; $ws) | join("; ")')
  [[ -z "$gaps" ]] || run_fail "$gaps"
  jq -n -e --argjson p "$pod" --arg c "$container" "$POD_MOUNTS"' kubeconfig_mount_ok($p; $c)' >/dev/null ||
    run_fail "worker kubeconfig directory lacks its ephemeral mount; late Dashboard token injection is possible"
  gaps=$(jq -n -r --argjson d "$defaults" --argjson r "$receipt" "$IMAGE_BINDINGS"' image_binding_gaps($d; $r) | join("; ")')
  [[ -z "$gaps" ]] || run_fail "$gaps"
  oc --request-timeout=30s get deployment "$(jq -r '.host' <<<"$receipt")" -n "$ns" -o json | jq -e --arg img "$(jq -r '.databaseImage' <<<"$receipt")" '
    (.status.availableReplicas // 0) == 1 and .spec.template.spec.containers[0].image == $img' >/dev/null ||
    run_fail "assigned database is not available on the pinned image"
  for secret in $(jq -r '.workspaceSecret, .fixtureSecret' <<<"$receipt"); do
    # Metadata only: the label/annotation contract and the pod's consumption; no Secret value is read.
    oc --request-timeout=30s get secret "$secret" -n "$ns" -o jsonpath='{.metadata}' | jq -e --arg ws "$WORKSPACE" '
      (.labels // {}) as $l | (.annotations // {}) as $a
      | $l["controller.devfile.io/watch-secret"] == "true" and $l["controller.devfile.io/mount-to-devworkspace"] == "true"
      and $a["controller.devfile.io/mount-to-devworkspace-include"] == $ws and $a["controller.devfile.io/mount-on-start"] == "true"
      and $a["controller.devfile.io/mount-as"] == "env"' >/dev/null || run_fail "incorrect secret targeting: $secret"
    jq -n -e --argjson p "$pod" --arg c "$container" --arg s "$secret" '[$p.spec.containers[] | select(.name == $c)][0] as $w
      | ([$w.env[]?.valueFrom.secretKeyRef.name] + [$w.envFrom[]?.secretRef.name]) | index($s) != null' >/dev/null ||
      run_fail "pod does not consume its assigned secret: $secret"
  done
  # The worker reaches MaaS through the gateway's in-cluster Service, not the public ELB, which drops silent
  # tool-call streams; the factory stamps a pod hostAlias at creation.
  maas_host=$(oc --request-timeout=30s get gateway maas-default-gateway -n openshift-ingress -o json |
    jq -r '[.spec.listeners[].hostname // "" | select(startswith("maas."))] | if length == 1 then .[0] else "" end')
  [[ -n "$maas_host" ]] || run_fail "Expected exactly one maas. API listener"
  maas_ip=$(oc --request-timeout=30s get service maas-gateway-internal -n openshift-ingress -o jsonpath='{.spec.clusterIP}')
  [[ "$maas_host" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?(\.[a-z0-9]([-a-z0-9]*[a-z0-9])?)*$ && "$maas_ip" =~ ^[0-9]+\.[0-9]+\.[0-9]+\.[0-9]+$ ]] ||
    run_fail "MaaS gateway host or internal IP unavailable"
  # B3: per-model token limits live on the MaaSSubscription every workspace key is minted under, so concurrent runs
  # of the same model share one bucket; only migration runs (their devfile names MIGRATION_RUN_NAME) of that model
  # draw the per-run demand, a run whose pin cannot be read still counts, every other consumer is the reserve.
  sub=$(oc --request-timeout=30s get maassubscription devspaces-coding-models -n models-as-a-service -o json)
  limits=$(jq -c --arg m "$model" '[.spec.modelRefs[]? | select(.name == $m) | (.tokenRateLimits // [])[]]' <<<"$sub")
  [[ $(jq length <<<"$limits") == 1 ]] || run_fail "devspaces-coding-models declares $(jq length <<<"$limits") token limits for $model; exactly one is admitted"
  quota_limit=$(jq -r '.[0].limit | tonumber' <<<"$limits") quota_window=$(jq -r '.[0].window | tostring' <<<"$limits")
  quota_others=0
  while IFS= read -r run; do
    d=$(oc --request-timeout=30s get configmap "$run-run-control" -n "$ns" -o json 2>/dev/null | jq -r '.data["profile.json"] | fromjson | .default_model // ""' 2>/dev/null || true)
    [[ -z "$d" || "$d" == "$model" ]] && quota_others=$((quota_others + 1))
  done < <(oc --request-timeout=30s get devworkspace -n "$ns" -o json | jq -r --arg ws "$WORKSPACE" '.items[]
    | select(.metadata.name != $ws and (.status.phase == "Running" or .status.phase == "Starting")
      and any((.spec.template.components // [])[]; any((.container.env // [])[]; .name == "MIGRATION_RUN_NAME")))
    | .metadata.name')
  llmi=$(oc --request-timeout=30s get llminferenceservice "$model" -n internal-models -o json)
  jq -e 'any(.status.conditions[]?; .type == "Ready" and .status == "True")' <<<"$llmi" >/dev/null || run_fail "Qwen model is not Ready"
  windows=$(jq -r '[.spec | .. | objects | .args? // empty | arrays | . as $a | range(length) as $i
      | if ($a[$i] | startswith("--max-model-len=")) then ($a[$i] | split("=")[1] | tonumber)
        elif $a[$i] == "--max-model-len" then ($a[$i + 1] | tonumber) else empty end] | unique | if length == 1 then .[0] else "" end' <<<"$llmi")
  [[ -n "$windows" ]] || run_fail "served model window absent or ambiguous"
  # The installed harness and the shared defaults the run's declaration binds must be the golden's, byte for byte.
  for dir in .hermes/kernel .hermes/lib .hermes/skills .hermes/planning/schemas .hermes/planning/catalogs decided-repairs; do
    [[ -d "$golden/$dir" ]] || run_fail "golden missing $dir"
  done
  expected=$(cd "$golden" && { find .hermes/kernel .hermes/lib .hermes/skills .hermes/planning/schemas .hermes/planning/catalogs decided-repairs \
      -type f ! -path '*/__pycache__/*' ! -name '._*' -exec shasum -a 256 {} +; shasum -a 256 run-defaults.json; } |
    jq -R -s -c 'split("\n") | map(select(. != "") | capture("^(?<v>[0-9a-f]{64})  (?<k>.+)$") | {key: .k, value: .v}) | from_entries')
  # The in-workspace checks print assertions only, never environment or configuration values.
  { printf 'EXPECTED_HOURS = %s\nEXPECTED = %s\nMODEL = %s\nWINDOW = %s\nWORKER_IDENTITY = %s\nWORKSPACE_NAME = %s\n' \
      "$(jq '.budget.max_wall_hours' <<<"$defaults")" "$(jq -n --arg e "$expected" '$e')" "$(jq -n --arg m "$model" '$m')" "$windows" \
      "$(jq -n --arg s "system:serviceaccount:$ns:$WORKSPACE-worker" '$s')" "$(jq -n --arg w "$WORKSPACE" '$w')"
    printf 'MAASHOSTVAL = %s\nMAASIPVAL = %s\nQLIMITVAL = %s\nQWINVAL = %s\nQOTHERSVAL = %s\n' \
      "$(jq -n --arg h "$maas_host" '$h')" "$(jq -n --arg i "$maas_ip" '$i')" "$quota_limit" "$(jq -n --arg w "$quota_window" '$w')" "$quota_others"
    printf '%s\n' "$IN_WORKSPACE_CHECKS"
  } | oc --request-timeout=60s exec -i -n "$ns" "$POD" -c "$container" -- python3 - || run_fail "in-workspace launch checks failed"
  echo "PASS: launch preflight for $WORKSPACE; no reset or dispatch performed"
}
# The run-mode gap functions on the cases they must refuse (no cluster): pinned images, worker identity, run stops.
run_launch_selftest() {
  local images defaults pod receipt table rd q fails=0 sa
  images='{"databaseImage":"registry/db@sha256:'"$(printf 'a%.0s' {1..64})"'","provisionerImage":"registry/cli@sha256:'"$(printf 'b%.0s' {1..64})"'"}'
  defaults=$(jq -c '{configuration: {images: .}}' <<<"$images")
  img() { jq -n -r --argjson d "$1" --argjson r "$2" "$IMAGE_BINDINGS"' image_binding_gaps($d; $r) | length'; }
  [[ $(img "$defaults" "$images") == 0 ]] || fails=$((fails + 1))
  for key in databaseImage provisionerImage; do
    for value in null '"registry/foreign@sha256:'"$(printf 'c%.0s' {1..64})"'"' '"registry/tag:latest"'; do
      [[ $(img "$defaults" "$(jq -c --arg k "$key" --argjson v "$value" '.[$k] = $v' <<<"$images")") -gt 0 ]] || fails=$((fails + 1))
    done
    for value in null '"registry/tag:latest"'; do
      [[ $(img "$(jq -c --arg k "$key" --argjson v "$value" '.configuration.images[$k] = $v' <<<"$defaults")" "$images") -gt 0 ]] || fails=$((fails + 1))
    done
  done
  sa=orders-migration-worker
  wid() { jq -n -r --argjson p "$1" --argjson r "{\"workerServiceAccount\":\"$sa\"}" --argjson b "$2" "$WORKER_IDENTITY"' worker_identity_gaps($p; $r; $b; "wksp-test"; "orders-migration") | length'; }
  [[ $(wid "{\"spec\":{\"serviceAccountName\":\"$sa\"}}" '{}') == 0 ]] || fails=$((fails + 1))
  [[ $(wid '{"spec":{"serviceAccountName":"workspace-legacy-sa"}}' '{}') -gt 0 ]] || fails=$((fails + 1))
  for subject in "{\"kind\":\"ServiceAccount\",\"name\":\"$sa\",\"namespace\":\"wksp-test\"}" '{"kind":"Group","name":"system:serviceaccounts:wksp-test"}' \
      "{\"kind\":\"User\",\"name\":\"system:serviceaccount:wksp-test:$sa\"}"; do
    [[ $(wid "{\"spec\":{\"serviceAccountName\":\"$sa\"}}" "{\"subjects\":[$subject]}") -gt 0 ]] || fails=$((fails + 1))
  done
  table=$(cat "$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-devspaces/model-profiles.json")
  rd=$(cat "$SCRIPT_DIR/scaffold-repo/quarkus-migration-scaffold/run-defaults.json")
  rsg() { jq -n -r --argjson t "$1" --arg m "$2" --argjson d "$3" "$RUN_STOP_GAPS"' run_stop_gaps($t; $m; $d) | join("|")'; }
  for model in $(jq -r '.profiles | keys[]' <<<"$table"); do [[ -z $(rsg "$table" "$model" "$rd") ]] || fails=$((fails + 1)); done
  q=$(jq -c '.profiles["other-model"] = (.profiles["qwen3-8-27b"] | del(.run_input_token_budget))' <<<"$table")
  [[ -z $(rsg "$q" qwen3-8-27b "$rd") && $(rsg "$q" other-model "$rd") == RUN_TOKEN_BUDGET* ]] || fails=$((fails + 1))
  for bad in 0 -1 true '"12000000"' null; do
    [[ -n $(rsg "$(jq -c --argjson b "$bad" '.profiles["qwen3-8-27b"].run_input_token_budget = $b' <<<"$table")" qwen3-8-27b "$rd") ]] || fails=$((fails + 1))
  done
  [[ $(rsg "$(jq -c 'del(.profiles["qwen3-8-27b"].loop_escalation.retry_start_turns)' <<<"$table")" qwen3-8-27b "$rd") == *retry_start_turns* ]] || fails=$((fails + 1))
  [[ $(rsg "$table" unserved-model "$rd") == RUN_TOKEN_BUDGET* && $(rsg null qwen3-8-27b "$rd") == RUN_TOKEN_BUDGET* ]] || fails=$((fails + 1))
  for key in run_input_token_budget no_accepted_checkpoint_minutes; do
    [[ $(rsg "$table" qwen3-8-27b "$(jq -c --arg k "$key" 'del(.budget[$k])' <<<"$rd")") == "RUN_STOPS: run-defaults.json budget.$key is not a positive integer" ]] || fails=$((fails + 1))
  done
  [[ $fails == 0 ]] && echo RUN_PREFLIGHT_TEST_OK || echo "RUN_PREFLIGHT_TEST_FAILED ($fails)"
}
if [[ "${1:-}" == --run ]]; then run_launch_check; exit; fi

echo "╔══════════════════════════════════════════════════════════════════╗"
echo "║  Stage 130: Autonomous Application Migration (MTA 8.3)     ║"
echo "╚══════════════════════════════════════════════════════════════════╝"
echo ""

log_step "Argo CD Application (platform stage owns the resources)"
check_stage_applications 070

log_step "MTA Operator"
check_csv_succeeded "openshift-mta" "mta-operator"

log_step "MTA Instance"
check "Tackle CR exists" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.metadata.name}'" \
  "mta"
check "Tackle LLM proxy enabled (inference separately qualified)" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.kai_llm_proxy_enabled}'" \
  "true"
# Stage 070 deliberately keeps the Solution Server disabled (database retained) until its vendor dependency fix;
# BACKLOG "Stage 070 live qualification". This check follows that decision instead of contradicting it.
check "Tackle Solution Server stays disabled as Stage 070 decided" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.kai_solution_server_enabled}'" \
  "false"
check "Tackle hub auth enabled (built-in OIDC provider)" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.feature_auth_required}'" \
  "true"
check "Tackle idp_primary auto-redirect enabled" \
  "oc get tackle mta -n openshift-mta -o jsonpath='{.spec.idp_primary}'" \
  "true"

log_step "MTA Core Deployments"
check "mta-ui deployment ready" \
  "oc get deployment mta-ui -n openshift-mta -o jsonpath='{.status.readyReplicas}'" \
  "1"
check "mta-hub deployment ready" \
  "oc get deployment mta-hub -n openshift-mta -o jsonpath='{.status.readyReplicas}'" \
  "1"

log_step "Platform SSO Federation (built-in Hub OIDC)"
check "IdentityProvider platform-sso exists" \
  "oc get identityprovider platform-sso -n openshift-mta -o jsonpath='{.metadata.name}'" \
  "platform-sso"
check "IdentityProvider issuer targets the platform realm" \
  "oc get identityprovider platform-sso -n openshift-mta -o jsonpath='{.spec.issuer}' | grep -c '/realms/platform' || echo 0" \
  "1"
check "IdP client Secret exists" \
  "oc get secret mta-idp-client-secret -n openshift-mta -o jsonpath='{.metadata.name}'" \
  "mta-idp-client-secret"
MTA_ROUTE_HOST=$(oc get route mta -n openshift-mta -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
if [[ -n "$MTA_ROUTE_HOST" ]]; then
    check_http_code "Hub OIDC discovery" \
      "https://${MTA_ROUTE_HOST}/oidc/.well-known/openid-configuration" "200"
    HUB_ANON=$(curl -sk -H "Accept: application/json" -o /dev/null -w '%{http_code}' "https://${MTA_ROUTE_HOST}/hub/applications" 2>/dev/null || echo "000")
    if [[ "$HUB_ANON" == "401" ]]; then
        echo -e "${GREEN}[PASS]${NC} Hub API enforces authentication (HTTP 401 unauthenticated)"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${RED}[FAIL]${NC} Hub API does not enforce authentication (HTTP ${HUB_ANON}, expected 401)"
        VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    fi
fi

log_step "MTA UI Route"
MTA_ROUTE=$(oc get route mta -n openshift-mta -o jsonpath='{.spec.host}' 2>/dev/null || echo "")
if [[ -n "$MTA_ROUTE" ]]; then
    check_http_code "MTA UI: https://${MTA_ROUTE}" "https://${MTA_ROUTE}" "200,302"
else
    echo -e "${YELLOW}[WARN]${NC} MTA UI route not found"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

log_step "ConsoleLink"
MTA_CL_HREF=$(oc get consolelink mta -o jsonpath='{.spec.href}' 2>/dev/null || echo "")
if [[ -n "$MTA_CL_HREF" ]] && [[ "$MTA_CL_HREF" != *"placeholder"* ]]; then
    echo -e "${GREEN}[PASS]${NC} MTA ConsoleLink: ${MTA_CL_HREF}"
    VALIDATE_PASS=$((VALIDATE_PASS + 1))
else
    echo -e "${YELLOW}[WARN]${NC} MTA ConsoleLink href is placeholder or missing"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

log_step "Migration Golden Path (app-migration template)"
check "app-migration template Location in the runtime catalog" \
  "oc get configmap catalog-runtime-rhdh -n rhdh -o jsonpath='{.data.all\\.yaml}' | grep -c 'templates/app-migration/template.yaml' || echo 0" \
  "1"
check "runtime catalog placeholders are resolved" \
  "oc get configmap catalog-runtime-rhdh -n rhdh -o jsonpath='{.data.all\\.yaml}' | grep -cE '__RHOAI3_DEMO_(REVISION|LOCATION_REF)__' || echo 0" \
  "0"
# B2 (a459cce7): the generator pins every template Location to the ONE revision
# it published and prunes the rest; the app-migration Location must name the
# catalog's recorded rhoai3.redhat.com/catalog-revision (Stage 050 checks all).
check "runtime catalog app-migration Location is pinned to the catalog revision" \
  "rev=\$(oc get configmap catalog-runtime-rhdh -n rhdh -o jsonpath='{.metadata.annotations.rhoai3\\.redhat\\.com/catalog-revision}'); oc get configmap catalog-runtime-rhdh -n rhdh -o jsonpath='{.data.all\\.yaml}' | grep 'templates/app-migration/template.yaml' | grep -oE '/blob/[0-9a-f]{40}/' | sort -u | grep -cx \"/blob/\$rev/\" || echo 0" \
  "1"
# The provisioner reads each run's own request (run-budget.json at the scaffold commit) through the run's reader
# token; an unreadable request selects no board protocol and dest-init refuses PROTOCOL_UNBOUND at workspace start.
check "provisioned migration runs read their own request (run control)" \
  "oc get configmaps -A -o json | jq '[.items[] | select(.metadata.namespace | startswith(\"wksp-\")) | select(.metadata.name | endswith(\"-run-control\")) | .data[\"contract.json\"] // \"{}\" | fromjson | .protocol_request.state // \"\" | select(startswith(\"unreadable\"))] | length'" \
  "0"
if command -v gh >/dev/null 2>&1 && gh auth status >/dev/null 2>&1; then
    GOLDEN_SHA=$(gh api repos/adnan-drina/quarkus-migration-scaffold-v2/git/refs/heads/main --jq '.object.sha' 2>/dev/null || echo "")
    if [[ -n "$GOLDEN_SHA" ]]; then
        echo -e "${GREEN}[PASS]${NC} quarkus-migration-scaffold-v2 golden repo exists (${GOLDEN_SHA:0:12})"
        VALIDATE_PASS=$((VALIDATE_PASS + 1))
    else
        echo -e "${RED}[FAIL]${NC} quarkus-migration-scaffold-v2 golden repo missing (the Stage 070 GitLab hook publishes it: stages/070-advanced-app-platform/deploy.sh)"
        VALIDATE_FAIL=$((VALIDATE_FAIL + 1))
    fi
else
    echo -e "${YELLOW}[WARN]${NC} gh not available — skipping golden repo check"
    VALIDATE_WARN=$((VALIDATE_WARN + 1))
fi

log_step "Harness Tooling (Session 0 — init script contract)"
# The migration golden path's workspaces (PROFILE=modernized) get the
# harness orchestrator + sensor tooling from the shared init ConfigMap:
# overlay-baked Hermes CLI (no curl install.sh) and the lazy kantra
# sensor helper (~690MB zip — deliberately NOT downloaded at postStart).
check "live init ConfigMap uses overlay-baked Hermes CLI" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'hermes_bin=\"/usr/local/bin/hermes\"' || echo 0" \
  "1"
check "live init ConfigMap does not curl-install Hermes" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'hermes-agent.nousresearch.com/install.sh' || echo 0" \
  "0"
# Since d0816c25 the worker's Hermes model, provider and limits are GENERATED
# from the one declared profile table (migration-model-profiles), not written
# as literals in the init script; check the declaration and the one provider
# name the script still carries.
# The run model is a pinned input chosen once, in the golden's run-defaults.json (v30 E-1: Qwen 3.6 vs 3.8);
# the platform's declared default and its provider must equal it, or the preflight refuses "worker model mismatch".
RUN_MODEL="$(jq -r '.configuration.model | "\(.id) \(.provider)"' "${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/run-defaults.json" 2>/dev/null || echo "missing missing")"
check "declared model profile default equals the golden run model (${RUN_MODEL})" \
  "oc get cm migration-model-profiles -n wksp-ai-developer -o go-template='{{index .data \"model-profiles.json\"}}' | jq -r '\"\\(.default_model) \\(.profiles[.default_model].provider)\"' 2>/dev/null || echo none" \
  "${RUN_MODEL}"
# E-1 (2026-10-01): the enforce-on-start model gate compared against the literal qwen3-8-27b and
# fail-closed every start of the first run provisioned with qwen3-6-27b; it must check the declared profile
check "dest-init model gate checks the declared profile default, not a literal model id" \
  "grep -c 'if m.get(\"default\") != MODEL_PROFILES\[DEFAULT_MODEL\]\[\"model_id\"\]:' \"$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-devspaces/maas-api-key-provisioning.yaml\" || echo 0" \
  "1"
check "dest-init model gate names no literal default model" \
  "grep -cE 'm.get\(\"(default|provider)\"\) != \"' \"$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-devspaces/maas-api-key-provisioning.yaml\" || true" \
  "0"
check "init script names the Hermes Qwen provider qwen38" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c '\"provider\": \"qwen38\"' || echo 0" \
  "1"
check "init script sets Hermes api_mode chat_completions" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c '\"api_mode\": \"chat_completions\"' || echo 0" \
  "1"
# the script writes discover_models False once, in the _provider() generator
# every profile-declared provider comes from (the MiniMax escalation provider
# was removed on 2026-10-09)
check "init script disables Hermes /models discovery on named providers" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c '\"discover_models\": False' || echo 0" \
  "1"
check "GitOps init script does not use legacy custom:maas-m2 default" \
  "grep -c 'custom:maas-m2' \"$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-devspaces/maas-api-key-provisioning.yaml\" || echo NONE" \
  "NONE"
check "GitOps init script forbids Hermes fallback_providers" \
  "grep -c 'forbids fallback_providers' \"$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-devspaces/maas-api-key-provisioning.yaml\" || echo 0" \
  "1"
check "init script ships the kantra-ensure lazy sensor helper (pinned)" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'KANTRA_VERSION=\"v0.10.0-beta.1\"' || echo 0" \
  "1"
check "kantra-ensure download message is on stderr (ensure_cli captures stdout as the CLI path)" \
  "grep -c 'Downloading kantra.*>&2' \"$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-devspaces/maas-api-key-provisioning.yaml\" || echo 0" \
  "1"
check "live kantra-ensure verifies every ELF in the kantra tree is executable" \
  "test \"\$(oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -cF 'kantra-assert-exec')\" -ge 2 && echo CHECKER_WIRED || echo CHECKER_MISSING" \
  "CHECKER_WIRED"
check "dest-init kantra-assert-exec skips ruleset fixture shebangs" \
  "grep -cF 'RULESET_FIXTURE_SHEBANG' \"$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-devspaces/maas-api-key-provisioning.yaml\" || echo 0" \
  "1"
check "init ConfigMap is DWO-mounted (volume, not kube-API curl as the primary path)" \
  "awk '/^kind: ConfigMap\$/{c=1} c && /^  name: devspace-ai-tools-init\$/{n=1} n && /controller.devfile.io\\/mount-to-devworkspace: \"true\"/ {print 1; exit} n && /^data:/{exit} /^---\$/{c=0; n=0}' \"$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-devspaces/maas-api-key-provisioning.yaml\" || echo 0" \
  "1"
SCAFFOLD_080="$REPO_ROOT/stages/130-ai-autonomous-migration/scaffold-repo/quarkus-migration-scaffold"
check "v2 scaffold ships dispatch-phase/autostart-migration.sh (the dest-init consumer the devfile postStart calls)" \
  "test -f \"$SCAFFOLD_080/.hermes/skills/harness/dispatch-phase/scripts/autostart-migration.sh\" && grep -c 'dispatch-phase/scripts/autostart-migration.sh' '$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-rhdh/templates/app-migration/skeleton/devfile.yaml' | awk '{print (\$1>=1)?1:0}'" \
  "1"
check "v2 scaffold has no .hermes/home/scripts" \
  "test ! -e \"$SCAFFOLD_080/.hermes/home/scripts\" && echo 1 || echo 0" \
  "1"
check "v2 scaffold has no handover-mint.py" \
  "test -d \"$SCAFFOLD_080\" && test -z \"$(find \"$SCAFFOLD_080\" -name handover-mint.py -print -quit 2>/dev/null)\" && echo 1 || echo 0" \
  "1"
check "ensure_cli invokes kantra-assert-exec (capability, not presence)" \
  "grep -c 'kantra-assert-exec' \"$SCAFFOLD_080/.hermes/skills/analysis/scan-with-mta/scripts/mta-analyze-legacy.sh\" || echo 0" \
  "3"
check "ensure_cli does not add a kantra version handshake" \
  "grep -E 'kantra[[:space:]]+version|--list-providers' \"$SCAFFOLD_080/.hermes/skills/analysis/scan-with-mta/scripts/mta-analyze-legacy.sh\" && echo HANDSHAKE || echo NONE" \
  "NONE"
check "assert-ensure-cli-path rejects a present-but-unusable sibling" \
  "bash \"$SCAFFOLD_080/.hermes/skills/analysis/scan-with-mta/scripts/assert-ensure-cli-path.sh\" >/dev/null && echo PASS || echo FAIL" \
  "PASS"
check "run-m4-pre-verdict invokes assert-no-fence-evasion (not a card pin)" \
  "grep -c 'assert-no-fence-evasion' \"$SCAFFOLD_080/.hermes/skills/gates/check-release-readiness/scripts/run-m4-pre-verdict.sh\" || echo 0" \
  "5"
check "run-m4-pre-verdict resolves work logs not M4 self" \
  "test -f \"$SCAFFOLD_080/.hermes/skills/gates/check-release-readiness/scripts/resolve-m4-work-logs.py\" && grep -c 'resolve-m4-work-logs' \"$SCAFFOLD_080/.hermes/skills/gates/check-release-readiness/scripts/run-m4-pre-verdict.sh\" || echo 0" \
  "1"
check "v2 Hermes config template is present" \
  "test -f \"$SCAFFOLD_080/.hermes/config/config.yaml.template\" && echo 1 || echo 0" \
  "1"
check "v2 config template forbids fallback_providers" \
  "grep -c 'OBJECT: fallback_providers' \"$SCAFFOLD_080/.hermes/config/config.yaml.template\" || echo 0" \
  "1"
check "inventory-type-graph imports type_graph as a module (no tree walk)" \
  "grep -c '_find_type_graph' \"$SCAFFOLD_080/.hermes/skills/analysis/inventory-entry-points/scripts/inventory-type-graph.py\" || echo NONE" \
  "NONE"
check "check-phase-matrix.py is not in the golden scaffold" \
  "test ! -f \"$SCAFFOLD_080/.hermes/skills/gates/check-release-readiness/scripts/check-phase-matrix.py\" && echo 1 || echo 0" \
  "1"
check "harness tooling is gated on the modernized profile" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'PROFILE}\" = \"modernized\"' || echo 0" \
  "2"
# AD-H §14 — dest-user + per-profile SOUL.md; init must abort on
# missing/empty/hash mismatch and smoke-test Hermes load+scan.
check "init script hash-verifies SOUL.md and aborts (AD-H §14)" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'SOUL.md hash mismatch after placement' || echo 0" \
  "1"
check "init script places per-profile SOUL.md (AD-H §14)" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'profiles/\${name}/SOUL.md' || echo 0" \
  "1"
check "init script load-time SOUL smoke via load_soul_md (AD-H §14)" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'from agent.prompt_builder import load_soul_md' || echo 0" \
  "1"
check "live dest-init SOUL smoke uses overlay /opt/hermes-agent" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'hermes_agent_root=\"/opt/hermes-agent\"' || echo 0" \
  "1"
check "live dest-init does not copy dest kanban-stuck-watchdog" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'home/scripts/kanban-stuck-watchdog' || echo 0" \
  "0"
check "live dest-init does not invoke golden assert-agent-pin.py" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -v '^[[:space:]]*#' | grep -c 'assert-agent-pin.py' || echo 0" \
  "0"
check "live workspace-maas-model-endpoint is the MaaS gateway path (not KServe)" \
  "oc get cm workspace-maas-model-endpoint -n wksp-ai-developer -o jsonpath='{.data.MAAS_API_PATH}'" \
  "/v1"
check "live workspace-maas-credentials Secret exists" \
  "oc get secret workspace-maas-credentials -n wksp-ai-developer -o jsonpath='{.metadata.name}'" \
  "workspace-maas-credentials"

log_step "Factory Migration Workspace (app-migration destfile)"
# Stage 130 seats are created at demo time from the RHDH template. Do not
# require a standing mca-coolstore DevWorkspace. Assert the factory contract
# and that the retired GitOps seats are gone.
SKELETON_080="$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-rhdh/templates/app-migration/skeleton/devfile.yaml"
# One runtime image everywhere it is named (v26 audit: run-defaults.json and the golden
# devfile still named sha256:6a8a69a3 while pins.json and the template named sha256:9147834b)
GOLDEN_080="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold"

# A file without its comment lines (the content a reader acts on).
uncommented() { sed -E 's/^[[:space:]]*#.*$//' "$1"; }
# One top-level Python function's source: from "def NAME" up to the next top-level def.
py_function() { awk -v name="$2" '$0 ~ "^def " name "\\(" { f = 1; print; next } f && /^def / { exit } f' "$1"; }
# Every rhoai3-ws-080 image reference in the factory skeleton, the golden devfile and run-defaults equals the pin.
ws080_pins_match() {
    local pin=$1 seen; shift
    seen=$( { grep -ohE 'rhoai3-ws-080@sha256:[0-9a-f]{64}' "$@" | sed 's/^rhoai3-ws-080@//'
              jq -r '.configuration.workspace_overlay.digest' "${@: -1}"; } | sort -u)
    [[ -n "$seen" && "$pin" == sha256:* && "$seen" == "$pin" ]] && echo match || echo "mismatch $(paste -sd, - <<<"$seen")"
}
# Apostrophes inside the K2 hook's single-quoted python body (from the line after "exec python3 -c '" to the closing
# quote line); one would end the shell string and the hook would fail open.
hook_body_apostrophes() {
    awk 'found && /^'"'"'/ { exit } found { print } /exec python3 -c / && /'"'"'$/ { found = 1 }' "$1" | tr -cd "'" | wc -c | tr -d ' '
}
WS080_PIN="$(jq -r '.pins.workspace_overlay.ws_080.digest' "${GOLDEN_080}/.hermes/pins.json" 2>/dev/null || echo missing)"
check "every ws-080 image reference equals the golden pin (${WS080_PIN:0:19}…)" \
  "ws080_pins_match '${WS080_PIN}' '${SKELETON_080}' '${GOLDEN_080}/devfile.yaml' '${GOLDEN_080}/run-defaults.json'" \
  "match"
GOLDEN_DEVFILE="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/devfile.yaml"
check_factory_mta_destfile() {
    local label="$1"
    local destfile="$2"
    check "factory destfile declares MTA default extensions: $label" \
        "grep -q '/opt/rhoai3/extensions/mta-vscode-extension.vsix;/opt/rhoai3/extensions/mta-core.vsix;/opt/rhoai3/extensions/java.vsix;/opt/rhoai3/extensions/mta-java.vsix' '$destfile' && echo present || echo missing" \
        "present"
    check "factory destfile uses baked MTA VS Code extension 8.3.1: $label" \
        "grep -q '/opt/rhoai3/extensions/mta-vscode-extension.vsix' '$destfile' && echo present || echo missing" \
        "present"
    check "factory destfile uses baked MTA core extension 8.3.1: $label" \
        "grep -q '/opt/rhoai3/extensions/mta-core.vsix' '$destfile' && echo present || echo missing" \
        "present"
    check "factory destfile uses baked MTA Java extension 8.3.1: $label" \
        "grep -q '/opt/rhoai3/extensions/mta-java.vsix' '$destfile' && echo present || echo missing" \
        "present"
    check "factory destfile uses baked redhat.java 1.47.0 (mta-java dependency): $label" \
        "grep -q '/opt/rhoai3/extensions/java.vsix' '$destfile' && echo present || echo missing" \
        "present"
    if [[ "$destfile" == "$SKELETON_080" ]]; then
        check "factory destfile receives authenticated Hub Route: $label" \
            "grep -q 'values.mtaHubUrl' '$destfile' && echo present || echo missing" "present"
    else
        check "generic golden leaves Hub binding to the factory: $label" \
            "grep -q 'name: HUB_URL' '$destfile' && echo bound || echo unbound" "unbound"
    fi
    check "factory destfile sets FORCE_HUB_ENABLED: $label" \
        "grep -q 'FORCE_HUB_ENABLED' '$destfile' && echo present || echo missing" \
        "present"
    check "factory destfile sets HUB_INSECURE: $label" \
        "grep -q 'HUB_INSECURE' '$destfile' && echo present || echo missing" \
        "present"
}
check_factory_mta_destfile "RHDH app-migration skeleton" "$SKELETON_080"
check_factory_mta_destfile "080 golden destfile" "$GOLDEN_DEVFILE"
for ns in wksp-kubeadmin wksp-ai-admin wksp-ai-developer; do
    check "retired mca-coolstore standing workspace is absent: $ns" \
        "oc get devworkspace mca-coolstore -n $ns >/dev/null 2>&1 && echo present || echo absent" \
        "absent"
    check "mta-hub-config ConfigMap exists with MTA hub URL: $ns" \
        "oc get configmap mta-hub-config -n $ns -o jsonpath='{.data.MTA_HUB_URL}' 2>/dev/null | grep -c 'https://' || echo 0" \
        "1"
done

# Stage 130 dest is Hermes Kanban. OpenCode skill diffs against stage 070
# were the dual-tool destfile lie (ST-7). Static destfile contract:
SCAFFOLD_DEVFILE="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/devfile.yaml"
SCAFFOLD_DASH="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/dashboard"
check "080 destfile is not OpenCode-only" \
  "grep -c 'OpenCode-only by design' '${SCAFFOLD_DEVFILE}' || echo 0" \
  "0"
check "080 destfile has no opencode-managed volume" \
  "grep -c 'opencode-managed' '${SCAFFOLD_DEVFILE}' || echo 0" \
  "0"
check "080 destfile keeps hermes-dash endpoint" \
  "grep -c 'name: hermes-dash' '${SCAFFOLD_DEVFILE}' || echo 0" \
  "1"
check "080 destfile has no start-hermes-dashboard launcher" \
  "grep -c 'start-hermes-dashboard' '${SCAFFOLD_DEVFILE}' || echo 0" \
  "0"
check "080 dashboard launcher defaults HERMES_WEB_DIST to overlay bake" \
  "grep -qF ': \"\${HERMES_WEB_DIST:=/usr/local/share/hermes/web_dist}\"' '${SCAFFOLD_DASH}/start-dashboard.sh' && echo 1 || echo 0" \
  "1"
check "080 dashboard launcher does not override HERMES_WEB_DIST to dest hermes_cli" \
  "grep -c 'hermes-agent/hermes_cli/web_dist' '${SCAFFOLD_DASH}/start-dashboard.sh' || echo 0" \
  "0"
check "080 dashboard launcher does not call dest-side install-web-dist" \
  "grep -c 'install-web-dist.sh' '${SCAFFOLD_DASH}/start-dashboard.sh' || echo 0" \
  "0"
check "080 golden has no dest dashboard web_dist bundle" \
  "test ! -e '${SCAFFOLD_DASH}/web_dist' && echo 1 || echo 0" \
  "1"
check "080 golden has no dest install-web-dist.sh" \
  "test ! -e '${SCAFFOLD_DASH}/install-web-dist.sh' && echo 1 || echo 0" \
  "1"
check "080 golden has no dest dashboard PIN" \
  "test ! -e '${SCAFFOLD_DASH}/PIN' && echo 1 || echo 0" \
  "1"
check "080 golden has no dest .hermes/checks tree" \
  "test ! -e '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/checks' && echo 1 || echo 0" \
  "1"

SCAFFOLD_PROFILES="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/config/profiles"
GITOPS_INIT="${REPO_ROOT}/gitops/stages/070-advanced-app-platform/070-devspaces/maas-api-key-provisioning.yaml"
# The per-persona key Job and its endpoint ConfigMap (Stage 070 devspaces/maas-keys/base).
GITOPS_KEYS="${REPO_ROOT}/gitops/stages/070-advanced-app-platform/070-devspaces/maas-keys/base"
check "080 GitOps does not invoke golden assert-agent-pin.py" \
  "grep -v '^[[:space:]]*#' '${GITOPS_INIT}' | grep -c 'assert-agent-pin.py' || echo 0" \
  "0"
check "080 GitOps pin oracle does not use --agent-src" \
  "grep -c -- '--agent-src' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 GitOps has no agent-pin heredoc" \
  "grep -c 'AGENTPINEOF' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 GitOps does not curl-install Hermes" \
  "grep -c 'hermes-install.sh' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 GitOps uses overlay-baked /usr/local/bin/hermes" \
  "grep -v '^[[:space:]]*#' '${GITOPS_INIT}' | grep -F 'hermes_bin=\"/usr/local/bin/hermes\"' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 GitOps pin oracle ast-reads overlay /opt/hermes-agent" \
  "grep -v '^[[:space:]]*#' '${GITOPS_INIT}' | grep -F 'agent_src=\"/opt/hermes-agent\"' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 GitOps SOUL smoke uses overlay /opt/hermes-agent (no dest fallback)" \
  "grep -v '^[[:space:]]*#' '${GITOPS_INIT}' | grep -F 'hermes_agent_root=\"/opt/hermes-agent\"' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 GitOps dest-init prefers env MAAS_API_BASE_URL then gateway MAAS_BASE_URL" \
  "grep -v '^[[:space:]]*#' '${GITOPS_INIT}' | grep -F 'os.environ.get(\"MAAS_API_BASE_URL\")' >/dev/null && grep -qF 'os.environ.get(\"MAAS_BASE_URL\")' '${GITOPS_INIT}' && grep -qF '/v1' '${GITOPS_INIT}' && grep -qF '/v1' '${GITOPS_INIT}' && echo 1 || echo 0" \
  "1"
check "080 GitOps ConfigMap is the MaaS gateway path (not KServe host)" \
  "grep -qF 'MAAS_API_PATH: /v1' '${GITOPS_KEYS}/workspace-maas-model-endpoint.yaml' && grep -qF 'MAAS_API_PATH_QWEN36: /v1' '${GITOPS_KEYS}/workspace-maas-model-endpoint.yaml' && grep -q 'name: workspace-maas-model-endpoint' '${GITOPS_KEYS}/workspace-maas-model-endpoint.yaml' && ! grep -q 'kserve-workload-svc' '${GITOPS_KEYS}/workspace-maas-model-endpoint.yaml' && echo 1 || echo 0" \
  "1"
check "080 GitOps derives workspace-maas-credentials from QWEN27B key + ConfigMap URL" \
  "grep -qF '\"name\": \"workspace-maas-credentials\"' '${GITOPS_KEYS}/maas-key-provisioner.yaml' && grep -q 'workspace-maas-model-endpoint' '${GITOPS_KEYS}/maas-key-provisioner.yaml' && grep -q 'secret_writer.py' '${GITOPS_KEYS}/maas-key-provisioner.yaml' && echo 1 || echo 0" \
  "1"
check "080 GitOps MaaS env derive does not bounce Running dest pods" \
  "grep -q 'workspace-maas-credentials derived' '${GITOPS_KEYS}/maas-key-provisioner.yaml' && awk '/workspace-maas-credentials derived/,0' '${GITOPS_KEYS}/maas-key-provisioner.yaml' | grep -c 'oc delete pod' || echo missing" \
  "0"
check "080 GitOps dest-init derives worker base from gateway MAAS_BASE_URL" \
  "grep -c 'MaaS gateway base from MAAS_BASE_URL' '${GITOPS_KEYS}/maas-key-provisioner.yaml' || echo 0" \
  "1"
check "080 GitOps dest-init pin files do not label the gateway as KServe" \
  "grep -c 'in-cluster-kserve' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 GitOps dest-init does not pin ssl_ca_cert on the qwen provider" \
  "grep -c '\"ssl_ca_cert\": service_ca,' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 GitOps dest-init pairs ssl_ca_cert with resolved .svc vs route" \
  "grep -c 'route endpoint must NOT pin ssl_ca_cert' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps dest-init ssl_ca_cert gate uses resolved model_base" \
  "grep -c 'Use the RESOLVED url (model_base)' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps does not copy dest kanban-stuck-watchdog" \
  "grep -c 'home/scripts/kanban-stuck-watchdog' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 RHDH skeleton destfile does not invoke dest supervise-gateway" \
  "grep -c '.hermes/home/scripts/supervise-gateway.sh' '${REPO_ROOT}/gitops/stages/070-advanced-app-platform/070-rhdh/templates/app-migration/skeleton/devfile.yaml' || echo 0" \
  "0"
check "080 golden destfile does not invoke dest supervise-gateway" \
  "grep -c '.hermes/home/scripts/supervise-gateway.sh' '${SCAFFOLD_080}/devfile.yaml' || echo 0" \
  "0"
# The factory replaces the golden devfile. DWO debug start is a metadata
# annotation set through Dev Spaces, not a devfile attribute.
check "080 golden destfile does not tee postStart to PVC" \
  "grep -c 'poststart.log' '${SCAFFOLD_080}/devfile.yaml' || echo 0" \
  "0"
check "080 factory does not claim debug mode through an ineffective devfile attribute" \
  "grep -c 'controller.devfile.io/debug-start:' '${REPO_ROOT}/gitops/stages/070-advanced-app-platform/070-rhdh/templates/app-migration/skeleton/devfile.yaml' || true" \
  "0"
check "080 RHDH skeleton destfile does not tee postStart to PVC" \
  "grep -c 'poststart.log' '${REPO_ROOT}/gitops/stages/070-advanced-app-platform/070-rhdh/templates/app-migration/skeleton/devfile.yaml' || echo 0" \
  "0"
check "080 golden orchestrator profile template present" \
  "test -f '${SCAFFOLD_PROFILES}/orchestrator.yaml.template' && echo present || echo missing" \
  "present"
check "080 golden implementer profile template present" \
  "test -f '${SCAFFOLD_PROFILES}/implementer.yaml.template' && echo present || echo missing" \
  "present"
check "080 golden reviewer profile template present" \
  "test -f '${SCAFFOLD_PROFILES}/reviewer.yaml.template' && echo present || echo missing" \
  "present"
check "080 golden orchestrator SOUL.md present" \
  "test -f '${SCAFFOLD_PROFILES}/orchestrator.SOUL.md' && echo present || echo missing" \
  "present"
check "080 golden implementer SOUL.md present" \
  "test -f '${SCAFFOLD_PROFILES}/implementer.SOUL.md' && echo present || echo missing" \
  "present"
check "080 golden reviewer SOUL.md present" \
  "test -f '${SCAFFOLD_PROFILES}/reviewer.SOUL.md' && echo present || echo missing" \
  "present"
check "080 golden worker SOUL.md files are git-tracked" \
  "git -C '${REPO_ROOT}' ls-files --error-unmatch '${SCAFFOLD_PROFILES}/orchestrator.SOUL.md' '${SCAFFOLD_PROFILES}/implementer.SOUL.md' '${SCAFFOLD_PROFILES}/reviewer.SOUL.md' >/dev/null && echo tracked || echo missing" \
  "tracked"
check "080 four SOUL.md files have distinct sha256" \
  "sha256sum '${SCAFFOLD_080}/.hermes/SOUL.md' '${SCAFFOLD_PROFILES}/orchestrator.SOUL.md' '${SCAFFOLD_PROFILES}/implementer.SOUL.md' '${SCAFFOLD_PROFILES}/reviewer.SOUL.md' | awk '{print \$1}' | sort -u | wc -l | tr -d ' '" \
  "4"
check "080 dest-user SOUL.md names dest-user identity" \
  "grep -c 'You are the dest-user' '${SCAFFOLD_080}/.hermes/SOUL.md' || echo 0" \
  "1"
# kanban_block is a phrasing lint, not the identity gate. Distinct sha256
# (above) is what proves dest-user is not a copy of a worker SOUL.
check "080 dest-user SOUL.md is not the implementer identity" \
  "grep -c 'kanban_block' '${SCAFFOLD_080}/.hermes/SOUL.md' || echo 0" \
  "0"
check "080 implementer SOUL.md names kanban_block" \
  "grep -c 'kanban_block' '${SCAFFOLD_PROFILES}/implementer.SOUL.md' || echo 0" \
  "1"
check "080 orchestrator SOUL.md refuses to implement" \
  "grep -c 'You do not implement' '${SCAFFOLD_PROFILES}/orchestrator.SOUL.md' || echo 0" \
  "1"
check "080 reviewer SOUL.md refuses to write the product tree" \
  "grep -c 'You do not write the product tree' '${SCAFFOLD_PROFILES}/reviewer.SOUL.md' || echo 0" \
  "1"
check "080 GitOps places per-profile SOUL.md" \
  "grep -c 'profiles/\${name}/SOUL.md' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps asserts four SOUL.md sha256 are distinct" \
  "grep -c 'four SOUL.md files have distinct sha256' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps resolves worker home via hermes profile show <name> (documented syntax)" \
  "grep -c -- 'profile show \"\${_soul_profile}\"' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps SOUL smoke does not couple identity phrasing" \
  "grep -c 'doctrine marker missing after load' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 GitOps seats dest worker profiles (C-2 skip retired)" \
  "grep -c 'ensure_dest_worker_profiles' '${GITOPS_INIT}' || echo 0" \
  "2"
check "080 GitOps seats reviewer profile" \
  "grep -c '_ensure_one_dest_profile reviewer' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps pins kanban.review_dispatch true" \
  "grep -c '\"review_dispatch\": True' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps does not skip single-persona profile create" \
  "grep -c 'skip hermes profile create (single-persona)' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 GitOps creates profiles with --no-alias" \
  "grep -c 'profile create \"\${name}\" --no-alias' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps does not invoke profile create --clone" \
  "grep -cE 'profile create [^\"]*--clone|profile create --clone' '${GITOPS_INIT}' || echo 0" \
  "0"
SCAFFOLD_KERNEL="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/kernel"
SCAFFOLD_LAYOUT="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/LAYOUT.md"
check "080 golden K2 REHOST pre_tool_call.sh present" \
  "test -f '${SCAFFOLD_KERNEL}/pre_tool_call.sh' && echo present || echo missing" \
  "present"
check "080 golden pre_tool_call.sh is executable" \
  "test -x '${SCAFFOLD_KERNEL}/pre_tool_call.sh' && echo 1 || echo 0" \
  "1"
check "080 K2 hook splits allow-root on pathsep" \
  "grep -q 'allow.split(os.pathsep)' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' && echo 1 || echo 0" \
  "1"
check "080 K2 hook uses hook_cwd for transparent pathless" \
  "grep -q 'hook_cwd' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' && echo 1 || echo 0" \
  "1"
check "080 K2 hook denies opaque construction" \
  "grep -q '_OPAQUE' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' && echo 1 || echo 0" \
  "1"
check "080 K2 opacity is not gated on not-proven" \
  "awk '/for _rx in _OPAQUE/{found=1; exit} /if cmd.strip()/{ok=1} END{print (found && ok)?1:0}' '${SCAFFOLD_KERNEL}/pre_tool_call.sh'" \
  "1"
check "080 K2 hook strips env assignments as values not access" \
  "grep -q 'strip_env_assignments' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' && echo 1 || echo 0" \
  "1"
check "080 K2 toolchain reads are not an allow-root widen" \
  "grep -q 'def toolchain_read' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' && echo 1 || echo 0" \
  "1"
check "080 K2 names orchestrator disabled toolset" \
  "grep -q 'disabled for profile orchestrator' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' && echo 1 || echo 0" \
  "1"
check "080 K2 enforces files_writable" \
  "grep -q 'files_writable' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' && echo 1 || echo 0" \
  "1"
check "080 K2 refuses complete after a red bound gate" \
  "grep -q 'kanban_complete refused' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' && echo 1 || echo 0" \
  "1"
check "080 inventory-legacy-surface scan root is fence-legal" \
  "awk '/inventory-entry-points.py/{getline; print}' '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/analysis/inventory-legacy-surface/SKILL.md' | grep -c '/projects/.derived/legacy-at-3' || echo 0" \
  "0"
check "080 catalog, templates and Locations bind to one verified release" \
  "python3 '${REPO_ROOT}/gitops/stages/070-advanced-app-platform/070-rhdh/jobs/catalog/render_catalog.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 K2 env-assignment selftest passes" \
  "python3 '${SCAFFOLD_KERNEL}/k2_selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
# V17-6b: the paved-road audit grades mandated commands from the execution
# ledger this observer writes; the producer copies this one file into Managed
# Scope, so it must be executable and self-contained.
check "080 K2 post_tool_call observer is executable" \
  "test -x '${SCAFFOLD_KERNEL}/post_tool_call.py' && echo 1 || echo 0" \
  "1"
check "080 the outcome authority never executes analyzer code from the destination tree" \
  "python3 '${SCAFFOLD_KERNEL}/../lib/planner/analyzer_isolation.test.py' >/dev/null 2>&1 && echo 1 || echo 0" \
  "1"
# outcome-board/v2 (architect review 2026-09-27): Hermes Kanban is the one
# lifecycle authority; the domain adapter guards native actions. No sidecar.
check "080 native control (outcome-board/v2) selftest passes (publication, same-task review, budget, owner repair, M4 accepted, M5 read-back, K2)" \
  "PYTHONDONTWRITEBYTECODE=1 python3 '${SCAFFOLD_KERNEL}/../lib/planner/native_board.test.py' >/dev/null 2>&1 && echo 1 || echo 0" \
  "1"
check "080 new runs default to outcome-board/v2 and the skeleton renders no authority sidecar" \
  "n=0; T='${REPO_ROOT}/gitops/stages/070-advanced-app-platform/070-rhdh/templates/app-migration'; grep -A1 -E '^ +boardProtocol:' \"\$T/template.yaml\" >/dev/null && awk '/boardProtocol:/{f=1} f&&/default:/{print; exit}' \"\$T/template.yaml\" | grep -q 'outcome-board/v2' && n=\$((n+1)); ! grep -q 'outcome-authority' \"\$T/skeleton/devfile.yaml\" && n=\$((n+1)); echo \$n" \
  "2"
check "080 the producer registers v2 hooks without a reconciler (outcome-board-hooks selftest)" \
  "python3 '${REPO_ROOT}/gitops/stages/070-advanced-app-platform/070-devspaces/outcome-board-hooks.test.py' >/dev/null 2>&1 && echo 1 || echo 0" \
  "1"
check "080 K2 refuses hand-written native-control records and reserved attachments" \
  "grep -c 'native-control\\] records are written by' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' || echo 0" \
  "1"
check "080 K2 post_tool_call observer records positive execution evidence" \
  "python3 '${SCAFFOLD_KERNEL}/post_tool_call.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 in-workspace stops: per-run token budget, run-level token budget and no-accepted-checkpoint (run_budget selftest)" \
  "PYTHONDONTWRITEBYTECODE=1 python3 '${SCAFFOLD_KERNEL}/run_budget.test.py' >/dev/null 2>&1 && echo 1 || echo 0" \
  "1"
check "080 a retry after a loop stop starts escalated only on a loop_escalation profile (worker_launch selftest)" \
  "PYTHONDONTWRITEBYTECODE=1 python3 '${SCAFFOLD_KERNEL}/worker_launch.test.py' >/dev/null 2>&1 && echo 1 || echo 0" \
  "1"
check "080 the producer installs the run budgets and the worker launch shim (run-budgets-hooks selftest)" \
  "python3 '${REPO_ROOT}/gitops/stages/070-advanced-app-platform/070-devspaces/run-budgets-hooks.test.py' >/dev/null 2>&1 && echo 1 || echo 0" \
  "1"
check "080 K2 implementer complete is request_review" \
  "tr -d '\n' < '${SCAFFOLD_KERNEL}/pre_tool_call.sh' | sed 's/\"[[:space:]]*\"//g' | grep -c 'implementer terminator is kanban_request_review' || echo 0" \
  "1"
# The hook is `exec python3 -c '<body>'`: one apostrophe anywhere in the body,
# including a comment, ends the shell string and the hook silently fails OPEN
# (measured 2026-09-10: "v6's" in a comment made every call allow).
check "080 K2 hook python body carries no apostrophe (single-quoted shell string)" \
  "hook_body_apostrophes '${SCAFFOLD_KERNEL}/pre_tool_call.sh'" \
  "0"
check "080 K2 hook refuses reviewer exploration after a green paved-road audit" \
  "grep -v '^[[:space:]]*#' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' | grep -c 'already exited 0' || echo 0" \
  "1"
check "080 K2 complete hook writes breadcrumb" \
  "grep -v '^[[:space:]]*#' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' | grep -c 'complete-invocations.jsonl' || echo 0" \
  "1"
SCAFFOLD_LIB="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/lib"
SCAFFOLD_PAVED="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/paved-road"
SCAFFOLD_AUTOSTART="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/harness/dispatch-phase/scripts"
check "080 paved-road lib selftest passes" \
  "python3 '${SCAFFOLD_LIB}/paved_road.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 paved-road-m1 selftest passes" \
  "python3 '${SCAFFOLD_PAVED}/paved-road-m1/scripts/selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 paved-road-m2 selftest passes (activation gate first; not-activated REFUSE)" \
  "python3 '${SCAFFOLD_PAVED}/paved-road-m2/scripts/selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 paved-road-m3 selftest passes (view-first; advance is the verdict step; reverted PASS; refused-advance REFUSE)" \
  "python3 '${SCAFFOLD_PAVED}/paved-road-m3/scripts/selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 loop cards pin paved-road-m3 only (no story-era pom skills, no bare fix-until-green pin)" \
  "python3 -c \"import sys; sys.path.insert(0, '${SCAFFOLD_LIB}'); from planner.cards import CARD_SKILLS; print(1 if all(v == ['paved-road-m3'] for k, v in CARD_SKILLS.items() if k != 'close') else 0)\"" \
  "1"
check "080 K2 lets the implementer complete a loop card on the recorded verdict (paved-road-m3)" \
  "grep -v '^[[:space:]]*#' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' | grep -c 'allow_implementer_loop' || echo 0" \
  "1"
# The measure may never be greener than the build. A generator whose output
# folder is not the registered compile source root makes the offline checker
# resolve types Maven cannot (pilot v7, 2026-09-10: DTOs in src/gen/java,
# pom registering src/main/java, Maven failing at default-compile while the
# checker reported zero errors).
check "080 the OpenAPI generator writes to the registered compile source root" \
  "jq -r '.plugin_config[\"org.openapitools:openapi-generator-maven-plugin\"].configOptions.sourceFolder' '${SCAFFOLD_080}/.hermes/planning/catalogs/compat-mapping.json'" \
  "src/main/java"
check "080 run-verify records whether Maven itself could compile" \
  "grep -c 'MVN_COMPILE_FAILED' '${SCAFFOLD_080}/.hermes/skills/migration/fix-until-green/scripts/run-verify.sh' || echo 0" \
  "3"
check "080 the measure is unknown when the checker disagrees with Maven" \
  "grep -v '^[[:space:]]*#' '${SCAFFOLD_LIB}/planner/worklist.py' | grep -c 'javac diagnostics disagree with Maven' || echo 0" \
  "1"
check "080 brief enrichment selftest passes (unmanaged→managed artifact; inventory; Jakarta rename; property mapping)" \
  "python3 '${SCAFFOLD_080}/.hermes/skills/migration/fix-until-green/scripts/brief.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 paved-road-m4 selftest passes (oracles first; runner before the producer; verdict composed, not chosen)" \
  "python3 '${SCAFFOLD_PAVED}/paved-road-m4/scripts/selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 the M4 card pins the paved-road index only (not a checklist of gate skills)" \
  "python3 -c \"import sys; sys.path.insert(0, '${SCAFFOLD_LIB}'); from planner.cards import CARD_SKILLS; print(','.join(CARD_SKILLS['close']))\"" \
  "paved-road-m4"
check "080 every implemented phase has a paved road (including M5 when shipped)" \
  "last=4; [[ -f '${SCAFFOLD_LIB}/m5_delivery.py' ]] && last=5; ok=1; for i in \$(seq 1 \$last); do [[ -f '${SCAFFOLD_PAVED}'/paved-road-m\$i/steps.json ]] || ok=0; done; echo \$ok" \
  "1"
check "080 paved-road coverage lint passes" \
  "python3 '${SCAFFOLD_LIB}/paved_road.py' coverage >/dev/null && echo 1 || echo 0" \
  "1"
# v8+: creating the workspace is the authorization. dest-init records it as an
# unbound pilot seal (fail-closed until M1 produces a bundle) and the last M1
# road step binds it, so a run needs no human keystroke between M1 and M2.
check "080 dest-init records the workspace-creator authorization as an unbound pilot seal" \
  "grep -v '^[[:space:]]*#' '${GITOPS_INIT}' | grep -c 'devworkspace-creator:' || echo 0" \
  "1"
check "080 dest-init leaves an activated planner or an existing seal alone" \
  "grep -c 'pilot seal already present for run' '${GITOPS_INIT}' || echo 0" \
  "1"
# both bind paths refuse an unfit bundle: the governed (run control) and the legacy (pins) one
check "080 the dispatcher binds a platform-authorized seal and refuses an unfit bundle" \
  "grep -c 'BIND_UNFIT_BUNDLE' '${SCAFFOLD_AUTOSTART}/autostart-migration.sh' || echo 0" \
  "2"
check "080 only a platform-recorded authorization may be bound (never a worker-authored one)" \
  "python3 -c \"import sys; sys.path.insert(0, '${SCAFFOLD_LIB}'); from planner.pins import pilot_bind_gaps as g; ok={'planner':{'activation':'pilot','pilot':{'run_id':'r','authorized_by':'u','evidence_bundle_sha256':'','authorization':{'source':'devworkspace','creator':'c'}}}}; bad={'planner':{'activation':'pilot','pilot':{'run_id':'r','authorized_by':'u','evidence_bundle_sha256':'','authorization':{'source':'worker','creator':'c'}}}}; print(1 if not g(ok) and g(bad) else 0)\"" \
  "1"
check "080 paved-road-m1 ends by dispatching the next phase" \
  "jq -r '.steps[-1].native' '${SCAFFOLD_PAVED}/paved-road-m1/steps.json'" \
  "autostart-migration.sh"
check "080 autostart pins paved-road-m1 only on M1" \
  "grep -c -- '--skill paved-road-m1' '${SCAFFOLD_AUTOSTART}/autostart-migration.sh' || echo 0" \
  "1"
check "080 autostart mints M2 only behind pins.planner.activation" \
  "grep -c 'PLANNER_ACTIVATION}\" == \"activated\"' '${SCAFFOLD_AUTOSTART}/autostart-migration.sh' || echo 0" \
  "1"
check "080 autostart M2 card pins paved-road-m2 (child of M1, key m2-plan)" \
  "grep -c -- '--idempotency-key m2-plan' '${SCAFFOLD_AUTOSTART}/autostart-migration.sh' || echo 0" \
  "1"
check "080 autostart never mints M3/M4" \
  "grep -c -E '\"M3 |\"M4 ' '${SCAFFOLD_AUTOSTART}/autostart-migration.sh' || echo 0" \
  "0"
check "080 autostart does not pin scan-with-mta on the card" \
  "grep -c -- '--skill scan-with-mta' '${SCAFFOLD_AUTOSTART}/autostart-migration.sh' || echo 0" \
  "0"
check "080 autostart-migration selftest passes" \
  "python3 '${SCAFFOLD_AUTOSTART}/autostart-migration.selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
# Run declarations (2026-09-24): the golden is reusable, so it names no run and
# claims no readiness; the factory writes the run's own run-budget.json into the
# destination's initial commit. One golden revision must serve v12 and every
# later run without an edit.
check "080 the golden carries shared run defaults only (no run identity, timestamp or readiness)" \
  "S='${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold'; test ! -e \"\$S/run-budget.json\" && test ! -e \"\$S/run-configuration.json\" && python3 -c \"import json,sys; d=json.load(open(sys.argv[1])); keys=set(); w=lambda o: [keys.add(k) or w(v) for k,v in o.items()] if isinstance(o,dict) else None; w(d); sys.exit(0 if d['budget']['max_wall_hours']>0 and not keys & {'run_id','declared_at','recorded_at','ready'} else 1)\" \"\$S/run-defaults.json\" && echo GOLDEN_RUN_FREE || echo GOLDEN_CARRIES_A_RUN" \
  "GOLDEN_RUN_FREE"
check "080 run_declaration refuses missing, foreign, stale and rewritten declarations" \
  "python3 '${SCAFFOLD_LIB}/planner/run_declaration.test.py' >/dev/null 2>&1 && echo DECLARATION_SELFTEST_OK || echo DECLARATION_SELFTEST_FAILED" \
  "DECLARATION_SELFTEST_OK"
check "080 launch check's in-workspace program compiles" \
  "printf '%s\\n' \"\$IN_WORKSPACE_CHECKS\" | python3 -c 'import sys; compile(sys.stdin.read(), \"in-workspace\", \"exec\")' && echo RUN_PREFLIGHT_SYNTAX_OK || echo RUN_PREFLIGHT_SYNTAX_FAILED" \
  "RUN_PREFLIGHT_SYNTAX_OK"
check "080 launch preflight preserves pinned images and worker identity without historical campaign receipts" \
  "run_launch_selftest" \
  "RUN_PREFLIGHT_TEST_OK"
check "080 the factory stamps run-budget.json from the full project name and its scaffolder task" \
  "T='${REPO_ROOT}/gitops/stages/070-advanced-app-platform/070-rhdh/templates/app-migration'; grep -qF '\"run_id\": \"\${{ values.name }}\"' \"\$T/skeleton/run-budget.json\" && grep -qF '\"scaffolder_task\": \"\${{ values.scaffolderTaskId }}\"' \"\$T/skeleton/run-budget.json\" && grep -v '^[[:space:]]*#' \"\$T/template.yaml\" | grep -qF 'scaffolderTaskId: \${{ context.task.id }}' && echo FACTORY_DECLARES_RUN || echo FACTORY_DOES_NOT_DECLARE" \
  "FACTORY_DECLARES_RUN"
check "080 build-worklist reports failures without repeating verification" \
  "python3 '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/planning/build-worklist/scripts/build-worklist.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 derive default DERIVED_ROOT is inside dest tree" \
  "grep -c '\${MODERNIZED_ROOT}/.derived/legacy-at-3' '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/migration/derive-legacy-boot3/scripts/derive-legacy-boot3.sh' || echo 0" \
  "1"
check "080 derive-legacy-boot3 identity omits derived_root" \
  "python3 '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/migration/derive-legacy-boot3/scripts/derive-legacy-boot3.selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 GitOps dest-init K2_ALLOW_ROOT includes /projects/legacy" \
  "awk '/K2_ALLOW_ROOT/ && /\\/projects\\/legacy/ {print 1; exit}' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps write sandbox stays PROJECT_DIR (legacy not in HERMES_WRITE_SAFE_ROOT)" \
  "grep -E '^[[:space:]]*(export )?HERMES_WRITE_SAFE_ROOT=' '${GITOPS_INIT}' | grep -c '/projects/legacy' || echo 0" \
  "0"
check "080 LAYOUT classifies K2 as REHOST" \
  "grep -q 'K2 REHOST' '${SCAFFOLD_LAYOUT}' && echo present || echo missing" \
  "present"
check "080 golden K1 schema loader validator present" \
  "test -f '${SCAFFOLD_KERNEL}/k1_schema.py' && test -f '${SCAFFOLD_KERNEL}/k1_load.py' && test -f '${SCAFFOLD_KERNEL}/k1_validate.py' && test -f '${SCAFFOLD_KERNEL}/.hermes-kernel' && echo present || echo missing" \
  "present"
check "080 golden K3 snapshot + live comparator present" \
  "test -f '${SCAFFOLD_KERNEL}/k3_schema.py' && test -f '${SCAFFOLD_KERNEL}/k3_verify.py' && test -f '${SCAFFOLD_KERNEL}/k3_live.py' && echo present || echo missing" \
  "present"
check "080 a set-wide packaging cause is a typed blocker, never a one-file card from the name it happened to report" \
  "n=0; grep -q -F 'def set_wide_scope' '${SCAFFOLD_LIB}/planner/worklist.py' && n=\$((n+1)); grep -q -F 'RUNTIME_SET_WIDE' '${SCAFFOLD_LIB}/planner/worklist.py' && n=\$((n+1)); grep -q -F '\"set_wide\": scope' '${SCAFFOLD_LIB}/planner/worklist.py' && n=\$((n+1)); grep -q -F '_set_wide_case' '${SCAFFOLD_LIB}/planner/worklist.test.py' && n=\$((n+1)); echo \$n" \
  "4"
check "080 the live board is enriched by ONE implementation, and K3 and K4 both use it (the edges arrive beside the task)" \
  "n=0; grep -q -F 'def collect_board' '${SCAFFOLD_LIB}/planner/live_board.py' && n=\$((n+1)); grep -q -F 'collect_board(' '${SCAFFOLD_KERNEL}/k3_live.py' && n=\$((n+1)); grep -q -F 'collect_board(' '${SCAFFOLD_KERNEL}/k4_mint.py' && n=\$((n+1)); grep -q -F 'detail.get(\"task\")' '${SCAFFOLD_KERNEL}/k3_live.py' '${SCAFFOLD_KERNEL}/k4_mint.py' || n=\$((n+1)); echo \$n" \
  "4"
check "080 the scenario corpus is a producer output and captures are qualified by a gate, never signed by a person (derive + qualify present, selftest referenced and green)" \
  "n=0; test -f '${SCAFFOLD_080}/.hermes/skills/gates/capture-source-oracles/scripts/derive-source-scenarios.py' && n=\$((n+1)); test -f '${SCAFFOLD_080}/.hermes/skills/gates/capture-source-oracles/scripts/qualify-source-captures.py' && n=\$((n+1)); grep -q -F 'scenario-derivation.test.py' '${SCAFFOLD_080}/.hermes/skills/gates/capture-source-oracles/SKILL.md' && n=\$((n+1)); grep -q -F 'derive-source-scenarios' '${SCAFFOLD_080}/.hermes/skills/paved-road/paved-road-m1/steps.json' && n=\$((n+1)); python3 '${SCAFFOLD_080}/.hermes/skills/gates/capture-source-oracles/scripts/scenario-derivation.test.py' >/dev/null 2>&1 && n=\$((n+1)); echo \$n" \
  "5"
check "080 K1 selftest passes (receipt/write-set/artifact body codes)" \
  "python3 '${SCAFFOLD_KERNEL}/k1_selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 golden K4 converter present" \
  "test -f '${SCAFFOLD_KERNEL}/k4_schema.py' && test -f '${SCAFFOLD_KERNEL}/k4_convert.py' && echo present || echo missing" \
  "present"
# B11 (635d9496): loop cards get one automatic recovery after a halt, so K4
# pins max_retries to k4_schema.LOOP_MAX_RETRIES = 2; autostart gives M1/M2 the same 2 (v32)
check "080 K4 payloads pin max_retries to LOOP_MAX_RETRIES (2)" \
  "grep -q '^LOOP_MAX_RETRIES = 2$' '${SCAFFOLD_KERNEL}/k4_schema.py' && grep -c '\"max_retries\": LOOP_MAX_RETRIES' '${SCAFFOLD_KERNEL}/k4_convert.py' || echo 0" \
  "1"
check "080 K4 converter emits no fixed m4-verify idempotency key (receipt-bound for M4 too)" \
  "grep -c 'm4-verify' '${SCAFFOLD_KERNEL}/k4_convert.py' || echo 0" \
  "0"
check "080 K4 mint refuses a fixed m4-verify key" \
  "grep -c 'key == \"m4-verify\"' '${SCAFFOLD_KERNEL}/k4_mint.py' || echo 0" \
  "1"
check "080 RHDH autoStartMigration parameter defaults true" \
  "grep -A6 'autoStartMigration:' '${REPO_ROOT}/gitops/stages/070-advanced-app-platform/070-rhdh/templates/app-migration/template.yaml' | grep -c 'default: true' || echo 0" \
  "1"
check "080 destfile stamps AUTO_START_MIGRATION" \
  "grep -c 'AUTO_START_MIGRATION' '${REPO_ROOT}/gitops/stages/070-advanced-app-platform/070-rhdh/templates/app-migration/skeleton/devfile.yaml' || echo 0" \
  "1"
check "080 RHDH template has no needsDatabase parameter" \
  "grep -c 'needsDatabase' '${REPO_ROOT}/gitops/stages/070-advanced-app-platform/070-rhdh/templates/app-migration/template.yaml' || echo 0" \
  "0"
check "080 skeleton ships postgres as k8s-templates not cut-time k8s/" \
  "test -f '${REPO_ROOT}/gitops/stages/070-advanced-app-platform/070-rhdh/templates/app-migration/skeleton/k8s-templates/postgres.yaml' && test ! -f '${REPO_ROOT}/gitops/stages/070-advanced-app-platform/070-rhdh/templates/app-migration/skeleton/k8s/postgres.yaml' && echo 1 || echo 0" \
  "1"
check "080 skeleton app.yaml is not Jinja-gated on needsDatabase" \
  "grep -c 'needsDatabase' '${REPO_ROOT}/gitops/stages/070-advanced-app-platform/070-rhdh/templates/app-migration/skeleton/k8s/app.yaml' || echo 0" \
  "0"
check "080 golden migration.yaml has no needsDatabase field" \
  "grep -c 'needsDatabase' '${SCAFFOLD_080}/migration.yaml' || echo 0" \
  "0"
check "080 golden K4 selftest passes" \
  "python3 '${SCAFFOLD_KERNEL}/k4_selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 golden K4 mint-writer present" \
  "test -f '${SCAFFOLD_KERNEL}/k4_mint.py' && echo present || echo missing" \
  "present"
check "080 K4 mint-writer selftest passes" \
  "python3 '${SCAFFOLD_KERNEL}/k4_mint_selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 kanban attach selftest passes" \
  "python3 '${SCAFFOLD_KERNEL}/kanban_attach_selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 M1/M2 handoff facts tests pass" \
  "python3 '${SCAFFOLD_KERNEL}/handoff_facts.test.py' >/dev/null 2>&1 && echo 1 || echo 0" \
  "1"
check "080 measurement execution and M4 test obligation tests pass (v24 WP2)" \
  "PYTHONDONTWRITEBYTECODE=1 python3 '${SCAFFOLD_KERNEL}/../lib/planner/measurement.test.py' >/dev/null 2>&1 && echo 1 || echo 0" \
  "1"
check "080 v24 integrated native sequence passes" \
  "PYTHONDONTWRITEBYTECODE=1 python3 '${SCAFFOLD_KERNEL}/../lib/planner/v24_sequence.test.py' >/dev/null 2>&1 && echo 1 || echo 0" \
  "1"
check "080 authoritative outcome line and retry brief tests pass (v24 WP4)" \
  "python3 '${SCAFFOLD_KERNEL}/../skills/migration/fix-until-green/scripts/outcome-line.test.py' >/dev/null 2>&1 && echo 1 || echo 0" \
  "1"
check "080 one family budget: native account governs, loop projects it (v24)" \
  "PYTHONDONTWRITEBYTECODE=1 python3 '${SCAFFOLD_KERNEL}/../lib/planner/family_budget.test.py' >/dev/null 2>&1 && PYTHONDONTWRITEBYTECODE=1 python3 '${SCAFFOLD_KERNEL}/../skills/migration/fix-until-green/scripts/family-budget-loop.test.py' >/dev/null 2>&1 && echo 1 || echo 0" \
  "1"
check "080 M1 MTA analyzer exit judgement tests pass (v24 WP5)" \
  "python3 '${SCAFFOLD_KERNEL}/../skills/analysis/scan-with-mta/scripts/mta-analyze-legacy.test.py' >/dev/null 2>&1 && echo 1 || echo 0" \
  "1"
check "080 G-4 claim consistency selftest passes" \
  "python3 '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/gates/check-release-readiness/scripts/assert-g4-claim-consistency.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
SCAFFOLD_PARK="${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/_park"
check "080 golden _park retired" \
  "test ! -e '${SCAFFOLD_PARK}' && echo absent || echo present" \
  "absent"
check "080 dest-init pins security.tirith_enabled false" \
  "grep -c 'tirith_enabled.: False' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 dest-init does not prepend HERMES_HOME/bin (braced; Operator 123436ZO)" \
  "grep -c 'HERMES_HOME}/bin' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 tirith-declared-absent rule retired" \
  "test ! -f '${REPO_ROOT}/.agents/rules/tirith-declared-absent.md' && echo absent || echo present" \
  "absent"
check "080 python human_home is in .hermes/lib" \
  "test -f '${SCAFFOLD_080}/.hermes/lib/human_home.py' && grep -c 'Path.home() in a KEEP' '${SCAFFOLD_080}/.hermes/lib/human_home.py' || echo 0" \
  "1"
check "080 assert-extension-tooling uses human_home" \
  "grep -c 'human_home()' '${SCAFFOLD_080}/.hermes/skills/migration/manage-quarkus-extensions/scripts/assert-extension-tooling.py' || echo 0" \
  "1"
check "080 GitOps copies kernel pre_tool_call when k2_present" \
  "grep -c 'elif k2_present' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps K2 matcher includes execute_code" \
  "grep -c 'execute_code|delegate_task' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps K2 matcher includes skill_manage" \
  "grep -c 'delegate_task|skill_manage' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 GitOps pre_tool_call matcher includes native complete" \
  "grep -oE '\"matcher\": \"[^\"]+\"' '${GITOPS_INIT}' | grep -F kanban_complete | grep -cF complete_task" \
  "2"
check "080 GitOps no longer forbids the K2 instrumentation land" \
  "grep -c 'Do not mkdir kernel/. Do not land K2' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 GitOps hooks_auto_accept is top-level official key" \
  "grep -c 'unknown event name and never auto-approves' '${GITOPS_INIT}' || echo 0" \
  "1"
check "080 AGENTS.md states the AI is not the planner of record" \
  "grep -c 'the AI is not the planner of record' '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/AGENTS.md' || echo 0" \
  "1"
check "080 dest-init external_dirs fail-closed names unreadable path" \
  "grep -c 'missing or unreadable' '${GITOPS_INIT}' || echo 0" \
  "2"
check "080 check-external-dirs requires dest-user home literal" \
  "grep -c '/home/user/.hermes/skills' '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/lib/check-external-dirs.py' || echo 0" \
  "3"
check "080 pom platform-pins plugin coverage selftest passes" \
  "python3 '${SCAFFOLD_080}/.hermes/skills/migration/manage-quarkus-extensions/scripts/check-pom-platform-pins.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 test-toolchain assertj pin selftest passes" \
  "python3 '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/gates/check-release-readiness/scripts/check-test-toolchain.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 emit-required-extensions (freeze analysis copy) selftest passes" \
  "python3 '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/skills/analysis/scan-with-mta/scripts/emit-required-extensions.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
SCAFFOLD_SKILLS="${SCAFFOLD_080}/.hermes/skills"
check "080 Spec Kit skills are removed (no compatibility path)" \
  "test ! -d '${SCAFFOLD_SKILLS}/sdd/plan-migration-partition' && test ! -d '${SCAFFOLD_SKILLS}/sdd/check-spec-readiness' && test ! -f '${SCAFFOLD_KERNEL}/speckit_feature.py' && echo absent || echo present" \
  "absent"
check "080 Spec Kit residue scan is clean (skills, kernel, lib, planning)" \
  "{ grep -rIl -E 'speckit|/speckit\\.|specify init|\\.specify/|spec\\.md|tasks\\.md|check-spec-readiness|plan-migration-partition|partition\\.json' '${SCAFFOLD_SKILLS}' '${SCAFFOLD_KERNEL}' '${SCAFFOLD_LIB}' '${SCAFFOLD_080}/.hermes/planning' --exclude-dir=__pycache__ || true; } | { grep -v -E 'paved_road(\\.test)?\\.py$|k4_(convert|schema|selftest|mint|mint_selftest)\\.py$|paved-road-m2/(SKILL\\.md|scripts/selftest\\.py)$|derive-story-oracles/|k2_selftest\\.py$|dispatch-phase/scripts/autostart-migration\\.(sh|selftest\\.py)$' || true; } | wc -l | tr -d ' '" \
  "0"
check "080 pins.json planner activation is not-activated on golden" \
  "jq -r '.pins.planner.activation' '${SCAFFOLD_080}/.hermes/pins.json'" \
  "not-activated"
check "080 pins.json: structure_extractor pinned to the toolchain JDK, mta_cli pinned 8.3 with a measured 64-hex artifact digest and named artifact, no retired optional producers" \
  "jq -r '.pins as \$p | (\$p.mta_cli // {}) as \$m | if (\$p.structure_extractor.version == \"jdk-21\") and \$m.version == \"8.3\" and (\$m.artifact_sha256 // \"\" | tostring | test(\"^[0-9a-f]{64}$\")) and (\$m.artifact // \"\" | tostring | gsub(\"\\\\s\"; \"\") | length > 0) and (\$p | has(\"spoon\") or has(\"jqassistant\") or has(\"context_probe\") | not) then \"ok\" else \"bad\" end' '${SCAFFOLD_080}/.hermes/pins.json'" \
  "ok"
check "080 K2 hook vetoes worker graph mutation (kanban_create/link/swarm/decompose)" \
  "grep -c 'GRAPH_MUTATION_TOOLS' '${SCAFFOLD_KERNEL}/pre_tool_call.sh' || echo 0" \
  "2"
check "080 K4 mint records task-id provenance for K3 (mint receipt)" \
  "grep -c 'def write_mint_receipt' '${SCAFFOLD_KERNEL}/k4_mint.py' || echo 0" \
  "1"
check "080 K3 never infers card provenance from title or body" \
  "grep -c -E 'title\\[len\\(prefix\\)|startswith\\(prefix\\)' '${SCAFFOLD_LIB}/planner/live_board.py' || echo 0" \
  "0"
check "080 K4 re-derives the activation/pilot verdict from pins.json" \
  "grep -c 'activation_gaps(' '${SCAFFOLD_KERNEL}/k4_convert.py' || echo 0" \
  "1"
check "080 golden pins.json carries no pilot seal" \
  "jq -r 'if (.pins.planner.pilot // null) | (. == null or . == false or . == {} or . == [] or . == \"\" or . == 0) then \"none\" else \"present\" end' '${SCAFFOLD_080}/.hermes/pins.json'" \
  "none"
check "080 planning contracts present (schemas, catalogs, canary, decisions example)" \
  "test -f '${SCAFFOLD_080}/.hermes/planning/schemas/admission-receipt.schema.json' && test -f '${SCAFFOLD_080}/.hermes/planning/catalogs/destination-platforms.json' && test -f '${SCAFFOLD_080}/.hermes/planning/mta-rules/rhoai3-canary.yaml' && test -f '${SCAFFOLD_080}/.hermes/planning/decisions.example.yaml' && echo present || echo missing" \
  "present"
check "080 freeze-migration-input selftest passes" \
  "python3 '${SCAFFOLD_SKILLS}/analysis/freeze-migration-input/scripts/freeze-migration-input.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 capture-build-evidence selftest passes" \
  "python3 '${SCAFFOLD_SKILLS}/analysis/capture-build-evidence/scripts/emit-build-receipt.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 inventory-legacy-surface (JDK-model extractor) selftest passes" \
  "python3 '${SCAFFOLD_SKILLS}/analysis/inventory-legacy-surface/scripts/inventory-legacy-surface.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 assemble-evidence-bundle selftest passes" \
  "python3 '${SCAFFOLD_SKILLS}/analysis/assemble-evidence-bundle/scripts/assemble-evidence-bundle.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 scan-with-mta selftest passes (provenance, canary, never --source)" \
  "python3 '${SCAFFOLD_SKILLS}/analysis/scan-with-mta/scripts/scan-with-mta.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 destination rescan analyzes a disposable copy of the candidate (analyzer metadata never reaches the product tree)" \
  "python3 '${SCAFFOLD_SKILLS}/analysis/scan-with-mta/scripts/mta-rescan-destination.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 worklist selftest passes (order, measure, progress rule)" \
  "python3 '${SCAFFOLD_LIB}/planner/worklist.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 card_title selftest passes (M3 display mapping)" \
  "python3 '${SCAFFOLD_LIB}/planner/cards.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 dest-model selftest passes (resolved signatures, real inheritance, exact annotation ranges)" \
  "python3 '${SCAFFOLD_LIB}/planner/dest_model.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 scope-amendment selftest passes (authority before the edit, locus, bounded)" \
  "python3 '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/amend-scope.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 typed repair selftest passes (plan inside the grant, pinned executor, complete-diff inspection, journaled apply)" \
  "python3 '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/typed-repair.test.py' >/dev/null 2>&1 && echo 1 || echo 0" \
  "1"
check "080 diagnosis selftest passes (bounded, reads only, discharges nothing)" \
  "python3 '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/diagnose.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 no profile condition or repository member is read with a regular expression" \
  "if grep -nE '[[:<:]](PROFILE_RE|_declared_members)[[:>:]]' '${SCAFFOLD_LIB}/planner/worklist.py' '${SCAFFOLD_SKILLS}/migration/bootstrap-destination/scripts/bootstrap-destination.py' >/dev/null 2>&1; then echo REGEX; else echo MODEL; fi" \
  "MODEL"
check "080 yamlite parses idFields: [id] without PyYAML" \
  "python3 '${SCAFFOLD_LIB}/planner/yamlite.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "app-migration stamp idFields is yamlite block form" \
  "if grep -qF 'idFields: [id]' '$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-rhdh/templates/app-migration/skeleton/migration.yaml'; then echo FLOW; else echo BLOCK; fi" \
  "BLOCK"
check "080 fix-until-green loop selftest passes (bootstrap → baseline → accept/revert/defer → M4)" \
  "python3 '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/fix-until-green.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 verification handles first admission, detects receipt changes and preserves parity routing" \
  "bash '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/run-verify.test.sh' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 an M4 verdict is consumed: a REFUSE resumes on its parity obligations, a clean acceptance CLOSES the run (issued card cleared, release blockers rewritten from THIS verdict, what remains before ship named)" \
  "python3 '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/resume-after-m4.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 the parity receipt counts how each entry point is covered: by read oracle, by a qualified binding scenario whose replay passed, or not at all" \
  "grep -q -F 'coverage_summary' '${SCAFFOLD_SKILLS}/gates/capture-source-oracles/scripts/compose-parity-receipt.py' && grep -q -F 'coverage_kind' '${SCAFFOLD_SKILLS}/gates/capture-source-oracles/scripts/compose-parity-receipt.py' && grep -q -F '_scenario_coverage_case' '${SCAFFOLD_SKILLS}/gates/capture-source-oracles/scripts/scenario-parity.test.py' && echo 1 || echo 0" \
  "1"
check "080 K4 mint + K3 live selftest passes" \
  "python3 '${SCAFFOLD_KERNEL}/k4_mint_selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 golden decisions.yaml is schema-valid with no missing decision (platform quarkus-rhbq-3.27, max_attempts 3)" \
  "cd '${SCAFFOLD_080}' && python3 -c \"import sys; sys.path.insert(0,'.hermes/lib'); from pathlib import Path; from planner.decisions import load_decisions, missing_decisions, max_attempts; d=load_decisions(Path('.')); print('ok' if d['destination_platform']['id']=='quarkus-rhbq-3.27' and max_attempts(d)==3 and not missing_decisions(d, Path('.')) else 'bad')\"" \
  "ok"
check "080 bootstrap-destination selftest passes (launcher with behavior kept; unmapped starter blocks; Maven settings wiring required; second run preserves the tree)" \
  "python3 '${SCAFFOLD_SKILLS}/migration/bootstrap-destination/scripts/bootstrap-destination.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 decided-repairs selftest passes (ADR-019: bootstrap transformations apply structurally and idempotently, conflicts are typed refusals, review reuse needs the exact reviewed bytes, admission and the baseline see the receipt)" \
  "python3 '${SCAFFOLD_SKILLS}/migration/bootstrap-destination/scripts/decided-repairs.test.py' >/dev/null 2>&1 && echo 1 || echo 0" \
  "1"
check "080 golden decided_repairs manifest is the one decisions.yaml pins, and its reviewed files are the pinned bytes" \
  "cd '${SCAFFOLD_080}' && python3 -c \"import sys,json,hashlib; sys.path.insert(0,'.hermes/lib'); from pathlib import Path; from planner.decisions import load_decisions; s=load_decisions(Path('.'))['decided_repairs']; m=Path(s['manifest']); h=lambda p: hashlib.sha256(Path(p).read_bytes()).hexdigest(); d=json.loads(m.read_text()); ok=h(m)==s['manifest_sha256'] and all(h(t['content'])==t['content_sha256'] for t in d['transformations'] if 'content' in t); print('ok' if ok else 'bad')\"" \
  "ok"
check "080 restore-source-response-shape selftest passes (ADR-019: the CORS adapter renders from the source policy, never widens or echoes rejected requests, leaves Content-Type alone; the media-type adapter is its own obligation)" \
  "python3 '${SCAFFOLD_SKILLS}/migration/restore-source-response-shape/scripts/install-response-adapter.test.py' >/dev/null 2>&1 && echo 1 || echo 0" \
  "1"
check "080 work list never issues a worker obligation under a harness-owned generated test root, and K2 refuses the write (ADR-015/ADR-019)" \
  "grep -c 'harness_owned' '${SCAFFOLD_LIB}/planner/worklist.py' | awk '{print (\$1>=1)?1:0}'" \
  "1"
check "080 advance.py binds acceptance to the issued card and the verified candidate tree" \
  "grep -c -E 'LOOP_NOT_ISSUED|LOOP_CANDIDATE_CHANGED|LOOP_WRONG_CARD' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/advance.py' | awk '{print (\$1>=3)?1:0}'" \
  "1"
check "080 revert restores the index as well as the working tree" \
  "grep -c 'git(root, \"reset\", \"-q\", \"HEAD\"' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/_loop_common.py' || echo 0" \
  "1"
check "080 run-verify.sh records the mvn test exit status and deletes stale surefire reports" \
  "grep -c -E 'surefire-reports\"\$|--test-rc' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/run-verify.sh' | awk '{print (\$1>=2)?1:0}'" \
  "1"
check "080 an empty work list does not close the run: the closing card needs packaging and startup on the same artifact" \
  "grep -q -F 'if not (worklist.get(\"runtime\") or {}).get(\"ready\"):' '${SCAFFOLD_LIB}/planner/cards.py' && grep -q -F 'def runtime_state' '${SCAFFOLD_LIB}/planner/worklist.py' && echo 1 || echo 0" \
  "1"
check "080 a packaging or startup gate that did not run is unknown, never a pass" \
  "cd '${SCAFFOLD_080}' && python3 -c \"import sys; sys.path.insert(0,'.hermes/lib'); from planner.worklist import runtime_state as r; a=r(None,None); b=r({'ran':True,'rc':0,'artifact_sha256':'x'},{'ran':True,'rc':0,'ready':True,'artifact_sha256':'y'}); c=r({'ran':True,'rc':0,'artifact_sha256':'x'},{'ran':True,'rc':0,'ready':True,'artifact_sha256':'x'}); print('%s %s %s' % (a['ready'], b['ready'], c['ready']))\"" \
  "False False True"
check "080 a runtime obligation's cause comes from a closed vocabulary, so an unpredicted failure cannot mint a new one" \
  "cd '${SCAFFOLD_080}' && python3 -c \"import sys; sys.path.insert(0,'.hermes/lib'); from planner.worklist import runtime_cause; print('%s %s %s' % (runtime_cause('No implementation of interface x.Y was found'), runtime_cause('UnableToParseMethodException: Method findAll'), runtime_cause('anything nobody wrote a signature for')))\"" \
  "missing-implementation underivable-query-method unclassified"
check "080 a failure that quotes the offending value locates the one file carrying it, and two files locate nothing" \
  "grep -q -F 'def quoted_literal_locus' '${SCAFFOLD_LIB}/planner/worklist.py' && grep -q -F 'Uniqueness is the whole check' '${SCAFFOLD_LIB}/planner/worklist.py' && echo 1 || echo 0" \
  "1"
check "080 a failure that names the member it could not handle makes that member part of the obligation" \
  "cd '${SCAFFOLD_080}' && python3 -c \"import sys; sys.path.insert(0,'.hermes/lib'); from planner.worklist import runtime_member; print('%s|%s' % (runtime_member(chr(34)+'Method '+chr(39)+'save'+chr(39)+' of repository x.Y'+chr(34)), runtime_member('nothing named here')))\"" \
  "save|"
check "080 an unstated verification mode cannot promote (unknown is not an acceptance pass)" \
  "grep -q -F 'or \"diagnostic\"' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/verify.py' && grep -q -F 'An unstated mode is NOT an acceptance pass' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/verify.py' && echo 1 || echo 0" \
  "1"
check "080 a retained candidate keeps its deletions and must come back as itself" \
  "grep -q -F 'PendingRestoreError' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/_loop_common.py' && grep -q -F '\"deleted\": deleted' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/_loop_common.py' && grep -q -F 'LOOP_PENDING_CANDIDATE_CHANGED' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/restore-pending.py' && echo 1 || echo 0" \
  "1"
check "080 the brief cites the frozen implementation a retirement removed, with its query" \
  "grep -q -F 'def frozen_member_implementations' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/brief.py' && grep -q -F 'rather than writing one' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/brief.py' && echo 1 || echo 0" \
  "1"
check "080 SI-1: a member the source wrote with must still write, and the rule reads the declaration rather than its name" \
  "cd '${SCAFFOLD_080}' && python3 -c \"import sys; sys.path.insert(0,'.hermes/skills/migration/fix-until-green/scripts'); from _loop_common import state_change_violations as v; w={'save','delete'}; q=chr(34); bad=len(v('@org.springframework.data.jpa.repository.Query('+q+'SELECT u FROM User u'+q+')\n void save(User u);', w)[0]); okm=len(v('@Query('+q+'DELETE FROM Pet p'+q+')\n @Modifying\n void delete(Pet p);', w)[0]); rd=len(v('@Query('+q+'SELECT p FROM Pet p'+q+')\n Pet updatedPetById(int id);', w)[0]); unk=len(v('@Query(C.SAVE)\n void save(User u);', w)[1]); print('%d%d%d%d' % (bad, okm, rd, unk))\"" \
  "1001"
check "080 a failing gate cannot discharge an obligation: the candidate is retained, not accepted" \
  "grep -q -F 'not proof it was repaired' '${SCAFFOLD_LIB}/planner/worklist.py' && grep -q -F 'unproven-repair' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/advance.py' && echo 1 || echo 0" \
  "1"
check "080 the brief names the members likely to carry the same cause, so one card is one verification" \
  "grep -q -F 'sibling_note' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/brief.py' && python3 '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/brief.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 acceptance is phase-aware: a gate repair with an unchanged measure is accepted, a regression is not" \
  "cd '${SCAFFOLD_080}' && python3 -c \"import sys; sys.path.insert(0,'.hermes/lib'); from planner.worklist import progress; m={'known':True,'tuple':[0,0,0]}; w={'known':True,'tuple':[0,1,0]}; f={'package':{'ran':True,'rc':1}}; t={'package':{'ran':True,'rc':0}}; print('%s %s %s' % (progress(m,m,set(),set(),gate='package',prev_runtime=f,cur_runtime=t)[0], progress(m,m,set(),set())[0], progress(m,w,set(),set(),gate='package',prev_runtime=f,cur_runtime=t)[0]))\"" \
  "True False False"
check "080 the build profile is a decision: a profile the legacy activated, still gating a source, blocks until decisions.yaml says what happens to it" \
  "grep -q -F 'BUILD_PROFILE_UNDECIDED' '${SCAFFOLD_SKILLS}/migration/bootstrap-destination/scripts/bootstrap-destination.py' && grep -q -F 'def check_build_profiles' '${SCAFFOLD_SKILLS}/migration/bootstrap-destination/scripts/bootstrap-destination.py' && echo 1 || echo 0" \
  "1"
check "080 the effective datasource is a decision: an absent or half-filled block keeps admission INCONCLUSIVE" \
  "cd '${SCAFFOLD_080}' && python3 -c \"import sys,copy; sys.path.insert(0,'.hermes/lib'); from pathlib import Path; from planner.decisions import load_decisions, missing_decisions; d=load_decisions(Path('.')); full=len(missing_decisions(d, Path('.'))); e=copy.deepcopy(d); e.pop('datasource'); h=copy.deepcopy(d); h['datasource']['jdbc_url_env']=''; print('%d %d %d' % (full, len(missing_decisions(e, Path('.'))), len(missing_decisions(h, Path('.')))))\"" \
  "0 1 1"
# Three PROPERTIES, one marker each, counted distinctly -- the previous form
# summed matching lines across an alternation, so two hits on one phrase could
# stand in for a property that had gone missing.
check "080 the destination's rendered datasource is measured against the decision at M2 (unprefixed keys, one matching driver, referenced credentials)" \
  "C='${SCAFFOLD_SKILLS}/migration/bootstrap-destination/scripts/check-datasource-decision.py'; n=0; for p in 'another profile would configure a different database' 'decision drift' 'environment reference'; do grep -q \"\$p\" \"\$C\" && n=\$((n+1)); done; echo \$n" \
  "3"
check "080 bootstrap and its own datasource checker agree on the tree bootstrap wrote (integration, not unit)" \
  "grep -c 'THE CONTRADICTION' '${SCAFFOLD_SKILLS}/migration/bootstrap-destination/scripts/bootstrap-destination.test.py' | awk '{print (\$1>=1)?1:0}'" \
  "1"
check "080 a cleared deferral raises the attempt budget and never deletes the attempts or their cards" \
  "grep -q -F 'def attempt_budget' '${SCAFFOLD_LIB}/planner/budget.py' && grep -q -F 'from planner.budget import attempt_budget' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/_loop_common.py' && grep -q -F 'deferral_clearances' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/operator-step.py' && echo 1 || echo 0" \
  "1"
check "080 the coverage plugin is pinned to a version that can read the pinned toolchain's class files (JaCoCo >= 0.8.11 for Java 21)" \
  "jq -r '.plugin_config[\"org.jacoco:jacoco-maven-plugin\"].version as \$v | if (\$v | split(\".\") | map(tonumber)) >= [0, 8, 11] then \"ok\" else \$v end' '${SCAFFOLD_080}/.hermes/planning/catalogs/compat-mapping.json'" \
  "ok"
check "080 the boot gate binds to the whole packaged application, a free port, the process it started and a datasource that came up (verify-runtime selftest)" \
  "python3 '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/verify-runtime.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 the parity receipt requires the corpus's scenarios, not the result files that happen to exist" \
  "grep -q -F 'never from which result files happen to exist' '${SCAFFOLD_SKILLS}/gates/capture-source-oracles/scripts/compose-parity-receipt.py' && grep -q -F 'required scenario(s) have no result' '${SCAFFOLD_SKILLS}/gates/capture-source-oracles/scripts/compose-parity-receipt.py' && echo 1 || echo 0" \
  "1"
check "080 a replay restores the declared initial state and proves the destination is in it" \
  "grep -q -F 'not in the state the source started from' '${SCAFFOLD_SKILLS}/gates/capture-source-oracles/scripts/compare-scenario-parity.py' && grep -q -F 'could not be restored' '${SCAFFOLD_SKILLS}/gates/capture-source-oracles/scripts/compare-scenario-parity.py' && echo 1 || echo 0" \
  "1"
check "080 the datasource checker reads the selected profile's overrides, and another profile pointing elsewhere is reported" \
  "grep -q -F 'under the %s profile' '${SCAFFOLD_SKILLS}/migration/bootstrap-destination/scripts/check-datasource-decision.py' && grep -q -F 'another profile would configure a different database' '${SCAFFOLD_SKILLS}/migration/bootstrap-destination/scripts/check-datasource-decision.py' && echo 1 || echo 0" \
  "1"

# ---------------------------------------------------------------------------
# Per-run migration resources (Operator 2026-09-22; architect ruling on the
# isolation review of 39792496, ADR-022/ADR-023). Every run's parity database,
# credentials and fixture identities are dedicated to that run and created at
# workspace initiation by trusted platform code. The invariants below are the
# ones that, if they slipped, would put two runs back on one database -- or
# deliver nothing at all -- without anyone noticing.
# ---------------------------------------------------------------------------
APP_MIGRATION_TMPL="$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-rhdh/templates/app-migration"
PIPELINES_BUILD="$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-pipelines/build"
check "080 the golden decisions.yaml names no shared parity database" \
  "grep -c 'petclinic-parity-postgres' '${SCAFFOLD_080}/decisions.yaml' || echo 0" \
  "0"
check "080 the golden datasource.instance stays UNSTAMPED until the run stamps its own" \
  "grep -c '^  instance: UNSTAMPED$' '${SCAFFOLD_080}/decisions.yaml' || echo 0" \
  "1"
check "080 the per-run isolation amendments are recorded as accepted decisions (ADR-022 datasource, ADR-023 fixtures)" \
  "cd '${SCAFFOLD_080}' && python3 -c \"import sys; sys.path.insert(0,'.hermes/lib'); from pathlib import Path; from planner.decisions import accepted_adrs, load_decisions; a=accepted_adrs(load_decisions(Path('.'))); print(sum(1 for x in ('ADR-022','ADR-023') if x in a))\"" \
  "2"
check "080 the ADR-022 amendment states the cost as requests and limits, and what a separate server does not isolate" \
  "cd '${SCAFFOLD_080}' && python3 -c \"import sys; sys.path.insert(0,'.hermes/lib'); from pathlib import Path; from planner.decisions import load_decisions; d=load_decisions(Path('.')); r=[x for x in d['adrs'] if x['id']=='ADR-022'][0]['title']; print(sum(1 for p in ('are REQUESTS','limits are 1 CPU and 512Mi','do NOT isolate shared-node or control-plane') if p in r))\"" \
  "3"
check "080 the M2 datasource checker refuses a decision that names nobody's database" \
  "grep -q -F 'UNSTAMPED' '${SCAFFOLD_SKILLS}/migration/bootstrap-destination/scripts/check-datasource-decision.py' && grep -q -F 'whatever database the namespace happens to hold' '${SCAFFOLD_SKILLS}/migration/bootstrap-destination/scripts/check-datasource-decision.py' && echo 1 || echo 0" \
  "1"
# The four counterexamples the architect demonstrated PASSING the substring
# check: wrong namespace, wrong database, a different host with the expected
# prefix, and the expected name only in a query parameter.
check "080 run_identity selftest passes (the four wrong-target counterexamples are refused by parsing, not matching)" \
  "cd '${SCAFFOLD_080}' && python3 .hermes/lib/planner/run_identity.test.py >/dev/null && echo 1 || echo 0" \
  "1"
check "080 stamp-run-resources selftest passes (verification precedes stamping; a refusal writes nothing)" \
  "python3 '${SCAFFOLD_SKILLS}/migration/bootstrap-destination/scripts/stamp-run-resources.py' --help >/dev/null && python3 '${SCAFFOLD_SKILLS}/migration/bootstrap-destination/scripts/stamp-run-resources.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 run-report compares emitted pins and preserves missing-evidence distinctions" \
  "python3 '${SCAFFOLD_SKILLS}/evaluation/run-report/scripts/run-report.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 completion map keeps every missing oracle open and flags the v29 false green (M-1/M-6)" \
  "python3 '${SCAFFOLD_LIB}/completion_map.test.py' >/dev/null 2>&1 && echo 1 || echo 0" \
  "1"
check "080 trusted platform code renders a run's resources, not the destination repository" \
  "test -f '${PIPELINES_BUILD}/task-provision-migration-run.yaml' && test -f '${PIPELINES_BUILD}/pipeline-provision-migration-run.yaml' && ! test -e '${APP_MIGRATION_TMPL}/skeleton/k8s-run' && ! test -e '${PIPELINES_BUILD}/appproject-migration-run.yaml' && echo 1 || echo 0" \
  "1"
check "080 no Argo CD Application is created over a self-service destination repository" \
  "f=\$(py_function '$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-pipelines/gitlab/reconcile.py' provision_migration); grep -qF \"resource('PipelineRun'\" <<<\"\$f\" && ! grep -qF \"'Application'\" <<<\"\$f\" && echo platform || echo open" \
  "platform"
check "080 the provisioner identity cannot be selected by a workload in the workspace namespace" \
  "uncommented '$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-devspaces/migration-run-resources-rbac.yaml' | awk '/kind: ServiceAccount/ { f = 1 } f && match(\$0, /namespace: [^[:space:]]+/) { print substr(\$0, RSTART + 11, RLENGTH - 11); found = 1; exit } END { if (!found) print \"absent\" }'" \
  "app-platform-build"
check "080 provisioning is bound to the scaffolding event, and a retired run cannot be resurrected" \
  "f=\$(py_function '$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-pipelines/gitlab/reconcile.py' provision_migration); k=\$(uncommented '${PIPELINES_BUILD}/task-provision-migration-run.yaml'); n=0; for x in \"'provision-' + name\" '(AlreadyExists)'; do grep -qF \"\$x\" <<<\"\$f\" && n=\$((n + 1)); done; for x in phase=retired 'was retired' 'was provisioned from'; do grep -qF \"\$x\" <<<\"\$k\" && n=\$((n + 1)); done; echo \$n" \
  "5"
check "080 the run's secrets are watched and mounted, so DWO's cache can see them at all" \
  "uncommented '${PIPELINES_BUILD}/task-provision-migration-run.yaml' | grep -oF 'controller.devfile.io/watch-secret: \"true\"' | wc -l | tr -d ' '" \
  "2"
# Three automounted objects bind this workspace: the two per-run Secrets and,
# since v13, the run-control ConfigMap.
check "080 the run's secrets and its run-control record bind THIS workspace name, all three" \
  "sed 's/^[[:space:]]*#.*//' '${PIPELINES_BUILD}/task-provision-migration-run.yaml' | grep -c -F 'mount-to-devworkspace-include: \"\${RUN}\"' || echo 0" \
  "3"
# A comma or a star in the include is the collision the architect demonstrated:
# demo-v10-retry matched demo-v10's pattern and received its database.
check "080 no include pattern carries a suffix wildcard or a second pattern" \
  "sed 's/^[[:space:]]*#.*//' '${PIPELINES_BUILD}/task-provision-migration-run.yaml' | grep 'mount-to-devworkspace-include:' | grep -cE '[*,]' || true" \
  "0"
check "080 the platform fixture source is data, never a namespace-wide mount" \
  "uncommented '$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-devspaces/migration-fixture-credentials-source.yaml' | grep -qF mount-to-devworkspace && echo mounted || echo source-only" \
  "source-only"
# The architect drove reset-parity-db.sh with an UNSTAMPED destination and with
# another run's URL and reached the Java reset runner. The same ownership
# check now guards every boundary that connects.
check "080 reset, fixture mutation, destination startup and parity all establish ownership before connecting" \
  "grep -lF run_identity '${SCAFFOLD_SKILLS}/gates/capture-source-oracles/scripts/reset-parity-db.sh' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/verify-runtime.py' '${SCAFFOLD_SKILLS}/paved-road/paved-road-m4/scripts/run-parity.py' '${SCAFFOLD_SKILLS}/migration/bootstrap-destination/scripts/check-datasource-decision.py' | wc -l | tr -d ' '" \
  "4"
check "080 the reset refuses a wrong or missing target before a driver is found or a credential read" \
  "R='${SCAFFOLD_SKILLS}/gates/capture-source-oracles/scripts/reset-parity-db.sh'; O=\$(grep -n 'python3 -m planner.run_identity' \"\$R\" | head -1 | cut -d: -f1); C=\$(grep -n 'URL_ENV:-' \"\$R\" | head -1 | cut -d: -f1); D=\$(grep -n 'javac -d' \"\$R\" | head -1 | cut -d: -f1); { [ -n \"\$O\" ] && [ \"\$O\" -lt \"\$C\" ] && [ \"\$O\" -lt \"\$D\" ] && echo before || echo after; }" \
  "before"
check "080 a refused ownership verdict stops the workspace autostart instead of warning" \
  "t=\$(uncommented '${APP_MIGRATION_TMPL}/skeleton/devfile.yaml'); grep -qF RUN_RESOURCES_RC <<<\"\$t\" && grep -qF 'autostart is NOT started' <<<\"\$t\" && echo blocks || echo warns" \
  "blocks"
check "080 the skeleton devfile names this run's own secrets and verifies the injection at start" \
  "t=\$(uncommented '${APP_MIGRATION_TMPL}/skeleton/devfile.yaml'); n=0; for x in PARITY_DB_SECRET PARITY_CREDENTIALS_SECRET stamp-run-resources.py; do grep -qF \"\$x\" <<<\"\$t\" && n=\$((n + 1)); done; echo \$n" \
  "3"
check "080 the skeleton migration.yaml is the one producer of the run's resource assignment" \
  "t=\$(uncommented '${APP_MIGRATION_TMPL}/skeleton/migration.yaml'); n=0; for x in parity_database: fixture_credentials: workspace_secret: jdbc_url_env: receipt_env:; do grep -qF \"\$x\" <<<\"\$t\" && n=\$((n + 1)); done; echo \$n" \
  "5"
check "080 the app-migration template marks its repos for the migration-run dispatcher" \
  "uncommented '${APP_MIGRATION_TMPL}/template.yaml' | grep -oF rhoai3-migration-run | wc -l | tr -d ' '" \
  "1"
check "080 the shared namespace-wide parity stack is retired, and nothing reintroduces it" \
  "find '$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-devspaces' -maxdepth 1 \\( -name 'migration-parity-database.yaml' -o -name 'petclinic-parity-credentials.yaml' \\) 2>/dev/null | wc -l | tr -d ' '" \
  "0"
check "080 a run credential is never mounted namespace-wide: only the run's own provisioner publishes one" \
  "for f in \$(grep -rl -E 'PETCLINIC_(DB|ADMIN|INVALID)' '$REPO_ROOT/gitops/stages/070-advanced-app-platform/070-devspaces/' 2>/dev/null); do sed 's/#.*//' \"\$f\" | grep -q 'mount-to-devworkspace' && echo \"\$f\" || :; done | wc -l | tr -d ' '" \
  "0"
check "080 an authenticated replay keeps its password reference through the request digest" \
  "cd '${SCAFFOLD_080}' && python3 -c \"import sys,tempfile; sys.path.insert(0,'.hermes/skills/gates/capture-source-oracles/scripts'); from pathlib import Path; from _scenarios import request_of; r=request_of(Path(tempfile.mkdtemp()), {'id':'x','entry_point':'e','method':'GET','path':'/a','body_absent':True,'identity':{'kind':'basic','user_env':'U','password_env':'P'}}); print('ok' if r['identity'].get('password_env')=='P' else 'dropped')\"" \
  "ok"
check "080 a read capture works before admission (M1 precedes M2) and binds to the frozen source" \
  "grep -q -F 'BEFORE the plan is' '${SCAFFOLD_SKILLS}/gates/capture-source-oracles/scripts/capture-source-oracles.py' && grep -q -F 'evidence_bundle_sha256' '${SCAFFOLD_SKILLS}/gates/capture-source-oracles/scripts/capture-source-oracles.py' && echo 1 || echo 0" \
  "1"
check "080 a recorded write is replayed with its body, headers and effects; a 204 that deleted nothing FAILs (scenario-parity selftest)" \
  "python3 '${SCAFFOLD_SKILLS}/gates/capture-source-oracles/scripts/scenario-parity.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 the body-less write comparison is gone: a non-idempotent oracle is routed to the scenario corpus" \
  "grep -q -F 'not a replay' '${SCAFFOLD_SKILLS}/gates/capture-source-oracles/scripts/compare-runtime-parity.py' && ! grep -q -F -- '--request-file' '${SCAFFOLD_SKILLS}/gates/capture-source-oracles/scripts/capture-source-oracles.py' && echo 1 || echo 0" \
  "1"
check "080 starting the source and capturing scenarios is an M1 producer step, not an Operator rescue" \
  "jq -r '[.steps[].id] as \$ids | if (\$ids | index(\"capture-source-scenarios\")) > (\$ids | index(\"assemble-evidence-bundle\")) then \"ok\" else \"bad\" end' '${SCAFFOLD_SKILLS}/paved-road/paved-road-m1/steps.json'" \
  "ok"
check "080 the scenario corpus ships an example a run can start from, and it obeys its own rules" \
  "cd '${SCAFFOLD_080}' && python3 -c \"import json,sys; sys.path.insert(0,'.hermes/skills/gates/capture-source-oracles/scripts'); d=json.load(open('.hermes/planning/scenarios.example.json')); sc=d['scenarios'][0]; ok=d['schema']=='rhoai3.scenario-corpus/v1' and d.get('approved_by') and sc.get('body_file') and sc.get('effects') and '{' not in sc['path']; print('ok' if ok else 'bad')\"" \
  "ok"
check "080 a scenario carries a concrete request: a route pattern, a missing body statement, or a write with no effect refuses" \
  "grep -q -F 'never a route pattern' '${SCAFFOLD_SKILLS}/gates/capture-source-oracles/scripts/_scenarios.py' && grep -q -F 'body_absent: true' '${SCAFFOLD_SKILLS}/gates/capture-source-oracles/scripts/_scenarios.py' && grep -q -F 'at least one effect' '${SCAFFOLD_SKILLS}/gates/capture-source-oracles/scripts/compare-scenario-parity.py' && echo 1 || echo 0" \
  "1"
check "080 a templated entry-point path is not captured as an oracle without a real value (capture-source-oracles selftest)" \
  "python3 '${SCAFFOLD_SKILLS}/gates/capture-source-oracles/scripts/capture-source-oracles.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 the generator writes where the mojo registers a compile source root (openapi-generator configOptions.sourceFolder)" \
  "jq -r '.plugin_config[\"org.openapitools:openapi-generator-maven-plugin\"].configOptions.sourceFolder' '${SCAFFOLD_080}/.hermes/planning/catalogs/compat-mapping.json'" \
  "src/main/java"
check "080 the mapping restores the assertion library the Spring test starter provided, in test scope, with its group id" \
  "jq -r 'if (.starters[\"org.springframework.boot:spring-boot-starter-test\"] | index(\"assertj-core\")) != null and .starter_group_ids[\"assertj-core\"] == \"org.assertj\" and (.test_scoped.artifacts | index(\"assertj-core\")) != null then \"ok\" else \"bad\" end' '${SCAFFOLD_080}/.hermes/planning/catalogs/compat-mapping.json'" \
  "ok"
check "080 the Jakarta namespace rename covers test sources (a test that cannot compile makes the measure unknown)" \
  "grep -q -F 'src/main/java,src/test/java' '${SCAFFOLD_SKILLS}/migration/bootstrap-destination/scripts/bootstrap-destination.py' && echo 1 || echo 0" \
  "1"
check "080 a late catalog row reaches an already bootstrapped tree from the rows that tree consumed (--reapply-catalog), never from the whole catalog" \
  "grep -c -E 'def reapply_catalog|def late_row_artifacts' '${SCAFFOLD_SKILLS}/migration/bootstrap-destination/scripts/bootstrap-destination.py' | awk '{print (\$1>=2)?1:0}'" \
  "1"
check "080 a deferral is lifted only by a measured tree and only where one is open (operator-step --clear-deferred)" \
  "grep -c -E 'clear-deferred|is not\" if len\\(unknown\\)' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/operator-step.py' | awk '{print (\$1>=2)?1:0}'" \
  "1"
check "080 an operator step that changes a test source refuses without an ADR and an independent reviewer" \
  "python3 '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/operator-step.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 M4 test evidence refuses skipped, empty and foreign reports (surefire selftest)" \
  "python3 '${SCAFFOLD_SKILLS}/gates/check-release-readiness/scripts/assert-surefire-results.test.py' >/dev/null 2>&1 && echo 1 || echo 0" \
  "1"
check "080 M4 accounts for every ADR-retired source, and a hidden coverage gap refuses (coverage-account selftest)" \
  "python3 '${SCAFFOLD_SKILLS}/gates/compose-m4-verdict/scripts/coverage-account.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 the M4 verdict must carry the coverage account (schema + reference in sync)" \
  "python3 '${SCAFFOLD_SKILLS}/gates/compose-m4-verdict/scripts/assert-m4-verdict-schema-sync.py' >/dev/null && grep -q -F 'coverage_account' '${SCAFFOLD_SKILLS}/gates/compose-m4-verdict/scripts/assert-m4-verdict-schema.py' && echo 1 || echo 0" \
  "1"
check "080 paved-road-m4 KEEPs the coverage account beside the verdict" \
  "jq -r '[.steps[] | select(.producer)][0].keep | if index(\"evidence/verdicts/coverage-account.json\") != null then \"ok\" else \"bad\" end' '${SCAFFOLD_SKILLS}/paved-road/paved-road-m4/steps.json'" \
  "ok"
check "080 golden decisions.yaml has no proposed ADR left open (a proposal is not a decision)" \
  "python3 -c \"import sys; sys.path.insert(0,'${SCAFFOLD_080}/.hermes/lib'); from pathlib import Path; from planner.decisions import load_decisions; d=load_decisions(Path('${SCAFFOLD_080}')); print(len([a for a in d['adrs'] if a.get('status')!='accepted']))\"" \
  "0"
check "080 bootstrap retires only ADR-listed sources (decisions.yaml retired_sources) and blocks on a stale path" \
  "grep -c -E 'RETIRED_SOURCE_MISSING|retired_sources' '${SCAFFOLD_SKILLS}/migration/bootstrap-destination/scripts/bootstrap-destination.py' | awk '{print (\$1>=2)?1:0}'" \
  "1"
check "080 bootstrap carries legacy-resolved versions for dependencies the pinned BOM does not manage (measured, never guessed)" \
  "grep -c -E 'VERSION_UNMANAGED|BOM_PROBE_MISSING|pom.pin-legacy-version' '${SCAFFOLD_SKILLS}/migration/bootstrap-destination/scripts/bootstrap-destination.py' | awk '{print (\$1>=3)?1:0}'" \
  "1"
check "080 warm-ups run the measured Maven goals online once (go-offline alone leaves compile/test artifacts unfetched)" \
  "grep -q -F -- '-Dmaven.test.failure.ignore=true test' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/run-verify.sh' && grep -q -F 'dependency:go-offline && mvn -q -B compile' '${SCAFFOLD_SKILLS}/analysis/capture-build-evidence/scripts/capture-build-evidence.sh' && grep -q -F '&& mvn -q -B dependency:build-classpath' '${SCAFFOLD_SKILLS}/analysis/capture-build-evidence/scripts/capture-build-evidence.sh' && echo 1 || echo 0" \
  "1"
check "080 run-verify.sh warms the destination up online once, then measures offline, and records the warm-up outcome" \
  "grep -c -E 'dependency:go-offline|\"warmup\": \{\"ran\"' '${SCAFFOLD_SKILLS}/migration/fix-until-green/scripts/run-verify.sh' | awk '{print (\$1>=2)?1:0}'" \
  "1"
check "080 skipped destination MTA rescan is never treated as a known incident slot" \
  "! grep -q 'destination-rescan-reused' '${SCAFFOLD_LIB}/planner/worklist.py' && echo 1 || echo 0" \
  "1"
check "080 work list marks source obligations unknown unless the MTA producer status is ok (an absent scan is not zero incidents)" \
  "grep -c 'incidents_known = mta_status == \"ok\"' '${SCAFFOLD_LIB}/planner/worklist.py' || echo 0" \
  "1"
check "080 obligation identity is line-free (rule, file, variables, message)" \
  "grep -c 'line-free identity' '${SCAFFOLD_LIB}/planner/worklist.py' || echo 0" \
  "1"
check "080 K4 mint registers control cards instead of treating every HERMES_KANBAN_TASK as M2" \
  "grep -c 'def register_control_cards' '${SCAFFOLD_KERNEL}/k4_mint.py' || echo 0" \
  "1"
check "080 AGENTS.md follows the Spring-compatibility path (no native-only rule)" \
  "grep -c 'Native Quarkus only' '${SCAFFOLD_080}/AGENTS.md' || echo 0" \
  "0"
check "080 compat mapping catalog present (bootstrap contract)" \
  "test -f '${SCAFFOLD_080}/.hermes/planning/catalogs/compat-mapping.json' && echo present || echo missing" \
  "present"
check "080 no ownership map / DAG / probe / bytecode machinery remains" \
  "{ grep -rIl -E 'planner\\.dag|planner\\.ownership|planner\\.ledger|increment-dag\\.json|probe-spring-bindings|enrich-legacy-bytecode' '${SCAFFOLD_080}/.hermes/lib' '${SCAFFOLD_080}/.hermes/kernel' '${SCAFFOLD_080}/.hermes/skills' --exclude-dir=__pycache__ --exclude-dir=fixtures || true; } | wc -l | tr -d ' '" \
  "0"
check "080 admit-migration-plan selftest passes" \
  "python3 '${SCAFFOLD_SKILLS}/planning/admit-migration-plan/scripts/admit-migration-plan.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 capture-source-oracles selftest passes" \
  "python3 '${SCAFFOLD_SKILLS}/gates/capture-source-oracles/scripts/capture-source-oracles.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 K4 producer-skill bar selftest passes" \
  "python3 '${SCAFFOLD_KERNEL}/k4_producers.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 mode-aware M4 parity selftest passes" \
  "python3 '${SCAFFOLD_080}/.hermes/lib/m4_parity.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 compose-m4-verdict selftest passes" \
  "python3 '${SCAFFOLD_080}/.hermes/skills/gates/compose-m4-verdict/scripts/compose-m4-verdict.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 assert-pinned-gates-ran receipts selftest passes" \
  "python3 '${SCAFFOLD_080}/.hermes/skills/gates/assert-pinned-gates-ran/scripts/assert-pinned-gates-ran.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 run-m4-pre-verdict selftest passes" \
  "bash '${SCAFFOLD_080}/.hermes/skills/gates/check-release-readiness/scripts/run-m4-pre-verdict.test.sh' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 cold-cache maven-settings skill text selftest passes" \
  "python3 '${SCAFFOLD_080}/.hermes/skills/migration/reference-rh-quarkus-pom/scripts/reference-rh-quarkus-pom.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 JAX-RS DefaultValue mapping selftest passes" \
  "python3 '${SCAFFOLD_080}/.hermes/skills/migration/spring-to-quarkus-patterns/scripts/rest-annotations-defaultvalue.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 check-external-dirs selftest passes" \
  "python3 '${SCRIPT_DIR}/scaffold-repo/quarkus-migration-scaffold/.hermes/lib/check-external-dirs.test.py' >/dev/null && echo 1 || echo 0" \
  "1"
check "080 init-spec-workspace skill is removed" \
  "test ! -d '${SCAFFOLD_080}/.hermes/skills/sdd/init-spec-workspace' && echo absent || echo present" \
  "absent"
check "080 destfile does not call Spec Kit init-workspace.sh" \
  "grep -E 'init-workspace.sh|init-spec-workspace' '${REPO_ROOT}/gitops/stages/070-advanced-app-platform/070-rhdh/templates/app-migration/skeleton/devfile.yaml' '${SCAFFOLD_080}/devfile.yaml' >/dev/null && echo present || echo absent" \
  "absent"
check "080 dest-init does not install specify PATH shim" \
  "grep -c 'specify-from-project.sh' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 dest-init does not run specify init" \
  "grep -c 'dest-init specify init' '${GITOPS_INIT}' || echo 0" \
  "0"
check "080 GitOps dest-init calls dispatch-phase autostart-migration.sh" \
  "grep -c 'dispatch-phase/scripts/autostart-migration.sh' '${GITOPS_INIT}' || true" \
  "1"
check "080 live dest-init calls dispatch-phase autostart-migration.sh" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'dispatch-phase/scripts/autostart-migration.sh' || true" \
  "1"
check "080 live dest-init does not ship init-spec-workspace" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'init-spec-workspace' || true" \
  "0"
check "080 live dest-init does not run specify init" \
  "oc get cm devspace-ai-tools-init -n wksp-ai-developer -o jsonpath='{.data.init-ai-tools\.sh}' | grep -c 'dest-init specify init' || true" \
  "0"
check "080 pins.json has no spec_kit pin" \
  "jq -r 'if (.pins // {} | has(\"spec_kit\")) then \"present\" else \"absent\" end' '${SCAFFOLD_080}/.hermes/pins.json'" \
  "absent"
check "080 inventory SKILL runs the JDK compiler-API extractor (no third-party dependency, no regex)" \
  "grep -c 'run-jdk-model-extract.sh' '${SCAFFOLD_SKILLS}/analysis/inventory-legacy-surface/SKILL.md' || echo 0" \
  "2"
check "080 no Spoon, JavaParser, JDT, or regex extractor in the scaffold" \
  "{ grep -rIl -E 'import spoon|spoon-core|com.github.javaparser|org.eclipse.jdt|oracle-regex' '${SCAFFOLD_080}/.hermes' --exclude-dir=__pycache__ || true; } | wc -l | tr -d ' '" \
  "0"
check "080 M1 paved road freezes the original source first (derive-legacy-boot3 never first)" \
  "jq -r '.steps[0] | .skill // .native // .kernel' '${SCAFFOLD_SKILLS}/paved-road/paved-road-m1/steps.json'" \
  "freeze-migration-input"
check "080 K4 mints one card per step and M4 VERIFY only on an empty list" \
  "grep -c 'CLOSE_ID = \"M4_VERIFY\"' '${SCAFFOLD_LIB}/planner/cards.py' || echo 0" \
  "1"
check "080 commit-destination-tree skill present" \
  "test -f '${SCAFFOLD_080}/.hermes/skills/migration/commit-destination-tree/SKILL.md' && echo present || echo missing" \
  "present"
check "080 commit-destination-tree selftest passes" \
  "python3 '${SCAFFOLD_080}/.hermes/skills/migration/commit-destination-tree/scripts/commit-destination-tree-selftest.py' >/dev/null && echo 1 || echo 0" \
  "1"

echo ""
validation_summary
