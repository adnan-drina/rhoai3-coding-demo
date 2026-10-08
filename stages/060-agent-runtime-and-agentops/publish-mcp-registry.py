#!/usr/bin/env python3
"""Publish catalog metadata first; publish an HTTPS endpoint only after qualification."""
import argparse
import hashlib
import json
import os
import re
import subprocess
from pathlib import Path
from urllib.parse import quote, urlparse

from native_api import guarded, need, oc, persona, service_transport

ROOT = Path(__file__).resolve().parents[2]
BASE = '/api/3.0/mlflow/mcp-servers'
WORKSPACE = 'demo-sandbox'
DESCRIPTION = 'Red Hat catalog OpenShift MCP Server 0.4; governed demo deployment. Local registry identity mapping; catalog provenance retained in version source.'


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'))


def endpoint_identity(record):
    # The API enriches GET with the referenced version's current tools/status.
    return {k: v for k, v in record.items() if k not in ('tools', 'resolved_version')}


def tool_metadata(tools):
    # Typed native responses materialize absent optional fields as JSON null.
    return sorted(({k: v for k, v in tool.items() if v is not None} for tool in tools), key=lambda tool: tool['name'])


def save(path, state):
    temporary = path.with_suffix('.pending')
    fd = os.open(temporary, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(fd, 'w') as stream:
        json.dump(state, stream, indent=2)
        stream.write('\n')
    os.replace(temporary, path)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--bootstrap-kubeconfig', required=True)
    parser.add_argument('--admin-kubeconfig', required=True)
    parser.add_argument('--state', required=True, help='Private persistent ownership receipt; retain for repeat deployment')
    parser.add_argument('--qualification', help='Private endpoint qualification receipt; absent means metadata only')
    args = parser.parse_args()
    statepath = Path(args.state)
    need(statepath.parent.is_dir() and not statepath.parent.stat().st_mode & 0o077, 'Ownership receipt directory must be private')
    need(not statepath.is_symlink(), 'Ownership receipt must not be a symlink')
    if statepath.exists():
        need(not statepath.stat().st_mode & 0o077, 'Ownership receipt must be private')
        state = json.loads(statepath.read_text())
    else:
        state = {}
        save(statepath, state)  # Reserve recovery record before any native write.
    pin = json.loads((ROOT / 'gitops/stages/060-agent-runtime-and-agentops/native-mcp/catalog-source.json').read_text())
    name, version = pin['registry_name'], pin['registry_version']
    # Native version.source is VARCHAR(512); full provenance belongs in JSON.
    source = canonical({'catalog': pin['catalog'], 'source_revision': pin['source_revision']})
    need(len(source) <= 512, 'Native provenance source exceeds its documented storage limit')
    serverjson = {'name': name, 'version': version, 'title': 'OpenShift MCP Server',
                  'description': DESCRIPTION, 'repository': {'url': pin['source_repository'], 'source': 'github'},
                  'packages': [{'registryType': 'oci', 'identifier': pin['image'], 'transport': {'type': 'streamable-http'}}],
                  '_meta': {'demo.rhoai.io/catalog-provenance': pin}}
    expectedhash = hashlib.sha256(canonical(serverjson).encode()).hexdigest()
    need(not state or (state.get('name') == name and state.get('workspace') == WORKSPACE and state.get('spec_hash') == expectedhash), 'Saved registry identity/spec differs')
    bootstrap = guarded(args.bootstrap_kubeconfig)
    _, token = persona(args.admin_kubeconfig, 'ai-admin')
    mlflow = json.loads(oc(bootstrap, 'get', 'mlflows.mlflow.opendatahub.io', 'mlflow', '-o', 'json'))
    ca = json.loads(oc(bootstrap, 'get', 'configmap', 'service-ca', '-n', 'openshift-config-managed', '-o', 'json'))['data']['ca-bundle.crt']
    entitypath = BASE + '/' + quote(name, safe='')
    with service_transport(bootstrap, 'mlflow', 'redhat-ods-applications', 8443, mlflow['status']['address']['url'], ca) as request:
        def call(method, path, body=None):
            return request(method, path, token, WORKSPACE, body)
        code, entity = call('GET', entitypath)
        if code == 404:
            need(not state.get('server'), 'Previously owned registry entity disappeared; refusing silent recreation')
            code, entity = call('POST', BASE, {'name': name, 'description': DESCRIPTION})
            need(code in (200, 201) and isinstance(entity, dict), 'Native registry creation failed; no ownership inferred')
            need(entity.get('name') == name and entity.get('workspace') == WORKSPACE and isinstance(entity.get('creation_timestamp'), int), 'Native creation identity missing')
            state.update(name=name, workspace=WORKSPACE, spec_hash=expectedhash,
                         server={'creation_timestamp': entity['creation_timestamp'], 'created_by': entity.get('created_by')})
            save(statepath, state)
        else:
            need(code == 200 and state.get('server') is not None, 'Existing registry entity has no owned creation receipt; refusing adoption')
        need(entity.get('name') == name and entity.get('workspace') == WORKSPACE and entity.get('description') == DESCRIPTION and
             all(entity.get(k) == v for k, v in state['server'].items()), 'Registry entity ownership/content changed')
        versionpath = entitypath + '/versions/' + quote(version, safe='')
        code, record = call('GET', versionpath)
        if code == 404:
            need('version_created' not in state, 'Previously owned version disappeared; refusing silent recreation')
            code, record = call('POST', entitypath + '/versions', {'server_json': serverjson, 'source': source, 'status': 'draft', 'tools': []})
            if code not in (200, 201):
                errorcode = record.get('error_code', 'unknown') if isinstance(record, dict) else 'unknown'
                errorcode = errorcode if isinstance(errorcode, str) and re.fullmatch(r'[A-Za-z0-9_.-]{1,100}', errorcode) else 'unknown'
                state['last_failure'] = {'http': code, 'error_code': errorcode, 'source_length': len(source)}
                save(statepath, state)
                raise RuntimeError('Native version creation failed (HTTP %s; %s); private recovery receipt retained' % (code, errorcode))
            need(isinstance(record, dict) and isinstance(record.get('creation_timestamp'), int), 'Native version creation identity missing')
            state['version_created'] = record['creation_timestamp']
            save(statepath, state)
        else:
            need(code == 200 and 'version_created' in state, 'Existing version has no owned receipt')
        need(record.get('name') == name and record.get('version') == version and record.get('workspace') == WORKSPACE and
             record.get('source') == source and record.get('server_json') == serverjson and
             record.get('creation_timestamp') == state['version_created'], 'Catalog version provenance/content changed')
        if args.qualification:
            proof = json.loads(Path(args.qualification).read_text())
            need(proof.get('passed') is True and proof.get('image') == pin['image'] and proof.get('server') == 'openshift-mcp-server' and proof.get('namespace') == WORKSPACE,
                 'Endpoint qualification identity differs')
            checks = proof.get('checks', {})
            need(all(checks.get(k) is True for k in ('https_verified', 'http_redirect', 'caller_read', 'foreign_denied', 'write_denied', 'secret_denied', 'missing_denied', 'invalid_denied', 'alternating_personas', 'sa_unprivileged')), 'Endpoint security acceptance incomplete')
            validation = subprocess.run(['python3', str(ROOT / 'stages/060-agent-runtime-and-agentops/validate-native-mcp.py')], env=bootstrap, capture_output=True, timeout=90)
            need(validation.returncode == 0, 'Current native source/readiness/security validation failed')
            server = json.loads(oc(bootstrap, 'get', 'mcpserver.mcp.x-k8s.io', 'openshift-mcp-server', '-n', WORKSPACE, '-o', 'json'))
            config = json.loads(oc(bootstrap, 'get', 'configmap', 'openshift-mcp-server', '-n', WORKSPACE, '-o', 'json'))
            need(server['metadata']['uid'] == proof['server_uid'] and server['metadata']['generation'] == proof['server_generation'] and
                 hashlib.sha256(canonical(config['data']).encode()).hexdigest() == proof['config_hash'], 'Qualified backend identity/config changed')
            need((record.get('status') == 'draft' and not record.get('tools')) or
                 (record.get('status') == 'active' and tool_metadata(record.get('tools', [])) == tool_metadata(proof['tools'])), 'Current version status/tool metadata changed; refusing overwrite')
            url = proof['endpoint']
            address = urlparse(url)
            need(address.scheme == 'https' and address.hostname and not address.username and not address.password and not address.query and not address.fragment and address.path == '/mcp', 'Endpoint is not credential-free HTTPS')
            route = json.loads(oc(bootstrap, 'get', 'route', 'openshift-mcp-server', '-n', WORKSPACE, '-o', 'json'))
            need(route['metadata']['uid'] == proof['route_uid'] and url == 'https://' + route['spec']['host'] + '/mcp', 'Qualified Route identity changed')
            endpoint = {'server_version': version, 'url': url, 'transport_type': 'streamable-http'}
            code, entries = call('GET', entitypath + '/endpoints')
            need(code == 200 and isinstance(entries, dict) and not entries.get('next_page_token'), 'Endpoint inventory unavailable or incomplete')
            items = entries.get('mcp_access_endpoints')
            need(isinstance(items, list), 'Native endpoint inventory shape differs')
            matching = [x for x in items if all(x.get(k) == v for k, v in endpoint.items())]
            need(len(items) == len(matching) and len(matching) <= 1, 'Foreign/different access endpoint exists; refusing overwrite')
            if matching:
                need(state.get('endpoint') is not None and endpoint_identity(state['endpoint']) == endpoint_identity(matching[0]), 'Existing endpoint has no matching owned creation receipt')
            if not matching:
                need(not state.get('endpoint'), 'Previously owned endpoint disappeared; refusing silent recreation')
                code, created = call('POST', entitypath + '/endpoints', endpoint)
                need(code in (200, 201) and all(created.get(k) == v for k, v in endpoint.items()), 'Native endpoint publication failed')
                state['endpoint'] = created
                save(statepath, state)
            code, record = call('PATCH', versionpath, {'status': 'active', 'tools': proof['tools']})
            need(code == 200 and record.get('status') == 'active' and tool_metadata(record.get('tools', [])) == tool_metadata(proof['tools']), 'Native version activation/tool metadata readback failed')
            state['qualified'] = True
            save(statepath, state)
    print('[PASS] Native catalog metadata' + (' and qualified HTTPS endpoint published' if args.qualification else ' registered as draft; no endpoint advertised'))


if __name__ == '__main__':
    try:
        main()
    except Exception as error:
        print('[FAIL] ' + (str(error) if isinstance(error, RuntimeError) else type(error).__name__))
        raise SystemExit(1)
