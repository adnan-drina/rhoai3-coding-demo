#!/usr/bin/env python3
"""Publish one nonsecret Studio MCP entry; preserve all other discovery fields."""
import argparse
import hashlib
import http.client
import json
import os
from pathlib import Path
import re
import socket
import ssl
import subprocess
import sys
import time
from urllib.parse import urlencode, urlparse

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'stages/060-agent-runtime-and-agentops'))
from native_api import guarded, need, oc, persona, private_receipt

APP = '040-governed-models-as-a-service'
NAMESPACE = 'redhat-ods-applications'
CM = 'gen-ai-aa-mcp-servers'
KEY = 'OpenShift-Catalog'
DELEGATION = {'group': '', 'kind': 'ConfigMap', 'name': CM, 'namespace': NAMESPACE,
              'jsonPointers': ['/data/' + KEY]}
DESCRIPTION = 'Read-only OpenShift MCP tools using your own OpenShift session token and project permissions. Secret resources and write operations are denied.'


def get(env, kind, name, namespace, optional=False):
    value = oc(env, 'get', kind, name, '-n', namespace, *(['--ignore-not-found'] if optional else []), '-o', 'json')
    return json.loads(value) if value else None


def app_guard(app, expected):
    spec = app['spec']; source = spec['source']; status = app.get('status', {})
    need(not app['metadata'].get('ownerReferences') and not app['metadata'].get('deletionTimestamp') and not app.get('operation'), 'Stage040 Application is foreign, terminating or busy')
    need(spec.get('project') == 'rhoai-demo' and not spec.get('sources') and source.get('repoURL') == 'https://github.com/adnan-drina/rhoai3-coding-demo.git' and source.get('path') == 'gitops/stages/' + APP + '/base' and spec.get('destination') == {'server': 'https://kubernetes.default.svc', 'namespace': 'openshift-gitops'}, 'Stage040 Application identity differs')
    revision = source.get('targetRevision', '')
    need(isinstance(expected, str) and re.fullmatch('[0-9a-f]{40}', expected) and revision == expected, 'Stage040 source differs from supplied reviewed revision')
    operation = status.get('operationState', {}); result = operation.get('syncResult', {})
    need(status.get('sync', {}).get('status') == 'Synced' and status['sync'].get('revision') == revision and status.get('health', {}).get('status') == 'Healthy' and operation.get('phase') == 'Succeeded' and result.get('revision') == revision and result.get('source', {}).get('repoURL') == source['repoURL'] and result['source'].get('path') == source['path'] and result['source'].get('targetRevision') == revision, 'Stage040 current reconciliation is not qualified')
    need('RespectIgnoreDifferences=true' in spec.get('syncPolicy', {}).get('syncOptions', []), 'Exact field preservation is unavailable')


def patch(env, kind, name, namespace, before, changes):
    payload = [{'op': 'test', 'path': '/metadata/uid', 'value': before['metadata']['uid']},
               {'op': 'test', 'path': '/metadata/resourceVersion', 'value': before['metadata']['resourceVersion']}] + changes
    result = subprocess.run(['oc', '--request-timeout=10s', 'patch', kind, name, '-n', namespace, '--type=json', '--patch-file=/dev/stdin', '-o', 'json'], input=json.dumps(payload), env=env, capture_output=True, text=True, timeout=25)
    need(result.returncode == 0, 'Exact owned patch failed; response suppressed')
    return json.loads(result.stdout)


def desired(env, expected):
    backend = get(env, 'applications.argoproj.io', 'agent-tools', 'openshift-gitops', True)
    if backend is None:
        return None
    revision = backend['spec']['source']['targetRevision']
    need(isinstance(expected, str) and re.fullmatch('[0-9a-f]{40}', expected) and revision == expected, 'Stage060 source differs from supplied reviewed revision')
    result = subprocess.run([sys.executable, str(ROOT / 'stages/060-agent-runtime-and-agentops/validate-native-mcp.py')], env={**env, 'RHOAI_STAGE060_EXPECTED_REVISION': revision}, capture_output=True, text=True, timeout=60)
    need(result.returncode == 0, 'Current catalog native ownership/configuration/readiness gate failed')
    route = get(env, 'route', 'openshift-mcp-server', 'mcp-servers')
    host = route['spec'].get('host', '')
    need(re.fullmatch('[a-z0-9.-]+', host), 'Qualified Route host is absent')
    value = {'url': 'https://' + host + '/mcp', 'transport': 'streamable-http', 'description': DESCRIPTION}
    parsed = urlparse(value['url'])
    need(parsed.scheme == 'https' and not parsed.username and not parsed.query and not parsed.fragment, 'Endpoint is not credential-free HTTPS')
    return value


def journal(path, identity):
    need(not path.is_symlink(), 'Ownership journal cannot be a symlink')
    path.parent.mkdir(mode=0o700, parents=True, exist_ok=True)
    need(not path.parent.stat().st_mode & 0o077, 'Ownership journal directory must be private')
    if path.exists():
        need(not path.stat().st_mode & 0o077 and json.loads(path.read_text()) == identity, 'Retained Studio field ownership differs')
        return True
    private_receipt(path, identity)
    return False


def publish(args, env):
    value = desired(env, args.expected_stage060_revision)
    if value is None:
        need(args.defer_if_absent, 'Stage060 catalog runtime is absent')
        print('DEFERRED Studio catalog entry: deploy and qualify the separately owned Stage060 runtime first.')
        return None
    app = get(env, 'applications.argoproj.io', APP, 'openshift-gitops'); app_guard(app, args.expected_stage040_revision)
    cm = get(env, 'configmap', CM, NAMESPACE)
    need(not cm['metadata'].get('ownerReferences') and not cm['metadata'].get('deletionTimestamp') and cm['metadata'].get('annotations', {}).get('argocd.argoproj.io/tracking-id') == APP + ':/ConfigMap:' + NAMESPACE + '/' + CM, 'Studio discovery ConfigMap is not the exact Stage040 input')
    old = cm.get('data', {}); need('OpenShift-MCP' in old, 'Retained legacy discovery entry is absent')
    if DELEGATION not in app['spec'].get('ignoreDifferences', []):
        need(args.delegate and not args.validate, 'Exact Studio field delegation is absent')
        before = app['spec']
        app = patch(env, 'applications.argoproj.io', APP, 'openshift-gitops', app,
                    [{'op': 'test', 'path': '/spec', 'value': before}, {'op': 'add', 'path': '/spec/ignoreDifferences', 'value': before.get('ignoreDifferences', []) + [DELEGATION]}])
        need(app['spec'] == {**before, 'ignoreDifferences': before.get('ignoreDifferences', []) + [DELEGATION]}, 'Unexpected Application change')
    encoded = json.dumps(value, sort_keys=True, separators=(',', ':'))
    identity = {'application': APP, 'cm_uid': cm['metadata']['uid'], 'key': KEY, 'value_sha256': hashlib.sha256(encoded.encode()).hexdigest()}
    path = Path(args.state).expanduser() if args.state else Path.home() / '.local/state/rhoai3-coding-demo/studio-mcp' / (cm['metadata']['uid'] + '.json')
    if args.validate:
        need(KEY in old and json.loads(old[KEY]) == value, 'Studio catalog field is missing or drifted')
        need(path.exists(), 'Retained Studio field journal is absent')
        journal(path, identity)
        print('PASS Exact Studio catalog configuration; session authentication is separate.')
        return value
    prior = path.exists()
    need(KEY not in old or prior, 'Existing Studio catalog field has no retained ownership journal')
    journal(path, identity)
    if KEY in old:
        need(json.loads(old[KEY]) == value, 'Existing Studio catalog field differs; no overwrite permitted')
        print('PASS Studio catalog publication repeat was a no-op.')
    else:
        after = patch(env, 'configmap', CM, NAMESPACE, cm, [{'op': 'test', 'path': '/data', 'value': old}, {'op': 'add', 'path': '/data/' + KEY, 'value': encoded}])
        need(after['metadata']['uid'] == cm['metadata']['uid'] and after['data'] == {**old, KEY: encoded}, 'Unexpected discovery ConfigMap change')
        print('PASS Added the single nonsecret Studio catalog field; legacy entries retained.')
    return value


def main():
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument('--bootstrap-kubeconfig', default=os.environ.get('KUBECONFIG'))
    p.add_argument('--state', default=os.environ.get('RHOAI_STUDIO_MCP_STATE'))
    p.add_argument('--expected-stage040-revision', default=os.environ.get('RHOAI_STAGE040_EXPECTED_REVISION'))
    p.add_argument('--expected-stage060-revision', default=os.environ.get('RHOAI_STAGE060_EXPECTED_REVISION'))
    p.add_argument('--delegate', action='store_true', help='Initial exact existing-Application field handoff; no reconciliation')
    p.add_argument('--validate', action='store_true')
    p.add_argument('--defer-if-absent', action='store_true')
    args = p.parse_args(); need(args.bootstrap_kubeconfig, 'Supply the guarded project kubeconfig')
    publish(args, guarded(args.bootstrap_kubeconfig))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('FAIL ' + (str(error) if isinstance(error, RuntimeError) else 'Studio publication input could not be interpreted'))
        sys.exit(1)
