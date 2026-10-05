#!/usr/bin/env bash
# Native metrics checks and one synthetic trace roundtrip; no workloads created.
# Actual persona sessions and dashboard UI acceptance remain separate.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT_DIR/scripts/shared/lib.sh"
load_env
check_oc_logged_in
python3 - <<'PY'
import base64, json, math, socket, ssl, subprocess, time, urllib.error, urllib.parse, urllib.request, uuid
processes = []
context = ssl._create_unverified_context()  # Repository demo certificate policy.
def need(value, message):
    if not value: raise RuntimeError(message)
def oc(*args):
    result = subprocess.run(['oc', '--request-timeout=20s', *args], capture_output=True, text=True)
    need(result.returncode == 0, 'cluster read failed: ' + ' '.join(args[:3]))
    return result.stdout.strip()
def get(kind, name=None, namespace=None):
    args = ['get', kind] + ([name] if name else []) + (['-n', namespace] if namespace else [])
    return json.loads(oc(*args, '-o', 'json'))
def http(url, body=None, headers=None):
    request = urllib.request.Request(url, data=body, headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json', **(headers or {})})
    with urllib.request.urlopen(request, context=context, timeout=20) as response: return json.load(response)
def forward(service, namespace, port):
    need(any(p['port'] == port for p in get('service', service, namespace)['spec']['ports']), 'native service port is absent')
    with socket.socket() as sock: sock.bind(('127.0.0.1', 0)); local = sock.getsockname()[1]
    process = subprocess.Popen(['oc', '-n', namespace, 'port-forward', 'service/' + service, f'{local}:{port}', '--address=127.0.0.1'], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    processes.append(process)
    for _ in range(50):
        need(process.poll() is None, 'native service port-forward exited')
        try:
            with socket.create_connection(('127.0.0.1', local), timeout=.2): return local
        except OSError: time.sleep(.1)
    raise RuntimeError('native service port-forward did not become ready')
try:
    token = oc('whoami', '-t')  # Memory only; never emitted or passed as a process argument.
    dsci = get('dscinitialization', 'default-dsci')
    need(dsci.get('status', {}).get('phase') == 'Ready' and any(c.get('type') == 'Ready' and c.get('status') == 'True' for c in dsci.get('status', {}).get('conditions', [])), 'DSCI phase and Ready condition disagree or are not ready')
    namespace = dsci['spec']['monitoring']['namespace']
    monitors = get('monitorings.services.platform.opendatahub.io')['items']
    need(len(monitors) == 1, 'expected exactly one native Monitoring resource')
    monitor = monitors[0]
    need(monitor.get('status', {}).get('phase') == 'Ready' and monitor['status'].get('observedGeneration') == monitor['metadata']['generation'] and any(c.get('type') == 'Ready' and c.get('status') == 'True' for c in monitor['status'].get('conditions', [])), 'Monitoring phase, Ready condition or current generation is not ready')
    # Native namespace proxy requires the namespace query parameter for its SAR and label filter.
    port = forward('data-science-prometheus-namespace-proxy', namespace, 8443)
    query = urllib.parse.urlencode({'query': 'up == 1 and (time() - timestamp(up) >= 0) and (time() - timestamp(up) <= 120)', 'namespace': namespace})
    result = http(f'https://127.0.0.1:{port}/api/v1/query?{query}')
    samples = result.get('data', {}).get('result', [])
    now = time.time()
    need(result.get('status') == 'success' and any(s.get('metric', {}).get('namespace') == namespace and math.isfinite(float(s['value'][1])) and float(s['value'][1]) == 1 and 0 <= now - float(s['value'][0]) <= 120 for s in samples), 'native namespace metrics query has no recent healthy target')
    print('[PASS] Authenticated native metrics query returned samples')
    collector = get('opentelemetrycollector', 'data-science-collector', namespace)
    config = collector['spec']['config']
    need(isinstance(config, dict), 'collector configuration is not the native structured API')
    need('http' in config['receivers']['otlp']['protocols'] and 'otlp' in config['service']['pipelines']['traces']['receivers'], 'collector OTLP/HTTP trace receiver is absent')
    collector_workload = get('statefulset', 'data-science-collector-collector', namespace)
    service_account = collector_workload['spec']['template']['spec']['serviceAccountName']
    # Tempo authorizes a virtual resource, which oc can-i can mis-map via discovery.
    # SubjectAccessReview is nonpersistent and checks the exact gateway attributes.
    review = {'apiVersion': 'authorization.k8s.io/v1', 'kind': 'SubjectAccessReview', 'spec': {'user': 'system:serviceaccount:' + namespace + ':' + service_account, 'resourceAttributes': {'group': 'tempo.grafana.com', 'resource': namespace, 'name': 'traces', 'verb': 'create'}}}
    permission = subprocess.run(['oc', '--request-timeout=20s', 'create', '--raw', '/apis/authorization.k8s.io/v1/subjectaccessreviews', '-f', '-'], input=json.dumps(review), capture_output=True, text=True)
    need(permission.returncode == 0 and json.loads(permission.stdout).get('status', {}).get('allowed') is True, 'collector service account cannot write the native Tempo tenant')
    port = forward('data-science-collector-collector', namespace, 4318)
    trace_id, span_id, start = uuid.uuid4().hex, uuid.uuid4().hex[:16], time.time_ns()
    print('[INFO] Synthetic trace ID ' + trace_id, flush=True)
    payload = {'resourceSpans': [{'resource': {'attributes': [{'key': 'service.name', 'value': {'stringValue': 'foundation-validation'}}]}, 'scopeSpans': [{'scope': {'name': 'foundation-validation'}, 'spans': [{'traceId': trace_id, 'spanId': span_id, 'name': 'foundation-roundtrip', 'kind': 1, 'startTimeUnixNano': str(start), 'endTimeUnixNano': str(start + 1000000)}]}]}]}
    result = http(f'http://127.0.0.1:{port}/v1/traces', json.dumps(payload).encode(), {'Content-Type': 'application/json'})
    need(not result.get('partialSuccess', {}).get('rejectedSpans', 0), 'collector rejected the synthetic span')
    datasource = get('persesdatasource', 'tempo-datasource', namespace)
    endpoint = urllib.parse.urlsplit(datasource['spec']['config']['plugin']['spec']['proxy']['spec']['url'])
    need(endpoint.scheme == 'https' and endpoint.hostname, 'native Tempo datasource endpoint is absent')
    port = forward(endpoint.hostname.split('.')[0], namespace, endpoint.port or 443)
    path = endpoint.path.rstrip('/') + '/api/traces/' + trace_id
    deadline = time.monotonic() + 90
    while True:
        try:
            result = http(f'https://127.0.0.1:{port}{path}', headers={'X-Scope-OrgID': namespace})
            spans = [s for batch in result.get('batches', result.get('resourceSpans', [])) for scope in batch.get('scopeSpans', batch.get('instrumentationLibrarySpans', [])) for s in scope.get('spans', [])]
            encoded_id = base64.b64encode(bytes.fromhex(trace_id)).decode()
            need(any(s.get('traceId', '').lower() == trace_id or s.get('traceId') == encoded_id for s in spans), 'Tempo response lacks the submitted trace ID')
            break
        except urllib.error.HTTPError as error:
            if error.code != 404 or time.monotonic() >= deadline: raise RuntimeError('Tempo lookup failed with HTTP ' + str(error.code)) from None
            time.sleep(3)
    print('[PASS] One synthetic trace traversed the native collector and was retrieved by its exact ID')
    print('Scope: administrator data-plane probes; actual persona and browser UI acceptance remain separate.')
except Exception as error:
    # Responses, URLs, tokens and subprocess stderr must never leak through error output.
    print('[FAIL] Foundation services: ' + (str(error) if isinstance(error, RuntimeError) else type(error).__name__))
    raise SystemExit(1)
finally:
    for process in processes:
        process.terminate()
        try: process.wait(timeout=3)
        except subprocess.TimeoutExpired: process.kill(); process.wait()
PY
