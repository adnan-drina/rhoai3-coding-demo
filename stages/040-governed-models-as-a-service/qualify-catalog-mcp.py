#!/usr/bin/env python3
"""Model-free Studio session discovery and bounded caller resource checks."""
import argparse
import base64
from contextlib import contextmanager
import hashlib
import http.client
import importlib.util
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import sys
import time
from urllib.parse import urlencode, urlparse

spec = importlib.util.spec_from_file_location('publication', Path(__file__).with_name('publish-catalog-mcp.py'))
pub = importlib.util.module_from_spec(spec); spec.loader.exec_module(pub)
from native_api import guarded, need, oc, persona, private_receipt


@contextmanager
def bff(env, receipt):
    hostname = 'odh-dashboard-gen-ai-ui.redhat-ods-applications.svc'
    ca = pub.get(env, 'configmap', 'mlflow-service-ca', pub.NAMESPACE)['data']['service-ca.crt']
    context = ssl.create_default_context(cadata=ca)
    with socket.socket() as listener:
        listener.bind(('127.0.0.1', 0)); port = listener.getsockname()[1]
    receipt['owned_forwards_closed'] = False
    process = subprocess.Popen(['oc', 'port-forward', '-n', pub.NAMESPACE, 'service/odh-dashboard-gen-ai-ui', f'{port}:8143', '--address=127.0.0.1'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    class HTTPS(http.client.HTTPSConnection):
        def connect(self):
            self.sock = context.wrap_socket(socket.create_connection(('127.0.0.1', port), self.timeout), server_hostname=hostname)
    try:
        end = time.monotonic() + 15
        while True:
            need(process.poll() is None and time.monotonic() < end, 'Owned Studio forward unavailable')
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.2): break
            except OSError: time.sleep(.2)
        def request(path, caller, mcp_token=None):
            headers = {'X-Forwarded-Access-Token': caller, 'Accept': 'application/json'}
            if mcp_token is not None: headers['X-MCP-Bearer'] = 'Bearer ' + mcp_token
            time.sleep(1)
            connection = HTTPS(hostname, timeout=30, context=context)
            try:
                connection.request('GET', path, headers=headers); response = connection.getresponse(); raw = response.read(1048577)
                need(len(raw) <= 1048576, 'Studio response exceeds bound')
                try: payload = json.loads(raw)
                except ValueError: payload = None
                return response.status, payload
            finally: connection.close()
        yield request
    finally:
        process.terminate()
        try: process.wait(timeout=5)
        except subprocess.TimeoutExpired: process.kill(); process.wait(timeout=5)
        receipt['owned_forwards_closed'] = process.poll() is not None


def denied(code, payload):
    if code in (401, 403): return True
    text = json.dumps(payload).lower()
    return isinstance(payload, dict) and ('error' in payload or payload.get('result', {}).get('isError') is True) and any(w in text for w in ('forbidden', 'the server has asked for the client to provide credentials'))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bootstrap-kubeconfig', required=True)
    parser.add_argument('--admin-kubeconfig', required=True)
    parser.add_argument('--developer-kubeconfig', required=True)
    parser.add_argument('--receipt', required=True)
    parser.add_argument('--state', default=os.environ.get('RHOAI_STUDIO_MCP_STATE'))
    parser.add_argument('--expected-stage040-revision', default=os.environ.get('RHOAI_STAGE040_EXPECTED_REVISION'))
    parser.add_argument('--expected-stage060-revision', default=os.environ.get('RHOAI_STAGE060_EXPECTED_REVISION'))
    args = parser.parse_args(); env = guarded(args.bootstrap_kubeconfig)
    args.validate = True; args.delegate = False; args.defer_if_absent = False
    value = pub.publish(args, env); endpoint = value['url']; receipt = {'passed': False, 'checks': {}, 'personas': {}}
    try:
        tokens = {u: persona(path, u)[1] for u, path in [('ai-admin', args.admin_kubeconfig), ('ai-developer', args.developer_kubeconfig)]}
        with bff(env, receipt) as request:
            for user, token in tokens.items():
                code, payload = request('/api/v1/aa/mcps?' + urlencode({'namespace': 'demo-sandbox'}), token)
                need(code == 200 and isinstance(payload, dict), 'Native Studio discovery failed')
                servers = payload.get('data', {}).get('servers', [])
                need(any(s.get('name') == pub.KEY and s.get('url') == endpoint for s in servers) and any(s.get('name') == 'OpenShift-MCP' for s in servers), 'Additive and legacy Studio entries are not both discoverable')
                paths = {kind: '/api/v1/mcp/' + kind + '?' + urlencode({'namespace': 'demo-sandbox', 'server_url': endpoint}) for kind in ('status', 'tools')}
                code, payload = request(paths['status'], token, token)
                need(code == 200 and payload.get('data', {}).get('status') == 'connected', 'Genuine per-session Studio status is not connected')
                code, payload = request(paths['tools'], token, token)
                data = payload.get('data', {}) if isinstance(payload, dict) else {}; tools = data.get('tools', [])
                need(code == 200 and data.get('status') == 'success' and len(tools) == 13 and {'pods_get', 'pods_list_in_namespace'} <= {t['name'] for t in tools}, 'Native Studio tool inventory differs')
                receipt['personas'][user] = {'discovery_http': 200, 'status': 'connected', 'tools_http': 200, 'tools_count': 13}
            code, payload = request(paths['status'], tokens['ai-developer'])
            data = payload.get('data', {}) if isinstance(payload, dict) else {}
            need(code in (401, 403) or (data.get('status') == 'error' and data.get('error_details', {}).get('code') == 'unauthorized') or (isinstance(payload, dict) and payload.get('error', {}).get('code') == 'unauthorized'), 'Missing per-session MCP bearer did not produce an explicit authorization error')
            receipt['checks']['missing_session_bearer_rejected'] = True
        # Public certificate only; never read the router's private key.
        crt = base64.b64decode(oc(env, 'get', 'secret', 'router-ca', '-n', 'openshift-ingress-operator', '-o', 'jsonpath={.data.tls\\.crt}')).decode()
        context = ssl.create_default_context(); context.load_verify_locations(cadata=crt); parsed = urlparse(endpoint)
        def rpc(namespace, token, ident):
            time.sleep(.6); connection = http.client.HTTPSConnection(parsed.hostname, timeout=20, context=context)
            try:
                body = {'jsonrpc': '2.0', 'id': ident, 'method': 'tools/call', 'params': {'name': 'pods_list_in_namespace', 'arguments': {'namespace': namespace}}}
                connection.request('POST', parsed.path, json.dumps(body), {'Authorization': 'Bearer ' + token, 'Content-Type': 'application/json', 'Accept': 'application/json, text/event-stream', 'MCP-Protocol-Version': '2025-03-26'})
                response = connection.getresponse(); raw = response.read(1048577); need(len(raw) <= 1048576, 'MCP response exceeds bound')
                try: payload = json.loads(raw)
                except ValueError: payload = next((json.loads(line[6:]) for line in raw.decode().splitlines() if line.startswith('data: ') and json.loads(line[6:]).get('id') == ident), None)
                return response.status, payload
            finally: connection.close()
        code, payload = rpc('demo-sandbox', tokens['ai-developer'], 1)
        need(code == 200 and isinstance(payload, dict) and 'result' in payload and not payload['result'].get('isError'), 'Developer own-project direct read failed')
        code, payload = rpc('mcp-servers', tokens['ai-developer'], 2); need(denied(code, payload), 'Developer hosting direct read was not forbidden')
        code, payload = rpc('demo-sandbox', 'synthetic-invalid-studio-qualification', 3); need(denied(code, payload), 'Invalid bearer resource call was not rejected')
        receipt['checks'].update(verified_bff_tls=True, verified_direct_tls=True, both_session_tool_lists=True, developer_workload_read=True, developer_hosting_denied=True, invalid_resource_bearer_denied=True)
        receipt['passed'] = True
    except Exception as error:
        receipt['failure'] = str(error) if isinstance(error, RuntimeError) else 'Bounded native Studio qualification did not complete'
        raise
    finally:
        private_receipt(args.receipt, receipt)
    print('PASS Genuine Studio session discovery/tools and bounded direct caller permission checks. Browser/model-generated invocation is separate.')


if __name__ == '__main__':
    try: main()
    except Exception as error:
        print('FAIL ' + (str(error) if isinstance(error, RuntimeError) else 'Bounded native qualification did not complete'))
        sys.exit(1)
