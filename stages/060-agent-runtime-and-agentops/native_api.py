"""Bounded guarded native API transport; credentials remain in memory."""
from contextlib import contextmanager
import http.client
import json
import os
from pathlib import Path
import socket
import ssl
import subprocess
import time
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[2]


def need(value, message):
    if not value:
        raise RuntimeError(message)


def guarded(kubeconfig):
    path = Path(kubeconfig).resolve()
    need(path.is_file() and not (path.stat().st_mode & 0o077), "Private session input must exist with private permissions")
    script = 'set -euo pipefail; set +x; source "$1/scripts/shared/lib.sh"; REPO_ROOT="${RHOAI_ENV_ROOT:-$1}"; load_env >/dev/null; export KUBECONFIG="$2"; check_oc_logged_in >/dev/null; python3 -c "import os,json; print(json.dumps({k:os.environ[k] for k in (\'KUBECONFIG\',\'PATH\',\'HOME\',\'RHOAI_EXPECTED_API_SERVER\') if k in os.environ}))"'
    result = subprocess.run(["/bin/bash", "-c", script, "guard", str(ROOT), str(path)], capture_output=True, text=True, timeout=45)
    need(result.returncode == 0, "Project cluster guard rejected session")
    return {**os.environ, **json.loads(result.stdout)}


def oc(env, *args):
    result = subprocess.run(["oc", "--request-timeout=10s", *args], env=env, capture_output=True, text=True, timeout=25)
    need(result.returncode == 0, "Guarded native API read failed")
    return result.stdout.strip()


def persona(kubeconfig, expected):
    env = guarded(kubeconfig)
    need(oc(env, "whoami") == expected, "Session is not the exact requested persona")
    return env, oc(env, "whoami", "-t")


@contextmanager
def service_transport(env, service, namespace, port, uri, ca, auth_header="Authorization"):
    address = urlparse(uri)
    need(address.scheme == "https" and address.hostname and not address.username and not address.password and not address.query and not address.fragment, "Native service address must be credential-free HTTPS")
    context = ssl.create_default_context(cadata=ca)
    need(auth_header in ('Authorization', 'X-Forwarded-Access-Token'), 'Unreviewed native authentication header')
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        local = reserved.getsockname()[1]
    forward = subprocess.Popen(["oc", "--request-timeout=10s", "port-forward", "-n", namespace, "service/" + service, f"{local}:{port}", "--address=127.0.0.1"], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    class NativeHTTPS(http.client.HTTPSConnection):
        def connect(self):
            self.sock = context.wrap_socket(socket.create_connection(("127.0.0.1", local), self.timeout), server_hostname=address.hostname)
    try:
        end = time.monotonic() + 20
        while True:
            need(forward.poll() is None and time.monotonic() < end, "Native service tunnel unavailable")
            try:
                with socket.create_connection(("127.0.0.1", local), timeout=.2):
                    break
            except OSError:
                time.sleep(.1)
        def request(method, path, token=None, workspace=None, body=None):
            need(path.startswith("/") and not path.startswith("//"), "Native API path is invalid")
            headers = {"Accept": "application/json", "Content-Type": "application/json"}
            if token is not None:
                headers[auth_header] = ('Bearer ' if auth_header == 'Authorization' else '') + token
            if workspace is not None:
                headers["X-MLFLOW-WORKSPACE"] = workspace
            connection = NativeHTTPS(address.hostname, timeout=20, context=context)
            try:
                connection.request(method, address.path.rstrip("/") + path, json.dumps(body) if body is not None else None, headers)
                response = connection.getresponse()
                data = response.read(2 * 1024 * 1024 + 1)
                need(len(data) <= 2 * 1024 * 1024, "Native API response exceeds limit")
                try:
                    payload = json.loads(data) if data else None
                except ValueError:
                    payload = None
                # Never return raw errors, URLs or credential-bearing headers.
                return response.status, payload
            finally:
                connection.close()
        yield request
    finally:
        forward.terminate()
        try:
            forward.wait(timeout=5)
        except subprocess.TimeoutExpired:
            forward.kill()
            forward.wait(timeout=5)


def private_receipt(path, data):
    destination = Path(path)
    descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, "w") as stream:
        json.dump(data, stream, indent=2)
        stream.write("\n")


@contextmanager
def native_gateway(env, cli, persona_home=None):
    """Pinned native CLI over an owned TLS tunnel; no credential output."""
    import base64
    import tempfile
    import shutil
    import urllib.request
    import urllib.parse
    from types import SimpleNamespace
    issuer = json.loads(oc(env, 'get', 'configmap', 'openshell-identity', '-n', 'openshell', '-o', 'json'))['data']['issuer']
    need(issuer.startswith('https://') and issuer.endswith('/realms/openshell'), 'Unexpected native issuer')
    with socket.socket() as reserved:
        reserved.bind(('127.0.0.1', 0)); port = reserved.getsockname()[1]
    forward = subprocess.Popen(['oc', '--request-timeout=10s', 'port-forward', 'svc/openshell', f'{port}:8080', '-n', 'openshell', '--address=127.0.0.1'], env=env, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    try:
        end = time.monotonic() + 15
        while True:
            need(forward.poll() is None and time.monotonic() < end, 'Native gateway tunnel unavailable')
            try:
                with socket.create_connection(('127.0.0.1', port), timeout=.2): break
            except OSError: time.sleep(.2)
        with tempfile.TemporaryDirectory(prefix='native-opencode-') as home:
            directory = Path(home) / 'openshell/gateways/openshell'
            if persona_home:
                source = Path(persona_home) / 'openshell/gateways/openshell'
                need(source.is_dir(), 'Genuine native persona session is missing')
                shutil.copytree(source, directory)
                metadata = json.loads((directory / 'metadata.json').read_text())
                need(metadata.get('oidc_issuer') == issuer and metadata.get('oidc_client_id') == 'openshell-cli', 'Foreign native persona session')
            else:
                (directory / 'mtls').mkdir(parents=True)
                metadata = {'name':'openshell','is_remote':True,'auth_mode':'oidc','oidc_issuer':issuer,'oidc_client_id':'openshell-bootstrap','oidc_audience':'openshell-gateway'}
            metadata.update(gateway_endpoint=f'https://127.0.0.1:{port}', gateway_port=port)
            (directory / 'metadata.json').write_text(json.dumps(metadata))
            (Path(home) / 'openshell/active_gateway').write_text('openshell')
            (directory / 'mtls/ca.crt').write_bytes(base64.b64decode(oc(env, 'get', 'secret', 'openshell-server-tls', '-n', 'openshell', '-o', r'jsonpath={.data.ca\.crt}')))
            expiration = [0]
            def refresh():
                if persona_home or time.time() < expiration[0] - 45: return
                secret = json.loads(oc(env, 'get', 'secret', 'openshell-auth', '-n', 'keycloak', '-o', 'json'))
                data = urllib.parse.urlencode({'grant_type':'client_credentials','client_id':'openshell-bootstrap','client_secret':base64.b64decode(secret['data']['bootstrap-client-secret']).decode()}).encode()
                with urllib.request.urlopen(urllib.request.Request(issuer+'/protocol/openid-connect/token', data=data), timeout=15) as response: token = json.load(response)['access_token']
                claims = json.loads(base64.urlsafe_b64decode(token.split('.')[1]+'='*(-len(token.split('.')[1])%4)))
                need(claims.get('iss') == issuer and 'openshell-platform-admin' in claims.get('realm_access', {}).get('roles', []), 'Native bootstrap identity differs')
                expiration[0] = claims['exp']
                credential = directory / 'oidc_token.json'
                credential.write_text(json.dumps({'access_token':token,'expires_at':claims['exp'],'issuer':issuer,'client_id':'openshell-bootstrap'})); credential.chmod(0o600)
            refresh()
            def command(arguments, workspace=None):
                return [str(cli),'--gateway','openshell'] + (['--workspace',workspace] if workspace else []) + arguments
            session_env = dict(env, XDG_CONFIG_HOME=home)
            def run(arguments, workspace=None, credentials=None, structured=True, timeout=30):
                refresh()
                result = subprocess.run(command(arguments,workspace), env=dict(session_env, **(credentials or {})), capture_output=True, text=True, timeout=timeout)
                need(result.returncode == 0, 'Bounded native operation failed: '+arguments[0]+' '+arguments[1]+'; raw errors/credentials suppressed')
                return json.loads(result.stdout) if structured else None
            session = SimpleNamespace(run=run, command=command, env=session_env, identity_verified=False)
            try:
                yield session
            finally:
                if persona_home and session.identity_verified:
                    target = Path(persona_home) / 'openshell/gateways/openshell/oidc_token.json'
                    need(target.is_file() and not target.is_symlink() and target.stat().st_mode & 0o077 == 0, 'Unsafe original native credential path')
                    pending = target.with_suffix('.refresh-pending')
                    descriptor = os.open(pending, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
                    with os.fdopen(descriptor, 'wb') as stream: stream.write((directory/'oidc_token.json').read_bytes())
                    pending.replace(target)

    finally:
        forward.terminate()
        try: forward.wait(timeout=5)
        except subprocess.TimeoutExpired: forward.kill(); forward.wait(timeout=5)


def owned_sandbox_identity(env, native, name, workspace, image, running=True):
    """Read only exact native Sandbox/Pod/PVC identity and restricted workload image."""
    sid = native['id']
    need(native.get('name')==name and native.get('workspace')==workspace, 'Owned native name/workspace differs')
    if running:
        if native.get('phase') in ('Starting', 'Provisioning'):
            raise RuntimeError('Owned native sandbox is starting')
        need(native.get('phase') == 'Ready', 'Owned native sandbox is not Ready; terminal or unexpected lifecycle state')
    else:
        need(native.get('phase') == 'Stopped', 'Owned native sandbox did not reach Stopped')
    resources = json.loads(oc(env, 'get', 'sandboxes', '-n', workspace, '-o', 'json'))
    matches = [r for r in resources['items'] if r['metadata'].get('labels', {}).get('openshell.ai/sandbox-id') == sid]
    need(len(matches) == 1, 'Exact owned Kubernetes Sandbox is ambiguous')
    resource = matches[0]
    pods = json.loads(oc(env, 'get', 'pods', '-n', workspace, '-o', 'json'))['items']
    pods = [p for p in pods if any(o.get('uid') == resource['metadata']['uid'] and o.get('controller') for o in p['metadata'].get('ownerReferences', []))]
    if running:
        need(len(pods) == 1 and pods[0]['status']['phase'] == 'Running', 'Owned workload is not Running')
        pod = pods[0]
        need(pod['metadata'].get('annotations', {}).get('openshift.io/scc') == 'restricted-v2' and
             pod['spec'].get('serviceAccountName') == 'openshell-sandbox' and
             pod['spec'].get('automountServiceAccountToken') is False, 'Native restricted workload identity differs')
        agents = [c for c in pod['spec']['containers'] if c.get('name') == 'agent']
        need(len(agents) == 1 and agents[0].get('image') == image, 'Owned immutable workload image differs')
        actual = [c for c in pod['status'].get('containerStatuses', []) if c.get('name') == 'agent']
        need(len(actual) == 1 and actual[0].get('ready') is True, 'Actual agent image is not ready')
        need(actual[0].get('imageID', '').endswith(image.split('@',1)[1]), 'Actual immutable agent image differs')
    else:
        need(not pods, 'Stopped sandbox workload remains')
    claims = resource['spec'].get('volumeClaimTemplates', [])
    need(claims, 'Native sandbox lacks persistent storage')
    pvcs = json.loads(oc(env, 'get', 'pvc', '-n', workspace, '-o', 'json'))['items']
    owned = [p for p in pvcs if any(o.get('uid') == resource['metadata']['uid'] for o in p['metadata'].get('ownerReferences', []))]
    need(len(owned) == len(claims) and all(p['status']['phase'] == 'Bound' for p in owned), 'Owned PVC identity is ambiguous')
    if running:
        mounted = {v['persistentVolumeClaim']['claimName'] for v in pod['spec'].get('volumes', []) if 'persistentVolumeClaim' in v}
        need(mounted == {p['metadata']['name'] for p in owned}, 'Mounted PVC is outside owned persistent storage')
    return {'sandboxUid': resource['metadata']['uid'], 'pvcs': sorted((p['metadata']['name'], p['metadata']['uid']) for p in owned)}
