"""Owner-authenticated MaaS key lifecycle for MTA 8.3 AI operands."""
import base64
import json
import subprocess
import urllib.error
import urllib.request
from pathlib import Path


def oc(*args, data=None):
    result = subprocess.run(['oc', *args], input=None if data is None else json.dumps(data), capture_output=True, text=True, check=True)
    return json.loads(result.stdout) if result.stdout.lstrip().startswith('{') else None


def active_key(row, principal, subscription):
    if row.get('username') != principal or row.get('subscription') != subscription:
        raise ValueError('Foreign MaaS key ownership or subscription')
    status = row.get('status')
    if status not in ('active', 'expired', 'revoked'):
        raise ValueError('Unknown MaaS key status')
    return status == 'active'


def main():
    principal = 'system:serviceaccount:openshift-mta:mta-maas-provisioner'
    sub = 'mta-migration-ai'
    bearer = Path('/var/run/secrets/kubernetes.io/serviceaccount/token').read_text().strip()
    gateway = oc('get', 'gateway.gateway.networking.k8s.io', 'maas-default-gateway', '-n', 'openshift-ingress', '-o', 'json')
    host = next(l['hostname'] for l in gateway['spec']['listeners'] if l['name'] == 'https')
    base = 'https://' + host

    def request(method, path, data=None):
        req = urllib.request.Request(base + '/maas-api/v1/api-keys' + path,
                                     None if data is None else json.dumps(data).encode(),
                                     {'Authorization': 'Bearer ' + bearer, 'Content-Type': 'application/json'}, method=method)
        with urllib.request.urlopen(req, timeout=30) as response:
            return json.load(response)

    try:
        existing = oc('get', 'secret', 'kai-api-keys', '-n', 'openshift-mta', '-o', 'json')
    except subprocess.CalledProcessError as error:
        if '(NotFound)' not in error.stderr: raise
        existing = None
    key = None
    if existing:
        data = existing['data']
        key_id = base64.b64decode(data['MAAS_KEY_ID']).decode()
        # Any network/HTTP/parse failure propagates before minting or revocation.
        row = request('GET', '/' + key_id)
        if active_key(row, principal, sub):
            key = base64.b64decode(data['OPENAI_API_KEY']).decode()
    if key is None:
        row = request('POST', '', {'name': 'mta-8.3-ai', 'subscription': sub})
        key, key_id = row['key'], row['id']
        if not key.startswith('sk-oai-') or not key_id:
            raise ValueError('MaaS did not return a usable key and identity')
        oc('apply', '-f', '-', data={'apiVersion': 'v1', 'kind': 'Secret', 'metadata': {'name': 'kai-api-keys', 'namespace': 'openshift-mta'}, 'stringData': {'OPENAI_API_KEY': key, 'MAAS_KEY_ID': key_id}})
    oc('patch', 'tackle', 'mta', '-n', 'openshift-mta', '--type=merge', '-p', json.dumps({'spec': {'kai_llm_baseurl': base + '/v1'}}))
    oc('patch', 'gateways.konveyor.io', 'maas-qwen', '-n', 'openshift-mta', '--type=merge', '-p', json.dumps({'spec': {'endpoint': base + '/v1'}}))
    print('MTA MaaS credential and native Gateway configured; readiness requires live connection verification')


if __name__ == '__main__': main()
