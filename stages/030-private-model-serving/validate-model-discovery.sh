#!/usr/bin/env bash
# Native model discovery read-only checks; no records or workloads created.
# Actual persona sessions and dashboard UI acceptance remain separate.
set -euo pipefail
ROOT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
source "$ROOT_DIR/scripts/shared/lib.sh"
REPO_ROOT="${RHOAI_ENV_ROOT:-$ROOT_DIR}"
load_env
check_oc_logged_in
python3 - <<'PY'
from http.client import HTTPSConnection
import json, socket, ssl, subprocess, time, urllib.request, urllib.parse
processes = []
context = ssl.create_default_context()  # Verify native ingress certificates.
class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise RuntimeError('Authenticated registry redirect refused')
opener = urllib.request.build_opener(NoRedirect(), urllib.request.HTTPSHandler(context=context))
def need(value, message):
    if not value: raise RuntimeError(message)
def oc(*args):
    result = subprocess.run(['oc', '--request-timeout=20s', *args], capture_output=True, text=True)
    need(result.returncode == 0, 'cluster read failed: ' + ' '.join(args[:3]))
    return result.stdout.strip()
def get(kind, name=None, namespace=None):
    args = ['get', kind] + ([name] if name else []) + (['-n', namespace] if namespace else [])
    return json.loads(oc(*args, '-o', 'json'))
def fresh(obj):
    status, spec = obj.get('status', {}), obj['spec']
    need(status.get('observedGeneration') == obj['metadata']['generation'], 'workload generation is stale')
    need(status.get('readyReplicas', 0) >= spec.get('replicas', 1) > 0 and status.get('updatedReplicas', 0) >= spec.get('replicas', 1), 'workload replicas are not current and ready')
def http(url, body=None, headers=None):
    request = urllib.request.Request(url, data=body, headers={'Authorization': 'Bearer ' + token, 'Accept': 'application/json', **(headers or {})})
    with opener.open(request, timeout=20) as response: return json.load(response)
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
    token = oc('whoami', '-t')  # Memory only; never emitted.
    regns = 'rhoai-model-registries'
    registry = get('modelregistries.modelregistry.opendatahub.io', 'demo-registry', regns)
    conditions = {c['type']: c.get('status') for c in registry.get('status', {}).get('conditions', [])}
    need(all(conditions.get(t) == 'True' for t in ['Available', 'KubeRBACProxyAvailable']), 'ModelRegistry native availability conditions are absent or false')
    uid = registry['metadata']['uid']
    def owned(obj): return any(o.get('uid') == uid and o.get('controller') is True for o in obj['metadata'].get('ownerReferences', []))
    workloads = [d for d in get('deployments', namespace=regns)['items'] if owned(d)]
    databases = [d for d in workloads if any('postgresql' in c.get('image', '') for c in d['spec']['template']['spec']['containers'])]
    apis = [d for d in workloads if d not in databases]
    need(len(apis) == 1, 'generated registry API deployment is not uniquely discoverable')
    fresh(apis[0])
    need(len(databases) == 1, 'generated registry PostgreSQL deployment is not uniquely discoverable')
    fresh(databases[0])
    claims = [v['persistentVolumeClaim']['claimName'] for v in databases[0]['spec']['template']['spec'].get('volumes', []) if 'persistentVolumeClaim' in v]
    need(claims, 'registry database has no persistent claim')
    for claim in claims: need(get('pvc', claim, regns).get('status', {}).get('phase') == 'Bound', 'registry database PVC is not Bound')
    routes = [r for r in get('routes', namespace=regns)['items'] if owned(r)]
    need(len(routes) == 1, 'registry authenticated route is not uniquely discoverable')
    result = http('https://' + routes[0]['spec']['host'] + '/api/model_registry/v1alpha3/registered_models')
    need(isinstance(result.get('items'), list), 'registry authenticated list API returned no collection')
    print('[PASS] Registry current generation, PostgreSQL readiness, Bound storage and authenticated list API')
    component = get('modelregistries.components.platform.opendatahub.io', 'default-modelregistry')
    need(component.get('status', {}).get('phase') == 'Ready', 'native catalog component is not Ready')
    need(isinstance(component['metadata'].get('generation'), int) and component.get('status', {}).get('observedGeneration') == component['metadata']['generation'], 'native catalog component generation is stale')
    component_uid = component['metadata']['uid']
    catalogs = [d for d in get('deployments', namespace=regns)['items'] if any(o.get('uid') == component_uid for o in d['metadata'].get('ownerReferences', []))]
    need(any(d['metadata']['name'] == 'model-catalog' for d in catalogs) and any(d['metadata']['name'] == 'model-catalog-postgres' for d in catalogs), 'native catalog API/database workloads are absent')
    for workload in catalogs: fresh(workload)
    dashboard = get('odhdashboardconfig', 'odh-dashboard-config', 'redhat-ods-applications')
    flags = dashboard['spec']['dashboardConfig']
    need(flags.get('disableModelRegistry') is not True and flags.get('disableModelCatalog') is not True and flags.get('agentsCatalog') is True, 'model discovery dashboard navigation is not enabled')
    need(flags.get('toolCalling') is True and flags.get('mcpCatalog') is True and flags.get('mcpRegistry') is True, 'tool and MCP catalog/registry dashboard configuration is not enabled')
    port = forward('odh-dashboard-model-registry-ui', 'redhat-ods-applications', 8043)
    ca = get('configmap', 'service-ca', 'openshift-config-managed')['data']['ca-bundle.crt']
    service_context = ssl.create_default_context(cadata=ca)
    hostname = 'odh-dashboard-model-registry-ui.redhat-ods-applications.svc'
    def catalog_page(catalog, query):
        connection = HTTPSConnection(hostname, timeout=20, context=service_context)
        connection.connect = lambda c=connection: setattr(c, 'sock', service_context.wrap_socket(socket.create_connection(('127.0.0.1', port), timeout=20), server_hostname=hostname))
        try:
            connection.request('GET', f'/api/v1/{catalog}?' + urllib.parse.urlencode(query), headers={'X-Forwarded-Access-Token': token, 'Accept':'application/json'})
            response = connection.getresponse()
            need(response.status == 200, 'authenticated catalog discovery HTTP failure')
            return json.loads(response.read(4*1024*1024)).get('data', {})
        finally: connection.close()
    for catalog in ['model_catalog/models', 'agent_catalog/agents']:
        items, next_token, seen = [], '', set()
        for page in range(20):
            query = {'namespace': regns, 'pageSize': 100}
            if next_token: query['nextPageToken'] = next_token
            result = catalog_page(catalog, query)
            need(isinstance(result.get('items'), list), 'Catalog page has no typed items')
            items.extend(result['items'])
            next_token = result.get('nextPageToken', '')
            need(isinstance(next_token, str), 'Catalog pagination token is invalid')
            if not next_token: break
            need(next_token not in seen, 'Catalog pagination loop detected')
            seen.add(next_token)
        need(not next_token, 'Catalog exceeds bounded discovery pagination')
        need(isinstance(items, list) and len(items) > 0, 'authenticated catalog discovery returned no items: ' + catalog)
        if catalog == 'agent_catalog/agents':
            for name in ['opencode', 'hermes']:
                matches = [item for item in items if item.get('name') == name and item.get('source_id') == 'governed-coding-agents']
                need(len(matches) == 1, 'Reviewed custom agent entry is missing or duplicated')
                need(matches[0].get('displayName') == {'opencode': 'OpenCode', 'hermes': 'Hermes'}[name], 'Custom agent display name differs from reviewed title')
        print('[PASS] Authenticated dashboard ' + catalog + ' discovery returned items')
    print('Scope: installation administrator API probes; actual persona and browser UI acceptance remain separate.')
except Exception as error:
    # Responses, URLs, tokens and subprocess stderr must never leak through error output.
    print('[FAIL] Model discovery: ' + (str(error) if isinstance(error, RuntimeError) else type(error).__name__))
    raise SystemExit(1)
finally:
    for process in processes:
        process.terminate()
        try: process.wait(timeout=3)
        except subprocess.TimeoutExpired: process.kill(); process.wait()
PY
